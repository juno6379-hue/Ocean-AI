"""Synthetic authority fixtures never create approval on the live database."""
import copy
import hashlib
import json
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.security import Actor
from app.core.config import settings
from app.models.domain import ApprovalHistory
from app.models.source_contracts import SourceContractPacket, SourceContractDecision
from app.services import source_contract_authority as authority
from app.api import routes_source_contracts as routes
from app.services.source_contract_review import exact_scope_key


def descriptor(root, path, role):
    data = (root/path).read_bytes()
    return {'role':role, 'path':path, 'sha256':hashlib.sha256(data).hexdigest(), 'bytes':len(data)}


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(authority, 'SOURCE_ROOT', tmp_path)
    (tmp_path/'original.csv').write_text('synthetic original', encoding='utf8')
    (tmp_path/'codebook.json').write_text('{"synthetic":true}', encoding='utf8')
    rows = [{'OBS_POST_ID':'DT_TEST', 'OBS_ITEM_CODE':'TEMP', 'OBS_TIME':'2024-01-01 00:00:00',
        'OBS_VALUE':'12.5', 'QC_FLAG':'OK', 'MQC_FLAG':'G ', 'N1_AQC_FLAG':None}]
    pq.write_table(pa.Table.from_pylist(rows), tmp_path/'raw.parquet')
    files = [descriptor(tmp_path, 'original.csv', 'RAW'), descriptor(tmp_path, 'raw.parquet', 'PARQUET'), descriptor(tmp_path, 'codebook.json', 'QC_CODEBOOK')]
    manifest = {'source_sha256':files[0]['sha256'], 'source_size':files[0]['bytes'], 'source_path':str(tmp_path/'original.csv'),
        'source_system':'GD_TEST', 'raw_sha256':files[1]['sha256'], 'raw_path':str(tmp_path/'raw.parquet')}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest), encoding='utf8')
    files.append(descriptor(tmp_path, 'manifest.json', 'SOURCE_MANIFEST'))
    scope = {'source_group':'GD_TEST', 'station_code':'DT_TEST', 'item_code':'TEMP', 'depth_step':None,
        'depth_from':None, 'depth_to':None, 'month':'2024-01'}
    proof = {key:'fixture' for key in authority.REQUIRED_STRINGS}
    proof.update(source_group='GD_TEST', source_station_code='DT_TEST', source_item_code='TEMP',
        source_station_literal='DT_TEST', source_item_literal='TEMP', source_identifier_transform={'station':'IDENTITY','item':'IDENTITY'},
        source_month='2024-01', source_row_locator='parquet_row_group=0;row_index=0',
        source_time_raw='2024-01-01 00:00:00', source_value_raw='12.5', value='12.5',
        source_qc_raw='OK', source_mqc_raw='G ', source_n1_aqc_raw=None,
        source_receive_time_raw=None,source_receive_timestamp_utc=None,source_receive_clock_policy='ABSENT_IN_SOURCE',
        timestamp_utc='2024-01-01T00:00:00+00:00', timezone='UTC', source_clock_semantics='OBSERVED_AT',
        quantity_kind='SCALAR', observation_role='OBSERVED', source_unit='degC', unit='degC', standard_variable='TEMPERATURE',
        quantity_transform={'scale':'1','offset':'0','datum':{'kind':'NOT_APPLICABLE'}},
        depth={'step':None,'from':None,'to':None}, exact_scope_key=exact_scope_key(scope),
        effective_start='2023-01-01T00:00:00+00:00', effective_end='2025-01-01T00:00:00+00:00',
        qc_effective_start='2023-01-01T00:00:00+00:00', qc_effective_end='2025-01-01T00:00:00+00:00',
        available_at='2024-01-01T00:01:00+00:00', qc_available_at='2024-01-01T00:02:00+00:00',
        training_value_status='ACCEPTED', validation_errors=[],
        source_sha256=files[0]['sha256'], parquet_sha256=files[1]['sha256'], source_qc_codebook_sha256=files[2]['sha256'], source_manifest_sha256=files[3]['sha256'])
    proof['field_evidence'] = {field:[{'file_sha256':files[2]['sha256'], 'locator':'synthetic.fixture.'+field, 'claim':'Synthetic fixture only'}] for field in authority.REQUIRED_EVIDENCE}
    packet = {'schema_version':authority.SCHEMA,'contract_id':'test-contract-1', 'source_availability_policy':'RAW_AND_TRANSFORM_REQUIRED',
        'source_row_reuse_policy':{'policy':'FORBIDDEN'},
        'files':files, 'scope':[scope], 'observations':{'OBS-1':proof}, 'validation_errors':[], 'agent_review':{'approved':False,'status':'TECHNICALLY_REVIEWED'}}
    engine = create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    for table in (ApprovalHistory.__table__, SourceContractPacket.__table__, SourceContractDecision.__table__):
        table.create(engine)
    with Session(engine) as db:
        yield tmp_path, packet, db


def approve(packet, db):
    requested = authority.request_contract(db, packet, Actor('real-synthetic-operator', 'operator'))
    return authority.decide_contract(db, packet['contract_id'], requested['packet_sha256'], 'APPROVED', Actor('real-synthetic-reviewer', 'reviewer'))


