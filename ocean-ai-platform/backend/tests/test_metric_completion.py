"""Scope, evidence denominators, and fail-closed integrity for diagnostic metrics."""
import hashlib
import json
from pathlib import Path

import pytest
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import date
from fastapi import HTTPException

from app.core.config import settings
from app.services import metric_completion as service


def channel(code,held,expected,reference=None,source='GD_OBS_ST_MONTHLY',item='TEMP'):
    return dict(source_group=source,station_code=code,item_code=item,depth_step=None,depth_from=None,depth_to=None,
                raw_rows=held,missing_value_rows=0,numeric_rows=held,invalid_time_rows=0,
                source_qc_present_rows=held if source!='GR_OBS_ST' else None,
                source_qc_field_state='PRESENT' if source!='GR_OBS_ST' else 'ABSENT',
                source_qc_primary_field='qc_raw' if source!='GR_OBS_ST' else None,
                unique_valid_month_timestamps=held,duplicate_timestamp_rows=0,qc_codes=[],
                grid=dict(status='STABLE' if expected else 'PHASE_UNSTABLE',expected_slots=expected,
                          held_slots=held if expected else None),report_refs=[reference] if reference else [])


@pytest.fixture
def audit(tmp_path,monkeypatch):
    ref=dict(rate_reference_id='cell:T1:DT1:temperature',station_code='DT1',station_name='실측소',
             item_label='수온',value=90.1,literal='90.1',status='PRINTED_REFERENCE',pdf_page=46,table_id='2-6')
    rows=[channel('DT1',90,100,ref),channel('DT2',10,20),channel('DT3',7,None),
          channel('DT1',5,10,ref,item='TEMP_ALT'),channel('GR1',4,10,source='GR_OBS_ST')]
    directory=tmp_path/'202607'/'metric-enrichment';directory.mkdir(parents=True)
    packet=dict(schema_version='metric-completion-1',approved=False,report_month='2026-07',snapshot='verified-july',
                generated_at='2026-10-08T00:00:00Z',channels=rows,source_file_verification={'files':146})
    def publish(value=packet,month='2026-07'):
        data=json.dumps(value).encode()
        (directory/'metric-completion.json').write_bytes(data)
        (directory/'published.json').write_text(json.dumps({'report_month':month,'sha256':hashlib.sha256(data).hexdigest()}))
    publish()
    monkeypatch.setattr(settings,'MONTHLY_REPORT_MATCHING_ROOT',str(tmp_path))
    monkeypatch.setattr(service.lake_browser,'context',lambda:(Path('verified-july'),None))
    return directory,packet,publish


def complete(**kwargs):
    return service.completion('GD_OBS_ST_MONTHLY','2026-07','2026-07',**kwargs)


def test_grid_uses_sum_of_denominators_and_excludes_unstable_grains(audit):
    result=complete()
    raw=result['raw'];grid=raw['grid']
    assert raw['held_rows']==112 and grid['held_slots']==105 and grid['expected_slots']==130
    assert grid['holding_fraction_percent']==80.769
    assert grid['excluded_channel_months']==1 and grid['eligible_channel_months']==3
    assert grid['approved_sampling_contract'] is False
    assert result['report_reference']['numeric_reference_values']==1
    assert result['report_reference']['unweighted_reference_mean_percent']==90.1


def test_source_station_item_and_station_scope_do_not_leak(audit):
    result=complete(station='DT1',item='TEMP',station_scope={'include':['DT1']})
    assert result['channel_months']==1 and result['raw']['held_rows']==90
    assert complete(station_scope={'exclude':['DT1','DT3']})['raw']['held_rows']==10
    raw=service.completion('GR_OBS_ST','2026-07','2026-07')['raw']
    assert raw['held_rows']==4 and raw['source_qc_presence_rate'] is None and raw['source_qc_field_state']=='ABSENT'


def test_empty_and_unsupported_periods_never_show_july_or_zero_percent(audit):
    result=complete(station='NOT_PRESENT')
    assert result['state']=='EMPTY_SCOPE' and result['raw']['grid']['holding_fraction_percent'] is None
    assert result['raw']['missing_value_rate'] is None
    result=service.completion('GD_OBS_ST_MONTHLY','2023-01','2026-07')
    assert result['state']=='UNAVAILABLE_PERIOD' and result['raw'] is None and result['report_reference'] is None


def test_catalog_only_station_is_not_counted_as_current_held_facility(audit):
    _,packet,publish=audit
    packet['channels'].append(channel('PAST_STATION',0,None))
    publish()
    raw=complete()['raw']
    assert 'PAST_STATION' not in {r['station_code'] for r in raw['stations']}
    assert raw['catalog_only_station_codes']==['PAST_STATION']
    assert complete(station='PAST_STATION')['state']=='EMPTY_SCOPE'


