# 파일 역할: 조위 예측의 기준 모델과 결과를 생성합니다.
"""Generate persistence/seasonal baseline forecast artifacts for MLOps."""
import argparse, json
from pathlib import Path
import pandas as pd
from app.services.lake_manifest import load_observations

def forecast(source: Path, station_id: str, horizon: int = 72, *, layer: str):
    d=load_observations(source,layer,station_id,"TIDE").dropna(subset=["value_raw"])
    if d.empty: return {"status":"NO_DATA"}
    last=float(d.value_raw.iloc[-1]); ts=d.timestamp_utc.iloc[-1]
    predictions=[{"timestamp_utc":(ts+pd.Timedelta(hours=i)).isoformat(),"predicted_value":last,"horizon_hour":i} for i in range(1,horizon+1)]
    return {"station_id":station_id,"variable_code":"TIDE","horizon_hours":horizon,"predictions":predictions,"model_name":"PERSISTENCE_BASELINE","model_version":"TIDE-FCST-BASELINE-1.0","metrics":{"precision":None,"recall":None,"f1":None,"auroc":None,"false_positive_rate":None,"false_negative_rate":None,"latency_ms":0},"status":"CANDIDATE"}

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--source",type=Path,required=True); ap.add_argument("--station-id",required=True); ap.add_argument("--horizon",type=int,default=72); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--layer",choices=["standardized"],required=True); a=ap.parse_args(); out=forecast(a.source,a.station_id,a.horizon,layer=a.layer); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({"status":out.get("status"),"horizon":out.get("horizon_hours",0)},ensure_ascii=False))
