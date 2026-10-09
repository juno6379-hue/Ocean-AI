"""Actual native-clock day cutoffs, distinct from complete-month publications.

The cutoff is inclusive through the day in the source's unapproved naive clock.
It never relabels later values, invents a timezone, or writes approval/serving DBs.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, time
from pathlib import Path
import json
import os
import threading
import uuid
import re
import duckdb
from fastapi import HTTPException
from app.core.config import settings
from app.services import lake_browser as lake, metric_completion as metrics
from app.services.native_month_metrics import KEYS, SOURCES, asset_month, typed_key, file_hash, digest, fetch, quote, month_bounds, grid, verify_asset, now

RECIPE_SHA=file_hash(__file__)
_locks=defaultdict(threading.Lock)
NATIVE_PATTERN=r'[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?'
OPERATION_UNVERIFIED=dict(state='UNVERIFIED',collection_rate=None,
    reason='파일 보유 자료만으로 기준일의 장비 운영상태·예정 관측건수를 확정할 수 없습니다.')

def day_bounds(month, as_of_day, as_of_time=None):
    day=date.fromisoformat(str(as_of_day))
    start,end,_=month_bounds(month)
    cutoff=datetime.combine(day+timedelta(days=1),datetime.min.time())
    if as_of_time is not None:
        clock=time.fromisoformat(str(as_of_time))
        if clock.tzinfo:raise HTTPException(422,'기준시각은 offset 없는 원문 시계 기준입니다.')
        cutoff=datetime.combine(day,clock)+timedelta(microseconds=1)
    end=min(end,cutoff)
    if end<=start:raise HTTPException(422,'조회 월은 관측 기준일 이후일 수 없습니다.')
    return start,end,int((end-start).total_seconds()*1_000_000)

def compute_month(view,source,month,as_of_day,saved,as_of_time=None):
    start,end,duration=day_bounds(month,as_of_day,as_of_time)
    catalog=view/'station-item-month-validation.parquet';authority=view/'file-only-timeseries.duckdb'
    catalog_sha,authority_sha=file_hash(catalog),file_hash(authority)
    assets=[a for a in lake.monthly_assets(str(authority),authority.stat().st_mtime_ns) if a['source_group']==source and asset_month(a)==month]
    root=lake.historical_root() if source=='GD_OBS_ST_MONTHLY' else Path(settings.SHARE_MONTHLY_LAKE_ROOT)
    for a in assets:lake.inside(root,a['parquet_path'])
    if not assets:raise HTTPException(503,'기준일 재산정에 필요한 보존 원천 파일이 없습니다.')
    try:files=[verify_asset(a) for a in assets]
    except ValueError:raise HTTPException(409,'원천 파일 해시가 검증 카탈로그와 다릅니다.')
    schemas={tuple((f['column'],f['arrow_type']) for f in a['schema']) for a in files}
    if len(schemas)!=1:raise ValueError('ASOF_SOURCE_SCHEMA_VARIANTS')
    cols={f['column'] for f in files[0]['schema']}
    station,item,clock,value=('station_raw','item_raw','time_raw','value_raw') if source=='GD_OBS_ST_MONTHLY' else ('OBS_POST_ID','OBS_ITEM_CODE','OBS_TIME','OBS_VALUE')
    qc_fields=[f for f in ('qc_raw','mq_raw','n1_aqc_raw') if f in cols] if source=='GD_OBS_ST_MONTHLY' else sorted(f for f in cols if f.endswith('_FLAG'))
    primary='qc_raw' if source=='GD_OBS_ST_MONTHLY' and 'qc_raw' in cols else 'QC_FLAG' if 'QC_FLAG' in cols else None
    depths=['NULL::VARCHAR']*3 if source=='GD_OBS_ST_MONTHLY' else [quote(f) if f in cols else 'NULL::VARCHAR' for f in ('WATER_STEP','FR_DEPTH','TO_DEPTH')]
    if 'FROM_DEPTH' in cols:
        if 'FR_DEPTH' in cols:raise ValueError('ASOF_AMBIGUOUS_DEPTH_ALIAS')
        depths[1]=quote('FROM_DEPTH')
    work=Path(settings.MONTHLY_REPORT_MATCHING_ROOT)/'asof-metrics'/'work'/uuid.uuid4().hex
    work.mkdir(parents=True,exist_ok=True)
    c=duckdb.connect(':memory:',config={'threads':2,'memory_limit':'768MB'})
    try:
        c.execute('SET temp_directory=?',[str(work)])
        c.execute('SET preserve_insertion_order=false')
        c.read_parquet([f['path'] for f in files],hive_partitioning=False).create_view('parquet_source')
        fields=[f'trim({quote(station)}) station_code',f'trim({quote(item)}) item_code']+[f'{v} {k}' for v,k in zip(depths,KEYS[2:])]
        fields += [f'{quote(value)} value_literal',f'try_cast({quote(value)} AS DOUBLE) parsed_number',f"CASE WHEN regexp_full_match(CAST({quote(clock)} AS VARCHAR),'{NATIVE_PATTERN}') THEN try_cast({quote(clock)} AS TIMESTAMP) END native_clock"]+[quote(f) for f in qc_fields]
        where=" WHERE record_class='OBSERVATION_SHAPED_UNVALIDATED'" if source=='GD_OBS_ST_MONTHLY' else ''
        c.execute('CREATE TEMP VIEW normalized AS SELECT '+','.join(fields)+' FROM parquet_source'+where)
        keys=','.join(KEYS)
        full=fetch(c,f'SELECT {keys},count(*) raw_rows FROM normalized GROUP BY {keys}')
        if {typed_key(r):r['raw_rows'] for r in full}!={typed_key(r):r['held_rows'] for r in saved if r['held_rows']>0}:
            raise ValueError('ASOF_FULL_SOURCE_CATALOG_MISMATCH')
        unlocatable=c.execute('SELECT count(*) FROM normalized WHERE native_clock IS NULL').fetchone()[0]
        c.execute('CREATE TEMP VIEW active AS SELECT * FROM normalized WHERE native_clock>=TIMESTAMP '+"'"+str(start)+"'"+' AND native_clock<TIMESTAMP '+"'"+str(end)+"'")
        counts=fetch(c,f'''SELECT {keys},count(*) raw_rows,
          count(*) FILTER(WHERE value_literal IS NULL OR trim(value_literal)='') missing_value_rows,
          count(*) FILTER(WHERE parsed_number IS NOT NULL AND isfinite(parsed_number)) numeric_rows,
          min(native_clock) first_native_clock,max(native_clock) last_native_clock
          FROM active GROUP BY {keys} ORDER BY {keys}''')
        c.execute(f'CREATE TEMP TABLE grains AS SELECT row_number() OVER(ORDER BY {keys}) grain_id,{keys} FROM active GROUP BY {keys}')
        join=' AND '.join(f'n.{k} IS NOT DISTINCT FROM g.{k}' for k in KEYS)
        c.execute('CREATE TEMP VIEW keyed AS SELECT g.grain_id,n.* FROM active n JOIN grains g ON '+join)
        ids={typed_key(r):r['grain_id'] for r in fetch(c,'SELECT * FROM grains')}
        codes=defaultdict(list)
        if qc_fields:
            qc_sql='SELECT grain_id,field,literal,count(*) count FROM keyed CROSS JOIN LATERAL (VALUES '+','.join(f"('{f}',{quote(f)})" for f in qc_fields)+') q(field,literal) GROUP BY grain_id,field,literal ORDER BY grain_id,field,literal'
            for r in fetch(c,qc_sql):codes[r.pop('grain_id')].append(r)
        c.execute('CREATE TEMP TABLE points AS SELECT grain_id,native_clock,count(*) raw_timestamp_rows FROM keyed GROUP BY grain_id,native_clock')
        points={r.pop('grain_id'):r for r in fetch(c,'SELECT grain_id,count(*) unique_valid_month_timestamps,sum(raw_timestamp_rows-1) duplicate_timestamp_rows FROM points GROUP BY grain_id')}
        intervals=defaultdict(list)
        for r in fetch(c,'''WITH deltas AS (SELECT grain_id,epoch_us(native_clock)-epoch_us(lag(native_clock) OVER(PARTITION BY grain_id ORDER BY native_clock)) delta_us FROM points)
            SELECT grain_id,delta_us,count(*) count FROM deltas WHERE delta_us>0 GROUP BY grain_id,delta_us ORDER BY grain_id,delta_us'''):
            r['microseconds']=r.pop('delta_us');intervals[r.pop('grain_id')].append(r)
        modes=[]
        for gid,values in intervals.items():
            maximum=max(v['count'] for v in values);choices=[v['microseconds'] for v in values if v['count']==maximum]
            if len(choices)==1:modes.append((gid,choices[0]))
        c.execute('CREATE TEMP TABLE modes(grain_id BIGINT,interval_us BIGINT)')
        if modes:c.executemany('INSERT INTO modes VALUES (?,?)',modes)
        phases=defaultdict(list)
        for r in fetch(c,'''SELECT p.grain_id,(epoch_us(native_clock)-epoch_us(?::TIMESTAMP))%m.interval_us phase_us,
            count(*) unique_timestamp_count,sum(raw_timestamp_rows) raw_rows FROM points p JOIN modes m USING(grain_id)
            GROUP BY p.grain_id,phase_us ORDER BY p.grain_id,phase_us''',[start]):
            r['microseconds']=r.pop('phase_us');phases[r.pop('grain_id')].append(r)
        channels=[]
        for r in counts:
            gid=ids[typed_key(r)];r.update(points[gid]);r['grid']=grid(month,intervals[gid],phases[gid],r['duplicate_timestamp_rows'])
            g=r['grid'];interval=g.get('representative_interval_microseconds');phase=g.get('phase_microseconds')
            # A rejected phase candidate still belongs to this cutoff period;
            # its reference denominator must not silently retain the full month.
            expected=None
            if interval is not None and phase is not None:
                expected=(duration-1-phase)//interval+1 if phase<duration else 0
                if 'candidate_phase_accounting' in g:
                    g['candidate_phase_accounting'].update(expected_slots=expected)
            if g.get('expected_slots') is not None:
                if not 0<=g['held_slots']<=expected or expected<=0:raise ValueError('ASOF_GRID_DENOMINATOR_INCONSISTENT')
                g.update(expected_slots=expected,holding_fraction_percent=100*g['held_slots']/expected,status='CALCULATED_NATIVE_DAY_CUTOFF_UNAPPROVED')
            g.update(period_end_native_exclusive=str(end),as_of_day=str(as_of_day),as_of_time=as_of_time,
                whole_calendar_month_denominator=end==month_bounds(month)[1])
            qc=codes[gid]
            r.update(month=month,source_group=source,source_qc_primary_field=primary,source_qc_field_state='PRESENT' if primary else 'ABSENT',
                source_qc_present_rows=sum(v['count'] for v in qc if v['field']==primary and v['literal'] is not None and str(v['literal']).strip()) if primary else None,
                qc_codes=qc,invalid_time_rows=0,report_refs=[],calculation_state='FULL_NATIVE_PARQUET_DIAGNOSTICS')
            for field in ('first_native_clock','last_native_clock'):r[field]=str(r[field])
            channels.append(r)
        for f in files:
            p=Path(f['path']);stat=p.stat()
            if (stat.st_size,stat.st_mtime_ns)!=(f['bytes'],f['mtime_ns']) or file_hash(p)!=f['sha256']:raise ValueError('ASOF_SOURCE_CHANGED_DURING_SCAN')
        if file_hash(catalog)!=catalog_sha or file_hash(authority)!=authority_sha:raise ValueError('ASOF_AUTHORITY_CHANGED_DURING_SCAN')
        return dict(schema_version='observation-day-packet-1',snapshot=view.name,source=source,month=month,as_of_day=str(as_of_day),
            as_of_time=as_of_time,period_end_native_exclusive=str(end),approved=False,operational_delay=False,timezone_inferred=False,
            recipe_sha256=RECIPE_SHA,catalog_sha256=catalog_sha,source_assets_sha256=authority_sha,source_files=files,
            unlocatable_clock_rows_excluded=unlocatable,generated_at=now(),channels=channels)
    finally:c.close()

def partial_packet(view,source,month,as_of_day,saved,catalog_sha,as_of_time=None):
    day_bounds(month,as_of_day,as_of_time)
    # Short names also work on Windows hosts without long-path support.
    scope_hash=digest([str(view.resolve()),source,month,str(as_of_day),as_of_time,RECIPE_SHA])
    directory=Path(settings.MONTHLY_REPORT_MATCHING_ROOT)/'asof-metrics'/scope_hash[:32]
    with _locks[str(directory)]:
        pointer=directory/'published.json'
        if not pointer.is_file():
            packet=compute_month(view,source,month,as_of_day,saved,as_of_time)
            directory.mkdir(parents=True,exist_ok=True)
            raw=(json.dumps(packet,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode();sha=__import__('hashlib').sha256(raw).hexdigest();name='packet-'+sha[:24]+'.json'
            if not (directory/name).exists():
                with (directory/name).open('xb') as stream:stream.write(raw)
            elif file_hash(directory/name)!=sha:raise ValueError('ASOF_EXISTING_PACKET_CORRUPT')
            pending=directory/('published.pending-'+uuid.uuid4().hex+'.json')
            pending.write_text(json.dumps(dict(packet=name,sha256=sha)),encoding='utf-8');os.replace(pending,pointer)
        marker=json.loads(pointer.read_text(encoding='utf-8'));name=marker['packet']
        if not re.fullmatch('[0-9a-f]{64}',marker['sha256']) or name!='packet-'+marker['sha256'][:24]+'.json':raise ValueError('ASOF_PACKET_PATH_INVALID')
        path=directory/name
        if file_hash(path)!=marker['sha256']:raise HTTPException(409,'기준일 진단 패킷 checksum 불일치')
        packet=json.loads(path.read_text(encoding='utf-8'))
        if (packet['snapshot'],packet['source'],packet['month'],packet['as_of_day'],packet.get('as_of_time'),packet['recipe_sha256'])!=(view.name,source,month,str(as_of_day),as_of_time,RECIPE_SHA):
            raise HTTPException(409,'기준일 진단 코드·범위가 변경되어 재산정이 필요합니다.')
        if packet['approved'] is not False or packet['catalog_sha256']!=catalog_sha or packet['source_assets_sha256']!=file_hash(view/'file-only-timeseries.duckdb'):
            raise HTTPException(409,'기준일 진단의 카탈로그·파일 목록 불일치')
        authority=view/'file-only-timeseries.duckdb'
        assets={str(Path(a['parquet_path']).resolve()):a for a in lake.monthly_assets(str(authority),authority.stat().st_mtime_ns) if a['source_group']==source and asset_month(a)==month}
        if {str(Path(a['path']).resolve()) for a in packet['source_files']}!=set(assets):raise ValueError('ASOF_ASSET_MEMBERSHIP_CHANGED')
        root=lake.historical_root() if source=='GD_OBS_ST_MONTHLY' else Path(settings.SHARE_MONTHLY_LAKE_ROOT)
        for f in packet['source_files']:
            p=lake.inside(root,f['path']);stat=p.stat()
            if f['sha256']!=assets[str(p.resolve())]['parquet_sha256'] or (stat.st_size,stat.st_mtime_ns)!=(f['bytes'],f['mtime_ns']):raise HTTPException(409,'기준일 재산정 후 원천 변경')
            lake.verify_file(str(p),stat.st_mtime_ns,stat.st_size,f['sha256'])
        return packet

def selected_rows(source,start,end,as_of_day,station='',item='',station_scope=None,as_of_time=None):
    if source not in SOURCES:raise HTTPException(422,'과거 정산 원천은 월 단위 조회를 사용하세요.')
    if start>end or end>str(as_of_day)[:7]:raise HTTPException(422,'조회 기간은 관측 기준일이 속한 월까지 선택하세요.')
    view,_=lake.context();census,evidence=metrics.catalog_counts(view,source);rows=[];unlocatable=0
    for month in metrics.calendar_months(start,end):
        saved=[r for r in census if str(r['month'])[:7]==month]
        if not any(r['held_rows'] for r in saved):continue
        packet=None
        if month<str(as_of_day)[:7]:
            packet,_=metrics.native_packet(view,source,month,saved,evidence['sha256'])
            if packet and any(r.get('invalid_time_rows',0) or r.get('unsupported_clock_representation_rows',0) or r.get('outside_month_rows',0) for r in packet['channels']):packet=None
        if packet is None:packet=partial_packet(view,source,month,as_of_day,saved,evidence['sha256'],as_of_time)
        unlocatable+=packet.get('unlocatable_clock_rows_excluded',0)
        def matches_scope(code):
            if station_scope is None:return True
            if 'include' in station_scope:return code in station_scope['include']
            return code not in station_scope['exclude']
        rows.extend(r for r in packet['channels'] if r['raw_rows']>0 and (not station or r['station_code']==station) and (not item or r['item_code']==item) and matches_scope(r['station_code']))
    names={r['station_code']:r.get('station_name') for r in census}
    if file_hash(view/'station-item-month-validation.parquet')!=evidence['sha256']:raise HTTPException(409,'기준일 집계 중 카탈로그 변경')
    return view,rows,names,unlocatable

def overview(source,start,end,as_of_day,station_scope=None,as_of_time=None):
    view,rows,names,excluded=selected_rows(source,start,end,as_of_day,station_scope=station_scope,as_of_time=as_of_time)
    groups=defaultdict(list)
    for r in rows:groups[r['station_code']].append(r)
    def summary(group):return dict(items=len({r['item_code'] for r in group}),held_rows=sum(r['raw_rows'] for r in group),
        first_clock=min((r['first_native_clock'] for r in group),default=None),last_clock=max((r['last_native_clock'] for r in group),default=None),held_months=len({r['month'] for r in group}))
    by_month=defaultdict(int)
    for r in rows:by_month[r['month']]+=r['raw_rows']
    return dict(source=source,snapshot=view.name,from_month=start,to_month=end,as_of_day=str(as_of_day),as_of_time=as_of_time,totals=dict(stations=len(groups),**summary(rows)),
        stations=[dict(station_code=code,station_name=names.get(code),operation=OPERATION_UNVERIFIED,**summary(group)) for code,group in sorted(groups.items())],
        operation_summary=dict(normal=None,warning=None,abnormal=None,collection_rate=None,unclassified=len(groups),reason=OPERATION_UNVERIFIED['reason']),
        monthly=[dict(month=month,held_rows=count) for month,count in sorted(by_month.items())],storage='PARQUET',approval_status='UNAPPROVED',simulated_included=False,
        unlocatable_clock_rows_excluded=excluded,cutoff_basis='NATIVE_OBSERVATION_CLOCK_INCLUSIVE_DAY')

def station_detail(station,source,start,end,as_of_day,as_of_time=None):
    view,rows,_,_=selected_rows(source,start,end,as_of_day,station=station,as_of_time=as_of_time)
    return dict(station_code=station,source=source,snapshot=view.name,as_of_day=str(as_of_day),as_of_time=as_of_time,timezone=None,approval_status='UNAPPROVED',
        months=[dict(r,held_rows=r['raw_rows'],first_clock=r['first_native_clock'],last_clock=r['last_native_clock']) for r in rows])

def completion(source,start,end,as_of_day,station='',item='',station_scope=None,as_of_time=None):
    view,rows,_,excluded=selected_rows(source,start,end,as_of_day,station,item,station_scope,as_of_time)
    raw=metrics.raw_metrics(rows)
    reason='원문 관측시각 기준 '+str(as_of_day)+' '+(as_of_time or '일 종료')+'까지의 달력 격자입니다. 승인 수집률이 아닙니다.'
    for grid_value in [raw['grid']]+[r['grid'] for r in raw['stations']]:grid_value.update(reason=reason,as_of_day=str(as_of_day),as_of_time=as_of_time)
    return dict(state='AVAILABLE' if rows else 'EMPTY_SCOPE',source=source,from_month=start,to_month=end,as_of_day=str(as_of_day),as_of_time=as_of_time,snapshot=view.name,
        scope=dict(station=station,item=item,station_scope_applied=station_scope is not None),raw=raw,
        report_reference=dict(status='NOT_APPLICABLE_TO_DAY_CUTOFF',normal_rates=[],unweighted_reference_mean_percent=None,numeric_reference_values=0,excluded_reference_values=0,reason='월간 보고서 전체 월 인쇄값을 기준일 통계로 재사용하지 않습니다.'),
        blocked_metrics=metrics.BLOCKED,limitations=[reason,'원문 시각을 변경하거나 시간대를 임의 적용하지 않습니다. 시각 해석 불가·offset 표현은 기준일 자료에서 제외합니다.'],
        unlocatable_clock_rows_excluded=excluded,calculation_coverage=dict(selected_held_months=len({r['month'] for r in rows}),fully_scanned_held_months=len({r['month'] for r in rows}),grid_applies_to_full_selected_scope=raw['grid']['scope_is_full_selection']))
