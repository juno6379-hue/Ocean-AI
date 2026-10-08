"""Read-only thirteen-stage development board; claims do not grant authority."""
import hashlib
import json
import re
from pathlib import Path

from app.rag.ingestion_recovery import backlog_snapshot, guarded, now, sha_file

CANONICAL_DOCUMENT_LEDGER = Path("C:/AI_Observation/ocean-ai-platform/backend/app/data/document_pipeline/ingestion.sqlite3")
STAGES = [
    (1, "운영 기반·백업과 복구"), (2, "원천·Parquet 보존과 과거 정산"),
    (3, "원천 의미·단위·시각 계약"), (4, "물리 센서 기간·사건 연결"),
    (5, "문서 적재·검색 검증"), (6, "규칙 QC 실행"), (7, "AI 분석과 고정 평가"),
    (8, "근거 융합 Recommendation"), (9, "Human Approval 중단·재개"),
    (10, "불변 Dataset·분할·계보"), (11, "업무별 모델 비교·독립 검토"),
    (12, "모델 등록·배포·재학습"), (13, "통합 검증·문서와 운영 이관"),
]
AXES = {
    "implementation": {"IMPLEMENTED", "PARTIAL", "UNKNOWN"},
    "verification": {"VERIFIED", "PARTIAL", "FAILED", "UNKNOWN"},
    "data_readiness": {"READY", "PARTIAL", "BLOCKED", "UNKNOWN"},
    "approval": {"APPROVED", "PENDING", "NOT_APPLICABLE", "UNKNOWN"},
    "operational_status": {"OPERATING", "ANALYSIS_ONLY", "BLOCKED", "NOT_STARTED", "UNKNOWN"},
}


