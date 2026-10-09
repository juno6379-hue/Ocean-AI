import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.services.native_receipt_diagnostics import (
    ReceiptDiagnosticError, calculate_field_absence_coverage, calculate_source, canonical_bytes, parse_clock, read_json,
    pooled_stats, publish_packets, receipt_diagnostics, sha_file, validate_packet,
    weighted_quantile,
)


@pytest.fixture(autouse=True)
def trusted_test_source_root(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.native_receipt_diagnostics.DATA_ROOT", tmp_path)
    monkeypatch.setattr("app.services.native_receipt_diagnostics.CATALOG_ROOT", tmp_path)


def source(tmp_path, rows, group="GD_OBS_BU"):
    path = tmp_path / f"{group}.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=2)
    return [{"path": str(path), "sha256": sha_file(path)}]


def row(observed="2026-07-01 00:00:00", received="2026-07-01 00:03:05", station="TW1", item="AIR_PRES", **extra):
    return {"OBS_POST_ID": station, "OBS_ITEM_CODE": item, "OBS_TIME": observed, "RECEIVE_TIME": received, **extra}


def frozen(tmp_path, rows, group="GD_OBS_BU"):
    entries = source(tmp_path, rows, group)
    packets = calculate_source(entries, group, "test-snapshot", tmp_path, {"2026-07"})
    root = tmp_path / "output"
    receipts = publish_packets(packets, root)
    return packets, receipts, root


@pytest.mark.parametrize("value,kind", [
    (None,"NULL"),(" ","NULL"),("2026-07-01","INVALID"),
    ("2026-02-30 00:00:00","INVALID"),("2026-07-01 00:00:00garbage","INVALID"),
    ("2026-07-01T00:00:00.0000001","INVALID"),(123,"INVALID"),
    ("2026-07-01 24:00:00","INVALID"),("2026-07-01 00:00:60","INVALID"),
    ("2026-07-01T00:00:00+24:00","INVALID"),("0000-07-01 00:00:00","INVALID"),
    ("2026-07-01 00:00:00","NAIVE_NATIVE"),("2026-07-01T00:00:00+09:00","EXPLICIT_OFFSET")])
def test_clock_has_no_inferred_midnight_timezone_or_precision(value,kind):
    assert parse_clock(value)[0] == kind


def test_signed_distribution_and_filtered_percentiles_pool_actual_pairs(tmp_path):
    rows=[row(received="2026-06-30 23:59:50"), row(received="2026-07-01 00:00:00"),
          row(received="2026-07-01 00:00:10"), row(received="2026-07-01 00:01:40",item="WATER_TEMP")]
    packets, receipts, root=frozen(tmp_path,rows)
    actual=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)
    assert actual["raw"]["difference_seconds"]=={"min":-10,"max":100,"mean":25,"p50":5,"p95":pytest.approx(86.5)}
    assert actual["raw"]["negative_difference_rows"]==1
    filtered=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",item="AIR_PRES",snapshot="test-snapshot",root=root)
    assert filtered["raw"]["difference_seconds"]["p95"]==pytest.approx(9)
    assert actual["stations"][0]["receipt_diagnostics"]["difference_seconds"]==actual["raw"]["difference_seconds"]
    assert actual["operational_delay"] is False and actual["approved"] is False
    assert packets[0]["channels"][0]["last_received"]["source"]["row_index"] in (0,1)


def test_null_invalid_and_mixed_pair_are_preserved_not_zero_imputed(tmp_path):
    packets, _, root=frozen(tmp_path,[row(received=None),row(received="bad"),
                                    row(received="2026-07-01T00:00:00+09:00"),
                                    row(observed="2026-07-99 00:00:00"),row()])
    value=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)["raw"]
    assert value["raw_rows"]==5 and value["comparable_pair_rows"]==1
    assert value["receipt_null_rows"]==1 and value["receipt_invalid_rows"]==1
    assert value["observation_invalid_rows"]==1 and value["clock_mixed_pair_rows"]==1
    assert value["difference_seconds"]["mean"]==185
    assert any(x["source"]["receipt_clock_raw"]=="bad" for x in packets[0]["channels"][0]["examples"])


def test_aware_offsets_exact_arithmetic_and_no_native_aware_pool(tmp_path):
    packets,_,root=frozen(tmp_path,[row("2026-07-01T09:00:00+09:00","2026-07-01T00:03:05Z"),row()])
    value=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)["raw"]
    assert value["state"]=="MIXED_CLOCK_REPRESENTATIONS"
    assert value["difference_seconds"] is None
    assert value["comparable_pair_rows"]==2


