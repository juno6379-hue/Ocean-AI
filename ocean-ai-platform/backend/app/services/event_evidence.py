# 파일 역할: 기준정보 매칭·UTC 사건 구간·다대다 근거와 검토 후보의 계보를 검증합니다.
import hashlib
import json
import re
import math
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import or_
from app.models.domain import (StationMetadata, SensorMetadata, ObservationStandard,
    ObservationRaw, QCRuleResult, OperationLog, DocumentIndex, EventRegistry, AILabel,
    ApprovalHistory, DatasetRegistry)
from app.models.evidence import EventEvidence, SensorAlias, LabelReviewSnapshot, DatasetMembership
from app.services.observation_provenance import raw_for_standard, source_issue

TARGETS = {'DOCUMENT': ('chunk_id', DocumentIndex), 'OBSERVATION': ('observation_id', ObservationStandard),
           'QC_RESULT': ('qc_result_id', QCRuleResult), 'OPERATION_LOG': ('operation_id', OperationLog),
           'AI_LABEL': ('label_id', AILabel)}
QUALITY = {'NORMAL', 'SUSPECT', 'BAD', 'MISSING'}
CAUSES = {'facility_damage','equipment_fault','sensor_degradation','biofouling','power_fault',
          'communication_fault','qc_algorithm_error','cross_variable_inconsistency','statistical_outlier',
          'db_error','service_publication_error','natural_event','unknown'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def utc(value, require_offset=False):
    """DB의 기존 naive 시각은 UTC지만 새 외부 입력에는 offset을 요구한다."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:
        if require_offset:
            raise HTTPException(422, 'Timestamp must include UTC offset')
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def in_period(timestamp, start, end):
    return timestamp is not None and utc(timestamp) >= utc(start) and (end is None or utc(timestamp) < utc(end))


def validate_scope(db, station_id, sensor_id, variable_code):
    station = db.query(StationMetadata).filter_by(station_id=station_id).first()
    sensor = db.query(SensorMetadata).filter_by(sensor_id=sensor_id).first()
    if not station or not sensor:
        raise HTTPException(422, 'Station/sensor must exist in shared metadata')
    if sensor.station_id != station_id or sensor.variable_code != variable_code:
        raise HTTPException(422, 'Sensor station/variable does not match shared metadata')
    return sensor


def normalize_alias(value):
    return re.sub(r'\s+', '', value).casefold()


def resolve_sensor(db, station_id, variable_code, expression, start, end=None):
    """이름 유사도만으로 장비를 확정하지 않고 검토된 별칭 또는 정확한 ID를 사용한다."""
    expression = normalize_alias(expression)
    candidates = {}
    for sensor in db.query(SensorMetadata).filter_by(station_id=station_id, variable_code=variable_code):
        if normalize_alias(sensor.sensor_id) == expression:
            candidates[sensor.sensor_id] = {'sensor_id': sensor.sensor_id, 'match': 'EXACT_ID'}
    aliases = db.query(SensorAlias).filter_by(station_id=station_id, variable_code=variable_code, active=True)
    for alias in aliases:
        if normalize_alias(alias.alias_text) != expression:
            continue
        if alias.valid_start > utc(start) or (alias.valid_end and (end is None or utc(end) > alias.valid_end)):
            continue
        validate_scope(db, station_id, alias.sensor_id, variable_code)
        candidates[alias.sensor_id] = {'sensor_id': alias.sensor_id, 'match': 'REVIEWED_ALIAS',
                                      'alias_id': alias.alias_id, 'mapping_version': alias.mapping_version}
    return {'status': 'RESOLVED' if len(candidates)==1 else ('AMBIGUOUS' if candidates else 'UNRESOLVED'),
            'candidates': list(candidates.values())}


def get_event(db, event_id, lock=False):
    query = db.query(EventRegistry).filter_by(event_id=event_id)
    if lock: query = query.with_for_update()
    event = query.first()
    if not event: raise HTTPException(404, 'Event not found')
    return event


def link_evidence(db, event, kind, target_id, actor, provenance=None):
    """실체·관측 조건·시간을 확인하고 같은 링크의 재전송은 중복 없이 처리한다."""
    # 모든 링크는 실제 대상과 동일한 관측소·센서·변수 또는 명시적 문서 매핑을 가져야 한다.
    if kind not in TARGETS: raise HTTPException(422, 'Unsupported evidence kind')
    field, model = TARGETS[kind]
    if kind == 'DOCUMENT': target = db.query(model).filter_by(chunk_id=str(target_id)).first()
    elif kind == 'OPERATION_LOG':
        try: target = db.get(model, int(target_id))
        except (ValueError, TypeError): raise HTTPException(422, 'Invalid operation ID')
    else: target = db.get(model, str(target_id))
    if target is None: raise HTTPException(404, 'Evidence target not found')
    if kind == 'OBSERVATION':
        issue = source_issue(raw_for_standard(db, target))
        if issue: raise HTTPException(409, issue)
    validate_scope(db, event.station_id, event.sensor_id, event.variable_code)
    if kind == 'DOCUMENT':
        proof = provenance or {}
        if not proof.get('quote') or proof['quote'] not in (target.chunk_text or ''):
            raise HTTPException(422, 'Document evidence requires an exact source quote')
        for attr, expected in [('related_station_id',event.station_id),('related_sensor_id',event.sensor_id),
                               ('related_variable_code',event.variable_code)]:
            if getattr(target,attr) and getattr(target,attr) != expected:
                raise HTTPException(409, 'Document metadata conflicts with event scope')
    else:
        if target.station_id != event.station_id or target.sensor_id != event.sensor_id:
            raise HTTPException(422, 'Evidence station/sensor mismatch')
        if kind != 'OPERATION_LOG' and target.variable_code != event.variable_code:
            raise HTTPException(422, 'Evidence variable mismatch')
        if kind == 'AI_LABEL':
            if target.event_start != event.event_start or target.event_end != event.event_end:
                raise HTTPException(422, 'Label must use the exact event interval')
        else:
            timestamp = target.event_time if kind == 'OPERATION_LOG' else target.timestamp_utc
            if not in_period(timestamp,event.event_start,event.event_end):
                raise HTTPException(422, 'Evidence lies outside half-open event interval')
        if kind == 'QC_RESULT':
            observation = db.get(ObservationStandard,target.observation_id)
            if not observation or any(getattr(observation,k)!=getattr(target,k) for k in
                                      ['station_id','sensor_id','variable_code','timestamp_utc']):
                raise HTTPException(409, 'QC result does not match its source observation')
            link_evidence(db,event,'OBSERVATION',target.observation_id,actor,{'source':'QC_RESULT'})
    value = int(target_id) if kind=='OPERATION_LOG' else str(target_id)
    existing = db.query(EventEvidence).filter(EventEvidence.event_id==event.event_id,
                                             getattr(EventEvidence,field)==value).first()
    if existing: return existing
    link = EventEvidence(link_id=digest([event.event_id,kind,str(target_id)]),event_id=event.event_id,
                         created_by=actor,provenance=provenance or {'source':'EXPLICIT_LINK'},**{field:value})
    db.add(link); db.flush()
    return link


def attach_observations(db, event, actor):
    """종료 시각이 있는 사건만 일괄 연결하고 상한 초과를 명시적으로 거절한다."""
    if event.event_end is None: raise HTTPException(409,'Close the event interval before linking observations')
    rows = db.query(ObservationStandard).filter_by(station_id=event.station_id,
        sensor_id=event.sensor_id,variable_code=event.variable_code).filter(
        ObservationStandard.timestamp_utc>=event.event_start,ObservationStandard.timestamp_utc<event.event_end).limit(10001).all()
    if len(rows)>10000: raise HTTPException(422,'Narrow the event interval; limit is 10000 observations')
    for row in rows:
        link_evidence(db,event,'OBSERVATION',row.observation_id,actor,{'rule':'UTC_HALF_OPEN_V1'})
        for qc in db.query(QCRuleResult).filter_by(observation_id=row.observation_id):
            link_evidence(db,event,'QC_RESULT',qc.qc_result_id,actor,{'rule':'OBSERVATION_FK'})
    return len(rows)


def event_lineage(db, event_id):
    event = get_event(db,event_id)
    evidence=[]
    for link in db.query(EventEvidence).filter_by(event_id=event_id).order_by(EventEvidence.link_id):
        kind, field = next((k,f) for k,(f,_) in TARGETS.items() if getattr(link,f) is not None)
        _, model = TARGETS[kind]
        obj = (db.query(model).filter_by(chunk_id=link.chunk_id).one() if kind=='DOCUMENT'
               else db.get(model,getattr(link,field)))
        item={'link_id':link.link_id,'kind':kind,'target_id':str(getattr(link,field)),
              'provenance':link.provenance,'created_by':link.created_by}
        if kind=='DOCUMENT':
            item.update(document_id=obj.document_id,document_name=obj.document_title,
                report_date=obj.document_date,section=obj.section_name,page=obj.page_no,chunk=obj.chunk_text,
                chunk_hash=digest(obj.chunk_text),embedding_version=obj.embedding_version,
                metadata=obj.metadata_json or {})
        elif obj:
            item['data']={c.name:getattr(obj,c.name) for c in obj.__table__.columns}
        evidence.append(item)
    members=db.query(DatasetMembership).filter_by(event_id=event_id).all()
    return {'event':{c.name:getattr(event,c.name) for c in event.__table__.columns},'evidence':evidence,
            'datasets':[{'dataset_id':m.dataset_id,'observation_id':m.observation_id,'label_id':m.label_id,
                         'snapshot_hash':m.snapshot_hash} for m in members]}


def reverse_lineage(db, kind, target_id):
    if kind not in TARGETS: raise HTTPException(422,'Unsupported evidence kind')
    field,_=TARGETS[kind]
    try: value=int(target_id) if kind=='OPERATION_LOG' else str(target_id)
    except ValueError: raise HTTPException(422,'Invalid operation ID')
    ids=[r.event_id for r in db.query(EventEvidence).filter(getattr(EventEvidence,field)==value)]
    return {'kind':kind,'target_id':target_id,'events':[event_lineage(db,eid) for eid in sorted(set(ids))]}


def label_payload(label):
    return {key:(utc(getattr(label,key)).isoformat() if key in {'event_start','event_end'} and getattr(label,key)
                 else getattr(label,key)) for key in ['label_id','station_id','sensor_id','variable_code',
        'event_start','event_end','quality_label','error_type','error_cause','label_source','label_confidence','label_version']}


def validate_label(label):
    if not isinstance(label.quality_label,str) or not isinstance(label.error_cause,str) or label.quality_label not in QUALITY or label.error_cause not in CAUSES:
        raise HTTPException(422,'Invalid AI quality label or error cause')
    if label.label_confidence is not None and (not isinstance(label.label_confidence,(int,float))
        or isinstance(label.label_confidence,bool) or not math.isfinite(label.label_confidence) or not 0<=label.label_confidence<=1):
        raise HTTPException(422,'Label confidence must be between zero and one')
    if label.event_end is not None and utc(label.event_end)<=utc(label.event_start):
        raise HTTPException(422,'Invalid label event interval')


def review_payload(db,label):
    """라벨뿐 아니라 승인 때 검토한 사건·문서·관측·QC·운영 근거도 고정한다."""
    events=[]
    for link in db.query(EventEvidence).filter_by(label_id=label.label_id).order_by(EventEvidence.event_id):
        graph=event_lineage(db,link.event_id)
        # 이미 연결된 자료도 출처가 변경되면 승인하거나 승인 증거로 재사용할 수 없다.
        for evidence in graph['evidence']:
            if evidence['kind'] == 'OBSERVATION':
                observation = db.get(ObservationStandard, evidence['target_id'])
                issue = source_issue(raw_for_standard(db, observation))
                if issue: raise HTTPException(409, issue)
        events.append({'event':graph['event'],'evidence':[r for r in graph['evidence'] if r['kind']!='AI_LABEL']})
    # JSON 컬럼에 시간 객체를 직접 넣지 않도록 표준 문자열로 바꾼다.
    return json.loads(json.dumps({'label':label_payload(label),'events':events},default=str,ensure_ascii=False))


def approved_label_proof(db,label):
    if label.review_status!='APPROVED' or not label.reviewer_id: return None
    history=db.query(ApprovalHistory).filter_by(approval_type='AI_LABEL',target_id=label.label_id,
        approval_status='APPROVED',approved_by=label.reviewer_id).order_by(ApprovalHistory.id.desc()).first()
    if not history: return None
    saved=db.get(LabelReviewSnapshot,history.id)
    try:
        payload = review_payload(db, label)
    except HTTPException:
        return None
    if not saved or saved.payload_hash!=digest(payload) or digest(saved.payload)!=saved.payload_hash:
        return None
    return {'approval_id':history.id,'approved_by':history.approved_by,'approved_at':history.created_at,
            'label_hash':saved.payload_hash,'comment':history.comment}


def create_label_candidate(db,event,actor,label_version):
    if not event.event_end: raise HTTPException(409,'Closed event interval required')
    graph=event_lineage(db,event.event_id)
    for evidence in graph['evidence']:
        if evidence['kind'] == 'OBSERVATION':
            issue = source_issue(raw_for_standard(db, db.get(ObservationStandard, evidence['target_id'])))
            if issue: raise HTTPException(409, issue)
    kinds={r['kind'] for r in graph['evidence']}
    if not {'DOCUMENT','OBSERVATION','QC_RESULT','OPERATION_LOG'}<=kinds:
        raise HTTPException(409,'Document, observation, QC and operation evidence are required')
    label_id='LBL-'+digest([event.event_id,label_version])[:40]
    existing=db.get(AILabel,label_id)
    if existing: return existing
    flags={r['data']['result_flag'] for r in graph['evidence'] if r['kind']=='QC_RESULT'}
    quality='MISSING' if '9' in flags else 'BAD' if flags & {'4','B','BAD'} else 'SUSPECT' if flags & {'3','S','SUSPECT'} else 'NORMAL'
    # QC 판정은 추천의 입력일 뿐 원인 확정·승인 상태를 생성하지 않는다.
    label=AILabel(label_id=label_id,station_id=event.station_id,sensor_id=event.sensor_id,
        variable_code=event.variable_code,event_start=event.event_start,event_end=event.event_end,
        quality_label=quality,error_cause='unknown',label_source='EVENT_EVIDENCE_RECOMMENDATION',
        review_status='PENDING',label_version=label_version)
    db.add(label);db.flush()
    link_evidence(db,event,'AI_LABEL',label.label_id,actor,{'rule':'QC_RECOMMENDATION_ONLY_V1'})
    db.add(ApprovalHistory(approval_type='AI_LABEL',target_id=label.label_id,requested_by=actor,
                          approval_status='PENDING',comment='사건·문서·QC·운영 근거를 확인할 검토 후보'))
    return label
