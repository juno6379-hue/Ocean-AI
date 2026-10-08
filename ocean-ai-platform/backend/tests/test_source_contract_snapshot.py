"""Real API wiring with isolated source bytes, plus production draft negatives."""
import copy,hashlib,json
from pathlib import Path
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from app.core.config import settings
from app.core.security import Actor
from app.models.domain import ObservationRaw,ObservationStandard,ApprovalHistory,DatasetRegistry,AILabel
from app.models.source_contracts import SourceContractPacket
from app.models.source_observation_binding import SourceObservationBinding
from app.services import source_contract_authority as authority
from app.services.source_contract_review import exact_scope_key
from app.services.source_contract_snapshot import (canonical_bytes,read_bounded,create_candidate_snapshot,DependencyError)
from app.ml.comparison_runner import digest
from test_event_evidence import env,checked,register_dataset,START,QUOTE,OP,REVIEW


def write_json(path,body,compact=False):
    raw=authority.canonical_bytes(body) if compact else canonical_bytes(body)
    path.write_bytes(raw);return str(path),hashlib.sha256(raw).hexdigest()


def source_packet(tmp_path,event_id,with_receive=False):
    raw=tmp_path/'source.csv';raw.write_bytes(b'isolated actual source bytes\n')
    source_sha=hashlib.sha256(raw.read_bytes()).hexdigest()
    data=[];proofs={}
    scope=dict(source_group='ISOLATED_TEST',station_code='ST1',item_code='TIDE_RAW',month='2025-02',depth_step=None,depth_from=None,depth_to=None)
    for i,value in enumerate(['50.0','150.0','9999.0']):
        data.append(dict(OBS_POST_ID='ST1',OBS_ITEM_CODE='TIDE_RAW',OBS_TIME=f'2025-02-01 09:0{i}:00',OBS_VALUE=value,QC_FLAG='OK',MQC_FLAG='G ',N1_AQC_FLAG=''))
        if with_receive:data[-1]['RECEIVE_TIME']=data[-1]['OBS_TIME']
    parquet=tmp_path/'raw.parquet';pq.write_table(pa.Table.from_pylist(data),parquet)
    parquet_sha=hashlib.sha256(parquet.read_bytes()).hexdigest()
    codebook=tmp_path/'qc.json';codebook.write_text('{"isolated_test_only":true}')
    csha=hashlib.sha256(codebook.read_bytes()).hexdigest()
    manifest=tmp_path/'manifest.json'
    write_json(manifest,dict(source_path=str(raw),source_sha256=source_sha,source_system='ISOLATED_TEST',source_size=raw.stat().st_size,
        raw_path=str(parquet),raw_sha256=parquet_sha,raw_rows=3,status='VERIFIED'))
    msha=hashlib.sha256(manifest.read_bytes()).hexdigest()
    files=[dict(role=role,path=p.name,sha256=sha,bytes=p.stat().st_size) for role,p,sha in
        [('RAW',raw,source_sha),('PARQUET',parquet,parquet_sha),('QC_CODEBOOK',codebook,csha),('SOURCE_MANIFEST',manifest,msha)]]
    for i,value in enumerate(['50.0','150.0','9999.0']):
        proof=dict(physical_sensor_id='isolated-serial-001',sensor_episode_id='isolated-episode-001',source_group='ISOLATED_TEST',
            source_station_code='ST1',source_item_code='TIDE_RAW',source_station_literal='ST1',source_item_literal='TIDE_RAW',
            source_identifier_transform={'station':'IDENTITY','item':'IDENTITY'},source_month='2025-02',exact_scope_key=exact_scope_key(scope),
            source_row_locator=f'parquet_row_group=0;row_index={i}',timezone='Asia/Seoul',source_clock_semantics='OBSERVED_AT',
            qc_rule_version='1',event_id=event_id,canonical_station_id='ST1',canonical_sensor_id='S1',standard_variable='TIDE',
            source_unit='cm',unit='cm',quantity_kind='SCALAR',observation_role='OBSERVED',training_value_status='ACCEPTED',
            source_sha256=source_sha,parquet_sha256=parquet_sha,source_qc_codebook_sha256=csha,source_manifest_sha256=msha,
            source_time_raw=f'2025-02-01 09:0{i}:00',source_value_raw=value,source_qc_raw='OK',source_mqc_raw='G ',source_n1_aqc_raw='',
            source_receive_time_raw=data[i].get('RECEIVE_TIME'),
            source_receive_timestamp_utc=f'2025-02-01T00:0{i}:00+00:00' if with_receive else None,
            source_receive_clock_policy='LOCAL_OBSERVED_TIMEZONE' if with_receive else 'ABSENT_IN_SOURCE',
            timestamp_utc=f'2025-02-01T00:0{i}:00+00:00',available_at=f'2025-02-01T00:0{i}:00+00:00',qc_available_at=f'2025-02-01T00:0{i}:00+00:00',
            effective_start='2024-01-01T00:00:00+00:00',effective_end='2026-01-01T00:00:00+00:00',
            qc_effective_start='2024-01-01T00:00:00+00:00',qc_effective_end='2026-01-01T00:00:00+00:00',
            depth={'step':None,'from':None,'to':None},value=float(value),validation_errors=[],
            quantity_transform={'scale':1,'offset':0,'datum':{'kind':'SOURCE_DATUM','identifier':'ISOLATED_FIXTURE_DATUM'},'reference':'isolated test only'})
        proof['field_evidence']={f:[{'file_sha256':source_sha,'locator':'isolated fixture line 1','claim':'isolated test evidence'}] for f in authority.REQUIRED_EVIDENCE}
        proofs[f'O{i}']=proof
    return dict(schema_version='source_contract_v2',contract_id='fixture-source-1',scope=[scope],
        source_availability_policy='RAW_AND_TRANSFORM_REQUIRED',source_row_reuse_policy={'policy':'FORBIDDEN'},files=files,observations=proofs,validation_errors=[],
        agent_review={'status':'TECHNICALLY_REVIEWED','approved':False})


