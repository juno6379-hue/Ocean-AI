"""Recent diagnostics have explicit boundaries and never invent receipt rates."""
from datetime import datetime, timedelta
import hashlib

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.core.config import settings
from app.services import lake_browser as lake
from app.services import observation_operation as operation

CUTOFF=datetime(2026,7,9,15,41,20)
CHANNEL=dict(source_group='SIMULATION',station_code='S',item_code='TEMP',physical_sensor_id='P',depth_step=None,depth_from=None,depth_to=None)


def codebook_evidence():
    from app.services.observation_operation_evidence import evaluate_records
    result=evaluate_records({},['S'],str(CUTOFF),str(CUTOFF-timedelta(days=1)),source='SIMULATION')['S']
    result['qc_semantics']=dict(state='USABLE',source='SIMULATION',source_group='SIMULATION',
        station_code='S',physical_sensor_id='P',item_code='TEMP',field='source_qc_raw',
        clock_basis='NATIVE_SIMULATION',codebook_version='TEST-QC-1',mapping={'G':'GOOD','B':'BAD'},
        effective_start=str(CUTOFF-timedelta(days=3)),effective_end=str(CUTOFF+timedelta(days=1)),
        available_at=str(CUTOFF-timedelta(days=3)),version_available_at=str(CUTOFF-timedelta(days=3)))
    return result


