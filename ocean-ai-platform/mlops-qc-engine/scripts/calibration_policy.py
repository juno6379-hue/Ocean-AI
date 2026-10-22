"""Held-out calibration objectives, kept separate from reported evaluation metrics."""
from __future__ import annotations

import importlib
import math

np = importlib.import_module("numpy")
pd = importlib.import_module("pandas")


def legacy_operational_threshold(dev_value: float) -> dict:
    """Decode the exact float operations of the unchanged operational scripts."""
    dev = float(dev_value)
    if not math.isfinite(dev) or dev < 0:
        raise ValueError("운영 DEV 임계값은 유한한 0 이상의 숫자여야 합니다.")
    sigma = next((sigma for upper, sigma in ((5.0, 6), (7.0, 5), (9.0, 4),
                                             (12.0, 3), (14.0, 2)) if dev <= upper), 1)
    std = dev / 3.0
    return {"effective_sigma": sigma, "std_estimate_cm": std,
            "effective_threshold_cm": std * sigma}


def encode_operational_threshold(*, raw_threshold_3sigma_cm: float,
                                 effective_threshold_cm: float,
                                 champion_raw_threshold_3sigma_cm: float | None = None,
                                 champion_effective_threshold_cm: float | None = None) -> dict:
    """Find the smallest DEV float satisfying both operational sensitivity floors.

    The stepped transform drops at each boundary. Search every branch instead
    of assuming that an increase of DEV always increases the LSTM threshold.
    """
    raw, calibrated = float(raw_threshold_3sigma_cm), float(effective_threshold_cm)
    reference = champion_raw_threshold_3sigma_cm is not None
    if reference != (champion_effective_threshold_cm is not None):
        raise ValueError("기존 모델의 원시 3σ와 유효 임계값을 함께 제공해야 합니다.")
    champion_raw = float(champion_raw_threshold_3sigma_cm) if champion_raw_threshold_3sigma_cm is not None else None
    champion_effective = float(champion_effective_threshold_cm) if champion_effective_threshold_cm is not None else None
    values = [raw, calibrated] + ([champion_raw, champion_effective] if reference else [])
    if any(value is None or not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("배포 임계값과 기존 모델 기준은 유한한 0 이상의 숫자여야 합니다.")
    raw_floor = max(raw, champion_raw if champion_raw is not None else 0.0)
    effective_floor = max(calibrated, champion_effective if champion_effective is not None else 0.0)
    feasible = []
    lower = 0.0
    for upper, sigma in ((5.0, 6), (7.0, 5), (9.0, 4), (12.0, 3), (14.0, 2), (math.inf, 1)):
        branch_floor = 0.0 if lower == 0.0 else math.nextafter(lower, math.inf)
        dev = max(raw_floor, branch_floor, (effective_floor / sigma) * 3.0)
        if not math.isfinite(dev) or dev > upper:
            lower = upper
            continue
        # Binary64 division/multiplication can put the analytic inverse one ULP
        # below the target. Adjust using the actual frozen-script expression.
        while dev <= upper and legacy_operational_threshold(dev)["effective_threshold_cm"] < effective_floor:
            dev = math.nextafter(dev, math.inf)
        if math.isfinite(dev) and dev <= upper:
            while dev > max(raw_floor, branch_floor):
                previous = math.nextafter(dev, 0.0)
                if previous < max(raw_floor, branch_floor) or legacy_operational_threshold(previous)["effective_threshold_cm"] < effective_floor:
                    break
                dev = previous
            feasible.append(dev)
        lower = upper
    if not feasible:
        raise ValueError("운영 계단식 계산으로 표현할 수 있는 배포 임계값이 없습니다.")
    dev = min(feasible)
    decoded = legacy_operational_threshold(dev)
    return {
        "raw_threshold_3sigma_cm": raw,
        "calibrated_effective_threshold_cm": calibrated,
        "operational_deploy_threshold_3sigma_cm": dev,
        **decoded,
        "effective_lstm_threshold_cm": decoded["effective_threshold_cm"],
        "champion_raw_threshold_3sigma_cm": champion_raw,
        "champion_effective_threshold_cm": champion_effective,
        "threshold_application_method": "OPERATIONAL_LEGACY_STEPPED_3SIGMA",
        "operational_encoding": {
            "algorithm": "MINIMUM_SAFE_PIECEWISE_INVERSE_V1",
            "raw_lower_bound_cm": raw_floor,
            "effective_lower_bound_cm": effective_floor,
            "champion_reference_available": reference,
            "numerical_constraints_passed": dev >= raw_floor and decoded["effective_threshold_cm"] >= effective_floor,
            "dev_float_hex": dev.hex(),
            "dev_serialization": "PYTHON_FLOAT_REPR_ROUNDTRIP",
        },
    }


def finalize_operational_calibration(threshold_info, normal_errors, anomaly_errors, *,
                                     champion_raw_threshold_3sigma_cm,
                                     champion_effective_threshold_cm,
                                     anomaly_timestamps=None) -> dict:
    """Re-evaluate held-out calibration observations at the DEV-deployed threshold."""
    normal = np.asarray(normal_errors, dtype=np.float64).reshape(-1)
    anomaly = np.asarray(anomaly_errors, dtype=np.float64).reshape(-1)
    if (not len(normal) or not np.isfinite(normal).all() or not np.isfinite(anomaly).all()
            or np.any(normal < 0) or np.any(anomaly < 0)):
        raise ValueError("보정 오차는 정상 표본이 있는 유한한 절댓값이어야 합니다.")
    result = dict(threshold_info)
    preserve = ("validation_tp_count", "validation_fp_count", "validation_fn_count",
                "validation_fp_rate", "validation_specificity", "validation_f1_score_100",
                "calibration_guardrails_passed", "calibration_objective_score_100",
                "effective_sigma", "std_estimate_cm")
    result.update({f"calibrated_{key}": result[key] for key in preserve if key in result})
    result.update(encode_operational_threshold(
        raw_threshold_3sigma_cm=result["raw_threshold_3sigma_cm"],
        effective_threshold_cm=result["effective_threshold_cm"],
        champion_raw_threshold_3sigma_cm=champion_raw_threshold_3sigma_cm,
        champion_effective_threshold_cm=champion_effective_threshold_cm))
    threshold = result["effective_threshold_cm"]
    tp, fp, fn = int(np.sum(anomaly > threshold)), int(np.sum(normal > threshold)), int(np.sum(anomaly <= threshold))
    weights = np.ones(len(anomaly), dtype=np.float64)
    event_count = None
    if anomaly_timestamps is not None:
        times = pd.to_datetime(list(anomaly_timestamps), errors="raise")
        if len(times) != len(anomaly) or times.isna().any():
            raise ValueError("보정 B 시각과 오차 개수가 다르거나 시각이 비어 있습니다.")
        event_count = 0
        if len(times):
            ticks = np.asarray(times, dtype="datetime64[ns]").astype(np.int64)
            if np.any(np.diff(ticks) <= 0):
                raise ValueError("보정 B 시각은 중복 없이 오름차순이어야 합니다.")
            groups = np.cumsum(np.r_[True, np.diff(ticks) != 60_000_000_000]) - 1
            sizes = np.bincount(groups)
            event_count = int(len(sizes))
            weights = len(anomaly) / event_count / sizes[groups]
    weighted_tp = float(weights[anomaly > threshold].sum())
    reference = (result["operational_encoding"]["champion_reference_available"]
                 and bool(threshold_info.get("calibration_guardrails_available"))
                 and threshold_info.get("calibration_reference_fp") is not None
                 and threshold_info.get("calibration_reference_fn") is not None)
    passed = (fp <= int(threshold_info["calibration_reference_fp"])
              and fn <= int(threshold_info["calibration_reference_fn"])) if reference else None
    result.update({
        "validation_tp_count": tp, "validation_fp_count": fp, "validation_fn_count": fn,
        "validation_fp_rate": round(fp / len(normal), 6), "validation_specificity": 1 - fp / len(normal),
        "validation_f1_score_100": round(2 * tp / (2 * tp + fp + fn) * 100, 2) if len(anomaly) else None,
        "calibration_objective_score_100": round(2 * weighted_tp / (float(weights.sum()) + weighted_tp + fp) * 100, 6) if len(anomaly) else None,
        "calibration_event_count": event_count,
        "calibration_guardrails_available": bool(reference), "calibration_guardrails_passed": passed,
        "calibration_evaluated_threshold_cm": threshold,
        "calibration_threshold_basis": "DEPLOYED_OPERATIONAL_DEV",
    })
    return result


def optimize_calibration_threshold(normal_errors, anomaly_errors, sigma_grid=None, *,
                                  legacy_threshold_fn, anomaly_timestamps=None,
                                  specificity_floor=None, reference_normal_errors=None,
                                  reference_anomaly_errors=None, reference_threshold_cm=None):
    normal = np.asarray(normal_errors, dtype=np.float64).reshape(-1)
    anomaly = np.asarray(anomaly_errors, dtype=np.float64).reshape(-1)
    if (not len(normal) or not np.isfinite(normal).all() or not np.isfinite(anomaly).all()
            or np.any(normal < 0) or np.any(anomaly < 0)):
        raise ValueError("보정 오차는 정상 표본이 있는 유한한 절댓값이어야 합니다.")
    grid = (np.round(np.arange(1.5, 12.05, 0.1), 2) if sigma_grid is None
            else np.asarray(sigma_grid, dtype=np.float64).reshape(-1))
    if not len(grid) or not np.isfinite(grid).all() or np.any(grid < 1.5) or np.any(grid > 12.0):
        raise ValueError("시그마 탐색값은 1.5~12.0 범위의 유한한 숫자여야 합니다.")
    mean, std = float(normal.mean()), float(normal.std())
    raw = mean + 3 * std
    legacy = legacy_threshold_fn(raw)
    weights, event_count = np.ones(len(anomaly), dtype=np.float64), None
    if anomaly_timestamps is not None:
        times = pd.to_datetime(list(anomaly_timestamps), errors="raise")
        if len(times) != len(anomaly):
            raise ValueError("보정 B 시각과 오차 개수가 다릅니다.")
        missing_positions = [index for index, missing in enumerate(times.isna()) if missing]
        if missing_positions:
            raise ValueError(f"보정 B 시각이 없는 위치가 있습니다: {missing_positions}")
        event_count = 0
        if len(times):
            ticks = np.asarray(times, dtype="datetime64[ns]").astype(np.int64)
            if np.any(np.diff(ticks) <= 0):
                raise ValueError("보정 B 시각은 중복 없이 오름차순이어야 합니다.")
            groups = np.cumsum(np.r_[True, np.diff(ticks) != 60_000_000_000]) - 1
            sizes = np.bincount(groups)
            event_count = int(len(sizes))
            weights = len(anomaly) / event_count / sizes[groups]
    reference = any(v is not None for v in (
        reference_normal_errors, reference_anomaly_errors, reference_threshold_cm))
    ref_fp = ref_fn = 0
    reference_threshold = 0.0
    if reference:
        if reference_normal_errors is None or reference_anomaly_errors is None or reference_threshold_cm is None:
            raise ValueError("기존 모델 보정 기준은 G/B 오차와 임계값을 함께 제공해야 합니다.")
        reference_threshold = float(reference_threshold_cm)
        rn = np.asarray(reference_normal_errors, dtype=np.float64).reshape(-1)
        rb = np.asarray(reference_anomaly_errors, dtype=np.float64).reshape(-1)
        if (len(rn) != len(normal) or len(rb) != len(anomaly) or not np.isfinite(rn).all()
                or not np.isfinite(rb).all() or np.any(rn < 0) or np.any(rb < 0)
                or not math.isfinite(reference_threshold) or reference_threshold < 0):
            raise ValueError("기존 모델과 후보의 보정 표본 또는 임계값을 확인하세요.")
        ref_fp, ref_fn = int(np.sum(rn > reference_threshold)), int(np.sum(rb <= reference_threshold))
    minimum = 0.0
    if specificity_floor is not None:
        if not math.isfinite(float(specificity_floor)) or not 0 <= specificity_floor <= 1:
            raise ValueError("정상 특이도 하한은 0~1 사이여야 합니다.")
        allowed = int(math.floor((1 - specificity_floor) * len(normal) + 1e-9))
        if allowed < len(normal):
            minimum = float(np.sort(normal)[len(normal) - allowed - 1])

    def counts(threshold):
        return int(np.sum(anomaly > threshold)), int(np.sum(normal > threshold)), int(np.sum(anomaly <= threshold))

    def raw_f1(threshold):
        tp, fp, fn = counts(threshold)
        return 2 * tp / (2 * tp + fp + fn) if len(anomaly) else 0.0

    def objective(threshold):
        tp, fp = float(weights[anomaly > threshold].sum()), int(np.sum(normal > threshold))
        return 2 * tp / (float(weights.sum()) + tp + fp) if len(anomaly) else 0.0

    def safe(threshold):
        _, fp, fn = counts(threshold)
        return not reference or (fp <= ref_fp and fn <= ref_fn)

    candidates: list[tuple[float, float | None, str]] = [
        (max(minimum, mean + float(k) * std), float(k), "sigma_grid") for k in grid]
    candidates.append((max(minimum, legacy["effective_threshold_cm"]), None, "legacy_step"))
    if specificity_floor is not None:
        candidates.append((minimum, None, "specificity_floor"))
    if reference:
        candidates.append((max(minimum, reference_threshold), None, "reference_threshold"))
    threshold, k, source = max(candidates, key=lambda item: (
        safe(item[0]), objective(item[0]), -counts(item[0])[1],
        -abs((item[1] if item[1] is not None else 3.0) - 3), -item[0]))
    mode = "F1_GRID_SEARCH_OPTIMIZED"
    normal_only_guardrail_adjusted = False
    if not len(anomaly):
        legacy_threshold = max(minimum, legacy["effective_threshold_cm"])
        if reference and not safe(legacy_threshold) and safe(threshold):
            # Keep the selected safe candidate rather than overwrite it with an unsafe fallback.
            normal_only_guardrail_adjusted = True
            mode = "NORMAL_ONLY_GUARDRAIL_ADJUSTED"
        else:
            threshold, source, mode = legacy_threshold, "legacy_step", "STEPPED_3SIGMA_FALLBACK"
    # Save sufficient precision for identical strict > comparisons after reload.
    threshold = float(threshold)
    tp, fp, fn = counts(threshold)
    optimal_k = (threshold - mean) / std if std > 0 else 3.0
    return {
        "raw_threshold_3sigma_cm": round(raw, 6), "validation_mean_error_cm": round(mean, 6),
        "validation_std_error_cm": round(std, 6), "validation_normal_sample_count": int(len(normal)),
        "validation_anomaly_sample_count": int(len(anomaly)), "sigma_grid_count": int(len(grid)),
        "sigma_grid_max": float(max(grid)), "f1_at_3sigma": round(raw_f1(raw) * 100, 2) if len(anomaly) else None,
        "f1_at_legacy_step_sigma": round(raw_f1(legacy["effective_threshold_cm"]) * 100, 2) if len(anomaly) else None,
        "optimal_sigma_k": round(optimal_k, 6), "effective_sigma": round(optimal_k, 6),
        "std_estimate_cm": round(std, 6), "effective_threshold_cm": threshold,
        "validation_f1_score_100": round(raw_f1(threshold) * 100, 2) if len(anomaly) else None,
        "f1_at_optimal_sigma": round(raw_f1(threshold) * 100, 2) if len(anomaly) else None,
        "validation_fp_rate": round(fp / len(normal), 6), "validation_specificity": 1 - fp / len(normal),
        "validation_tp_count": tp, "validation_fp_count": fp, "validation_fn_count": fn,
        "threshold_optimization_mode": mode,
        "calibration_objective": "EVENT_BALANCED_F1" if anomaly_timestamps is not None else "POINT_F1",
        "calibration_objective_score_100": round(objective(threshold) * 100, 6) if len(anomaly) else None,
        "calibration_event_count": event_count, "calibration_reference_fp": ref_fp if reference else None,
        "calibration_reference_fn": ref_fn if reference else None,
        "calibration_guardrails_available": reference, "calibration_guardrails_passed": bool(safe(threshold)),
        "normal_only_guardrail_adjusted": normal_only_guardrail_adjusted,
        "specificity_floor": specificity_floor, "selected_threshold_source": source,
        "threshold_candidate_sources": sorted({item[2] for item in candidates}),
    }