def fixed_protocols(tmp_path,db,features):
    base=dict(schema_version='ocean-model-protocol-1',status='DRAFT',protocol_id='isolated-test',version='1',domain='TIDE',item_id='TIDE_RAW',
        target_variable='TIDE',unit='cm',task='QUALITY_REVIEW',quantity_kind='SCALAR')
    split=dict(base,role='SPLIT_PROTOCOL',split_strategy='station_holdout',dataset_ids={'TRAIN':'DS1','VALIDATION':'DS2','TEST':'DS3'},
        holdout_locked=True,periods={s:{'start':a,'end':b} for s,a,b in [('TRAIN','2025-02-01T00:00:00Z','2025-02-01T00:02:00Z'),
        ('VALIDATION','2025-03-01T00:00:00Z','2025-03-02T00:00:00Z'),('TEST','2025-04-01T00:00:00Z','2025-04-02T00:00:00Z')]},
        member_ids_sha256={'TRAIN':digest(['O0','O1']),'VALIDATION':digest(['V0']),'TEST':digest(['T0'])},
        disjoint_groups=['EVENT','SOURCE_RECORD','DOCUMENT_FAMILY','SENSOR_EPISODE','STATION'],embargo_seconds=0)
    evaluation=dict(base,role='EVALUATION_PROTOCOL',feature_ids=features,test_pair_policy='ALL_APPROVED_COMMON_ORIGINS',
        preprocessing_fit='TRAIN_ONLY',horizon_seconds=0,lookback_seconds=60,positive_labels=['BAD'],worker_policy={'max_attempts':1,'lease_seconds':60},
        zero_mad_policy='UNIT_SCALE_ONE_EXPLICIT_ENGINEERING_BASELINE',normal_quantiles=[0.9],human_label_policy='PRESERVE_ALL_QC_LABELS_BINARY_SCORE_ONLY_NORMAL_BAD')
    acceptance=dict(base,role='ACCEPTANCE_POLICY',limits={'min_test_samples':1,'max_local_p95_ms':10,'min_f1':0.5,'max_false_positive_rate':0.2,'max_false_negative_rate':0.2,
        'min_guide_rule_coverage':0.5,'min_human_qc_agreement':0.5,'max_false_good_rate':0.2},cost_policy='LOCAL_PILOT_COST_NOT_REQUIRED')
    specs=[]
    for body in [split,evaluation,acceptance]:
        path,sha=write_json(tmp_path/(body['role']+'.json'),body,True)
        db.add(ApprovalHistory(approval_type='MODEL_PROTOCOL',target_id=sha,requested_by='reviewer',approved_by='reviewer',approval_status='APPROVED',comment='snapshot_sha256='+sha))
        specs.append({'role':body['role'],'path':path,'sha256':sha})
    db.commit();return specs


