# 파일 역할: 학습 특성 정의와 값 관련 요청을 검증하고 API 응답을 제공합니다.
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import FeatureDefinition, FeatureValue
from app.schemas.domain import FeatureDefinition as FeatureDefinitionSchema
from app.schemas.domain import FeatureValue as FeatureValueSchema

router = APIRouter(prefix="/api/features", tags=["Feature Store"])

FEATURE_GROUPS = {
    "Raw Feature", "Rule QC Feature", "Temporal Feature", "Spatial Feature",
    "Metadata Feature", "Operation Feature", "Event Feature",
}


@router.get("/definitions", response_model=List[FeatureDefinitionSchema])
def list_feature_definitions(
    feature_group: Optional[str] = None,
    feature_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(FeatureDefinition)
    if feature_group:
        query = query.filter(FeatureDefinition.feature_group == feature_group)
    if feature_id:
        query = query.filter(FeatureDefinition.feature_id == feature_id)
    return query.order_by(FeatureDefinition.feature_name, FeatureDefinition.feature_version).all()


@router.post("/definitions", response_model=FeatureDefinitionSchema)
def create_feature_definition(req: FeatureDefinitionSchema, db: Session = Depends(get_db)):
    if req.feature_group not in FEATURE_GROUPS:
        raise HTTPException(status_code=422, detail="Unsupported feature_group")
    definition = FeatureDefinition(**(req.model_dump() if hasattr(req, "model_dump") else req.dict()))
    db.add(definition)
    try:
        db.commit()
        db.refresh(definition)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Feature definition version already exists")
    return definition


@router.get("/values", response_model=List[FeatureValueSchema])
def list_feature_values(
    station_id: Optional[str] = None,
    feature_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(FeatureValue)
    if station_id:
        query = query.filter(FeatureValue.station_id == station_id)
    if feature_id:
        query = query.filter(FeatureValue.feature_id == feature_id)
    return query.order_by(FeatureValue.timestamp_utc.desc()).limit(min(limit, 1000)).all()


@router.post("/values", response_model=FeatureValueSchema)
def create_feature_value(req: FeatureValueSchema, db: Session = Depends(get_db)):
    definition = db.query(FeatureDefinition).filter(
        FeatureDefinition.feature_id == req.feature_id,
        FeatureDefinition.feature_version == req.feature_version,
    ).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Feature definition/version not found")
    value = FeatureValue(**(req.model_dump() if hasattr(req, "model_dump") else req.dict()))
    db.add(value)
    try:
        db.commit()
        db.refresh(value)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Feature value already exists")
    return value