def test_authenticated_approval_binds_packet_receipt_actor_and_raw_row(case):
    root, packet, db = case
    assert authority.packet_errors(packet, verify_sources=True) == []
    result = approve(packet, db)
    db.commit()
    proof = authority.verify_approved_receipt(db, result['receipt'], result['receipt_sha256'])
    assert proof['reviewer_id'] == 'real-synthetic-reviewer'
    assert proof['packet_sha256'] == authority.receipt_sha256(packet)
    assert result['receipt']['observations']['OBS-1']['source_mqc_raw'] == 'G '
    assert db.query(ApprovalHistory).count() == 2


@pytest.mark.parametrize('change,expected', [
    (lambda p:p['observations']['OBS-1'].update(timezone=None), 'MISSING_TIMEZONE'),
    (lambda p:p['observations']['OBS-1'].update(source_mqc_raw='G'), 'SOURCE_LITERAL_MISMATCH'),
    (lambda p:p['observations']['OBS-1'].update(source_station_literal='WRONG'), 'SOURCE_LITERAL_MISMATCH'),
    (lambda p:p['observations']['OBS-1'].update(value='125'), 'SOURCE_QUANTITY_CONVERSION_MISMATCH'),
    (lambda p:p['observations']['OBS-1'].update(timestamp_utc='2024-01-01T00:00:00'), 'OBSERVATION_CLOCK_TRANSFORM_INCOMPLETE'),
    (lambda p:p['observations']['OBS-1'].update(qc_effective_end='2024-01-01T00:00:00+00:00'), 'SOURCE_OR_QC_PERIOD_MISMATCH'),
    (lambda p:p['observations']['OBS-1'].update(quantity_kind='VECTOR_UV'), 'CURRENT_SOURCE_TYPED_BINDING_MISSING'),
    (lambda p:p['observations']['OBS-1']['field_evidence'].pop('source_unit'), 'FIELD_EVIDENCE_MISSING_SOURCE_UNIT'),
])
def test_missing_or_altered_source_cannot_approve(case, change, expected):
    root, packet, db = case
    change(packet)
    requested = authority.request_contract(db, packet, Actor('operator', 'operator'))
    assert requested['status'] == 'PENDING'
    with pytest.raises(authority.SourceContractError, match=expected):
        authority.decide_contract(db, packet['contract_id'], requested['packet_sha256'], 'APPROVED', Actor('reviewer', 'reviewer'))
    assert db.query(SourceContractDecision).count() == 0


def test_caller_identity_and_approval_fields_forbidden(case):
    root, packet, db = case
    packet['approved_by'] = 'fake-human'
    with pytest.raises(authority.SourceContractError, match='CALLER_APPROVAL_FIELDS_FORBIDDEN'):
        authority.request_contract(db, packet, Actor('operator', 'operator'))
    packet.pop('approved_by')
    with pytest.raises(authority.SourceContractError, match='AUTHENTICATED_REVIEWER_REQUIRED'):
        authority.decide_contract(db, 'x', 'a'*64, 'APPROVED', Actor('viewer', 'viewer'))


def test_latest_revocation_invalidates_frozen_receipt(case):
    root, packet, db = case
    result = approve(packet, db)
    authority.decide_contract(db, packet['contract_id'], authority.receipt_sha256(packet), 'REVOKED', Actor('second-reviewer', 'reviewer'), 'Wrong adoption interval')
    db.commit()
    with pytest.raises(authority.SourceContractError, match='SOURCE_APPROVAL_NOT_CURRENT'):
        authority.verify_approved_receipt(db, result['receipt'], result['receipt_sha256'])


def test_rehashed_receipt_cannot_reuse_actual_ledger(case):
    root, packet, db = case
    result = approve(packet, db)
    changed = copy.deepcopy(result['receipt'])
    changed['observations']['OBS-1']['unit'] = 'WRONG'
    with pytest.raises(authority.SourceContractError, match='SOURCE_APPROVAL_LEDGER_HASH_MISMATCH'):
        authority.verify_approved_receipt(db, changed, authority.receipt_sha256(changed))


def test_changed_source_bytes_invalidate_approval_consumer(case):
    root, packet, db = case
    result = approve(packet, db)
    (root/'codebook.json').write_text('tampered', encoding='utf8')
    with pytest.raises(authority.SourceContractError, match='SOURCE_APPROVED_PACKET_CHANGED_OR_INCOMPLETE'):
        authority.verify_approved_receipt(db, result['receipt'], result['receipt_sha256'])


def test_deleted_original_requires_explicit_policy_and_exact_manifest(case):
    root, packet, db = case
    source = packet['files'][0]
    source.update(path=None, availability='ORIGINAL_DELETED', original_path=str(root/'original.csv'))
    (root/'original.csv').unlink()
    assert any('RAW_DELETION_POLICY_NOT_EXPLICIT' in x for x in authority.packet_errors(packet, verify_sources=True))
    packet['source_availability_policy'] = 'APPROVED_TRANSFORM_ONLY'
    assert authority.packet_errors(packet, verify_sources=True) == []
    assert approve(packet, db)['status'] == 'APPROVED'


def test_failed_transaction_has_no_approval_or_receipt_or_files(case):
    root, packet, db = case
    before = sorted(str(p) for p in root.iterdir())
    result = approve(packet, db)
    db.rollback()
    assert db.query(SourceContractDecision).count() == 0
    assert db.query(SourceContractPacket).count() == 0
    assert db.query(ApprovalHistory).count() == 0
    assert sorted(str(p) for p in root.iterdir()) == before
    with pytest.raises(authority.SourceContractError, match='SOURCE_APPROVAL_LEDGER_MISSING'):
        authority.verify_approved_receipt(db, result['receipt'], result['receipt_sha256'])


