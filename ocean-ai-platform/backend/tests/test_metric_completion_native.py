"""Period-aware serving of exact catalog counts and frozen native diagnostics."""
from pathlib import Path
from datetime import datetime,timedelta,date
import copy
import json
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import HTTPException
from app.core.config import settings
from app.services import metric_completion as api
from app.services import native_month_metrics as producer
from app.services.native_receipt_diagnostics import receipt_diagnostics as real_receipt_diagnostics


@pytest.fixture
def audit(tmp_path,monkeypatch):
    snapshot=tmp_path/'snapshot';snapshot.mkdir();lake=tmp_path/'lake';lake.mkdir()
    catalog=[];assets=[]
    for month in ['2024-01','2024-02']:
        start=datetime.fromisoformat(month+'-01')
        raw=[dict(station_raw='DT_A  ',item_raw='TEMP ',time_raw=str(start+timedelta(minutes=i)),
          value_raw=str(i),qc_raw=None if i==0 else 'G ',mq_raw='B ',n1_aqc_raw='',
          record_class='OBSERVATION_SHAPED_UNVALIDATED') for i in range(4)]
        path=lake/('raw-'+month+'.parquet');pq.write_table(pa.Table.from_pylist(raw),path)
        assets.append(dict(source_group='GD_OBS_ST_MONTHLY',source_path='data_'+month.replace('-','')+'.csv',
          parquet_path=str(path),parquet_sha256=producer.file_hash(path),source_sha256='a'*64))
        catalog.append(dict(source_group='GD_OBS_ST_MONTHLY',station_code='DT_A',item_code='TEMP',
          depth_step=None,depth_from=None,depth_to=None,month=date(start.year,start.month,1),held_rows=4,
          numeric_rows=4,missing_value_rows=0,invalid_time_rows=0,source_qc_present_rows=3,
          first_clock=start,last_clock=start+timedelta(minutes=3),distinct_timestamps=None))
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    with duckdb.connect(str(snapshot/'file-only-timeseries.duckdb')) as c:
        c.register('input_assets',pa.Table.from_pylist(assets));c.execute('CREATE TABLE source_assets AS SELECT * FROM input_assets')
    monkeypatch.setattr(settings,'MONTHLY_REPORT_MATCHING_ROOT',str(tmp_path/'reports'))
    monkeypatch.setattr(api.lake_browser,'context',lambda:(snapshot,snapshot/'station-item-month-validation.parquet'))
    monkeypatch.setattr(api.lake_browser,'historical_root',lambda:lake)
    monkeypatch.setattr(settings,'SHARE_MONTHLY_LAKE_ROOT',str(lake))
    from app.services import native_receipt_diagnostics
    monkeypatch.setattr(native_receipt_diagnostics,'receipt_diagnostics',lambda *a,**k:{'state':'UNAVAILABLE_PERIOD','raw':None,'stations':[]})
    def publish(month='2024-01'):
        packet=producer.compute_month(snapshot,'GD_OBS_ST_MONTHLY',month,assets,
          [r for r in catalog if str(r['month'])[:7]==month],tmp_path/'work'/month)
        return packet,producer.publish_packet(tmp_path/'reports'/'native-metrics',packet)
    return snapshot,assets,catalog,publish,tmp_path


def complete(start='2024-01',end='2024-02',**kwargs):
    return api.completion('GD_OBS_ST_MONTHLY',start,end,**kwargs)


def test_uncomputed_period_returns_catalog_numeric_qc_counts_with_null_grid(audit):
    result=complete();raw=result['raw']
    assert result['state']=='PARTIAL_CATALOG_COUNTS' and raw['held_rows']==8
    assert raw['numeric_rows']==8 and raw['source_qc_present_rows']==6 and raw['source_qc_presence_rate']==75
    assert raw['grid']['holding_fraction_percent'] is None and raw['grid']['expected_slots']==0
    assert result['calculation_coverage']['uncalculated_held_months']==['2024-01','2024-02']
    assert result['report_reference']['normal_rates']==[] and result['report_reference']['reference_months']==[]
    assert raw['stations'][0]['first_native_clock']=='2024-01-01 00:00:00'


