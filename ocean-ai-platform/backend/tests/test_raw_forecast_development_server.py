import copy
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from starlette.testclient import TestClient

from app.ml.raw_forecast_development_server import (
    DEV_FLAGS, DevelopmentReleaseError, ReleaseStore, canonical, create_app,
    file_sha, prediction, validate_artifact, validate_release, digest, NATIVE_PERIODS, verify_membership,
)


def save(path,body):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(canonical(body))
    return file_sha(path)


def candidate(root, source_root, *, release_id='release-one'):
    source_root.mkdir(parents=True,exist_ok=True)
    columns=['OBS_POST_ID','OBS_ITEM_CODE','OBS_TIME','OBS_VALUE','META_ID','RECEIVE_TIME','TRACK_SEQ','REMOTE_CHECK']
    source_rows=[]; rows={}
    for vi,var in enumerate(['AIR_PRES','WATER_TEMP','SALINITY']):
        rows[var]=[]
        for i,day in enumerate([1,2,3,4,19,20,21,22,25,26,27,31]):
            literal={key:None for key in columns}
            literal.update(OBS_POST_ID='DT_0001',OBS_ITEM_CODE=var,OBS_TIME=f'2026-07-{day:02d} 23:59:00',OBS_VALUE=str(10+vi+i),META_ID='M',TRACK_SEQ='1',REMOTE_CHECK='0')
            idx=len(source_rows);source_rows.append(literal)
            rows[var].append((idx,literal))
    source=source_root/'raw.parquet';pq.write_table(pa.Table.from_pylist(source_rows),source)
    sha=file_sha(source)
    base={'task':'NEXT_OBSERVED_ROW_FORECAST','native_clock_only':True,'unit':None,'timezone':None,'horizon_seconds':None,**DEV_FLAGS}
    manifest={'schema_version':'raw-forecast-release-v1','release_id':release_id,'source_period':'2026-07',**base,
              'sources':[{'path':str(source),'sha256':sha,'bytes':source.stat().st_size}],'models':[],
              'source_group':'GR_OBS_ST','source_table':'GR_OBS_ST','station_code':'DT_0001','recipe_sha256':'1'*64}
    selection={'schema_version':'raw-next-row-source-selection-v1','source_period':'2026-07','station_code':'DT_0001',
               'identifier_transform':'IDENTITY_NO_TRIM','native_clock_only':True,'unit':None,'timezone':None,'horizon_seconds':None,
               'source':{'path':str(source),'sha256':sha,'bytes':source.stat().st_size,'source_group':'GR_OBS_ST'},**DEV_FLAGS}
    manifest['source_selection_relative_path']='source-selection.json';manifest['source_selection_sha256']=save(root/'source-selection.json',selection)
    for var,rawrows in rows.items():
        members=[]
        for i,(idx,literal) in enumerate(rawrows):
            members.append({'row_id':f'{var}-{idx}','split':'TRAIN' if i<4 else 'VALIDATION' if i<8 else 'TEST',
                            'clock_raw':literal['OBS_TIME'],'value_raw':literal['OBS_VALUE'],'numeric_value':float(literal['OBS_VALUE']),
                            'numeric_status':'FINITE','pair_eligible_numeric':True,
                            'source':{'sha256':sha,'locator':f'parquet_row_group=0;row_index={idx}','row_group':0,'row_index':idx,'column':'OBS_VALUE'},
                            'raw_literals':literal,'source_group':'GR_OBS_ST','station_literal':'DT_0001','item_literal':var})
        member_path=root/f'memberships/{var}.jsonl';member_path.parent.mkdir(parents=True,exist_ok=True)
        member_path.write_bytes(b'\n'.join(canonical(row) for row in members)+b'\n');member_sha=file_sha(member_path)
        split_ids={split:digest([m['row_id'] for m in members if m['split']==split]) for split in ['TRAIN','VALIDATION','TEST']}
        policy={'schema_version':'raw-next-row-training-policy-v1','variable_code':var,'source_group':'GR_OBS_ST','station_code':'DT_0001','source_period':'2026-07',
                'native_periods':NATIVE_PERIODS,'input_lags':3,'holdout_locked':True,'parameters_fit':'TRAIN_ONLY','selection':'VALIDATION_MAE_ONLY_TIES_PERSISTENCE',
                'target':'NEXT_OBSERVED_NATIVE_ROW_NOT_FIXED_CADENCE','ridge_alphas':[0.01,0.1,1.0,10.0,100.0],
                'missing_policy':'RETAIN_NATIVE_ROW_AND_EXCLUDE_ANY_NONFINITE_OR_AMBIGUOUS_4_ROW_WINDOW_NO_IMPUTATION',
                'source_membership_sha256':member_sha,'source_membership_count':12,'membership_split_counts':{'TRAIN':4,'VALIDATION':4,'TEST':4},
                'source_selection_sha256':manifest['source_selection_sha256'],'split_member_ids_sha256':split_ids,'approved':False,'nonoperational':True,
                'physical_unit':None,'timezone':None,'horizon_seconds':None}
        policy_sha=save(root/f'policies/{var}.json',policy)
        metrics={kind:{'mae':0.5 if kind=='RIDGE' and var=='WATER_TEMP' else 1.,'rmse':1.2,'pair_count':1} for kind in ['PERSISTENCE','RIDGE']}
        artifact={'schema_version':'raw-next-row-model-v1','variable_code':var,'input_lags':3,'selected_model':'RIDGE' if var=='WATER_TEMP' else 'PERSISTENCE',
                  'params':{'coefficients':[0.2,0.3,0.5],'intercept':1.0,'mean':[1.,2.,3.],'scale':[2.,2.,2.]} if var=='WATER_TEMP' else {},
                  'source_membership_sha256':member_sha,'source_membership_count':12,'membership_split_counts':{'TRAIN':4,'VALIDATION':4,'TEST':4},
                  'source_group':'GR_OBS_ST','station_code':'DT_0001','source_period':'2026-07','parameters_fit':'TRAIN_ONLY','refit_on_validation':False,
                  'model_selection':'VALIDATION_ONLY_NO_TEST_TUNING','recipe_sha256':manifest['recipe_sha256'],'source_selection_sha256':manifest['source_selection_sha256'],
                  'policy_sha256':policy_sha,'split_member_ids_sha256':split_ids,'pair_counts':{'TRAIN':1,'VALIDATION':1,'TEST':1},
                  'validation_metrics':metrics,'test_metrics':metrics,**base}
        artifact_sha=save(root/f'models/{var}.json',artifact)
        spec={'variable_code':var,'artifact_relative_path':f'models/{var}.json','artifact_sha256':artifact_sha,
              'source_membership_relative_path':f'memberships/{var}.jsonl','source_membership_sha256':member_sha,
              'source_membership_count':12,'membership_split_counts':{'TRAIN':4,'VALIDATION':4,'TEST':4},'split_counts':{'TRAIN':4,'VALIDATION':4,'TEST':4},
              'pair_counts':{'TRAIN':1,'VALIDATION':1,'TEST':1},'split_member_ids_sha256':split_ids,'selected_model':artifact['selected_model'],
              'policy_relative_path':f'policies/{var}.json','policy_sha256':policy_sha,
              'last_values':[m['numeric_value'] for m in members[-3:]],'last_native_times':[m['clock_raw'] for m in members[-3:]],
              'last_source_locators3':[m['source'] for m in members[-3:]],
              'validation_metrics':metrics,'test_metrics':metrics}
        for kind in ['training','eval']:
            name=f'receipts/{var}-{kind}.json'
            receipt={'source_membership_sha256':member_sha,'artifact_sha256':artifact_sha,'selected_model':artifact['selected_model'],
                     'validation_metrics':metrics,'test_metrics':metrics,'source_membership_count':12,'membership_split_counts':spec['membership_split_counts'],
                     'split_counts':spec['split_counts'],'policy_sha256':policy_sha,'source_selection_sha256':manifest['source_selection_sha256'],
                     'recipe_sha256':manifest['recipe_sha256'],'approved':False,'production_eligible':False,'parameters_fit':'TRAIN_ONLY','refit_on_validation':False,
                     'test_used_for_selection':False,'model_selection':'VALIDATION_MAE_ONLY_TIES_PERSISTENCE','pair_counts':spec['pair_counts'],
                     'holdout_used_only_for_evaluation':True}
            spec[kind+'_receipt_relative_path']=name;spec[kind+'_receipt_sha256']=save(root/name,receipt)
        manifest['models'].append(spec)
    manifest['dependency_contract_version']=2
    paths=['source-selection.json']+[f'{folder}/{var}{suffix}' for var in rows for folder,suffix in [('models','.json'),('memberships','.jsonl'),('policies','.json'),('receipts','-training.json'),('receipts','-eval.json')]]
    manifest['pinned_dependencies']=[{'path':path,'sha256':file_sha(root/path)} for path in paths]
    save(root/'release-manifest.json',manifest)
    return manifest


