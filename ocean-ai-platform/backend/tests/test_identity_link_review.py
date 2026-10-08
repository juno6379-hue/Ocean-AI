from datetime import date, datetime
import hashlib
import pytest
from app.services.identity_link_review import (candidate_id, date_bounds, review_channels, verify_document_alias, month, exact_scope_key, rehydrate_report_table, reported_date_candidates,
    report_event_links, sensor_binding_errors, evidence_time_errors, split_leakage_errors, DECISIONS)


def channel(**changes):
    row = dict(source_group='GD_OBS_ST_MONTHLY', station_code='DT_0001', item_code='AIR_PRES',
        depth_step=None, depth_from=None, depth_to=None, month=date(2023, 1, 1), held_rows=44640,
        first_clock=datetime(2023, 1, 1), last_clock=datetime(2023, 1, 31, 23, 59),
        approval_status='UNAPPROVED', event_ids='[]', management_event_ids='[]',
        installation_claim_ids='[]', physical_sensor_candidate_ids='[]')
    row.update({k: '해소' if k == 'source_identity_decision' else '근거 부족' for k in DECISIONS})
    row.update(changes)
    return row


def test_raw_source_depth_and_month_are_part_of_stable_identity():
    a = channel()
    assert candidate_id(a) == candidate_id(channel(month='2023-01-01'))
    assert candidate_id(a) != candidate_id(channel(source_group='GR_OBS_ST'))
    assert candidate_id(a) != candidate_id(channel(depth_step='1'))
    assert candidate_id(a) != candidate_id(channel(month='2023-02-01'))
    assert exact_scope_key(a) == exact_scope_key(channel(month='2023-01'))
    assert exact_scope_key(channel(depth_step=1)) != exact_scope_key(channel(depth_step='1'))


@pytest.mark.parametrize('value', ['2023-01garbage', '2023-01-99', '2023-02-29', '2023-01-01BAD', '2023-01-01T00:00BAD'])
def test_month_rejects_invalid_suffixes_and_dates(value):
    with pytest.raises(ValueError):
        month(value)


def test_even_resolved_references_and_claimed_approval_do_not_create_membership():
    a = channel(**{k: '해소' for k in DECISIONS}, approval_status='APPROVED',
                physical_sensor_id='real', standard_unit='hPa', timezone_name='Asia/Seoul',
                valid_from='2023-01-01', valid_to='2023-02-01')
    receipt, candidates, _ = review_channels([a], 'a' * 64, 'test')
    assert receipt['status'] == 'DRAFT_BLOCKED' and receipt['eligible_members'] == 0
    assert not candidates[0]['training_eligible'] and candidates[0]['split'] == 'UNASSIGNED'
    assert 'ROW_MEMBERSHIP_UNFROZEN' in candidates[0]['validation_errors']


def test_duplicate_grain_fails_census_but_cross_source_overlap_is_not_merged():
    receipt, candidates, overlaps = review_channels([channel(), channel(source_group='GR_OBS_ST')], 'a' * 64, 'x')
    assert receipt['coverage_complete'] and len(overlaps) == 1 and len(candidates) == 2
    receipt, _, _ = review_channels([channel(), channel()], 'a' * 64, 'x')
    assert not receipt['coverage_complete'] and receipt['duplicate_candidate_ids']


def test_event_month_match_never_invents_sensor_or_exact_event_date():
    events = [dict(id='e', station_codes='["DT_0001"]', item_codes='["*"]',
                   period_start='2023-01', period_end_inclusive='2023-01', sha256='a' * 64, locator='pdf_page:7')]
    result = report_event_links([channel(event_ids='["e"]')], events)
    assert not result['validation_errors']
    assert result['links'][0]['match_kind'] == 'STATION_WIDE_MONTH_CANDIDATE'
    assert result['links'][0]['physical_sensor_id'] is None
    assert result['links'][0]['event_start_utc'] is None
    result = report_event_links([channel(event_ids='["e"]', month='2023-02-01')], events)
    assert result['validation_errors'][0]['error'] == 'EVENT_MONTH_MISMATCH'
    events[0].update(period_start='2023-01-31', period_end_inclusive='2023-01-01')
    result = report_event_links([channel(event_ids='["e"]')], events)
    assert result['validation_errors'][0]['error'] == 'EVENT_PERIOD_REVERSED'


