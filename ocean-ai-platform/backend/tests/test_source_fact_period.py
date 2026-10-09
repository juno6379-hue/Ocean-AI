"""Source-period contracts, with synthetic inputs and no fitting/DB mutations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from app.services.qc_analysis_readiness import fact_period, FactPeriodError, inspect_source_inputs
from app.services.anomaly_analysis import _rows, source_requirements
from app.services.qc_rule_engine import _record, NotEvaluated, implementation_hashes
from app.ml.anomaly_artifact import fingerprint
from test_anomaly_analysis import fixture
from test_qc_rule_engine import row as rule_row, CONTEXT


def declared():
    series,_,_=fixture()
    series['rows']=series['rows'][:1]
    return series


def readiness_rejected(series):
    report=source_requirements(series)
    assert report['status']=='NOT_EVALUATED'
    assert report['training_executed'] is False
    assert report['approved'] is report['production_eligible'] is False
    return report


def test_canonical_engine_input_is_ready_without_fitting_or_approval():
    series,_,_=fixture()
    before=deepcopy(series)
    assert len(_rows(series))==380
    assert not any(r['errors'] for r in _rows(series))
    assert inspect_source_inputs(series)['blocker_counts']=={}
    report=source_requirements(series)
    assert report['status']=='CONDITIONAL_INPUT_READY'
    assert report['training_executed'] is False
    assert report['source_authority']=='DECLARED_DEVELOPMENT_CONTRACT'
    assert report['approved'] is report['production_eligible'] is False
    assert series==before


@pytest.mark.parametrize('kind',['alias_only','identical_alias','conflicting_alias','partial_alias'])
def test_anomaly_period_never_falls_back_to_or_selects_an_ambiguous_alias(kind):
    series=declared();fact=series['facts']['unit']
    if kind=='alias_only':
        fact['effective_start']=fact.pop('start');fact['effective_end']=fact.pop('end')
    elif kind=='identical_alias':fact.update(effective_start=fact['start'],effective_end=fact['end'])
    elif kind=='conflicting_alias':fact.update(effective_start='2019-01-01T00:00:00Z',effective_end='2030-01-01T00:00:00Z')
    else:fact['effective_start']=fact['start']
    assert _rows(series)[0]['errors']
    readiness_rejected(series)


def test_anomaly_rule_and_readiness_agree_on_inclusive_start_and_exclusive_end_to_microsecond():
    series=declared();point=series['rows'][0]['timestamp'];instant=datetime.fromisoformat(point)
    sample=rule_row();sample['timestamp_utc']=point;sample['available_at']=point
    runtime={'as_of':datetime.fromisoformat(series['as_of'])}
    for delta,accepted in [(timedelta(0),False),(timedelta(microseconds=1),True)]:
        end=(instant+delta).isoformat()
        series['facts']['unit'].update(start=point,end=end)
        sample['source_facts'].update(effective_start=point,effective_end=end)
        rows=_rows(series)
        assert (not rows[0]['errors']) is accepted
        assert (source_requirements(series)['status']=='CONDITIONAL_INPUT_READY') is accepted
        if accepted:assert _record(sample,runtime)==instant
        else:
            with pytest.raises(NotEvaluated):_record(sample,runtime)
    # A valid interval whose end is exactly the observed instant still excludes it.
    series['facts']['unit'].update(start=(instant-timedelta(seconds=1)).isoformat(),end=point)
    sample['source_facts'].update(effective_start=(instant-timedelta(seconds=1)).isoformat(),effective_end=point)
    assert 'UNIT_CONTRACT_OUTSIDE_EFFECTIVE_INTERVAL' in _rows(series)[0]['errors']
    readiness_rejected(series)
    with pytest.raises(NotEvaluated,match='SOURCE_EPISODE_OUTSIDE_EFFECTIVE_PERIOD'):_record(sample,runtime)


def test_explicit_offset_equivalence_preserves_instants_without_inferring_a_native_timezone():
    series=declared();series['facts']['unit'].update(start='2020-01-01T09:00:00+09:00',end='2020-01-01T09:00:00.000001+09:00')
    assert _rows(series)[0]['errors']==[]
    assert source_requirements(series)['status']=='CONDITIONAL_INPUT_READY'
    assert series['rows'][0]['timestamp']=='2020-01-01T00:00:00+00:00'


@pytest.mark.parametrize('changes',[
    {'start':None},{'end':None},{'start':'2020-01-01 00:00:00'},
    {'end':'2020-01-01T00:01:00'}, {'start':'2020-02-30T00:00:00Z'},
    {'start':'2020-01-02T00:00:00Z','end':'2020-01-01T00:00:00Z'},
    {'start':'2020-01-01T00:00:00Z','end':'2020-01-01T00:00:00Z'},
    {'start':'0001-01-01T00:00:00+23:59'},
    {'end':'9999-12-31T23:59:59-23:59'},
])
def test_invalid_unknown_reversed_and_empty_periods_are_not_ready(changes):
    series=declared();series['facts']['clock'].update(changes)
    assert _rows(series)[0]['errors']
    readiness_rejected(series)


@pytest.mark.parametrize('key',['available_at','version_available_at'])
def test_metadata_version_availability_is_checked_and_propagated_to_analysis_availability(key):
    series=declared();fact=series['facts']['qc'];fact[key]=series['as_of']
    assert _rows(series)[0]['errors']==[]
    assert _rows(series)[0]['available']==datetime.fromisoformat(series['as_of'])
    assert source_requirements(series)['status']=='CONDITIONAL_INPUT_READY'
    fact[key]=(datetime.fromisoformat(series['as_of'])+timedelta(microseconds=1)).isoformat()
    assert 'QC_CONTRACT:FACT_VERSION_NOT_AVAILABLE_AS_OF' in _rows(series)[0]['errors']
    readiness_rejected(series)
    fact[key]=series['as_of'].split('+')[0]
    assert 'QC_CONTRACT:FACT_AVAILABILITY_OFFSET_REQUIRED' in _rows(series)[0]['errors']
    readiness_rejected(series)


@pytest.mark.parametrize('field',['station_id','sensor_id','variable_code','unit','sensor_episode_id'])
def test_explicit_fact_scope_and_source_row_scope_must_match_exactly(field):
    series=declared();series['facts']['sensor_episode']['scope']={**series['scope'],field:'UNRELATED'}
    assert 'SENSOR_EPISODE_CONTRACT:FACT_EXACT_SCOPE_MISMATCH' in _rows(series)[0]['errors']
    readiness_rejected(series)
    series=declared();series['rows'][0]['scope']={**series['scope'],field:'UNRELATED'}
    report=readiness_rejected(series)
    assert 'ROW_EXACT_PHYSICAL_SCOPE_MISMATCH' in report['blockers']


@pytest.mark.parametrize('fact,field,bad',[
    ('semantic','value','OTHER'),('unit','value','OTHER'),('clock','value','LOCAL_TIME_UNCONFIRMED'),
    ('qc','value',''),('sensor_episode','physical_sensor_id','UNRELATED'),
])
def test_source_quantity_physical_sensor_clock_and_missing_qc_revision_are_not_approved(fact,field,bad):
    series=declared();series['facts'][fact][field]=bad
    readiness_rejected(series)


@pytest.mark.parametrize('change',[
    {'source':{'sha256':'unverified','locator':'row:1'}},
    {'source':{'sha256':'a'*64,'locator':''}},
    {'qc_eligible':False}, {'timestamp':'2020-01-01 00:00:00'},
    {'available_at':'2020-01-01T06:21:00+00:00'},
    {'qc_available_at':'2020-01-01T06:21:00+00:00'},
])
def test_source_cell_qc_and_future_or_naive_row_clocks_remain_strict(change):
    series=declared();series['rows'][0].update(change)
    readiness_rejected(series)


def test_rule_schema_uses_same_codec_without_anomaly_field_aliases_or_future_metadata():
    sample=rule_row();runtime={'as_of':datetime.fromisoformat(CONTEXT['as_of'])}
    assert _record(sample,runtime)
    for changes in [
        {'start':'2025-01-01T00:00:00Z'},
        {'available_at':'2026-01-02T00:00:00.000001Z'},
        {'version_available_at':None},
        {'scope':{'station_id':'OTHER','sensor_id':'S1','variable_code':'AIR_TEMP','unit':'degC'}},
    ]:
        bad=deepcopy(sample);bad['source_facts'].update(changes)
        with pytest.raises(NotEvaluated):_record(bad,runtime)
    aliased=deepcopy(sample);facts=aliased['source_facts']
    facts['start']=facts.pop('effective_start');facts['end']=facts.pop('effective_end')
    with pytest.raises(NotEvaluated,match='AMBIGUOUS_FACT_PERIOD_FIELDS'):_record(aliased,runtime)


def test_period_code_is_bound_to_anomaly_and_rule_fingerprints():
    from hashlib import sha256
    from pathlib import Path
    import app.services.qc_analysis_readiness as contract
    expected=sha256(Path(contract.__file__).read_bytes()).hexdigest()
    assert implementation_hashes()['fact_contract_sha256']==expected
    baseline=fingerprint()
    assert len(baseline)==64
    # Existing artifact fingerprint also binds these dependency bytes; no old
    # artifact is relabelled or re-signed by the period change.
    import app.ml.anomaly_artifact as module
    with pytest.MonkeyPatch.context() as patch:
        original=module.hashlib.sha256
        class Hash:
            def hexdigest(self):return 'f'*64
        patch.setattr(module.hashlib,'sha256',lambda value:Hash() if value==Path(contract.__file__).read_bytes() else original(value))
        assert fingerprint()!=baseline
