"""Project historical comparison evidence onto the two deployable LSTM models.

These functions return independent values. Stored reports and their hashes remain
the original evidence; this projection never changes promotion decisions.
"""
from __future__ import annotations

import copy
import math
from typing import Any

DUEL_MODEL_KEYS = ("champion_2025", "candidate")
_DIAGNOSTIC_KEYS = frozenset({
    "ridge", "persistence", "anomaly_ridge", "anomaly_persistence",
    "ridge_sha256", "persistence_sha256", "ridge_baseline", "ridge_alphas",
    "ridge_alpha_selection",
})


def _project(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in _DIAGNOSTIC_KEYS:
                continue
            if key == "models" and isinstance(item, dict):
                result[key] = {name: _project(item[name]) for name in DUEL_MODEL_KEYS if name in item}
            else:
                result[key] = _project(item)
        return result
    if isinstance(value, list):
        return [_project(item) for item in value]
    return copy.deepcopy(value)


def _finite_score(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def _classification_score(metrics: dict) -> float | None:
    classification = metrics.get("classification") or {}
    counts = {key: _finite_score(classification.get(key)) for key in ("tp", "fp", "fn", "tn")}
    tp, fp, fn, tn = (counts[key] for key in ("tp", "fp", "fn", "tn"))
    if tp is not None and fp is not None and fn is not None and min(tp, fp, fn) >= 0:
        positive = tp if tp + fn > 0 else tn
        if positive is not None and positive >= 0:
            denominator = 2 * positive + fp + fn
            if denominator:
                return 2 * positive / denominator
    for key, scale in (("f1_score", 1), ("f1_score_100", 100),
                       ("normal_f1_score", 1), ("normal_f1_score_100", 100)):
        score = _finite_score(classification.get(key))
        if score is not None:
            return score / scale
    return None


def duel_comparison(comparison: dict) -> dict:
    """Filter diagnostic baselines and rank only available, recorded LSTM scores."""
    result = _project(comparison)
    models = result.get("models") or {}
    maes = {name: _finite_score(metrics.get("mae")) for name, metrics in models.items()}
    maes = {name: score for name, score in maes.items() if score is not None}
    f1s = {}
    for name, metrics in models.items():
        score = _classification_score(metrics)
        if score is not None:
            f1s[name] = score
    result["best_model_by_test_mae"] = min(maes, key=maes.__getitem__) if maes else None
    result["best_model_by_f1_score"] = max(f1s, key=lambda name: (f1s[name], -maes.get(name, math.inf))) if f1s else None
    return result


def duel_series(series: dict) -> dict:
    """Keep observations, events and recorded LSTM values from legacy series."""
    result = _project(series)
    if isinstance(result.get("anomaly_points"), list):
        result["anomaly_points"] = [
            point for point in result["anomaly_points"]
            if point.get("is_anomaly") or not point.get("models")
            or not all(point["models"].get(name, {}).get("status") == "TN" for name in DUEL_MODEL_KEYS)
        ]
    return result
