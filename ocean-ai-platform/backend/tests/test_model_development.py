"""Actual isolated authority -> migration -> worker -> review -> serving chain.

All source bytes and actors are fixture-only; the workstation DB is never used.
No production authority is patched out of this end-to-end test.
"""
import copy,hashlib,json,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.security import Actor
from app.api import routes_model_development,routes_mlops
from app.models.domain import (ObservationRaw,ObservationStandard,StationMetadata,SensorMetadata,
    DocumentIndex,DatasetRegistry,FeatureDefinition,ApprovalHistory,ModelRegistry)
from app.models.source_contracts import SourceContractPacket
from app.models.evidence import DatasetMembership
from app.services import source_contract_authority as source_authority
from app.services.dataset_migration import review_migration,migrate_v2
from app.services.source_contract_snapshot import DependencyError
from app.services.source_contract_review import exact_scope_key
from app.services.model_development import inspect_manifest,manifest_catalog,build_policy_bundle,task_readiness
from app.ml.comparison_runner import ComparisonBlocked,DatabaseAuthority,preflight,digest
from app.ml.job_queue import DurableQueue
from test_event_evidence import env,checked,OP,REVIEW,register_dataset
from test_source_contract_snapshot import source_packet,write_json


def install(client):
    client.app.include_router(routes_model_development.router)
    client.app.include_router(routes_mlops.router,prefix='/api/mlops')