def test_partial_then_complete_month_calculations_keep_full_calendar_denominators(audit):
    _,_,_,publish,_=audit;publish('2024-01')
    result=complete();coverage=result['calculation_coverage']
    assert result['state']=='PARTIAL_CATALOG_COUNTS' and coverage['fully_scanned_months']==['2024-01']
    assert coverage['uncalculated_held_months']==['2024-02'] and coverage['grid_applies_to_full_selected_scope'] is False
    assert result['raw']['held_rows']==8 and result['raw']['grid']['held_slots']==4
    assert result['raw']['grid']['expected_slots']==31*24*60
    publish('2024-02');result=complete()
    assert result['state']=='AVAILABLE' and result['raw']['grid']['held_slots']==8
    assert result['raw']['grid']['expected_slots']==(31+29)*24*60
    assert result['calculation_coverage']['fully_scanned_held_months']==2
    assert result['raw']['source_qc_presence_rate']==75 and result['blocked_metrics'][1]['status']=='INPUTS_MISSING'


def test_station_item_scope_and_missing_period_do_not_reuse_other_data(audit):
    _,_,_,publish,_=audit;publish()
    assert complete(station='NOT_FOUND')['state']=='EMPTY_SCOPE'
    assert complete(item='NOT_FOUND')['raw']['numeric_row_rate'] is None
    assert complete(station_scope={'exclude':['DT_A']})['raw']['held_rows']==0
    result=complete(start='2023-01',end='2023-01')
    assert result['state']=='EMPTY_SCOPE' and result['raw']['grid']['holding_fraction_percent'] is None
    assert result['calculation_coverage']['months_without_held_catalog']==['2023-01']


def test_old_checksum_tamper_and_current_source_tamper_are_explicit(audit):
    _,assets,_,publish,_=audit;_,location=publish()
    path=Path(location['path']);original=path.read_bytes();path.write_bytes(original+b' ')
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==409
    path.write_bytes(original)
    source=Path(assets[0]['parquet_path']);source.write_bytes(source.read_bytes()+b' changed')
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==409


def test_stale_catalog_same_snapshot_name_is_not_joined_to_old_native_packet(audit):
    snapshot,_,catalog,publish,_=audit;publish()
    replacement=[{**r,'numeric_rows':3} for r in catalog]
    pq.write_table(pa.Table.from_pylist(replacement),snapshot/'station-item-month-validation.parquet')
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==409


@pytest.mark.parametrize('change',[
    lambda p:p['channels'][0].update(raw_rows=True),
    lambda p:p['channels'][0]['grid'].update(expected_slots=1000,holding_fraction_percent=1),
    lambda p:p['channels'][0]['qc_codes'].pop(),
    lambda p:p['channels'][0].update(depth_step='0'),
    lambda p:p['source_files'][0].update(footer_rows=3),
    lambda p:p['channels'][0]['grid']['phase_distribution'][0].update(unique_timestamp_count=3,raw_rows=3),
])
def test_recomputed_checksum_cannot_promote_impossible_counts_grid_qc_or_scope(audit,change):
    _,_,_,publish,tmp=audit;packet,_=publish()
    change(packet)
    for row in packet['channels']:row['channel_sha256']=producer.digest({k:v for k,v in row.items() if k!='channel_sha256'})
    producer.publish_packet(tmp/'reports'/'native-metrics',packet)
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==503


