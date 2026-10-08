"""Synthetic faults and isolated contracts; no real approvals or runtime writes."""
import copy
from datetime import datetime,timedelta,timezone

import numpy as np
import pytest

from app.ml.anomaly_artifact import sha256,envelope
from app.services.anomaly_analysis import fit_analysis,analyze_series


def fixture(family="TEMP",modes=None):
    rng=np.random.default_rng(61)
    start=datetime(2020,1,1,tzinfo=timezone.utc)
    stamp=lambda i:(start+timedelta(minutes=i)).isoformat()
    scope={"station_id":"SYNTHETIC-STATION","sensor_id":"SYNTHETIC-PRIMARY","sensor_episode_id":"SYNTHETIC-EPISODE",
           "variable_code":family,"unit":"meter" if family=="TIDE" else "psu" if family=="SAL" else "degree_C"}
    source=lambda i:{"sha256":"a"*64,"locator":f"SYNTHETIC:row={i}"}
    evidence=[{"sha256":"b"*64,"locator":"SYNTHETIC-DOCUMENT-ONLY"}]
    facts={k:{"documented":True,"value":v,"evidence":evidence} for k,v in {
        "semantic":family,"unit":scope["unit"],"clock":"UTC_WITH_EXPLICIT_OFFSET","qc":"SYNTHETIC-USABLE-CODEBOOK",
        "sensor_episode":scope["sensor_episode_id"],"datum":"SYNTHETIC-DATUM"}.items()}
    for k in facts:facts[k].update(start=stamp(-1),end=stamp(2000))
    facts["semantic"]["variable_family"]=family
    facts["sensor_episode"]["physical_sensor_id"]=scope["sensor_id"]
    contract={"kind":"PREDICTED_TIDE" if family=="TIDE" else "INDEPENDENT_SENSOR","unit":scope["unit"],
        "station_id":scope["station_id"],"variable_code":family,"datum":"SYNTHETIC-DATUM","evidence":evidence,
        "sensor_id":"SYNTHETIC-REFERENCE","sensor_episode_id":"SYNTHETIC-REFERENCE-EPISODE",
        "effective_start":stamp(-1),"effective_end":stamp(2000),"qc_version":"SYNTHETIC-REF-QC",
        "qc_effective_start":stamp(-1),"qc_effective_end":stamp(2000),"model_training_end":stamp(-100)}
    contexts={k:{"applicable":True,"evidence":evidence} for k in ("BIOFOULING_CANDIDATE","SENSOR_DEGRADATION_CANDIDATE")}
    rows=[]
    for i in range(540):
        reference=20+np.sin(i*.3)*.8+np.sin(i*.075)*.4
        rows.append({"row_id":str(i),"timestamp":stamp(i),"available_at":stamp(i),"qc_available_at":stamp(i),"scope":scope,
            "value":float(reference+rng.normal(0,.015)),"qc_eligible":True,"source":source(i),
            "reference":{"value":float(reference),"timestamp":stamp(i),"available_at":stamp(i),"qc_available_at":stamp(i),
                "unit":scope["unit"],"station_id":scope["station_id"],"variable_code":family,
                "datum":"SYNTHETIC-DATUM","issued_at":stamp(i-1),"sensor_id":contract["sensor_id"],
                "sensor_episode_id":contract["sensor_episode_id"],"source":{"sha256":"c"*64,"locator":f"SYNTHETIC:reference={i}"},"qc_eligible":True}})
    base={"schema_version":"ocean-anomaly-series-1","scope":scope,"facts":facts,"reference_contract":contract,"candidate_context":contexts}
    fit={**copy.deepcopy(base),"as_of":stamp(380),"rows":copy.deepcopy(rows[:380])}
    test={**copy.deepcopy(base),"as_of":stamp(600),"rows":copy.deepcopy(rows[380:])}
    protocol={"schema_version":"ocean-anomaly-protocol-1","protocol_id":"SYNTHETIC","version":"synthetic-v1",
        "variable_family":family,"modes":modes or ["SPIKE","PERSISTENCE","DRIFT","BIOFOULING_CANDIDATE","SENSOR_DEGRADATION_CANDIDATE"],
        "cadence_seconds":60,"window_samples":8,"min_train_samples":50,"min_calibration_samples":50,
        "scale_floor":.001,"persistence_epsilon":.001,"calibration_quantile":.99,
        "periods":{"TRAIN":{"start":stamp(0),"end":stamp(220)},"CALIBRATION":{"start":stamp(220),"end":stamp(380)}},
        "membership_sha256":{"TRAIN":sha256([str(i) for i in sorted(range(220),key=lambda i:str(i))]),
                             "CALIBRATION":sha256(sorted(str(i) for i in range(220,380)))}}
    return fit,test,protocol


