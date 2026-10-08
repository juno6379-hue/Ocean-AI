# 파일 역할: 승인 라벨·Feature·사건 근거를 고정하고 데이터셋 분할 누수와 무결성을 검증합니다.
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import List, Literal
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import Actor, require_reviewer, current_actor
from app.core.config import settings
from app.models.domain import DatasetRegistry, ApprovalHistory
from app.models.evidence import DatasetMembership
from app.schemas.domain import DatasetRegistry as DatasetRegistrySchema
from app.services.dataset_lineage import build_content, leakage_errors, family_lock
from app.services.event_evidence import utc
from app.services.source_contract_snapshot import (freeze_dependencies,reattach_frozen_dependencies,
    frozen_integrity_errors,create_candidate_snapshot,ingest_approved_source,read_bounded,source_roots,protocol_authority,DependencyError)
from app.models.source_contracts import SourceContractPacket,SourceContractDecision
from app.models.source_observation_binding import SourceObservationBinding

router=APIRouter(prefix='/api/datasets',tags=['Dataset Registry'])
SPLITS={'TRAIN','VALIDATION','TEST','BLIND_TEST','RETRAINING_POOL'}


class DependencySpec(BaseModel):
    model_config=ConfigDict(extra='forbid')
    role: Literal['SOURCE_CONTRACT','SPLIT_PROTOCOL','EVALUATION_PROTOCOL','ACCEPTANCE_POLICY','REVIEW_CANDIDATES']
    path: str
    sha256: str=Field(pattern=r'^[0-9a-f]{64}$')


class DatasetBuildRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dependencies: list[DependencySpec]=Field(default_factory=list,max_length=128)