def test_vbu_missing_field_and_type_sensitive_depths(tmp_path):
    rows=[{k:v for k,v in row(**{"WATER_STEP":depth,"FR_DEPTH":None,"TO_DEPTH":"0"}).items() if k!="RECEIVE_TIME"} for depth in [None,"0",""]]
    packets,_,root=frozen(tmp_path,rows,"GD_OBS_VBU")
    actual=receipt_diagnostics("GD_OBS_VBU","2026-07","2026-07",snapshot="test-snapshot",root=root)
    assert len(actual["channels"])==3
    assert actual["state"]=="FIELD_ABSENT" and actual["raw"]["receipt_null_rows"] is None
    assert actual["raw"]["receipt_field_absent_rows"]==3
    assert actual["raw"]["difference_seconds"] is None


def test_sqlplus_metadata_excluded_padding_only_identifier_transform(tmp_path):
    rows=[{"station_raw":"DT_0001 ","item_raw":"AIR_PRES  ","time_raw":"2026-07-01 00:00:00","record_class":"OBSERVATION_SHAPED_UNVALIDATED"},
          {"station_raw":"----","item_raw":"------","time_raw":"-------------","record_class":"SQLPLUS_METADATA"}]
    packets,_,root=frozen(tmp_path,rows,"GD_OBS_ST_MONTHLY")
    assert packets[0]["raw"]["raw_rows"]==1
    assert packets[0]["channels"][0]["station_code"]=="DT_0001"
    assert packets[0]["raw"]["state"]=="FIELD_ABSENT"


def test_packet_tamper_source_tamper_and_unknown_month_do_not_return_metrics(tmp_path):
    packets,receipts,root=frozen(tmp_path,[row()])
    assert receipt_diagnostics("GD_OBS_BU","2026-08","2026-08",snapshot="test-snapshot",root=root)["state"]=="UNAVAILABLE_PERIOD"
    path=Path(receipts[0]["packet_path"])
    original=path.read_bytes(); path.write_bytes(original+b" ")
    actual=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)
    assert actual["state"]=="INVALID_PACKET" and actual["error_code"]=="PACKET_CHECKSUM_MISMATCH"
    path.write_bytes(original)
    sourcepath=tmp_path/"GD_OBS_BU.parquet";sourcepath.write_bytes(sourcepath.read_bytes()+b" ")
    actual=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)
    assert actual["state"]=="INVALID_PACKET" and actual["error_code"]=="SOURCE_CHECKSUM_MISMATCH"


def test_scope_include_exclude_and_invalid_pointer_path(tmp_path):
    _,receipts,root=frozen(tmp_path,[row(station="A"),row(station="B")])
    included=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",station_scope={"include":["B"]},snapshot="test-snapshot",root=root)
    assert [x["station_code"] for x in included["stations"]]==["B"]
    excluded=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",station_scope={"exclude":["B"]},snapshot="test-snapshot",root=root)
    assert [x["station_code"] for x in excluded["stations"]]==["A"]
    pointer=Path(receipts[0]["packet_path"]).parent/"published.json"
    body=json.loads(pointer.read_bytes());body["packet_path"]="../../evil.json";pointer.write_bytes(canonical_bytes(body))
    assert receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)["error_code"]=="POINTER_INVALID"


def test_immutable_pointer_and_histogram_integrity(tmp_path):
    packets,_,root=frozen(tmp_path,[row()])
    packet=json.loads(canonical_bytes(packets[0]));packet["generated_at"]="changed"
    with pytest.raises(ReceiptDiagnosticError,match="IMMUTABLE_POINTER_EXISTS"):
        publish_packets([packet],root)
    packet=json.loads(canonical_bytes(packets[0]));packet["channels"][0]["difference_histogram"][0]["count"]=2
    with pytest.raises(ReceiptDiagnosticError,match="HISTOGRAM_COUNT_MISMATCH"):
        validate_packet(packet)


def test_history_native_month_preserves_raw_clock_without_utc(tmp_path):
    entries=source(tmp_path,[{"station_id_raw":"DT_0001","station_id_candidate":"DT_0001","item_code_raw":"VEG","observed_at_raw":"2000-01-01 00:00:00","received_at_raw":"2000-01-01 00:01:00"}],"HISTORICAL_RECONCILED")
    packets=calculate_source(entries,"HISTORICAL_RECONCILED","test-snapshot",tmp_path)
    assert packets[0]["month"]=="2000-01" and packets[0]["raw"]["difference_seconds"]["mean"]==60
    assert packets[0]["method"]["clock_timezone_inferred"] is False


