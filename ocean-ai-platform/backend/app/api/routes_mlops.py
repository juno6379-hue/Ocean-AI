# 파일 역할: 모델 학습·평가·배포 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Literal
import math
from app.core.database import get_db
from app.core.security import Actor, require_reviewer
from app.models.domain import ModelRegistry, RetrainingHistory, AIPredictionResult
from app.services.mlops_readiness import get_mlops_readiness, model_readiness
from pydantic import BaseModel, Field
import datetime
import uuid
import asyncio

router = APIRouter(tags=["MLOps"])

REQUIRED_METRICS = {"precision", "recall", "f1", "auroc", "false_positive_rate", "false_negative_rate", "latency"}

def validate_metrics(metrics: Dict[str, Any], task: str = "CLASSIFICATION"):
    """Validate task-specific metrics without constraining regression errors to [0, 1]."""
    required = {"mae", "rmse", "latency"} if task == "FORECASTING" else REQUIRED_METRICS
    normalized = {str(key).lower(): value for key, value in metrics.items()}
    missing = required - normalized.keys()
    if missing:
        raise HTTPException(422, detail=f"Missing evaluation metrics: {sorted(missing)}")
    for key, value in normalized.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise HTTPException(422, detail=f"{key} must be numeric")
        if isinstance(value, bool) or not math.isfinite(numeric):
            raise HTTPException(422, detail=f"{key} must be finite")
        if task == "FORECASTING":
            if key != "bias" and numeric < 0:
                raise HTTPException(422, detail=f"{key} must be non-negative")
        elif key == "latency":
            if numeric < 0: raise HTTPException(422, "latency must be non-negative")
        elif not 0 <= numeric <= 1:
            raise HTTPException(422, detail=f"{key} must be between 0 and 1")

class ModelRegistrationRequest(BaseModel):
    model_name: str
    model_type: str
    model_version: str
    target_variable: str
    target_task: Literal["CLASSIFICATION", "FORECASTING"] = "CLASSIFICATION"
    dataset_version: str
    feature_version: str
    label_version: str
    preprocessing_version: str
    metrics: Dict[str, Any]
    artifact_path: str = ""
    status: str = "PENDING_APPROVAL"
    comparison_receipt_path: str | None = None

class DeployRequest(BaseModel):
    deployment_target: str = "production"

class CompareRequest(BaseModel):
    champion_version: str
    challenger_version: str

class RetrainRequest(BaseModel):
    model_id: str | None = None
    triggered_by: str = "admin"
    manifest_path: str | None = None
    expected_sha256: str | None = Field(default=None,pattern='^[0-9a-f]{64}$')

@router.get("/summary")
def get_mlops_summary(db: Session = Depends(get_db)):
    models = db.query(ModelRegistry).all()
    readiness = get_mlops_readiness(db)
    by_version = {item["model_version"]: item for item in readiness["models"]}
    
    status_counts = {
        "ACTIVE": 0,
        "VALIDATING": 0,
        "RETRAIN_REQUIRED": 0,
        "PENDING_APPROVAL": 0,
        "ARCHIVED": 0,
        "PRODUCTION": 0
    }
    
    results = []
    for m in models:
        st = m.status or "ARCHIVED"
        if st in status_counts:
            status_counts[st] += 1
        else:
            status_counts[st] = 1
            
        results.append({
            "model_id": str(m.id),
            "name": m.model_name,
            "version": m.model_version,
            "target": m.target_variable,
            "status": m.status,
            "description": f"{m.model_type} Model for {m.target_variable}",
            "metrics": m.metrics_json or {},
            "dataset_version": m.dataset_version,
            "feature_version": m.feature_version,
            "label_version": m.label_version,
            "preprocessing_version": m.preprocessing_version,
            "deployment_status": m.deployment_status or m.status,
            "is_champion": bool(m.is_champion),
            "deployed_at": m.deployed_at.isoformat() if m.deployed_at else None,
            "readiness": by_version[m.model_version],
        })

    # perfTrendData
    history = db.query(RetrainingHistory).order_by(RetrainingHistory.training_end_time.asc()).all()
    perf_trend_data = []
    for h in history:
        metrics = h.metrics_after_json or {}
        perf_trend_data.append({
            "version": h.candidate_model_id.split('_v')[-1] if '_v' in h.candidate_model_id else h.candidate_model_id,
            "rmse": metrics.get("RMSE", metrics.get("rmse")),
            "f1": metrics.get("F1", metrics.get("f1"))
        })

    # causeData
    causes = db.query(AIPredictionResult.cause_candidate, func.count(AIPredictionResult.id)).group_by(AIPredictionResult.cause_candidate).order_by(func.count(AIPredictionResult.id).desc()).all()
    cause_data = [{"cause": c, "count": cnt} for c, cnt in causes]

    return {
        "models": results,
        "counts": status_counts,
        "total": len(models),
        "readiness": readiness,
        "perfTrendData": perf_trend_data,
        "causeData": cause_data
    }


@router.get("/readiness")
def read_mlops_readiness(db: Session = Depends(get_db)):
    return get_mlops_readiness(db)

