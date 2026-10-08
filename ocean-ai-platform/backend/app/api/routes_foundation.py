"""Read verified file-lake inventory and bounded raw samples without promoting QC.

The operational PostgreSQL dashboard and file-lake validation have distinct scopes.
Never replace unknown sensors/units/timezones or infer approval from conversion.
"""
from pathlib import Path
from functools import lru_cache
from typing import Literal
import hashlib
import json
import re
import stat
from collections import Counter
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from app.core.config import settings

router = APIRouter(prefix='/api/data-lake/foundation', tags=['File lake validation'])

@router.get('/workflow')
def foundation_workflow(source: Literal['GD_OBS_ST_MONTHLY','GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST','HISTORICAL_RECONCILED']='GD_OBS_ST_MONTHLY',
    from_month: str=Query('2023-01',pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),
    to_month: str=Query('2026-07',pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),network: str='',sea: str=''):
    from app.core.database import SessionLocal
    from app.services.workflow_status import status
    with SessionLocal() as db:return status(db,source,from_month,to_month,network,sea)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def inside(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(503, 'Configured artifact is outside its root')
    return path


def snapshot():
    root = Path(settings.FOUNDATION_OUTPUT_ROOT).resolve()
    try:
        run = inside(root, (root/'latest-run.txt').read_text(encoding='utf8').strip())
        requested = inside(run, (run/'latest-validation.txt').read_text(encoding='utf8').strip())
        # Batch workers update their work pointer before rendering/catalog/checks.
        # Keep serving the last completely verified bundle until publication is
        # ready; never mix a new registry with an older channel list or catalog.
        candidates = [requested] + sorted(run.glob('validation-*'), reverse=True)
        required = ['summary.json','channel-validation.json','station-item-month-validation.parquet',
                    'file-only-timeseries.duckdb','lake-manifest.json','verification.json']
        for candidate in dict.fromkeys(candidates):
            candidate=inside(run,candidate)
            if not all((candidate/name).is_file() for name in required):continue
            try:
                checks=read_json(candidate/'verification.json').get('checks',[])
            except (OSError,json.JSONDecodeError):
                continue
            if checks and all(x.get('passed') is True for x in checks):
                return run,candidate
        raise HTTPException(503, 'No completely verified serving snapshot is available')
    except OSError:
        raise HTTPException(503, 'File validation snapshot is not available')


def manifests():
    root = Path(settings.SHARE_MONTHLY_LAKE_ROOT).resolve()
    found = []
    for p in sorted(root.glob('*/manifest.json')):
        if not re.fullmatch(r'(GD_OBS_BU|GD_OBS_VBU|GR_OBS_ST)_20\d{4}', p.parent.name):
            continue
        m = read_json(p)
        if m.get('status') == 'VERIFIED':
            found.append(m)
    return found


def source_file_availability(files):
    """Current source presence is separate from an earlier conversion receipt."""
    counts = Counter()
    for manifest in files:
        location = manifest.get('source_path')
        if not isinstance(location, str) or not location or not Path(location).is_absolute():
            counts['PATH_UNRESOLVED'] += 1
            continue
        try:
            current = Path(location).stat()
            if not stat.S_ISREG(current.st_mode):
                state = 'NOT_A_FILE'
            elif current.st_size != manifest.get('source_size'):
                state = 'SIZE_CHANGED'
            elif current.st_mtime_ns != manifest.get('source_mtime_ns'):
                state = 'MTIME_CHANGED'
            else:
                state = 'METADATA_MATCH_NOT_REHASHED'
        except FileNotFoundError:
            state = 'MISSING'
        except OSError:
            state = 'ACCESS_ERROR'
        counts[state] += 1
    return {'checked_at': datetime.now(timezone.utc).isoformat(), 'total': len(files),
            'counts': dict(counts), 'hash_rechecked': False,
            'note': 'Current source-path metadata only. Earlier Parquet conversion receipts do not prove original CSV bytes are still preserved.'}


@router.get('/summary')
def foundation_summary():
    run, view = snapshot()
    files = manifests()
    groups = []
    for source in sorted({m['source_system'] for m in files}):
        selected = [m for m in files if m['source_system'] == source]
        groups.append({'source': source, 'files': len(selected), 'rows': sum(m['raw_rows'] for m in selected)})
    validation = read_json(view/'summary.json')
    return {'scope': 'FILE_ONLY_MDC_EXCLUDED', 'validation_snapshot': view.name,
            'validation': validation, 'verified_monthly_files': len(files), 'monthly_groups': groups,
            'conversion': read_json(Path(settings.SHARE_MONTHLY_LAKE_ROOT)/'status.json'),
            'source_availability': source_file_availability(files),
            'document_extraction': read_json(run/'expanded-extraction-status.json') if (run/'expanded-extraction-status.json').exists() else None,
            'approval_status': 'UNAPPROVED', 'training_eligible': False,
            'note': 'Conversion totals and validation snapshot have separate refresh times. Raw source groups can overlap; do not interpret their sum as unique observations.'}


@router.get('/channels')
def foundation_channels(station: str = '', item: str = '', limit: int = Query(50, ge=1, le=200)):
    _, view = snapshot()
    rows = read_json(view/'channel-validation.json')
    selected = [r for r in rows if (not station or r['station_code'] == station) and (not item or r['item_code'] == item)]
    return {'snapshot': view.name, 'total': len(selected), 'channels': selected[:limit]}


@lru_cache(maxsize=128)
def verify_file(path, mtime_ns, size, digest):
    # Cache by file identity; a changed file must pass checksum again.
    with Path(path).open('rb') as f:
        actual = hashlib.file_digest(f, 'sha256').hexdigest()
    if actual != digest:
        raise HTTPException(409, 'Parquet checksum differs from the verified manifest')


@router.get('/observations')
def foundation_observations(
    source: Literal['GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST'],
    month: str = Query(..., pattern=r'^20\d{2}(0[1-9]|1[0-2])$'),
    station: str = Query(..., min_length=1, max_length=40),
    item: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(100, ge=1, le=500),
):
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
    root = Path(settings.SHARE_MONTHLY_LAKE_ROOT).resolve()
    manifest = root/f'{source}_{month}'/'manifest.json'
    if not manifest.is_file(): raise HTTPException(404, 'Monthly source is not available')
    m = read_json(manifest)
    if m.get('status') != 'VERIFIED' or m.get('source_system') != source:
        raise HTTPException(409, 'Source file is not verified')
    path = inside(root, m['raw_path'])
    stat = path.stat()
    verify_file(str(path), stat.st_mtime_ns, stat.st_size, m['raw_sha256'])
    if pq.ParquetFile(path).metadata.num_rows != m['raw_rows']:
        raise HTTPException(409, 'Parquet row count differs from manifest')
    dataset = ds.dataset(str(path), format='parquet')
    allowed = ['OBS_POST_ID','OBS_ITEM_CODE','OBS_TIME','OBS_VALUE','RECEIVE_TIME','WATER_STEP','FR_DEPTH','TO_DEPTH','META_ID','QC_FLAG','MQC_FLAG','USER_QC_FLAG']
    columns = [c for c in allowed if c in dataset.schema.names]
    scanner = dataset.scanner(columns=columns, filter=(ds.field('OBS_POST_ID')==station)&(ds.field('OBS_ITEM_CODE')==item),batch_size=4096)
    rows = []
    for batch in scanner.to_batches():
        rows.extend(batch.slice(0,limit-len(rows)).to_pylist())
        if len(rows)>=limit:break
    return {'source':source,'month':month,'station':station,'item':item,'rows':rows,
            'returned_rows':len(rows),'limit':limit,'ordering':'source file order; bounded sample',
            'source_sha256':m['source_sha256'],'parquet_sha256':m['raw_sha256'],
            'layer':'raw','approval_status':'UNAPPROVED','unit':None,'timezone':None,
            'note':'Original values and flags retained. This sample is not an approved training dataset.'}
