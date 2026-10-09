"""Bounded GET review only; mutations use the existing authenticated workflow."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import get_db
from app.core.security import current_actor
from app.services.qc_candidate_review import (CandidateError, flag_catalog, registered_detail, archive_detail,begin_readonly_snapshot)

router=APIRouter(prefix='/api/qc',tags=['QC candidate detail'])
Source=Literal['REGISTERED','GD_OBS_ST_MONTHLY','GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST']
KEYS={'source','preset','date_from','date_to','as_of','clock_basis','offset','granularity','mode','window_id','snapshot','station','item','half_window_minutes'}


def strict_query(request:Request):
    if set(request.query_params)-KEYS or any(len(request.query_params.getlist(key))!=1 for key in request.query_params):
        raise HTTPException(422,dict(code='INVALID_CANDIDATE_QUERY'))


@router.get('/flag-catalog')
def get_flag_catalog(): return flag_catalog()


@router.get('/candidates/{candidate_id}',dependencies=[Depends(strict_query)])
def get_candidate(candidate_id:str,request:Request,source:Source='REGISTERED',
    preset:Literal['today','yesterday','7d','30d','custom']='today',
    date_from:str=Query(...,max_length=40),date_to:str=Query(...,max_length=40),as_of:str=Query(...,max_length=40),
    clock_basis:str=Query(...,max_length=40),offset:str|None=Query(None,max_length=16),
    granularity:Literal['hour','day']='hour',mode:str|None=Query(None,max_length=24),
    window_id:str=Query(...,pattern=r'^[0-9a-f]{64}$'),snapshot:str|None=Query(None,max_length=100),
    station:str=Query('',max_length=128),item:str=Query('',max_length=128),
    half_window_minutes:int=Query(120,ge=1,le=120),db:Session=Depends(get_db)):
    from app.services.qc_overview import validate_window_identity
    window=dict(source=source,mode=mode or ('OPERATIONAL' if source=='REGISTERED' else 'ARCHIVE'),preset=preset,
        start=date_from,end=date_to,as_of=as_of,clock_basis=clock_basis,offset=offset,granularity=granularity,window_id=window_id)
    try:
        validate_window_identity(window)
        actor=current_actor(request) if request.headers.get('Authorization') else None
        with db.no_autoflush:
            snapshot_provenance=begin_readonly_snapshot(db)
            if source=='REGISTERED':
                if snapshot is not None: raise CandidateError('REGISTERED_SNAPSHOT_NOT_SUPPORTED')
                packet=registered_detail(db,candidate_id,window,station,item,half_window_minutes,actor)
            else: packet=archive_detail(db,candidate_id,window,snapshot,station,item,half_window_minutes)
            from app.services.qc_candidate_review import digest
            packet['provenance']['query_snapshot']=snapshot_provenance
            packet.pop('result_sha256',None);packet['result_sha256']=digest(packet)
            return packet
    except CandidateError as exc:
        status=404 if exc.code in {'CANDIDATE_NOT_FOUND','ARCHIVE_ROW_NOT_FOUND'} else 409 if 'AUTHORITY' in exc.code or 'SNAPSHOT' in exc.code else 422
        raise HTTPException(status,dict(code=exc.code,mutation_performed=False)) from None
    except SQLAlchemyError:
        raise HTTPException(503,dict(code='QC_CANDIDATE_STORAGE_UNAVAILABLE',mutation_performed=False)) from None
