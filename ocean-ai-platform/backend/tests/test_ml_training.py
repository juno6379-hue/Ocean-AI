# 파일 역할: 모델 학습과 평가의 재현성을 검증합니다.
"""Causality, model persistence and source mapping tests without external services."""
from datetime import datetime
from pathlib import Path
import os
import uuid
import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException
from app.ml.feature_generator import make_features, prepare_hourly
from app.ml.trainer import train_hourly_forecaster
from app.ml.model_registry import save_candidate
from app.api.routes_mlops import validate_metrics
from app.scripts.sync_mdc_db import observation_from_mdc


def test_future_values_cannot_change_past_features():
    index = pd.date_range("2020-01-01", periods=200, freq="h", tz="UTC")
    hourly = pd.Series(np.arange(200, dtype=float), index=index)
    before = make_features(hourly)
    changed = hourly.copy()
    changed.iloc[150:] = -9999
    after = make_features(changed)
    pd.testing.assert_frame_equal(before.loc[:index[149]], after.loc[:index[149]])
    assert before.loc[index[150], "lag_1"] == hourly.iloc[149]


def test_hourly_intervals_and_gaps_are_preserved():
    times = pd.date_range("2020-01-01", periods=24, freq="5min", tz="UTC")
    raw = pd.DataFrame({"timestamp_utc": times, "value_raw": np.arange(24, dtype=float)})
    hourly, quality = prepare_hourly(raw.drop(index=range(12, 20)))
    assert hourly.index[0] == pd.Timestamp("2020-01-01T01:00:00Z")
    assert hourly.iloc[0] == 5.5
    assert pd.isna(hourly.iloc[1])
    assert quality["missing_bins_interpolated"] == 0
    conflict = pd.concat([raw, raw.iloc[[0]].assign(value_raw=99)])
    with pytest.raises(ValueError, match="Conflicting"):
        prepare_hourly(conflict)


def test_training_holdouts_and_artifact_reload():
    times = pd.date_range("2020-01-01", periods=24 * 12 * 50, freq="5min", tz="UTC")
    hours = np.arange(len(times)) / 12
    values = 15 + np.sin(hours * 2 * np.pi / 24) + np.random.default_rng(42).normal(0, .1, len(times))
    raw = pd.DataFrame({"timestamp_utc": times, "value_raw": values})
    model, metadata, evaluation, features = train_hourly_forecaster(raw)
    splits = metadata["splits"]
    assert splits["train"]["end"] < splits["validation"]["start"] < splits["test"]["start"]
    assert metadata["test_metrics"]["sample_count"] == len(evaluation)
    scratch = Path(os.environ.get("OCEAN_TEST_WORKDIR", str(Path(__file__).parent / ".work"))) / uuid.uuid4().hex
    saved = save_candidate(model, metadata, evaluation, features, scratch)
    assert saved["artifact_reload_verified"] is True
    assert saved["status"] == "CANDIDATE" and saved["approval_required"]


def test_regression_metrics_and_nonfinite_rejection():
    validate_metrics({"mae": 2.5, "rmse": 3, "bias": -.5, "latency": .1}, "FORECASTING")
    with pytest.raises(HTTPException):
        validate_metrics({"mae": np.nan, "rmse": 3, "latency": .1}, "FORECASTING")
    with pytest.raises(HTTPException):
        validate_metrics({"mae": 2, "rmse": 3, "latency": .1}, "CLASSIFICATION")


def test_source_unit_identity_and_absent_qc():
    source = {"obs_post_id": "UN_0006", "obs_item_code": "WATER_TEMP", "obs_time": datetime(2012, 1, 1, 9), "obs_value": 12.5}
    row = observation_from_mdc(source, "WEB_OBS_ST")
    assert row.value_unit == "C" and row.value_status == "UNREVIEWED"
    assert row.timestamp_utc == datetime(2012, 1, 1)
    assert row.source_system == "MDC_WEB_OBS_ST"
    first = observation_from_mdc({**source, "water_step": "1", "fr_depth": 0, "to_depth": 1}, "WEB_OBS_VBU")
    second = observation_from_mdc({**source, "water_step": "2", "fr_depth": 1, "to_depth": 2}, "WEB_OBS_VBU")
    assert first.sensor_id != second.sensor_id


def test_tide_and_station_collection_use_distinct_source_tables(monkeypatch):
    from app.scripts import sync_mdc_db as sync
    tables = []
    monkeypatch.setattr(sync, "_sync_observations", lambda db, table, *args: tables.append(table))
    sync.sync_tide_data(None)
    sync.sync_station_data(None)
    sync.sync_buoy_data(None)
    assert tables == ["TP_OBS_SO", "WEB_OBS_ST", "WEB_OBS_VBU"]


def test_historical_qc_filter_timezone_and_empty_hour():
    from app.scripts.train_parquet_history import hourly_from_parquet
    scratch = Path(os.environ.get("OCEAN_TEST_WORKDIR", str(Path(__file__).parent / ".work"))) / uuid.uuid4().hex
    scratch.mkdir(parents=True)
    source = scratch / "history.parquet"
    pd.DataFrame({"Time": pd.date_range("2020-01-01", periods=120, freq="min"),
                  "OTT": [100.] * 60 + [9999.] * 60, "QC2": ["G"] * 60 + ["B"] * 60}).to_parquet(source)
    hourly, quality = hourly_from_parquet(source, "Time", "OTT", "QC2")
    assert hourly.index[0] == pd.Timestamp("2019-12-31T16:00:00Z")
    assert hourly.iloc[0] == 100 and pd.isna(hourly.iloc[1])
    assert quality["accepted_rows"] == quality["rejected_or_missing_rows"] == 60