def real_chain(client,sessions,tmp_path,monkeypatch,packet_mutator=None,expected_valid=True,with_receive=False):
    monkeypatch.setattr(authority,'SOURCE_ROOT',tmp_path)
    monkeypatch.setenv('SOURCE_CONTRACT_ALLOWED_ROOTS',json.dumps([str(tmp_path)]))
    with sessions() as db:
        db.query(ObservationStandard).delete();db.query(ObservationRaw).delete();db.commit()
    checked(client.post('/api/events/sensor-aliases',headers=REVIEW,json={'station_id':'ST1','sensor_id':'S1','variable_code':'TIDE','alias_text':'주 조위계','mapping_version':'1','valid_start':'2024-01-01T00:00:00Z'}))
    event=checked(client.post('/api/events/from-document',headers=OP,json={'station_id':'ST1','variable_code':'TIDE','expression':'주 조위계','event_start':'2025-02-01T09:00:00+09:00','event_end':'2025-02-01T09:02:00+09:00','event_type':'COMMUNICATION_DELAY','chunk_id':'C1','period_quote':QUOTE,'operation_quote':'통신 지연 확인','operation_time':'2025-02-01T09:01:00+09:00'}))
    packet=source_packet(tmp_path,event['event_id'],with_receive)
    if packet_mutator is not None:packet_mutator(packet)
    with sessions() as db:
        authority.request_contract(db,packet,Actor('operator','operator'))
        decision=authority.decide_contract(db,packet['contract_id'],authority.receipt_sha256(packet),'APPROVED',Actor('reviewer','reviewer'))
        db.commit()
    path,sha=write_json(tmp_path/'approved-receipt.json',decision['receipt'],True)
    ingest={'receipt_path':path,'receipt_sha256':sha}
    assert checked(client.post('/api/datasets/source-ingest',headers=OP,json=ingest))['inserted']==3
    assert checked(client.post('/api/datasets/source-ingest',headers=OP,json=ingest))['already_bound']==3
    eid=event['event_id']
    checked(client.post('/api/qc/rules/execute',headers=OP,json={'station_id':'ST1','sensor_id':'S1','variable_code':'TIDE'}))
    assert checked(client.post(f'/api/events/{eid}/link-observations',headers=OP))['observations']==2
    label=checked(client.post(f'/api/events/{eid}/label-candidates',headers=OP,json={'label_version':'1'}))
    checked(client.post('/api/approvals/approve',headers=REVIEW,json={'target_type':'AI_LABEL','target_id':label['label_id']}))
    checked(client.post(f'/api/events/{eid}/features',headers=OP))
    checked(register_dataset(client))
    with sessions() as db:
        from app.models.domain import FeatureDefinition
        specs=fixed_protocols(tmp_path,db,[r.feature_id for r in db.query(FeatureDefinition).all()])
    specs.append({'role':'SOURCE_CONTRACT','path':path,'sha256':sha})
    built=checked(client.post('/api/datasets/DS1/build',headers=OP,json={'dependencies':specs}))
    if expected_valid:assert built['validation_errors']==[],built
    return built,packet,ingest,specs


