"""Read raw observations and their evidence without synthesizing metadata.

Monthly coverage is a reconciled snapshot, not an operational uptime measure.
Series queries select one source/month/channel, preserve duplicate rows, and
verify every returned Parquet asset against its manifest. No MDC connection.
"""
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
import calendar
import json
import math
import threading

import duckdb
import pyarrow.parquet as pq
from fastapi import HTTPException
from app.api.routes_foundation import snapshot, inside, verify_file
from app.core.config import settings

SOURCES = ['GD_OBS_ST_MONTHLY', 'GD_OBS_BU', 'GD_OBS_VBU', 'GR_OBS_ST', 'HISTORICAL_RECONCILED']


@contextmanager
def connection():
    # Each request owns a bounded read-only query; never share mutable cursors.
    c = duckdb.connect(':memory:', config={'threads': 2, 'memory_limit': '512MB'})
    c.execute("SET temp_directory = ''")
    timer = threading.Timer(45, c.interrupt)
    timer.start()
    try:
        yield c
    except duckdb.InterruptException:
        raise HTTPException(504, '조회 제한시간 초과: 관측소·항목·월 범위를 확인하세요.')
    finally:
        timer.cancel()
        c.close()


def records(cursor):
    names = [x[0] for x in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def context():
    _, view = snapshot()
    path = view/'station-item-month-validation.parquet'
    if not path.is_file() or not (view/'file-only-timeseries.duckdb').is_file():
        raise HTTPException(503, '정산된 조회 카탈로그가 아직 준비되지 않았습니다.')
    return view, path


def historical_root():
    return Path(settings.INTEGRATED_LAKE_ROOT).resolve()


@lru_cache(maxsize=4)
def history_catalog(root_text, manifest_mtime):
    root = Path(root_text)
    manifest = json.loads((root/'metadata/raw/manifest.json').read_text(encoding='utf8'))
    if manifest.get('status') != 'RAW_ONLY':
        raise HTTPException(409, '과거 원천층의 정산 상태를 확인해야 합니다.')
    assets, coverage = [], []
    for entry in manifest['files']:
        # Only the explicit reconciled contract is readable. Legacy HOLD stays HOLD.
        if not entry['path'].startswith('raw/reconciled_v1/'):
            continue
        p = inside(root, root/entry['path'])
        q = pq.ParquetFile(p)
        if q.metadata.num_rows != entry['rows']:
            raise HTTPException(409, '과거 원천 Parquet 행 수 불일치')
        first = next(q.iter_batches(batch_size=1)).to_pylist()[0]
        time_index = q.schema_arrow.get_field_index('source_clock_naive')
        stats = [q.metadata.row_group(i).column(time_index).statistics for i in range(q.num_row_groups)]
        starts = [s.min for s in stats if s and s.has_min_max]
        ends = [s.max for s in stats if s and s.has_min_max]
        asset = {**entry, 'parquet_path': str(p), 'parquet_sha256': entry['sha256'],
                 'source_group': 'HISTORICAL_RECONCILED', 'station_code': first['station_id_raw'],
                 'item_code': first['item_code_raw'], 'month': entry['month_raw_clock']}
        assets.append(asset)
        coverage.append({'source_group': 'HISTORICAL_RECONCILED', 'station_code': first['station_id_raw'],
                         'station_name': None, 'item_code': first['item_code_raw'],
                         'depth_step': None, 'depth_from': None, 'depth_to': None,
                         'month': entry['month_raw_clock']+'-01', 'held_rows': entry['rows'],
                         'first_clock': min(starts) if starts else None, 'last_clock': max(ends) if ends else None,
                         'overall_decision': '근거 부족', 'physical_sensor_id': None,
                         'standard_unit': None, 'timezone_name': None, 'approval_status': 'UNAPPROVED'})
    return assets, coverage


def history():
    root = historical_root()
    p = root/'metadata/raw/manifest.json'
    if not p.is_file():
        return [], []
    return history_catalog(str(root), p.stat().st_mtime_ns)


def register_coverage(c, source):
    import pyarrow as pa
    view, p = context()
    # A published matching snapshot supplies PostgreSQL evidence. Never join a
    # newer/older snapshot to these files; a not-yet-published snapshot uses its
    # own reconciled Parquet registry. Observation values remain in the lake.
    if settings.LAKE_WEB_POSTGRES_CATALOG:
        from app.core.database import engine
        from sqlalchemy import text
        with engine.connect() as db:
            exists = db.execute(text("SELECT to_regclass('lake_serving.channel_month')")).scalar()
            if exists:
                saved = db.execute(text('SELECT evidence FROM lake_serving.channel_month WHERE snapshot_id=:s AND source_group=:g ORDER BY row_number'),{'s':view.name,'g':source}).scalars().all()
                if saved:
                    c.register('coverage',pa.Table.from_pylist(saved))
                    return view
    if source == 'HISTORICAL_RECONCILED':
        _, rows = history()
        if not rows:
            raise HTTPException(503, '정산된 과거 원천 카탈로그 없음')
        c.register('coverage', pa.Table.from_pylist(rows))
    else:
        c.read_parquet(str(p)).create_view('coverage')
    return view


def predicate(source, start, end, station=None):
    sql = 'source_group=? AND cast(month as varchar)>=? AND cast(month as varchar)<=?'
    args = [source, start+'-01', end+'-31']
    if station:
        sql += ' AND station_code=?'
        args.append(station)
    return sql, args


def overview(source, start, end, station_scope=None):
    with connection() as c:
        view = register_coverage(c, source)
        where, args = predicate(source, start, end)
        from app.services.station_classification import sql_scope
        extra, extra_args=sql_scope(station_scope)
        where+=extra;args+=extra_args
        totals = records(c.execute(f'''SELECT count(distinct station_code) stations,
          count(distinct item_code) items, coalesce(sum(held_rows),0)::BIGINT held_rows,
          min(first_clock) first_clock,max(last_clock) last_clock,
          count(distinct month) held_months FROM coverage WHERE {where}''', args))[0]
        stations = records(c.execute(f'''SELECT station_code,max(station_name) station_name,
          count(distinct item_code) items,sum(held_rows)::BIGINT held_rows,
          min(first_clock) first_clock,max(last_clock) last_clock,
          count(distinct month) held_months FROM coverage WHERE {where}
          GROUP BY station_code ORDER BY station_code''', args))
        monthly = records(c.execute(f'''SELECT cast(month as varchar) AS "month",sum(held_rows)::BIGINT held_rows
          FROM coverage WHERE {where} GROUP BY month ORDER BY month''', args))
    return {'source': source, 'snapshot': view.name, 'from_month': start, 'to_month': end,
            'sources': SOURCES, 'totals': totals, 'stations': stations, 'monthly': monthly,
            'storage': 'PARQUET', 'approval_status': 'UNAPPROVED', 'simulated_included': False,
            'legacy_status': 'HOLD: legacy 전체와 2011~2021 전 관측소 연결은 별도 정산 필요',
            'note': '원천별 보유 행 수입니다. 중복을 제거한 고유 관측 수·가동률·QC 정상률이 아닙니다.'}


def station_detail(station, source, start, end):
    with connection() as c:
        view = register_coverage(c, source)
        where, args = predicate(source, start, end, station)
        rows = records(c.execute(f'''SELECT * FROM coverage WHERE {where}
                     ORDER BY item_code,depth_step,depth_from,depth_to,month''', args))
    return {'station_code': station, 'source': source, 'snapshot': view.name, 'months': rows,
            'approval_status': 'UNAPPROVED', 'timezone': None}


@lru_cache(maxsize=4)
def monthly_assets(catalog, modified):
    with duckdb.connect(catalog, read_only=True) as c:
        return records(c.execute('SELECT * FROM source_assets'))


def series(source, month, station, item, depth, limit, offset, tail=False,as_of_day=None,as_of_time=None):
    cutoff_end=None
    if as_of_day:
        from app.services.observation_asof import day_bounds,NATIVE_PATTERN
        _,cutoff_end,_=day_bounds(month,as_of_day,as_of_time)
    view, _ = context()
    catalog = view/'file-only-timeseries.duckdb'
    if source == 'HISTORICAL_RECONCILED':
        all_assets, _ = history()
        assets = [a for a in all_assets if a['month']==month and a['station_code']==station and a['item_code']==item]
    else:
        assets = [a for a in monthly_assets(str(catalog), catalog.stat().st_mtime_ns)
                  if a['source_group']==source and month.replace('-','') in Path(a['source_path']).name]
    if not assets:
        return {'rows': [], 'has_more': False, 'source': source, 'month': month,'station':station,'item':item,'tail':tail,
                'offset':offset,'limit':limit,'snapshot':view.name,'as_of_day':as_of_day,'as_of_time':as_of_time,
                'approval_status': 'UNAPPROVED'}
    root = historical_root() if source in ('HISTORICAL_RECONCILED','GD_OBS_ST_MONTHLY') else Path(settings.SHARE_MONTHLY_LAKE_ROOT)
    paths = [str(inside(root, a['parquet_path'])) for a in assets]
    with connection() as c:
        c.read_parquet(paths, hive_partitioning=False, filename=True, file_row_number=True, union_by_name=True).create_view('raw_files')
        cols = {x[0] for x in c.execute('describe raw_files').fetchall()}
        def col(name):
            return '"'+name+'"' if name in cols else 'NULL::VARCHAR'
        if source == 'GD_OBS_ST_MONTHLY':
            select = "trim(station_raw) station_code,trim(item_raw) item_code,time_raw observed_time_raw,value_raw,qc_raw source_qc_raw,mq_raw source_mq_raw,n1_aqc_raw source_n1_qc_raw,NULL::VARCHAR received_time_raw,NULL::VARCHAR depth_step,NULL::VARCHAR depth_from,NULL::VARCHAR depth_to"
            extra = "WHERE record_class='OBSERVATION_SHAPED_UNVALIDATED'"
        elif source == 'HISTORICAL_RECONCILED':
            select = 'station_id_raw station_code,item_code_raw item_code,observed_at_raw observed_time_raw,value_raw,qc1_raw source_qc_raw,qc2_raw source_mq_raw,NULL::VARCHAR source_n1_qc_raw,received_at_raw received_time_raw,NULL::VARCHAR depth_step,NULL::VARCHAR depth_from,NULL::VARCHAR depth_to'
            extra = ''
        else:
            if 'FROM_DEPTH' in cols and 'FR_DEPTH' in cols:raise HTTPException(409,'원천의 수심 별칭이 충돌합니다.')
            from_depth='FROM_DEPTH' if 'FROM_DEPTH' in cols else 'FR_DEPTH'
            select = 'trim(OBS_POST_ID) station_code,trim(OBS_ITEM_CODE) item_code,OBS_TIME observed_time_raw,OBS_VALUE value_raw,'+','.join(col(n)+' '+alias for n,alias in [('QC_FLAG','source_qc_raw'),('MQC_FLAG','source_mq_raw'),('N1_AQC_FLAG','source_n1_qc_raw'),('RECEIVE_TIME','received_time_raw'),('WATER_STEP','depth_step'),(from_depth,'depth_from'),('TO_DEPTH','depth_to')])
            extra = ''
        c.execute('CREATE VIEW normalized AS SELECT '+select+',filename,file_row_number FROM raw_files '+extra)
        year, mon = map(int, month.split('-'))
        end = f'{month}-{calendar.monthrange(year,mon)[1]:02d} 23:59:59.999999'
        direction = 'DESC' if tail else 'ASC'
        cutoff_sql=' AND regexp_full_match(CAST(observed_time_raw AS VARCHAR),?) AND try_cast(observed_time_raw AS TIMESTAMP)<?::TIMESTAMP' if cutoff_end else ''
        cutoff_args=[NATIVE_PATTERN,str(cutoff_end)] if cutoff_end else []
        rows = records(c.execute(f'''SELECT *,try_cast(value_raw AS DOUBLE) value_numeric FROM normalized
          WHERE station_code=? AND item_code=? AND try_cast(observed_time_raw AS TIMESTAMP) BETWEEN ?::TIMESTAMP AND ?::TIMESTAMP
          {cutoff_sql} AND depth_step IS NOT DISTINCT FROM ? AND depth_from IS NOT DISTINCT FROM ? AND depth_to IS NOT DISTINCT FROM ?
          ORDER BY try_cast(observed_time_raw AS TIMESTAMP) {direction},filename {direction},file_row_number {direction} LIMIT ? OFFSET ?''',
          [station,item,month+'-01 00:00:00',end,*cutoff_args,*depth,limit+1,offset]))
    by_path = {str(Path(a['parquet_path']).resolve()):a for a in assets}
    # Verify before returning any values. Unknown metadata stays null.
    for filename in {r['filename'] for r in rows}:
        p = Path(filename).resolve(); a=by_path[str(p)]; stat=p.stat()
        verify_file(str(p),stat.st_mtime_ns,stat.st_size,a['parquet_sha256'])
    for r in rows:
        a = by_path[str(Path(r['filename']).resolve())]
        r.update(source_sha256=a['source_sha256'],parquet_sha256=a['parquet_sha256'],
                 physical_sensor_id=None,unit=None,timezone=None,approval_status='UNAPPROVED')
        if r['value_numeric'] is not None and not math.isfinite(r['value_numeric']):
            r['value_numeric'] = None
    return {'source':source,'month':month,'station':station,'item':item,'rows':rows[:limit],
            'has_more':len(rows)>limit,'offset':offset,'limit':limit,'storage':'PARQUET',
            'approval_status':'UNAPPROVED','snapshot':view.name,
            'tail':tail,'as_of_day':as_of_day,'as_of_time':as_of_time,
            'ordering':('descending ' if tail else '')+'observed source clock, filename, file row number',
            'note':'원천 시각·값·QC 보존. 중복 제거·결측 보간·센서 추정·UTC 변환 없음.'}