def client(store):
    return TestClient(create_app(store),base_url='http://127.0.0.1:8011',client=('127.0.0.1',51234))


def request_for(release,var='WATER_TEMP',values=None):
    spec=next(m for m in release['models'] if m['variable_code']==var)
    return {'model_id':var,'values':values if values is not None else spec['last_values'],
            'expected_release_id':release['release_id'],'expected_artifact_sha256':spec['artifact_sha256']}


def test_real_json_parquet_membership_release_serves_selected_math(tmp_path):
    manifest=candidate(tmp_path/'candidate',tmp_path/'source')
    store=ReleaseStore(tmp_path/'deploy',allowed_source_roots=[tmp_path/'source'])
    pointer=store.register(tmp_path/'candidate')
    api=client(store)
    assert api.get('/readiness').json()['model_count']==3
    details=api.get('/release').json()
    assert details['source_period']=='2026-07' and details['source_table']=='GR_OBS_ST'
    for var in ['AIR_PRES','WATER_TEMP','SALINITY']:
        body=request_for(manifest,var)
        response=api.post('/predict',json=body)
        assert response.status_code==200
        artifact=json.loads((tmp_path/'candidate'/f'models/{var}.json').read_bytes())
        assert response.json()['prediction']==prediction(artifact,body['values'])
        assert response.json()['approved'] is False and response.json()['horizon_seconds'] is None
    assert pointer['release_id']=='release-one'