def test_real_ingest_to_v2_approval_preserves_binding_and_original_qc(env,tmp_path,monkeypatch):
    client,sessions=env
    built,packet,_,specs=real_chain(client,sessions,tmp_path,monkeypatch)
    assert checked(client.post('/api/datasets/DS1/validate',headers=OP))['status']=='VALIDATED'
    checked(client.post('/api/datasets/DS1/approve',headers=REVIEW))
    snapshot=checked(client.get('/api/datasets/DS1/lineage'))['snapshot']
    assert snapshot['schema_version']=='event-evidence-dataset-2'
    assert snapshot['records'][0]['raw']['mqc_flag']=='G '
    assert snapshot['records'][0]['raw']['source_row_locator']=='parquet_row_group=0;row_index=0'
    assert snapshot['records'][0]['timestamp'].endswith('+00:00')
    assert len(snapshot['source_contracts'])==1 and len(snapshot['frozen_protocol_dependencies'])==3
    with sessions() as db:
        assert db.query(SourceObservationBinding).count()==3
        assert db.get(ObservationStandard,'O0').value_raw==50
    assert client.post('/api/datasets/DS1/build',headers=OP,json={'dependencies':specs}).status_code==409


def test_reviewed_primary_receive_clock_is_preserved_through_ingest_and_snapshot(env,tmp_path,monkeypatch):
    client,sessions=env
    real_chain(client,sessions,tmp_path,monkeypatch,with_receive=True)
    snapshot=checked(client.get('/api/datasets/DS1/lineage'))['snapshot']
    raw=snapshot['records'][0]['raw']
    assert raw['source_receive_time_raw']=='2025-02-01 09:00:00'
    assert raw['source_receive_timestamp_utc']=='2025-02-01T00:00:00+00:00'
    assert raw['source_receive_clock_policy']=='LOCAL_OBSERVED_TIMEZONE'
    assert raw['receive_time']==raw['source_receive_timestamp_utc']
    assert checked(client.post('/api/datasets/DS1/validate',headers=OP))['status']=='VALIDATED'
    checked(client.post('/api/datasets/DS1/approve',headers=REVIEW))


@pytest.mark.parametrize('field',['available_at','qc_available_at'])
def test_approved_source_release_cannot_be_backdated_by_feature_provenance(env,tmp_path,monkeypatch,field):
    client,sessions=env
    def later_release(packet):
        packet['observations']['O0'][field]='2025-02-01T00:01:00+00:00'
    built,_,_,_=real_chain(client,sessions,tmp_path,monkeypatch,later_release,False)
    assert any(e.startswith('SOURCE_FEATURE_AVAILABLE_AFTER_DECLARED_TIME:') and e.endswith(':'+field) for e in built['validation_errors'])
    assert any(e.startswith('CLOCK_ORIGIN_POLICY_REVIEW_REQUIRED:') and e.endswith(':'+field) for e in built['validation_errors'])
    assert checked(client.post('/api/datasets/DS1/validate',headers=OP))['status']=='INVALID'
    assert client.post('/api/datasets/DS1/approve',headers=REVIEW).status_code==409
    with sessions() as db:
        assert db.query(SourceObservationBinding).count()==3
        observation=db.get(ObservationStandard,'O0')
        assert db.query(ObservationRaw).filter_by(station_id=observation.station_id,sensor_id=observation.sensor_id,
            variable_code=observation.variable_code,timestamp_utc=observation.timestamp_utc).one().mqc_flag=='G '
        assert db.query(ApprovalHistory).filter_by(approval_type='DATASET',approval_status='APPROVED').count()==0


@pytest.mark.parametrize('source_ids',[['outside-reviewed-contract'],[None],[{'invented':'source'}]])
def test_feature_source_membership_must_bind_to_the_approved_receipt(env,tmp_path,monkeypatch,source_ids):
    from app.services.source_contract_snapshot import overlay_proofs
    client,sessions=env
    real_chain(client,sessions,tmp_path,monkeypatch)
    snapshot=checked(client.get('/api/datasets/DS1/lineage'))['snapshot']
    feature=snapshot['records'][0]['features'][0]
    feature['provenance']['source_observation_ids']=source_ids
    with sessions() as db:checked_snapshot=overlay_proofs(db,snapshot)
    assert any(e.startswith('SOURCE_FEATURE_CONTRACT_OR_BINDING_MISSING:') for e in checked_snapshot['validation_errors'])