def binding(**changes):
    result = dict(record_id='a', source_group='GD_OBS_ST_MONTHLY', station_code='DT_0001',
        source_item_code='AIR_PRES', physical_sensor_id='pressure-serial', sensor_episode_id='episode',
        unit='hPa', standard_variable='AIR_PRESSURE', depth=None, approval_status='APPROVED',
        approval_id='reviewer-approval', effective_start='2023-01-01T00:00:00+00:00',
        effective_end='2023-02-01T00:00:00+00:00')
    result.update(changes)
    return result


def test_sensor_period_adjacency_allowed_overlap_and_naive_clocks_rejected():
    a, b = binding(), binding(record_id='b', effective_start='2023-02-01T00:00:00+00:00',
                             effective_end='2023-03-01T00:00:00+00:00')
    assert not sensor_binding_errors([a, b])
    b['effective_start'] = '2023-01-31T00:00:00+00:00'
    assert any(x['error'] == 'OVERLAPPING_SENSOR_PERIODS' for x in sensor_binding_errors([a, b]))
    assert any(x['error'] == 'SENSOR_INTERVAL_UNVERIFIED' for x in sensor_binding_errors([binding(effective_start='2023-01-01')]))


def test_partial_dates_remain_bounds_not_exact_instants():
    assert date_bounds('2024', 'YEAR') == ('2024-01-01', '2024-12-31')
    assert date_bounds('2024-02', 'MONTH') == ('2024-02-01', '2024-02-29')


def test_report_date_does_not_substitute_asof_availability():
    evidence = dict(role='FEATURE_INPUT', report_date='2025-12-24', source_sha256='a' * 64, locator='pdf_page:7')
    assert 'AVAILABLE_AT_OR_ORIGIN_UNVERIFIED' in evidence_time_errors(evidence, '2025-01-01T00:00:00Z')
    evidence['available_at'] = '2025-12-24T00:00:00Z'
    assert 'POST_ORIGIN_EVIDENCE' in evidence_time_errors(evidence, '2025-01-01T00:00:00Z')
    evidence['role'] = 'RETROSPECTIVE_LABEL_EVIDENCE'
    assert evidence_time_errors(evidence, '2025-01-01T00:00:00Z') == ['NOT_AN_ASOF_FEATURE_INPUT']


def test_evidence_hash_must_be_full_sha256():
    evidence = dict(role='FEATURE_INPUT', available_at='2023-01-01T00:00:00Z', source_sha256='abc', locator='p7')
    assert 'SOURCE_LOCATOR_MISSING' in evidence_time_errors(evidence, '2023-01-01T00:00:00Z')


def test_local_report_date_is_not_compared_with_utc_calendar_date():
    evidence = dict(role='FEATURE_INPUT', report_date='2023-01-02',
        available_at='2023-01-01T15:30:00Z', source_sha256='a' * 64, locator='p7')
    assert not evidence_time_errors(evidence, '2023-01-01T16:00:00Z')
    assert 'POST_ORIGIN_EVIDENCE' in evidence_time_errors(evidence, '2023-01-01T15:00:00Z')
    evidence['report_created_at'] = '2023-01-02T00:45:00+09:00'
    assert 'AVAILABLE_BEFORE_REPORTED_DATE' in evidence_time_errors(evidence, '2023-01-01T16:00:00Z')


def member(**changes):
    row = dict(member_id='m1', split='TRAIN', event_id='e1', sensor_episode_id='s1', source_record_identity='r1',
               document_family_id='d1', origin='2023-01-01T00:04:00Z', feature_window_start='2023-01-01T00:00:00Z',
               feature_window_end='2023-01-01T00:03:00Z', available_at='2023-01-01T00:04:00Z',
               target_time='2023-01-01T00:05:00Z', sensor_effective_start='2023-01-01T00:00:00Z',
               sensor_effective_end='2023-02-01T00:00:00Z')
    row.update(changes)
    return row


def test_split_event_and_document_family_leakage_and_future_inputs_rejected():
    assert not split_leakage_errors([member()])
    errors = split_leakage_errors([member(), member(member_id='m2', split='TEST', source_record_identity='r2')])
    assert 'EVENT_ID_CROSSES_SPLITS:e1' in errors
    assert 'SENSOR_EPISODE_ID_CROSSES_SPLITS:s1' in errors
    assert 'DOCUMENT_FAMILY_ID_CROSSES_SPLITS:d1' in errors
    assert 'FEATURE_FUTURE_LEAKAGE' in split_leakage_errors([member(available_at='2023-01-01T00:06:00Z')])
    assert 'TARGET_CROSSES_SENSOR_EPISODE' in split_leakage_errors([member(target_time='2023-02-01T00:00:00Z')])