def records(step=60):
    start=CUTOFF-timedelta(days=2)
    return [dict(observed_time_raw=str(start+timedelta(seconds=index*step)),value_raw='0',source_qc_raw='G')
            for index in range(1,172800//step+1)]


def classify(rows, *, evidence=None):
    return operation.classify_channel(operation.summarize_channel(rows,str(CUTOFF),CHANNEL),str(CUTOFF),evidence=evidence)


def test_normal_is_recent_data_flow_with_explicit_unconfirmed_health_and_receipts():
    result=classify(records())
    assert result['state']=='NORMAL'
    assert result['raw_rows']==result['unique_timestamps']==result['finite_unique_timestamps']==1440
    assert result['observed_grid']['expected_slots']==1440
    assert result['observed_grid']['availability_percent']==100
    assert result['collection_rate'] is None and result['equipment_state']=='UNVERIFIED'
    assert result['qc_evidence']=='UNKNOWN' and result['confidence']=='LOW'
    assert result['inspection_missing'] and result['qc_interpretation_missing']
    assert result['window_start']==str(CUTOFF-timedelta(days=1))
    assert result['window_end']==str(CUTOFF)
    assert len(result['policy_hash'])==64


@pytest.mark.parametrize('removed,expected',[(1,'NORMAL'),(10,'WARNING'),(11,'ABNORMAL')])
def test_observed_grid_99_and_90_percent_boundaries(removed,expected):
    rows=records(864)
    # Last clock remains fresh; only the early recent grid has gaps.
    rows=rows[:100]+rows[100+removed:]
    result=classify(rows)
    assert result['observed_grid']['expected_slots']==100
    assert result['observed_grid']['held_slots']==100-removed
    assert result['state']==expected


@pytest.mark.parametrize('missing,expected',[(1,'NORMAL'),(10,'WARNING'),(11,'ABNORMAL')])
def test_finite_fraction_boundaries_use_recent_unique_clocks(missing,expected):
    rows=records(864)
    for row in rows[100:100+missing]:row['value_raw']=None
    result=classify(rows)
    assert result['unique_timestamps']==100
    assert result['finite_unique_timestamps']==100-missing
    assert result['state']==expected


@pytest.mark.parametrize('seconds,expected',[(300,'NORMAL'),(301,'WARNING'),(1800,'WARNING'),(1801,'ABNORMAL')])
def test_latest_age_strict_warning_and_abnormal_boundaries(seconds,expected):
    rows=records()
    shifted=CUTOFF+timedelta(seconds=seconds)
    stats=operation.summarize_channel(rows,str(shifted),CHANNEL)
    result=operation.classify_channel(stats,str(shifted))
    assert result['delay_seconds']==seconds
    assert result['state']==expected


def test_invalid_offset_future_microsecond_and_old_bad_qc_are_excluded():
    rows=records()
    for row in rows[:1440]:row['value_raw']=None;row['source_qc_raw']='B'
    rows.extend([dict(observed_time_raw=str(CUTOFF+timedelta(microseconds=1)),value_raw=None,source_qc_raw='B'),
                 dict(observed_time_raw=str(CUTOFF)+'+09:00',value_raw=None,source_qc_raw='B'),
                 dict(observed_time_raw='invalid',value_raw=None,source_qc_raw='B')])
    evidence=codebook_evidence()
    result=classify(rows,evidence=evidence)
    assert result['state']=='NORMAL'
    assert result['missing_rows']==0 and result['qc_interpreted']=={'GOOD':1440}
    assert result['future_rows_excluded']==1 and result['invalid_clock_rows_excluded']==2


def test_bad_qc_requires_exact_semantics_and_recent_window():
    rows=records()
    for row in rows[-288:]:row['source_qc_raw']='B'
    assert classify(rows)['state']=='NORMAL'
    evidence=codebook_evidence()
    result=classify(rows,evidence=evidence)
    assert result['state']=='ABNORMAL' and result['qc_interpreted']['BAD']==288
    rows[-1]['source_qc_raw']='B '
    exact=classify(rows,evidence=evidence)
    assert exact['qc_interpreted']['UNKNOWN']==1
    assert exact['qc_interpretation_missing'] and exact['qc_evidence']=='UNKNOWN'


def test_duplicates_preserve_raw_rows_but_do_not_inflate_availability():
    rows=records();rows.append(dict(rows[-1]))
    result=classify(rows)
    assert result['raw_rows']==1441 and result['unique_timestamps']==1440
    assert result['observed_grid']['availability_percent']==100 and result['state']=='NORMAL'
    rows.append({**rows[-1],'value_raw':'-1'})
    result=classify(rows)
    assert result['state']=='WARNING' and result['duplicate_conflict_slots']==1


def test_replayed_bad_qc_at_one_clock_does_not_inflate_bad_clock_fraction():
    rows=records()
    bad={**rows[-1],'source_qc_raw':'B'}
    rows.extend([dict(bad) for _ in range(500)])
    result=classify(rows,evidence=codebook_evidence())
    assert result['raw_rows']==1940 and result['unique_timestamps']==1440
    assert result['qc_interpreted']=={'GOOD':1439,'BAD':1}
    assert result['state']=='WARNING'
    assert next(code['count'] for code in result['qc_codes'] if code['literal']=='B')==500


@pytest.mark.parametrize('count,expected',[(1,'WARNING'),(144,'ABNORMAL')])
def test_documented_missing_qc_is_not_treated_as_good(count,expected):
    rows=records()
    for row in rows[-count:]:row['source_qc_raw']='M'
    evidence=codebook_evidence();evidence['qc_semantics']['mapping']['M']='MISSING'
    result=classify(rows,evidence=evidence)
    assert result['state']==expected and result['qc_interpreted']['MISSING']==count


def test_recent_cadence_change_and_multiple_phases_do_not_publish_availability():
    rows=records()
    changed=rows[:1440]+[row for index,row in enumerate(rows[1440:]) if index%5==4]
    result=classify(changed)
    assert result['state']=='WARNING' and result['cadence']['status']=='CADENCE_CHANGED'
    assert result['observed_grid']['availability_percent'] is None
    rows.append(dict(observed_time_raw=str(CUTOFF-timedelta(seconds=30)),value_raw='1',source_qc_raw='G'))
    result=classify(rows)
    assert result['state']=='WARNING' and result['cadence']['status']=='PHASE_UNSTABLE'
    assert result['observed_grid']['expected_slots'] is None
    changed_phase=records()
    for row in changed_phase[1440:]:
        row['observed_time_raw']=str(datetime.fromisoformat(row['observed_time_raw'])-timedelta(seconds=20))
    result=classify(changed_phase)
    assert result['state']=='WARNING' and result['cadence']['status']=='PHASE_CHANGED'
    assert result['observed_grid']['expected_slots'] is None


def test_cadence_minimum_sample_count_and_eighty_percent_dominance_boundaries():
    distribution=[dict(microseconds=60_000_000,count=16),dict(microseconds=120_000_000,count=4)]
    assert operation._cadence(distribution,21,operation.POLICY)['status']=='INFERRED'
    assert operation._cadence(distribution,11,operation.POLICY)['status']=='INSUFFICIENT_CLOCKS'
    distribution[0]['count']=15
    assert operation._cadence(distribution,20,operation.POLICY)['status']=='INTERVAL_MODE_NOT_DOMINANT'


def test_empty_window_prior_stale_and_insufficient_samples_remain_visible():
    assert classify([])['state']=='UNVERIFIED'
    result=classify(records()[:1440])
    assert result['state']=='ABNORMAL' and result['raw_rows']==0
    result=classify(records()[-11:])
    assert result['state']=='WARNING' and result['cadence']['status']=='INSUFFICIENT_CLOCKS'
    assert result['observed_grid']['expected_slots'] is None


def test_station_worst_channel_and_recovery_cannot_clear_live_bad_values():
    normal=classify(records())
    rows=records();rows[-300:]=[{**row,'value_raw':'NaN'} for row in rows[-300:]]
    from app.services.observation_operation_evidence import evaluate_records
    recovered=evaluate_records({'operation_log':[dict(station_id='S',sensor_id='P',event_type='RECOVERY',
        event_time=str(CUTOFF-timedelta(minutes=10)),available_at=str(CUTOFF-timedelta(minutes=10)),
        resolution_of='UNMATCHED',clock_basis='NATIVE_SIMULATION')]},['S'],str(CUTOFF),str(CUTOFF-timedelta(days=1)),source='SIMULATION')['S']
    bad=classify(rows,evidence=recovered)
    result=operation.aggregate_station('S',[normal,bad],str(CUTOFF))
    assert result['state']=='ABNORMAL' and result['channels_evaluated']==2
    result=operation.aggregate_station('S',[normal,classify([])],str(CUTOFF))
    assert result['state']=='WARNING' and result['channels_not_evaluated']==1
    from app.services.observation_operation_evidence import evaluate_records
    event_record=dict(station_id='S',sensor_id='P',event_id='E',event_start=str(CUTOFF-timedelta(minutes=30)),
        event_end=None,status='OPEN',severity='ABNORMAL',available_at=str(CUTOFF-timedelta(minutes=30)),
        version_available_at=str(CUTOFF-timedelta(minutes=30)),clock_basis='NATIVE_SIMULATION')
    evidence=evaluate_records({'event_registry':[event_record]},['S'],str(CUTOFF),str(CUTOFF-timedelta(days=1)),source='SIMULATION')['S']
    event=classify(records(),evidence=evidence)
    assert event['state']=='ABNORMAL'
    event_record['version_available_at']=str(CUTOFF+timedelta(microseconds=1))
    future=evaluate_records({'event_registry':[event_record]},['S'],str(CUTOFF),str(CUTOFF-timedelta(days=1)),source='SIMULATION')['S']
    assert classify(records(),evidence=future)['state']=='NORMAL'


@pytest.mark.parametrize('field,value',[
    ('available_at',str(CUTOFF+timedelta(microseconds=1))),
    ('version_available_at',str(CUTOFF+timedelta(microseconds=1))),
    ('effective_start',str(CUTOFF-timedelta(minutes=30))),
    ('effective_end',str(CUTOFF)),('station_code','OTHER'),('physical_sensor_id','OTHER'),
    ('item_code','SALINITY'),('field','OTHER_FLAG'),('source_group','GD_OBS_VBU'),
    ('clock_basis','UTC_INFERRED'),('codebook_version',None),
])
def test_qc_codebook_must_match_channel_and_full_window_as_of(field,value):
    rows=records()
    for row in rows[-288:]:row['source_qc_raw']='B'
    evidence=codebook_evidence();evidence['qc_semantics'][field]=value
    result=classify(rows,evidence=evidence)
    assert result['state']=='NORMAL'
    assert result['qc_evidence']=='UNKNOWN' and result['qc_interpretation_missing']
    assert result['qc_interpreted']=={}


def test_simulation_codebook_cannot_interpret_live_source_and_wrong_sensor_event_is_ignored():
    rows=records()
    for row in rows[-288:]:row['source_qc_raw']='B'
    stats=operation.summarize_channel(rows,str(CUTOFF),{**CHANNEL,'source_group':'GD_OBS_VBU'})
    result=operation.classify_channel(stats,str(CUTOFF),evidence=codebook_evidence())
    assert result['state']=='NORMAL' and result['qc_evidence']=='UNKNOWN'
    from app.services.observation_operation_evidence import evaluate_records
    event=dict(station_id='S',sensor_id='OTHER',event_id='E',event_start=str(CUTOFF-timedelta(minutes=30)),
        event_end=None,status='OPEN',severity='ABNORMAL',available_at=str(CUTOFF-timedelta(minutes=30)),
        version_available_at=str(CUTOFF-timedelta(minutes=30)),clock_basis='NATIVE_SIMULATION')
    evidence=evaluate_records({'event_registry':[event]},['S'],str(CUTOFF),str(CUTOFF-timedelta(days=1)),source='SIMULATION')['S']
    assert classify(records(),evidence=evidence)['state']=='NORMAL'


def test_cutoff_is_naive_and_microsecond_precise():
    with pytest.raises(Exception):operation.window_bounds('2026-07-09 15:41:20+09:00')
    rows=records();rows[-1]['observed_time_raw']='2026-07-09 15:41:20.000000'
    assert classify(rows)['unique_timestamps']==1440
    rows[-1]['observed_time_raw']='2026-07-09 15:41:20.000001'
    assert classify(rows)['unique_timestamps']==1439


def test_actual_window_scan_preserves_source_depth_and_matches_pure_adapter(tmp_path,monkeypatch):
    rows=records()
    source=tmp_path/'vbu.parquet';other=tmp_path/'bu.parquet'
    native=dict(OBS_POST_ID=['S']*len(rows),OBS_ITEM_CODE=['TEMP']*len(rows),
        OBS_TIME=[row['observed_time_raw'] for row in rows],OBS_VALUE=[row['value_raw'] for row in rows],
        QC_FLAG=[row['source_qc_raw'] for row in rows],WATER_STEP=[None]*len(rows))
    deep=dict(OBS_POST_ID=['S']*12,OBS_ITEM_CODE=['TEMP']*12,
        OBS_TIME=[str(CUTOFF-timedelta(seconds=i*60)) for i in range(12)],OBS_VALUE=['999']*12,
        QC_FLAG=['B']*12,WATER_STEP=['2']*12)
    pq.write_table(pa.concat_tables([pa.table(native).cast(pa.schema([('OBS_POST_ID',pa.string()),('OBS_ITEM_CODE',pa.string()),('OBS_TIME',pa.string()),('OBS_VALUE',pa.string()),('QC_FLAG',pa.string()),('WATER_STEP',pa.string())])),pa.table(deep)]),source)
    pq.write_table(pa.table(deep),other)
    pq.write_table(pa.table({'unused':[1]}),tmp_path/'station-item-month-validation.parquet')
    authority=tmp_path/'file-only-timeseries.duckdb'
    with duckdb.connect(str(authority)) as db:
        db.execute('CREATE TABLE source_assets(parquet_path VARCHAR,source_group VARCHAR,source_path VARCHAR,source_sha256 VARCHAR,parquet_sha256 VARCHAR)')
        for path,group in [(source,'GD_OBS_VBU'),(other,'GD_OBS_BU')]:
            db.execute('INSERT INTO source_assets VALUES(?,?,?,?,?)',[str(path),group,group+'_202607.csv','a'*64,hashlib.sha256(path.read_bytes()).hexdigest()])
    monkeypatch.setattr(settings,'SHARE_MONTHLY_LAKE_ROOT',str(tmp_path))
    monkeypatch.setattr(settings,'MONTHLY_REPORT_MATCHING_ROOT',str(tmp_path/'work'))
    assets,signatures,sha,census=operation._source_identity(tmp_path,'GD_OBS_VBU',str(CUTOFF))
    actual=operation._cached_window(str(tmp_path),'GD_OBS_VBU',str(CUTOFF),tuple(signatures),sha,census,operation.RECIPE_HASH)
    assert len(assets)==1 and len(actual)==2
    shallow=next(row for row in actual if row['depth_step'] is None)
    deep=next(row for row in actual if row['depth_step']=='2')
    assert shallow['raw_rows']==shallow['unique_timestamps']==1440 and deep['raw_rows']==12
    expected=operation.summarize_channel(rows,str(CUTOFF),CHANNEL)
    for key in ('raw_rows','unique_timestamps','finite_unique_timestamps','missing_rows','nonfinite_rows','nonnumeric_rows','duplicate_rows','interval_distribution','phase_distribution','history_interval_distribution','history_phase_distribution'):
        assert shallow[key]==expected[key]
    assert operation.classify_channel(shallow,str(CUTOFF))['state']=='NORMAL'
    assert shallow['qc_codes']==[dict(field='QC_FLAG',literal='G',count=1440)]
    assert deep['source_group']=='GD_OBS_VBU'