@pytest.mark.parametrize('values',[[1,2],[1,2,3,4],[True,2,3],['1',2,3],[10**400,2,3],[1e300,2,float('inf')]])
def test_bad_length_type_and_nonfinite_never_500(tmp_path,values):
    store=ReleaseStore(tmp_path/'deploy',allowed_source_roots=[tmp_path/'source'])
    body={'model_id':'AIR_PRES','values':values,'expected_release_id':'one','expected_artifact_sha256':'0'*64}
    response=client(store).post('/predict',content=json.dumps(body),headers={'Content-Type':'application/json'})
    assert response.status_code==422


def test_bad_body_shape_extra_and_size_denied(tmp_path):
    api=client(ReleaseStore(tmp_path/'deploy',allowed_source_roots=[tmp_path/'source']))
    for body in [[],{'model_id':[]},{'model_id':'AIR_PRES','values':[1,2,3],'path':'/etc/model.pkl'}]:
        assert api.post('/predict',json=body).status_code==422
    assert api.post('/predict',content=' '*17000,headers={'Content-Type':'application/json'}).status_code==413
    assert api.post('/predict',content='{"model_id":"AIR_PRES","model_id":"SALINITY"}',headers={'Content-Type':'application/json'}).status_code==422
    assert api.post('/predict',content='['*2000+'0'+']'*2000,headers={'Content-Type':'application/json'}).status_code==422


def test_remote_and_dns_host_forbidden(tmp_path):
    store=ReleaseStore(tmp_path/'deploy',allowed_source_roots=[tmp_path/'source'])
    assert TestClient(create_app(store),base_url='http://127.0.0.1:8011',client=('192.168.0.2',1)).get('/health').status_code==403
    assert client(store).get('/health',headers={'Host':'evil.example'}).status_code==403
    assert client(store).get('/health',headers={'Origin':'https://evil.example'}).status_code==403
    assert client(store).get('/health',headers={'Origin':'http://localhost:5174'}).status_code==200
    assert client(store).post('/predict',content='{}',headers={'Content-Type':'text/plain'}).status_code==415