def test_distinct_entities_still_require_chronological_forecast_splits():
    train = member()
    test = member(member_id='test', split='TEST', event_id='e2', sensor_episode_id='s2',
                  source_record_identity='r2', document_family_id='d2')
    assert 'CHRONOLOGICAL_SPLIT_LEAKAGE:TRAIN:TEST' in split_leakage_errors([train, test])
    test.update(origin='2023-01-02T00:04:00Z', feature_window_start='2023-01-02T00:00:00Z',
                feature_window_end='2023-01-02T00:03:00Z', available_at='2023-01-02T00:04:00Z',
                target_time='2023-01-02T00:05:00Z')
    assert not split_leakage_errors([train, test])


def test_canonical_document_alias_requires_identical_bytes_and_allowed_root(tmp_path):
    path = tmp_path/'evidence.pdf'
    path.write_bytes(b'original document bytes')
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = verify_document_alias('D:/share/removed.pdf', sha, path, tmp_path)
    assert receipt['source_sha256'] == sha and not receipt['meaning_or_period_approval']
    path.write_bytes(b'changed document bytes')
    with pytest.raises(ValueError, match='HASH_MISMATCH'):
        verify_document_alias('D:/share/removed.pdf', sha, path, tmp_path)
    with pytest.raises(ValueError, match='NOT_ALLOWED'):
        verify_document_alias('D:/share/removed.pdf', sha, path, tmp_path/'other-root')


def test_merged_pdf_cell_requires_geometry_proof_before_inheritance():
    table = dict(rows=[['2025.01','A'],['2025.02',None],['2025.03',None]],
                 row_bboxes=[[0,0,20,20],[0,10,20,20],[0,20,20,30]],
                 cells=[[[0,0,10,10],[10,0,20,20]],[[0,10,10,20],None],[[0,20,10,30],None]])
    rows = rehydrate_report_table(table)
    assert rows[1]['values'][1] == 'A' and not rows[1]['validation_errors']
    assert rows[1]['cell_provenance'][1]['kind'] == 'SPANNING_CELL'
    assert rows[2]['values'][1] is None and rows[2]['validation_errors'] == ['EMPTY_UNMERGED_CELL:1']


def test_incheon_cleaning_is_action_date_not_failure_interval():
    rows = reported_date_candidates('수온·염분계 감도 저하 추정 → 세척(`24.12.26)', 2025)
    assert len(rows) == 1 and rows[0]['role'] == 'REPORTED_ACTION_TIME'
    assert rows[0]['statement_context'] == '세척'
    assert rows[0]['reported_start']['value'] == '2024-12-26'
    assert rows[0]['reported_start']['utc'] is None


def test_jeju_failure_interval_and_replacement_date_are_separate_candidates():
    rows = reported_date_candidates('통합기상센서 고장(`24.10.21 ~ `25.08.03) → 정밀점검을 통한 통합기상센서 교체(08.03)', 2025)
    assert [x['role'] for x in rows] == ['REPORTED_CONDITION_INTERVAL', 'REPORTED_ACTION_TIME']
    assert rows[0]['reported_start']['value'] == '2024-10-21'
    assert rows[0]['reported_end']['value'] == '2025-08-03'
    assert rows[1]['reported_start']['value'] == '2025-08-03'
    assert rows[1]['reported_start']['year_evidence'] == 'REPORT_CONTEXT_YEAR_CANDIDATE'
    assert all(x['endpoint_policy'] == 'UNAPPROVED' for x in rows)


def test_unknown_date_role_is_unclassified_and_ongoing_end_remains_null():
    rows = reported_date_candidates('자료 메모(08.03)', 2025)
    assert rows[0]['role'] == 'UNCLASSIFIED_REPORTED_DATE_CANDIDATE'
    rows = reported_date_candidates('센서 고장(08.27 ~ 지속)', 2025)
    assert rows[0]['reported_end'] is None and rows[0]['open_end_reported']