def test_packet_actor_and_history_tamper_fail_closed(case):
    root, packet, db = case
    result = approve(packet, db)
    history = db.get(ApprovalHistory, result['receipt']['approval_receipt']['approval_history_id'])
    history.approved_by = 'forged-other-reviewer'
    db.flush()
    with pytest.raises(authority.SourceContractError, match='SOURCE_APPROVAL_ACTOR_MISMATCH'):
        authority.verify_approved_receipt(db, result['receipt'], result['receipt_sha256'])


def test_api_never_accepts_caller_user_id_or_unauthenticated_review(case, monkeypatch):
    root, packet, db = case
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda:db
    monkeypatch.setattr(settings, 'API_IDENTITIES', {'reviewer':{'token':'synthetic-token','role':'reviewer'}, 'viewer':{'token':'viewer-token','role':'viewer'}})
    with TestClient(app) as client:
        assert client.post('/api/source-contracts/request', json={'packet':packet}).status_code == 401
        assert client.post('/api/source-contracts/request', json={'packet':packet,'user_id':'fake'}, headers={'Authorization':'Bearer synthetic-token'}).status_code == 422
        assert client.post('/api/source-contracts/request', json={'packet':packet}, headers={'Authorization':'Bearer viewer-token'}).status_code == 403


def test_duplicate_scope_and_nonfinite_or_traversal_rejected(case):
    root, packet, db = case
    packet['scope'].append(copy.deepcopy(packet['scope'][0]))
    assert 'EXACT_SOURCE_SCOPE_DUPLICATE' in authority.packet_errors(packet)
    packet['scope'].pop()
    packet['files'][2]['path'] = '../outside.json'
    assert 'SOURCE_PATH_OUTSIDE_ROOT' in authority.packet_errors(packet)
    packet['files'][2]['path'] = 'codebook.json'
    packet['observations']['OBS-1']['value'] = float('nan')
    assert authority.packet_errors(packet) == ['SOURCE_CONTRACT_JSON_INVALID']


def test_sqlplus_original_padding_and_alias_are_preserved(case):
    root, packet, db = case
    proof = packet['observations']['OBS-1']
    source_sha = proof['source_sha256']
    rows = [{'station_raw':'DT_TEST   ', 'item_raw':'TEMP    ', 'time_raw':'2024-01-01 00:00:00',
        'value_raw':'    12.5', 'qc_raw':'OK', 'mq_raw':'G ', 'n1_aqc_raw':None,
        'record_class':'OBSERVATION_SHAPED_UNVALIDATED'}]
    table = pa.Table.from_pylist(rows).replace_schema_metadata({b'source_sha256':source_sha.encode()})
    pq.write_table(table, root/'raw.parquet')
    packet['files'][1] = descriptor(root, 'raw.parquet', 'PARQUET')
    packet['files'][0].update(availability='PRESERVED_ALIAS', original_path='C:\\old-source\\original.csv')
    (root/'manifest.json').write_text(json.dumps({'path':'C:\\old-source\\original.csv',
        'source_sha256':source_sha, 'source_size':packet['files'][0]['bytes'], 'status':'RAW_PARSED_RECONCILED',
        'files':[{'path':'raw.parquet', 'sha256':packet['files'][1]['sha256']}]}), encoding='utf8')
    packet['files'][3] = descriptor(root, 'manifest.json', 'SOURCE_MANIFEST')
    # A canonical relative base directory is required; use a real child for it.
    (root/'parts').mkdir()
    (root/'raw.parquet').rename(root/'parts'/'raw.parquet')
    packet['files'][1]['path'] = 'parts/raw.parquet'
    packet['files'][3].update(format='MONTHLY_SQLPLUS_RAW_V1', parquet_root='parts')
    proof.update(parquet_sha256=packet['files'][1]['sha256'], source_manifest_sha256=packet['files'][3]['sha256'],
        source_station_literal='DT_TEST   ', source_item_literal='TEMP    ', source_value_raw='    12.5',
        source_identifier_transform={'station':'STRIP_SQLPLUS_PADDING','item':'STRIP_SQLPLUS_PADDING'})
    assert authority.packet_errors(packet, verify_sources=True) == []
    proof['source_station_literal'] = 'DT_TEST'
    assert any('SOURCE_LITERAL_MISMATCH' in e for e in authority.packet_errors(packet, verify_sources=True))


