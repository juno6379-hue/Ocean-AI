"""Recalculate selected monthly file diagnostics; never write operational database."""
import argparse
from pathlib import Path
import json
import sys
import duckdb
import pyarrow.parquet as pq
from app.services.native_month_metrics import SOURCES,asset_month,compute_month,publish_packet,file_hash,dump,now,LOADED_RECIPE_SHA256

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--audit-root',type=Path,required=True)
    parser.add_argument('--source',choices=SOURCES,default='GD_OBS_ST_MONTHLY')
    parser.add_argument('--from-month',default='2023-01');parser.add_argument('--to-month',default='2026-07')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();args.audit_root.mkdir(parents=True,exist_ok=True)
    if args.from_month>args.to_month:parser.error('from-month exceeds to-month')
    def emit(stage,**fields):
        line=json.dumps({'at':now(),'stage':stage,**fields},ensure_ascii=False)
        print(line,flush=True)
        with (args.audit_root/'progress.jsonl').open('a',encoding='utf-8') as stream:stream.write(line+'\n')
    catalog_sha=file_hash(args.snapshot/'station-item-month-validation.parquet');assets_sha=file_hash(args.snapshot/'file-only-timeseries.duckdb')
    with duckdb.connect(str(args.snapshot/'file-only-timeseries.duckdb'),read_only=True) as c:
        cursor=c.execute('SELECT * FROM source_assets');names=[d[0] for d in cursor.description]
        assets=[dict(zip(names,row)) for row in cursor.fetchall()]
    assets=[a for a in assets if a['source_group']==args.source and args.from_month<=asset_month(a)<=args.to_month]
    months=sorted({asset_month(a) for a in assets})
    coverage=pq.read_table(args.snapshot/'station-item-month-validation.parquet').to_pylist()
    coverage=[r for r in coverage if r['source_group']==args.source and args.from_month<=str(r['month'])[:7]<=args.to_month]
    if file_hash(args.snapshot/'station-item-month-validation.parquet')!=catalog_sha or file_hash(args.snapshot/'file-only-timeseries.duckdb')!=assets_sha:
        raise ValueError('SNAPSHOT_CHANGED_WHILE_READING')
    inventory={'source_group':args.source,'from_month':args.from_month,'to_month':args.to_month,
      'snapshot':args.snapshot.name,'catalog_sha256':catalog_sha,'source_assets_sha256':assets_sha,
      'months':months,'files':len(assets),'bytes':sum(Path(a['parquet_path']).stat().st_size for a in assets),
      'catalog_channel_months':len(coverage),'catalog_held_rows':sum(r['held_rows'] or 0 for r in coverage),
      'threads':2,'memory_limit':'512MB','approved':False,'DB_writes':0}
    dump(args.audit_root/'inventory.json',inventory);emit('START',**inventory)
    completed=[]
    for index,month in enumerate(months):
        marker=args.output_root/args.snapshot.name/args.source/month/'published.json'
        reusable=False
        if args.resume and marker.is_file():
            value=json.loads(marker.read_text(encoding='utf-8'));path=marker.parent/value['packet_file']
            if file_hash(path)!=value['sha256']:raise ValueError('RESUME_PACKET_CHECKSUM_MISMATCH')
            packet=json.loads(path.read_text(encoding='utf-8'))
            if packet['catalog_sha256']!=inventory['catalog_sha256'] or packet['source_assets_sha256']!=inventory['source_assets_sha256']:raise ValueError('RESUME_INPUT_SNAPSHOT_CHANGED')
            for asset in packet['source_files']:
                if file_hash(asset['path'])!=asset['sha256']:raise ValueError('RESUME_SOURCE_BYTES_CHANGED')
            reusable=packet.get('recipe_sha256')==LOADED_RECIPE_SHA256
            if reusable:result={'path':str(path),'sha256':value['sha256'],'resumed':True}
        if not reusable:
            emit('MONTH_START',month=month,index=index+1,total=len(months))
            packet=compute_month(args.snapshot,args.source,month,assets,[r for r in coverage if str(r['month'])[:7]==month],args.audit_root/'work'/month,emit)
            result=publish_packet(args.output_root,packet)
        summary={**result,'month':month,'held_rows':sum(r['raw_rows'] for r in packet['channels']),
          'channel_months':len(packet['channels']),'grid_calculated':sum(r['grid']['expected_slots'] is not None for r in packet['channels']),
          'grid_excluded':sum(r['grid']['expected_slots'] is None for r in packet['channels']),
          'files':len(packet['source_files']),'elapsed_seconds':packet['elapsed_seconds']}
        completed.append(summary);dump(args.audit_root/'completed.json',{'completed':completed,'approved':False,'DB_writes':0})
        emit('MONTH_DONE',index=index+1,total=len(months),**summary)
    emit('COMPLETE',months=len(completed),held_rows=sum(r['held_rows'] for r in completed),channel_months=sum(r['channel_months'] for r in completed))

if __name__=='__main__':main()