@pytest.mark.parametrize('mutation',['parquet','contract_revoke','protocol_revoke','binding','receipt','membership','db_membership'])
def test_live_source_dependency_and_approval_changes_block_dataset(env,tmp_path,monkeypatch,mutation):
    client,sessions=env
    _,packet,ingest,specs=real_chain(client,sessions,tmp_path,monkeypatch)
    assert checked(client.post('/api/datasets/DS1/validate',headers=OP))['status']=='VALIDATED'
    with sessions() as db:
        if mutation=='contract_revoke':authority.decide_contract(db,packet['contract_id'],authority.receipt_sha256(packet),'REVOKED',Actor('reviewer','reviewer'))
        if mutation=='protocol_revoke':
            sha=specs[0]['sha256'];db.add(ApprovalHistory(approval_type='MODEL_PROTOCOL',target_id=sha,approval_status='REVOKED',comment='snapshot_sha256='+sha))
        if mutation=='binding':db.get(SourceObservationBinding,'O0').payload={}
        if mutation=='membership':db.get(ObservationStandard,'O0').value_standard=0
        if mutation=='db_membership':
            from app.models.evidence import DatasetMembership
            db.query(DatasetMembership).filter_by(dataset_id='DS1').first().snapshot_hash='0'*64
        db.commit()
    if mutation=='parquet':(tmp_path/'raw.parquet').write_bytes(b'changed actual source bytes')
    if mutation=='receipt':
        dependency=Path(settings.DATASET_SNAPSHOT_DIR)/'dependencies'/f"{ingest['receipt_sha256']}.json";dependency.write_text('{}')
    assert client.post('/api/datasets/DS1/approve',headers=REVIEW).status_code==409


def test_pending_or_caller_approved_source_never_ingests(env,tmp_path,monkeypatch):
    client,sessions=env
    monkeypatch.setenv('SOURCE_CONTRACT_ALLOWED_ROOTS',json.dumps([str(tmp_path)]))
    path,sha=write_json(tmp_path/'fake.json',{'schema_version':'source-semantics-identity-period-event-1','source_contract_schema':'source_contract_v2','status':'APPROVED','approved_by':'invented','approval_complete':True},True)
    response=client.post('/api/datasets/source-ingest',headers=OP,json={'receipt_path':path,'receipt_sha256':sha})
    assert response.status_code==422 and 'SOURCE_APPROVAL' in response.text
    with sessions() as db:assert db.query(SourceObservationBinding).count()==0


def test_source_candidate_locator_and_raw_literals_are_not_approved(tmp_path):
    packet=source_packet(tmp_path,'unapproved-event-candidate')
    manifest=tmp_path/'manifest.json';sha=hashlib.sha256(manifest.read_bytes()).hexdigest()
    result=create_candidate_snapshot(str(tmp_path/'raw.parquet'),str(manifest),sha,'ISOLATED_TEST',packet['scope'],tmp_path/'snap',limit=2,roots=[tmp_path])
    body=result['snapshot'];assert body['candidate_count']==2 and body['training_eligible'] is False
    assert body['operational_membership_count']==0 and body['candidate_rows'][0]['source_mqc_raw']=='G '
    assert body['candidate_rows'][1]['source_row_locator']=='parquet_row_group=0;row_index=1'
    assert body['candidate_rows'][0]['timezone'] is None and body['whole_month_coverage'] is False
    with pytest.raises(DependencyError,match='HASH_MISMATCH'):
        read_bounded(manifest,[tmp_path],'0'*64)


@pytest.mark.parametrize('mutation',[lambda s:s.update(source_contracts=None),lambda s:s.update(source_contract_root=[]),
    lambda s:s.update(verified_source_roots=[None]),lambda s:s.update(source_contracts=[None]),
    lambda s:s.update(source_contracts=[{'role':'SOURCE_CONTRACT','sha256':'0'*64,'path':'../escape.json'}])])