def fitted(family="TEMP",modes=None):
    fit,test,protocol=fixture(family,modes)
    result=fit_analysis(fit,protocol)
    assert result["status"]=="FITTED",result
    return fit,test,protocol,result["artifact"]


def results(report,mode):return [r for r in report["results"] if r["mode"]==mode]


def test_fit_is_reproducible_numeric_json_and_never_production():
    fit,_,policy,artifact=fitted()
    assert fit_analysis(fit,policy)["artifact"]==artifact
    assert artifact["artifact"]["approved"] is False
    assert artifact["artifact"]["production_eligible"] is False
    assert artifact["artifact"]["fit_data_sha256"]==sha256(fit["rows"])
    assert artifact["artifact"]["score_kind"].endswith("NOT_PROBABILITY")


def test_heldout_spikes_detected_with_bounded_false_positives():
    _,test,_,artifact=fitted(modes=["SPIKE"])
    healthy=analyze_series(test,artifact)
    evaluated=[r for r in results(healthy,"SPIKE") if r["result_status"]=="EVALUATED"]
    assert sum(r["assessment"]=="ANOMALY" for r in evaluated)/len(evaluated)<.06
    injected=copy.deepcopy(test)
    for index in (40,80,120):injected["rows"][index]["value"]+=4.
    report=analyze_series(injected,artifact)
    by_id={r["row_id"]:r for r in results(report,"SPIKE")}
    truth={injected["rows"][i]["row_id"] for i in (40,41,80,81,120,121)}
    assert all(by_id[row]["assessment"]=="ANOMALY" for row in truth)
    assert sum(r["assessment"]=="ANOMALY" and r["row_id"] not in truth for r in by_id.values())<=8


def test_temp_sal_drift_requires_paired_reference_and_is_candidate_not_cause():
    for family in ("TEMP","SAL"):
        _,test,_,artifact=fitted(family,["DRIFT","SENSOR_DEGRADATION_CANDIDATE"])
        for i,row in enumerate(test["rows"]):
            if i>=60:row["value"]+=(i-60)*.01
        report=analyze_series(test,artifact)
        assert all(r["assessment"]=="ANOMALY" for r in results(report,"DRIFT")[-40:])
        assert all(r["cause_attribution"]=="NOT_ESTABLISHED" and r["final_qc_changed"] is False for r in report["results"])
        assert report["registered_models"]==report["deployed_models"]==0


def test_persistence_and_biofouling_signals_need_review():
    _,test,_,artifact=fitted(modes=["PERSISTENCE","BIOFOULING_CANDIDATE"])
    for row in test["rows"][70:]:row["value"]=22.
    report=analyze_series(test,artifact)
    assert all(r["assessment"]=="ANOMALY" for r in results(report,"PERSISTENCE")[-50:])
    assert any(r["assessment"]=="ANOMALY" for r in results(report,"BIOFOULING_CANDIDATE")[-50:])
    assert report["source_authority"]=="DECLARED_DEVELOPMENT_CONTRACT"
    assert all(r["candidate_only"] for r in report["results"])


def test_tide_residual_compares_exact_time_unit_and_datum():
    _,test,_,artifact=fitted("TIDE",["TIDE_RESIDUAL"])
    test["rows"][20]["value"]+=1.
    report=analyze_series(test,artifact)
    assert results(report,"TIDE_RESIDUAL")[20]["assessment"]=="ANOMALY"
    for key,value in (("datum","different-datum"),("unit","centimeter"),("timestamp","2030-01-01T00:00:00Z")):
        changed=copy.deepcopy(test);changed["rows"][20]["reference"][key]=value
        row=results(analyze_series(changed,artifact),"TIDE_RESIDUAL")[20]
        assert row["result_status"]=="NOT_EVALUATED" and row["assessment"]=="UNKNOWN"


