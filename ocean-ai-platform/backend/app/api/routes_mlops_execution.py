"""Actual actor-authorized protocols, queue, independent review and local serving."""
import hashlib
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import Actor, require_reviewer
from app.core.config import settings
from app.ml.comparison_runner import ComparisonBlocked, DatabaseAuthority, read_json
from app.ml.serving import runtime_root, health, load_candidate, deployment_identity, predict_artifact
from app.ml.protocols import canonical_bytes, validate_protocol
from app.models.domain import ApprovalHistory, ModelRegistry

router = APIRouter()


def blocked(exc):
    return HTTPException(409, {"code": exc.code, "detail": exc.detail, "mutation_performed": False})


def exact_path(path, child):
    from app.ml.comparison_runner import reject_reparse
    reject_reparse(path)
    actual, root = Path(path).resolve(), (runtime_root() / child).resolve()
    if not actual.is_relative_to(root):
        raise ComparisonBlocked("MLOPS_INPUT_OUTSIDE_CONFIGURED_ROOT", child)
    return actual


def loopback_only(request: Request):
    import ipaddress
    try:
        if request.client and ipaddress.ip_address(request.client.host).is_loopback: return
    except ValueError: pass
    raise HTTPException(403, "This serving executor is limited to loopback local pilot clients")


class ProtocolDraft(BaseModel):
    body: dict


class Decision(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED|REVOKED)$")


class ManifestRequest(BaseModel):
    manifest_path: str


class CandidateRequest(BaseModel):
    receipt_path: str
    model_version: str = Field(min_length=1, max_length=80, pattern="^[A-Za-z0-9_.-]+$")


class PredictionRequest(BaseModel):
    scope_key: str
    features: list[float]
    typed_payload: dict | None = None


@router.get("/adapters")
def adapters():
    from app.ml.adapter_registry import adapter_coverage
    return adapter_coverage()