def test_malformed_frozen_dependencies_report_errors(tmp_path,mutation):
    from app.services.source_contract_snapshot import frozen_integrity_errors
    body={'schema_version':'event-evidence-dataset-2','source_contract_root':str(tmp_path),'verified_source_roots':[str(tmp_path)],'source_contracts':[]}
    mutation(body)
    assert frozen_integrity_errors(None,body,tmp_path)


def test_disallowed_candidate_is_guarded_before_parquet_metadata_read(tmp_path,monkeypatch):
    packet=source_packet(tmp_path,'draft');manifest=tmp_path/'manifest.json'
    sha=hashlib.sha256(manifest.read_bytes()).hexdigest()
    other=tmp_path/'allowed';other.mkdir()
    def forbidden(*args,**kwargs):raise AssertionError('Parquet must not be opened before root guard')
    monkeypatch.setattr(pq,'ParquetFile',forbidden)
    with pytest.raises(DependencyError,match='OUTSIDE_ALLOWED_ROOTS'):
        create_candidate_snapshot(str(tmp_path/'raw.parquet'),str(manifest),sha,'ISOLATED_TEST',packet['scope'],other,roots=[other])


def test_approved_temporal_strategy_allows_station_reuse_with_embargo(env,tmp_path,monkeypatch):
    client,sessions=env
    _,_,_,specs=real_chain(client,sessions,tmp_path,monkeypatch)
    body=json.loads(Path(specs[0]['path']).read_text(encoding='utf8'))
    body.update(split_strategy='temporal_with_purge',disjoint_groups=['EVENT','SOURCE_RECORD','DOCUMENT_FAMILY'],embargo_seconds=60)
    path,sha=write_json(tmp_path/'temporal-split.json',body,True)
    with sessions() as db:
        db.add(ApprovalHistory(approval_type='MODEL_PROTOCOL',target_id=sha,approved_by='reviewer',approval_status='APPROVED',comment='snapshot_sha256='+sha));db.commit()
    dataset=register_dataset(client,'DS2',dataset_split='VALIDATION',period_start='2025-03-01T00:00:00Z',period_end='2025-03-02T00:00:00Z').request.content
    # Legacy registration remains strict for the same station.
    assert client.post('/api/datasets',content=dataset,headers=OP|{'content-type':'application/json'}).status_code==409
    request={'dataset':json.loads(dataset),'split_protocol':{'role':'SPLIT_PROTOCOL','path':path,'sha256':sha}}
    assert checked(client.post('/api/datasets/register-reviewed',headers=OP,json=request))['dataset_id']=='DS2'
    with sessions() as db:
        from app.services.dataset_lineage import leakage_errors
        candidate=db.get(DatasetRegistry,'DS2');candidate.period_start=START
        assert any('temporal_split_leakage' in e for e in leakage_errors(db,candidate,body))