def test_future_observations_do_not_change_past_scores():
    _,test,_,artifact=fitted()
    report=analyze_series(test,artifact)
    future_changed=copy.deepcopy(test)
    for row in future_changed["rows"][100:]:row["value"]+=100.
    changed=analyze_series(future_changed,artifact)
    assert [r for r in report["results"] if int(r["row_id"])<480]==[r for r in changed["results"] if int(r["row_id"])<480]


def test_calibration_changes_thresholds_but_not_train_statistics():
    fit,_,policy,artifact=fitted()
    for row in fit["rows"][220:]:row["value"]+=.2
    changed=fit_analysis(fit,policy)["artifact"]["artifact"]
    assert changed["fitted"]==artifact["artifact"]["fitted"]
    assert changed["fit_data_sha256"]!=artifact["artifact"]["fit_data_sha256"]
    assert changed["models"]["DRIFT"]["threshold"]!=artifact["artifact"]["models"]["DRIFT"]["threshold"]


@pytest.mark.parametrize("key",["semantic","unit","clock","qc","sensor_episode"])
def test_missing_source_facts_not_fitted(key):
    fit,_,policy=fixture();del fit["facts"][key]
    assert fit_analysis(fit,policy)["status"]=="NOT_EVALUATED"


@pytest.mark.parametrize("mutation",["naive_clock","duplicate_time","other_sensor","future_fit_rows","changed_members","split_overlap","nonfinite"])
def test_invalid_fit_inputs_are_structured(mutation):
    fit,_,policy=fixture()
    if mutation=="naive_clock":fit["rows"][5]["timestamp"]="2020-01-01T00:05:00"
    elif mutation=="duplicate_time":fit["rows"][5]["timestamp"]=fit["rows"][4]["timestamp"]
    elif mutation=="other_sensor":fit["rows"][5]["scope"]={**fit["scope"],"sensor_id":"OTHER"}
    elif mutation=="future_fit_rows":fit["rows"][-1]["timestamp"]="2021-01-01T00:00:00Z"
    elif mutation=="changed_members":fit["rows"][5]["row_id"]="different"
    elif mutation=="split_overlap":policy["periods"]["CALIBRATION"]["start"]=policy["periods"]["TRAIN"]["start"]
    else:fit["rows"][5]["value"]=float("nan")
    assert fit_analysis(fit,policy)["status"]=="NOT_EVALUATED"


def test_test_cannot_reuse_train_source_or_fit_time():
    _,test,_,artifact=fitted()
    test["rows"][0]["source"]={"sha256":"a"*64,"locator":"SYNTHETIC:row=0"}
    assert analyze_series(test,artifact)["blockers"]==["FIT_TEST_SOURCE_RECORD_REUSE"]


def test_artifact_tamper_and_rehashed_threshold_forgery_are_rejected():
    _,test,_,artifact=fitted()
    artifact["artifact"]["fitted"]["delta_scale"]*=2
    assert analyze_series(test,artifact)["blockers"]==["ARTIFACT_HASH_MISMATCH"]
    _,test,_,artifact=fitted()
    artifact["artifact"]["models"]["SPIKE"]["threshold"]=1e10
    assert analyze_series(test,envelope(artifact["artifact"]))["blockers"]==["ARTIFACT_THRESHOLD_CALIBRATION_MISMATCH"]


def test_source_qc_delay_missing_value_and_gap_break_windows():
    _,test,_,artifact=fitted(modes=["SPIKE","PERSISTENCE","DRIFT"])
    test["rows"][20]["qc_available_at"]="2030-01-01T00:00:00Z"
    test["rows"][40]["value"]=None
    test["rows"][60]["timestamp"]="2020-01-01T07:20:30Z"
    test["rows"][60]["available_at"]=test["rows"][60]["timestamp"]
    test["rows"][60]["qc_available_at"]=test["rows"][60]["timestamp"]
    report=analyze_series(test,artifact)
    for mode in ("SPIKE","PERSISTENCE","DRIFT"):
        by_id={r["row_id"]:r for r in results(report,mode)}
        assert by_id["400"]["result_status"]=="NOT_EVALUATED"
        assert by_id["420"]["result_status"]=="NOT_EVALUATED"
        assert by_id["440"]["result_status"]=="NOT_EVALUATED"


