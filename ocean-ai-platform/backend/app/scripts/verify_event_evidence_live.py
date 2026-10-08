# 파일 역할: 실제 사건의 전체 계보 준비 여부를 점검하고 부족한 근거를 문서화합니다.
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import inspect, func, or_
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.database import SessionLocal, engine
from app.core.config import settings
from app.models.domain import ObservationStandard, SensorMetadata, EventRegistry, AILabel, DatasetRegistry
from app.models.evidence import EventEvidence
from app.api.routes_events import router
from app.services.event_evidence import event_lineage, approved_label_proof
from app.services.observation_provenance import raw_for_standard, source_issue
from app.api.routes_datasets import read_snapshot
from app.scripts.inspect_evidence_readiness import inspect_readiness


def verify():
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'is_demo':False,'read_only':True,
            'readiness':inspect_readiness(),'cases':[]}
    with SessionLocal() as db:
        missing=db.query(ObservationStandard.sensor_id,func.count()).outerjoin(SensorMetadata,
            SensorMetadata.sensor_id==ObservationStandard.sensor_id).filter(or_(SensorMetadata.sensor_id.is_(None),
            SensorMetadata.station_id!=ObservationStandard.station_id,SensorMetadata.variable_code!=ObservationStandard.variable_code)).group_by(ObservationStandard.sensor_id).all()
        result['missing_or_conflicting_sensor_scopes']=[{'sensor_id':r[0],'observations':r[1]} for r in missing]
        for event in db.query(EventRegistry).order_by(EventRegistry.event_id).limit(100):
            graph=event_lineage(db,event.event_id); kinds={r['kind'] for r in graph['evidence']}
            issues=[]
            for evidence in graph['evidence']:
                if evidence['kind'] == 'OBSERVATION':
                    raw = raw_for_standard(db, db.get(ObservationStandard, evidence['target_id']))
                    issue = source_issue(raw)
                    if issue or 'TEST' in (raw.source_system or '').upper():
                        issues.append(issue or 'test_source_not_real_case')
            if not event.event_end: issues.append('event_end_missing')
            if not {'DOCUMENT','OBSERVATION','QC_RESULT','OPERATION_LOG','AI_LABEL'}<=kinds: issues.append('evidence_incomplete')
            labels=[db.get(AILabel,r.label_id) for r in db.query(EventEvidence).filter_by(event_id=event.event_id) if r.label_id]
            if not any(approved_label_proof(db,label) for label in labels): issues.append('reviewer_approved_label_missing')
            approved=[]
            for member in graph['datasets']:
                dataset=db.query(DatasetRegistry).filter_by(dataset_id=member['dataset_id'],status='APPROVED').first()
                if not dataset: continue
                try:
                    snapshot=read_snapshot(dataset)
                    if not snapshot.get('validation_errors') and event.event_id in snapshot.get('events',{}): approved.append(dataset.dataset_id)
                except Exception: issues.append('snapshot_integrity_failed')
            if not approved: issues.append('approved_dataset_snapshot_missing')
            result['cases'].append({'event_id':event.event_id,'status':'VERIFIED' if not issues else 'INCOMPLETE',
                                    'issues':issues,'datasets':sorted(set(approved))})
    app=FastAPI();app.include_router(router)
    with TestClient(app) as client:
        response=client.get('/api/events');assert response.status_code==200,response.text
        result['live_database_router_check']={'status_code':response.status_code,'events':len(response.json()['events']),
                                            'transport':'FastAPI TestClient / actual PostgreSQL'}
    required={'sensor_alias','event_evidence','label_review_snapshot','feature_provenance','dataset_membership'}
    result['schema_tables']=sorted(required&set(inspect(engine).get_table_names()))
    result['reviewer_authentication_configured']=any(x.get('role') in {'reviewer','admin'} for x in settings.API_IDENTITIES.values())
    result['verified_real_cases']=sum(r['status']=='VERIFIED' for r in result['cases'])
    result['status']='VERIFIED' if result['verified_real_cases'] else 'REAL_CASE_NOT_READY'
    result['required_next_inputs']=([] if result['verified_real_cases'] else [
        '실제 사건의 관측소·센서·변수 기준정보 및 검토된 장비 별칭',
        '보고일과 구별된 실제 사건 발생기간 및 해당 기간의 원시·표준 관측',
        '원문 청크·운영 기록·개별 QC 결과 연결',
        '실제 담당자의 라벨 검토·승인과 Feature 생성 후 Dataset 검증·승인'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=verify();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'status':result['status'],'verified_real_cases':result['verified_real_cases'],
        'schema_tables':result['schema_tables'],'unmatched_sensors':len(result['missing_or_conflicting_sensor_scopes']),
        'reviewer_authentication_configured':result['reviewer_authentication_configured']},ensure_ascii=False))