def test_pending_and_stale_selection_are_blocked(tmp_path):
    store=ReleaseStore(tmp_path/'deploy',allowed_source_roots=[tmp_path/'source'])
    api=client(store)
    assert api.get('/health').status_code==200
    assert api.get('/readiness').json()['status']=='BLOCKED'
    body={'model_id':'AIR_PRES','values':[1,2,3],'expected_release_id':'one','expected_artifact_sha256':'0'*64}
    assert api.post('/predict',json=body).status_code==503
    manifest=candidate(tmp_path/'candidate',tmp_path/'source');store.register(tmp_path/'candidate')
    body=request_for(manifest);body['expected_release_id']='old'
    assert api.post('/predict',json=body).status_code==409
    body=request_for(manifest);body['expected_artifact_sha256']='0'*64
    assert api.post('/predict',json=body).status_code==409


def test_new_release_preserves_previous_and_invalid_cannot_switch(tmp_path):
    first=candidate(tmp_path/'first',tmp_path/'source')
    store=ReleaseStore(tmp_path/'deploy',allowed_source_roots=[tmp_path/'source']);store.register(tmp_path/'first')
    second=copy.deepcopy(first);second['release_id']='release-two';save(tmp_path/'first'/'release-manifest.json',second)
    store.register(tmp_path/'first')
    assert (tmp_path/'deploy/releases/release-one').is_dir()
    assert store.current()['manifest']['release_id']=='release-two'
    bad=copy.deepcopy(second);bad['release_id']='release-three';bad['models'][0]['artifact_relative_path']='../model.pkl';save(tmp_path/'first/release-manifest.json',bad)
    with pytest.raises(DevelopmentReleaseError,match='ALLOWLISTED'):store.register(tmp_path/'first')
    assert store.current()['manifest']['release_id']=='release-two'


@pytest.mark.parametrize('target',['model','membership','source'])
def test_changed_release_dependency_or_raw_source_blocks_serving(tmp_path,target):
    manifest=candidate(tmp_path/'candidate',tmp_path/'source')
    store=ReleaseStore(tmp_path/'deploy',allowed_source_roots=[tmp_path/'source']);store.register(tmp_path/'candidate')
    assert store.current()
    path={'model':tmp_path/'deploy/releases/release-one/models/AIR_PRES.json',
          'membership':tmp_path/'deploy/releases/release-one/memberships/AIR_PRES.jsonl',
          'source':tmp_path/'source/raw.parquet'}[target]
    path.write_bytes(path.read_bytes()+b' ')
    assert store.current() is None
    assert client(store).post('/predict',json=request_for(manifest)).status_code==503


def test_rehashed_wrong_raw_locator_is_rejected(tmp_path):
    manifest=candidate(tmp_path/'candidate',tmp_path/'source')
    spec=manifest['models'][0];path=tmp_path/'candidate'/spec['source_membership_relative_path']
    rows=[json.loads(line) for line in path.read_bytes().splitlines()]
    rows[0]['source']['row_index']=1;rows[0]['source']['locator']='parquet_row_group=0;row_index=1'
    path.write_bytes(b'\n'.join(canonical(r) for r in rows)+b'\n');sha=file_sha(path);spec['source_membership_sha256']=sha
    artifact_path=tmp_path/'candidate'/spec['artifact_relative_path'];artifact=json.loads(artifact_path.read_bytes());artifact['source_membership_sha256']=sha
    spec['artifact_sha256']=save(artifact_path,artifact);save(tmp_path/'candidate/release-manifest.json',manifest)
    sources={s['sha256']:Path(s['path']) for s in manifest['sources']}
    with pytest.raises(DevelopmentReleaseError,match='RAW_LITERAL'):
        verify_membership(path,sha,12,spec['membership_split_counts'],'AIR_PRES',sources,{})


def test_ridge_scale_and_receipt_metrics_cannot_be_forged(tmp_path):
    artifact={'schema_version':'raw-next-row-model-v1','variable_code':'AIR_PRES','input_lags':3,'selected_model':'RIDGE',
              'params':{'mean':[1,2,3],'scale':[1,0,1],'coefficients':[1,2,3],'intercept':0},
              'source_membership_sha256':'0'*64,'task':'NEXT_OBSERVED_ROW_FORECAST','native_clock_only':True,
              'unit':None,'timezone':None,'horizon_seconds':None,**DEV_FLAGS}
    with pytest.raises(DevelopmentReleaseError,match='RIDGE_PARAMS'):validate_artifact(artifact,'AIR_PRES')
    manifest=candidate(tmp_path/'candidate',tmp_path/'source');manifest['models'][0]['test_metrics']['RIDGE']['mae']=999
    save(tmp_path/'candidate/release-manifest.json',manifest)
    with pytest.raises(DevelopmentReleaseError,match='METRICS_MISMATCH'):validate_release(tmp_path/'candidate',[tmp_path/'source'])