def test_nested_malformed_input_and_untrusted_source_root_are_structured(tmp_path):
    packets,receipts,root=frozen(tmp_path,[row()])
    assert receipt_diagnostics([],"2026-07","2026-07",snapshot="test-snapshot",root=root)["state"]=="UNAVAILABLE"
    assert receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",station_scope={"include":[{}]},snapshot="test-snapshot",root=root)["state"]=="INVALID_SCOPE"
    pointer=Path(receipts[0]["packet_path"]).parent/"published.json"
    original=pointer.read_bytes();pointer.write_bytes(b"[]")
    assert receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)["error_code"]=="POINTER_INVALID"
    pointer.write_bytes(original)
    assert receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root,source_root=tmp_path/"other")["error_code"]=="SOURCE_ROOT_MISMATCH"


def test_mixed_clock_last_received_does_not_compare_unconfirmed_timezones(tmp_path):
    _,_,root=frozen(tmp_path,[row(),row("2026-07-01T09:00:00+09:00","2026-07-01T00:04:00Z")])
    value=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)["raw"]
    assert value["difference_seconds"] is None and value["last_received_clock_raw"] is None


def test_sql_parser_does_not_normalize_24_hour_or_leap_second_literals(tmp_path):
    packets,_,root=frozen(tmp_path,[row(observed="2026-07-01 24:00:00"),row(received="2026-07-01 00:00:60"),row()])
    value=receipt_diagnostics("GD_OBS_BU","2026-07","2026-07",snapshot="test-snapshot",root=root)["raw"]
    assert value["observation_invalid_rows"]==1 and value["receipt_invalid_rows"]==1
    assert value["comparable_pair_rows"]==1


def test_history_candidate_station_cannot_replace_raw_literal(tmp_path):
    entries=source(tmp_path,[{"station_id_raw":"78","station_id_candidate":"DT_0001","item_code_raw":"dt_apress","observed_at_raw":"2013-01-01 00:00:00","received_at_raw":None}],"HISTORICAL_RECONCILED")
    packets=calculate_source(entries,"HISTORICAL_RECONCILED","test-snapshot",tmp_path)
    root=tmp_path/"out";publish_packets(packets,root)
    actual=receipt_diagnostics("HISTORICAL_RECONCILED","2013-01","2013-01",snapshot="test-snapshot",root=root)
    assert actual["stations"][0]["station_code"]=="78"
    assert actual["state"]=="NO_COMPARABLE_PAIRS" and actual["raw"]["receipt_null_rows"]==1


def test_path_confinement_is_checked_before_parquet_read(tmp_path):
    entries=source(tmp_path,[row()])
    with pytest.raises(ReceiptDiagnosticError,match="PATH_OUTSIDE_ROOT"):
        calculate_source(entries,"GD_OBS_BU","test-snapshot",tmp_path/"another")


def test_impossible_huge_counts_or_clock_deltas_rejected(tmp_path):
    packets,_,_=frozen(tmp_path,[row()])
    packet=json.loads(canonical_bytes(packets[0]));packet["channels"][0]["raw_rows"]=10**400
    with pytest.raises(ReceiptDiagnosticError,match="COUNT_INVALID"):
        validate_packet(packet)
    packet=json.loads(canonical_bytes(packets[0]));packet["channels"][0]["difference_histogram"][0]["microseconds"]=10**400
    with pytest.raises(ReceiptDiagnosticError,match="HISTOGRAM_INVALID"):
        validate_packet(packet)


@pytest.mark.parametrize("data,code",[(b'{"x":1,"x":2}',"JSON_DUPLICATE_KEY"),(b'{"x":NaN}',"JSON_NONFINITE"),(b'{"x":Infinity}',"JSON_NONFINITE"),(b'{"x":1e400}',"JSON_NONFINITE")])
def test_strict_json_rejects_duplicate_or_nonfinite_values(tmp_path,data,code):
    path=tmp_path/'input.json';path.write_bytes(data)
    with pytest.raises(ReceiptDiagnosticError,match=code):read_json(path,tmp_path)


def test_last_clock_rejects_self_inconsistent_ticks_or_literal(tmp_path):
    packets,_,_=frozen(tmp_path,[row()])
    packet=json.loads(canonical_bytes(packets[0]));packet["channels"][0]["last_received"]["microseconds"]+=1
    with pytest.raises(ReceiptDiagnosticError,match="LAST_CLOCK_LITERAL_BINDING_MISMATCH"):validate_packet(packet)
    packet=json.loads(canonical_bytes(packets[0]));packet["channels"][0]["last_received"]["source"]["receipt_clock_raw"]='different'
    with pytest.raises(ReceiptDiagnosticError,match="LAST_CLOCK_LITERAL_BINDING_MISMATCH"):validate_packet(packet)


