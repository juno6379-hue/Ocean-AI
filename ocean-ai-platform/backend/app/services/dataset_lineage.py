# 파일 역할: 승인 라벨과 Feature·원문 근거를 포함하는 데이터셋 내용 및 분할 누수를 검증합니다.
import math
from sqlalchemy import or_, text
from app.models.domain import (ObservationStandard, ObservationRaw, AILabel, FeatureValue,
                              FeatureDefinition, DatasetRegistry)
from app.models.evidence import EventEvidence, FeatureProvenance
from app.services.event_evidence import (approved_label_proof, label_payload, event_lineage,
                                        digest, in_period)
from app.services.evidence_features import observation_payload
from app.services.observation_provenance import raw_for_standard, source_issue

ORDER={'TRAIN':0,'VALIDATION':1,'TEST':2,'BLIND_TEST':3}


def family_lock(db,name):
    # 동시에 다른 분할이 등록되어 검사 사이를 통과하는 것을 PostgreSQL에서 방지한다.
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:name))'),{'name':'dataset:'+name})


def overlap(a,b):
    return '*' in (a or []) or '*' in (b or []) or bool(set(a or [])&set(b or []))


def leakage_errors(db,dataset,split_protocol=None):
    errors=[]
    if dataset.dataset_split not in ORDER: return errors
    # dataset_name은 분할을 공유하는 동일 평가 실험군이다. 다른 실험은 독립적으로 버전 관리한다.
    for other in db.query(DatasetRegistry).filter(DatasetRegistry.dataset_name==dataset.dataset_name,
                                                DatasetRegistry.dataset_id!=dataset.dataset_id):
        if other.dataset_split not in ORDER or other.dataset_split==dataset.dataset_split: continue
        strategy=split_protocol.get('split_strategy') if split_protocol else 'station_holdout'
        if strategy=='station_holdout' and overlap(dataset.station_scope,other.station_scope): errors.append('station_leakage:'+other.dataset_id)
        if strategy=='sensor_transition_holdout' and overlap(dataset.sensor_scope,other.sensor_scope): errors.append('sensor_leakage:'+other.dataset_id)
        earlier,later=(dataset,other) if ORDER[dataset.dataset_split]<ORDER[other.dataset_split] else (other,dataset)
        from datetime import timedelta
        embargo=split_protocol.get('embargo_seconds',0) if split_protocol else 0
        if earlier.period_end+timedelta(seconds=embargo)>later.period_start: errors.append('temporal_split_leakage:'+other.dataset_id)
    return sorted(set(errors))


