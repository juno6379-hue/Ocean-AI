"""Actual isolated Parquet, exact raw literals and month-grid boundaries."""
from datetime import datetime,timedelta,date
from pathlib import Path
import hashlib
import json
import pytest
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from app.services import native_month_metrics as service


def fixture(tmp_path,source='GD_OBS_ST_MONTHLY',bad_numeric=False):
    month='2024-02';rows=[]
    for i in range(8):
        row={'station_raw':'DT_A  ','item_raw':'TEMP  ','time_raw':str(datetime(2024,2,1)+timedelta(minutes=i)),
             'value_raw':str(i),'qc_raw':'G ','mq_raw':'B ','n1_aqc_raw':None,'record_class':'OBSERVATION_SHAPED_UNVALIDATED'}
        rows.append(row)
    if bad_numeric:
        rows[2]['value_raw']='';rows[3]['value_raw']='NaN';rows[4]['value_raw']='bad'
    rows.append({**rows[0],'time_raw':rows[3]['time_raw']})
    rows.append({**rows[0],'record_class':'SQLPLUS_METADATA','time_raw':'query heading'})
    path=tmp_path/'raw.parquet';pq.write_table(pa.Table.from_pylist(rows),path)
    sha=service.file_hash(path)
    assets=[{'source_group':source,'source_path':'data_202402.csv','parquet_path':str(path),
             'parquet_sha256':sha,'source_sha256':'a'*64}]
    missing=1 if bad_numeric else 0;numeric=6 if bad_numeric else 9
    catalog=[{'source_group':source,'station_code':'DT_A','item_code':'TEMP','depth_step':None,
       'depth_from':None,'depth_to':None,'month':date(2024,2,1),'held_rows':9,
       'missing_value_rows':missing,'numeric_rows':numeric,'invalid_time_rows':0,'source_qc_present_rows':9}]
    snapshot=tmp_path/'snapshot';snapshot.mkdir()
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    with duckdb.connect(str(snapshot/'file-only-timeseries.duckdb')) as c:
        c.register('assets',pa.Table.from_pylist(assets));c.execute('CREATE TABLE source_assets AS SELECT * FROM assets')
    return snapshot,assets,catalog


def test_isolated_parquet_preserves_qc_padding_and_duplicate_and_leap_month_denominator(tmp_path):
    snapshot,assets,catalog=fixture(tmp_path)
    packet=service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog,tmp_path/'work')
    row=packet['channels'][0]
    assert row['raw_rows']==9 and row['unique_valid_month_timestamps']==8 and row['duplicate_timestamp_rows']==1
    assert row['grid']['expected_slots']==29*24*60 and row['grid']['held_slots']==8
    assert next(r for r in row['qc_codes'] if r['field']=='qc_raw')['literal']=='G '
    assert next(r for r in row['qc_codes'] if r['field']=='mq_raw')['literal']=='B '
    assert row['source_qc_present_rows']==9 and row['source_QC_codes_interpreted'] is False
    assert packet['source_file_verification']['footer_rows']==10 and packet['source_file_verification']['non_observation_rows']==1
    assert packet['source_file_verification']['sha256_before_and_after_all_files'] is True


def test_numeric_missing_nonfinite_and_nonnumeric_not_bad_classification(tmp_path):
    snapshot,assets,catalog=fixture(tmp_path,bad_numeric=True)
    row=service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog,tmp_path/'work')['channels'][0]
    assert (row['missing_value_rows'],row['numeric_rows'],row['nonfinite_numeric_rows'],row['nonnumeric_value_rows'])==(1,6,1,1)
    assert 'qc_bad_rate' not in row and row['grid']['held_slots']==8


def test_source_hash_and_membership_and_counts_are_rechecked(tmp_path):
    snapshot,assets,catalog=fixture(tmp_path)
    source_path=Path(assets[0]['parquet_path']);original=source_path.read_bytes();source_path.write_bytes(original+b'tamper')
    with pytest.raises(ValueError,match='SOURCE_PARQUET_HASH_OR_STAT_CHANGED'):
        service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog,tmp_path/'work')
    source_path.write_bytes(original)
    catalog[0]['held_rows']=8
    with pytest.raises(ValueError,match='CALLER_CATALOG_ROWS_NOT_BOUND_TO_SNAPSHOT'):
        service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog,tmp_path/'work')