def test_schema_only_other_month_absence_and_catalog_tamper(tmp_path):
    import duckdb
    from datetime import datetime
    entries=source(tmp_path,[{k:v for k,v in row(observed='2026-06-01 00:00:00').items() if k!='RECEIVE_TIME'}],"GD_OBS_VBU")
    snapshot=tmp_path/'test-snapshot';snapshot.mkdir()
    path=snapshot/'file-only-timeseries.duckdb';db=duckdb.connect(str(path))
    db.execute('create table source_assets(source_group varchar,source_path varchar,parquet_path varchar,parquet_sha256 varchar)')
    db.execute('insert into source_assets values (?,?,?,?)',['GD_OBS_VBU','GD_OBS_VBU_202606.csv',entries[0]['path'],entries[0]['sha256']]);db.close()
    catalog=[{'source_group':'GD_OBS_VBU','station_code':'TW1','item_code':'AIR_PRES','depth_step':None,'depth_from':None,'depth_to':None,'month':'2026-06-01','held_rows':1,'first_clock':datetime(2026,6,1),'last_clock':datetime(2026,6,1)}]
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    packets=calculate_field_absence_coverage(snapshot,tmp_path,sources=['GD_OBS_VBU'])
    root=tmp_path/'out';publish_packets(packets,root)
    result=receipt_diagnostics('GD_OBS_VBU','2026-06','2026-06',snapshot='test-snapshot',root=root)
    assert result['state']=='FIELD_ABSENT' and result['raw']['raw_rows']==1
    assert packets[0]['channels'][0]['catalog_last_clock']=='2026-06-01 00:00:00'
    assert result['raw']['difference_seconds'] is None and result['raw']['observation_invalid_rows'] is None
    assert result['raw']['last_observed_clock_raw'] is None
    p=snapshot/'station-item-month-validation.parquet';p.write_bytes(p.read_bytes()+b' ')
    assert receipt_diagnostics('GD_OBS_VBU','2026-06','2026-06',snapshot='test-snapshot',root=root)['error_code']=='CATALOG_DEPENDENCY_CHANGED'


def test_schema_only_absence_rejects_a_real_receipt_column(tmp_path):
    import duckdb
    entries=source(tmp_path,[row()],"GD_OBS_VBU")
    snapshot=tmp_path/'test-snapshot';snapshot.mkdir()
    db=duckdb.connect(str(snapshot/'file-only-timeseries.duckdb'))
    db.execute('create table source_assets(source_group varchar,source_path varchar,parquet_path varchar,parquet_sha256 varchar)')
    db.execute('insert into source_assets values (?,?,?,?)',['GD_OBS_VBU','GD_OBS_VBU_202606.csv',entries[0]['path'],entries[0]['sha256']]);db.close()
    pq.write_table(pa.Table.from_pylist([{'source_group':'GD_OBS_VBU','month':'2026-06','held_rows':1}]),snapshot/'station-item-month-validation.parquet')
    with pytest.raises(ReceiptDiagnosticError,match='RECEIPT_FIELD_ABSENCE_CONTRADICTED'):
        calculate_field_absence_coverage(snapshot,tmp_path,sources=['GD_OBS_VBU'])


def test_all_month_cli_real_row_scan_catalog_binding_and_idempotent_resume(tmp_path):
    import duckdb
    from types import SimpleNamespace
    from app.scripts.calculate_native_receipt_diagnostics import native_receipt_coverage
    entries=source(tmp_path,[row(observed='2026-06-01 00:00:00',received='2026-06-01 00:03:00')])
    snapshot=tmp_path/'test-snapshot';snapshot.mkdir()
    db=duckdb.connect(str(snapshot/'file-only-timeseries.duckdb'))
    db.execute('create table source_assets(source_group varchar,source_path varchar,parquet_path varchar,parquet_sha256 varchar)')
    db.execute('insert into source_assets values (?,?,?,?)',['GD_OBS_BU','GD_OBS_BU_202606.csv',entries[0]['path'],entries[0]['sha256']]);db.close()
    catalog=[{'source_group':'GD_OBS_BU','station_code':'TW1','item_code':'AIR_PRES','depth_step':None,'depth_from':None,'depth_to':None,'month':'2026-06','held_rows':1}]
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    args=SimpleNamespace(snapshot_path=snapshot,snapshot='test-snapshot',sources=['GD_OBS_BU'],output_root=tmp_path/'out',source_root=tmp_path)
    first=native_receipt_coverage(args)
    assert first['new_packet_count']==1 and first['new_packets'][0]['raw']['difference_seconds']['mean']==180
    second=native_receipt_coverage(args)
    assert second['new_packet_count']==0 and len(second['preserved_packets'])==1
    args.output_root=tmp_path/'bad-out';catalog[0]['held_rows']=2
    pq.write_table(pa.Table.from_pylist(catalog),snapshot/'station-item-month-validation.parquet')
    with pytest.raises(ValueError,match='ACTUAL_RECEIPT_ROW_COUNTS_NOT_BOUND_TO_CATALOG'):
        native_receipt_coverage(args)