def test_future_reference_qc_blocks_only_reference_modes():
    _,test,_,artifact=fitted(modes=["SPIKE","DRIFT"])
    test["rows"][20]["reference"]["qc_available_at"]="2030-01-01T00:00:00Z"
    report=analyze_series(test,artifact)
    assert results(report,"SPIKE")[20]["result_status"]=="EVALUATED"
    assert results(report,"DRIFT")[20]["result_status"]=="NOT_EVALUATED"


def test_output_availability_includes_reference_qc_and_past_window():
    _,test,_,artifact=fitted(modes=["DRIFT"])
    test["rows"][20]["reference"]["qc_available_at"]="2020-01-01T08:00:00Z"
    report=analyze_series(test,artifact)
    assert results(report,"DRIFT")[25]["available_at"]=="2020-01-01T08:00:00+00:00"


def test_reference_and_biofouling_context_absence_is_partial_not_invented():
    fit,_,policy=fixture();fit["candidate_context"]={}
    result=fit_analysis(fit,policy)
    assert result["status"]=="FITTED"
    assert result["artifact"]["artifact"]["models"]["BIOFOULING_CANDIDATE"]["status"]=="NOT_EVALUATED"
    fit,_,policy=fixture("TIDE",["SPIKE","TIDE_RESIDUAL"]);del fit["facts"]["datum"]
    result=fit_analysis(fit,policy)
    assert result["artifact"]["artifact"]["models"]["TIDE_RESIDUAL"]["reason"]=="COMMON_TIDE_DATUM_NOT_DOCUMENTED"


def test_loopback_api_needs_no_approval_and_never_connects_db():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes_anomaly_analysis import router
    app=FastAPI();app.include_router(router)
    fit,_,policy=fixture()
    client=TestClient(app,client=("127.0.0.1",12345))
    response=client.post("/api/anomaly-analysis/fit",json={"series":fit,"protocol":policy})
    assert response.status_code==200 and response.json()["approved"] is False
    remote=TestClient(app,client=("198.51.100.5",12345))
    assert remote.post("/api/anomaly-analysis/fit",json={"series":fit,"protocol":policy}).status_code==403


def test_reference_cell_cannot_reappear_as_later_primary_cell():
    fit,_,policy=fixture()
    fit["rows"][5]["source"]=copy.deepcopy(fit["rows"][0]["reference"]["source"])
    assert fit_analysis(fit,policy)["blockers"]==["DUPLICATE_SOURCE_RECORD_REUSE"]


def test_ref_cells_are_part_of_fit_test_leakage_gate():
    _,test,_,artifact=fitted()
    test["rows"][10]["reference"]["source"]={"sha256":"c"*64,"locator":"SYNTHETIC:reference=10"}
    assert analyze_series(test,artifact)["blockers"]==["FIT_TEST_SOURCE_RECORD_REUSE"]


def test_reference_station_and_variable_are_exact_not_assumed():
    _,test,_,artifact=fitted(modes=["DRIFT"])
    for key,value in (("station_id","OTHER"),("variable_code","OTHER")):
        changed=copy.deepcopy(test);changed["rows"][20]["reference"][key]=value
        assert results(analyze_series(changed,artifact),"DRIFT")[20]["reason"]=="REFERENCE_STATION_OR_VARIABLE_MISMATCH"


def test_current_unit_metadata_cannot_cover_unknown_historical_period():
    fit,_,policy=fixture();del fit["facts"]["unit"]["start"]
    report=fit_analysis(fit,policy)
    assert report["status"]=="NOT_EVALUATED"
    assert report["blockers"]==["MINIMUM_USABLE_TRAIN_SAMPLES_NOT_MET"]


def test_tide_hindcast_issued_after_target_is_not_prediction_evidence():
    _,test,_,artifact=fitted("TIDE",["TIDE_RESIDUAL"])
    test["rows"][20]["reference"]["issued_at"]="2020-01-01T08:00:00Z"
    assert results(analyze_series(test,artifact),"TIDE_RESIDUAL")[20]["reason"]=="TIDE_PREDICTION_NOT_AVAILABLE_CAUSALLY"


def test_normal_support_is_distinct_from_anomaly_rank():
    _,test,_,artifact=fitted(modes=["SPIKE"])
    for row in analyze_series(test,artifact)["results"]:
        if row["result_status"]=="EVALUATED":
            assert row["support_strength"]==(row["calibration_rank"] if row["assessment"]=="ANOMALY" else 1-row["calibration_rank"])