def typed_packet(root, packet, kind):
    proof = packet['observations']['OBS-1']
    metadata = {'CIRCULAR_DEGREES':{'magnitude_unit':'m/s'},
        'SIGNED_RADIAL':{'coordinate_frame':'SITE_RADIAL','site_geometry_version':'synthetic-1','coverage_fraction':1,'qc_eligible':True},
        'VECTOR_UV':{'coordinate_frame':'EAST_NORTH','grid_cell_id':'synthetic-cell','geometry_version':'synthetic-1'},
        'PROFILE_BINS':{'coordinate_frame':'DEPTH_BELOW_SURFACE','layout_version':'synthetic-1','target_variable':proof['standard_variable'],'unit':proof['unit'],'value_representation':'SCALAR'},
        'TRAJECTORY':{'coordinate_frame':'WGS84','trajectory_id':'synthetic-1'}}[kind]
    binding = {'file_sha256':proof['parquet_sha256'],'row_group':0,'row_index':0,'column':'OBS_VALUE',
        'source_sha256':proof['source_sha256'],'source_manifest_sha256':proof['source_manifest_sha256'],
        'source_group':proof['source_group'],'source_station_code':proof['source_station_code'],
        'source_item_code':proof['source_item_code'],'source_time_raw':proof['source_time_raw'],
        'source_station_literal':proof['source_station_literal'],'source_item_literal':proof['source_item_literal'],
        'source_identifier_transform':proof['source_identifier_transform'],
        'depth':proof['depth'],'exact_scope_key':proof['exact_scope_key'],'scale':'1','offset':'0',
        'source_unit':'fixture-unit','unit':proof['unit']}
    # This fixture uses the same actual row/origin. Production must supply each
    # component's own evidence; the authority never copies overall facts.
    binding.update({field:copy.deepcopy(proof[field]) for field in ('physical_sensor_id','sensor_episode_id',
        'event_id','timezone','source_clock_semantics','qc_rule_version','effective_start','effective_end',
        'qc_effective_start','qc_effective_end','available_at','qc_available_at','timestamp_utc',
        'source_qc_codebook_sha256','source_qc_raw','source_mqc_raw','source_n1_aqc_raw')})
    binding.update(source_receive_time_raw=None,source_receive_timestamp_utc=None,
        source_receive_clock_policy='ABSENT_IN_SOURCE',training_value_status='ACCEPTED',source_qc_interpretation='ACCEPTED',
        source_sensor_column='PHYSICAL_SENSOR_ID',source_episode_column='SENSOR_EPISODE_ID')
    binding['field_evidence']={field:copy.deepcopy(proof['field_evidence']['physical_sensor_id'])
        for field in (*authority.COMPONENT_REQUIRED_EVIDENCE,'source_sensor_column','source_episode_column')}
    fields, payload = {}, {'representation':kind,**metadata}
    rows = pq.read_table(root/'raw.parquet').to_pylist()
    rows[0]['PHYSICAL_SENSOR_ID']=proof['physical_sensor_id']
    rows[0]['SENSOR_EPISODE_ID']=proof['sensor_episode_id']
    for field in authority.TYPED_FIELDS[kind]:
        rows[0]['TYPED_'+field.upper()] = 'TEMP' if field == 'bin_ids' else '12.5'
    pq.write_table(pa.Table.from_pylist(rows),root/'raw.parquet')
    packet['files'][1] = descriptor(root,'raw.parquet','PARQUET')
    proof['parquet_sha256'] = packet['files'][1]['sha256']
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf8'))
    manifest['raw_sha256'] = proof['parquet_sha256']
    (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    packet['files'][3] = descriptor(root,'manifest.json','SOURCE_MANIFEST')
    proof['source_manifest_sha256'] = packet['files'][3]['sha256']
    for field in authority.TYPED_FIELDS[kind]:
        entry = copy.deepcopy(binding)
        entry.update(file_sha256=proof['parquet_sha256'],source_manifest_sha256=proof['source_manifest_sha256'],column='TYPED_'+field.upper())
        if field == 'bin_ids':
            fields[field], payload[field] = [entry], ['TEMP']
        elif kind == 'PROFILE_BINS':
            entry['unit'] = 'm' if field == 'depths' else proof['unit']
            fields[field], payload[field] = [entry], [12.5]
        else:
            entry['unit'] = 'degree' if kind in {'CIRCULAR_DEGREES','TRAJECTORY'} and field in {'value','longitude','latitude'} else metadata.get('magnitude_unit') if field == 'magnitude' else proof['unit']
            fields[field], payload[field] = entry, 12.5
    proof.update(quantity_kind=kind, typed_payload=payload,
        typed_payload_bindings={'representation':kind, 'fields':fields, 'constant_metadata':metadata})
    proof['field_evidence']['typed_payload'] = copy.deepcopy(proof['field_evidence']['quantity_kind'])
    return proof


@pytest.mark.parametrize('kind', list(authority.TYPED_FIELDS))
def test_typed_payload_reads_explicit_actual_components_without_synthesis(case, kind):
    root, packet, db = case
    proof = typed_packet(root, packet, kind)
    assert authority.packet_errors(packet, verify_sources=True) == []
    field = 'values' if kind == 'PROFILE_BINS' else next(iter(authority.TYPED_FIELDS[kind]))
    proof['typed_payload'][field] = [99] if kind == 'PROFILE_BINS' else 99
    assert any('SOURCE_TYPED_COMPONENT_VALUE_MISMATCH' in e for e in authority.packet_errors(packet, verify_sources=True))


def test_typed_component_pairing_clock_and_unit_must_match_source(case):
    root, packet, db = case
    proof = typed_packet(root, packet, 'VECTOR_UV')
    proof['typed_payload_bindings']['fields']['v']['source_station_code'] = 'OTHER'
    assert any('SOURCE_TYPED_BINDING_SCOPE_MISMATCH' in e for e in authority.packet_errors(packet, verify_sources=True))
    proof['typed_payload_bindings']['fields']['v']['source_station_code'] = proof['source_station_code']
    proof['typed_payload_bindings']['fields']['v']['source_time_raw'] = '2024-01-01 00:01:00'
    assert any('SOURCE_TYPED_COMPONENT_IDENTITY_MISMATCH' in e for e in authority.packet_errors(packet, verify_sources=True))
    proof['typed_payload_bindings']['fields']['v']['source_time_raw'] = proof['source_time_raw']
    proof['typed_payload_bindings']['fields']['v']['unit'] = 'wrong-unit'
    assert any('SOURCE_TYPED_COMPONENT_UNIT_UNBOUND' in e for e in authority.packet_errors(packet, verify_sources=True))


@pytest.mark.parametrize('field,value', [('source_station_literal','DT_TEST '),
    ('source_manifest_sha256','0'*64), ('source_sha256','0'*64), ('file_sha256',[])])
def test_typed_components_cannot_bypass_literal_or_own_manifest_binding(case, field, value):
    root, packet, db = case
    proof = typed_packet(root,packet,'VECTOR_UV')
    proof['typed_payload_bindings']['fields']['v'][field] = value
    assert authority.packet_errors(packet,verify_sources=True)


def test_typed_representation_and_radial_qc_eligibility_are_explicit(case):
    root, packet, db = case
    proof = typed_packet(root,packet,'SIGNED_RADIAL')
    proof['typed_payload']['representation'] = 'SCALAR'
    assert any('SOURCE_TYPED_BINDING_FIELDS_INVALID' in x for x in authority.packet_errors(packet,verify_sources=True))
    proof['typed_payload']['representation'] = 'SIGNED_RADIAL'
    proof['typed_payload']['qc_eligible'] = False
    proof['typed_payload_bindings']['constant_metadata']['qc_eligible'] = False
    assert any('SOURCE_RADIAL_COVERAGE_INVALID' in x for x in authority.packet_errors(packet,verify_sources=True))


@pytest.mark.parametrize('datum,code', [({'kind':'SOURCE_DATUM'},'SOURCE_DATUM_IDENTIFIER_MISSING'),
    ({'kind':'CONVERSION','source_identifier':'A'},'DATUM_CONVERSION_REFERENCE_MISSING')])
def test_datum_name_and_version_cannot_be_omitted_from_reviewed_transform(case, datum, code):
    root, packet, db = case
    packet['observations']['OBS-1']['quantity_transform']['datum'] = datum
    assert any(code in x for x in authority.packet_errors(packet,verify_sources=True))


@pytest.mark.parametrize('change', [
    lambda p:p.update(agent_review=None), lambda p:p.update(agent_review=[]),
    lambda p:p.update(source_availability_policy=[]),
    lambda p:p['observations']['OBS-1'].update(field_evidence=None),
    lambda p:p['observations']['OBS-1']['field_evidence'].update(source_unit=[{'file_sha256':[], 'locator':'x','claim':'unproved'}]),
    lambda p:p['observations']['OBS-1'].update(quantity_transform=[]),
    lambda p:p['observations']['OBS-1'].update(quantity_transform={'scale':{},'offset':'0','datum':None}),
    lambda p:p['observations']['OBS-1'].update(quantity_kind=[]),
    lambda p:p['observations']['OBS-1'].update(source_identifier_transform={'station':[],'item':'IDENTITY'}),
    lambda p:p['observations']['OBS-1'].update(quantity_kind='VECTOR_UV',typed_payload={},typed_payload_bindings={'representation':'VECTOR_UV','fields':[]}),
    lambda p:p['observations']['OBS-1'].update(standard_variable=None),
    lambda p:p.update(source_row_reuse_policy={'policy':[]}),
    lambda p:p.update(observations=[{}]),
])
def test_malformed_nested_packet_blocks_structurally_without_500(case, change, monkeypatch):
    root, packet, db = case
    change(packet)
    assert authority.packet_errors(packet,verify_sources=True)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda:db
    monkeypatch.setattr(settings,'API_IDENTITIES',{'reviewer':{'token':'synthetic-token','role':'reviewer'}})
    headers = {'Authorization':'Bearer synthetic-token'}
    with TestClient(app) as client:
        response = client.post('/api/source-contracts/request',json={'packet':packet},headers=headers)
        assert response.status_code == 200
        assert response.json()['status'] == 'PENDING'
        decision = client.post('/api/source-contracts/test-contract-1/decision',json={
            'expected_packet_sha256':response.json()['packet_sha256'],'decision':'APPROVED'},headers=headers)
        assert decision.status_code == 409
        assert decision.json()['detail']['code'] == 'SOURCE_CONTRACT_APPROVAL_BLOCKED'
        assert db.query(SourceContractDecision).count() == 0


def test_authenticated_api_returns_exact_receipt_bytes_and_receipt_hash(case, monkeypatch):
    root, packet, db = case
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_db] = lambda:db
    monkeypatch.setattr(settings,'API_IDENTITIES',{'reviewer':{'token':'synthetic-token','role':'reviewer'}})
    headers = {'Authorization':'Bearer synthetic-token'}
    with TestClient(app) as client:
        request = client.post('/api/source-contracts/request',json={'packet':packet},headers=headers).json()
        approve = client.post('/api/source-contracts/test-contract-1/decision',json={
            'expected_packet_sha256':request['packet_sha256'],'decision':'APPROVED'},headers=headers)
        assert approve.status_code == 200
        exported = client.get('/api/source-contracts/test-contract-1/receipt')
        assert exported.status_code == 200
        assert hashlib.sha256(exported.content).hexdigest() == exported.headers['X-Content-SHA256']
        assert exported.content == authority.canonical_bytes(exported.json())
        assert exported.json()['approved_by'] == 'reviewer'