@router.post("/protocols/draft")
def protocol_draft(req: ProtocolDraft, actor: Actor = Depends(require_reviewer)):
    try:
        body = validate_protocol(req.body, req.body.get("role"))
        raw = canonical_bytes(body); sha = hashlib.sha256(raw).hexdigest()
        path = runtime_root() / "protocols" / (sha + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw: raise ComparisonBlocked("IMMUTABLE_PROTOCOL_CHANGED")
        else:
            with path.open("xb") as stream: stream.write(raw)
        return {"status": "DRAFT", "approved": False, "sha256": sha, "path": str(path), "submitted_by": actor.user_id}
    except ComparisonBlocked as exc: raise blocked(exc)


@router.post("/protocols/{sha256}/decision")
def protocol_decision(sha256: str, req: Decision, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    try:
        path = exact_path(runtime_root() / "protocols" / (sha256 + ".json"), "protocols")
        body, actual = read_json(path)
        if actual != sha256 or hashlib.sha256(canonical_bytes(body)).hexdigest() != actual:
            raise ComparisonBlocked("IMMUTABLE_PROTOCOL_HASH_MISMATCH")
        validate_protocol(body, body["role"], for_approval=req.decision == "APPROVED")
        # Keep policy content immutable; decision authority lives in the ledger.
        row = ApprovalHistory(approval_type="MODEL_PROTOCOL", target_id=sha256, approval_status=req.decision,
                              approved_by=actor.user_id, comment="snapshot_sha256=" + sha256)
        db.add(row); db.commit(); db.refresh(row)
        return {"approval_id": row.id, "decision": req.decision, "sha256": sha256, "reviewer_id": actor.user_id}
    except ComparisonBlocked as exc: db.rollback(); raise blocked(exc)


@router.post("/training/enqueue")
def enqueue(req: ManifestRequest, db: Session = Depends(get_db)):
    try:
        if os.environ.get("OCEAN_TRAINING_WORKER_ENABLED", "0") != "1": raise ComparisonBlocked("TRAINING_WORKER_DISABLED")
        from app.ml.job_queue import DurableQueue
        path = exact_path(req.manifest_path, "requests")
        with db.no_autoflush:
            return DurableQueue(runtime_root() / "worker").enqueue(path, DatabaseAuthority(db, settings.DATASET_SNAPSHOT_DIR))
    except ComparisonBlocked as exc: raise blocked(exc)


@router.get("/training/jobs")
def jobs():
    path = runtime_root() / "worker" / "worker-queue.sqlite3"
    if not path.exists(): return {"jobs": [], "queue_initialized": False}
    import sqlite3
    with sqlite3.connect("file:" + path.as_posix() + "?mode=ro", uri=True) as ledger:
        ledger.row_factory = sqlite3.Row
        rows = ledger.execute("SELECT job_id,state,attempts,max_attempts,lease_until,receipt_path,receipt_sha256,reason FROM queue_jobs ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"jobs": [dict(row) for row in rows], "queue_initialized": True}


@router.post("/candidates/review")
def review(req: CandidateRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    try:
        from app.ml.candidate_authority import verified_worker_receipt
        report, sha, _ = verified_worker_receipt(db, req.receipt_path, replay=True)
        if report["acceptance"]["status"] != "PASS": raise ComparisonBlocked("ACCEPTANCE_LIMITS_NOT_PASSED")
        latest = db.query(ApprovalHistory).filter_by(approval_type="MODEL_INDEPENDENT_REVIEW", target_id=req.model_version).order_by(ApprovalHistory.id.desc()).first()
        if latest and latest.comment != "snapshot_sha256=" + sha:
            raise ComparisonBlocked("MODEL_VERSION_BOUND_TO_OTHER_REPORT")
        row = ApprovalHistory(approval_type="MODEL_INDEPENDENT_REVIEW", target_id=req.model_version, approval_status="APPROVED",
                              approved_by=actor.user_id, comment="snapshot_sha256=" + sha)
        db.add(row); db.commit(); db.refresh(row)
        return {"status": "INDEPENDENT_REPLAY_MATCH", "model_version": req.model_version, "approval_id": row.id,
                "report_sha256": sha, "operating_selected": False, "reviewer_id": actor.user_id}
    except ComparisonBlocked as exc: db.rollback(); raise blocked(exc)


@router.post("/candidates/register")
def register(req: CandidateRequest, db: Session = Depends(get_db)):
    try:
        from app.ml.candidate_authority import register_candidate
        model = register_candidate(db, req.receipt_path, req.model_version)
        return {"model_version": model.model_version, "status": model.status, "deployment_status": model.deployment_status}
    except ComparisonBlocked as exc: db.rollback(); raise blocked(exc)


@router.post("/models/{model_version}/decision")
def model_decision(model_version: str, req: Decision, rollback: bool = False, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    try:
        from app.ml.comparison_runner import digest
        model = db.query(ModelRegistry).filter_by(model_version=model_version).with_for_update().first()
        if not model: raise HTTPException(404, "Model version not found")
        _, report, sha = load_candidate(db, model)
        identity = deployment_identity(model, sha, report["artifact_sha256"]); exact = digest(identity)
        row = ApprovalHistory(approval_type="MODEL_ROLLBACK" if rollback else "MODEL_DEPLOY", target_id=model_version,
            approval_status=req.decision, approved_by=actor.user_id, comment="snapshot_sha256=" + exact)
        db.add(row)
        if req.decision == "APPROVED" and not rollback and model.status == "PENDING_APPROVAL": model.status = "APPROVED"
        db.commit(); db.refresh(row)
        return {"approval_id": row.id, "decision": req.decision, "identity": identity, "identity_sha256": exact,
                "serving_started": False, "reviewer_id": actor.user_id}
    except ComparisonBlocked as exc: db.rollback(); raise blocked(exc)


@router.get("/serving/health", dependencies=[Depends(loopback_only)])
def serving_health(scope_key: str | None = None, db: Session = Depends(get_db)):
    try: return health(db, scope_key)
    except ComparisonBlocked as exc: raise blocked(exc)


@router.post("/serving/predict", dependencies=[Depends(loopback_only)])
def serving_predict(req: PredictionRequest, db: Session = Depends(get_db)):
    try:
        import time
        started = time.perf_counter()
        from app.ml.serving import validated_runtime
        probe, artifact = validated_runtime(db, req.scope_key)
        result = predict_artifact(artifact, req.features, req.typed_payload)
        return {"identity": probe["identity"], "prediction": result,
                "scope": "LOOPBACK_PILOT", "this_call_total_ms": (time.perf_counter() - started) * 1000,
                "full_api_p95_status": "NOT_MEASURED", "throughput_status": "NOT_MEASURED"}
    except ComparisonBlocked as exc: raise blocked(exc)
