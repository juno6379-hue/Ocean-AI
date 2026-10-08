"""Read-only point checks and bounded operational records; no synthetic uptime."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os
import time
import urllib.request
from sqlalchemy import text
from app.core.config import settings


def windows_process(pid):
    """Query identity without signalling the process or acquiring a worker lock."""
    if not pid or os.name!='nt':return {'state':'NOT_CHECKED'}
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,int(pid))
    if not handle:return {'state':'NOT_FOUND' if ctypes.get_last_error()==87 else 'ACCESS_UNVERIFIED'}
    try:
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        exit_code=wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code)):return {'state':'ACCESS_UNVERIFIED'}
        if exit_code.value!=259:return {'state':'EXITED'}
        fields=[wintypes.FILETIME() for _ in range(4)]
        kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(f) for f in fields]):return {'state':'PID_EXISTS_START_UNVERIFIED'}
        ticks=(fields[0].dwHighDateTime<<32)|fields[0].dwLowDateTime
        started=datetime.fromtimestamp((ticks-116444736000000000)/10000000,timezone.utc)
        return {'state':'PID_EXISTS','started_at':started.isoformat()}
    finally:kernel.CloseHandle(handle)


def batch_record(name,path,now):
    result={'name':name,'source_path':str(path),'reported_state':None,'process':{'state':'NOT_CHECKED'},'os_lock':'NOT_CHECKED'}
    try:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        result.update(reported_state=data.get('state'),reported_at=data.get('at') or data.get('checked_at'),pid=data.get('pid'),completed=data.get('completed'),total=data.get('total'),counts=data.get('counts'),scope=data.get('scope'))
        if result['reported_at']:
            at=datetime.fromisoformat(result['reported_at'].replace('Z','+00:00'))
            if at.tzinfo is None:at=at.replace(tzinfo=timezone.utc)
            result['age_seconds']=max(0,round((now-at).total_seconds()))
        terminal=str(result['reported_state']).startswith(('COMPLETE','SOURCE_COPY_VERIFIED','WEB_CUTOVER_VERIFIED'))
        if not terminal:
            result['process']=windows_process(data.get('pid'))
            expected=data.get('started_at')
            if expected and result['process'].get('started_at'):
                a=datetime.fromisoformat(expected.replace('Z','+00:00'));b=datetime.fromisoformat(result['process']['started_at'])
                if a.tzinfo is None:a=a.replace(tzinfo=timezone.utc)
                result['process']['start_matches']=abs((a-b).total_seconds())<3
        result['status']='REPORTED_COMPLETE' if terminal else 'CHECK_DETAILS'
    except (OSError,ValueError,TypeError):result['status']='RECORD_UNAVAILABLE'
    return result


def overview(db,start,end):
    now=datetime.now(timezone.utc)
    services=[{'id':'api','name':'데이터 API','state':'RESPONDING','basis':'현재 API 요청 응답','latency_ms':None}]
    started=time.perf_counter();database_ok=False
    try:
        db.execute(text('SELECT 1'));database_ok=True
        services.append({'id':'postgres','name':'PostgreSQL','state':'REACHABLE','latency_ms':round((time.perf_counter()-started)*1000,2),'basis':'SELECT 1 단일 연결 확인'})
    except Exception:
        db.rollback();services.append({'id':'postgres','name':'PostgreSQL','state':'CHECK_FAILED','latency_ms':None,'basis':'연결 확인 실패 · 원인 추가 확인 필요'})
    started=time.perf_counter()
    try:
        scheme='https' if settings.DOCUMENT_CHROMA_SSL else 'http'
        request=urllib.request.Request(f'{scheme}://{settings.DOCUMENT_CHROMA_HOST}:{settings.DOCUMENT_CHROMA_PORT}/api/v2/heartbeat')
        with urllib.request.urlopen(request,timeout=2) as response:heartbeat=json.load(response)
        if not heartbeat:raise ValueError('Empty heartbeat')
        services.append({'id':'chroma','name':'Chroma','state':'REACHABLE','latency_ms':round((time.perf_counter()-started)*1000,2),'basis':'heartbeat 단일 확인 · 실제 검색 정확도와 별도'})
    except Exception:services.append({'id':'chroma','name':'Chroma','state':'CHECK_FAILED','latency_ms':None,'basis':'heartbeat 확인 실패'})
    try:
        from app.api.routes_foundation import snapshot
        _,view=snapshot()
        services.append({'id':'lake','name':'Parquet 검증본','state':'AVAILABLE','latency_ms':None,'basis':view.name+' · 전체 파일 재읽기를 이번 요청에서 수행한 것은 아님'})
    except Exception:services.append({'id':'lake','name':'Parquet 검증본','state':'CHECK_FAILED','latency_ms':None,'basis':'완료 검증본 선택 실패'})
    ops=Path(os.getenv('OPERATIONS_STATUS_ROOT',r'C:\AI_Observation\ocean-ai-platform\backend\tests\.work\operations-20261006'))
    foundation=Path(settings.FOUNDATION_OUTPUT_ROOT)/'run-20261006T082954Z'
    batches=[batch_record(name,path,now) for name,path in [
        ('Dshare 임베딩 대조',ops/'share-embedding-comparison-status.json'),
        ('문서 최종화',foundation/'completion-status.json'),
        ('추가 문서 추출',foundation/'expanded-extraction-status.json'),
        ('C/E 원천·레이크 이전',Path(r'D:\AI_Observation\metadata\migration\c_e_to_d_v1\status.json')),
        ('웹 소스 D 전환',Path(r'D:\AI_Observation\metadata\migration\web_source_20261007\status.json'))]]
    logs=[];log_count=None;log_state='DATABASE_UNAVAILABLE';level_counts={}
    if database_ok:
        try:
            args={'start':start.replace(tzinfo=None),'end':end.replace(tzinfo=None)}
            base='FROM service_monitoring_log WHERE check_time>=:start AND check_time<=:end'
            log_count=db.execute(text('SELECT count(*) '+base),args).scalar()
            level_counts={str(r[0] or 'UNKNOWN'):r[1] for r in db.execute(text('SELECT issue_level,count(*) '+base+' GROUP BY issue_level'),args)}
            columns='service_log_id,service_name,check_time,station_id,station_name,api_status,display_status,delay_minutes,issue_level,issue_detail'
            logs=[dict(r) for r in db.execute(text('SELECT '+columns+' '+base+' ORDER BY check_time DESC,service_log_id LIMIT 100'),args).mappings()]
            for r in logs:
                if r['check_time']:r['check_time']=r['check_time'].replace(tzinfo=timezone.utc).isoformat()
            log_state='AVAILABLE'
        except Exception:db.rollback();log_state='QUERY_FAILED'
    return {'checked_at':now.isoformat(),'from_time':start.isoformat(),'to_time':end.isoformat(),
            'services':services,'batches':batches,'logs':logs,'log_count':log_count,'level_counts':level_counts,'log_state':log_state,
            'uptime_rate':None,'error_rate':None,'active_users':None,'average_api_latency_ms':None,
            'note':'상태 점검은 현재의 단일 응답입니다. 기간 가동률·전체 요청 오류율·동시 접속자 집계는 미연결입니다.',
            'log_note':'최대 100건의 업무 점검 기록. 작성 당시 입력된 지연값 기반 기록이며 HTTP 접근 로그·자동 수집 상태의 증명은 아닙니다. 저장된 UTC 시각을 사용합니다.',
            'batch_note':'원장 상태·갱신시각·PID/시작시각 확인을 구분합니다. OS lock 미검사이므로 독점 실행이나 작업 진척을 단정하지 않습니다.'}
