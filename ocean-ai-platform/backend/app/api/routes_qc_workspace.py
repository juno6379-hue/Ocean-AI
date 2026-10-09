"""Strict bounded read-only QC workspace. There are no mutation routes."""
from datetime import date,time
from typing import Literal
from fastapi import APIRouter,Depends,Query,Request,HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.qc_workspace import workspace
from app.services.qc_overview import context,overview

router=APIRouter(prefix='/api/qc',tags=['Native-clock QC workspace'])
Source=Literal['GD_OBS_ST_MONTHLY','GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST']
MONTH_PATTERN=r'^20\d{2}-(0[1-9]|1[0-2])$'
QUERY_KEYS={'source','from_month','to_month','as_of_day','as_of_time','station','item','network','sea','qc_field','qc_literal','qc_literal_is_null'}

def strict_query(request:Request):
    if set(request.query_params)-QUERY_KEYS or any(len(request.query_params.getlist(key))!=1 for key in request.query_params):
        raise HTTPException(422,'QC 조회는 정의된 단일 값 필터만 지원합니다.')

@router.get('/workspace',dependencies=[Depends(strict_query)])
def get_workspace(source:Source='GD_OBS_ST_MONTHLY',
    from_month:str=Query('2026-07',pattern=MONTH_PATTERN),to_month:str=Query('2026-07',pattern=MONTH_PATTERN),
    as_of_day:date=date(2026,7,9),as_of_time:time=time(15,41,20),
    station:str=Query('',max_length=40),item:str=Query('',max_length=80),
    network:str=Query('',max_length=80),sea:str=Query('',max_length=80),
    qc_field:str=Query('',max_length=32),qc_literal:str|None=Query(None,max_length=128),
    qc_literal_is_null:bool=False,db:Session=Depends(get_db)):
    return workspace(db,source,from_month,to_month,str(as_of_day),str(as_of_time),station,item,network,sea,qc_field,qc_literal,qc_literal_is_null)

OVERVIEW_KEYS={'source','preset','date_from','date_to','station_id','variable_code','network','sea','flag','queue_limit','queue_offset'}

def strict_overview_query(request:Request):
    if set(request.query_params)-OVERVIEW_KEYS or any(len(request.query_params.getlist(key))!=1 for key in request.query_params):
        raise HTTPException(422,'QC 운영 조회는 정의된 단일 값 필터만 지원합니다.')

def no_context_query(request:Request):
    if request.query_params:raise HTTPException(422,'QC 서버 시계 조회에는 필터를 사용할 수 없습니다.')

@router.get('/context',dependencies=[Depends(no_context_query)])
def get_context():
    return context()

@router.get('/overview',dependencies=[Depends(strict_overview_query)])
def get_overview(source:Literal['REGISTERED','GD_OBS_ST_MONTHLY','GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST']='REGISTERED',
    preset:Literal['today','yesterday','7d','30d','custom']='today',
    date_from:str|None=Query(None,max_length=40),date_to:str|None=Query(None,max_length=40),
    station_id:str=Query('',max_length=40),variable_code:str=Query('',max_length=80),
    network:str=Query('',max_length=80),sea:str=Query('',max_length=80),flag:str=Query('',max_length=32),
    queue_limit:int=Query(30,ge=1,le=30),queue_offset:int=Query(0,ge=0,le=1000),db:Session=Depends(get_db)):
    return overview(db,source,preset,date_from,date_to,station_id,variable_code,network,sea,flag,queue_limit,queue_offset)