def test_source_components_cannot_duplicate_axes_or_observations_without_review(case):
    root, packet, db = case
    proof = typed_packet(root,packet,'VECTOR_UV')
    proof['typed_payload_bindings']['fields']['v']['column'] = 'TYPED_U'
    assert any('SOURCE_CELL_BOUND_TO_MULTIPLE_TYPED_FIELDS' in x for x in authority.packet_errors(packet,verify_sources=True))
    proof['typed_payload_bindings']['fields']['v']['column'] = 'TYPED_V'
    packet['observations']['OBS-2'] = copy.deepcopy(proof)
    assert 'SOURCE_COMPONENT_REUSE_NOT_REVIEWED' in authority.packet_errors(packet,verify_sources=True)


def test_shared_component_policy_is_exact_and_evidence_bound(case):
    root, packet, db = case
    proof = packet['observations']['OBS-1']
    packet['observations']['OBS-2'] = copy.deepcopy(proof)
    packet['source_row_reuse_policy'] = {'policy':'EXPLICIT_COMPONENT_SHARING','reviewed_shared_components':[
        {'file_sha256':proof['parquet_sha256'],'row_group':0,'row_index':0,'column':'OBS_VALUE',
            'observation_ids':['OBS-1','OBS-2'],'reason':'Synthetic explicit reviewed sharing',
            'evidence':copy.deepcopy(proof['field_evidence']['quantity_kind'])}]}
    assert authority.packet_errors(packet,verify_sources=True) == []
    packet['source_row_reuse_policy']['reviewed_shared_components'][0]['observation_ids'].append('OTHER')
    assert 'SOURCE_COMPONENT_REUSE_NOT_REVIEWED' in authority.packet_errors(packet,verify_sources=True)


