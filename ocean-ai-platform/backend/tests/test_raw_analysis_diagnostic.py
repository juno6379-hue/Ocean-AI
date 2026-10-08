import copy
import json
from datetime import datetime, timedelta

import numpy as np
import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from app.services.qc_raw_diagnostic import (SERIES, RawDiagnosticError, digest,
    fixed_membership, fit_raw_diagnostic, analyze_raw_diagnostic, hash_file,
    read_raw_parquet_series, unevaluated_rule_report)
from app.services.evidence_fusion import fuse_raw_diagnostics, FusionError
from app.services.anomaly_analysis import source_requirements, analyze_series


GRAIN = {'source_group': 'SYNTHETIC_TEST_ONLY', 'source_station_code': 'ST',
    'source_item_code': 'X', 'depth_step': None, 'depth_from': None, 'depth_to': None}


def fixture(n=120):
    start = datetime(2026, 7, 1)
    rows = [{'row_id': str(i), 'grain': copy.deepcopy(GRAIN),
        'clock_raw': (start+timedelta(minutes=i)).isoformat(' '),
        'value_raw': str(10+np.sin(i/7)*.2), 'source_qc_raw': {'MQC': 'G '},
        'source': {'sha256': 'b'*64, 'locator': f'parquet_row_group=0;row_index={i};column=VALUE'}} for i in range(n)]
    series = {'schema_version': SERIES, 'grain': GRAIN, 'source_manifest_sha256': 'a'*64,
        'clock_format': '%Y-%m-%d %H:%M:%S', 'rows': rows}
    policy = {'schema_version': 'raw-native-diagnostic-policy-1',
        'membership': fixed_membership(series, 60, 30), 'window_samples': 8,
        'calibration_quantile': .95, 'raw_numeric_scale_floor': 1e-9}
    return series, policy


def test_actual_shape_fit_prediction_and_raw_fusion_are_separate_from_physical():
    series, policy = fixture(); series['rows'][105]['value_raw'] = '50'
    artifact = fit_raw_diagnostic(series, policy)
    ai = analyze_raw_diagnostic(series, artifact)
    rules = unevaluated_rule_report(series, '2026-10-08T00:00:00Z')
    fused = fuse_raw_diagnostics(series, artifact, ai, rules)
    assert fused['raw_numeric_candidate_count'] >= 1 and fused['physical_fusion_status'] == 'NOT_EVALUATED'
    assert fused['production_eligible'] is False and fused['approved'] is False
    assert artifact['artifact']['unit'] is artifact['artifact']['timezone'] is None
    assert rules['summary'] == {'NOT_EVALUATED': 1440}
    # Existing statistical/operating loader rejects the separate artifact.
    result = analyze_series({}, artifact)
    assert result['status'] == 'NOT_EVALUATED'


def test_test_values_cannot_change_fitted_parameters_or_calibration():
    series, policy = fixture(); before = fit_raw_diagnostic(series, policy)
    series['rows'][110]['value_raw'] = '100000'
    after = fit_raw_diagnostic(series, policy)
    assert before['artifact']['models'] == after['artifact']['models']
    assert before['artifact']['source_series_sha256'] != after['artifact']['source_series_sha256']


def test_causal_prediction_uses_no_future_test_values():
    series, policy = fixture(); before = analyze_raw_diagnostic(series, fit_raw_diagnostic(series, policy))
    series['rows'][-1]['value_raw'] = '100000'
    after = analyze_raw_diagnostic(series, fit_raw_diagnostic(series, policy))
    assert [r for r in before['results'] if r['row_id'] != '119'] == [r for r in after['results'] if r['row_id'] != '119']


@pytest.mark.parametrize('mutation,reason', [
    ('overlap', 'RAW_MEMBERSHIP_OVERLAP'), ('reversed', 'RAW_CLOCK_DUPLICATE'),
    ('reuse', 'RAW_SOURCE_CELL_REUSE'), ('grain', 'MIXED_RAW_GRAIN'),
    ('nonfinite', 'RAW_VALUE_NONFINITE'), ('unit_approval', 'RAW_ARTIFACT_PARAMETERS')])
