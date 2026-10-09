"""Numerical/causal and stateful sample contracts; no live DB or source writes."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.services import ai_insights_sample as s
from app.api import routes_ai_insights_sample as routes


@pytest.fixture(autouse=True)
def isolated():
    s.reset_store_for_tests()
    yield
    s.reset_store_for_tests()


def session():
    context=s.context();packet=s.create_session(context['bootstrap_token'],'owned-create-0001')
    return packet['session_token'],packet['session_id']


def review(token,identity,case,action,key):
    current=s.detail(token,identity,case)
    return s.review(token,identity,case,action,'가상 근거 검토',current['revision'],current['recommendation_sha256'],key)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes.settings,'AI_INSIGHTS_SAMPLE_ENABLED',True,raising=False)
    monkeypatch.setattr(routes.settings,'ENVIRONMENT','test')
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as instance:yield instance


@pytest.mark.parametrize('scenario',[r[0] for r in s.SCENARIOS])
def test_fixed_membership_actual_fit_uses_only_past_and_declared_synthetic_facts(scenario):
    inputs=s.scenario_inputs(scenario);output=s._template()[scenario]
    assert {k:len(v) for k,v in inputs['membership'].items()}==dict(TRAIN=480,VALIDATION=168,TEST=280)
    assert len(inputs['rows'])==928 and len({r['row_id'] for r in inputs['rows']})==928
    assert all(datetime.fromisoformat(r['timestamp'])<=s.AS_OF for r in inputs['rows'])
    assert not set(inputs['membership']['TEST'])&{r['row_id'] for r in inputs['fit']['rows']}
    artifact=output['fitted_anomaly_artifact']['artifact']
    assert artifact['fit_data_sha256']==s.sha256(inputs['fit']['rows'])
    assert set(artifact['models'])=={'SPIKE','DRIFT'}
    assert all(v['status']=='FITTED' for v in artifact['models'].values())
    assert artifact['used_train_count']==480
    assert artifact['registered_models']==artifact['deployed_models']==0
    assert output['not_evaluated_row_count']==7
    assert output['anomaly_evaluation']['evaluated_count']==273
    assert output['forecast']['pair_counts']==dict(TRAIN=477,VALIDATION=165,TEST=277)
    selected=next(row for row in output['series'] if row['row_id']==output['selected_row_id'])
    assert output['selected_value']==selected['value']
    assert output['selected_prediction']==selected['prediction']
    assert output['selected_reference_value']==selected['reference_value']
    assert output['selected_observation']==selected['timestamp']
    assert output['forecast']['prediction_target_timestamp']=='2026-07-09T16:00:00+09:00'
    assert output['forecast']['prediction_is_observation'] is False


@pytest.mark.parametrize('scenario',[r[0] for r in s.SCENARIOS])
def test_independent_sklearn_oracle_train_only_validation_selection_and_common_test_pairs(scenario):
    inputs=s.scenario_inputs(scenario);report=s._template()[scenario]['forecast']
    values={r['row_id']:r['value'] for r in inputs['rows']}
    arrays={}
    for split,ids in inputs['membership'].items():
        arrays[split]=(np.asarray([[values[i] for i in ids[j-3:j]] for j in range(3,len(ids))]),
                       np.asarray([values[ids[j]] for j in range(3,len(ids))]))
    train,validation,test=arrays['TRAIN'],arrays['VALIDATION'],arrays['TEST']
    candidates=[]
    for alpha in (.01,.1,1.):
        model=make_pipeline(StandardScaler(),Ridge(alpha=alpha)).fit(*train)
        val=model.predict(validation[0]);mae=float(np.mean(abs(val-validation[1])))
        candidates.append((mae,alpha,model))
    best=min(candidates,key=lambda row:(row[0],row[1]))
    baseline=float(np.mean(abs(validation[0][:,-1]-validation[1])))
    assert report['selected_model']==('RIDGE' if best[0]<baseline else 'PERSISTENCE')
    assert report['selected_alpha']==best[1]
    assert report['artifact']['preprocessing_fit']=='TRAIN_ONLY'
    assert report['artifact']['parameters_fit']=='TRAIN_ONLY'
    assert report['artifact']['refit_after_selection'] is False
    np.testing.assert_allclose(report['artifact']['ridge_model']['mean'],best[2][0].mean_,atol=1e-12)
    np.testing.assert_allclose(report['artifact']['ridge_model']['scale'],best[2][0].scale_,atol=1e-12)
    np.testing.assert_allclose(report['artifact']['ridge_model']['coef'],best[2][1].coef_,atol=1e-10)
    preds=np.asarray([r['ridge'] for r in report['paired_test_predictions']])
    np.testing.assert_allclose(preds,best[2].predict(test[0]),atol=1e-10)
    assert report['test_metrics']['RIDGE']['mae']==pytest.approx(float(np.mean(abs(preds-test[1]))))
    assert report['test_metrics']['PERSISTENCE']['count']==report['test_metrics']['RIDGE']['count']==277
    for pair in report['paired_test_predictions']:
        assert all(i in inputs['membership']['TEST'] for i in pair['feature_row_ids'])
        assert pair['target_id'] in inputs['membership']['TEST']


def test_test_values_cannot_change_fitted_models_or_validation_selection():
    inputs=s.scenario_inputs('normal');original=s.calculate_scenario(inputs)
    changed=deepcopy(inputs)
    for row in changed['rows']:
        if row['row_id'] in set(changed['membership']['TEST']):row['value']+=50.
    for row in changed['test']['rows']:row['value']+=50.
    altered=s.calculate_scenario(changed)
    assert original['fitted_anomaly_artifact']==altered['fitted_anomaly_artifact']
    assert original['forecast']['artifact']==altered['forecast']['artifact']
    assert original['forecast']['validation_metrics']==altered['forecast']['validation_metrics']
    assert original['forecast']['test_metrics']!=altered['forecast']['test_metrics']


def test_future_test_edits_cannot_change_earlier_causal_anomaly_or_forecast_predictions():
    inputs=s.scenario_inputs('normal');original=s.calculate_scenario(inputs)
    changed=deepcopy(inputs)
    for rows in (changed['rows'],changed['test']['rows']):
        for row in rows:
            if datetime.fromisoformat(row['timestamp'])>=datetime.fromisoformat('2026-07-08T00:00:00+09:00'):row['value']+=100.
    altered=s.calculate_scenario(changed)
    before=lambda rows:[r for r in rows if r['timestamp']<'2026-07-08T00:00:00+09:00']
    assert before(original['series'])==before(altered['series'])


def test_injected_truth_metrics_and_environmental_condition_are_real_computations():
    template=s._template()
    spike=template['spike']['anomaly_evaluation'];drift=template['salinity-drift']['anomaly_evaluation']
    assert spike['tp']==8 and spike['fn']==0
    assert drift['tp']>=75 and drift['fn']>0  # delay/false negative is disclosed
    for key,case in template.items():
        metrics=case['anomaly_evaluation']
        assert sum(metrics[k] for k in ('tp','fp','fn','tn'))==metrics['evaluated_count']==273
        assert case['confidence_probability'] is None and case['uncertainty'] is None
        assert case['score']['kind'].endswith('NOT_PROBABILITY')
    normal=template['normal']['anomaly_evaluation']
    assert normal['tp']==0 and normal['recall'] is None and normal['fp']>0
    assert normal['false_positive_rate']==pytest.approx(normal['fp']/(normal['fp']+normal['tn']))
    environmental=template['high-temp-neighbor']['environment_evaluation']
    assert environmental['candidate'] and environmental['primary_value']>=26 and environmental['neighbor_value']>=26
    assert template['high-temp-neighbor']['anomaly_evaluation']['tp']==0
    inputs=s.scenario_inputs('high-temp-neighbor')
    for row in inputs['test']['rows']:row['reference']['value']-=10.
    assert not s.calculate_scenario(inputs)['environment_evaluation']['candidate']
    assert template['salinity-drift']['environment_evaluation']['status']=='NOT_APPLICABLE'


def test_sample_result_checksums_numeric_artifacts_and_no_operational_authority():
    token,identity=session()
    for packet in (s.overview(token,identity),s.detail(token,identity,'spike')):
        copy=deepcopy(packet);checksum=copy.pop('result_sha256')
        assert s.sha256(copy)==checksum
        assert packet['source']=='SAMPLE' and packet['approved'] is False
        assert packet['source_reads']==packet['operational_writes']==packet['model_registry_writes']==packet['final_qc_writes']==0
        json.dumps(packet,allow_nan=False)
    overview=s.overview(token,identity)
    assert overview['kpis']['analysis_report_count']==4 and overview['kpis']['review_report_ready_count']==0
    assert overview['kpis']['virtual_station_count']==4
    assert overview['kpis']['fitted_ridge_model_count']==12
    assert overview['kpis']['fitted_anomaly_modes_count']==8
    assert all(r['virtual'] and r['station_id'].startswith('AI-SAMPLE-') for r in overview['stations'])


def test_pending_approval_stop_then_explicit_resume_only_readies_sample_report():
    token,identity=session()
    with pytest.raises(s.SampleError,match='REPORT_REQUIRES'):s.report(token,identity,'spike')
    with pytest.raises(s.SampleError,match='WORKFLOW_GATE'):review(token,identity,'spike','RESUME','bad-resume-0001')
    approved=review(token,identity,'spike','APPROVE','approve-valid-0001')
    assert approved['workflow']['status']=='APPROVED' and approved['workflow']['blocked']
    assert approved['workflow']['downstream_executed'] is False and approved['workflow']['report_status']=='BLOCKED'
    with pytest.raises(s.SampleError,match='REPORT_REQUIRES'):s.report(token,identity,'spike')
    completed=review(token,identity,'spike','RESUME','resume-valid-0001')
    assert completed['workflow']['status']=='COMPLETED'
    result=s.report(token,identity,'spike')
    assert result['revision']==completed['revision'] and result['recommendation_sha256']==completed['recommendation_sha256']
    assert result['report']['delivered'] is False and result['report']['recipients']==[]
    assert result['report_sha256']==s.sha256(result['report'])
    assert result['markdown_sha256']==hashlib.sha256(result['markdown'].encode('utf-8')).hexdigest()
    assert 'TEST MAE' in result['markdown'] and 'FP' in result['markdown']
    assert result['model_registry_writes']==result['final_qc_writes']==result['training_queue_writes']==0


@pytest.mark.parametrize('action',['HOLD','REJECT'])
def test_hold_and_reject_never_resume_report(action):
    token,identity=session();packet=review(token,identity,'normal',action,'stop-action-0001')
    assert packet['workflow']['blocked'] and packet['workflow']['report_status']=='BLOCKED'
    with pytest.raises(s.SampleError,match='WORKFLOW_GATE'):review(token,identity,'normal','RESUME','stop-resume-0001')


def test_review_cas_hash_idempotency_and_reset_generation():
    token,identity=session();detail=s.detail(token,identity,'spike')
    args=(token,identity,'spike','APPROVE','샘플',detail['revision'],detail['recommendation_sha256'],'idem-review-0001')
    approved=s.review(*args);repeat=s.review(*args)
    assert repeat['idempotent_replay'] and repeat['revision']==approved['revision']
    with pytest.raises(s.SampleError,match='IDEMPOTENCY'):
        s.review(token,identity,'spike','REJECT','변경',1,detail['recommendation_sha256'],'idem-review-0001')
    with pytest.raises(s.SampleError,match='STALE_REVISION'):s.review(*args[:-1],'new-key-stale-0001')
    current=s.detail(token,identity,'spike')
    with pytest.raises(s.SampleError,match='RECOMMENDATION_CHANGED'):s.review(token,identity,'spike','RESUME','근거변조',current['revision'],'a'*64,'hash-wrong-0001')
    reset=s.reset(token,identity,approved['session_revision'],'reset-owned-0001')
    assert reset['generation']==2
    with pytest.raises(s.SampleError,match='RECOMMENDATION_CHANGED'):s.review(*args)
    assert s.detail(token,identity,'spike')['workflow']['status']=='PENDING'
    assert s.reset(token,identity,approved['session_revision'],'reset-owned-0001')['idempotent_replay']


def test_concurrent_same_review_is_applied_once():
    token,identity=session();d=s.detail(token,identity,'normal')
    args=(token,identity,'normal','APPROVE','가상 검토',1,d['recommendation_sha256'],'concurrent-0001')
    with ThreadPoolExecutor(max_workers=4) as pool:responses=list(pool.map(lambda _:s.review(*args),range(4)))
    assert all(r['revision']==2 for r in responses)
    assert sum(not r['idempotent_replay'] for r in responses)==1
    assert len(s.detail(token,identity,'normal')['workflow']['history'])==2


def test_tokens_cross_session_contexts_capacity_and_expiry(monkeypatch):
    first=s.context();second=s.context();a=s.create_session(first['bootstrap_token'],'independent-0001')
    b=s.create_session(second['bootstrap_token'],'independent-0001')
    assert a['session_id']!=b['session_id']
    with pytest.raises(s.SampleError):s.overview(a['session_token'],b['session_id'])
    with pytest.raises(s.SampleError):s.overview('ai-sample-token-비ASCII',a['session_id'])
    with pytest.raises(s.SampleError):s.create_session('qc-sample-bootstrap-fixture-not-live','foreign-context-0001')
    monkeypatch.setattr(s,'MAX_SESSIONS',2)
    with pytest.raises(s.SampleError,match='CAPACITY'):s.create_session(first['bootstrap_token'],'capacity-fail-0001')
    now=s.time.monotonic();monkeypatch.setattr(s.time,'monotonic',lambda:now+s.TTL_SECONDS+1)
    with pytest.raises(s.SampleError):s.overview(a['session_token'],a['session_id'])
    with pytest.raises(s.SampleError):s.create_session(first['bootstrap_token'],'expired-create-0001')


def test_action_and_bootstrap_capacity(monkeypatch):
    token,identity=session();monkeypatch.setattr(s,'MAX_ACTIONS',1)
    review(token,identity,'normal','COMMENT','cap-comment-0001')
    with pytest.raises(s.SampleError,match='CAPACITY'):review(token,identity,'normal','COMMENT','cap-comment-0002')
    monkeypatch.setattr(s,'MAX_BOOTSTRAPS',len(s._BOOTSTRAPS))
    with pytest.raises(s.SampleError,match='CAPACITY'):s.context()


@pytest.mark.parametrize('headers',[{'Authorization':'Bearer operational-secret'}, {'Cookie':'session=actual'}, {'Authorization':''}])
def test_api_rejects_operational_identities_even_context(client,headers):
    response=client.get('/api/ai-insights-sample/context',headers=headers)
    assert response.status_code==401 and not s._BOOTSTRAPS


def test_api_disabled_and_production_are_404(client,monkeypatch):
    monkeypatch.setattr(routes.settings,'AI_INSIGHTS_SAMPLE_ENABLED',False,raising=False)
    assert client.get('/api/ai-insights-sample/context').status_code==404
    monkeypatch.setattr(routes.settings,'AI_INSIGHTS_SAMPLE_ENABLED',True,raising=False)
    monkeypatch.setattr(routes.settings,'ENVIRONMENT','production')
    assert client.get('/api/ai-insights-sample/context').status_code==404


def test_api_real_session_flow_body_rejections_and_query_isolation(client):
    context=client.get('/api/ai-insights-sample/context');assert context.status_code==200
    assert context.headers['Cache-Control']=='no-store'
    root='/api/ai-insights-sample';headers={'X-AI-Sample-Token':context.json()['bootstrap_token']}
    response=client.post(root+'/sessions',headers=headers,json={'request_key':'api-start-0001'})
    assert response.status_code==200
    session=response.json();headers={'X-AI-Sample-Token':session['session_token']}
    path=root+'/sessions/'+session['session_id']+'/scenarios/spike'
    detail=client.get(path,headers=headers).json()
    assert client.get(path).status_code==401
    assert client.get(path,headers={'X-AI-Sample-Token':'qc-sample-token-fixture'}).status_code==401
    assert client.get(path+'?source=LIVE',headers=headers).status_code==422
    body=dict(action='APPROVE',comment='가상 검토',expected_revision=True,
        recommendation_sha256=detail['recommendation_sha256'],request_key='api-review-0001')
    assert client.post(path+'/review',headers=headers,json=body).status_code==422
    body['expected_revision']=detail['revision'];body['extra']='forbidden'
    assert client.post(path+'/review',headers=headers,json=body).status_code==422
    body.pop('extra');approved=client.post(path+'/review',headers=headers,json=body)
    assert approved.status_code==200 and approved.json()['workflow']['blocked']
    assert client.get(path+'/report',headers=headers).status_code==409
    body.update(action='RESUME',expected_revision=approved.json()['revision'],request_key='api-resume-0001')
    assert client.post(path+'/review',headers=headers,json=body).status_code==200
    assert client.get(path+'/report',headers=headers).status_code==200


def test_source_generator_does_not_read_files_or_real_source(monkeypatch):
    import pathlib
    def bomb(*args,**kwargs):raise AssertionError('real file access forbidden')
    monkeypatch.setattr(pathlib.Path,'read_bytes',bomb)
    generated=s.scenario_inputs('spike')
    assert len(generated['rows'])==928
