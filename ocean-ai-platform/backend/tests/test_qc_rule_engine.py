"""Guide-equivalence and causal QC tests, with explicit synthetic metadata only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from app.services.qc_rule_engine import execute_rules, catalog, GUIDE_SHA256, KINDS, digest, to_fusion_evidence

REF = {"sha256": "a" * 64, "locator": "SYNTHETIC TEST EVIDENCE; NOT FIELD APPROVAL"}
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
CONTEXT = {"as_of": "2026-01-02T00:00:00+00:00", "executed_at": "2026-01-02T00:00:00+00:00"}


def row(value=10, minute=0, variable="AIR_TEMP", unit="degC", oid=None):
    return {"observation_id": oid or f"{variable}-{minute}", "station_id": "ST1", "sensor_id": "S1", "variable_code": variable,
        "unit": unit, "timestamp_utc": (START + timedelta(minutes=minute)).isoformat(), "available_at": (START + timedelta(minutes=minute, seconds=1)).isoformat(),
        "value": value, "source_facts": {"physical_sensor_id": "P1", "sensor_episode_id": "E1", "quantity_kind": catalog()["items"].get(variable, {}).get("quantity_kind", variable + "_SCALAR"),
            "clock_semantics": "EXPLICIT_TEST_UTC", "source_timezone_name": "UTC", "effective_start": "2025-01-01T00:00:00+00:00", "effective_end": "2027-01-01T00:00:00+00:00", "reference_datum": "EXPLICIT_TEST_ML", "evidence": deepcopy(REF)}}


def rule(kind, variable="AIR_TEMP", unit="degC", **parameters):
    return {"qc_rule_id": "TEST-" + kind, "rule_version": "TEST-SYNTHETIC-v1", "kind": kind,
        "parameters": {"variable_code": variable, "unit": unit, "quantity_kind": catalog()["items"][variable]["quantity_kind"], "missing_sentinels": [-999], "calendar_timezone": "UTC", "failure_flag": "3", **parameters},
        "provenance": {"guide_sha256": GUIDE_SHA256, "pdf_pages": [23, 81], "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION", "configuration_reference": deepcopy(REF), "conflict_resolution": deepcopy(REF)}}


def one(records, spec):
    return execute_rules(records, [spec], CONTEXT)["results"][-1]


def baseline():
    return {"station_id": "ST1", "sensor_id": "S1", "variable_code": "AIR_TEMP", "unit": "degC", "period_start": "2016-01-01T00:00:00+00:00", "period_end": "2025-01-31T23:59:59+00:00", "available_at": "2025-02-01T00:00:00+00:00", "month": 1,
        "calendar_timezone": "UTC", "source_episode_policy": "EXPLICIT_REVIEWED_REFERENCE", "years": list(range(2016, 2026)), "statistic": "MONTHLY_MEAN_STD", "sample_count": 100, "mean": 10, "std": 2, "min": 5, "max": 15, "evidence": deepcopy(REF), "qc_exclusion_evidence": deepcopy(REF)}


@pytest.mark.parametrize("kind", KINDS)
def test_all_twelve_have_real_pass_and_failure(kind):
    good, bad = [row()], [row()]
    params = {}
    if kind in {"WT", "DE"}:
        for target in (good[0], bad[0]): target["receive_evidence"] = deepcopy(REF)
        good[0]["received_at"] = "2026-01-01T00:00:01+00:00"
        if kind == "WT":
            bad[0]["received_at"] = "2025-12-31T23:59:59+00:00"
        else:
            params["max_delay_seconds"] = 3600
            bad[0]["received_at"] = "2026-01-01T02:00:00+00:00"
            bad[0]["available_at"] = bad[0]["received_at"]
    elif kind == "LO":
        params = {"method": "WGS84_RECTANGLE", "station_type": "BUOY", "latitude_min": 33, "latitude_max": 34, "longitude_min": 126, "longitude_max": 127}
        for r in (good[0], bad[0]):
            r["station_type"] = "BUOY"; r["location"] = {"latitude": 33.5, "longitude": 126.5, "coordinate_frame": "WGS84", "evidence": deepcopy(REF)}
        bad[0]["location"]["latitude"] = 35
    elif kind == "ER":
        params["sentinels"] = [-999]; bad[0]["value"] = -999
    elif kind == "GR":
        params = {"min": -50, "max": 40, "boundary": "CLOSED"}; bad[0]["value"] = 41
    elif kind == "GD":
        params = {"duration_seconds": 120, "interval_seconds": 60, "duration_boundary": "AT_LEAST"}
        good = [row(10 + i, i) for i in range(3)]; bad = [row(10, i) for i in range(3)]
    elif kind == "SP":
        params = {"max_delta": 1, "interval_seconds": 60, "difference": "LINEAR"}
        good = [row(10, 0), row(11, 1)]; bad = [row(10, 0), row(12, 1)]
    elif kind == "RL":
        good, bad = [row(5, variable="WIND_SPEED", unit="m/s")], [row(5, variable="WIND_SPEED", unit="m/s")]
        params = {"method": "GUST_GE_WIND_SPEED", "related_name": "gust", "related_variable_code": "WIND_GUST", "related_unit": "m/s"}
        for r, val in ((good[0], 6), (bad[0], 4)):
            related = row(val, variable="WIND_GUST", unit="m/s"); related["sensor_id"] = "GUST1"
            r["auxiliary"] = {"gust": related}; r["pairing"] = {"gust": "GUST1", "evidence": deepcopy(REF)}
    elif kind in {"RR", "SR", "ST"}:
        for r in (good[0], bad[0]): r["baseline"] = baseline()
        bad[0]["value"] = 20
        params = {"baseline_policy": "EXPLICIT_HISTORICAL_EXTREMES", "limit_method": "EXACT_EXTREMES", "boundary": "CLOSED", "std_multiplier": 3}
    elif kind == "PO":
        params = {"related_name": "power", "related_variable_code": "POWER_VOLTAGE", "minimum_voltage": 12}
        for r, val in ((good[0], 12), (bad[0], 11.99)):
            power = row(val, variable="POWER_VOLTAGE", unit="V"); power["sensor_id"] = "BAT1"
            r["auxiliary"] = {"power": power}; r["pairing"] = {"power": "BAT1", "evidence": deepcopy(REF)}
    spec = rule(kind, good[-1]["variable_code"], good[-1]["unit"], **params)
    g, b = one(good, spec), one(bad, spec)
    assert g["result_flag"] == "1", g
    assert b["result_flag"] in {"3", "4", "9"}, b
    assert not b["approved"] and b["analysis_only"]
    assert b["result_score"] is None


def test_catalog_is_exact_12_existing_not_10_proposal_and_15_item_matrix():
    cat = catalog()
    assert tuple(r["kind"] for r in cat["rules"]) == KINDS
    assert len(cat["items"]) == 15
    assert cat["guide"]["sha256"] == GUIDE_SHA256
    assert cat["guide"]["cover_edition"] == "2023.12"
    assert cat["items"]["TIDE"]["summary_profile"]["range_min"] == -300
    assert cat["items"]["TIDE"]["summary_profile"]["range_max"] == 1300
    assert cat["items"]["AIR_PRES"]["reference_unit"] == "hPa"
    assert cat["items"]["AIR_PRES"]["summary_profile"]["spike_interval_seconds_max_delta"] == [[60, 2], [1800, 8.6]]
    assert "GD" not in cat["items"]["SOLAR_RADIATION"]["applicable_rules"]
    assert "GD" in cat["items"]["SUNSHINE"]["applicable_rules"]
    assert "ST" not in cat["items"]["TIDE"]["applicable_rules"]


@pytest.mark.parametrize("variable", list(catalog()["items"]))
def test_appendix1_range_sentinel_and_inclusive_boundaries(variable):
    item = catalog()["items"][variable]; cfg = item["summary_profile"]; unit = item["reference_unit"]
    gr = rule("GR", variable, unit, min=cfg["range_min"], max=cfg["range_max"], boundary="CLOSED", missing_sentinels=cfg["missing_sentinels"])
    for val in (cfg["range_min"], cfg["range_max"]):
        assert one([row(val, variable=variable, unit=unit)], gr)["result_flag"] == "1"
    assert one([row(cfg["range_max"] + .1, variable=variable, unit=unit)], gr)["result_flag"] == "4"
    missing = one([row(cfg["missing_sentinels"][0], variable=variable, unit=unit)], gr)
    assert missing["evaluation_status"] == "MISSING" and missing["result_flag"] == "9"


@pytest.mark.parametrize("mutate,reason", [
    (lambda rs: rs[0].update(timestamp_utc="2026-01-01T00:00:00"), "AWARE_TIMESTAMP_REQUIRED"),
    (lambda rs: rs[0].update(unit=None), "EXACT_SCOPE_AND_UNIT_REQUIRED"),
    (lambda rs: rs[0].update(available_at="2027-01-01T00:00:00Z"), "INPUT_NOT_AVAILABLE_AS_OF"),
    (lambda rs: rs[0].update(available_at="2025-12-31T23:59:59Z"), "INPUT_AVAILABLE_BEFORE_OBSERVED_CLOCK"),
    (lambda rs: rs[0].update(source_facts=None), "SOURCE_FACTS_REQUIRED"),
    (lambda rs: rs[0]["source_facts"].update(quantity_kind="SIGNED_RADIAL"), "SOURCE_QUANTITY_KIND_MISMATCH"),
    (lambda rs: rs[0].update(value=True), "FINITE_NUMERIC_VALUE_REQUIRED"),
])
def test_missing_unknown_and_signed_speed_are_not_good(mutate, reason):
    records = [row()]; mutate(records)
    result = one(records, rule("GR", min=-50, max=40, boundary="CLOSED"))
    assert result["result_flag"] == "NOT_EVALUATED"
    assert result["result_reason"] == reason
    assert to_fusion_evidence(result)["support_strength"] == 0


@pytest.mark.parametrize("mutation,reason", [
    (lambda rs: rs[1].update(timestamp_utc=rs[0]["timestamp_utc"]), "INPUT_INTERVAL_GAP_DUPLICATE_OR_REVERSED"),
    (lambda rs: rs[1].update(timestamp_utc="2026-01-01T00:04:00Z", available_at="2026-01-01T00:04:01Z"), "INPUT_INTERVAL_GAP_DUPLICATE_OR_REVERSED"),
    (lambda rs: rs[0].update(value=None), "MISSING_VALUE_IN_WINDOW"),
    (lambda rs: rs[0].update(value=-999), "MISSING_SENTINEL_IN_WINDOW"),
    (lambda rs: rs[0]["source_facts"].update(sensor_episode_id="OLD"), "SOURCE_SCOPE_OR_EPISODE_CHANGED"),
    (lambda rs: rs[0].update(unit="K"), "SOURCE_SCOPE_OR_EPISODE_CHANGED"),
])
def test_temporal_checks_do_not_cross_gap_missing_or_episode(mutation, reason):
    records = [row(10, 0), row(15, 1)]; mutation(records)
    result = one(records, rule("SP", interval_seconds=60, max_delta=1, difference="LINEAR"))
    assert result["evaluation_status"] == "NOT_EVALUATED" and result["result_reason"] == reason


def test_flat_elapsed_duration_and_equality_selection():
    records = [row(10, i) for i in range(4)]
    strict = rule("GD", duration_seconds=120, interval_seconds=60, duration_boundary="GREATER_THAN")
    assert one(records[:3], strict)["result_reason"] == "INSUFFICIENT_CAUSAL_WINDOW"
    assert one(records, strict)["result_flag"] == "4"
    result = one(records, strict)
    assert len(result["provenance_json"]["input_observation_ids"]) == 4


@pytest.mark.parametrize("change,reason", [
    (lambda b: b.update(period_end="2026-01-01T00:00:00Z"), "FUTURE_OR_UNAVAILABLE_BASELINE"),
    (lambda b: b.update(available_at="2027-01-01T00:00:00Z"), "FUTURE_OR_UNAVAILABLE_BASELINE"),
    (lambda b: b.update(month=2), "SAME_MONTH_BASELINE_REQUIRED"),
    (lambda b: b.update(years=list(range(2017, 2026))), "TEN_PRIOR_YEARS_REQUIRED"),
    (lambda b: b.update(unit="K"), "BASELINE_SCOPE_OR_UNIT_MISMATCH"),
])
def test_statistical_baseline_cannot_leak_future_or_short_history(change, reason):
    r = row(); r["baseline"] = baseline(); change(r["baseline"])
    result = one([r], rule("ST", std_multiplier=3))
    assert result["result_reason"] == reason and result["result_flag"] == "NOT_EVALUATED"


def test_conflict_requires_explicit_evidence_and_raw_PR_is_unsupported():
    spec = rule("GR", min=-50, max=40, boundary="CLOSED")
    del spec["provenance"]["conflict_resolution"]
    assert one([row()], spec)["result_reason"] == "EVIDENCE_REFERENCE_REQUIRED"
    assert one([row()], rule("PR"))["result_reason"] == "UNSUPPORTED_RULE_KIND"


def test_circular_distance_wrap_and_auxiliary_availability_scope():
    r = row(359, variable="WAVE_DIRECTION", unit="degree")
    aux = row(1, variable="WIND_DIRECTION", unit="degree"); aux["sensor_id"] = "WD1"
    r["auxiliary"] = {"wind": aux}; r["pairing"] = {"wind": "WD1", "evidence": deepcopy(REF)}
    spec = rule("RL", "WAVE_DIRECTION", "degree", method="CIRCULAR_DIRECTION_DIFFERENCE", related_name="wind", related_variable_code="WIND_DIRECTION", related_unit="degree", max_delta=25)
    assert one([r], spec)["result_flag"] == "1"
    aux["available_at"] = "2027-01-01T00:00:00Z"
    assert one([r], spec)["result_reason"] == "INPUT_NOT_AVAILABLE_AS_OF"
    aux["available_at"] = r["available_at"]; aux["station_id"] = "ST2"
    assert one([r], spec)["result_reason"] == "RELATED_STATION_MISMATCH"


@pytest.mark.parametrize("field,value", [("parameters", []), ("provenance", []), ("parameters", {"min": []}), ("provenance", {"pdf_pages": {}})])
def test_malformed_nested_rule_is_structured_not_evaluated(field, value):
    spec = rule("GR", min=-50, max=40, boundary="CLOSED"); spec[field] = value
    assert one([row()], spec)["result_flag"] == "NOT_EVALUATED"


def test_content_hashes_are_reproducible_and_sensitive():
    spec = rule("SP", interval_seconds=60, max_delta=1, difference="LINEAR")
    records = [row(10, 0), row(11, 1)]
    first = one(records, spec)
    assert first == one(deepcopy(records), deepcopy(spec))
    records[0]["value"] = 9
    assert first["provenance_json"]["input_window_sha256"] != one(records, spec)["provenance_json"]["input_window_sha256"]
    spec["parameters"]["max_delta"] = 2
    assert first["provenance_json"]["rule_spec_sha256"] != one(records, spec)["provenance_json"]["rule_spec_sha256"]
    assert digest(first) == to_fusion_evidence(first)["source_sha256"]


def test_nonfinite_and_size_limit_are_rejected_without_json_nan():
    with pytest.raises(ValueError): execute_rules([row(float("nan"))], [rule("ER", sentinels=[-999])], CONTEXT)
    with pytest.raises(ValueError): execute_rules([row()] * 10001, [], CONTEXT)


@pytest.mark.parametrize("variable,source_unit,guide_unit,factor,value,guide_value,lo,hi", [
    ('TIDE','m','cm',100,1.0,100,-300,1300),
    ('AIR_PRES','Pa','hPa',.01,101300,1013,850,1060),
    ('CURRENT_SPEED','m/s','cm/s',100,1.2,120,0,300),
])
def test_explicit_si_to_guide_equivalence_preserves_input(variable,source_unit,guide_unit,factor,value,guide_value,lo,hi):
    original=row(value,variable=variable,unit=source_unit);frozen=deepcopy(original)
    spec=rule('GR',variable,guide_unit,min=lo,max=hi,boundary='CLOSED',missing_sentinels=[-9999],unit_conversion={'from':source_unit,'to':guide_unit,'scale':factor,'offset':0,'evidence':deepcopy(REF)})
    actual=one([original],spec);expected=one([row(guide_value,variable=variable,unit=guide_unit)],spec)
    assert actual['result_flag']==expected['result_flag']=='1'
    assert original==frozen and actual['input_value']==value and actual['scope']['unit']==source_unit
    assert actual['provenance_json']['evaluation_unit']==guide_unit
    assert actual['provenance_json']['input_normalization']['source_value']==value
    spec['parameters']['unit_conversion']['scale']=factor*10
    assert one([original],spec)['result_reason']=='UNIT_CONVERSION_FACTOR_MISMATCH'


def test_conversion_not_inferred_for_unknown_unit_or_signed_radial():
    spec=rule('GR','CURRENT_SPEED','cm/s',min=0,max=300,boundary='CLOSED')
    actual=row(1,variable='CURRENT_SPEED',unit='m/s')
    assert one([actual],spec)['result_reason']=='EXPLICIT_UNIT_CONVERSION_REQUIRED'
    spec['parameters']['unit_conversion']={'from':'m/s','to':'cm/s','scale':100,'offset':0,'evidence':deepcopy(REF)}
    actual['source_facts']['quantity_kind']='SIGNED_RADIAL'
    assert one([actual],spec)['result_reason']=='SOURCE_QUANTITY_KIND_MISMATCH'


def test_episode_end_is_exclusive_and_future_analysis_not_backdated():
    actual=row();actual['source_facts']['effective_end']=actual['timestamp_utc']
    assert one([actual],rule('GR',min=-50,max=40,boundary='CLOSED'))['result_reason']=='SOURCE_EPISODE_OUTSIDE_EFFECTIVE_PERIOD'
    result=one([row()],rule('GR',min=-50,max=40,boundary='CLOSED'))
    assert result['available_at']==CONTEXT['executed_at']
    assert result['provenance_json']['executed_at_utc']==CONTEXT['executed_at']


@pytest.mark.parametrize("variable", [v for v,item in catalog()['items'].items() if item['summary_profile']['spike_interval_seconds_max_delta']])
def test_appendix1_selected_spike_interval_threshold_equivalence(variable):
    item=catalog()['items'][variable];unit=item['reference_unit']
    for seconds,delta in item['summary_profile']['spike_interval_seconds_max_delta']:
        spec=rule('SP',variable,unit,interval_seconds=seconds,max_delta=delta,difference='LINEAR',missing_sentinels=item['summary_profile']['missing_sentinels'])
        spec['provenance']['profile_id']='APPENDIX1_SUMMARY_P81'
        base=item['summary_profile']['range_min']+5
        assert one([row(base,0,variable,unit),row(base+delta,seconds/60,variable,unit)],spec)['result_flag']=='1'
        assert one([row(base,0,variable,unit),row(base+delta+.001,seconds/60,variable,unit)],spec)['result_flag']=='3'


def test_claimed_guide_profile_requires_exact_original_parameters():
    spec=rule('GR','AIR_PRES','hPa',min=850,max=1060,boundary='CLOSED')
    spec['provenance']['profile_id']='APPENDIX1_SUMMARY_P81'
    assert one([row(1013,variable='AIR_PRES',unit='hPa')],spec)['result_flag']=='1'
    spec['parameters']['min']=700
    assert one([row(1013,variable='AIR_PRES',unit='hPa')],spec)['result_reason']=='GUIDE_SELECTED_PROFILE_PARAMETER_MISMATCH'


def test_time_diagnostic_can_flag_future_raw_clock_without_using_future_quantity():
    r=row();r.update(timestamp_utc='2026-01-02T01:00:00+00:00',received_at='2026-01-01T00:00:01+00:00',receive_evidence=deepcopy(REF))
    result=one([r],rule('WT'))
    assert result['result_flag']=='4' and result['evaluation_status']=='EVALUATED'
    assert one([r],rule('GR',min=-50,max=40,boundary='CLOSED'))['result_reason']=='INPUT_AVAILABLE_BEFORE_OBSERVED_CLOCK'


@pytest.mark.parametrize('field,bad',[('source_facts',['x']),('normalization',['x'])])
def test_malformed_earlier_window_objects_fail_structurally(field,bad):
    records=[row(10,0),row(12,1)];records[0][field]=bad
    result=one(records,rule('SP',interval_seconds=60,max_delta=1,difference='LINEAR'))
    assert result['evaluation_status']=='NOT_EVALUATED'


def test_month_and_year_use_explicit_source_calendar_without_utc_default():
    r=row();r.update(timestamp_utc='2025-12-31T18:00:00+00:00',available_at='2025-12-31T18:01:00+00:00')
    r['source_facts']['source_timezone_name']='Asia/Seoul';r['baseline']=baseline();r['baseline']['calendar_timezone']='Asia/Seoul'
    spec=rule('ST',std_multiplier=3,calendar_timezone='Asia/Seoul')
    assert one([r],spec)['result_flag']=='1' # local January2026, not UTC December2025
    spec['parameters']['calendar_timezone']='UTC'
    assert one([r],spec)['result_reason']=='EXPLICIT_COMMON_SOURCE_CALENDAR_REQUIRED'


def test_exact_episode_is_preserved_for_fusion_scope_gate():
    result=one([row()],rule('GR',min=-50,max=40,boundary='CLOSED'))
    assert result['scope']['sensor_episode_id']=='E1'
    assert to_fusion_evidence(result)['scope']['sensor_episode_id']=='E1'


def test_report_checksum_binds_flag_scope_and_full_provenance():
    report=execute_rules([row()],[rule('GR',min=-50,max=40,boundary='CLOSED')],CONTEXT)
    checksum=report.pop('result_sha256')
    assert checksum==digest(report)
    report['results'][0]['result_flag']='4'
    assert checksum!=digest(report)
