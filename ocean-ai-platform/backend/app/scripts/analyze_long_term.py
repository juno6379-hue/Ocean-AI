# 파일 역할: 장기간 관측 시계열의 추세와 통계를 분석합니다.
"""Compute reproducible long-term trend summaries from Parquet observations."""
import argparse, json
from pathlib import Path
import pandas as pd
from app.services.lake_manifest import load_observations
import numpy as np

def analyze(source: Path, variable_code: str = "TIDE", *, layer: str):
    df=load_observations(source,layer,variable_code=variable_code)
    if df.empty: return {"status":"NO_DATA","variable_code":variable_code.upper()}
    df=df.dropna(subset=["value_raw"])
    results=[]
    for station,g in df.groupby("station_id"):
        g=g.sort_values("timestamp_utc"); x=((g.timestamp_utc-g.timestamp_utc.min()).dt.total_seconds()/86400).to_numpy(); y=g.value_raw.to_numpy()
        slope=float(np.polyfit(x-x.mean(),y,1)[0]*365.25) if len(g)>1 else 0.0
        monthly=g.assign(month=g.timestamp_utc.dt.month).groupby("month").value_raw.median().to_dict()
        results.append({"station_id":station,"sample_count":len(g),"period_start":g.timestamp_utc.min().isoformat(),"period_end":g.timestamp_utc.max().isoformat(),"annual_slope":slope,"monthly_median":{str(k):float(v) for k,v in monthly.items()},"status":"ANALYSIS"})
    return {"variable_code":variable_code.upper(),"station_count":len(results),"results":results,"method":"linear_trend_monthly_median","status":"ANALYSIS_ONLY"}

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--source",type=Path,required=True); ap.add_argument("--variable-code",default="TIDE"); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--layer",choices=["standardized"],required=True); a=ap.parse_args(); out=analyze(a.source,a.variable_code,layer=a.layer); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({"status":out.get("status"),"station_count":out.get("station_count",0)},ensure_ascii=False))
