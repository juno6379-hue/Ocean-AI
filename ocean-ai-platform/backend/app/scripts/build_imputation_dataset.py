# 파일 역할: 긴 결측 보간에 사용할 학습 자료를 구성합니다.
"""Create masked time-series windows for GRU-D/BRITS/SAITS training."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd
from app.services.lake_manifest import load_observations

def build(source: Path, output: Path, station_id: str, variable_code: str, window: int = 48, stride: int = 12, *, layer: str):
    if window<=0 or stride<=0: raise ValueError("Positive window and stride required")
    df=load_observations(source,layer,station_id,variable_code)
    if df.empty: raise RuntimeError("No approved matching Parquet observations")
    df["value_raw"]=pd.to_numeric(df.value_raw, errors="coerce"); values=df.value_raw.tolist(); rows=[]
    for start in range(0,max(0,len(values)-window+1),stride):
        seq=values[start:start+window]
        if len(seq)<window: continue
        observed=[x==x for x in seq]; missing=sum(not x for x in observed)
        if missing==0: continue
        target=[x if x==x else None for x in seq]
        rows.append({"station_id":station_id,"variable_code":variable_code.upper(),"window_start":df.timestamp_utc.iloc[start].isoformat(),"window_end":df.timestamp_utc.iloc[start+window-1].isoformat(),"values_json":json.dumps(target,allow_nan=False),"observed_mask_json":json.dumps(observed),"target_json":json.dumps(target),"missing_count":missing,"window_size":window,"dataset_split":"RETRAINING_POOL"})
    if not rows: raise ValueError("No windows with missing values; no dataset written")
    output.parent.mkdir(parents=True,exist_ok=True); out=pd.DataFrame(rows); out.to_parquet(output,index=False)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    meta={"dataset_name":"imputation_long_gap","dataset_version":"1.0","station_scope":[station_id],"variable_scope":[variable_code.upper()],"sample_count":len(out),"window_size":window,"feature_version":"IMPUTE-MASK-1.0","label_version":"NONE_PENDING_APPROVAL","preprocessing_version":"RAW-NORMALIZE-1.0","data_hash":digest,"model_candidates":["GRU-D","BRITS","SAITS"]}
    output.with_suffix(".json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8"); return meta

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--source",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--station-id",required=True); ap.add_argument("--variable-code",default="TIDE"); ap.add_argument("--window",type=int,default=48); ap.add_argument("--stride",type=int,default=12); ap.add_argument("--layer",choices=["standardized"],required=True); a=ap.parse_args(); print(json.dumps(build(a.source,a.output,a.station_id,a.variable_code,a.window,a.stride,layer=a.layer),ensure_ascii=False,indent=2))