def test_unsafe_source_root_and_physical_claims_rejected(tmp_path):
    manifest=candidate(tmp_path/'candidate',tmp_path/'source')
    with pytest.raises(DevelopmentReleaseError,match='SOURCE_FILE_UNVERIFIED'):validate_release(tmp_path/'candidate',[tmp_path/'elsewhere'])
    manifest['approved']=True;save(tmp_path/'candidate/release-manifest.json',manifest)
    with pytest.raises(DevelopmentReleaseError,match='FLAGS_REQUIRED'):validate_release(tmp_path/'candidate',[tmp_path/'source'])


def test_policies_selection_and_exact_ui_split_dependencies_are_required(tmp_path):
    manifest=candidate(tmp_path/'candidate',tmp_path/'source')
    store=ReleaseStore(tmp_path/'deploy',allowed_source_roots=[tmp_path/'source']);store.register(tmp_path/'candidate')
    assert (tmp_path/'deploy/releases/release-one/source-selection.json').is_file()
    assert (tmp_path/'deploy/releases/release-one/policies/AIR_PRES.json').is_file()
    manifest['models'][0]['split_counts']['TRAIN']=5;save(tmp_path/'candidate/release-manifest.json',manifest)
    with pytest.raises(DevelopmentReleaseError,match='UI_SPLIT_COUNTS'):validate_release(tmp_path/'candidate',[tmp_path/'source'])


def test_fixed_native_policy_and_pin_set_cannot_be_changed(tmp_path):
    manifest=candidate(tmp_path/'candidate',tmp_path/'source')
    spec=manifest['models'][0];policy_path=tmp_path/'candidate'/spec['policy_relative_path']
    policy=json.loads(policy_path.read_bytes());policy['native_periods']['TRAIN']['end_exclusive']='2026-07-20 00:00:00'
    spec['policy_sha256']=save(policy_path,policy)
    artifact_path=tmp_path/'candidate'/spec['artifact_relative_path'];artifact=json.loads(artifact_path.read_bytes());artifact['policy_sha256']=spec['policy_sha256']
    spec['artifact_sha256']=save(artifact_path,artifact);save(tmp_path/'candidate/release-manifest.json',manifest)
    with pytest.raises(DevelopmentReleaseError,match='FIXED_NATIVE_POLICY'):validate_release(tmp_path/'candidate',[tmp_path/'source'])
    manifest=candidate(tmp_path/'second',tmp_path/'source-two');manifest['pinned_dependencies'].pop()
    save(tmp_path/'second/release-manifest.json',manifest)
    with pytest.raises(DevelopmentReleaseError,match='PINNED_DEPENDENCIES'):validate_release(tmp_path/'second',[tmp_path/'source-two'])


def test_artifact_metrics_and_computed_pair_counts_must_match(tmp_path):
    manifest=candidate(tmp_path/'candidate',tmp_path/'source');spec=manifest['models'][0]
    artifact_path=tmp_path/'candidate'/spec['artifact_relative_path'];artifact=json.loads(artifact_path.read_bytes())
    artifact['test_metrics']['RIDGE']['mae']=123;spec['artifact_sha256']=save(artifact_path,artifact)
    for kind in ['training','eval']:
        path=tmp_path/'candidate'/spec[kind+'_receipt_relative_path'];receipt=json.loads(path.read_bytes());receipt['artifact_sha256']=spec['artifact_sha256'];spec[kind+'_receipt_sha256']=save(path,receipt)
    save(tmp_path/'candidate/release-manifest.json',manifest)
    with pytest.raises(DevelopmentReleaseError,match='EVALUATION_METRICS_REQUIRED'):validate_release(tmp_path/'candidate',[tmp_path/'source'])
    manifest=candidate(tmp_path/'second',tmp_path/'source-two');spec=manifest['models'][0]
    spec['pair_counts']['TEST']=2;save(tmp_path/'second/release-manifest.json',manifest)
    with pytest.raises(DevelopmentReleaseError,match='EXACT_SPLIT_OR_PAIR'):validate_release(tmp_path/'second',[tmp_path/'source-two'])