def typed_source_packet(tmp_path,kind):
    packet=source_packet(tmp_path,'typed-event-fixture')
    proof=packet['observations']['O0'];packet['observations']={'O0':proof}
    metadata={
        'CIRCULAR_DEGREES':{'magnitude_unit':'m/s'},
        'SIGNED_RADIAL':{'coordinate_frame':'SITE_RADIAL','site_geometry_version':'test-1','coverage_fraction':1,'qc_eligible':True},
        'VECTOR_UV':{'coordinate_frame':'EAST_NORTH','grid_cell_id':'test-cell','geometry_version':'test-1'},
        'PROFILE_BINS':{'coordinate_frame':'DEPTH_BELOW_SURFACE','layout_version':'test-1','target_variable':'TEMPERATURE','unit':'degC','value_representation':'SCALAR'},
        'TRAJECTORY':{'coordinate_frame':'WGS84','trajectory_id':'test-1'}}[kind]
    unit='degree' if kind in {'CIRCULAR_DEGREES','TRAJECTORY'} else 'degC' if kind=='PROFILE_BINS' else 'm/s'
    target='POSITION' if kind=='TRAJECTORY' else 'WIND_DIRECT' if kind=='CIRCULAR_DEGREES' else 'TEMPERATURE' if kind=='PROFILE_BINS' else 'CURRENT_VECTOR'
    proof.update(quantity_kind=kind,unit=unit,source_unit=unit,standard_variable=target,canonical_sensor_id='S-'+kind)
    row=pq.read_table(tmp_path/'raw.parquet').slice(0,1).to_pylist()[0];payload=dict(metadata,representation=kind)
    if kind=='PROFILE_BINS':
        proof['depth']['from']=12.5;row['FROM_DEPTH']=12.5
        packet['scope'][0]['depth_from']=12.5
        proof['exact_scope_key']=exact_scope_key(packet['scope'][0])
    fields={}
    for field in authority.TYPED_FIELDS[kind]:
        value='bin-1' if field=='bin_ids' else '1.5' if field=='magnitude' else '35' if field=='latitude' else '122.5' if field=='longitude' else '12.5'
        row['component_'+field]=value
        bound={'row_group':0,'row_index':0,'column':'component_'+field,'source_group':proof['source_group'],
            'source_station_code':proof['source_station_code'],'source_item_code':proof['source_item_code'],
            'source_station_literal':proof['source_station_literal'],'source_item_literal':proof['source_item_literal'],
            'source_identifier_transform':proof['source_identifier_transform'],'source_time_raw':proof['source_time_raw'],
            'depth':proof['depth'],'exact_scope_key':proof['exact_scope_key'],'scale':1,'offset':0,'source_unit':unit,
            'unit':'degree' if kind in {'CIRCULAR_DEGREES','TRAJECTORY'} and field in {'value','longitude','latitude'} else 'm/s' if field=='magnitude' else 'm' if field=='depths' else unit}
        fields[field]=[bound] if kind=='PROFILE_BINS' else bound
        number=value if field=='bin_ids' else float(value)
        payload[field]=[number] if kind=='PROFILE_BINS' else number
    parquet=tmp_path/'raw.parquet';pq.write_table(pa.Table.from_pylist([row]),parquet)
    psha=hashlib.sha256(parquet.read_bytes()).hexdigest();manifest=tmp_path/'manifest.json'
    m=json.loads(manifest.read_text(encoding='utf8'));m.update(raw_sha256=psha,raw_rows=1);write_json(manifest,m)
    msha=hashlib.sha256(manifest.read_bytes()).hexdigest()
    for file in packet['files']:
        if file['role']=='PARQUET':file.update(sha256=psha,bytes=parquet.stat().st_size)
        if file['role']=='SOURCE_MANIFEST':file.update(sha256=msha,bytes=manifest.stat().st_size)
    for field,bound in fields.items():
        for b in bound if isinstance(bound,list) else [bound]:
            b.update(file_sha256=psha,source_sha256=proof['source_sha256'],source_manifest_sha256=msha)
            for key in authority.COMPONENT_REQUIRED_STRINGS:
                if key in proof:b[key]=proof[key]
            for key in ['effective_start','effective_end','qc_effective_start','qc_effective_end','timestamp_utc','available_at','qc_available_at',
                'source_qc_raw','source_mqc_raw','source_n1_aqc_raw','source_qc_codebook_sha256']:
                b[key]=proof[key]
            b.update(source_receive_time_raw=None,source_receive_timestamp_utc=None,source_receive_clock_policy='ABSENT_IN_SOURCE',
                training_value_status='ACCEPTED',source_qc_interpretation='ACCEPTED',
                field_evidence={key:copy.deepcopy(proof['field_evidence']['quantity_kind']) for key in authority.COMPONENT_REQUIRED_EVIDENCE})
    proof.update(parquet_sha256=psha,source_manifest_sha256=msha,typed_payload=payload,
        typed_payload_bindings={'representation':kind,'fields':fields,'constant_metadata':metadata})
    proof['field_evidence']['typed_payload']=copy.deepcopy(proof['field_evidence']['quantity_kind'])
    proof['field_evidence']['canonical_sensor_identity']=copy.deepcopy(proof['field_evidence']['quantity_kind'])
    return packet


