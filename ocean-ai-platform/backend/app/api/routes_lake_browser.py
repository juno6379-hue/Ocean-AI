"""Shared real-file API for dashboard, station list and station details."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import date, time
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services import dashboard_monitoring
from app.services import lake_browser as lake
from app.services.station_classification import resolve_scope

router = APIRouter(prefix='/api/lake', tags=['Real observation lake'])
Source = Literal['GD_OBS_ST_MONTHLY','GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST','HISTORICAL_RECONCILED']
MONTH_PATTERN = r'^(19|20)\d{2}-(0[1-9]|1[0-2])$'
CURRENT_OBSERVATION_MONTH = '2026-07'

def cutoff(as_of_day,as_of_time):
    if as_of_time is not None and (as_of_day is None or as_of_time.tzinfo is not None):
        raise HTTPException(422,'기준시각은 기준일과 함께 offset 없이 선택하세요.')
    return str(as_of_time) if as_of_time is not None else None


@router.get('/publication-comparison')
def publication_comparison(month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), source: Source='GD_OBS_ST_MONTHLY'):
    from app.services.monthly_report_matching import comparison
    return comparison(month,source)


@router.get('/metric-completion')
def metric_completion(source:Source='GD_OBS_ST_MONTHLY',from_month:str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN),
                      to_month:str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN),station:str=Query('',max_length=40),
                      item:str=Query('',max_length=80),network:str=Query('',max_length=80),sea:str=Query('',max_length=80),
                      db:Session=Depends(get_db),as_of_day:date|None=None,as_of_time:time|None=None):
    if from_month>to_month:raise HTTPException(422,'시작월이 종료월보다 늦습니다.')
    from app.services.metric_completion import completion
    scope=resolve_scope(db,network,sea,CURRENT_OBSERVATION_MONTH if from_month==to_month==CURRENT_OBSERVATION_MONTH else None)
    clock=cutoff(as_of_day,as_of_time)
    if as_of_day:
        from app.services.observation_asof import completion as dated_completion
        return dated_completion(source,from_month,to_month,str(as_of_day),station,item,scope,clock)
    return completion(source,from_month,to_month,station,item,scope)


@router.get('/monitoring')
def monitoring(source: Source='GD_OBS_ST_MONTHLY', from_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), to_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), station: str=Query('',max_length=40), item: str=Query('',max_length=80), network: str=Query('',max_length=80), sea: str=Query('',max_length=80), db: Session=Depends(get_db)):
    if from_month>to_month: raise HTTPException(422,'시작월이 종료월보다 늦습니다.')
    return dashboard_monitoring.monitoring(source,from_month,to_month,station,item,resolve_scope(db,network,sea,CURRENT_OBSERVATION_MONTH if from_month==to_month==CURRENT_OBSERVATION_MONTH else None))


@router.get('/daily-reports')
def daily_reports(from_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), to_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), day: date|None=None, db: Session=Depends(get_db)):
    if from_month>to_month: raise HTTPException(422,'시작월이 종료월보다 늦습니다.')
    return dashboard_monitoring.daily_reports(db,from_month,to_month,day)


@router.get('/equipment-evidence')
def equipment_evidence(source: Source='GD_OBS_ST_MONTHLY', from_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), to_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), station: str=Query('',max_length=40), network: str=Query('',max_length=80), sea: str=Query('',max_length=80), db: Session=Depends(get_db)):
    if from_month>to_month: raise HTTPException(422,'시작월이 종료월보다 늦습니다.')
    return dashboard_monitoring.equipment_evidence(source,from_month,to_month,station,resolve_scope(db,network,sea,CURRENT_OBSERVATION_MONTH if from_month==to_month==CURRENT_OBSERVATION_MONTH else None))


@router.get('/summary')
def summary(source: Source='GD_OBS_ST_MONTHLY', from_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), to_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), network: str=Query('',max_length=80), sea: str=Query('',max_length=80), db: Session=Depends(get_db),as_of_day:date|None=None,as_of_time:time|None=None):
    if from_month>to_month: raise HTTPException(422,'시작월이 종료월보다 늦습니다.')
    clock=cutoff(as_of_day,as_of_time)
    scope=resolve_scope(db,network,sea,CURRENT_OBSERVATION_MONTH if from_month==to_month==CURRENT_OBSERVATION_MONTH else None)
    if as_of_day:
        from app.services.observation_asof import overview
        return overview(source,from_month,to_month,str(as_of_day),scope,clock,db=db)
    return lake.overview(source,from_month,to_month,scope)


@router.get('/stations/{station}')
def station_detail(station: str, source: Source='GD_OBS_ST_MONTHLY', from_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN), to_month: str=Query(CURRENT_OBSERVATION_MONTH,pattern=MONTH_PATTERN),as_of_day:date|None=None,as_of_time:time|None=None,db:Session=Depends(get_db)):
    if from_month>to_month: raise HTTPException(422,'시작월이 종료월보다 늦습니다.')
    clock=cutoff(as_of_day,as_of_time)
    if as_of_day:
        from app.services.observation_asof import station_detail as dated_detail
        return dated_detail(station,source,from_month,to_month,str(as_of_day),clock,db=db)
    return lake.station_detail(station,source,from_month,to_month)


@router.get('/series')
def series(source: Source, month: str=Query(...,pattern=MONTH_PATTERN), station: str=Query(...,min_length=1,max_length=40), item: str=Query(...,min_length=1,max_length=80),
           depth_step: str|None=None,depth_from: str|None=None,depth_to: str|None=None,
           limit: int=Query(500,ge=1,le=2000),offset: int=Query(0,ge=0,le=1000000),tail: bool=False,as_of_day:date|None=None,as_of_time:time|None=None):
    clock=cutoff(as_of_day,as_of_time)
    return lake.series(source,month,station,item,[depth_step,depth_from,depth_to],limit,offset,tail=tail,as_of_day=str(as_of_day) if as_of_day else None,as_of_time=clock)