def test_tampering_month_and_stale_snapshot_are_explicit(audit,monkeypatch):
    directory,packet,publish=audit
    (directory/'metric-completion.json').write_text('{}')
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==409
    publish(month='2026-06')
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==409
    publish()
    monkeypatch.setattr(service.lake_browser,'context',lambda:(Path('other-snapshot'),None))
    result=complete()
    assert result['state']=='STALE' and result['raw'] is None


@pytest.mark.parametrize('change',[
    lambda p:p['channels'].append(p['channels'][0]),
    lambda p:p['channels'][0]['grid'].update(held_slots=101),
    lambda p:p['channels'][0].update(missing_value_rows=-1),
    lambda p:p['channels'][0]['report_refs'][0].update(value=101),
])
def test_impossible_or_duplicate_metric_evidence_is_rejected(audit,change):
    _,packet,publish=audit
    change(packet);publish()
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==503


def test_same_printed_cell_cannot_conflict_across_channels(audit):
    _,packet,publish=audit
    packet['channels'][3]['report_refs']=[{**packet['channels'][0]['report_refs'][0],'value':91}]
    publish()
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==409


def test_original_null_and_padded_qc_tokens_are_preserved(audit):
    _,packet,publish=audit
    packet['channels'][0]['qc_codes']=[{'field':'qc_raw','literal':'G ','count':80},
                                      {'field':'qc_raw','literal':None,'count':10}]
    publish()
    rows=complete(station='DT1',item='TEMP')['raw']['qc_codes']
    assert next(r for r in rows if r['literal']=='G ')['percent_of_field_rows']==88.889
    assert next(r for r in rows if r['literal'] is None)['count']==10


def test_legacy_july_same_snapshot_name_must_match_current_catalog_counts(audit,monkeypatch,tmp_path):
    _,packet,_=audit
    view=tmp_path/'verified-july';view.mkdir()
    rows=[]
    for row in packet['channels']:
        rows.append({k:row[k] for k in ('source_group','station_code','item_code','depth_step','depth_from','depth_to')}
          |dict(month=date(2026,7,1),held_rows=row['raw_rows'],numeric_rows=row['numeric_rows'],missing_value_rows=row['missing_value_rows'],
            invalid_time_rows=row['invalid_time_rows'],source_qc_present_rows=row['source_qc_present_rows']))
    rows[0]['held_rows']+=1
    pq.write_table(pa.Table.from_pylist(rows),view/'station-item-month-validation.parquet')
    monkeypatch.setattr(service.lake_browser,'context',lambda:(view,view/'station-item-month-validation.parquet'))
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==503


def test_gr_legacy_catalog_zero_placeholder_does_not_become_qc_zero_percent(audit,monkeypatch,tmp_path):
    _,packet,_=audit
    view=tmp_path/'verified-july';view.mkdir()
    raw=next(r for r in packet['channels'] if r['source_group']=='GR_OBS_ST')
    catalog={k:raw[k] for k in ('source_group','station_code','item_code','depth_step','depth_from','depth_to')}
    catalog.update(month=date(2026,7,1),held_rows=4,numeric_rows=4,missing_value_rows=0,
      invalid_time_rows=0,source_qc_present_rows=0)
    pq.write_table(pa.Table.from_pylist([catalog]),view/'station-item-month-validation.parquet')
    monkeypatch.setattr(service.lake_browser,'context',lambda:(view,view/'station-item-month-validation.parquet'))
    result=service.completion('GR_OBS_ST','2026-07','2026-07')
    assert result['state']=='AVAILABLE' and result['raw']['held_rows']==4
    assert result['raw']['source_qc_present_rows'] is None and result['raw']['source_qc_presence_rate'] is None
    assert result['raw']['source_qc_field_state']=='ABSENT'


def test_present_qc_catalog_zero_is_still_strictly_checked(audit,monkeypatch,tmp_path):
    _,packet,_=audit
    view=tmp_path/'verified-july';view.mkdir()
    catalog=[]
    for raw in packet['channels']:
        if raw['source_group']!='GD_OBS_ST_MONTHLY':continue
        catalog.append({k:raw[k] for k in ('source_group','station_code','item_code','depth_step','depth_from','depth_to')}
          |dict(month=date(2026,7,1),held_rows=raw['raw_rows'],numeric_rows=raw['numeric_rows'],
            missing_value_rows=0,invalid_time_rows=0,source_qc_present_rows=0))
    pq.write_table(pa.Table.from_pylist(catalog),view/'station-item-month-validation.parquet')
    monkeypatch.setattr(service.lake_browser,'context',lambda:(view,view/'station-item-month-validation.parquet'))
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==503