def test_zero_held_catalog_counts_do_not_nullify_real_qc_presence_or_hide_absent_qc():
    present=dict(station_code='A',month='2024-01',raw_rows=10,numeric_rows=10,missing_value_rows=0,
      invalid_time_rows=0,source_qc_present_rows=10,source_qc_primary_field='qc_raw',source_qc_field_state='PRESENT',
      duplicate_timestamp_rows=0,unique_valid_month_timestamps=10,qc_codes=[],grid={'status':'UNCOMPUTED','expected_slots':None,'held_slots':None})
    empty={**present,'station_code':'B','raw_rows':0,'numeric_rows':None,'missing_value_rows':None,'invalid_time_rows':None,
      'source_qc_present_rows':None,'source_qc_field_state':'NO_ROWS','duplicate_timestamp_rows':None,'unique_valid_month_timestamps':None}
    raw=api.raw_metrics([present,empty]);assert raw['source_qc_presence_rate']==100 and raw['numeric_row_rate']==100
    assert raw['catalog_only_station_codes']==['B']
    absent={**present,'source_qc_present_rows':None,'source_qc_primary_field':None,'source_qc_field_state':'ABSENT'}
    raw=api.raw_metrics([absent,empty]);assert raw['source_qc_presence_rate'] is None and raw['source_qc_field_state']=='ABSENT'


def test_native_empty_catalog_channel_is_accepted_and_excluded_from_qc_denominator(audit):
    snapshot,_,catalog,publish,_=audit
    catalog.append({**catalog[0],'station_code':'EMPTY','held_rows':None,'numeric_rows':None,
      'missing_value_rows':None,'invalid_time_rows':None,'source_qc_present_rows':None,'first_clock':None,'last_clock':None})
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    publish()
    result=complete(start='2024-01',end='2024-01')
    assert result['state']=='AVAILABLE' and result['raw']['source_qc_presence_rate']==75
    assert result['raw']['catalog_only_station_codes']==['EMPTY']
    assert result['raw']['grid']['excluded_channel_months']==1


def test_catalog_changed_during_response_aggregation_is_not_served(audit,monkeypatch):
    snapshot,_,catalog,publish,_=audit;publish()
    original=api.raw_metrics
    def changed(rows):
        result=original(rows)
        pq.write_table(pa.Table.from_pylist([{**r,'held_rows':5} for r in catalog]),snapshot/'station-item-month-validation.parquet')
        return result
    monkeypatch.setattr(api,'raw_metrics',changed)
    with pytest.raises(HTTPException) as exc:complete()
    assert exc.value.status_code==409


def test_actual_gr_schema_without_qc_overrides_old_catalog_zero_placeholder(audit,monkeypatch):
    snapshot,assets,catalog,_,tmp=audit
    for asset,row in zip(assets,catalog):
        raw=[dict(OBS_POST_ID='DT_A',OBS_ITEM_CODE='TEMP',OBS_TIME=str(row['first_clock']+timedelta(minutes=i)),
          OBS_VALUE=str(i)) for i in range(4)]
        pq.write_table(pa.Table.from_pylist(raw),asset['parquet_path'])
        asset['source_group']='GR_OBS_ST';asset['parquet_sha256']=producer.file_hash(asset['parquet_path'])
        row.update(source_group='GR_OBS_ST',source_qc_present_rows=0)
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    with duckdb.connect(str(snapshot/'file-only-timeseries.duckdb')) as c:
        c.register('updated',pa.Table.from_pylist(assets))
        c.execute('CREATE OR REPLACE TABLE source_assets AS SELECT * FROM updated')
    before=api.completion('GR_OBS_ST','2024-01','2024-01')
    assert before['state']=='PARTIAL_CATALOG_COUNTS' and before['raw']['source_qc_presence_rate'] is None
    packet=producer.compute_month(snapshot,'GR_OBS_ST','2024-01',assets,catalog[:1],tmp/'work'/'gr')
    producer.publish_packet(tmp/'reports'/'native-metrics',packet)
    result=api.completion('GR_OBS_ST','2024-01','2024-01')
    assert result['state']=='AVAILABLE' and result['raw']['held_rows']==4
    assert result['raw']['numeric_rows']==4 and result['raw']['source_qc_field_state']=='ABSENT'
    assert result['raw']['source_qc_present_rows'] is None and result['raw']['source_qc_presence_rate'] is None
    # A packet claim cannot invent a QC column, even with freshly recomputed hashes.
    packet['channels'][0].update(source_qc_primary_field='QC_FLAG',source_qc_present_rows=0,source_qc_field_state='PRESENT')
    packet['channels'][0]['channel_sha256']=producer.digest({k:v for k,v in packet['channels'][0].items() if k!='channel_sha256'})
    producer.publish_packet(tmp/'reports'/'native-metrics',packet)
    with pytest.raises(HTTPException) as exc:api.completion('GR_OBS_ST','2024-01','2024-01')
    assert exc.value.status_code==503