class ReviewedDatasetRegistration(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset: DatasetRegistrySchema
    split_protocol: DependencySpec


@router.post('/register-reviewed',response_model=DatasetRegistrySchema)
def register_reviewed_dataset(req: ReviewedDatasetRegistration,db: Session=Depends(get_db)):
    if req.split_protocol.role!='SPLIT_PROTOCOL':raise HTTPException(422,'SPLIT_PROTOCOL dependency required')
    try:
        body,_,sha=read_bounded(req.split_protocol.path,source_roots(),req.split_protocol.sha256)
        protocol_authority(db,body,sha,'SPLIT_PROTOCOL')
        if body.get('dataset_ids',{}).get(req.dataset.dataset_split.upper())!=req.dataset.dataset_id:raise DependencyError('SPLIT_PROTOCOL_DATASET_ID_MISMATCH')
        return _register_dataset(req.dataset,db,body)
    except (ValueError,OSError) as exc:raise HTTPException(422,getattr(exc,'code',str(exc)))


class SourceCandidateRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    parquet_path: str
    manifest_path: str
    manifest_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    source_group: str
    scopes: list[dict]=Field(min_length=1,max_length=128)
    limit: int=Field(default=500,ge=1,le=5000)


class SourceIngestRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    receipt_path: str
    receipt_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    register_metadata: bool=False


@router.post('/source-ingest')
def source_ingest(req: SourceIngestRequest,db: Session=Depends(get_db),actor: Actor=Depends(current_actor)):
    try:
        receipt,_,sha=read_bounded(req.receipt_path,source_roots(),req.receipt_sha256)
        result=ingest_approved_source(db,receipt,sha,actor,req.register_metadata)
        db.commit();return result
    except (ValueError,OSError) as exc:
        db.rollback();raise HTTPException(422,getattr(exc,'code',str(exc)))
    except Exception:
        db.rollback();raise


@router.post('/source-candidates')
def source_candidates(req: SourceCandidateRequest,actor: Actor=Depends(current_actor)):
    if actor.role not in {'operator','reviewer','admin'}:raise HTTPException(403,'Operator role required')
    try:return create_candidate_snapshot(**req.model_dump(),root=settings.DATASET_SNAPSHOT_DIR)
    except (ValueError,OSError) as exc:raise HTTPException(422,getattr(exc,'code',str(exc)))


@router.get('',response_model=List[DatasetRegistrySchema])
def list_datasets(dataset_split: str=None,db: Session=Depends(get_db)):
    query=db.query(DatasetRegistry)
    if dataset_split: query=query.filter_by(dataset_split=dataset_split.upper())
    return query.order_by(DatasetRegistry.created_at.desc()).all()


@router.post('',response_model=DatasetRegistrySchema)
def register_dataset(req: DatasetRegistrySchema,db: Session=Depends(get_db)):
    return _register_dataset(req,db)


def _register_dataset(req,db,split_protocol=None):
    if req.status!='DRAFT' or req.approved_by or req.data_hash:
        raise HTTPException(422,'New datasets must start as unbuilt drafts')
    req.period_start,req.period_end=utc(req.period_start,True),utc(req.period_end,True)
    req.dataset_split=req.dataset_split.upper()
    if req.dataset_split not in SPLITS or req.period_start>=req.period_end:
        raise HTTPException(422,'Invalid split or period')
    if not req.station_scope or not req.variable_scope or any(not v.strip() for v in req.station_scope+req.variable_scope):
        raise HTTPException(422,'Nonempty station and variable scopes are required')
    if any(x<0 for x in [req.sample_count,req.normal_count,req.suspect_count,req.bad_count,req.missing_count]):
        raise HTTPException(422,'Dataset counts cannot be negative')
    family_lock(db,req.dataset_name)
    dataset=DatasetRegistry(**req.model_dump())
    errors=leakage_errors(db,dataset,split_protocol)
    if errors: raise HTTPException(409,errors)
    db.add(dataset)
    try: db.commit();db.refresh(dataset)
    except Exception:
        db.rollback();raise HTTPException(409,'Dataset ID or name/version already exists')
    return dataset


def _get_dataset(db,dataset_id,lock=False):
    query=db.query(DatasetRegistry).filter_by(dataset_id=dataset_id)
    if lock: query=query.with_for_update()
    dataset=query.first()
    if not dataset: raise HTTPException(404,'Dataset not found')
    return dataset


def _serialized(snapshot):
    try: return json.dumps(snapshot,sort_keys=True,ensure_ascii=False,allow_nan=False,default=str)
    except ValueError: raise HTTPException(422,'Nonfinite source value; standardize missing values before building')


def _snapshot_hash(snapshot):
    return hashlib.sha256(_serialized(snapshot).encode('utf-8')).hexdigest()


def _dataset_content(db,dataset,dependency_specs=None):
    rows,snapshot,counts=build_content(db,dataset)
    if dependency_specs is not None:
        snapshot=freeze_dependencies(db,snapshot,dependency_specs,settings.DATASET_SNAPSHOT_DIR)
    elif dataset.data_hash:
        frozen=read_snapshot(dataset)
        snapshot=reattach_frozen_dependencies(db,snapshot,frozen,settings.DATASET_SNAPSHOT_DIR)
    protocol=None
    for dep in snapshot.get('frozen_protocol_dependencies',[]):
        if dep['role']=='SPLIT_PROTOCOL' and not dep.get('review_errors') and dep.get('approval_receipt'):
            body,_,sha=read_bounded(Path(settings.DATASET_SNAPSHOT_DIR)/dep['path'],[settings.DATASET_SNAPSHOT_DIR],dep['sha256'])
            protocol_authority(db,body,sha,'SPLIT_PROTOCOL');protocol=body
    snapshot['validation_errors']=sorted(set(snapshot['validation_errors']+leakage_errors(db,dataset,protocol)))
    return rows,snapshot,counts


def _snapshot_path(dataset):
    if not dataset.data_hash or len(dataset.data_hash)!=64 or any(c not in '0123456789abcdef' for c in dataset.data_hash):
        raise HTTPException(409,'Valid snapshot hash required')
    return Path(settings.DATASET_SNAPSHOT_DIR)/f'{dataset.data_hash}.json'


def read_snapshot(dataset):
    path=_snapshot_path(dataset)
    try:
        value,_,_=read_bounded(path,[settings.DATASET_SNAPSHOT_DIR],dataset.data_hash)
        return value
    except (ValueError,OSError) as exc:raise HTTPException(409,getattr(exc,'code','Dataset snapshot file missing or invalid'))


@router.get('/{dataset_id}',response_model=DatasetRegistrySchema)
def get_dataset(dataset_id: str,db: Session=Depends(get_db)):
    return _get_dataset(db,dataset_id)


@router.post('/{dataset_id}/build')
def build_dataset(dataset_id: str,req: DatasetBuildRequest|None=Body(default=None),db: Session=Depends(get_db)):
    dataset=_get_dataset(db,dataset_id,True)
    if dataset.status=='APPROVED': raise HTTPException(409,'Approved datasets are immutable; create a new version')
    family_lock(db,dataset.dataset_name)
    try:rows,snapshot,counts=_dataset_content(db,dataset,[s.model_dump() for s in req.dependencies] if req else None)
    except (ValueError,OSError) as exc:raise HTTPException(422,getattr(exc,'code',str(exc)))
    dataset.sample_count=len(snapshot['records'])
    dataset.normal_count,dataset.suspect_count=counts['1'],counts['3']
    dataset.bad_count,dataset.missing_count=counts['4'],counts['9']
    dataset.data_hash=_snapshot_hash(snapshot)
    path=_snapshot_path(dataset);path.parent.mkdir(parents=True,exist_ok=True)
    serialized=_serialized(snapshot)
    if path.exists():
        if path.read_text(encoding='utf-8')!=serialized: raise HTTPException(409,'Dataset snapshot integrity check failed')
    else:
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='\n',dir=path.parent,suffix='.tmp',delete=False) as stream:
                temporary=Path(stream.name);stream.write(serialized)
            try:os.link(temporary,path)
            except FileExistsError:
                if path.read_text(encoding='utf-8')!=serialized:raise HTTPException(409,'Dataset snapshot integrity check failed')
        finally:
            if temporary and temporary.exists(): temporary.unlink()
    # 파일의 내용 해시와 같은 참여 목록만 DB에 공개한다.
    db.query(DatasetMembership).filter_by(dataset_id=dataset_id).delete(synchronize_session=False)
    for record in snapshot['records']:
        db.add(DatasetMembership(dataset_id=dataset_id,observation_id=record['id'],label_id=record['label']['label_id'],
                                event_id=record['event_id'],snapshot_hash=dataset.data_hash))
    dataset.status='BUILT';db.commit()
    return {'dataset_id':dataset_id,'status':dataset.status,'sample_count':dataset.sample_count,
            'source_observation_count':len(rows),'unreviewed_count':counts['UNREVIEWED'],
            'data_hash':dataset.data_hash,'validation_errors':snapshot['validation_errors']}


