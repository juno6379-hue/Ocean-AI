import copy
import pytest
from app.services.evidence_fusion import fuse_evidence,validate_scope,FusionError,rule_evidence,ai_evidence

SCOPE={'station_id':'ST','sensor_id':'S1','variable_code':'AIR_PRES','unit':'hPa','period_start':'2025-01-01T00:00:00Z','period_end':'2025-01-01T00:10:00Z','as_of':'2025-01-01T00:20:00Z'}
def item(category='RULE',assessment='ANOMALY',**changes):
    kinds={'RULE':'RULE_ANALYSIS','AI':'ANOMALY_ANALYSIS','METADATA':'SENSOR_METADATA','OPERATION':'OPERATION_LOG','RAG':'DOCUMENT_CHUNK'}
    result={'category':category,'source_kind':kinds[category],'source_id':category+'-1','source_sha256':'a'*64,'locator':'row:'+category,
        'scope':{k:SCOPE[k] for k in ('station_id','sensor_id','variable_code','unit')},'event_at':'2025-01-01T00:01:00Z','available_at':'2025-01-01T00:02:00Z',
        'assessment':assessment,'support_strength':1.,'result_status':'EVALUATED','approved':True}
    result.update(changes);return result

def test_weighted_score_is_not_probability_and_no_approval():
    result=fuse_evidence(SCOPE,[item()])
    assert result['recommendation_score']==.30 and result['coverage_weight']==.30
    assert result['score_kind']=='WEIGHTED_EVIDENCE_SUPPORT_NOT_PROBABILITY'
    assert result['approved'] is False and result['accepted_evidence'][0]['approved'] is False
    assert 'confidence' not in result

def test_absence_is_unknown_not_normal():
    result=fuse_evidence(SCOPE,[])
    assert result['recommendation_score'] is None and result['recommendation']=='INSUFFICIENT_EVIDENCE'
    assert result['coverage_weight']==0 and len(result['missing_categories'])==5

def test_duplicate_sources_do_not_raise_score():
    original=item();duplicate=item(source_id='alternate')
    result=fuse_evidence(SCOPE,[original,duplicate]*25)
    assert result['duplicate_count']==49 and len(result['accepted_evidence'])==1
    assert result['recommendation_score']==.30
    assert fuse_evidence(SCOPE,[duplicate,original])==fuse_evidence(SCOPE,[original,duplicate])

def test_same_provenance_contradiction_is_quarantined():
    result=fuse_evidence(SCOPE,[item(),item(assessment='NORMAL')])
    assert result['recommendation_score'] is None and result['conflicts'][0]['kind']=='CONTRADICTORY_DUPLICATE_PROVENANCE'
    assert not result['accepted_evidence']

def test_independent_normal_anomaly_disagreement_is_visible():
    result=fuse_evidence(SCOPE,[item(),item('AI','NORMAL')])
    assert result['recommendation']=='REVIEW_CONFLICT' and result['normal_support']==.25

@pytest.mark.parametrize('change,reason',[
    ({'available_at':'2025-01-01T00:21:00Z'},'FUTURE_EVIDENCE'),
    ({'event_at':'2025-01-01T00:22:00Z','available_at':'2025-01-01T00:23:00Z'},'FUTURE_EVIDENCE'),
    ({'available_at':'2025-01-01T00:00:00Z'},'AVAILABLE_BEFORE_EVENT'),
    ({'available_at':'2025-01-01T00:02:00'},'EXPLICIT_OFFSET_CLOCK_REQUIRED'),
    ({'source_kind':'DOCUMENT_CHUNK'},'SOURCE_KIND_CATEGORY_MISMATCH'),
    ({'source_sha256':'short'},'EXACT_SOURCE_HASH_REQUIRED'),
    ({'support_strength':True},'SUPPORT_STRENGTH_INVALID'),
    ({'scope':{}},'EVIDENCE_SCOPE_MISSING_OR_MISMATCH'),
    ({'result_status':'NOT_EVALUATED'},'EVIDENCE_NOT_EVALUATED')])
def test_invalid_future_or_mixed_source_is_unscored(change,reason):
    result=fuse_evidence(SCOPE,[item(**change)])
    assert result['recommendation_score'] is None
    assert result['excluded_evidence'][0]['reason']==reason

def test_rag_error_differs_from_empty_retrieval_and_cosine_is_not_score():
    empty=fuse_evidence(SCOPE,[],{'RAG':{'status':'MISSING'}})
    failure=fuse_evidence(SCOPE,[],{'RAG':{'status':'ERROR','error_type':'TimeoutError'}})
    assert empty['coverage']['RAG']['status']=='MISSING' and failure['coverage']['RAG']['status']=='ERROR'
    contextual=item('RAG','CONTEXT',support_strength=0,similarity=.99)
    assert fuse_evidence(SCOPE,[contextual])['recommendation_score'] is None
    assert fuse_evidence(SCOPE,[contextual])['coverage_weight']==.15

def test_unit_and_episode_are_exact_and_typed_locator_preserved():
    scope=dict(SCOPE,sensor_episode_id='E1');e=item();e['scope']=dict(e['scope'],sensor_episode_id='E1');e['locator']={'row_index':1,'row_group':0}
    assert fuse_evidence(scope,[e])['accepted_evidence'][0]['locator']==e['locator']
    e['scope']['unit']='Pa'
    assert not fuse_evidence(scope,[e])['accepted_evidence']

@pytest.mark.parametrize('field,value',[('sensor_id',''),('period_end','2025-01-01T00:00:00Z'),('as_of','2024-12-31T00:00:00Z')])
def test_scope_must_be_exact_and_causal(field,value):
    with pytest.raises(FusionError):validate_scope(dict(SCOPE,**{field:value}))

def test_rule_and_ai_actual_report_adapters():
    scope={k:SCOPE[k] for k in ('station_id','sensor_id','variable_code','unit')}
    rule=rule_evidence({'observation_id':'O1','qc_rule_id':'R','rule_version':'1','result_flag':'3','evaluation_status':'EVALUATED',
        'scope':scope,'event_at':'2025-01-01T00:01:00Z','available_at':'2025-01-01T00:02:00Z','provenance_json':{'input_window_sha256':'b'*64}})
    assert fuse_evidence(SCOPE,[rule])['recommendation_score']==.15
    ai=ai_evidence({'row_id':'O1','mode':'SPIKE','result_status':'EVALUATED','assessment':'ANOMALY','support_strength':.8,'calibration_rank':.8,
        'scope':scope,'event_at':'2025-01-01T00:01:00Z','available_at':'2025-01-01T00:02:00Z','report_sha256':'c'*64,'artifact_sha256':'d'*64})
    result=fuse_evidence(SCOPE,[rule,ai]);assert result['recommendation_score']==.35
    assert ai['provenance']['calibration_rank']==.8


def test_normal_and_anomaly_at_different_observation_times_are_not_conflicting():
    normal=item('AI','NORMAL',event_at='2025-01-01T00:02:00Z',available_at='2025-01-01T00:03:00Z')
    result=fuse_evidence(SCOPE,[item(),normal])
    assert result['conflicts']==[] and result['recommendation']=='REVIEW_ANOMALY'