@pytest.mark.parametrize('kind',['CIRCULAR_DEGREES','SIGNED_RADIAL','VECTOR_UV','PROFILE_BINS','TRAJECTORY'])
def test_typed_source_ingest_preserves_actual_component_cells_without_scalar_promotion(env,tmp_path,monkeypatch,kind):
    from app.services.source_contract_snapshot import overlay_proofs
    client,sessions=env
    monkeypatch.setattr(authority,'SOURCE_ROOT',tmp_path)
    monkeypatch.setenv('SOURCE_CONTRACT_ALLOWED_ROOTS',json.dumps([str(tmp_path)]))
    packet=typed_source_packet(tmp_path,kind)
    assert authority.packet_errors(packet,verify_sources=True)==[]
    with sessions() as db:
        db.query(ObservationStandard).delete();db.query(ObservationRaw).delete();db.commit()
        requested=authority.request_contract(db,packet,Actor('operator','operator'))
        decision=authority.decide_contract(db,packet['contract_id'],requested['packet_sha256'],'APPROVED',Actor('reviewer','reviewer'));db.commit()
    path,sha=write_json(tmp_path/'typed-receipt.json',decision['receipt'],True)
    result=checked(client.post('/api/datasets/source-ingest',headers=OP,json={'receipt_path':path,'receipt_sha256':sha,'register_metadata':True}))
    assert result['inserted']==1
    root=Path(settings.DATASET_SNAPSHOT_DIR);(root/'dependencies').mkdir(parents=True,exist_ok=True)
    (root/'dependencies'/f'{sha}.json').write_bytes(Path(path).read_bytes())
    with sessions() as db:
        observation=db.get(ObservationStandard,'O0');raw=db.query(ObservationRaw).one()
        assert observation.value_standard is None
        assert db.get(SourceObservationBinding,'O0').payload['typed_payload_bindings']==packet['observations']['O0']['typed_payload_bindings']
        record={'id':'O0','station_id':observation.station_id,'sensor_id':observation.sensor_id,'variable_code':observation.variable_code,'unit':observation.standard_unit,
            'timestamp':observation.timestamp_utc.replace(tzinfo=__import__('datetime').timezone.utc).isoformat(),'value_standard':None,
            'raw':{c.name:getattr(raw,c.name) for c in raw.__table__.columns}}
        snap={'source_contract_root':str(root),'source_contracts':[{'sha256':sha,'path':f'dependencies/{sha}.json','review_errors':[],
            'approval_receipt':authority.verify_approved_receipt(db,decision['receipt'],sha)}],'records':[record],'validation_errors':[]}
        assert overlay_proofs(db,snap)['validation_errors']==[]
        assert snap['records'][0]['typed_payload']==packet['observations']['O0']['typed_payload']


def test_failed_ingest_commit_rolls_back_observations_and_source_bindings(env,tmp_path,monkeypatch):
    from app.api.routes_datasets import source_ingest,SourceIngestRequest
    client,sessions=env
    monkeypatch.setattr(authority,'SOURCE_ROOT',tmp_path)
    monkeypatch.setenv('SOURCE_CONTRACT_ALLOWED_ROOTS',json.dumps([str(tmp_path)]))
    packet=source_packet(tmp_path,'isolated-source-review-only-event-id')
    with sessions() as db:
        db.query(ObservationStandard).delete();db.query(ObservationRaw).delete();db.commit()
        request=authority.request_contract(db,packet,Actor('operator','operator'))
        decision=authority.decide_contract(db,packet['contract_id'],request['packet_sha256'],'APPROVED',Actor('reviewer','reviewer'));db.commit()
    path,sha=write_json(tmp_path/'commit-receipt.json',decision['receipt'],True)
    with sessions() as db:
        def failed_commit():raise RuntimeError('isolated database commit fault')
        monkeypatch.setattr(db,'commit',failed_commit)
        with pytest.raises(RuntimeError,match='commit fault'):
            source_ingest(SourceIngestRequest(receipt_path=path,receipt_sha256=sha),db,Actor('operator','operator'))
    with sessions() as db:
        assert db.query(ObservationStandard).count()==0
        assert db.query(ObservationRaw).count()==0
        assert db.query(SourceObservationBinding).count()==0
