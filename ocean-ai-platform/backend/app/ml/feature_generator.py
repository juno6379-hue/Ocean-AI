# 파일 역할: 미래 정보를 사용하지 않는 시계열 학습 특성을 계산합니다.
"""Causal hourly features: no interpolation or backward filling across data gaps."""
import numpy as np
import pandas as pd

FEATURE_VERSION = "HOURLY-LAGS-1"
PREPROCESSING_VERSION = "HOURLY-MEAN-MIN6-1"
LAGS = (1, 2, 3, 6, 12, 24, 48)


def prepare_hourly(raw: pd.DataFrame, min_samples: int = 6):
    """Index each average at its interval END, when all contributing values are known."""
    data = raw[["timestamp_utc", "value_raw"]].copy()
    data["timestamp_utc"] = pd.to_datetime(data.timestamp_utc, utc=True)
    data["value_raw"] = pd.to_numeric(data.value_raw, errors="coerce")
    data.loc[~np.isfinite(data.value_raw), "value_raw"] = np.nan
    duplicates = int(data.duplicated("timestamp_utc").sum())
    conflicts = data.groupby("timestamp_utc").value_raw.nunique().gt(1)
    if conflicts.any():
        raise ValueError("Conflicting observations at the same timestamp require review")
    data = data.drop_duplicates("timestamp_utc").sort_values("timestamp_utc").set_index("timestamp_utc")
    buckets = data.value_raw.resample("1h", label="right", closed="left").agg(["mean", "count"])
    hourly = buckets["mean"].where(buckets["count"] >= min_samples)
    hourly.name = "target"
    return hourly, {"source_rows": len(raw), "duplicate_rows": duplicates, "total_hour_bins": len(hourly),
                    "usable_hour_bins": int(hourly.notna().sum()), "min_samples_per_hour": min_samples,
                    "missing_bins_interpolated": 0}


def make_features(hourly: pd.Series):
    """Predict the next hourly mean from values available at least one hour earlier."""
    frame = pd.DataFrame({"target": hourly})
    for lag in LAGS:
        frame[f"lag_{lag}"] = hourly.shift(lag)
    frame["past_mean_6"] = hourly.shift(1).rolling(6, min_periods=6).mean()
    frame["past_std_6"] = hourly.shift(1).rolling(6, min_periods=6).std()
    frame["hour_sin"] = np.sin(2 * np.pi * frame.index.hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * frame.index.hour / 24)
    return frame.dropna()
