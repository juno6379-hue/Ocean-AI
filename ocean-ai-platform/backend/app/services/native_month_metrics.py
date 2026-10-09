"""Bounded, read-only Parquet diagnostics. No inferred schedule, UTC or QC approval."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import calendar
import hashlib
import json
import os
import re
import time
import uuid
import duckdb
import pyarrow.parquet as pq

SOURCES = ('GD_OBS_ST_MONTHLY','GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST')
KEYS = ('station_code','item_code','depth_step','depth_from','depth_to')
MONTH_RE = re.compile(r'^20\d{2}-(0[1-9]|1[0-2])$')

def now(): return datetime.now(timezone.utc).isoformat()
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def file_hash(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
LOADED_RECIPE_SHA256 = file_hash(Path(__file__))
def dump(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def fetch(connection,query,params=None):
    cursor=connection.execute(query,params or [])
    return [dict(zip([d[0] for d in cursor.description],r)) for r in cursor.fetchall()]
def quote(name): return '"'+name.replace('"','""')+'"'
def typed_key(row):
    return tuple((type(row.get(key)).__name__,row.get(key)) for key in KEYS)
def month_bounds(month):
    if not MONTH_RE.fullmatch(month): raise ValueError('INVALID_NATIVE_MONTH')
    year,mon=map(int,month.split('-'))
    start=datetime(year,mon,1)
    end=datetime(year+1,1,1) if mon==12 else datetime(year,mon+1,1)
    return start,end,int((end-start).total_seconds()*1000000)
def asset_month(asset):
    basename=str(asset['source_path']).replace('\\','/').split('/')[-1]
    found=re.findall(r'(?<!\d)(20\d{2}(?:0[1-9]|1[0-2]))(?!\d)',basename)
    if len(found)!=1: raise ValueError('SOURCE_ASSET_MONTH_AMBIGUOUS')
    return found[0][:4]+'-'+found[0][4:]

def grid(month,intervals,phases,duplicate_rows):
    """Unique positive mode, exact unanimous phase, whole calendar denominator."""
    start,end,duration=month_bounds(month)
    result={'status':'INSUFFICIENT_POSITIVE_INTERVALS','expected_slots':None,'held_slots':None,
      'representative_interval_microseconds':None,'phase_microseconds':None,
      'positive_interval_distribution':intervals,'phase_distribution':phases,
      'month_start_native_literal':str(start),'month_end_native_exclusive_literal':str(end),
      'duplicate_timestamp_rows_excluded':duplicate_rows,'off_grid_rows':None,'off_grid_unique_timestamps':None,
      'approved_sampling_contract':False,'timezone_approved':False,'operational_period_approved':False,
      'round_or_snap_applied':False,'holding_fraction_percent':None}
    if not intervals: return result
    count=max(r['count'] for r in intervals)
    modes=[r['microseconds'] for r in intervals if r['count']==count]
    result['interval_mode_candidates_microseconds']=modes
    if len(modes)!=1: result['status']='INTERVAL_MODE_AMBIGUOUS';return result
    interval=modes[0];result['representative_interval_microseconds']=interval
    if not phases:result['status']='PHASE_EVIDENCE_MISSING';return result
    maximum=max(r['unique_timestamp_count'] for r in phases)
    modes=[r['microseconds'] for r in phases if r['unique_timestamp_count']==maximum]
    result['phase_mode_candidates_microseconds']=modes
    if len(modes)!=1:result['status']='PHASE_MODE_AMBIGUOUS';return result
    phase=modes[0]
    expected=(duration-1-phase)//interval+1 if phase<duration else 0
    main=next(r for r in phases if r['microseconds']==phase)
    result['phase_microseconds']=phase
    result['candidate_phase_accounting']={'expected_slots':expected,'held_slots':main['unique_timestamp_count'],
      'off_reference_unique_timestamps':sum(r['unique_timestamp_count'] for r in phases if r['microseconds']!=phase),
      'off_reference_rows':sum(r['raw_rows'] for r in phases if r['microseconds']!=phase),
      'usable_for_holding_fraction':len(phases)==1,'holding_fraction_percent':None}
    if len(phases)!=1:result['status']='PHASE_UNSTABLE_MULTIPLE_REMAINDERS';return result
    held=main['unique_timestamp_count']
    if not 0<=held<=expected or expected<=0:raise ValueError('NATIVE_GRID_DENOMINATOR_INCONSISTENT')
    result.update(status='CALCULATED_NATIVE_FULL_MONTH_HOLDING_GRID_DIAGNOSTIC_UNAPPROVED',
      expected_slots=expected,held_slots=held,off_grid_rows=0,off_grid_unique_timestamps=0,
      holding_fraction_percent=100*held/expected)
    return result

def verify_asset(asset):
    path=Path(asset['parquet_path']);before=path.stat();started=now()
    value=file_hash(path)
    if value!=asset['parquet_sha256']:raise ValueError('SOURCE_PARQUET_HASH_OR_STAT_CHANGED')
    q=pq.ParquetFile(path);after=path.stat()
    if value!=asset['parquet_sha256'] or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('SOURCE_PARQUET_HASH_OR_STAT_CHANGED')
    return {'path':str(path),'sha256':value,'bytes':after.st_size,'mtime_ns':after.st_mtime_ns,
      'footer_rows':q.metadata.num_rows,'source_group':asset['source_group'],
      'source_csv_sha256_historical_not_rechecked':asset['source_sha256'],
      'source_csv_current_preservation_asserted':False,'hash_started_at':started,'hash_finished_at':now(),
      'schema':[{'column':f.name,'arrow_type':str(f.type)} for f in q.schema_arrow]}

def compute_month(snapshot,source,month,assets,catalog_rows,work,emit=None):
    if source not in SOURCES:raise ValueError('UNSUPPORTED_SOURCE_SCHEMA')
    started=now();begin=time.monotonic();start,end,duration=month_bounds(month)
    snapshot=Path(snapshot)
    catalog_path=snapshot/'station-item-month-validation.parquet';assets_path=snapshot/'file-only-timeseries.duckdb'
    catalog_sha=file_hash(catalog_path);assets_sha=file_hash(assets_path)
    frozen_catalog=[r for r in pq.read_table(catalog_path).to_pylist() if r['source_group']==source and str(r['month'])[:7]==month]
    if len({typed_key(r) for r in catalog_rows})!=len(catalog_rows) or len({typed_key(r) for r in frozen_catalog})!=len(frozen_catalog):
        raise ValueError('DUPLICATE_TYPED_CATALOG_GRAIN')
    if {typed_key(r):r for r in frozen_catalog}!={typed_key(r):r for r in catalog_rows}:
        raise ValueError('CALLER_CATALOG_ROWS_NOT_BOUND_TO_SNAPSHOT')
    with duckdb.connect(str(assets_path),read_only=True) as authority:
        frozen_assets=fetch(authority,'SELECT * FROM source_assets')
    # Only exact frozen source-asset membership for the requested native file month.
    selected=[a for a in assets if a['source_group']==source and asset_month(a)==month]
    if not selected:raise ValueError('NO_SOURCE_FILES_FOR_MONTH')
    frozen_assets=[a for a in frozen_assets if a['source_group']==source and asset_month(a)==month]
    if len({a['parquet_path'] for a in selected})!=len(selected) or len({a['parquet_path'] for a in frozen_assets})!=len(frozen_assets):
        raise ValueError('DUPLICATE_SOURCE_ASSET_PATH')
    fields=('source_group','source_path','parquet_path','source_sha256','parquet_sha256')
    if sorted(tuple(a[f] for f in fields) for a in selected)!=sorted(tuple(a[f] for f in fields) for a in frozen_assets):
        raise ValueError('CALLER_SOURCE_ASSETS_NOT_BOUND_TO_SNAPSHOT')
    if file_hash(catalog_path)!=catalog_sha or file_hash(assets_path)!=assets_sha:
        raise ValueError('SNAPSHOT_CHANGED_WHILE_READING')
    files=[verify_asset(a) for a in selected]
    if emit:emit('HASHED',source=source,month=month,files=len(files),bytes=sum(f['bytes'] for f in files))
    schemas={tuple((v['column'],v['arrow_type']) for v in f['schema']) for f in files}
    if len(schemas)!=1:raise ValueError('SOURCE_SCHEMA_VARIANTS_REQUIRE_EXPLICIT_ADAPTER')
    columns={v['column'] for v in files[0]['schema']}
    qc_fields=[f for f in ('qc_raw','mq_raw','n1_aqc_raw') if f in columns] if source=='GD_OBS_ST_MONTHLY' else sorted(f for f in columns if f.endswith('_FLAG'))
    primary='qc_raw' if source=='GD_OBS_ST_MONTHLY' and 'qc_raw' in columns else 'QC_FLAG' if source!='GD_OBS_ST_MONTHLY' and 'QC_FLAG' in columns else None
    station,item,clock,value=('station_raw','item_raw','time_raw','value_raw') if source=='GD_OBS_ST_MONTHLY' else ('OBS_POST_ID','OBS_ITEM_CODE','OBS_TIME','OBS_VALUE')
    if not {station,item,clock,value}<=columns:raise ValueError('SOURCE_REQUIRED_COLUMNS_MISSING')
    where=" WHERE record_class='OBSERVATION_SHAPED_UNVALIDATED'" if source=='GD_OBS_ST_MONTHLY' else ''
    depths=['NULL::VARCHAR']*3 if source=='GD_OBS_ST_MONTHLY' else [quote(f) if f in columns else 'NULL::VARCHAR' for f in ('WATER_STEP','FR_DEPTH','TO_DEPTH')]
    if source!='GD_OBS_ST_MONTHLY' and 'FROM_DEPTH' in columns:
        if 'FR_DEPTH' in columns:raise ValueError('DEPTH_COLUMN_ALIAS_NEEDS_EXPLICIT_SOURCE_CONTRACT')
        depths[1]=quote('FROM_DEPTH')
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    connection=duckdb.connect(':memory:',config={'threads':2,'memory_limit':'512MB'})
    try:
        connection.execute('SET temp_directory=?',[str(work)])
        connection.execute('SET preserve_insertion_order=false')
        connection.read_parquet([f['path'] for f in files],hive_partitioning=False).create_view('parquet_source')
        excluded=fetch(connection,'SELECT record_class,count(*) row_count FROM parquet_source GROUP BY record_class') if source=='GD_OBS_ST_MONTHLY' else []
        fields=[f'trim({quote(station)}) station_code',f'trim({quote(item)}) item_code']+[f'{field} {name}' for field,name in zip(depths,KEYS[2:])]
        native_pattern=r'[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?'
        native=f"CASE WHEN regexp_full_match(CAST({quote(clock)} AS VARCHAR),'{native_pattern}') THEN try_cast({quote(clock)} AS TIMESTAMP) ELSE NULL END"
        fields += [f'{quote(value)} value_literal',f'try_cast({quote(value)} AS DOUBLE) parsed_number',
           f'{quote(clock)} clock_literal',f'try_cast({quote(clock)} AS TIMESTAMP) legacy_parsed_clock',f'{native} native_clock']+[quote(f) for f in qc_fields]
        connection.execute('CREATE TEMP VIEW normalized AS SELECT '+','.join(fields)+' FROM parquet_source'+where)
        key_sql=','.join(KEYS)
        counts=fetch(connection,f'''SELECT {key_sql},count(*) raw_rows,
          count(*) FILTER(WHERE value_literal IS NULL OR trim(value_literal)='') missing_value_rows,
          count(*) FILTER(WHERE parsed_number IS NOT NULL AND isfinite(parsed_number)) numeric_rows,
          count(*) FILTER(WHERE parsed_number IS NOT NULL AND NOT isfinite(parsed_number)) nonfinite_numeric_rows,
          count(*) FILTER(WHERE parsed_number IS NULL AND value_literal IS NOT NULL AND trim(value_literal)<>'') nonnumeric_value_rows,
          count(*) FILTER(WHERE legacy_parsed_clock IS NULL) invalid_time_rows,
          count(*) FILTER(WHERE legacy_parsed_clock IS NOT NULL AND native_clock IS NULL) unsupported_clock_representation_rows,
          count(*) FILTER(WHERE native_clock IS NOT NULL AND (native_clock<? OR native_clock>=?)) outside_month_rows,
          min(native_clock) first_native_clock,max(native_clock) last_native_clock
          FROM normalized GROUP BY {key_sql} ORDER BY {key_sql}''',[start,end])
        connection.execute(f'CREATE TEMP TABLE grains AS SELECT row_number() OVER(ORDER BY {key_sql}) grain_id,{key_sql} FROM normalized GROUP BY {key_sql}')
        join=' AND '.join(f'n.{k} IS NOT DISTINCT FROM g.{k}' for k in KEYS)
        connection.execute('CREATE TEMP VIEW keyed AS SELECT g.grain_id,n.* FROM normalized n JOIN grains g ON '+join)
        ids={typed_key(r):r['grain_id'] for r in fetch(connection,'SELECT * FROM grains')}
        codes=defaultdict(list)
        if qc_fields:
            query='SELECT grain_id,field,literal,count(*) count FROM keyed CROSS JOIN LATERAL (VALUES '+','.join(f"('{f}',{quote(f)})" for f in qc_fields)+') q(field,literal) GROUP BY grain_id,field,literal ORDER BY grain_id,field,literal'
            for r in fetch(connection,query):codes[r.pop('grain_id')].append(r)
        connection.execute('CREATE TEMP TABLE points AS SELECT grain_id,native_clock,count(*) raw_timestamp_rows FROM keyed WHERE native_clock>=? AND native_clock<? GROUP BY grain_id,native_clock',[start,end])
        points={r.pop('grain_id'):r for r in fetch(connection,'''SELECT grain_id,count(*) unique_valid_month_timestamps,
          sum(raw_timestamp_rows) valid_month_rows,sum(raw_timestamp_rows-1) duplicate_timestamp_rows,
          min(native_clock) first_month_native_clock,max(native_clock) last_month_native_clock FROM points GROUP BY grain_id''')}
        intervals=defaultdict(list)
        for r in fetch(connection,'''WITH delta AS (SELECT grain_id,epoch_us(native_clock)-epoch_us(lag(native_clock) OVER(PARTITION BY grain_id ORDER BY native_clock)) delta_us FROM points)
          SELECT grain_id,delta_us,count(*) count FROM delta WHERE delta_us>0 GROUP BY grain_id,delta_us ORDER BY grain_id,delta_us'''):
            r['microseconds']=r.pop('delta_us')
            intervals[r.pop('grain_id')].append(r)
        modes=[]
        for gid,distribution in intervals.items():
            maximum=max(r['count'] for r in distribution);choices=[r['microseconds'] for r in distribution if r['count']==maximum]
            if len(choices)==1:modes.append((gid,choices[0]))
        connection.execute('CREATE TEMP TABLE modal_intervals(grain_id BIGINT,interval_us BIGINT)')
        if modes:connection.executemany('INSERT INTO modal_intervals VALUES (?,?)',modes)
        phases=defaultdict(list)
        for r in fetch(connection,'''SELECT p.grain_id,(epoch_us(p.native_clock)-epoch_us(?::TIMESTAMP))%m.interval_us phase_us,
          count(*) unique_timestamp_count,sum(p.raw_timestamp_rows) raw_rows FROM points p JOIN modal_intervals m ON p.grain_id=m.grain_id
          GROUP BY p.grain_id,phase_us ORDER BY p.grain_id,phase_us''',[start]):
            r['microseconds']=r.pop('phase_us');phases[r.pop('grain_id')].append(r)
        baseline={typed_key(r):r for r in catalog_rows}
        actual={typed_key(r):r for r in counts}
        if set(actual)!={k for k,v in baseline.items() if v.get('held_rows')}:
            raise ValueError('ACTUAL_GRAIN_MEMBERSHIP_DIFFERS_FROM_FROZEN_CATALOG')
        output=[]
        for key in sorted(set(baseline)|set(actual),key=repr):
            saved=baseline[key];row=actual.get(key);gid=ids.get(key)
            if row:
                if row['raw_rows']!=saved['held_rows']:raise ValueError('RAW_ROW_COUNT_DIFFERS_FROM_FROZEN_CATALOG')
                for field in ('missing_value_rows','numeric_rows','invalid_time_rows'):
                    if saved.get(field) is not None and saved[field]!=row[field]:raise ValueError('RAW_VALUE_COUNT_DIFFERS_FROM_FROZEN_CATALOG')
                row={k:str(v) if isinstance(v,datetime) else v for k,v in row.items()}
                row.update({k:str(v) if isinstance(v,datetime) else int(v) for k,v in points.get(gid,{}).items()})
                for field in ('valid_month_rows','unique_valid_month_timestamps','duplicate_timestamp_rows'):row.setdefault(field,0)
                qc=codes.get(gid,[])
                present=sum(v['count'] for v in qc if v['field']==primary and v['literal'] is not None and str(v['literal']).strip()!='') if primary else None
                if primary and saved.get('source_qc_present_rows') is not None and saved['source_qc_present_rows']!=present:
                    raise ValueError('QC_PRESENCE_DIFFERS_FROM_FROZEN_CATALOG')
                row.update(month=month,source_group=source,source_qc_present_rows=present,
                  source_qc_field_state='PRESENT' if primary else 'ABSENT',source_qc_primary_field=primary,
                  qc_codes=qc,grid=grid(month,intervals.get(gid,[]),phases.get(gid,[]),row['duplicate_timestamp_rows']),
                  report_refs=[],calculation_state='FULL_NATIVE_PARQUET_DIAGNOSTICS',source_QC_codes_interpreted=False)
                if row['unsupported_clock_representation_rows']:
                    row['grid'].update(status='CLOCK_REPRESENTATION_UNVERIFIED',expected_slots=None,held_slots=None,holding_fraction_percent=None)
            else:
                row={k:saved[k] for k in KEYS}
                row.update(month=month,source_group=source,raw_rows=0,missing_value_rows=0,numeric_rows=0,
                  invalid_time_rows=0,source_qc_present_rows=None,source_qc_field_state='NO_ROWS',source_qc_primary_field=primary,
                  qc_codes=[],unique_valid_month_timestamps=0,duplicate_timestamp_rows=0,
                  grid={'status':'NO_CURRENT_HELD_ROWS','expected_slots':None,'held_slots':None},report_refs=[],
                  calculation_state='CATALOG_REFERENCE_ONLY')
            row['channel_sha256']=digest(row);output.append(row)
        metadata=sum(v['row_count'] for v in excluded if v['record_class']!='OBSERVATION_SHAPED_UNVALIDATED')
        footer=sum(f['footer_rows'] for f in files)
        if sum(r['raw_rows'] for r in output)+metadata!=footer:raise ValueError('FOOTER_OBSERVATION_METADATA_RECONCILIATION_FAILED')
        # Repeat complete source bytes after computation; no stat-only publication claim.
        for f in files:
            p=Path(f['path']);s=p.stat()
            if (s.st_size,s.st_mtime_ns)!=(f['bytes'],f['mtime_ns']) or file_hash(p)!=f['sha256']:
                raise ValueError('SOURCE_PARQUET_CHANGED_DURING_CALCULATION')
        if file_hash(catalog_path)!=catalog_sha or file_hash(assets_path)!=assets_sha:
            raise ValueError('SNAPSHOT_CHANGED_DURING_CALCULATION')
        return {'schema_version':'native-month-metric-packet-1','approved':False,'production_eligible':False,
          'snapshot':Path(snapshot).name,'source_group':source,'month':month,'generated_at':now(),
          'started_at':started,'elapsed_seconds':time.monotonic()-begin,'channels':output,
          'source_files':files,'source_file_verification':{'files':len(files),'bytes':sum(f['bytes'] for f in files),
            'footer_rows':footer,'actual_observation_rows':sum(r['raw_rows'] for r in output),'non_observation_rows':metadata,
            'sha256_before_and_after_all_files':True,'source_csv_current_preservation_asserted':False},
          'catalog_sha256':catalog_sha,'source_assets_sha256':assets_sha,
          'recipe_sha256':LOADED_RECIPE_SHA256,'recipe_source_file_changed_during_run':file_hash(Path(__file__))!=LOADED_RECIPE_SHA256,
          'clock_semantics':'NATIVE_SOURCE_LITERAL_WITHOUT_TIMEZONE_APPROVAL',
          'deduplication':'EXACT_TIMESTAMP_PER_SOURCE_MONTH_STATION_ITEM_TYPED_DEPTH_ONLY',
          'source_unit_scale_datum_QC_sensor_period_sampling_approved':False}
    finally:connection.close()

def publish_packet(root,packet):
    """Publish only a technical diagnostic; immutable bytes plus atomic small pointer."""
    directory=Path(root)/packet['snapshot']/packet['source_group']/packet['month']
    directory.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(packet,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    sha=hashlib.sha256(raw).hexdigest();name='packet-'+sha+'.json';path=directory/name
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('IMMUTABLE_DIAGNOSTIC_PUBLICATION_CONFLICT')
    else:
        with path.open('xb') as stream:stream.write(raw)
    marker={'schema_version':'native-month-metric-publication-1','packet_file':name,'sha256':sha,
      'snapshot':packet['snapshot'],'source_group':packet['source_group'],'month':packet['month'],
      'approved':False,'generated_at':packet['generated_at']}
    temporary=directory/('published.pending-'+uuid.uuid4().hex+'.json')
    dump(temporary,marker);os.replace(temporary,directory/'published.json')
    return {'path':str(path),'sha256':sha,'publication_path':str(directory/'published.json')}