def test_temperature_unit_is_not_a_salinity_contract():
    fit,_,policy=fixture('SAL')
    fit['scope']['unit']='degree_C';fit['facts']['unit']['value']='degree_C'
    fit['reference_contract']['unit']='degree_C'
    for row in fit['rows']:
        row['scope']['unit']='degree_C';row['reference']['unit']='degree_C'
    assert 'UNIT_NOT_SUPPORTED_FOR_DECLARED_VARIABLE_FAMILY' in fit_analysis(fit,policy)['blockers']


def test_rehashed_invalid_numeric_artifact_is_blocked_without_divide_by_zero():
    _,test,_,artifact=fitted()
    artifact['artifact']['fitted']['delta_scale']=0
    assert analyze_series(test,envelope(artifact['artifact']))['blockers']==['ARTIFACT_NUMERIC_PARAMETER_INVALID']


def test_work_budget_blocks_large_windows_before_expensive_features(monkeypatch):
    from app.services import anomaly_analysis
    fit,_,policy=fixture()
    monkeypatch.setattr(anomaly_analysis,'MAX_WINDOW_WORK',100)
    assert fit_analysis(fit,policy)['blockers']==['CAUSAL_WINDOW_WORK_BUDGET_EXCEEDED']


def test_api_body_is_bounded_even_before_algorithm_contracts():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes_anomaly_analysis import router
    app=FastAPI();app.include_router(router)
    client=TestClient(app,client=('127.0.0.1',12345))
    response=client.post('/api/anomaly-analysis/fit',json={'series':{'padding':'x'*(4*1024*1024)},'protocol':{}})
    assert response.status_code==413


def test_kst_clock_representation_is_equivalent_not_implicitly_assumed():
    fit,test,policy=fixture()
    original=fit_analysis(fit,policy)['artifact']['artifact']['fitted']
    kst=timezone(timedelta(hours=9))
    for row in fit['rows']:
        for key in ('timestamp','available_at','qc_available_at'):
            row[key]=datetime.fromisoformat(row[key]).astimezone(kst).isoformat()
        for key in ('timestamp','available_at','qc_available_at','issued_at'):
            row['reference'][key]=datetime.fromisoformat(row['reference'][key]).astimezone(kst).isoformat()
    result=fit_analysis(fit,policy)
    assert result['status']=='FITTED'
    assert result['artifact']['artifact']['fitted']==original


def test_actual_anomaly_report_to_fusion_keeps_scope_time_and_nonprobability():
    from app.services.evidence_fusion import ai_evidence,fuse_evidence
    _,test,_,artifact=fitted(modes=['SPIKE'])
    test['rows'][40]['value']+=4.
    report=analyze_series(test,artifact)
    row=results(report,'SPIKE')[40]
    normalized=dict(row,scope=report['scope'],report_sha256=report['result_sha256'],artifact_sha256=report['artifact_sha256'])
    evidence=ai_evidence(normalized)
    scope={**report['scope'],'period_start':'2020-01-01T06:20:00Z','period_end':'2020-01-01T09:00:00Z','as_of':report['as_of']}
    fused=fuse_evidence(scope,[evidence])
    assert fused['recommendation']=='REVIEW_ANOMALY'
    assert fused['anomaly_support']==.25
    assert fused['accepted_evidence'][0]['source_sha256']==report['result_sha256']
    assert fused['accepted_evidence'][0]['provenance']['calibration_rank']==row['calibration_rank']
    assert fused['score_kind'].endswith('NOT_PROBABILITY')
    assert fused['definitive_qc'] is False
    wrong_scope=copy.deepcopy(evidence);wrong_scope['scope']['unit']='K'
    assert fuse_evidence(scope,[wrong_scope])['excluded_evidence'][0]['reason']=='EVIDENCE_SCOPE_MISSING_OR_MISMATCH'


def test_shared_environmental_change_does_not_become_confirmed_sensor_fault():
    _,test,_,artifact=fitted(modes=['DRIFT','SENSOR_DEGRADATION_CANDIDATE'])
    original=analyze_series(test,artifact)
    for row in test['rows'][40:]:
        row['value']+=2.;row['reference']['value']+=2.
    shifted=analyze_series(test,artifact)
    for before,after in zip(original['results'],shifted['results']):
        assert before['assessment']==after['assessment']
        assert after['cause_attribution']=='NOT_ESTABLISHED'