def test_negative_contracts_and_rehashed_artifact_claims(mutation, reason):
    series, policy = fixture()
    if mutation == 'overlap': policy['membership']['TEST'][0] = policy['membership']['TRAIN'][0]
    elif mutation == 'reversed': series['rows'][2]['clock_raw'] = series['rows'][1]['clock_raw']
    elif mutation == 'reuse': series['rows'][2]['source'] = series['rows'][1]['source']
    elif mutation == 'grain': series['rows'][2]['grain']['depth_from'] = '0'
    elif mutation == 'nonfinite': series['rows'][2]['value_raw'] = 'NaN'
    if mutation == 'unit_approval':
        artifact = fit_raw_diagnostic(series, policy)
        artifact['artifact']['approved'] = True; artifact['sha256'] = digest(artifact['artifact'])
        with pytest.raises(RawDiagnosticError, match=reason): analyze_raw_diagnostic(series, artifact)
    else:
        with pytest.raises(RawDiagnosticError, match=reason): fit_raw_diagnostic(series, policy)


def test_native_gap_is_not_interpolated_or_bridged():
    series, policy = fixture()
    for row in series['rows'][100:]:
        row['clock_raw'] = (datetime.fromisoformat(row['clock_raw'])+timedelta(minutes=5)).isoformat(' ')
    report = analyze_raw_diagnostic(series, fit_raw_diagnostic(series, policy))
    spike = next(r for r in report['results'] if r['row_id'] == '100' and r['mode'] == 'SPIKE')
    assert spike['result_status'] == 'NOT_EVALUATED' and spike['reason'] == 'SPLIT_WARMUP_OR_NATIVE_CLOCK_GAP'


@pytest.mark.parametrize('tamper', ['row', 'grain', 'reason', 'drop', 'duplicate', 'guide'])
def test_fusion_rejects_unrelated_or_rehashed_rule_report(tamper):
    series, policy = fixture(); artifact = fit_raw_diagnostic(series, policy)
    ai = analyze_raw_diagnostic(series, artifact); rules = unevaluated_rule_report(series, '2026-10-08T00:00:00Z')
    if tamper == 'row': rules['results'][0]['observation_id'] = 'unrelated'
    elif tamper == 'grain': rules['results'][0]['provenance_json']['raw_grain'] = {'station': 'OTHER'}
    elif tamper == 'reason': rules['results'][0]['result_reason'] = 'UNRELATED'
    elif tamper == 'drop': rules['results'].pop()
    elif tamper == 'duplicate': rules['results'][0] = rules['results'][1]
    else: rules['results'][0]['provenance_json']['guide_sha256'] = 'c'*64
    rules['result_sha256'] = digest({k:v for k,v in rules.items() if k != 'result_sha256'})
    with pytest.raises(FusionError, match='RAW_RULE_GRAIN_MEMBERSHIP_OR_RECIPE_MISMATCH'):
        fuse_raw_diagnostics(series, artifact, ai, rules)


def test_actual_parquet_reader_preserves_literals_and_rechecks_bytes(tmp_path):
    file = tmp_path/'source.parquet'; manifest = tmp_path/'manifest.json'
    rows = [{'ST': 'ST  ', 'ITEM': 'X ', 'CLOCK': row['clock_raw'], 'VALUE': row['value_raw'], 'MQC': 'G '}
        for row in fixture()[0]['rows']]
    pq.write_table(pa.Table.from_pylist(rows), file, row_group_size=37)
    manifest.write_text(json.dumps({'files':[{'path':'source.parquet','sha256':hash_file(file),'rows':120}]}), encoding='utf-8')
    cols = {'station':'ST', 'item':'ITEM', 'clock':'CLOCK', 'value':'VALUE', 'qc':['MQC']}
    series = read_raw_parquet_series(file, hash_file(file), manifest, hash_file(manifest), GRAIN, cols, 'STRIP_SQLPLUS_PADDING', 60, 10)
    assert series['rows'][0]['raw_literals']['ST'] == 'ST  '
    assert series['rows'][0]['source_qc_raw']['MQC'] == 'G '
    assert series['rows'][27]['source']['locator'] == 'parquet_row_group=1;row_index=0;column=VALUE'
    with pytest.raises(RawDiagnosticError, match='HASH_MISMATCH'):
        read_raw_parquet_series(file, 'd'*64, manifest, hash_file(manifest), GRAIN, cols, 'STRIP_SQLPLUS_PADDING', 60)


