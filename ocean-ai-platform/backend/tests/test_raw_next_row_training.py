import copy,hashlib,json
from datetime import datetime,timedelta
import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from app.services.raw_next_row_training import (canonical,digest,freeze_membership,train_frozen_rows,RawTrainingError,DEFAULT_PERIODS)


def fixture(tmp_path):
    rows=[]
    for split,start in [('TRAIN',datetime(2026,7,1)),('VALIDATION',datetime(2026,7,19)),('TEST',datetime(2026,7,25))]:
        for i in range(50):
            value=float(10+.4*i+np.sin(i/3));clock=(start+timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M:%S')
            rows.append({'row_id':split+str(i),'clock_raw':clock,'value_raw':str(value),'numeric_value':value,
                         'numeric_status':'FINITE','pair_eligible_numeric':True,'source':{'sha256':'a'*64,'row_group':0,'row_index':len(rows),'column':'OBS_VALUE'},'exclusion_reasons':[]})
    frozen=freeze_membership(rows,DEFAULT_PERIODS,tmp_path/'membership.jsonl')
    policy={'schema_version':'raw-next-row-training-policy-v1','task':'NEXT_OBSERVED_ROW_FORECAST','holdout_locked':True,
            'input_lags':3,'ridge_alphas':[.01,.1,1.,10.,100.],**frozen}
    return rows,policy


def test_actual_fit_has_train_only_scaler_and_independent_ridge_oracle(tmp_path):
    rows,policy=fixture(tmp_path);result=train_frozen_rows(rows,policy)
    values=np.array([r['numeric_value'] for r in rows]);x=np.array([values[i-2:i+1] for i in range(2,49)]);y=values[3:50]
    scale=StandardScaler().fit(x);model=Ridge(alpha=result['ridge_alpha']).fit(scale.transform(x),y)
    tx=np.array([values[i-2:i+1] for i in range(102,149)])
    prediction=model.predict(scale.transform(tx))
    assert np.max(np.abs(prediction-np.array([r['ridge'] for r in result['paired_test_predictions']])))<1e-11
    assert result['ridge_params']['mean']==pytest.approx(scale.mean_)
    assert result['pair_counts']=={'TRAIN':47,'VALIDATION':47,'TEST':47}
    assert result['parameters_fit']=='TRAIN_ONLY' and result['test_used_for_selection'] is False and result['refit_on_validation'] is False


def test_final_test_values_do_not_change_selection_or_parameters(tmp_path):
    rows,policy=fixture(tmp_path);before=train_frozen_rows(rows,policy)
    altered=copy.deepcopy(rows)
    for r in altered[100:]:r['numeric_value']+=999;r['value_raw']=str(r['numeric_value'])
    changed=copy.deepcopy(policy);changed['source_membership_sha256']=hashlib.sha256(b''.join(canonical(r)+b'\n' for r in altered)).hexdigest()
    after=train_frozen_rows(altered,changed)
    assert before['selected_model']==after['selected_model'] and before['ridge_params']==after['ridge_params']
    assert before['alpha_validation_candidates']==after['alpha_validation_candidates']
    assert before['test_metrics']!=after['test_metrics']


def test_missing_value_remains_in_native_order_and_excludes_all_four_affected_windows(tmp_path):
    rows,policy=fixture(tmp_path);rows[120].update(numeric_value=None,numeric_status='MISSING',pair_eligible_numeric=False,value_raw=None)
    policy['source_membership_sha256']=hashlib.sha256(b''.join(canonical(r)+b'\n' for r in rows)).hexdigest()
    result=train_frozen_rows(rows,policy)
    assert result['pair_counts']['TEST']==43
    ids=[r['target_id'] for r in result['paired_test_predictions']]
    assert 'TEST20' not in ids and 'TEST21' not in ids and 'TEST22' not in ids and 'TEST23' not in ids
    assert len(rows)==150 and policy['source_membership_count']==150


def test_irregular_missing_minute_interval_is_next_observed_row_without_fixed_cadence(tmp_path):
    rows,policy=fixture(tmp_path)
    for r in rows[125:]:r['clock_raw']=(datetime.strptime(r['clock_raw'],'%Y-%m-%d %H:%M:%S')+timedelta(minutes=8)).strftime('%Y-%m-%d %H:%M:%S')
    policy['source_membership_sha256']=hashlib.sha256(b''.join(canonical(r)+b'\n' for r in rows)).hexdigest()
    result=train_frozen_rows(rows,policy)
    assert result['pair_counts']['TEST']==47
    pair=next(r for r in result['paired_test_predictions'] if r['target_id']=='TEST25')
    assert pair['origin_clock_raw']=='2026-07-25 00:24:00' and pair['target_clock_raw']=='2026-07-25 00:33:00'


def test_duplicate_window_excluded_without_removing_original_membership_row(tmp_path):
    rows,policy=fixture(tmp_path);rows[120]['pair_eligible_numeric']=False;rows[120]['exclusion_reasons']=['AMBIGUOUS_DUPLICATE_NATIVE_CLOCK']
    policy['source_membership_sha256']=hashlib.sha256(b''.join(canonical(r)+b'\n' for r in rows)).hexdigest()
    result=train_frozen_rows(rows,policy);assert result['pair_counts']['TEST']==43 and len(rows)==150


@pytest.mark.parametrize('kind',['changed_bytes','unlocked','nonfinite_alpha','overlap','duplicate_row_id'])
def test_training_contract_corruption_is_blocked(tmp_path,kind):
    rows,policy=fixture(tmp_path)
    if kind=='changed_bytes':rows[0]['numeric_value']+=1
    if kind=='unlocked':policy['holdout_locked']=False
    if kind=='nonfinite_alpha':policy['ridge_alphas']=[float('inf')]
    if kind=='overlap':
        periods=copy.deepcopy(DEFAULT_PERIODS);periods['VALIDATION']=('2026-07-01 00:00:00','2026-07-25 00:00:00')
        with pytest.raises(RawTrainingError):freeze_membership(rows,periods,tmp_path/'corrupt.jsonl')
        return
    if kind=='duplicate_row_id':
        rows[50]['row_id']=rows[0]['row_id']
        with pytest.raises(RawTrainingError):freeze_membership(rows,DEFAULT_PERIODS,tmp_path/'corrupt.jsonl')
        return
    with pytest.raises(RawTrainingError):train_frozen_rows(rows,policy)


def release_fixture(tmp_path):
    from app.services.raw_next_row_training import immutable
    root=tmp_path/'parent';spec={};dependencies={}
    for name,relative_key,hash_key in [('model','artifact_relative_path','artifact_sha256'),('members','source_membership_relative_path','source_membership_sha256'),
                                      ('policy','policy_relative_path','policy_sha256'),('fit','training_receipt_relative_path','training_receipt_sha256'),
                                      ('eval','eval_receipt_relative_path','eval_receipt_sha256')]:
        relative=name+'.json';sha=immutable(root/relative,canonical({'kind':name,'unchanged':True}))
        spec.update({relative_key:relative,hash_key:sha});dependencies[relative]=sha
    selection_sha=immutable(root/'source-selection.json',canonical({'source_group':'GR_OBS_ST'}))
    dependencies['source-selection.json']=selection_sha
    manifest={'schema_version':'raw-forecast-release-v1','approved':False,'production_eligible':False,'nonoperational':True,'experimental':True,
              'models':[spec],'source_selection_relative_path':'source-selection.json','source_selection_sha256':selection_sha}
    manifest['release_id']=digest(manifest);immutable(root/'release-manifest.json',canonical(manifest))
    return root,manifest,dependencies


def test_republication_pins_all_dependency_bytes_and_keeps_parent_immutable(tmp_path):
    from app.scripts.publish_raw_training_release import republish
    from app.services.raw_next_row_training import hash_file
    parent,original,dependencies=release_fixture(tmp_path);before=(parent/'release-manifest.json').read_bytes()
    result=republish(parent,tmp_path/'v2');manifest=json.loads((tmp_path/'v2/release-manifest.json').read_bytes())
    assert result['release_id']!=original['release_id'] and manifest['dependency_contract_version']==2
    assert manifest['parent_release_id']==original['release_id'] and (parent/'release-manifest.json').read_bytes()==before
    assert {d['path']:d['sha256'] for d in manifest['pinned_dependencies']}==dependencies
    for relative,sha in dependencies.items():assert hash_file(tmp_path/'v2'/relative)==sha==hash_file(parent/relative)
    assert republish(parent,tmp_path/'v2')==result


@pytest.mark.parametrize('corruption',['changed_policy','escaped_path'])
def test_republication_rejects_changed_or_escaped_dependency_before_output(tmp_path,corruption):
    from app.scripts.publish_raw_training_release import republish
    parent,manifest,_=release_fixture(tmp_path)
    if corruption=='changed_policy':(parent/'policy.json').write_bytes(b'changed')
    else:
        manifest['models'][0]['policy_relative_path']='../policy.json';manifest.pop('release_id');manifest['release_id']=digest(manifest)
        (parent/'release-manifest.json').write_bytes(canonical(manifest))
    with pytest.raises(RawTrainingError):republish(parent,tmp_path/'v2')
    assert not (tmp_path/'v2').exists()
