"""2025 QC 기준본 확보 전 실행 가능한 원천 구조 검증. 물리 QC 판정은 하지 않는다."""
from pathlib import Path
import json
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import pyarrow.parquet as pq
from app.services.lake_manifest import select_files, checksum

def audit(d):
    d=d.sort_values('source_record_number',kind='stable')
    t=pd.to_datetime(d.source_clock_naive,errors='coerce')
    x=pd.to_numeric(d.value_numeric,errors='coerce')
    delta=t.diff().dt.total_seconds(); positive=delta[delta>0]
    median=float(positive.median()) if len(positive) else None
    dupe=t.notna() & t.duplicated(keep=False)
    missing=d.value_status.eq('MISSING_MARKER')
    gaps=d.loc[delta.gt(median*1.5) if median else pd.Series(False,index=d.index),['source_record_number','observed_at_raw']].copy()
    gaps['previous_raw_clock']=d.observed_at_raw.shift().loc[gaps.index]
    gaps['elapsed_seconds']=delta.loc[gaps.index]
    return {'rows':len(d),'numeric':int((np.isfinite(x)&d.value_status.eq('NUMERIC_UNREVIEWED')).sum()),'recorded_missing':int(missing.sum()),'unresolved_sentinel':int(d.value_status.eq('SENTINEL_UNRESOLVED').sum()),'invalid_clock':int(t.isna().sum()),'duplicate_clock_rows':int(dupe.sum()),'duplicate_source_record_rows':int(d.source_record_number.duplicated(keep=False).sum()),'clock_reversals':int(delta.lt(0).sum()),'infinite_numeric':int(np.isinf(x).sum()),'observed_median_interval_seconds':median,'first_raw_clock':str(t.min()),'last_raw_clock':str(t.max()),'gap_candidates':json.loads(gaps.to_json(orient='records')),'nominal_missing_count':None,'qc_valid_count':None,'physical_qc_status':'NOT_EVALUATED_2025_GUIDE_REQUIRED','sensor_unknown_rows':int(d.sensor_id.isna().sum())}

def run(lake,output):
    lake=Path(lake);output=Path(output)
    if output.exists():raise ValueError('OUTPUT_EXISTS')
    manifest=lake/'metadata/raw/manifest.json'; before=checksum(manifest)
    paths=select_files(lake,'raw');frames=[]
    for p,n in paths:
        pf=pq.ParquetFile(p)
        if pf.metadata.num_rows!=n:raise ValueError('ROW_COUNT_MISMATCH')
        frames.append(pf.read().to_pandas())
    d=pd.concat(frames,ignore_index=True);series=[]
    for (source,station,item),g in d.groupby(['source_id','station_id_raw','item_code_raw'],dropna=False):
        series.append(dict(source_id=source,station_id_raw=station,item_code_raw=item,**audit(g)))
    if before!=checksum(manifest):raise ValueError('MANIFEST_CHANGED_DURING_RUN')
    output.mkdir(parents=True)
    report={'created_at':datetime.now(timezone.utc).isoformat(),'status':'STRUCTURAL_PREFLIGHT_ONLY','required_qc_edition':2025,'guide_status':'AWAITING_VERIFIED_2025_DOCUMENT','input_manifest':str(manifest),'input_manifest_sha256':before,'files_hash_verified':len(paths),'rows':len(d),'series':series,'numeric':sum(s['numeric'] for s in series),'recorded_missing':sum(s['recorded_missing'] for s in series),'qc_evaluated_count':0,'qc_valid_count':None,'approved_usable_periods':[],'note':'Observed gaps are candidates, not theoretical missing counts; source clock and source QC remain unchanged.'}
    (output/'preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--lake',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    s=run(a.lake,a.output);print(json.dumps({k:s[k] for k in ['rows','numeric','recorded_missing','files_hash_verified','status']}))