def test_source_requirements_reports_all_missing_scope_facts_clocks():
    series = {'schema_version':'ocean-anomaly-series-1', 'scope':{}, 'facts':{},
        'rows':[{'row_id':'real-native', 'timestamp':'2023-01-01 00:00:00',
            'source':{'sha256':'a'*64, 'locator':'parquet_row_group=0;row_index=1'}}]}
    result = source_requirements(series)
    assert result['status'] == 'NOT_EVALUATED' and result['training_executed'] is False
    assert 'SOURCE_UNIT_NOT_DOCUMENTED' in result['blockers']
    assert 'SOURCE_CLOCK_NOT_DOCUMENTED' in result['blockers']
    assert 'SOURCE_SCOPE_FIELD_REQUIRED:sensor_id' in result['blockers']
    assert result['requirements']['blocker_counts']['SOURCE_ROW_CLOCK_REQUIRED:qc_available_at'] == 1


def test_reader_explicit_native_sort_retains_original_reversal_evidence(tmp_path):
    file = tmp_path/'source.parquet'; manifest = tmp_path/'manifest.json'
    original = fixture()[0]['rows']; original[1],original[2] = original[2],original[1]
    rows = [{'ST':'ST', 'ITEM':'X', 'CLOCK':r['clock_raw'], 'VALUE':r['value_raw']} for r in original]
    pq.write_table(pa.Table.from_pylist(rows),file)
    manifest.write_text(json.dumps({'files':[{'path':'source.parquet','sha256':hash_file(file),'rows':120}]}),encoding='utf-8')
    cols={'station':'ST','item':'ITEM','clock':'CLOCK','value':'VALUE','qc':[]}
    with pytest.raises(RawDiagnosticError,match='RAW_CLOCK_DUPLICATE_OR_REVERSAL'):
        read_raw_parquet_series(file,hash_file(file),manifest,hash_file(manifest),GRAIN,cols,limit=60)
    series=read_raw_parquet_series(file,hash_file(file),manifest,hash_file(manifest),GRAIN,cols,limit=60,ordering='NATIVE_CLOCK_ASCENDING')
    assert series['selection']['ordering_audit']['original_clock_reversals'] == 1
    assert series['selection']['ordering_audit']['native_sort_is_online_availability'] is False
    assert series['rows'][1]['source']['locator'] == 'parquet_row_group=0;row_index=2;column=VALUE'


def test_manifest_source_mismatch_is_rejected_even_with_valid_whole_hash(tmp_path):
    file=tmp_path/'raw.parquet'; manifest=tmp_path/'manifest.json'
    pq.write_table(pa.table({'ST':['ST']}),file)
    manifest.write_text(json.dumps({'files':[{'path':'another.parquet','sha256':hash_file(file),'rows':1}]}),encoding='utf-8')
    with pytest.raises(RawDiagnosticError,match='PARQUET_NOT_EXACTLY_BOUND_TO_MANIFEST'):
        read_raw_parquet_series(file,hash_file(file),manifest,hash_file(manifest),GRAIN,
            {'station':'ST','item':'ST','clock':'ST','value':'ST'},limit=40)


@pytest.mark.parametrize('value',[None, [], {'facts':[],'scope':[],'rows':[None]},
    {'rows':[{'row_id':float('nan')}]}, {'facts':{'qc':{'evidence':True}}}])
def test_malformed_readiness_stays_structured_and_does_not_approve(value):
    result=source_requirements(value)
    assert result['status']=='NOT_EVALUATED' and result['production_eligible'] is False
    assert result['requirements']['requirements'] and result['blockers']
