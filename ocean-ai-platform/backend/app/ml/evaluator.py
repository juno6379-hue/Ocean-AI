# 파일 역할: 예측 또는 분류 모델의 평가 지표를 계산합니다.
"""Forecast regression metrics; classification scores do not apply to this task."""
import numpy as np


def regression_metrics(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if len(actual) == 0 or actual.shape != predicted.shape or not np.isfinite([actual, predicted]).all():
        raise ValueError("Evaluation requires aligned finite observations and predictions")
    error = predicted - actual
    return {"mae": float(np.mean(np.abs(error))), "rmse": float(np.sqrt(np.mean(error ** 2))),
            "bias": float(np.mean(error)), "sample_count": int(len(actual))}