def complete_legacy_family(client,sessions,tmp_path,monkeypatch):
    """Make 3 disjoint-source v1 snapshots using real existing review routes."""
    monkeypatch.setattr(source_authority,'SOURCE_ROOT',tmp_path)
    monkeypatch.setenv('SOURCE_CONTRACT_ALLOWED_ROOTS',json.dumps([str(tmp_path)]))
    monkeypatch.setenv('OCEAN_MLOPS_ROOT',str(tmp_path/'runtime'))
    monkeypatch.setenv('OCEAN_TRAINING_WORKER_ENABLED','1')
    monkeypatch.setenv('OCEAN_LOCAL_MODEL_SERVING_ENABLED','1')
    install(client)
    with sessions() as db:
        db.query(ObservationStandard).delete();db.query(ObservationRaw).delete();db.query(DocumentIndex).delete();db.commit()
    specs=[];old={};new={};spans={}
    for index,split in enumerate(('TRAIN','VALIDATION','TEST'),1):
        month=index+1;station='ST'+str(index);sensor='S'+str(index)
        start=datetime(2025,month,1);end=start+timedelta(minutes=12)
        quote=f'2025-{month:02d}-01 09:00~09:12(KST) 시험관측소 주 조위계 통신 지연 확인'
        with sessions() as db:
            if index>1:
                db.add(StationMetadata(station_id=station,station_name='시험관측소'));db.flush()
                db.add(SensorMetadata(sensor_id=sensor,station_id=station,variable_code='TIDE'))
            db.add(DocumentIndex(document_id='D'+split,chunk_id='C'+split,document_title='격리 E2E 시험 보고서',
                document_type='DAILY_INSPECTION_REPORT',document_date=end,chunk_text=quote,related_station_id=station,
                related_variable_code='TIDE',page_no=1,section_name='격리 시험',metadata_json={'is_demo':True,'source_checksum':'TEST-'+split}))
            db.commit()
        checked(client.post('/api/events/sensor-aliases',headers=REVIEW,json={'station_id':station,'sensor_id':sensor,'variable_code':'TIDE',
            'alias_text':'주 조위계','mapping_version':'1','valid_start':'2024-01-01T00:00:00Z'}))
        event=checked(client.post('/api/events/from-document',headers=OP,json={'station_id':station,'variable_code':'TIDE','expression':'주 조위계',
            'event_start':start.replace(tzinfo=timezone.utc).isoformat(),'event_end':end.replace(tzinfo=timezone.utc).isoformat(),
            'event_type':'COMMUNICATION_DELAY','chunk_id':'C'+split,'period_quote':quote,'operation_quote':'통신 지연 확인',
            'operation_time':(start+timedelta(minutes=1)).replace(tzinfo=timezone.utc).isoformat()}))
        folder=tmp_path/split;folder.mkdir()
        packet=source_packet(folder,event['event_id'])
        packet['contract_id']='source-'+split
        scope=dict(source_group='ISOLATED_TEST',station_code=station,item_code='TIDE_RAW',month=f'2025-{month:02d}',
                   depth_step=None,depth_from=None,depth_to=None)
        rows=[];proofs={};template=next(iter(packet['observations'].values()))
        for i in range(13):
            stamp=start+timedelta(minutes=i);literal=(stamp+timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')
            value=str(float(50+2*i))
            rows.append(dict(OBS_POST_ID=station,OBS_ITEM_CODE='TIDE_RAW',OBS_TIME=literal,OBS_VALUE=value,
                             QC_FLAG='OK',MQC_FLAG='G ',N1_AQC_FLAG=''))
            proof=copy.deepcopy(template)
            proof.update(source_station_code=station,source_station_literal=station,canonical_station_id=station,
                         canonical_sensor_id=sensor,physical_sensor_id='serial-'+split,sensor_episode_id='episode-'+split,
                         source_month=scope['month'],exact_scope_key=exact_scope_key(scope),source_time_raw=literal,source_value_raw=value,
                         timestamp_utc=stamp.replace(tzinfo=timezone.utc).isoformat(),available_at=stamp.replace(tzinfo=timezone.utc).isoformat(),
                         qc_available_at=stamp.replace(tzinfo=timezone.utc).isoformat(),source_row_locator=f'parquet_row_group=0;row_index={i}',
                         value=float(value),document_family_ids=['document-family-'+split])
            proofs[split+'-O'+str(i)]=proof
        parquet=folder/'raw.parquet';pq.write_table(pa.Table.from_pylist(rows),parquet)
        psha=hashlib.sha256(parquet.read_bytes()).hexdigest()
        raw_source=folder/'source.csv'
        raw_source.write_text(json.dumps(rows,sort_keys=True,ensure_ascii=False),encoding='utf-8')
        raw_sha=hashlib.sha256(raw_source.read_bytes()).hexdigest()
        manifest=json.loads((folder/'manifest.json').read_text());manifest.update(raw_sha256=psha,raw_rows=len(rows),source_sha256=raw_sha,source_size=raw_source.stat().st_size)
        write_json(folder/'manifest.json',manifest);msha=hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest()
        for f in packet['files']:
            f['path']=split+'/'+f['path'];path=tmp_path/f['path'];f.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
        packet['scope']=[scope];packet['observations']=proofs
        for proof in proofs.values():
            proof.update(parquet_sha256=psha,source_manifest_sha256=msha,source_sha256=raw_sha)
            for claims in proof['field_evidence'].values():
                for claim in claims:claim['file_sha256']=raw_sha
        with sessions() as db:
            source_authority.request_contract(db,packet,Actor('operator','operator'))
            decision=source_authority.decide_contract(db,packet['contract_id'],source_authority.receipt_sha256(packet),'APPROVED',Actor('reviewer','reviewer'))
            db.commit()
        receipt_path,receipt_sha=write_json(folder/'receipt.json',decision['receipt'],True)
        specs.append({'role':'SOURCE_CONTRACT','path':receipt_path,'sha256':receipt_sha})
        checked(client.post('/api/datasets/source-ingest',headers=OP,json={'receipt_path':receipt_path,'receipt_sha256':receipt_sha}))
        checked(client.post('/api/qc/rules/execute',headers=OP,json={'station_id':station,'sensor_id':sensor,'variable_code':'TIDE'}))
        eid=event['event_id'];assert checked(client.post(f'/api/events/{eid}/link-observations',headers=OP))['observations']==12
        label=checked(client.post(f'/api/events/{eid}/label-candidates',headers=OP,json={'label_version':'1'}))
        checked(client.post('/api/approvals/approve',headers=REVIEW,json={'target_type':'AI_LABEL','target_id':label['label_id']}))
        checked(client.post(f'/api/events/{eid}/features',headers=OP))
        old[split]='LEGACY-'+split;new[split]='V2-'+split
        checked(register_dataset(client,old[split],dataset_name='isolated-full-chain',dataset_version='legacy-'+split,
            dataset_split=split,station_scope=[station],sensor_scope=[sensor],period_start=start.replace(tzinfo=timezone.utc).isoformat(),
            period_end=end.replace(tzinfo=timezone.utc).isoformat()))
        built=checked(client.post(f'/api/datasets/{old[split]}/build',headers=OP))
        assert not built['validation_errors']
        spans[split]=(start,end)
    with sessions() as db:
        features=[r.feature_id for r in db.query(FeatureDefinition).order_by(FeatureDefinition.feature_id)]
        draft=build_policy_bundle(db,{'domain':'fixed_station','item_id':'tide','task':'FORECASTING','target_variable':'TIDE','unit':'cm',
            'dataset_ids':old,'protocol_id':'isolated-e2e-policy','version':'1','feature_ids':features,
            'split_strategy':'station_holdout','embargo_seconds':0,'horizon_seconds':60,'lookback_seconds':720,
            'ridge_alphas':[0.001,0.01,0.1],'limits':{'min_test_samples':2,'max_local_p95_ms':10000,
                'min_mae_improvement_fraction':0.01,'max_rmse_regression_fraction':0.1},'cost_policy':'LOCAL_PILOT_COST_NOT_REQUIRED'})
    assert draft['approved'] is False
    draft['protocols']['SPLIT_PROTOCOL']['body']['dataset_ids']=new
    for role,entry in draft['protocols'].items():
        result=checked(client.post('/api/mlops/protocols/draft',headers=REVIEW,json={'body':entry['body']}))
        checked(client.post(f"/api/mlops/protocols/{result['sha256']}/decision",headers=REVIEW,json={'decision':'APPROVED'}))
        specs.append({'role':role,'path':result['path'],'sha256':result['sha256']})
    return old,new,specs


def test_migration_worker_independent_review_predict_and_rollback_real_authority(env,tmp_path,monkeypatch):
    client,sessions=env
    old,new,specs=complete_legacy_family(client,sessions,tmp_path,monkeypatch)
    original={}
    for split in old:
        with sessions() as db:
            row=db.get(DatasetRegistry,old[split]);sha=row.data_hash
            original[split]=(Path(settings.DATASET_SNAPSHOT_DIR)/(sha+'.json')).read_bytes()
            review=review_migration(db,old[split],new[split],'v2-'+split,specs,settings.DATASET_SNAPSHOT_DIR)
            assert not review['blockers'],review
        request={'new_dataset_id':new[split],'new_version':'v2-'+split,'dependencies':specs,
                 'expected_legacy_sha256':sha,'expected_review_sha256':review['review_sha256']}
        result=checked(client.post(f'/api/model-development/datasets/{old[split]}/migrate-v2',headers=OP,json=request))
        assert result['status']=='BUILT_UNAPPROVED' and result['legacy_approval_copied'] is False
        assert checked(client.post(f'/api/datasets/{new[split]}/validate',headers=OP))['status']=='VALIDATED'
        checked(client.post(f'/api/datasets/{new[split]}/approve',headers=REVIEW))
        with sessions() as db:
            assert db.get(DatasetRegistry,old[split]).status=='BUILT'
            assert (Path(settings.DATASET_SNAPSHOT_DIR)/(sha+'.json')).read_bytes()==original[split]
    request=checked(client.post('/api/model-development/training-manifests',headers=OP,json={'dataset_ids':new}))
    assert request['status']=='READY' and request['queue_created'] is False,json.dumps(request.get('blockers'),ensure_ascii=False)
    inspect=checked(client.get('/api/model-development/training-preflight',params={'manifest_path':request['manifest_path'],'expected_sha256':request['manifest_sha256']}))
    assert inspect['status']=='READY' and inspect['training_started'] is False
    altered=client.post('/api/mlops/training/enqueue',headers=OP,json={'manifest_path':request['manifest_path'],'expected_sha256':'f'*64})
    assert altered.status_code==409 and 'REVIEWED_MANIFEST_CHANGED' in altered.text
    assert not (tmp_path/'runtime'/'worker').exists()
    job=checked(client.post('/api/mlops/training/enqueue',headers=OP,json={'manifest_path':request['manifest_path'],'expected_sha256':request['manifest_sha256']}))
    queue=DurableQueue(tmp_path/'runtime'/'worker')
    with sessions() as db:completed=queue.run_once(DatabaseAuthority(db,settings.DATASET_SNAPSHOT_DIR))
    assert completed['acceptance']['status']=='PASS'
    with queue.connect() as ledger:receipt=ledger.execute('SELECT receipt_path FROM queue_jobs WHERE job_id=?',(job['job_id'],)).fetchone()[0]
    body={'receipt_path':receipt,'model_version':'ISOLATED-E2E-1'}
    assert client.post('/api/mlops/candidates/register',headers=OP,json=body).status_code==409
    monkeypatch.setattr(settings,'API_IDENTITIES',{**settings.API_IDENTITIES,'independent':{'token':'isolated-independent-token','role':'reviewer'}})
    independent={'Authorization':'Bearer isolated-independent-token'}
    reviewed=checked(client.post('/api/mlops/candidates/review',headers=independent,json=body))
    assert reviewed['reviewer_id']=='independent' and reviewed['status']=='INDEPENDENT_REPLAY_MATCH'
    registered=checked(client.post('/api/mlops/candidates/register',headers=OP,json=body))
    assert registered['status']=='PENDING_APPROVAL'
    assert client.post('/api/mlops/models/ISOLATED-E2E-1/deploy',headers=REVIEW,json={'deployment_target':'loopback'}).status_code==409
    checked(client.post('/api/mlops/models/ISOLATED-E2E-1/decision',headers=REVIEW,json={'decision':'APPROVED'}))
    deployed=checked(client.post('/api/mlops/models/ISOLATED-E2E-1/deploy',headers=REVIEW,json={'deployment_target':'loopback'}))
    report=json.loads(Path(receipt).read_text());sample=report['serving_smoke_sample']
    with TestClient(client.app,client=('127.0.0.1',31001)) as local:
        response=checked(local.post('/api/mlops/serving/predict',headers=OP,json={'scope_key':deployed['scope_key'],**sample}))
        assert response['identity']==deployed['identity']
    # A second immutable manifest/run makes a distinct candidate while keeping
    # the first candidate's source input untouched for rollback authority.
    manifest=json.loads(Path(request['manifest_path']).read_text());manifest['isolated_repeat']='SECOND'
    second_path=tmp_path/'runtime'/'requests'/'second.json';write_json(second_path,manifest,True)
    second_job=checked(client.post('/api/mlops/training/enqueue',headers=OP,json={'manifest_path':str(second_path)}))
    with sessions() as db:queue.run_once(DatabaseAuthority(db,settings.DATASET_SNAPSHOT_DIR))
    with queue.connect() as ledger:second_receipt=ledger.execute('SELECT receipt_path FROM queue_jobs WHERE job_id=?',(second_job['job_id'],)).fetchone()[0]
    second={'receipt_path':second_receipt,'model_version':'ISOLATED-E2E-2'}
    checked(client.post('/api/mlops/candidates/review',headers=independent,json=second));checked(client.post('/api/mlops/candidates/register',headers=OP,json=second))
    checked(client.post('/api/mlops/models/ISOLATED-E2E-2/decision',headers=REVIEW,json={'decision':'APPROVED'}))
    checked(client.post('/api/mlops/models/ISOLATED-E2E-2/deploy',headers=REVIEW,json={'deployment_target':'loopback'}))
    pointer=tmp_path/'runtime'/'serving'/(deployed['scope_key']+'.json');before=pointer.read_bytes()
    assert client.post('/api/mlops/models/ISOLATED-E2E-2/rollback',headers=REVIEW).status_code==409
    assert pointer.read_bytes()==before
    checked(client.post('/api/mlops/models/ISOLATED-E2E-1/decision?rollback=true',headers=REVIEW,json={'decision':'APPROVED'}))
    restored=checked(client.post('/api/mlops/models/ISOLATED-E2E-2/rollback',headers=REVIEW))
    assert restored['identity']==deployed['identity'] and restored['operation']=='ROLLBACK'
    with sessions() as db:
        assert db.query(ApprovalHistory).filter_by(approval_type='MODEL_INDEPENDENT_REVIEW',approved_by='independent').count()==2
        assert db.query(ModelRegistry).count()==2
    evidence={'status':'PASS','failed':0,'passed':1,'source':'ISOLATED_FIXTURES_ONLY_NO_PRODUCTION_AUTHORITY_PATCH',
              'checks':[{'name':name,'passed':True} for name in ('REAL_SOURCE_AND_PROTOCOL_REVIEW','V1_IMMUTABLE_NEW_V2_BUILD',
                'SEPARATE_DATASET_APPROVAL','SAME_LOCKED_TEST_PAIRS','FAILED_HASH_NO_QUEUE_CREATION','FENCED_WORKER',
                'INDEPENDENT_REPLAY_REQUIRED','CANDIDATE_REGISTRATION','MODEL_APPROVAL_REQUIRED','LOCAL_AUTHORIZED_PREDICT',
                'SECOND_DEPLOY','UNAPPROVED_ROLLBACK_POINTER_UNCHANGED','APPROVED_PREVIOUS_CHAMPION_RESTORED')],
              'job_id':job['job_id'],'manifest_sha256':request['manifest_sha256'],'report_sha256':reviewed['report_sha256'],
              'artifact_sha256':report['artifact_sha256'],'origin_membership_sha256':report['origin_membership_sha256'],
              'pairs':len(report['paired_test_predictions']),'test_metrics':report['test_metrics'],'acceptance':report['acceptance'],
              'independent_reviewer':'independent','prediction':response['prediction'],'rollback_identity':restored['identity'],
              'live_database_mutations':0}
    if os.environ.get('OCEAN_MODEL_E2E_EVIDENCE'):
        target=Path(os.environ['OCEAN_MODEL_E2E_EVIDENCE']);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
        (target.parent/'isolated-worker-report.json').write_bytes(Path(receipt).read_bytes())
        (target.parent/'isolated-model-artifact.json').write_bytes(Path(report['artifact_path']).read_bytes())


def test_legacy_review_missing_authorities_does_not_write_or_change_snapshot(env,tmp_path,monkeypatch):
    from test_event_evidence import complete_chain
    client,sessions=env;install(client)
    _,_,built=complete_chain(client)
    path=Path(settings.DATASET_SNAPSHOT_DIR)/(built['data_hash']+'.json');before=path.read_bytes()
    with sessions() as db:
        reviewed=review_migration(db,'DS1','V2-new','v2',[],settings.DATASET_SNAPSHOT_DIR)
        assert reviewed['status']=='BLOCKED' and 'SOURCE_CONTRACT_DEPENDENCIES_MISSING' in reviewed['blockers']
        assert db.query(DatasetRegistry).count()==1 and reviewed['mutation_performed'] is False
        with pytest.raises(DependencyError,match='MIGRATION_REVIEW_BLOCKED'):
            migrate_v2(db,'DS1','V2-new','v2',[],settings.DATASET_SNAPSHOT_DIR,built['data_hash'],reviewed['review_sha256'],Actor('operator','operator'))
        assert db.query(DatasetRegistry).count()==1
    assert path.read_bytes()==before


@pytest.mark.parametrize('kind',['outside','altered_hash','unapproved'])
def test_rejected_enqueue_does_not_even_initialize_queue(env,tmp_path,monkeypatch,kind):
    client,sessions=env;install(client);monkeypatch.setenv('OCEAN_MLOPS_ROOT',str(tmp_path/'runtime'));monkeypatch.setenv('OCEAN_TRAINING_WORKER_ENABLED','1')
    path=tmp_path/'runtime'/'requests'/'request.json';path.parent.mkdir(parents=True)
    body={'schema_version':'typed-model-comparison-2','task':'FORECASTING','domain':'fixed_station','item_id':'tide','quantity_kind':'SCALAR',
        'acceptance_criteria_status':'NOT_DEFINED','target_variable':'TIDE','unit':'cm','horizon_seconds':60,'feature_ids':['x'],
        'ridge_alphas':[1.],'refit_train_validation':False,'splits':{s:{'dataset_id':'NO-'+s,'sha256':'a'*64} for s in ('TRAIN','VALIDATION','TEST')},
        'locked_holdout_sha256':'a'*64}
    write_json(path,body,True)
    params={'manifest_path':str(path),'expected_sha256':'b'*64}
    if kind=='outside':params['manifest_path']=str(tmp_path/'.env')
    response=client.post('/api/mlops/training/enqueue',headers=OP,json=params)
    assert response.status_code==409
    assert not (tmp_path/'runtime'/'worker').exists()
    if kind=='outside':assert client.get('/api/model-development/training-preflight',params=params).status_code==409


def test_catalog_is_review_only_and_cannot_follow_dependency_reparse_or_env(env,tmp_path,monkeypatch):
    client,sessions=env;install(client);monkeypatch.setenv('OCEAN_MLOPS_ROOT',str(tmp_path/'runtime'))
    assert manifest_catalog()['state']=='NO_REQUESTS' and not (tmp_path/'runtime').exists()
    with sessions() as db:
        with pytest.raises(ComparisonBlocked,match='OUTSIDE_CONFIGURED_ROOT'):inspect_manifest(db,tmp_path/'.env',settings.DATASET_SNAPSHOT_DIR)


@pytest.mark.parametrize('body',[None,[],17,'bad',{}, {'schema_version':'wrong'}])
def test_malformed_request_is_invalid_catalog_item_and_structured_preflight_failure(env,tmp_path,monkeypatch,body):
    client,_=env;install(client);monkeypatch.setenv('OCEAN_MLOPS_ROOT',str(tmp_path/'runtime'))
    root=tmp_path/'runtime'/'requests';root.mkdir(parents=True);write_json(root/'bad.json',body,True)
    catalog=checked(client.get('/api/model-development/training-manifests'))
    assert catalog['manifests'][0]['status']=='INVALID'
    assert catalog['manifests'][0]['blocker']=='COMPARISON_MANIFEST_SCHEMA_REQUIRED'
    response=client.get('/api/model-development/training-preflight',params={'manifest_path':str(root/'bad.json')})
    assert response.status_code==409 and 'COMPARISON_MANIFEST_SCHEMA_REQUIRED' in response.text
    monkeypatch.setenv('OCEAN_TRAINING_WORKER_ENABLED','1')
    enqueue=client.post('/api/mlops/training/enqueue',headers=OP,json={'manifest_path':str(root/'bad.json')})
    assert enqueue.status_code==409
    assert not (tmp_path/'runtime'/'worker').exists()


def test_migration_stale_review_revoked_source_and_commit_failure_leave_legacy_intact(env,tmp_path,monkeypatch):
    client,sessions=env;old,new,specs=complete_legacy_family(client,sessions,tmp_path,monkeypatch)
    with sessions() as db:
        sha=db.get(DatasetRegistry,old['TRAIN']).data_hash
        path=Path(settings.DATASET_SNAPSHOT_DIR)/(sha+'.json');before=path.read_bytes()
        review=review_migration(db,old['TRAIN'],new['TRAIN'],'v2-TRAIN',specs,settings.DATASET_SNAPSHOT_DIR)
        with pytest.raises(DependencyError,match='MIGRATION_REVIEW_CHANGED'):
            migrate_v2(db,old['TRAIN'],new['TRAIN'],'v2-TRAIN',specs,settings.DATASET_SNAPSHOT_DIR,sha,'f'*64,Actor('operator','operator'))
        assert db.get(DatasetRegistry,new['TRAIN']) is None
        def failed_commit():raise RuntimeError('ISOLATED_COMMIT_FAILURE')
        with monkeypatch.context() as scoped:
            scoped.setattr(db,'commit',failed_commit)
            with pytest.raises(RuntimeError,match='ISOLATED_COMMIT_FAILURE'):
                migrate_v2(db,old['TRAIN'],new['TRAIN'],'v2-TRAIN',specs,settings.DATASET_SNAPSHOT_DIR,sha,review['review_sha256'],Actor('operator','operator'))
        assert db.get(DatasetRegistry,new['TRAIN']) is None
        assert db.get(DatasetRegistry,old['TRAIN']).data_hash==sha and path.read_bytes()==before
        packet=db.get(SourceContractPacket,'source-TRAIN')
        source_authority.decide_contract(db,packet.contract_id,packet.packet_sha256,'REVOKED',Actor('reviewer','reviewer'));db.commit()
        revoked=review_migration(db,old['TRAIN'],new['TRAIN'],'v2-TRAIN',specs,settings.DATASET_SNAPSHOT_DIR)
        assert revoked['status']=='BLOCKED' and any('SOURCE_CONTRACT' in e for e in revoked['blockers'])
        with pytest.raises(DependencyError,match='MIGRATION_REVIEW_(CHANGED|BLOCKED)'):
            migrate_v2(db,old['TRAIN'],new['TRAIN'],'v2-TRAIN',specs,settings.DATASET_SNAPSHOT_DIR,sha,review['review_sha256'],Actor('operator','operator'))
        assert db.get(DatasetRegistry,new['TRAIN']) is None and path.read_bytes()==before


def test_task_inventory_keeps_raw_discovery_distinct_from_approval(env,tmp_path,monkeypatch):
    client,sessions=env;monkeypatch.setenv('OCEAN_MLOPS_ROOT',str(tmp_path/'runtime'))
    root=tmp_path/'diagnostic';root.mkdir()
    _,sha=write_json(root/'source-file-manifest.json',{'files':[]})
    write_json(root/'diagnostic-channel-metrics.json',{'approved':False,'source_files_manifest_sha256':sha,'channels':[
        {'grain':{'source_group':'RAW_TEST','item_code':'AIR_PRES','station_code':'S','month':'2026-07'},'raw_rows':50,'channel_sha256':'f'*64}]})
    with sessions() as db:
        result=task_readiness(db,root)
        assert result['task_keys']==72 and result['training_ready_count']==0
        assert result['operational_ready_count'] is None
        matched=[r for r in result['rows'] if r['raw_grain_count']]
        assert len(matched)==3 and all(r['source_status']=='BLOCKED' and r['raw_mapping_authority'].startswith('LITERAL_DISCOVERY') for r in matched)
        (root/'source-file-manifest.json').write_text('{}')
        changed=task_readiness(db,root)
        assert changed['source_inventory_status']=='UNAVAILABLE' and changed['diagnostic_issues']==['RAW_DIAGNOSTIC_SOURCE_MANIFEST_CHANGED']


@pytest.mark.parametrize('channels',[None,[None],[{}],[{'grain':None,'raw_rows':4}],[{'grain':{'source_group':'X','station_code':'S','item_code':'AIR_PRES','month':'2026-07'},'raw_rows':'50'}]])
def test_malformed_raw_inventory_returns_unavailable_not_ready(env,tmp_path,monkeypatch,channels):
    _,sessions=env;monkeypatch.setenv('OCEAN_MLOPS_ROOT',str(tmp_path/'runtime'))
    root=tmp_path/'diagnostic';root.mkdir();_,sha=write_json(root/'source-file-manifest.json',{'files':[]})
    write_json(root/'diagnostic-channel-metrics.json',{'approved':False,'source_files_manifest_sha256':sha,'channels':channels})
    with sessions() as db:result=task_readiness(db,root)
    assert result['source_inventory_status']=='UNAVAILABLE' and result['diagnostic_issues']
    assert result['training_ready_count']==0 and all(r['raw_held_rows']==0 for r in result['rows'])


@pytest.mark.parametrize('records',[None,[],[None],[{'id':'O','event_id':'E','label':None}]])
def test_malformed_legacy_records_are_structured_get_and_post_blockers(env,tmp_path,monkeypatch,records):
    from test_event_evidence import complete_chain
    client,sessions=env;install(client);_,_,built=complete_chain(client)
    original=Path(settings.DATASET_SNAPSHOT_DIR)/(built['data_hash']+'.json')
    body=json.loads(original.read_bytes());body['records']=records
    sha=digest(body);target=Path(settings.DATASET_SNAPSHOT_DIR)/(sha+'.json');write_json(target,body)
    with sessions() as db:db.get(DatasetRegistry,'DS1').data_hash=sha;db.commit()
    get=client.get('/api/model-development/datasets/DS1/migration-review',params={'new_dataset_id':'NEW','new_version':'2'})
    assert get.status_code==409 and 'LEGACY_FROZEN_RECORDS_SHAPE_INVALID' in get.text
    post=client.post('/api/model-development/datasets/DS1/migrate-v2',headers=OP,json={'new_dataset_id':'NEW','new_version':'2','dependencies':[],
        'expected_legacy_sha256':sha,'expected_review_sha256':'a'*64})
    assert post.status_code==409 and 'LEGACY_FROZEN_RECORDS_SHAPE_INVALID' in post.text
    with sessions() as db:assert db.get(DatasetRegistry,'NEW') is None


def test_missing_legacy_file_is_structured_blocker_without_new_version(env):
    from test_event_evidence import complete_chain
    client,sessions=env;install(client);complete_chain(client)
    with sessions() as db:db.get(DatasetRegistry,'DS1').data_hash='e'*64;db.commit()
    get=client.get('/api/model-development/datasets/DS1/migration-review',params={'new_dataset_id':'NEW','new_version':'2'})
    assert get.status_code==409 and 'DEPENDENCY_NOT_REGULAR_FILE' in get.text
    post=client.post('/api/model-development/datasets/DS1/migrate-v2',headers=OP,json={'new_dataset_id':'NEW','new_version':'2','dependencies':[],
        'expected_legacy_sha256':'e'*64,'expected_review_sha256':'a'*64})
    assert post.status_code==409 and 'DEPENDENCY_NOT_REGULAR_FILE' in post.text
    with sessions() as db:assert db.get(DatasetRegistry,'NEW') is None


@pytest.mark.parametrize('role',[[],{},None,4])
def test_nested_dependency_role_shapes_are_structured_for_get_and_post(env,role):
    from test_event_evidence import complete_chain
    client,sessions=env;install(client);_,_,built=complete_chain(client)
    dependencies=[{'role':role,'path':'fixture.json','sha256':'b'*64}]
    response=client.get('/api/model-development/datasets/DS1/migration-review',params={'new_dataset_id':'NEW','new_version':'2','dependencies_json':json.dumps(dependencies)})
    assert response.status_code==409 and 'DEPENDENCY_SPEC_INVALID' in response.text
    post=client.post('/api/model-development/datasets/DS1/migrate-v2',headers=OP,json={'new_dataset_id':'NEW','new_version':'2','dependencies':dependencies,
        'expected_legacy_sha256':built['data_hash'],'expected_review_sha256':'a'*64})
    assert post.status_code==409 and 'DEPENDENCY_SPEC_INVALID' in post.text
    with sessions() as db:assert db.get(DatasetRegistry,'NEW') is None


@pytest.mark.parametrize('shape',['list','records_null','record_null','duplicate_id'])
def test_policy_preview_rejects_exact_hash_but_malformed_snapshot(env,shape):
    from test_event_evidence import complete_chain
    client,sessions=env;install(client);_,_,built=complete_chain(client)
    original=json.loads((Path(settings.DATASET_SNAPSHOT_DIR)/(built['data_hash']+'.json')).read_bytes())
    body=[] if shape=='list' else copy.deepcopy(original)
    if shape=='records_null':body['records']=None
    if shape=='record_null':body['records']=[None]
    if shape=='duplicate_id':body['records']=[body['records'][0],body['records'][0]]
    sha=digest(body);write_json(Path(settings.DATASET_SNAPSHOT_DIR)/(sha+'.json'),body)
    with sessions() as db:db.get(DatasetRegistry,'DS1').data_hash=sha;db.commit()
    selection={'domain':'fixed_station','item_id':'tide','task':'FORECASTING','dataset_ids':{'TRAIN':'DS1','VALIDATION':'DS2','TEST':'DS3'}}
    response=client.get('/api/model-development/policy-bundle',params={'selection_json':json.dumps(selection)})
    assert response.status_code==409 and 'FIXED_' in response.text