@pytest.mark.parametrize('kind',['SCALAR','VECTOR_UV'])
def test_fr_depth_uses_explicit_column_map_and_rejects_alias_conflicts(case,kind):
    root,packet,db=case
    proof=packet['observations']['OBS-1']
    packet['scope'][0]['depth_from']=2.0
    proof['depth']['from']=2.0
    proof['exact_scope_key']=exact_scope_key(packet['scope'][0])
    proof['source_column_map']={'depth_from':'FR_DEPTH'}
    proof['field_evidence']['source_column_map']=copy.deepcopy(proof['field_evidence']['source_item_code'])
    rows=pq.read_table(root/'raw.parquet').to_pylist()
    rows[0]['FR_DEPTH']=2.0
    pq.write_table(pa.Table.from_pylist(rows),root/'raw.parquet')
    packet['files'][1]=descriptor(root,'raw.parquet','PARQUET')
    proof['parquet_sha256']=packet['files'][1]['sha256']
    manifest=json.loads((root/'manifest.json').read_text())
    manifest['raw_sha256']=proof['parquet_sha256']
    (root/'manifest.json').write_text(json.dumps(manifest))
    packet['files'][3]=descriptor(root,'manifest.json','SOURCE_MANIFEST')
    proof['source_manifest_sha256']=packet['files'][3]['sha256']
    if kind!='SCALAR':
        typed_packet(root,packet,kind)
        for binding in proof['typed_payload_bindings']['fields'].values():
            binding['source_column_map']={'depth_from':'FR_DEPTH'}
            binding['field_evidence']['source_column_map']=copy.deepcopy(proof['field_evidence']['source_column_map'])
    assert authority.packet_errors(packet,verify_sources=True)==[]
    proof.pop('source_column_map')
    assert any('SOURCE_DEPTH_COLUMN_MAP_REQUIRED' in e for e in authority.packet_errors(packet,verify_sources=True))
    proof['source_column_map']={'depth_from':'FR_DEPTH'}
    if kind!='SCALAR':
        proof['typed_payload_bindings']['fields']['v'].pop('source_column_map')
        assert any('SOURCE_DEPTH_COLUMN_MAP_REQUIRED' in e for e in authority.packet_errors(packet,verify_sources=True))
        proof['typed_payload_bindings']['fields']['v']['source_column_map']={'depth_from':'FR_DEPTH'}
    assert authority._depth_from({'FR_DEPTH':2.0,'FROM_DEPTH':2.0},proof)==2.0
    with pytest.raises(authority.SourceContractError,match='SOURCE_DEPTH_COLUMN_ALIAS_CONFLICT'):
        authority._depth_from({'FR_DEPTH':2.0,'FROM_DEPTH':3.0},proof)
    with pytest.raises(authority.SourceContractError,match='SOURCE_DEPTH_COLUMN_ALIAS_CONFLICT'):
        authority._depth_from({'FR_DEPTH':2.0,'FROM_DEPTH':2},proof)
    rows=pq.read_table(root/'raw.parquet').to_pylist()
    rows[0]['FROM_DEPTH']=3.0
    pq.write_table(pa.Table.from_pylist(rows),root/'raw.parquet')
    packet['files'][1]=descriptor(root,'raw.parquet','PARQUET')
    proof['parquet_sha256']=packet['files'][1]['sha256']
    manifest=json.loads((root/'manifest.json').read_text())
    manifest['raw_sha256']=proof['parquet_sha256']
    (root/'manifest.json').write_text(json.dumps(manifest))
    packet['files'][3]=descriptor(root,'manifest.json','SOURCE_MANIFEST')
    proof['source_manifest_sha256']=packet['files'][3]['sha256']
    if kind!='SCALAR':
        for binding in proof['typed_payload_bindings']['fields'].values():
            binding.update(file_sha256=proof['parquet_sha256'],source_manifest_sha256=proof['source_manifest_sha256'])
    assert any('SOURCE_DEPTH_COLUMN_ALIAS_CONFLICT' in e for e in authority.packet_errors(packet,verify_sources=True))