def test_exact_phase_offset_and_multi_phase_exclusion_do_not_snap():
    intervals=[{'microseconds':1200000000,'count':20}]
    phase=[{'microseconds':180000000,'unique_timestamp_count':4,'raw_rows':4}]
    row=service.grid('2026-07',intervals,phase,0)
    assert row['expected_slots']==2232 and row['phase_microseconds']==180000000
    assert row['held_slots']==4 and row['round_or_snap_applied'] is False
    phase.append({'microseconds':180000001,'unique_timestamp_count':1,'raw_rows':1})
    row=service.grid('2026-07',intervals,phase,0)
    assert row['expected_slots'] is None and row['holding_fraction_percent'] is None
    assert row['candidate_phase_accounting']['off_reference_rows']==1


def test_modal_interval_and_phase_ties_and_no_positive_interval_are_explicit():
    assert service.grid('2026-07',[],[],0)['status']=='INSUFFICIENT_POSITIVE_INTERVALS'
    assert service.grid('2026-07',[{'microseconds':1,'count':2},{'microseconds':2,'count':2}],[],0)['status']=='INTERVAL_MODE_AMBIGUOUS'
    row=service.grid('2026-07',[{'microseconds':2,'count':3}],
      [{'microseconds':0,'unique_timestamp_count':2,'raw_rows':2},{'microseconds':1,'unique_timestamp_count':2,'raw_rows':2}],0)
    assert row['status']=='PHASE_MODE_AMBIGUOUS' and row['expected_slots'] is None


def test_publication_content_addressed_packet_and_atomic_scope_pointer(tmp_path):
    snapshot,assets,catalog=fixture(tmp_path)
    packet=service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog,tmp_path/'work')
    first=service.publish_packet(tmp_path/'published',packet)
    second=service.publish_packet(tmp_path/'published',packet)
    assert first==second
    pointer=json.loads(Path(first['publication_path']).read_text(encoding='utf-8'))
    assert pointer['approved'] is False and pointer['sha256']==service.file_hash(first['path'])


def test_typed_grain_keys_keep_null_string_zero_and_numeric_zero_distinct():
    base=dict(station_code='DT_A',item_code='X',depth_step=None,depth_from=None,depth_to=None)
    assert len({service.typed_key({**base,'depth_step':v}) for v in [None,'0','0.0',0,0.0]})==5


def test_duplicate_catalog_grain_is_not_silently_overwritten(tmp_path):
    snapshot,assets,catalog=fixture(tmp_path)
    with pytest.raises(ValueError,match='DUPLICATE_TYPED_CATALOG_GRAIN'):
        service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog+catalog,tmp_path/'work')


def test_snapshot_changed_after_source_hash_cannot_be_published(tmp_path):
    snapshot,assets,catalog=fixture(tmp_path)
    def change(stage,**fields):
        if stage=='HASHED':
            replacement=[{**catalog[0],'held_rows':10}]
            pq.write_table(pa.Table.from_pylist(replacement),snapshot/'station-item-month-validation.parquet')
    with pytest.raises(ValueError,match='SNAPSHOT_CHANGED_DURING_CALCULATION'):
        service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog,tmp_path/'work',change)


def test_explicit_offset_clock_is_preserved_as_unsupported_not_converted_to_naive_grid(tmp_path):
    snapshot,assets,catalog=fixture(tmp_path)
    path=Path(assets[0]['parquet_path']);data=pq.read_table(path).to_pylist()
    data[4]['time_raw']='2024-02-01 00:04:00+09:00'
    pq.write_table(pa.Table.from_pylist(data),path);assets[0]['parquet_sha256']=service.file_hash(path)
    with duckdb.connect(str(snapshot/'file-only-timeseries.duckdb')) as c:
        c.execute('UPDATE source_assets SET parquet_sha256=?',[assets[0]['parquet_sha256']])
    packet=service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog,tmp_path/'work')
    row=packet['channels'][0]
    assert row['unsupported_clock_representation_rows']==1
    assert row['grid']['status']=='CLOCK_REPRESENTATION_UNVERIFIED'
    assert row['grid']['holding_fraction_percent'] is None and row['grid']['expected_slots'] is None


def test_no_primary_qc_column_is_absent_with_null_presence_not_zero(tmp_path):
    snapshot,assets,catalog=fixture(tmp_path)
    path=Path(assets[0]['parquet_path']);data=pq.read_table(path).drop(['qc_raw']);pq.write_table(data,path)
    assets[0]['parquet_sha256']=service.file_hash(path);catalog[0]['source_qc_present_rows']=None
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    with duckdb.connect(str(snapshot/'file-only-timeseries.duckdb')) as c:
        c.execute('UPDATE source_assets SET parquet_sha256=?',[assets[0]['parquet_sha256']])
    row=service.compute_month(snapshot,'GD_OBS_ST_MONTHLY','2024-02',assets,catalog,tmp_path/'work')['channels'][0]
    assert row['source_qc_present_rows'] is None and row['source_qc_primary_field'] is None
    assert row['source_qc_field_state']=='ABSENT'
