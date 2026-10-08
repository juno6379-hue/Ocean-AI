"""Review-only inputs and authenticated legacy-to-new-version migration."""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.security import Actor, current_actor
from app.services.dataset_migration import review_migration,migrate_v2
from app.services.model_development import task_readiness,manifest_catalog,inspect_manifest,build_policy_bundle,create_comparison_manifest
from app.services.source_contract_snapshot import DependencyError
from app.ml.comparison_runner import ComparisonBlocked

router=APIRouter(prefix='/api/model-development',tags=['Model Development Review'])


def failure(exc):
    return HTTPException(409,{'code':getattr(exc,'code','REVIEW_INPUT_INVALID'),
                             'detail':getattr(exc,'detail',str(exc)),
                             'mutation_performed':False})


@router.get('/task-readiness')
def source_task_readiness(db:Session=Depends(get_db)):
    try:
        with db.no_autoflush:return task_readiness(db)
    except (DependencyError,ComparisonBlocked) as exc:raise failure(exc)


@router.get('/training-manifests')
def training_manifests():
    try:return manifest_catalog()
    except ComparisonBlocked as exc:raise failure(exc)


class FixedDatasetSelection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset_ids:dict[str,str]


@router.post('/training-manifests')
def build_training_manifest(req:FixedDatasetSelection,db:Session=Depends(get_db),actor:Actor=Depends(current_actor)):
    if actor.role not in {'operator','reviewer','admin'}:raise HTTPException(403,'Operator role required')
    try:return create_comparison_manifest(db,req.dataset_ids,settings.DATASET_SNAPSHOT_DIR)
    except (DependencyError,ComparisonBlocked) as exc:raise failure(exc)


@router.get('/training-preflight')
def training_preflight(manifest_path:str,expected_sha256:str|None=Query(default=None,pattern='^[0-9a-f]{64}$'),db:Session=Depends(get_db)):
    try:return inspect_manifest(db,manifest_path,settings.DATASET_SNAPSHOT_DIR,expected_sha256)
    except (DependencyError,ComparisonBlocked) as exc:raise failure(exc)


@router.get('/policy-bundle')
def policy_bundle(selection_json:str=Query(max_length=65536),db:Session=Depends(get_db)):
    try:
        selection=json.loads(selection_json)
        if not isinstance(selection,dict):raise ComparisonBlocked('POLICY_SELECTION_OBJECT_REQUIRED')
        with db.no_autoflush:return build_policy_bundle(db,selection)
    except (DependencyError,ComparisonBlocked) as exc:raise failure(exc)
    except (ValueError,KeyError,TypeError) as exc:raise failure(ComparisonBlocked('POLICY_SELECTION_INVALID',type(exc).__name__))


@router.get('/datasets/{dataset_id}/migration-review')
def migration_review(dataset_id:str,new_dataset_id:str,new_version:str,dependencies_json:str=Query(default='[]',max_length=65536),db:Session=Depends(get_db)):
    try:
        with db.no_autoflush:return review_migration(db,dataset_id,new_dataset_id,new_version,
            json.loads(dependencies_json),settings.DATASET_SNAPSHOT_DIR)
    except (DependencyError,ComparisonBlocked) as exc:raise failure(exc)
    except (ValueError,TypeError,KeyError) as exc:raise failure(ComparisonBlocked('MIGRATION_REVIEW_INPUT_INVALID',type(exc).__name__))


class MigrationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    new_dataset_id:str=Field(min_length=1,max_length=128)
    new_version:str=Field(min_length=1,max_length=128)
    dependencies:list[dict]=Field(max_length=128)
    expected_legacy_sha256:str=Field(pattern='^[0-9a-f]{64}$')
    expected_review_sha256:str=Field(pattern='^[0-9a-f]{64}$')


@router.post('/datasets/{dataset_id}/migrate-v2')
def migrate(dataset_id:str,req:MigrationRequest,db:Session=Depends(get_db),actor:Actor=Depends(current_actor)):
    try:return migrate_v2(db,dataset_id,req.new_dataset_id,req.new_version,req.dependencies,
                         settings.DATASET_SNAPSHOT_DIR,req.expected_legacy_sha256,req.expected_review_sha256,actor)
    except (DependencyError,ComparisonBlocked) as exc:db.rollback();raise failure(exc)