def validation_errors(db,dataset):
    try:_,snapshot,counts=_dataset_content(db,dataset)
    except (ValueError,OSError,HTTPException) as exc:return [getattr(exc,'code',str(getattr(exc,'detail',exc)))]
    errors=list(snapshot['validation_errors'])
    snapshot['validation_errors']=errors
    if _snapshot_hash(snapshot)!=dataset.data_hash: errors=errors+['source_or_evidence_changed_rebuild_required']
    if counts['UNREVIEWED']: errors.append('unreviewed_observations')
    if dataset.sample_count<=0: errors.append('no_samples')
    if dataset.status not in {'BUILT','VALIDATED','APPROVED'}: errors.append('build_required')
    try:
        frozen=read_snapshot(dataset)
        errors.extend(frozen_integrity_errors(db,frozen,settings.DATASET_SNAPSHOT_DIR))
        members=db.query(DatasetMembership).filter_by(dataset_id=dataset.dataset_id).all()
        stored={(m.observation_id,m.label_id,m.event_id,m.snapshot_hash) for m in members}
        expected={(r['id'],r['label']['label_id'],r['event_id'],dataset.data_hash) for r in frozen.get('records',[])}
        if stored!=expected or len(members)!=len(frozen.get('records',[])):errors.append('FROZEN_MEMBERSHIP_MISMATCH')
    except HTTPException as exc: errors.append(str(exc.detail))
    return errors


@router.post('/{dataset_id}/validate')
def validate_dataset(dataset_id: str,db: Session=Depends(get_db)):
    dataset=_get_dataset(db,dataset_id,True)
    if dataset.status=='APPROVED': raise HTTPException(409,'Approved datasets cannot be revalidated')
    family_lock(db,dataset.dataset_name)
    errors=validation_errors(db,dataset)
    if errors:
        if dataset.status=='VALIDATED': dataset.status='BUILT';db.commit()
        return {'dataset_id':dataset_id,'status':'INVALID','errors':errors}
    dataset.status='VALIDATED';db.commit()
    return {'dataset_id':dataset_id,'status':'VALIDATED','errors':[]}


@router.post('/{dataset_id}/approve')
def approve_dataset(dataset_id: str,db: Session=Depends(get_db),actor: Actor=Depends(require_reviewer)):
    dataset=_get_dataset(db,dataset_id,True)
    if dataset.status!='VALIDATED': raise HTTPException(409,'Only VALIDATED datasets can be approved')
    family_lock(db,dataset.dataset_name)
    errors=validation_errors(db,dataset)
    if errors: raise HTTPException(409,errors)
    dataset.status,dataset.approved_by='APPROVED',actor.user_id
    db.add(ApprovalHistory(approval_type='DATASET',target_id=dataset_id,requested_by=actor.user_id,
        approved_by=actor.user_id,approval_status='APPROVED',comment='snapshot_sha256='+dataset.data_hash))
    db.commit()
    return {'dataset_id':dataset_id,'status':dataset.status,'approved_by':actor.user_id}


@router.get('/{dataset_id}/lineage')
def dataset_lineage(dataset_id: str,db: Session=Depends(get_db)):
    dataset=_get_dataset(db,dataset_id)
    return {'dataset_id':dataset_id,'data_hash':dataset.data_hash,'snapshot':read_snapshot(dataset),
            'approval_history':db.query(ApprovalHistory).filter_by(approval_type='DATASET',target_id=dataset_id).all()}