@pytest.mark.parametrize('raw,zone,expected', [
    ('2024-01-01 00:00:00','UTC','2024-01-01T00:00:00+00:00'),
    ('2024-01-01 09:00:00','Asia/Seoul','2024-01-01T00:00:00+00:00'),
    ('2024-01-01 00:00:00','America/New_York','2024-01-01T05:00:00+00:00')])
def test_unambiguous_source_clock_roundtrips_exactly(raw,zone,expected):
    assert authority._local_clock(raw,zone)==authority._clock(expected)


@pytest.mark.parametrize('raw,code', [
    ('2024-11-03 01:30:00','SOURCE_CLOCK_AMBIGUOUS'),
    ('2024-03-10 02:30:00','SOURCE_CLOCK_NONEXISTENT')])
def test_source_clock_never_defaults_dst_fold_or_nonexistent_time(raw,code):
    with pytest.raises(authority.SourceContractError,match=code):
        authority._local_clock(raw,'America/New_York')


@pytest.mark.parametrize('field,value,code',[
    ('available_at','2024-01-01T00:03:00+00:00','SOURCE_TYPED_COMPONENT_AVAILABILITY_MISMATCH'),
    ('qc_available_at','2024-01-01T00:03:00+00:00','SOURCE_TYPED_COMPONENT_AVAILABILITY_MISMATCH'),
    ('physical_sensor_id','OTHER','SOURCE_TYPED_COMPONENT_SENSOR_EPISODE_CLOCK_MISMATCH'),
    ('sensor_episode_id','OTHER','SOURCE_TYPED_COMPONENT_SENSOR_EPISODE_CLOCK_MISMATCH'),
    ('effective_end','2024-01-01T00:00:00+00:00','SOURCE_TYPED_COMPONENT_PERIOD_MISMATCH'),
    ('qc_effective_end','2024-01-01T00:00:00+00:00','SOURCE_TYPED_COMPONENT_PERIOD_MISMATCH'),
    ('source_qc_interpretation','UNKNOWN','SOURCE_TYPED_COMPONENT_QC_UNRESOLVED'),
    ('source_qc_raw','BAD','SOURCE_TYPED_COMPONENT_QC_RECEIVE_LITERAL_MISMATCH'),
    ('source_mqc_raw','G','SOURCE_TYPED_COMPONENT_QC_RECEIVE_LITERAL_MISMATCH'),
    ('source_qc_codebook_sha256','0'*64,'SOURCE_TYPED_COMPONENT_CODEBOOK_UNBOUND'),
    ('field_evidence',[],'SOURCE_TYPED_COMPONENT_EVIDENCE_MISSING'),
])
def test_overall_origin_cannot_supply_missing_or_conflicting_component_review(case,field,value,code):
    root,packet,db=case
    proof=typed_packet(root,packet,'VECTOR_UV')
    proof['typed_payload_bindings']['fields']['v'][field]=value
    assert any(code in e for e in authority.packet_errors(packet,verify_sources=True))


def refresh_typed_source_files(root,packet,proof):
    packet['files'][1]=descriptor(root,'raw.parquet','PARQUET')
    proof['parquet_sha256']=packet['files'][1]['sha256']
    manifest=json.loads((root/'manifest.json').read_text())
    manifest['raw_sha256']=proof['parquet_sha256']
    (root/'manifest.json').write_text(json.dumps(manifest))
    packet['files'][3]=descriptor(root,'manifest.json','SOURCE_MANIFEST')
    proof['source_manifest_sha256']=packet['files'][3]['sha256']
    for entry in proof.get('typed_payload_bindings',{}).get('fields',{}).values():
        for binding in entry if isinstance(entry,list) else [entry]:
            binding.update(file_sha256=proof['parquet_sha256'],source_manifest_sha256=proof['source_manifest_sha256'])


def test_auxiliary_later_receipt_requires_own_clock_and_aggregate_availability(case):
    root,packet,db=case
    proof=typed_packet(root,packet,'VECTOR_UV')
    rows=pq.read_table(root/'raw.parquet').to_pylist()
    rows[0]['RECEIVE_TIME']=None
    rows.append({**rows[0],'RECEIVE_TIME':'2024-01-01 00:05:00'})
    pq.write_table(pa.Table.from_pylist(rows),root/'raw.parquet')
    refresh_typed_source_files(root,packet,proof)
    bound=proof['typed_payload_bindings']['fields']['v']
    bound.update(row_index=1,source_receive_time_raw='2024-01-01 00:05:00',
        source_receive_clock_policy='LOCAL_OBSERVED_TIMEZONE',source_receive_timestamp_utc='2024-01-01T00:05:00+00:00')
    assert any('SOURCE_TYPED_COMPONENT_AVAILABLE_BEFORE_RECEIVED' in e for e in authority.packet_errors(packet,verify_sources=True))
    bound.update(available_at='2024-01-01T00:06:00+00:00',qc_available_at='2024-01-01T00:07:00+00:00')
    assert any('SOURCE_TYPED_COMPONENT_AVAILABILITY_MISMATCH' in e for e in authority.packet_errors(packet,verify_sources=True))
    proof.update(available_at=bound['available_at'],qc_available_at=bound['qc_available_at'])
    assert authority.packet_errors(packet,verify_sources=True)==[]
    bound['source_receive_time_raw']=None
    bound['source_receive_timestamp_utc']=None
    bound['source_receive_clock_policy']='ABSENT_IN_SOURCE'
    assert any('SOURCE_TYPED_COMPONENT_QC_RECEIVE_LITERAL_MISMATCH' in e for e in authority.packet_errors(packet,verify_sources=True))


