# 파일 역할: 시간 순서에 따른 학습·검증과 모델 산출물 생성을 수행합니다.
"""Reproducible offline forecast training with chronological holdouts."""
import hashlib
import time
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from app.ml.evaluator import regression_metrics
from app.ml.feature_generator import FEATURE_VERSION, PREPROCESSING_VERSION, make_features, prepare_hourly


def train_hourly_forecaster(raw, min_split_samples=100):
    """Select alpha on validation only; refit train+validation before one held-out test."""
    hourly, quality = prepare_hourly(raw)
    return train_from_hourly(hourly, quality, min_split_samples)


def train_from_hourly(hourly, quality, min_split_samples=100, external_hourly=None):
    """Train from an already audited hourly series, with optional same-site past covariates."""
    frame = make_features(hourly)
    if external_hourly is not None:
        for name in external_hourly.columns:
            for lag in (1, 6, 24):
                frame[f"external_{name}_lag_{lag}"] = external_hourly[name].reindex(hourly.index).shift(lag).reindex(frame.index)
        frame = frame.dropna()
    if len(frame) < min_split_samples * 5:
        raise ValueError(f"Insufficient complete hourly lag windows: {len(frame)}")
    n_train, n_validation = int(len(frame) * .6), int(len(frame) * .8)
    train, validation, test = frame.iloc[:n_train], frame.iloc[n_train:n_validation], frame.iloc[n_validation:]
    if min(map(len, (train, validation, test))) < min_split_samples:
        raise ValueError("Time-ordered evaluation partitions are too small")
    columns = [column for column in frame if column != "target"]
    candidates = []
    started = time.perf_counter()
    for alpha in (0.1, 1.0, 10.0, 100.0):
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(train[columns], train.target)
        metrics = regression_metrics(validation.target, model.predict(validation[columns]))
        candidates.append({"alpha": alpha, "validation": metrics})
    selected = min(candidates, key=lambda candidate: candidate["validation"]["mae"])
    model = make_pipeline(StandardScaler(), Ridge(alpha=selected["alpha"]))
    development = frame.iloc[:n_validation]
    model.fit(development[columns], development.target)
    training_seconds = time.perf_counter() - started
    started = time.perf_counter()
    predictions = model.predict(test[columns])
    latency = (time.perf_counter() - started) * 1000 / len(test)
    model_metrics = regression_metrics(test.target, predictions)
    persistence = regression_metrics(test.target, test.lag_1)
    seasonal = regression_metrics(test.target, test.lag_24)
    digest = hashlib.sha256(frame.to_csv(date_format="%Y-%m-%dT%H:%M:%S%z", float_format="%.17g").encode()).hexdigest()
    split = lambda part: {"samples": len(part), "start": part.index[0].isoformat(), "end": part.index[-1].isoformat()}
    metadata = {"model_name": "RIDGE_HOURLY_FORECAST", "task": "FORECASTING", "horizon_hours": 1,
                "feature_version": FEATURE_VERSION, "preprocessing_version": quality.get("preprocessing_version", PREPROCESSING_VERSION),
                "label_version": "OBSERVED_VALUE_UNREVIEWED", "dataset_hash": digest,
                "data_quality": quality, "complete_windows": len(frame), "features": columns,
                "splits": {"train": split(train), "validation": split(validation), "test": split(test)},
                "selection": candidates, "selected_alpha": selected["alpha"], "training_seconds": training_seconds,
                "test_metrics": model_metrics, "baseline_persistence": persistence, "baseline_seasonal_24h": seasonal,
                "mae_improvement_vs_persistence_pct": 100 * (1 - model_metrics["mae"] / persistence["mae"]) if persistence["mae"] else None,
                "latency_ms_per_sample": latency, "status": "CANDIDATE", "approval_required": True,
                "evaluation_protocol": "rolling one-hour-ahead: observed past holdout values are available at each forecast origin; no shuffled split or interpolation"}
    evaluation = test[["target", "lag_1", "lag_24"]].copy()
    evaluation["prediction"] = predictions
    return model, metadata, evaluation, test[columns]
