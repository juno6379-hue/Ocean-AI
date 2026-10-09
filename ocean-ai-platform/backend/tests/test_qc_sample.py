"""Meaningful synthetic engine, gate, concurrency and ephemeral-state checks."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.api.routes_qc_sample import router
from app.services import qc_sample as sample


@pytest.fixture
def client(monkeypatch):
    sample.reset_store_for_tests()
    monkeypatch.setattr(settings,'QC_SAMPLE_ENABLED',True)
    monkeypatch.setattr(settings,'ENVIRONMENT','test')
    app=FastAPI();app.include_router(router)
    yield TestClient(app)
    sample.reset_store_for_tests()


def session(client,key='sample-create-1'):
    context=client.get('/api/qc-sample/context').json()
    response=client.post('/api/qc-sample/sessions',json={'request_key':key},headers={'X-QC-Sample-Token':context['bootstrap_token']})
    assert response.status_code==200,response.text
    return response.json()


def get(client,state,case_id=None):
    suffix='/cases/'+case_id if case_id else '/overview'
    response=client.get('/api/qc-sample/sessions/'+state['session_id']+suffix,headers={'X-QC-Sample-Token':state['session_token']})
    assert response.status_code==200,response.text
    return response.json()


def review(client,state,detail,action,key,comment='가상 근거 검토'):
    body=dict(action=action,comment=comment,expected_revision=detail['revision'],
              recommendation_sha256=detail['recommendation_sha256'],request_key=key)
    return client.post('/api/qc-sample/sessions/'+state['session_id']+'/cases/'+detail['case']['case_id']+'/review',
                       json=body,headers={'X-QC-Sample-Token':state['session_token']})


def test_actual_engine_normal_delay_null_gap_and_spike_range_are_distinct(client):
    state=session(client);overview=get(client,state)
    assert {row['scenario_id']:row['flag'] for row in overview['cases']}==dict(normal='1',late='3',missing='9',spike='4')
    assert {name:overview['summary'][name]['count'] for name in ('normal','suspect','bad','missing')}==dict(normal=1,suspect=1,bad=1,missing=1)
    assert sum(row['count'] for row in overview['flag_distribution'])==4
    assert sum(row['total'] for row in overview['quality_trend'])==244
    assert sum(row['total'] for row in overview['station_variable_matrix'])==244
    assert overview['counts']['planned_slots']==244 and overview['counts']['received_slots']==241
    assert overview['rule_qc_counts']['catalog_count']==12 and overview['rule_qc_counts']['result_count']==2928
    for case in overview['cases']:
        data=get(client,state,case['case_id']);rules={row['kind']:row for row in data['rules']}
        assert len(rules)==12 and data['ai']==dict(status='NOT_RUN',trained_model=False,result=None)
        assert data['provenance']['operational_writes']==0 and data['provenance']['model_training']==0
        assert all(row['analysis_only'] and row['approved'] is False for row in rules.values())
        assert all(datetime.fromisoformat(row['available_at'])<=datetime.fromisoformat(data['window']['as_of']) for row in data['series']['rows'])
        if case['scenario_id']=='normal':assert rules['GR']['result_flag']=='1' and rules['SP']['result_flag']=='1'
        if case['scenario_id']=='late':
            assert case['delay_seconds']==480 and rules['DE']['result_flag']=='3' and rules['DE']['threshold_value']==300
        if case['scenario_id']=='missing':
            gaps=[row for row in data['series']['rows'] if row['is_missing']]
            assert len(gaps)==3 and data['series']['received_slots']==58 and data['series']['missing_slots']==3
            assert all(row['value'] is None and row['rule_input_value']==-999 and row['received_time'] is None and not row['observed'] and not row['interpolated'] for row in gaps)
            assert rules['ER']['result_flag']=='9' and rules['ER']['result_reason']=='DECLARED_MISSING_SENTINEL'
            assert rules['DE']['result_flag']=='NOT_EVALUATED'
        if case['scenario_id']=='spike':
            assert case['value']==45 and rules['SP']['result_flag']=='3' and rules['GR']['result_flag']=='4'
            assert rules['GR']['threshold_value']==40 and rules['SP']['threshold_value']==1
    rr=next(row for row in overview['rule_qc_counts']['items'] if row['rule_id']=='RR')
    assert rr['full_test_evaluated_count']==0 and rr['missing_precheck_count']==3 and rr['sample_configured'] is False


def test_review_stops_until_approved_then_explicit_resume_and_counts_align(client):
    state=session(client);case=get(client,state)['cases'][3];detail=get(client,state,case['case_id'])
    assert detail['workflow']['status']=='PENDING' and detail['workflow']['blocked']
    assert review(client,state,detail,'RESUME','blocked-resume-1').status_code==409
    approved=review(client,state,detail,'APPROVE','approved-request-1').json()
    assert approved['workflow']['status']=='APPROVED' and approved['workflow']['blocked']
    assert not approved['workflow']['downstream_executed'] and approved['approved'] is False
    assert get(client,state)['summary']['completed']['count']==0
    completed=review(client,state,approved,'RESUME','resume-request-1').json()
    assert completed['workflow']['status']=='COMPLETED' and completed['workflow']['downstream_executed']
    assert not completed['workflow']['blocked'] and completed['workflow']['definitive_qc'] is False
    assert [row['to_state'] for row in completed['workflow']['history']][-2:]==['RESUMING','COMPLETED']
    overview=get(client,state)
    assert overview['summary']['pending']['count']==3 and overview['summary']['completed']['count']==1
    assert next(row for row in overview['review_queue']['rows'] if row['case_id']==case['case_id'])['review_status']=='COMPLETED'
    assert get(client,state,case['case_id'])['workflow']['status']=='COMPLETED'


def test_atomic_review_same_revision_applies_once_and_retry_is_idempotent(client):
    state=session(client);detail=get(client,state,get(client,state)['cases'][0]['case_id'])
    def run(index):return review(client,state,detail,'APPROVE','concurrent-request-'+str(index)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(run,(1,2)))
    assert sorted(codes)==[200,409]
    fresh=get(client,state,detail['case']['case_id']);assert fresh['revision']==2
    assert len(fresh['workflow']['history'])==2


def test_payload_hash_revision_key_and_comment_fail_without_mutation(client):
    state=session(client);detail=get(client,state,get(client,state)['cases'][0]['case_id'])
    assert review(client,state,detail,'APPROVE','comment-request-1','   ').status_code==422
    wrong=deepcopy(detail);wrong['recommendation_sha256']='0'*64
    assert review(client,state,wrong,'APPROVE','hash-request-1').status_code==409
    bad=deepcopy(detail);bad['revision']=2
    assert review(client,state,bad,'APPROVE','revision-request-1').status_code==409
    response=review(client,state,detail,'COMMENT','comment-request-2');assert response.status_code==200
    retry=review(client,state,detail,'COMMENT','comment-request-2');assert retry.status_code==200 and retry.json()['idempotent_replay']
    assert review(client,state,detail,'APPROVE','comment-request-2').status_code==409
    fresh=get(client,state,detail['case']['case_id']);assert fresh['revision']==2 and fresh['workflow']['status']=='PENDING'


def test_reset_changes_generation_authority_and_preserves_other_session(client):
    one,two=session(client,'create-session-1'),session(client,'create-session-2')
    first,second=get(client,one)['cases'][0],get(client,two)['cases'][0]
    assert first['recommendation_sha256']!=second['recommendation_sha256']
    old=get(client,one,first['case_id'])
    reset=client.post('/api/qc-sample/sessions/'+one['session_id']+'/reset',json=dict(expected_session_revision=1,request_key='reset-request-1'),headers={'X-QC-Sample-Token':one['session_token']})
    assert reset.status_code==200 and reset.json()['generation']==2
    assert reset.json()['session_history'][-1]['action']=='RESET_SESSION'
    assert review(client,one,old,'APPROVE','old-authority-1').status_code==404
    fresh=get(client,one)['cases'][0]
    assert fresh['case_id']!=first['case_id'] and fresh['recommendation_sha256']!=first['recommendation_sha256']
    assert get(client,two)['generation']==1 and get(client,two)['cases'][0]==second


def test_expiry_capacity_and_server_restart_are_ephemeral(client,monkeypatch):
    monkeypatch.setattr(sample,'MAX_SESSIONS',1)
    state=session(client)
    context=client.get('/api/qc-sample/context').json()
    headers={'X-QC-Sample-Token':context['bootstrap_token']}
    assert client.post('/api/qc-sample/sessions',json={'request_key':'second-session-1'},headers=headers).status_code==429
    then=sample.time.monotonic()+sample.TTL_SECONDS+1
    monkeypatch.setattr(sample.time,'monotonic',lambda:then)
    assert client.get('/api/qc-sample/sessions/'+state['session_id']+'/overview',headers={'X-QC-Sample-Token':state['session_token']}).status_code==401
    fresh=session(client,'second-session-1');sample.reset_store_for_tests()
    assert client.get('/api/qc-sample/sessions/'+fresh['session_id']+'/overview',headers={'X-QC-Sample-Token':fresh['session_token']}).status_code==401


def test_creation_idempotency_is_bound_to_each_bootstrap_context(client):
    one=client.get('/api/qc-sample/context').json();two=client.get('/api/qc-sample/context').json()
    assert one['bootstrap_token']!=two['bootstrap_token']
    def create(context):
        return client.post('/api/qc-sample/sessions',json=dict(request_key='public-identical-request'),
                           headers={'X-QC-Sample-Token':context['bootstrap_token']})
    a,b=create(one).json(),create(two).json()
    assert a['session_id']!=b['session_id'] and a['session_token']!=b['session_token']
    assert create(one).json()['session_id']==a['session_id'] and create(two).json()['session_id']==b['session_id']
    assert client.get('/api/qc-sample/sessions/'+a['session_id']+'/overview',headers={'X-QC-Sample-Token':b['session_token']}).status_code==401


def test_bootstrap_expiry_and_capacity_are_bounded_without_revoking_sessions(client,monkeypatch):
    monkeypatch.setattr(sample,'MAX_BOOTSTRAPS',1)
    first=client.get('/api/qc-sample/context').json()
    state=client.post('/api/qc-sample/sessions',json=dict(request_key='bootstrap-bound-1'),headers={'X-QC-Sample-Token':first['bootstrap_token']}).json()
    assert client.get('/api/qc-sample/context').status_code==429
    then=sample.time.monotonic()+sample.BOOTSTRAP_TTL_SECONDS+1
    monkeypatch.setattr(sample.time,'monotonic',lambda:then)
    expired=client.post('/api/qc-sample/sessions',json=dict(request_key='bootstrap-bound-2'),headers={'X-QC-Sample-Token':first['bootstrap_token']})
    assert expired.status_code==401
    assert get(client,state)['session_id']==state['session_id']
    assert client.get('/api/qc-sample/context').status_code==200


@pytest.mark.parametrize('environment',['production','staging','DEV'])
def test_all_routes_fail_closed_outside_allowed_environment(client,monkeypatch,environment):
    monkeypatch.setattr(settings,'ENVIRONMENT',environment)
    assert client.get('/api/qc-sample/context').status_code==404
    assert client.post('/api/qc-sample/sessions',json={'request_key':'denied-request-1'}).status_code==404


def test_packet_hashes_and_returns_are_independent_copies(client):
    state=session(client);overview=get(client,state);detail=get(client,state,overview['cases'][0]['case_id'])
    for packet in (state,overview,detail):
        sha=packet.pop('result_sha256');assert sample.digest(packet)==sha
        assert packet['is_sample'] and packet['source']=='SAMPLE' and packet['production_writes']==0
    direct=sample.detail(state['session_token'],state['session_id'],overview['cases'][0]['case_id'])
    direct['series']['rows'][0]['value']=999;direct['workflow']['history'].clear()
    again=sample.detail(state['session_token'],state['session_id'],overview['cases'][0]['case_id'])
    assert again['series']['rows'][0]['value']!=999 and len(again['workflow']['history'])==1
    assert re.fullmatch(r'qc-sample-session-[A-Za-z0-9_-]+',state['session_id'])
