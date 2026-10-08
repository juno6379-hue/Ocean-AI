# 파일 역할: 미래 관측을 사용하지 않는 Feature 값과 입력 관측 계보를 함께 생성합니다.
import math
import statistics
from datetime import timedelta
from fastapi import HTTPException
from app.models.domain import ObservationStandard, FeatureDefinition, FeatureValue
from app.models.evidence import EventEvidence, FeatureProvenance
from app.services.event_evidence import digest
from app.services.observation_provenance import raw_for_standard, source_issue

FEATURE_VERSION='event-causal-1'
DEFINITIONS={
    'evidence_value':('Raw Feature','현재 표준 관측값','value_standard(t)'),
    'evidence_moving_mean':('Temporal Feature','사건 시작 이후 최근 60분의 과거·현재 평균','mean(x[s]), max(event_start,t-60min)<=s<=t'),
    'evidence_moving_std':('Temporal Feature','사건 시작 이후 최근 60분의 과거·현재 표준편차','population_std(x[s]), max(event_start,t-60min)<=s<=t'),
}


def observation_payload(row):
    return {key:getattr(row,key) for key in ['observation_id','station_id','sensor_id','variable_code',
        'timestamp_utc','value_standard','standardization_version','standard_unit']}


def generate_event_features(db,event):
    """사건의 연결된 관측만 사용하며 QC 판정·승인 라벨은 입력 Feature로 쓰지 않는다."""
    if not event.event_end: raise HTTPException(409,'Closed event interval required')
    ids=[r.observation_id for r in db.query(EventEvidence).filter_by(event_id=event.event_id)
         if r.observation_id]
    rows=db.query(ObservationStandard).filter(ObservationStandard.observation_id.in_(ids)).order_by(ObservationStandard.timestamp_utc).all()
    for row in rows:
        issue = source_issue(raw_for_standard(db, row))
        if issue: raise HTTPException(409, issue)
    for feature_id,(group,description,logic) in DEFINITIONS.items():
        definition=db.get(FeatureDefinition,(feature_id,FEATURE_VERSION))
        if not definition:
            db.add(FeatureDefinition(feature_id=feature_id,feature_name=feature_id,feature_group=group,
                description=description,calculation_logic=logic,source_fields=['ObservationStandard.value_standard'],
                window_size='0' if feature_id=='evidence_value' else '60min',feature_version=FEATURE_VERSION))
        elif definition.calculation_logic!=logic:
            raise HTTPException(409,'Feature definition changed; use a new algorithm version')
    db.flush()
    created=0
    for index,row in enumerate(rows):
        if row.value_standard is None or not math.isfinite(row.value_standard): continue
        history=[r for r in rows[:index+1] if r.timestamp_utc>=row.timestamp_utc-timedelta(hours=1)
                 and r.value_standard is not None and math.isfinite(r.value_standard)]
        values={'evidence_value':row.value_standard,'evidence_moving_mean':statistics.mean(r.value_standard for r in history),
                'evidence_moving_std':statistics.pstdev(r.value_standard for r in history)}
        for feature_id,value in values.items():
            source=[row] if feature_id=='evidence_value' else history
            source_hash=digest([observation_payload(r) for r in source])
            key=(row.station_id,row.sensor_id,row.variable_code,row.timestamp_utc,feature_id,FEATURE_VERSION)
            saved=db.get(FeatureValue,key)
            provenance=db.get(FeatureProvenance,(row.observation_id,feature_id,FEATURE_VERSION))
            if saved:
                if not provenance or provenance.source_hash!=source_hash or saved.feature_value!=value:
                    raise HTTPException(409,'Feature inputs changed; generate a new feature version')
                continue
            db.add(FeatureValue(station_id=row.station_id,sensor_id=row.sensor_id,variable_code=row.variable_code,
                timestamp_utc=row.timestamp_utc,observation_id=row.observation_id,feature_id=feature_id,
                feature_version=FEATURE_VERSION,feature_value=value))
            db.add(FeatureProvenance(observation_id=row.observation_id,feature_id=feature_id,feature_version=FEATURE_VERSION,
                window_start=source[0].timestamp_utc,window_end=row.timestamp_utc,available_at=row.timestamp_utc,
                source_observation_ids=[r.observation_id for r in source],source_hash=source_hash))
            created+=1
    return {'event_id':event.event_id,'feature_version':FEATURE_VERSION,'created':created,
            'observations':len(rows),'input_policy':'PAST_AND_PRESENT_ONLY'}