def test_receipt_channel_details_are_not_duplicated_in_summary_response(audit,monkeypatch):
    from app.services import native_receipt_diagnostics
    sample={'state':'AVAILABLE','diagnostic_kind':'SOURCE_CLOCK_DIFFERENCE_NOT_OPERATIONAL_DELAY',
      'approved':False,'operational_delay':False,'raw':{'comparable_pair_rows':4,'state':'INNER_STATE'},'stations':[],
      'channels':[{'station_code':'DT_A'}]*10}
    monkeypatch.setattr(native_receipt_diagnostics,'receipt_diagnostics',lambda *a,**k:sample)
    result=complete(start='2024-01',end='2024-01')
    assert 'channels' not in result['raw']['receipt_diagnostics']
    assert 'raw' not in result['raw']['receipt_diagnostics'] and 'stations' not in result['raw']['receipt_diagnostics']
    assert result['raw']['receipt_diagnostics']['state']=='AVAILABLE'
    assert result['raw']['receipt_diagnostics']['comparable_pair_rows']==4
    assert result['raw']['receipt_diagnostics']['channel_months']==10
    assert len(sample['channels'])==10


def test_actual_receipt_packet_becomes_flat_overview_and_station_evidence(audit,monkeypatch):
    from app.services import native_receipt_diagnostics as receipt_service
    snapshot,assets,catalog,_,tmp=audit
    # Native source literals are calculated, frozen, rehashed and read through the real helper.
    # The source QC/metric catalogue remains independent of the receipt clock arithmetic.
    path=Path(assets[0]['parquet_path'])
    original=[{'OBS_POST_ID':'DT_A','OBS_ITEM_CODE':'TEMP','OBS_TIME':str(catalog[0]['first_clock']+timedelta(minutes=i)),
      'OBS_VALUE':str(i),'RECEIVE_TIME':str(catalog[0]['first_clock']+timedelta(minutes=i,seconds=10+i))} for i in range(4)]
    pq.write_table(pa.Table.from_pylist(original),path)
    catalog[0].update(source_group='GR_OBS_ST',source_qc_present_rows=0)
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    root=tmp/'receipt'
    packets=receipt_service.calculate_source([{'path':str(path),'sha256':producer.file_hash(path)}],
      'GR_OBS_ST',snapshot.name,path.parent,{'2024-01'})
    receipt_service.publish_packets(packets,root)
    monkeypatch.setattr(receipt_service,'DEFAULT_ROOT',root)
    monkeypatch.setattr(receipt_service,'DATA_ROOT',path.parent)
    monkeypatch.setattr(receipt_service,'receipt_diagnostics',real_receipt_diagnostics)
    result=api.completion('GR_OBS_ST','2024-01','2024-01')
    overview=result['raw']['receipt_diagnostics']
    station=result['raw']['stations'][0]['receipt_diagnostics']
    for summary in (overview,station):
        assert summary['state']=='CALCULATED_NATIVE_CLOCK_DIFFERENCE'
        assert summary['diagnostic_kind']=='SOURCE_CLOCK_DIFFERENCE_NOT_OPERATIONAL_DELAY'
        assert summary['approved'] is False and summary['operational_delay'] is False
        assert summary['comparable_pair_rows']==4
        assert summary['difference_seconds']['mean']==11.5
        assert summary['last_received_clock_raw']=='2024-01-01 00:03:13'
    assert not {'raw','stations','channels'}.intersection(overview)
    assert overview['channel_months']==1