def test_auxiliary_raw_sensor_or_episode_cannot_be_replaced_by_overall_claim(case):
    root,packet,db=case
    proof=typed_packet(root,packet,'VECTOR_UV')
    rows=pq.read_table(root/'raw.parquet').to_pylist()
    rows.append({**rows[0],'PHYSICAL_SENSOR_ID':'OTHER-SENSOR'})
    pq.write_table(pa.Table.from_pylist(rows),root/'raw.parquet')
    refresh_typed_source_files(root,packet,proof)
    proof['typed_payload_bindings']['fields']['v']['row_index']=1
    assert any('SOURCE_TYPED_COMPONENT_RAW_SENSOR_EPISODE_MISMATCH' in e for e in authority.packet_errors(packet,verify_sources=True))


def test_vector_cannot_pair_different_actual_depth_bins(case):
    root,packet,db=case
    proof=typed_packet(root,packet,'VECTOR_UV')
    rows=pq.read_table(root/'raw.parquet').to_pylist()
    rows[0]['FROM_DEPTH']=None
    rows.append({**rows[0],'FROM_DEPTH':2.0})
    pq.write_table(pa.Table.from_pylist(rows),root/'raw.parquet')
    other={**packet['scope'][0],'depth_from':2.0}
    packet['scope'].append(other)
    bound=proof['typed_payload_bindings']['fields']['v']
    bound.update(row_index=1,depth={'step':None,'from':2.0,'to':None},exact_scope_key=exact_scope_key(other))
    refresh_typed_source_files(root,packet,proof)
    assert any('SOURCE_TYPED_COMPONENT_DEPTH_PAIRING_MISMATCH' in e for e in authority.packet_errors(packet,verify_sources=True))
    assert not authority._same_depth({'step':None,'from':2,'to':None},{'step':None,'from':2.0,'to':None})


def test_profile_distinct_bins_are_explicitly_aligned_without_sorting(case):
    root,packet,db=case
    proof=typed_packet(root,packet,'PROFILE_BINS')
    rows=pq.read_table(root/'raw.parquet').to_pylist()
    rows[0]['FROM_DEPTH']=None
    rows.append({**rows[0],'FROM_DEPTH':2.0,'TYPED_BIN_IDS':'BIN2','TYPED_DEPTHS':'2.5','TYPED_VALUES':'22.5'})
    pq.write_table(pa.Table.from_pylist(rows),root/'raw.parquet')
    other={**packet['scope'][0],'depth_from':2.0}
    packet['scope'].append(other)
    for entries in proof['typed_payload_bindings']['fields'].values():
        entries.append(copy.deepcopy(entries[0]))
        entries[-1].update(row_index=1,depth={'step':None,'from':2.0,'to':None},exact_scope_key=exact_scope_key(other))
    proof['typed_payload'].update(bin_ids=['TEMP','BIN2'],depths=[12.5,2.5],values=[12.5,22.5])
    refresh_typed_source_files(root,packet,proof)
    assert authority.packet_errors(packet,verify_sources=True)==[]
    second=proof['typed_payload_bindings']['fields']['values'][1]
    second.update(depth=copy.deepcopy(proof['depth']),exact_scope_key=proof['exact_scope_key'])
    assert any('SOURCE_PROFILE_BIN_DEPTH_PAIRING_MISMATCH' in e for e in authority.packet_errors(packet,verify_sources=True))


def test_primary_receive_literal_and_own_timezone_are_frozen_without_alias_loss(case):
    root,packet,db=case
    proof=packet['observations']['OBS-1']
    rows=pq.read_table(root/'raw.parquet').to_pylist()
    rows[0]['RECEIVE_TIME']='2024-01-01 09:00:30'
    pq.write_table(pa.Table.from_pylist(rows),root/'raw.parquet')
    refresh_typed_source_files(root,packet,proof)
    proof.update(source_receive_time_raw='2024-01-01 09:00:30',source_receive_timestamp_utc='2024-01-01T00:00:30+00:00',
        source_receive_clock_policy='LOCAL_RECEIVE_TIMEZONE',source_receive_timezone='Asia/Seoul')
    proof['field_evidence']['source_receive_timezone']=copy.deepcopy(proof['field_evidence']['source_receive_clock_policy'])
    assert authority.packet_errors(packet,verify_sources=True)==[]
    proof['source_receive_time_literal']='different'
    assert any('SOURCE_RECEIVE_ALIAS_CONFLICT' in e for e in authority.packet_errors(packet,verify_sources=True))
    proof.pop('source_receive_time_literal')
    proof['available_at']='2024-01-01T00:00:20+00:00'
    assert any('SOURCE_AVAILABLE_BEFORE_RECEIVED' in e for e in authority.packet_errors(packet,verify_sources=True))
    proof['available_at']='2024-01-01T00:01:00+00:00'
    proof.update(source_receive_time_raw=None,source_receive_timestamp_utc=None,source_receive_clock_policy='ABSENT_IN_SOURCE')
    assert any('SOURCE_LITERAL_MISMATCH:RECEIVE_TIME' in e for e in authority.packet_errors(packet,verify_sources=True))
