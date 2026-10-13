"""Dry-run by default; system-policy approval, standard mapping and row bindings.

Every committed batch can be replayed. Receipt reports specify the actual native
time window; they never imply that the whole historical lake was loaded.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import duckdb
import pyarrow.parquet as pq

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import source_auto_mapping as auto


def census(packet, start, end):
    file = next(f for f in packet['files'] if f['role'] == 'PARQUET')
    path = auto.authority._path(auto.authority.SOURCE_ROOT, file['path'])
    with duckdb.connect() as con:
        con.execute('SET threads=2')
        rows = con.execute('SELECT upper(trim(OBS_ITEM_CODE)),count(*) FROM read_parquet(?) '
                           'WHERE try_cast(OBS_TIME AS TIMESTAMP)>=? AND try_cast(OBS_TIME AS TIMESTAMP)<=? '
                           'GROUP BY 1 ORDER BY 1', [str(path), start, end]).fetchall()
        names = set(pq.ParquetFile(path).schema_arrow.names)
        def column(name):
            return '"'+name+'"' if name in names else 'NULL::VARCHAR'
        depths = [column(n) for n in ('WATER_STEP', 'FR_DEPTH' if 'FR_DEPTH' in names else 'FROM_DEPTH', 'TO_DEPTH')]
        payload = ','.join('f'+str(i)+':='+column(n) for i,n in enumerate(('OBS_VALUE','QC_FLAG','MQC_FLAG','N1_AQC_FLAG','RECEIVE_TIME')))
        known = packet['mapping_policy']['items']
        sql = ('SELECT count(*) FROM (SELECT upper(trim(OBS_POST_ID)),upper(trim(OBS_ITEM_CODE)),OBS_TIME,'+','.join(depths)+
               ' FROM read_parquet(?) WHERE try_cast(OBS_TIME AS TIMESTAMP)>=? AND try_cast(OBS_TIME AS TIMESTAMP)<=? '
               'AND upper(trim(OBS_ITEM_CODE)) IN ('+','.join('?' for _ in known)+') GROUP BY ALL '
               'HAVING count(DISTINCT struct_pack('+payload+'))>1)')
        conflicts = con.execute(sql, [str(path),start,end,*known]).fetchone()[0]
    known = packet['mapping_policy']['items']
    return dict(total_window_rows=sum(n for _,n in rows), mapped_window_rows=sum(n for k,n in rows if k in known),
                unmapped_window_rows=sum(n for k,n in rows if k not in known),
                conflicting_natural_keys=conflicts,
                by_item=[dict(source_item_code=k, rows=n, mapped=k in known) for k,n in rows])


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--from-native', required=True, help='Original KST local clock, inclusive')
    parser.add_argument('--to-native', required=True, help='Original KST local clock, inclusive')
    parser.add_argument('--sources', nargs='+', choices=auto.policy()['sources'], default=auto.policy()['sources'])
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--register-source-identifiers', action='store_true',
                        help='Register missing exact source IDs only; no physical names, positions or periods')
    parser.add_argument('--batch-size', type=int, default=1000)
    args = parser.parse_args()
    start, end = auto.window(args.from_native), auto.window(args.to_native)
    if start > end or not 1 <= args.batch_size <= 2000:
        parser.error('Invalid source-native time window or batch size')
    if args.receipt.exists():
        parser.error('Receipt already exists; choose a new output path')
    if args.apply and (not settings.SOURCE_AUTO_MAPPING_ENABLED or settings.DATA_MODE != 'live'):
        parser.error('Explicit live SOURCE_AUTO_MAPPING_ENABLED configuration required')
    files = sorted(p for p in Path(settings.SHARE_MONTHLY_LAKE_ROOT).glob('*/manifest.json')
                   if (match := auto.SOURCE_PATTERN.fullmatch(p.parent.name)) and match[1] in args.sources
                   and start.strftime('%Y%m') <= match[2] <= end.strftime('%Y%m'))
    if not files:
        parser.error('No verified monthly manifests in requested scope')
    report = dict(schema_version='operational-parquet-ingest-run-1', mode='APPLY' if args.apply else 'DRY_RUN',
                  started_at=datetime.now(timezone.utc).isoformat(), from_native=start.isoformat(),
                  to_native=end.isoformat(), timezone='Asia/Seoul', mapping_version=auto.VERSION,
                  source_scope=args.sources, whole_history_loaded=False, files=[], status='RUNNING',
                  human_approval_created=False, training_approval_created=False, final_qc_approval_created=False)
    report['register_source_identifiers'] = args.register_source_identifiers
    args.receipt.parent.mkdir(parents=True, exist_ok=True)

    def save():
        temp = args.receipt.with_suffix('.tmp')
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        temp.replace(args.receipt)

    save()
    try:
        # Preflight every file before any approval or observation writes.
        packets = [auto.prepare_manifest(p) for p in files]
        for packet in packets:
            result = dict(source=packet['source_group'], month=packet['month'], contract_id=packet['contract_id'],
                          source_sha256=packet['source_sha256'], census=census(packet, start, end), counts={})
            report['files'].append(result)
        save()
        if args.apply and any(f['census']['conflicting_natural_keys'] for f in report['files']):
            raise RuntimeError('Conflicting natural keys require source reconciliation before apply')
        for packet,result in zip(packets, report['files']):
            if not args.apply:
                continue
            with SessionLocal() as db:
                receipt, sha = auto.approve_manifest(db, packet)
                auto.adopt_mapping(db)
                db.commit()
                counts, cache = Counter(), {}
                for index, rows in enumerate(auto.selected_batches(packet, start, end, batch_size=args.batch_size)):
                    try:
                        counts.update(auto.ingest_batch(db, receipt, sha, rows, source_cache=cache,
                                                       register_source_identifiers=args.register_source_identifiers))
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise
                    result['counts'] = dict(counts)
                    if index % 50 == 0:
                        save()
                        print(json.dumps(dict(source=packet['source_group'], batch=index+1, **dict(counts))), flush=True)
                auto.verify_receipt(db, receipt, sha, verify_sources=True)
                if counts['selected_rows'] != result['census']['mapped_window_rows']:
                    raise RuntimeError('Mapped source census and processed row counts disagree')
                result['counts'] = dict(counts)
                result['receipt_sha256'] = sha
                result['status'] = 'COMPLETE_WITH_QUARANTINE' if counts['quarantined_rows'] else 'COMPLETE'
                save()
        report['status'] = 'DRY_RUN_COMPLETE' if not args.apply else 'COMPLETE_WITH_QUARANTINE' if any(f['counts'].get('quarantined_rows') for f in report['files']) else 'COMPLETE'
    except Exception as exc:
        report['status'] = 'FAILED_RESUMABLE'
        report['error'] = getattr(exc, 'code', None) or type(exc).__name__
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps(dict(status=report['status'], receipt=str(args.receipt), files=len(files))), flush=True)


if __name__ == '__main__':
    main()