def build_content(db,dataset):
    query=db.query(ObservationStandard).filter(ObservationStandard.timestamp_utc>=dataset.period_start,
                                               ObservationStandard.timestamp_utc<dataset.period_end)
    for field,values in [('station_id',dataset.station_scope),('sensor_id',dataset.sensor_scope),('variable_code',dataset.variable_scope)]:
        if values and '*' not in values: query=query.filter(getattr(ObservationStandard,field).in_(values))
    rows=query.order_by(ObservationStandard.observation_id).all()
    counts={'1':0,'3':0,'4':0,'9':0,'UNREVIEWED':0}
    quality_codes={'NORMAL':'1','SUSPECT':'3','BAD':'4','MISSING':'9'}
    records=[]; errors=[]; graphs={}
    definitions=db.query(FeatureDefinition).filter_by(feature_version=dataset.feature_version).order_by(FeatureDefinition.feature_id).all()
    if not definitions: errors.append('feature_definitions_missing')
    for row in rows:
        item_errors=[]
        issue = source_issue(raw_for_standard(db, row))
        if issue:
            errors.append(f'{row.observation_id}:{issue}')
            counts['UNREVIEWED'] += 1
            continue
        labels=db.query(AILabel).filter_by(station_id=row.station_id,sensor_id=row.sensor_id,
            variable_code=row.variable_code,label_version=dataset.label_version,review_status='APPROVED').filter(
            AILabel.event_start<=row.timestamp_utc,AILabel.event_end>row.timestamp_utc).all()
        proven=[(label,approved_label_proof(db,label)) for label in labels]
        proven=[(label,proof) for label,proof in proven if proof]
        if len(proven)!=1:
            counts['UNREVIEWED']+=1
            errors.append(f'{row.observation_id}:approved_label_missing_or_ambiguous')
            continue
        label,approval=proven[0]
        if label.quality_label not in quality_codes:
            errors.append(f'{row.observation_id}:unsupported_quality_label');continue
        events=[r.event_id for r in db.query(EventEvidence).filter_by(label_id=label.label_id)]
        common=[eid for eid in events if db.query(EventEvidence).filter_by(event_id=eid,observation_id=row.observation_id).first()]
        if len(common)!=1:
            errors.append(f'{row.observation_id}:event_link_missing_or_ambiguous');continue
        event_id=common[0]
        if event_id not in graphs:
            graph=event_lineage(db,event_id)
            # 역방향 Dataset 목록은 현재 snapshot에 다시 포함하면 자기 참조 해시가 된다.
            graphs[event_id]={'event':graph['event'],'evidence':graph['evidence']}
        graph=graphs[event_id]; event=graph['event']
        if (not event['event_end'] or event['event_start']<dataset.period_start or event['event_end']>dataset.period_end
            or label.event_start!=event['event_start'] or label.event_end!=event['event_end']):
            item_errors.append('event_interval_leakage_or_label_mismatch')
        if any(event[k]!=getattr(row,k) for k in ['station_id','sensor_id','variable_code']):
            item_errors.append('event_scope_mismatch')
        kinds={item['kind'] for item in graph['evidence']}
        if not {'DOCUMENT','OPERATION_LOG','QC_RESULT'}<=kinds: item_errors.append('source_evidence_incomplete')
        qc=[r for r in graph['evidence'] if r['kind']=='QC_RESULT' and r['data']['observation_id']==row.observation_id]
        if not qc: item_errors.append('observation_qc_missing')
        if dataset.qc_rule_version and any(r['data']['rule_version']!=dataset.qc_rule_version for r in qc):
            item_errors.append('qc_rule_version_mismatch')
        raw=db.query(ObservationRaw).filter_by(station_id=row.station_id,sensor_id=row.sensor_id,
                  variable_code=row.variable_code,timestamp_utc=row.timestamp_utc).first()
        if not raw: item_errors.append('raw_observation_missing')
        features=[]
        for definition in definitions:
            feature=db.get(FeatureValue,(row.station_id,row.sensor_id,row.variable_code,row.timestamp_utc,
                                       definition.feature_id,dataset.feature_version))
            provenance=db.get(FeatureProvenance,(row.observation_id,definition.feature_id,dataset.feature_version))
            if not feature or not provenance or feature.observation_id!=row.observation_id:
                item_errors.append('feature_or_provenance_missing:'+definition.feature_id);continue
            if feature.feature_value is not None and not math.isfinite(feature.feature_value):
                item_errors.append('nonfinite_feature:'+definition.feature_id)
            if (provenance.window_start<dataset.period_start or provenance.window_end>row.timestamp_utc
                or provenance.available_at>row.timestamp_utc or provenance.window_start>provenance.window_end):
                item_errors.append('feature_time_leakage:'+definition.feature_id)
            sources=[db.get(ObservationStandard,oid) for oid in provenance.source_observation_ids]
            if (not sources or any(s is None or s.station_id!=row.station_id or s.sensor_id!=row.sensor_id
                or s.variable_code!=row.variable_code or s.timestamp_utc<provenance.window_start
                or s.timestamp_utc>provenance.window_end for s in sources)):
                item_errors.append('feature_source_scope_or_time_invalid:'+definition.feature_id)
            elif digest([observation_payload(s) for s in sources])!=provenance.source_hash:
                item_errors.append('feature_source_changed:'+definition.feature_id)
            elif any(source_issue(raw_for_standard(db, s)) for s in sources):
                item_errors.append('feature_source_provenance_invalid:'+definition.feature_id)
            features.append({'feature_id':feature.feature_id,'feature_version':feature.feature_version,
                'value':feature.feature_value,'definition':{c.name:getattr(definition,c.name) for c in definition.__table__.columns},
                'provenance':{c.name:getattr(provenance,c.name) for c in provenance.__table__.columns}})
        errors.extend(row.observation_id+':'+error for error in item_errors)
        counts[quality_codes[label.quality_label]]+=1
        records.append({'id':row.observation_id,'station_id':row.station_id,'sensor_id':row.sensor_id,
            'variable_code':row.variable_code,'timestamp':row.timestamp_utc,'value_raw':row.value_raw,
            'value_standard':row.value_standard,'standardization_version':row.standardization_version,
            'unit':row.standard_unit,'raw':{c.name:getattr(raw,c.name) for c in raw.__table__.columns} if raw else None,
            'label':label_payload(label),'approval':approval,'event_id':event_id,'features':features,
            'quality_label':label.quality_label,'validation_errors':item_errors})
    snapshot={'schema_version':'event-evidence-dataset-1','dataset_id':dataset.dataset_id,
        'dataset_name':dataset.dataset_name,'dataset_version':dataset.dataset_version,'split':dataset.dataset_split,
        'period_start':dataset.period_start,'period_end':dataset.period_end,'station_scope':dataset.station_scope,
        'sensor_scope':dataset.sensor_scope,'variable_scope':dataset.variable_scope,
        'records':records,'events':graphs,'feature_version':dataset.feature_version,'label_version':dataset.label_version,
        'preprocessing_version':dataset.preprocessing_version,'qc_rule_version':dataset.qc_rule_version,
        'validation_errors':sorted(set(errors)),'source_observation_count':len(rows),
        'selection_hash':digest([observation_payload(row) for row in rows])}
    return rows,snapshot,counts
