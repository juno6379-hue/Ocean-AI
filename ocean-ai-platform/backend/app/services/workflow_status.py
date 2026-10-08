"""One read-only progress contract for the lake, review and MLOps menus.

Counts describe records, never approval or deployment. Source/month scope is
applied to channels; model/label/report totals explicitly remain global.
"""
from datetime import datetime,timezone
from sqlalchemy import text
from fastapi import HTTPException
from app.services.station_classification import resolve_scope

def status(db,source,start,end,network='',sea=''):
    if start>end:raise HTTPException(422,'Reverse month range')
    if not db.execute(text("SELECT to_regclass('facility_registry.run')")).scalar():
        raise HTTPException(503,'Facility evidence registry has not been published')
    row=db.execute(text("SELECT run_id,as_of,manifest FROM facility_registry.run WHERE manifest->>'status'='PUBLISHED_REVIEW_ONLY' ORDER BY run_id DESC LIMIT 1")).mappings().first()
    if not row:raise HTTPException(503,'No published facility review registry')
    rid=row['run_id'];params={'r':rid,'s':source,'a':start,'b':end}
    predicate='run_id=:r AND source_group=:s AND month>=:a AND month<=:b'
    scope=resolve_scope(db,network,sea)
    if scope is not None:
        key='include' if 'include' in scope else 'exclude'
        params['codes']=scope[key]
        predicate+=' AND '+('station_code = ANY(:codes)' if key=='include' else 'NOT (station_code = ANY(:codes))')
    q=f'''SELECT count(*) channels,count(DISTINCT station_code) stations,coalesce(sum(held_rows),0) held_rows,
        count(*) FILTER(WHERE physical_sensor_id IS NOT NULL) physical_sensor_linked,
        count(*) FILTER(WHERE valid_from IS NOT NULL AND valid_to IS NOT NULL) bounded_intervals,
        count(*) FILTER(WHERE nominal_interval_seconds IS NOT NULL) nominal_interval_known,
        count(*) FILTER(WHERE approval_status='APPROVED') approved_channels
        FROM facility_registry.channel_month WHERE {predicate}'''
    channels=dict(db.execute(text(q),params).mappings().one())
    metrics={}
    # Fixed identifiers only. Missing tables stay unknown rather than reporting 0.
    tables={'labels':'ai_label','datasets':'dataset_registry','models':'model_registry','reports':'report_registry',
       'qc_reviews':'qc_flag_history','events':'event_registry','approvals':'approval_history','training_runs':'retraining_history'}
    for key,table in tables.items():
        exists=db.execute(text('SELECT to_regclass(:t)'),{'t':'public.'+table}).scalar()
        metrics[key]=db.execute(text(f'SELECT count(*) FROM public.{table}')).scalar() if exists else None
    def approved(table,where):return db.execute(text(f'SELECT count(*) FROM public.{table} WHERE {where}')).scalar()
    metrics['approved_labels']=approved('ai_label',"review_status='APPROVED'") if metrics['labels'] is not None else None
    metrics['approved_datasets']=approved('dataset_registry',"status='APPROVED' AND approved_by IS NOT NULL") if metrics['datasets'] is not None else None
    metrics['production_models']=approved('model_registry',"status='PRODUCTION' AND deployment_status='PRODUCTION' AND is_champion IS TRUE") if metrics['models'] is not None else None
    reg={k:v['rows'] for k,v in row['manifest']['files'].items()}
    verified_docs=db.execute(text("SELECT count(*) FROM facility_registry.document WHERE run_id=:r AND vector_state='SQL_VECTOR_IDS_MATCH'"),{'r':rid}).scalar()
    stages=[
       {'stage':2,'name':'문서–사건–관측 연결','state':'REVIEW_REQUIRED','count':reg.get('document_link'), 'unit':'근거 연결 후보','href':'/data-lake','blockers':['2026-07-31 운영 명부·변경 근거 대조','시설/항목/센서별 기간 및 관측간격 확정']},
       {'stage':3,'name':'QC·전문가 검토','state':'REVIEW_REQUIRED','count':metrics['qc_reviews'],'unit':'QC 검토 기록 · 전역','href':'/qc','blockers':['원천 QC와 현재 재검사 분리','규칙·단위·센서 계약과 담당자 검토']},
       {'stage':4,'name':'검토 Label','state':'REVIEW_REQUIRED' if metrics['labels'] else 'NOT_EXECUTED','count':metrics['approved_labels'],'unit':'승인 Label · 전역','href':'/alerts','blockers':['관측 구간·사건·원문 근거','검토자의 명시적 승인']},
       {'stage':5,'name':'Dataset Registry','state':'REVIEW_REQUIRED' if metrics['datasets'] else 'NOT_EXECUTED','count':metrics['approved_datasets'],'unit':'승인 데이터셋 · 전역','href':'/data-lake','blockers':['업무별 고정 멤버십·기간 분할','중복·미래정보 누수 검사']},
       {'stage':6,'name':'업무별 모델 평가','state':'NOT_ESTABLISHED','count':metrics['models'],'unit':'등록 모델 · 전역','href':'/mlops','blockers':['예측·이상 탐지 후보 실험','검색·보고서 근거 평가와 비용·지연 측정']},
       {'stage':7,'name':'업무 서비스 검증','state':'REVIEW_REQUIRED','count':metrics['reports'],'unit':'보고서 등록 · 전역','href':'/reports','blockers':['수치·인용 재검증','담당자 수정·승인·재현 검증']},
       {'stage':8,'name':'MLOps 운영','state':'RUNTIME_VALIDATION_REQUIRED' if metrics['production_models'] else 'NOT_DEPLOYED','count':metrics['production_models'],'unit':'운영 등록 모델 · 전역','href':'/mlops','blockers':['승인 배포와 실제 추론 런타임 연결','성능·드리프트 감시·롤백 실증']},
    ]
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'as_of':str(row['as_of']),'run_id':rid,
        'snapshot':row['manifest']['snapshot'],'scope':{'source':source,'from':start,'to':end,'network':network,'sea':sea},
        'channels':channels,'coverage_supported':source!='HISTORICAL_RECONCILED','registry_counts':reg,'global_counts':metrics,'stages':stages,'verified_vector_documents':verified_docs,
        'operating_facility_count':None,'operating_count_status':'NOT_ESTABLISHED_FOR_ASOF',
        'training_worker_configured':False,'note':'근거 후보/실행/승인/운영을 구분합니다. 시설 기준일과 관측자료 조회기간은 별도입니다.'}