@router.get("/retrain-history")
def get_retrain_history(db: Session = Depends(get_db)):
    history = db.query(RetrainingHistory).order_by(RetrainingHistory.training_end_time.desc()).all()
    
    results = []
    for h in history:
        results.append({
            "training_id": h.training_id,
            "model_id": h.base_model_id,
            "model_name": h.base_model_id,
            "start_time": h.training_start_time.strftime("%m/%d %H:%M") if h.training_start_time else "",
            "end_time": h.training_end_time.strftime("%m/%d %H:%M") if h.training_end_time else "",
            "status": "COMPLETED" if h.training_end_time else "NOT_EXECUTED",
            "new_version": h.candidate_model_id,
            "performance_before": h.metrics_before_json or {},
            "performance_after": h.metrics_after_json or {}
        })
        
    return {"history": results}


@router.post("/models")
def register_model(req: ModelRegistrationRequest, db: Session = Depends(get_db)):
    # Client-declared metrics and an uploaded path do not prove comparative selection.
    if not req.comparison_receipt_path:
        raise HTTPException(409, "A committed independently reviewed comparison receipt is required")
    from app.ml.candidate_authority import register_candidate
    from app.ml.comparison_runner import ComparisonBlocked
    try:
        model = register_candidate(db, req.comparison_receipt_path, req.model_version)
        return {"model_version": model.model_version, "status": model.status, "metrics": model.metrics_json}
    except ComparisonBlocked as exc:
        db.rollback(); raise HTTPException(409, {"code": exc.code, "detail": exc.detail})


@router.post("/models/{model_version}/deploy")
def deploy_model(model_version: str, req: DeployRequest, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    model = db.query(ModelRegistry).filter(ModelRegistry.model_version == model_version).with_for_update().first()
    if not model: raise HTTPException(404, "Model version not found")
    if model.status != "APPROVED":
        raise HTTPException(409, "Only approved models can be promoted")
    if (model.metrics_json or {}).get("provenance"):
        from app.ml.serving import deploy
        from app.ml.comparison_runner import ComparisonBlocked
        if req.deployment_target != "loopback": raise HTTPException(409, "Only explicit loopback local pilot is implemented")
        try: return deploy(db, model)
        except ComparisonBlocked as exc: db.rollback(); raise HTTPException(409, {"code": exc.code, "detail": exc.detail})
    # Never archive a champion or advertise a runtime deployment from DB state alone.
    raise HTTPException(409, detail={"code": "DEPLOYMENT_BLOCKED", "mutation_performed": False,
                                    "readiness": model_readiness(db, model)})


@router.post("/models/{model_version}/rollback")
def rollback_model(model_version: str, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    model = db.query(ModelRegistry).filter(ModelRegistry.model_version == model_version).with_for_update().first()
    if not model: raise HTTPException(404, "Model version not found")
    if not model.is_champion or model.status != "PRODUCTION":
        raise HTTPException(409, "Only the current production champion can be rolled back")
    if (model.metrics_json or {}).get("provenance"):
        from app.ml.serving import rollback_previous
        from app.ml.comparison_runner import ComparisonBlocked
        try: return rollback_previous(db, model)
        except ComparisonBlocked as exc: db.rollback(); raise HTTPException(409, {"code": exc.code, "detail": exc.detail})
    # Restoring a row is not a runtime rollback. Preserve the current state.
    raise HTTPException(409, detail={"code": "ROLLBACK_RUNTIME_NOT_CONFIGURED", "mutation_performed": False,
                                    "readiness": model_readiness(db, model)})


@router.get("/champion-challenger")
def compare_champion_challenger(champion_version: str, challenger_version: str, db: Session = Depends(get_db)):
    models = db.query(ModelRegistry).filter(ModelRegistry.model_version.in_([champion_version, challenger_version])).all()
    by_version = {m.model_version: m for m in models}
    if champion_version not in by_version or challenger_version not in by_version:
        raise HTTPException(404, "Champion or challenger version not found")
    return {"champion": {"version": champion_version, "metrics": by_version[champion_version].metrics_json or {}}, "challenger": {"version": challenger_version, "metrics": by_version[challenger_version].metrics_json or {}}}


@router.post("/retrain")
def queue_retraining(req: RetrainRequest, db: Session = Depends(get_db)):
    import os
    if os.environ.get("OCEAN_TRAINING_WORKER_ENABLED", "0") != "1":
        raise HTTPException(501, "Training worker is disabled; no training job was queued")
    if not req.manifest_path:
        raise HTTPException(409, {"code": "FIXED_APPROVED_MANIFEST_REQUIRED", "mutation_performed": False,
            "workflow": "/api/mlops/training/enqueue", "message": "An approved fixed manifest is required; model_id cannot define dataset splits or policies."})
    from app.api.routes_mlops_execution import enqueue, ManifestRequest
    if req.model_id:
        model = db.query(ModelRegistry).filter_by(model_version=req.model_id).first()
        if not model: raise HTTPException(404, "Base model version not found")
        from app.ml.comparison_runner import read_json
        from app.api.routes_mlops_execution import exact_path
        manifest, _ = read_json(exact_path(req.manifest_path, "requests"))
        provenance = (model.metrics_json or {}).get("provenance", {})
        if manifest.get("target_variable") != model.target_variable or any(manifest.get(k) != provenance.get(k) for k in ("domain", "item_id", "task")):
            raise HTTPException(409, {"code": "BASE_MODEL_COMPARISON_SCOPE_MISMATCH", "mutation_performed": False})
    return enqueue(ManifestRequest(manifest_path=req.manifest_path,expected_sha256=req.expected_sha256), db)


from app.api.routes_mlops_execution import router as execution_router
router.include_router(execution_router)
