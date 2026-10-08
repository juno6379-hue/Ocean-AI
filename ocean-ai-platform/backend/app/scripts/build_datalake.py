# 파일 역할: 관측 원본을 파티션 Parquet로 변환하고 처리 목록을 기록합니다.
"""Build a partitioned Parquet data lake and lightweight time-series statistics.

The source tree is read-only from this script's perspective. It streams delimited
legacy files in chunks so the full 2001-2021 archive is never loaded into memory.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from datetime import datetime
import pandas as pd

SUPPORTED = {".csv", ".txt", ".dat", ".prd"}
ITEM_RE = re.compile(r"(TIDE_LEVEL_[A-Z0-9_]+|WATER_TEMP|SALINITY|ELECT_CONDUCT|WIND_SPEED|WIND_DIRECT|WIND_GUST|AIR_PRES|AIR_TEMP|MAX_WAVE_HEIGHT|MAX_WAVE_PERIOD|SIGNIFI_WAVE_HEIGHT|SIGNIFI_WAVE_PERIOD)")

def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def read_chunks(path: Path, size: int):
    if path.suffix.lower() in {".prd", ".dat"}:
        return _fixed_width_reader(path, size)
    for enc in ("utf-8-sig", "cp949", "euc-kr", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, chunksize=size, sep=None, engine="python", on_bad_lines="skip")
        except Exception:
            continue
    # Legacy PRD/DAT files are often fixed-width or headered text rather than CSV.
    return _fixed_width_reader(path, size)

def _fixed_width_reader(path: Path, size: int):
    def fixed_width():
        rows=[]
        for enc in ("cp949", "euc-kr", "utf-8", "latin1"):
            try:
                with path.open("r", encoding=enc, errors="ignore") as stream:
                    for line in stream:
                        m=re.search(r"(20\d{2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})", line)
                        if not m: continue
                        ts=f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d} {int(m.group(4)):02d}:{int(m.group(5)):02d}:00"
                        nums=re.findall(r"[-+]?\d+(?:\.\d+)?", line[m.end():])
                        if nums: rows.append({"timestamp_local":ts,"value_raw":float(nums[0]),"variable_code":"TIDE"})
                        if len(rows)>=size: yield pd.DataFrame(rows); rows=[]
                    if rows: yield pd.DataFrame(rows)
                return
            except OSError: return
    return fixed_width()

def normalize(df: pd.DataFrame, source: Path, source_timezone: str = "Asia/Seoul") -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        u = c.upper()
        if "OBS_POST_ID" in u or u in {"STATION_ID", "OBS_ID"}: rename[c] = "station_id"
        elif "OBS_TIME" in u or "TIMESTAMP" in u or u in {"DATETIME", "DATE"}: rename[c] = "timestamp_local"
        elif "OBS_ITEM_CODE" in u or "VARIABLE_CODE" in u: rename[c] = "variable_code"
        elif "OBS_VALUE" in u or u in {"VALUE", "VALUE_RAW"}: rename[c] = "value_raw"
        elif "QC_FLAG" in u and "MQC" not in u: rename[c] = "qc_flag"
        elif "MQC_FLAG" in u: rename[c] = "mqc_flag"
    out = df.rename(columns=rename)
    if "station_id" not in out: out["station_id"] = source.stem.split("-")[0]
    if "timestamp_local" not in out: out["timestamp_local"] = pd.NaT
    if "value_raw" not in out:
        candidates = [c for c in out.columns if pd.api.types.is_numeric_dtype(out[c])]
        if candidates: out["value_raw"] = out[candidates[0]]
    if "variable_code" not in out:
        text = " ".join(map(str, out.columns)); m = ITEM_RE.search(text)
        out["variable_code"] = m.group(1) if m else "UNKNOWN"
    out["station_id"] = out["station_id"].astype(str).str.strip().str.upper()
    out["variable_code"] = out["variable_code"].astype(str).str.strip().str.upper()
    timestamps = pd.to_datetime(out["timestamp_local"], errors="coerce")
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(source_timezone, ambiguous="NaT", nonexistent="NaT")
    out["timestamp_utc"] = timestamps.dt.tz_convert("UTC")
    out["source_file"] = str(source)
    out["source_checksum"] = checksum(source)
    return out[[c for c in ["station_id","variable_code","timestamp_utc","value_raw","qc_flag","mqc_flag","source_file","source_checksum"] if c in out]]

def build(source: Path, lake: Path, limit_files: int | None = None, chunk_size: int = 100_000, source_timezone: str = "Asia/Seoul"):
    lake.mkdir(parents=True, exist_ok=True); manifest=[]; stats={}
    files = [p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED]
    for path in files[:limit_files] if limit_files else files:
        reader = read_chunks(path, chunk_size)
        if reader is None: manifest.append({"file": str(path), "status": "UNPARSEABLE", "sha256": checksum(path)}); continue
        rows=0
        for chunk in reader:
            out=normalize(chunk, path, source_timezone); out=out.dropna(subset=["timestamp_utc"])
            if out.empty: continue
            out["year"]=out.timestamp_utc.dt.year; out["month"]=out.timestamp_utc.dt.month
            for (year, month, station, variable), part in out.groupby(["year","month","station_id","variable_code"]):
                dest=lake/f"year={int(year)}"/f"month={int(month):02d}"/f"station_id={station}"/f"variable_code={variable}"
                dest.mkdir(parents=True, exist_ok=True); part.drop(columns=["year","month"]).to_parquet(dest/f"{path.stem}-{hashlib.sha256(str(path.relative_to(source)).encode()).hexdigest()[:16]}-{rows}.parquet", index=False)
                key=str(variable); s=stats.setdefault(key,{"rows":0,"min":None,"max":None,"missing":0})
                s["rows"] += len(part); s["missing"] += int(part.value_raw.isna().sum())
                vals=pd.to_numeric(part.value_raw, errors="coerce").dropna()
                if not vals.empty: s["min"]=float(vals.min()) if s["min"] is None else min(s["min"],float(vals.min())); s["max"]=float(vals.max()) if s["max"] is None else max(s["max"],float(vals.max()))
            rows += len(out)
        manifest.append({"file": str(path), "status": "CONVERTED", "sha256": checksum(path), "rows": rows})
    (lake/"manifest.json").write_text(json.dumps({"created_at":datetime.utcnow().isoformat(),"files":manifest,"stats":stats},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"files":len(manifest),"stats":stats,"lake":str(lake)}

if __name__ == "__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--source",type=Path,required=True); ap.add_argument("--lake",type=Path,required=True); ap.add_argument("--limit-files",type=int); args=ap.parse_args(); print(json.dumps(build(args.source,args.lake,args.limit_files),ensure_ascii=False,indent=2))
