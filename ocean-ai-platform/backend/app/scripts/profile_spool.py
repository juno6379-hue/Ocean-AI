# 파일 역할: 보관 관측 파일의 크기·확장자·표본 구조를 조사합니다.
"""Read-only inventory/profiling for the legacy spool archive."""
from __future__ import annotations
import argparse, csv, hashlib, json, re
from pathlib import Path
from datetime import datetime

EXTENSIONS={'.csv','.txt','.dat','.prd','.sql','.xlsx','.zip'}
ITEM_RE=re.compile(r"TIDE_LEVEL_[A-Z0-9_]+|WATER_TEMP|SALINITY|ELECT_CONDUCT|WIND_SPEED|WIND_DIRECT|WIND_GUST|AIR_PRES|AIR_TEMP|MAX_WAVE_HEIGHT|MAX_WAVE_PERIOD|SIGNIFI_WAVE_HEIGHT|SIGNIFI_WAVE_PERIOD",re.I)
DATE_RE=re.compile(r"20\d{2}[-_/]?\d{2}[-_/]?\d{2}")

def profile(path: Path, sample_bytes: int):
    row={'path':str(path),'name':path.name,'extension':path.suffix.lower(),'size_bytes':path.stat().st_size,'modified_at':datetime.fromtimestamp(path.stat().st_mtime).isoformat()}
    try:
        with path.open('rb') as f: raw=f.read(sample_bytes)
        row['sha256_sample']=hashlib.sha256(raw).hexdigest()
        enc=None; text=''
        for candidate in ('utf-8-sig','cp949','euc-kr','latin1'):
            try: text=raw.decode(candidate); enc=candidate; break
            except UnicodeDecodeError: continue
        row['encoding']=enc or 'unknown'; row['sample_lines']=text.count('\n')
        row['item_candidates']=sorted(set(x.upper() for x in ITEM_RE.findall(text)))
        row['date_candidates']=sorted(set(DATE_RE.findall(text)))[:20]
        lines=[x for x in text.splitlines() if x.strip()][:5]
        row['delimiter_candidates']={d:sum(line.count(d) for line in lines) for d in [',','\t',';','|']}
        try: row['csv_field_count']=len(next(csv.reader([lines[0]]))) if lines else 0
        except Exception: row['csv_field_count']=None
        row['status']='SAMPLED'
    except Exception as exc: row['status']='ERROR'; row['error']=str(exc)
    return row

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--sample-bytes',type=int,default=65536); args=ap.parse_args()
    files=[p for p in args.source.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS]
    rows=[profile(p,args.sample_bytes) for p in files]
    summary={'created_at':datetime.utcnow().isoformat(),'source':str(args.source),'file_count':len(rows),'total_bytes':sum(x['size_bytes'] for x in rows),'by_extension':{},'items':sorted({i for x in rows for i in x.get('item_candidates',[])})}
    for x in rows: summary['by_extension'][x['extension']]=summary['by_extension'].get(x['extension'],0)+1
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps({'summary':summary,'files':rows},ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