class DevelopmentStageReviewError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def get_development_stage_review(artifact_root, *, ledger_path=None):
    try:
        root = guarded(artifact_root)
    except (ValueError,OSError) as error:
        raise DevelopmentStageReviewError('ARTIFACT_ROOT_UNSAFE') from error
    candidates = [root / "stage-index.json", root / "identity-events" / "stage-index.json"]
    index_path = next((p for p in candidates if p.is_file()), None)
    index_error = None
    try:
        if index_path:
            index_path = guarded(index_path, root)
            if index_path.stat().st_size > 1024 * 1024:
                raise ValueError("STAGE_INDEX_TOO_LARGE")
        if index_path:
            before = index_path.stat()
            with index_path.open('rb') as stream:raw=stream.read(1024*1024+1)
            after = index_path.stat()
            if len(raw)>1024*1024 or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
                raise ValueError('STAGE_INDEX_CHANGED_DURING_READ')
            index=json.loads(raw)
        else:index={}
        if not isinstance(index, dict) or not isinstance(index.get("stages", []), list):
            raise ValueError("STAGE_INDEX_SCHEMA_INVALID")
    except (ValueError, OSError) as error:
        index, index_error = {}, "STAGE_INDEX_UNREADABLE"
    declared = index.get("stages", [])
    items = {}
    duplicates = set()
    if len(declared) > 13:
        index_error = "STAGE_INDEX_TOO_MANY_ENTRIES"
        declared = []
    for row in declared:
        if not isinstance(row, dict) or type(row.get("stage_id")) is not int or not 1 <= row["stage_id"] <= 13:
            index_error = "STAGE_INDEX_INVALID_ENTRY"
            continue
        if row["stage_id"] in items:
            duplicates.add(row["stage_id"])
        items[row["stage_id"]] = row
    verified_cache = {}
    stages = []
    for stage_id, title in STAGES:
        stage = {"stage_id": stage_id, "title": title, **{k: "UNKNOWN" for k in AXES},
                 "reasons": [], "evidence": [], "next_required": []}
        spec = items.get(stage_id)
        if not spec:
            stage["reasons"] = [index_error or "NO_VERIFIABLE_STAGE_RECEIPT"]
            stage["next_required"] = ["Publish a bounded validation receipt with exact artifact SHA and remaining work"]
            stages.append(stage)
            continue
        valid = True
        bodies = []
        declared_evidence = spec.get("evidence", [])
        if not isinstance(declared_evidence, list) or len(declared_evidence) > 64 or stage_id in duplicates:
            declared_evidence = []
            valid = False
            stage["reasons"].append("INVALID_OR_DUPLICATE_STAGE_EVIDENCE")
        for entry in declared_evidence:
            if not isinstance(entry, dict):
                stage["evidence"].append({"path": None, "sha256": None, "verified": False, "error": "ARTIFACT_ENTRY_INVALID"})
                valid = False
                continue
            evidence = {"path": entry.get("path"), "sha256": entry.get("sha256"), "verified": False, "error": None}
            try:
                path = guarded(root / entry["path"], root)
                cache_key = (str(path), entry.get("sha256"))
                if not isinstance(entry.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
                    raise ValueError("ARTIFACT_HASH_MISMATCH")
                if cache_key not in verified_cache:
                    before = path.stat()
                    if path.suffix == ".json":
                        if before.st_size > 4 * 1024 * 1024:
                            raise ValueError("RECEIPT_TOO_LARGE")
                        with path.open('rb') as stream:raw=stream.read(4*1024*1024+1)
                        if len(raw)>4*1024*1024:raise ValueError('RECEIPT_TOO_LARGE')
                        verified = hashlib.sha256(raw).hexdigest() == entry["sha256"]
                        body = json.loads(raw)
                    else:
                        verified, body = sha_file(path) == entry["sha256"], None
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                        raise ValueError("ARTIFACT_CHANGED_DURING_READ")
                    verified_cache[cache_key] = (verified, body)
                if not verified_cache[cache_key][0]:
                    raise ValueError("ARTIFACT_HASH_MISMATCH")
                evidence["verified"] = True
                body = verified_cache[cache_key][1]
                if isinstance(body, dict):
                    bodies.append(body)
            except (KeyError, TypeError, ValueError, OSError):
                evidence["error"] = "ARTIFACT_MISSING_INVALID_OR_CHANGED"
                valid = False
            stage["evidence"].append(evidence)
        if not stage["evidence"]:
            valid = False
        stage["reasons"].extend([v[:250] for v in spec.get("reasons", []) if isinstance(v, str)] if isinstance(spec.get("reasons", []), list) else [])
        stage["next_required"] = [v[:350] for v in spec.get("next_required", []) if isinstance(v, str)] if isinstance(spec.get("next_required", []), list) else []
        if valid:
            for key, allowed in AXES.items():
                if isinstance(spec.get(key), str) and spec[key] in allowed:
                    stage[key] = spec[key]
            # Manifest status is a technical claim, not server approval authority.
            if stage["approval"] == "APPROVED":
                stage["approval"] = "UNKNOWN"
                stage["reasons"].append("BODY_APPROVAL_CLAIM_NOT_AN_AUTHORITY_LEDGER")
            if stage["operational_status"] == "OPERATING":
                stage["operational_status"] = "UNKNOWN"
                stage["reasons"].append("BODY_OPERATIONAL_CLAIM_REQUIRES_CURRENT_RUNTIME_AUTHORITY")
            if stage["verification"] == "VERIFIED" and not any(
                b.get("status") == "PASS" and type(b.get("failed")) is int and b["failed"] == 0 and (
                    type(b.get("passed")) is int and b["passed"] > 0 or
                    isinstance(b.get("checks"), list) and len(b["checks"]) > 0 and all(
                        isinstance(c, dict) and c.get("passed") is True and isinstance(c.get("name"), str) for c in b["checks"]))
                for b in bodies):
                stage["verification"] = "PARTIAL"
                stage["reasons"].append("NO_EXACT_PASS_RECEIPT_FOR_COMPLETE_STAGE")
        else:
            stage["verification"] = "FAILED"
            stage["reasons"].append("EVIDENCE_INTEGRITY_FAILED")
        stages.append(stage)
    # Only document counts are read from current canonical state; no write-capable
    # document_pipeline.status/connect_ledger helper is used by this board.
    current = None
    try:
        snap = backlog_snapshot(ledger_path or CANONICAL_DOCUMENT_LEDGER)
        current = {"counts": snap["counts"], "snapshot_sha256": snap["snapshot_sha256"], "checked_at": snap["checked_at"]}
        stage = stages[4]
        if current["counts"].get("PENDING", 0) or current["counts"].get("FAILED", 0):
            stage["data_readiness"] = "PARTIAL"
            stage["operational_status"] = "ANALYSIS_ONLY"
            stage["reasons"].append("CURRENT_DOCUMENT_BACKLOG_REMAINS")
    except Exception:
        # Safe error class only, no connection strings or private source text.
        stages[4]["reasons"].append("CURRENT_DOCUMENT_LEDGER_UNAVAILABLE")
    return {"schema_version": "development-stage-review-v1", "checked_at": now(), "stages": stages,
            "approved": False, "authority": "TECHNICAL_REVIEW_NOT_HUMAN_APPROVAL", "current_document_ingestion": current}
