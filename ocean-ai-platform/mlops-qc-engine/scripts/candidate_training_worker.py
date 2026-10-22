"""Isolated candidate LSTM training and deterministic Champion/Candidate evaluation."""
from __future__ import annotations

import argparse
import ctypes
import faulthandler
import hashlib
import importlib
import json
import math
import os
import random
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("candidate_training_worker", sys.modules[__name__])
sys.modules.setdefault("scripts.candidate_training_worker", sys.modules[__name__])

joblib: Any = importlib.import_module("joblib")
np: Any = importlib.import_module("numpy")
pd: Any = importlib.import_module("pandas")
sklearn_prep: Any = importlib.import_module("sklearn.preprocessing")

from scripts.local_trial_manifest import confined_path, sha256, validate, write_json
from scripts.ocean_ai_snapshot import ParquetSnapshotAuthority, _contiguous_windows_for_frame
from scripts.workspace_paths import resolve_manifest_root
from scripts.training_diagnostics import record_training_stage, runtime_diagnostics, validate_training_arrays
from scripts.calibration_policy import (optimize_calibration_threshold, legacy_operational_threshold,
                                        encode_operational_threshold, finalize_operational_calibration)
from scripts.evaluation_safety import honest_promotion_verdict as safe_promotion_verdict, event_detection_metrics, trend_reversal_diagnostics
from scripts.training_control import DEFAULT_EPOCHS, DEFAULT_BATCH_SIZE, build_training_callbacks, restore_best_training_weights
from scripts.comparison_contract import duel_comparison, duel_series

CANDIDATE_RUNS_ROOT = BASE / "reports/candidate_runs"
MANIFEST_PATH = BASE / "manifests/20261006_local_trial_manifest.json"
MAX_THRESHOLD_CM = 30.0
EVALUATION_CONTRACT_VERSION = 3

_tf_engine = None


def tensorflow_engine():
    global _tf_engine
    if _tf_engine is None:
        engine = importlib.import_module("tensorflow")
        engine.config.set_visible_devices([], "GPU")
        engine.config.threading.set_inter_op_parallelism_threads(1)
        engine.config.threading.set_intra_op_parallelism_threads(1)
        _tf_engine = engine
    return _tf_engine


def compute_effective_threshold(raw_threshold_3sigma_cm: float) -> dict:
    """Exact stepped sigma rule from the unchanged operational scripts."""
    val = float(raw_threshold_3sigma_cm)
    return {"raw_threshold_3sigma_cm": val, **legacy_operational_threshold(val)}


def optimize_f1_threshold_sigma(val_normal_errors, val_anomaly_errors, sigma_grid=None, *,
                                anomaly_timestamps=None, specificity_floor=None,
                                reference_normal_errors=None, reference_anomaly_errors=None,
                                reference_threshold_cm=None) -> dict:
    """Select a frozen threshold on matched held-out G/B calibration observations."""
    return optimize_calibration_threshold(
        val_normal_errors, val_anomaly_errors, sigma_grid,
        legacy_threshold_fn=compute_effective_threshold, anomaly_timestamps=anomaly_timestamps,
        specificity_floor=specificity_floor, reference_normal_errors=reference_normal_errors,
        reference_anomaly_errors=reference_anomaly_errors, reference_threshold_cm=reference_threshold_cm)


def load_candidate_threshold(bundle_dir: Path, metadata: dict | None = None) -> dict:
    """Read frozen T directly; historical numeric DEV bundles retain the stepped rule."""
    bundle_dir = Path(bundle_dir)
    raw = float((bundle_dir / "Thres.forecast.DEV").read_text(encoding="utf-8").strip())
    if not math.isfinite(raw) or raw < 0:
        raise ValueError("DEV 임계값이 유한한 0 이상의 숫자가 아닙니다.")
    sidecar = bundle_dir / "threshold_metadata.json"
    artifact_file = bundle_dir.parent / "artifact.json"
    artifact = json.loads(artifact_file.read_text(encoding="utf-8")) if artifact_file.is_file() else {}
    expected = ((artifact.get("bundle") or {}).get("threshold_metadata") or {}).get("sha256")
    if metadata is None and expected and not sidecar.is_file():
        raise ValueError("번들에 선언된 임계값 메타데이터 파일이 없습니다.")
    if metadata is None and sidecar.is_file():
        if expected and sha256(sidecar) != expected:
            raise ValueError("임계값 메타데이터 해시가 번들 기록과 다릅니다.")
        document = json.loads(sidecar.read_text(encoding="utf-8"))
        if document.get("schema_version") != "ocean-ai-threshold-2":
            raise ValueError("임계값 메타데이터 버전이 올바르지 않습니다.")
        if document.get("dev_sha256") and document["dev_sha256"] != sha256(bundle_dir / "Thres.forecast.DEV"):
            raise ValueError("임계값 메타데이터의 DEV 해시가 다릅니다.")
        metadata = document["threshold"]
    if metadata is None:
        return compute_effective_threshold(raw)
    info = dict(metadata)
    if info.get("threshold_optimization_mode") not in {
            "F1_GRID_SEARCH_OPTIMIZED", "STEPPED_3SIGMA_FALLBACK", "NORMAL_ONLY_GUARDRAIL_ADJUSTED"}:
        raise ValueError("임계값 메타데이터의 계산 모드를 확인할 수 없습니다.")
    if info.get("threshold_application_method") == "OPERATIONAL_LEGACY_STEPPED_3SIGMA":
        canonical = encode_operational_threshold(
            raw_threshold_3sigma_cm=info["raw_threshold_3sigma_cm"],
            effective_threshold_cm=info["calibrated_effective_threshold_cm"],
            champion_raw_threshold_3sigma_cm=info.get("champion_raw_threshold_3sigma_cm"),
            champion_effective_threshold_cm=info.get("champion_effective_threshold_cm"))
        dev = float(info["operational_deploy_threshold_3sigma_cm"])
        if raw != dev or dev != canonical["operational_deploy_threshold_3sigma_cm"]:
            raise ValueError("운영 DEV 배포값과 임계값 인코딩 기록이 다릅니다.")
        effective = float(info["effective_threshold_cm"])
        if effective != canonical["effective_threshold_cm"]:
            raise ValueError("운영 DEV의 계단식 유효 임계값과 메타데이터가 다릅니다.")
        if ("effective_lstm_threshold_cm" in info
                and float(info["effective_lstm_threshold_cm"]) != effective):
            raise ValueError("운영 LSTM 유효 임계값 표시와 배포값이 다릅니다.")
        return {**info, **canonical}
    if "operational_deploy_threshold_3sigma_cm" in info:
        raise ValueError("운영 DEV 배포값의 적용 방식을 확인할 수 없습니다.")
    if not math.isclose(raw, float(info["raw_threshold_3sigma_cm"]), rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("DEV 원시 3σ와 임계값 메타데이터가 다릅니다.")
    effective = float(info["effective_threshold_cm"])
    if not math.isfinite(effective) or effective < 0:
        raise ValueError("최적 유효 임계값이 올바르지 않습니다.")
    return info


def write_candidate_threshold(bundle_dir: Path, threshold_info: dict) -> tuple[Path, Path]:
    """Persist a frozen operational DEV float and its verifiable sidecar."""
    if threshold_info.get("threshold_application_method") != "OPERATIONAL_LEGACY_STEPPED_3SIGMA":
        raise ValueError("후보 배포 임계값은 운영 계단식 인코딩을 사용해야 합니다.")
    canonical = encode_operational_threshold(
        raw_threshold_3sigma_cm=threshold_info["raw_threshold_3sigma_cm"],
        effective_threshold_cm=threshold_info["calibrated_effective_threshold_cm"],
        champion_raw_threshold_3sigma_cm=threshold_info.get("champion_raw_threshold_3sigma_cm"),
        champion_effective_threshold_cm=threshold_info.get("champion_effective_threshold_cm"))
    for key in ("operational_deploy_threshold_3sigma_cm", "effective_threshold_cm"):
        if float(threshold_info[key]) != canonical[key]:
            raise ValueError("후보 임계값과 운영 배포 인코딩 계산이 다릅니다.")
    dev_path = Path(bundle_dir) / "Thres.forecast.DEV"
    metadata_path = Path(bundle_dir) / "threshold_metadata.json"
    dev = canonical["operational_deploy_threshold_3sigma_cm"]
    write_immutable_bytes(dev_path, (repr(dev) + "\n").encode("utf-8"))
    write_immutable_bytes(metadata_path, json.dumps({
        "schema_version": "ocean-ai-threshold-2", "threshold": threshold_info,
        "dev_sha256": sha256(dev_path)}, ensure_ascii=False, sort_keys=True,
        allow_nan=False).encode("utf-8"))
    return dev_path, metadata_path


def honest_promotion_verdict(candidate: dict, champion: dict, natural_b_windows: int) -> dict:
    """The recommendation and actual promotion share the same raw-count safety policy."""
    return safe_promotion_verdict(candidate, champion, natural_b_windows)


def _classification_score(evaluation: dict) -> float:
    cls = evaluation["classification"]
    positive = cls["tp"] if cls["anomaly_b_windows"] else cls["tn"]
    denominator = 2 * positive + cls["fp"] + cls["fn"]
    return 2.0 * positive / denominator if denominator else 0.0


def _natural_classification(y_normal, pred_normal, y_b, pred_b, threshold_info) -> dict:
    count = int(len(y_b))
    result = classification_metrics_summary(
        np.concatenate([y_normal, y_b]), np.concatenate([pred_normal, pred_b]),
        np.concatenate([np.zeros(len(y_normal), dtype=bool), np.ones(count, dtype=bool)]),
        threshold_info["effective_threshold_cm"],
        evaluation_mode="NATURAL_MQC_FLAG_G_AND_B" if count else "NATURAL_MQC_FLAG_G_ONLY",
        natural_b_count=count)
    return {**result, "natural_mqc": dict(result)}


def _evaluation_classification(y_g, pred_g, y_b, pred_b, threshold_info, b_timestamps):
    result = _natural_classification(y_g, pred_g, y_b, pred_b, threshold_info)
    events = event_detection_metrics(
        b_timestamps, [True] * len(y_b),
        (np.abs(y_b - pred_b) > float(threshold_info["effective_threshold_cm"])).tolist())
    result.update(events)
    result["event_scope"] = "ELIGIBLE_B_TARGET_WINDOWS"
    return result


def _split_target_bounds(split: dict) -> tuple[str, str]:
    frame = split["frame"]
    if frame.empty:
        raise ValueError("평가 구간에 관측 자료가 없습니다.")
    return str(frame["OBS_TIME"].min()), str(frame["OBS_TIME"].max())


def _test_target_bounds(manifest: dict, splits: dict) -> tuple[str, str]:
    start, last_g = _split_target_bounds(splits["TEST"])
    return start, str(manifest["date_end"])[:10] + " 23:59:59" if manifest.get("date_end") else last_g


def _period_yms(start: str, end: str) -> list[str]:
    return [str(period).replace("-", "") for period in pd.period_range(start[:10], end[:10], freq="M")]


def _target_prd(splits: dict, times: list[str]) -> list[float]:
    mapping = {}
    for split in splits.values():
        frame = split["frame"]
        mapping.update(zip(frame["OBS_TIME"].astype(str).tolist(), frame["PRD"].tolist()))
    return [float(mapping[str(ts)]) for ts in times]


def _evaluation_windows(splits: dict, scope: str) -> tuple:
    if scope == "ALL":
        frame = pd.concat([splits[name]["frame"] for name in ("TRAIN", "VALIDATION", "TEST")], ignore_index=True)
        frame = frame.sort_values("OBS_TIME").drop(columns=["SPLIT"], errors="ignore")
        x, y, times, sources = _contiguous_windows_for_frame(frame)
        return x, y[:, 0], times, sources
    split = splits["TEST"]
    return split["X_raw"], split["y_raw"][:, 0], split["timestamps"], split["source_obs_timestamps"]


def validate_independent_evaluation(artifact: dict, train_manifest: dict, eval_manifest: dict, actual_scope: str) -> None:
    """A calendar month used for training or threshold calibration is unavailable for independent tests."""
    if eval_manifest["snapshot_id"] == train_manifest["snapshot_id"]:
        if actual_scope != "TEST":
            raise ValueError("학습 스냅샷에서는 독립 TEST 구간만 평가할 수 있습니다.")
        return
    def months(manifest, preferred=None):
        selected = preferred or manifest.get("selected_yms")
        if not selected:
            return set(_period_yms(manifest["date_start"], manifest["date_end"]))
        if not isinstance(selected, list):
            raise ValueError("selected_yms는 연·월 문자열 목록이어야 합니다.")
        normalized = {str(ym).strip() for ym in selected}
        if any(not re.fullmatch(r"\d{6}", ym) or not 1 <= int(ym[4:]) <= 12 for ym in normalized):
            raise ValueError("selected_yms에 올바르지 않은 연·월이 있습니다.")
        return normalized
    train_yms = months(train_manifest, artifact.get("train_selected_yms") or artifact.get("training_yms"))
    calibration_yms = set((artifact.get("threshold") or {}).get("calibration_yms") or [])
    requested = months(eval_manifest)
    overlap = requested & (train_yms | calibration_yms)
    if overlap:
        raise ValueError("학습 또는 임계값 탐색에 사용한 달은 독립 평가에서 제외해야 합니다: " + ", ".join(sorted(overlap)))


def collect_calibration_anomalies(authority, snapshot_manifest, splits, excluded_yms=None) -> dict:
    """Collect B only from the same explicit validation intervals as normal G errors."""
    excluded = set(excluded_yms or [])
    validation_frame = splits["VALIDATION"]["frame"]
    if any(str(ts)[:7].replace("-", "") in excluded for ts in validation_frame["OBS_TIME"]):
        raise ValueError("보정 VALIDATION과 외부 평가 월이 겹칩니다.")
    intervals = authority.split_target_intervals(
        snapshot_manifest["snapshot_id"], "VALIDATION", manifest=snapshot_manifest)
    if not intervals and not snapshot_manifest.get("splits"):
        start, end = _split_target_bounds(splits["VALIDATION"])
        intervals = [(start, str(pd.Timestamp(end) + pd.Timedelta(minutes=1)))]
    selected = authority.extract_labeled_evaluation_windows(
        snapshot_manifest["snapshot_id"], manifest=snapshot_manifest, splits=splits,
        target_intervals=intervals)
    times = selected["natural_b_timestamps"]
    anomaly_file = authority.root / snapshot_manifest["snapshot_id"] / "labeled_anomalies.csv"
    sources = ([{"path": str(anomaly_file), "sha256": sha256(anomaly_file)}]
               if anomaly_file.is_file() else [])
    return {"X_raw": selected["X_natural_b"], "y_raw": selected["y_natural_b"],
            "source": "MATCHED_VALIDATION", "normal_split": "VALIDATION",
            "calibration_yms": sorted({str(ts)[:7].replace("-", "") for ts in validation_frame["OBS_TIME"]}),
            "calibration_timestamps": times, "calibration_source_files": sources,
            "calibration_periods": [{"date_start": start,
                "date_end": str(pd.Timestamp(end) - pd.Timedelta(minutes=1))} for start, end in intervals],
            "excluded_test_start": _split_target_bounds(splits["TEST"])[0],
            "excluded_yms": sorted(excluded)}


def scale_windows(scaler, x_raw):
    frame = pd.DataFrame(x_raw.reshape(-1, 2), columns=["OBS", "PRD"])
    scaled = scaler.transform(frame).reshape(-1, 4, 2)
    if not np.isfinite(scaled).all():
        raise ValueError("Non-finite scaled input window")
    return scaled.astype(np.float32)


def inverse_obs(scaled_col_1d, scaler):
    col = np.asarray(scaled_col_1d, dtype=float).reshape(-1, 1)
    dummy_prd = np.zeros_like(col)
    stacked = np.hstack([col, dummy_prd])
    physical = scaler.inverse_transform(stacked)[:, 0]
    if not np.isfinite(physical).all():
        raise ValueError("Non-finite inverse-transformed prediction")
    return np.asarray(physical, dtype=np.float64)


def predict_keras_model(model, scaler, x_raw) -> tuple:
    t0 = time.perf_counter()
    if len(x_raw) == 0:
        return np.empty((0,), dtype=np.float64), 0.0
    scaled = np.ascontiguousarray(scale_windows(scaler, x_raw), dtype=np.float32)
    chunk_size = 16384
    if len(scaled) <= chunk_size:
        out = np.asarray(model(scaled, training=False), dtype=np.float64)
    else:
        chunks = [
            np.asarray(model(scaled[i : i + chunk_size], training=False), dtype=np.float64)
            for i in range(0, len(scaled), chunk_size)
        ]
        out = np.vstack(chunks)
    preds = inverse_obs(out[:, 0], scaler)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return preds, elapsed_ms


def classification_metrics_summary(
    y_true,
    y_pred,
    is_anomaly_true,
    effective_threshold_cm: float,
    evaluation_mode: str = "NATURAL_MQC_FLAG_G_AND_B",
    natural_b_count: int = 0,
) -> dict:
    """Compute binary anomaly classification metrics (G=0 Normal, B=1 Anomaly) and 100-point F1 score."""
    y_t = np.asarray(y_true, dtype=np.float64).reshape(-1)
    y_p = np.asarray(y_pred, dtype=np.float64).reshape(-1)
    true_anom = np.asarray(is_anomaly_true, dtype=bool).reshape(-1)
    eff_thresh = float(effective_threshold_cm)
    errors = np.abs(y_t - y_p)
    pred_anom = errors > eff_thresh

    tp = int(np.sum(pred_anom & true_anom))
    fp = int(np.sum(pred_anom & (~true_anom)))
    tn = int(np.sum((~pred_anom) & (~true_anom)))
    fn = int(np.sum((~pred_anom) & true_anom))
    total = int(tp + fp + tn + fn)
    actual_positives = int(tp + fn)
    actual_negatives = int(tn + fp)

    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    recall = float(tp / actual_positives) if actual_positives > 0 else 1.0
    f1_score = (
        float(2.0 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )
    specificity = float(tn / actual_negatives) if actual_negatives > 0 else 1.0
    normal_precision = float(tn / (tn + fn)) if (tn + fn) > 0 else 1.0
    normal_f1_score = (
        float(2.0 * normal_precision * specificity / (normal_precision + specificity))
        if (normal_precision + specificity) > 0
        else 0.0
    )
    accuracy = float((tp + tn) / total) if total > 0 else 1.0
    macro_f1_score = (
        float((f1_score + normal_f1_score) / 2.0)
        if actual_positives > 0
        else normal_f1_score
    )

    result = {
        "evaluation_mode": evaluation_mode,
        "effective_threshold_cm": round(eff_thresh, 6),
        "total_evaluated_windows": total,
        "normal_g_windows": actual_negatives,
        "anomaly_b_windows": actual_positives,
        "natural_mqc_b_windows": int(natural_b_count),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "specificity": round(specificity, 6),
        "accuracy": round(accuracy, 6),
        "f1_score": round(f1_score, 6),
        "normal_f1_score": round(normal_f1_score, 6),
        "macro_f1_score": round(macro_f1_score, 6),
        "precision_100": round(precision * 100.0, 2),
        "recall_100": round(recall * 100.0, 2),
        "specificity_100": round(specificity * 100.0, 2),
        "accuracy_100": round(accuracy * 100.0, 2),
        "f1_score_100": round(f1_score * 100.0, 2),
        "normal_f1_score_100": round(normal_f1_score * 100.0, 2),
        "macro_f1_score_100": round(macro_f1_score * 100.0, 2),
    }
    if actual_positives == 0:
        for key in ("precision", "recall", "f1_score", "precision_100", "recall_100", "f1_score_100"):
            result[key] = None
    return result




def metrics_summary(
    y_true,
    y_pred,
    elapsed_ms: float,
    threshold_info: dict | None = None,
    classification_info: dict | None = None,
) -> dict:
    y_t = np.asarray(y_true, dtype=np.float64).reshape(-1)
    y_p = np.asarray(y_pred, dtype=np.float64).reshape(-1)
    errors = np.abs(y_t - y_p)
    mae = float(np.mean(errors))
    rmse = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
    max_err = float(np.max(errors)) if len(errors) else 0.0
    p95_err = float(np.percentile(errors, 95)) if len(errors) else 0.0
    count = int(len(y_t))
    result = {
        "sample_count": count,
        "mae": round(mae, 6),
        "rmse": round(rmse, 6),
        "mean_abs_error_cm": round(mae, 6),
        "std_abs_error_cm": round(float(np.std(errors)), 6),
        "p95_abs_error_cm": round(p95_err, 6),
        "max_abs_error_cm": round(max_err, 6),
        "latency": {
            "total_ms": round(float(elapsed_ms), 4),
            "per_window_ms": round(float(elapsed_ms) / max(1, count), 6),
        },
    }
    if threshold_info is not None:
        eff_thresh = threshold_info["effective_threshold_cm"]
        exceeded = int(np.sum(errors > eff_thresh))
        result["threshold"] = {
            **threshold_info,
            "test_exceedance_count": exceeded,
            "test_exceedance_rate": round(exceeded / max(1, count), 6),
        }
    if classification_info is not None:
        result["classification"] = classification_info
    return result


def array_sha256(arr) -> str:
    contiguous = np.ascontiguousarray(np.asarray(arr, dtype=np.float64))
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


def write_immutable_bytes(path: Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"FROZEN_BUNDLE_ARTIFACT_MODIFIED: {path.name}")
    else:
        with path.open("xb") as stream:
            stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def load_champion_2025_assets(manifest: dict, station: str, sensor: str):
    tf = tensorflow_engine()
    root = resolve_manifest_root(manifest, BASE)
    pair = next(
        (p for p in manifest["models"] if p["station"] == station and p["sensor"] == sensor),
        None,
    )
    if pair is None:
        raise ValueError(f"2025 운영 매핑에서 관측소/센서를 찾지 못했습니다: {station} / {sensor}")
    model_path = confined_path(root, pair["model"])
    scaler_path = confined_path(root, pair["scaler"])
    thres_path = confined_path(root, pair["threshold"])
    model = tf.keras.models.load_model(str(model_path), compile=False)
    scaler = joblib.load(scaler_path)
    raw_threshold = float(thres_path.read_text(encoding="utf-8").strip())
    if tuple(model.input_shape[1:]) != (4, 2) or tuple(model.output_shape[1:]) != (1,):
        raise ValueError("Champion 2025 모델 입출력 구조가 (4, 2) -> (1,)이 아닙니다.")
    if getattr(scaler, "n_features_in_", None) != 2:
        raise ValueError("Champion 2025 스케일러의 피처 수가 2가 아닙니다.")
    return model, scaler, raw_threshold, pair


def _build_comparison_series_payload(
    *, station: str, sensor: str, sea: str, eval_times: list[str], eval_src_times: list[str],
    y_eval: Any, pred_champion: Any, pred_candidate: Any,
    natural_b_timestamps: list[str], y_natural_b: Any,
    pred_b_champion: Any, pred_b_candidate: Any, champ_eff_cm: float, cand_eff_cm: float,
    extra_meta: dict | None = None, model_thresholds: dict | None = None,
    eval_prd: Any = None, natural_b_prd: Any = None,
) -> dict:
    """Preserve every real minute target and every TP/FP/FN; the UI reduces visible points only."""
    thresholds = {"candidate": float(cand_eff_cm), "champion_2025": float(champ_eff_cm),
                  **{name: value for name, value in (model_thresholds or {}).items() if name in ("candidate", "champion_2025")}}
    points = []
    def append_rows(times, sources, truth, predictions, is_b, astronomical):
        count = len(truth)
        if len(times) != count or any(len(values) != count for values in predictions.values()):
            raise ValueError("차트 시각·관측값·모델 예측값의 개수가 다릅니다.")
        for i in range(count):
            ts, obs = str(times[i]), float(truth[i])
            details = {}
            for name, values in predictions.items():
                prediction = float(values[i])
                error = abs(obs - prediction)
                threshold = thresholds[name]
                detected = bool(error > threshold) if threshold is not None else None
                status = (("TP" if detected else "FN") if is_b else ("FP" if detected else "TN")) if threshold is not None else "UNAVAILABLE"
                details[name] = {"prediction": prediction, "error_cm": error,
                                 "threshold_cm": threshold, "detected": detected, "status": status}
            cand, champ = details["candidate"], details["champion_2025"]
            status = ("CAND_ONLY_TP" if cand["detected"] and not champ["detected"] else
                      "BOTH_TP" if cand["detected"] and champ["detected"] else
                      "CHAMP_ONLY_TP" if champ["detected"] else "FN") if is_b else (
                      "CAND_FP" if cand["detected"] else "CHAMP_FP_CAND_TN" if champ["detected"] else "NORMAL_G")
            points.append({
                "timestamp": ts, "source_obs_timestamp": str(sources[i]) if i < len(sources) else ts,
                "obs": obs, "y_true": obs, "y_clean_ref": None if is_b else obs,
                "prd": float(astronomical[i]) if astronomical is not None and i < len(astronomical) else None,
                **{name: data["prediction"] for name, data in details.items()},
                "is_anomaly": bool(is_b), "mqc_flag": "B" if is_b else "G",
                "anomaly_type": "NATURAL_MQC_B" if is_b else "NORMAL_G", "point_status": status,
                "candidate_error_cm": cand["error_cm"], "champion_error_cm": champ["error_cm"],
                "candidate_detected": cand["detected"], "champion_detected": champ["detected"],
                "models": details})
    append_rows(eval_times, eval_src_times, y_eval, {"champion_2025": pred_champion, "candidate": pred_candidate}, False, eval_prd)
    append_rows(natural_b_timestamps, natural_b_timestamps, y_natural_b, {"champion_2025": pred_b_champion, "candidate": pred_b_candidate}, True, natural_b_prd)
    points.sort(key=lambda p: p["timestamp"])
    events = []
    for index, point in enumerate(points):
        point["index"] = index
        point["gap_before"] = bool(index and pd.Timestamp(point["timestamp"]) - pd.Timestamp(points[index - 1]["timestamp"]) > pd.Timedelta(minutes=1))
        if point["is_anomaly"] or any(m["status"] == "FP" for m in point["models"].values()):
            events.append(point)
    return {
        "schema_version": "ocean-ai-series-2", "station": station, "sensor": sensor, "sea": sea,
        **(extra_meta or {}), "total_test_windows": int(len(y_eval)), "displayed_windows": len(points),
        "preferred_render_points": 1440, "resolution": "RAW_MINUTE_TARGETS", "model_thresholds": thresholds,
        "anomaly_mode": "NATURAL_MQC_B" if len(y_natural_b) else "NATURAL_MQC_FLAG_G_ONLY",
        "candidate_threshold_cm": float(cand_eff_cm), "champion_threshold_cm": float(champ_eff_cm),
        "anomaly_count_in_chart": int(len(y_natural_b)),
        "candidate_caught_in_chart": sum(p["is_anomaly"] and p["candidate_detected"] for p in points),
        "champion_caught_in_chart": sum(p["is_anomaly"] and p["champion_detected"] for p in points),
        "timestamps": [p["timestamp"] for p in points],
        "source_obs_timestamps": [p["source_obs_timestamp"] for p in points],
        "y_true": [p["obs"] for p in points], "y_true_clean": [p["y_clean_ref"] for p in points],
        "prd": [p["prd"] for p in points],
        **{name: [p[name] for p in points] for name in thresholds},
        "is_anomaly": [p["is_anomaly"] for p in points],
        "candidate_detected": [p["candidate_detected"] for p in points],
        "champion_detected": [p["champion_detected"] for p in points],
        "point_status": [p["point_status"] for p in points], "points": points, "anomaly_points": events,
    }


def evaluate_bundle_on_test(
    run_folder: Path,
    manifest: dict,
    snapshot_manifest: dict,
    splits: dict,
    replay: bool = False,
) -> dict:
    """Deterministic evaluation of Champion 2025 and Candidate on TEST windows. If replay=True, verifies bitwise match."""
    tf = tensorflow_engine()
    bundle_dir = run_folder / "bundle"
    cand_model_path = bundle_dir / "residual_lstm_forecast.h5"
    cand_scaler_path = bundle_dir / "scaler.forecast.gz"
    cand_thres_path = bundle_dir / "Thres.forecast.DEV"

    for p in (cand_model_path, cand_scaler_path, cand_thres_path):
        if not p.is_file():
            raise ValueError(f"번들 산출물이 누락되었습니다: {p.name}")

    cand_model = tf.keras.models.load_model(str(cand_model_path), compile=False)
    cand_scaler = joblib.load(cand_scaler_path)

    if tuple(cand_model.input_shape[1:]) != (4, 2) or tuple(cand_model.output_shape[1:]) != (1,):
        raise ValueError("후보 모델 입출력 구조가 (4, 2) -> (1,)이 아닙니다.")
    if getattr(cand_scaler, "n_features_in_", None) != 2:
        raise ValueError("후보 스케일러의 피처 수가 2가 아닙니다.")

    station = snapshot_manifest["station"]
    sensor = snapshot_manifest["sensor"]
    champ_model, champ_scaler, champ_raw_thres, champ_pair = load_champion_2025_assets(
        manifest, station, sensor
    )

    test_split = splits["TEST"]
    x_test = test_split["X_raw"]
    y_test = test_split["y_raw"][:, 0]
    test_times = test_split["timestamps"]
    test_src_times = test_split["source_obs_timestamps"]

    pred_champion, ms_champion = predict_keras_model(champ_model, champ_scaler, x_test)
    pred_candidate, ms_candidate = predict_keras_model(cand_model, cand_scaler, x_test)

    paired_digests = {
        "y_true_sha256": array_sha256(y_test),
        "champion_2025_sha256": array_sha256(pred_champion),
        "candidate_sha256": array_sha256(pred_candidate),
    }

    npz_path = run_folder / "paired_test_predictions.npz"
    if replay:
        if not npz_path.is_file():
            raise ValueError("재현 검증 대상인 paired_test_predictions.npz 파일이 없습니다.")
        with np.load(npz_path, allow_pickle=False) as saved:
            current_threshold = load_candidate_threshold(bundle_dir)
            if "candidate_effective_threshold_cm" in saved and float(saved["candidate_effective_threshold_cm"][0]) != float(current_threshold["effective_threshold_cm"]):
                raise ValueError("재현 검증 중 동결된 임계값이 변경되었습니다.")
            current_signature = sha256(bundle_dir / "threshold_metadata.json") if (bundle_dir / "threshold_metadata.json").is_file() else sha256(cand_thres_path)
            if "threshold_signature" in saved and str(saved["threshold_signature"][0]) != current_signature:
                raise ValueError("재현 검증 중 임계값 메타데이터 해시가 변경되었습니다.")
            bitwise_checks = {
                "y_true": bool(np.array_equal(saved["y_true"], y_test)),
                "champion_2025": bool(np.array_equal(saved["champion_2025"], pred_champion)),
                "candidate": bool(np.array_equal(saved["candidate"], pred_candidate)),
            }
            if "anomaly_y_true" in saved:
                authority = ParquetSnapshotAuthority()
                labeled = authority.extract_labeled_evaluation_windows(
                    snapshot_manifest["snapshot_id"], manifest=snapshot_manifest, splits=splits,
                    target_intervals=authority.split_target_intervals(
                        snapshot_manifest["snapshot_id"], "TEST", manifest=snapshot_manifest))
                bx, by = labeled["X_natural_b"], labeled["y_natural_b"][:, 0]
                bitwise_checks["anomaly_y_true"] = bool(np.array_equal(saved["anomaly_y_true"], by))
                bitwise_checks["anomaly_timestamps"] = bool(np.array_equal(
                    saved["anomaly_timestamps"], np.asarray(labeled["natural_b_timestamps"])))
                predictions = {
                    "candidate": predict_keras_model(cand_model, cand_scaler, bx)[0],
                    "champion_2025": predict_keras_model(champ_model, champ_scaler, bx)[0],
                } if len(bx) else {name: np.empty((0,), dtype=np.float64)
                                  for name in ("candidate", "champion_2025")}
                for name, prediction in predictions.items():
                    bitwise_checks[f"anomaly_{name}"] = bool(np.array_equal(saved[f"anomaly_{name}"], prediction))
        if not all(bitwise_checks.values()):
            raise ValueError(f"결정론적 재현 검증 실패(비트 불일치): {bitwise_checks}")
        replay_report = {
            "passed": True,
            "replay_mode": True,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "bitwise_identical": True,
            "model_checks": bitwise_checks,
            "paired_digests": paired_digests,
            "test_window_count": int(len(y_test)),
        }
        write_json(run_folder / "replay_verification.json", replay_report)
        return replay_report

    authority = ParquetSnapshotAuthority()
    labeled_eval = authority.extract_labeled_evaluation_windows(
        snapshot_manifest["snapshot_id"],
        manifest=snapshot_manifest,
        splits=splits,
        target_intervals=authority.split_target_intervals(snapshot_manifest["snapshot_id"], "TEST", manifest=snapshot_manifest),
    )
    x_natural_b = labeled_eval["X_natural_b"]
    y_natural_b = (
        labeled_eval["y_natural_b"][:, 0]
        if len(labeled_eval["y_natural_b"]) > 0
        else np.empty((0,), dtype=np.float64)
    )
    natural_b_count = int(len(x_natural_b))

    if natural_b_count > 0:
        pred_b_champion, _ = predict_keras_model(champ_model, champ_scaler, x_natural_b)
        pred_b_candidate, _ = predict_keras_model(cand_model, cand_scaler, x_natural_b)
    else:
        pred_b_champion = np.empty((0,), dtype=np.float64)
        pred_b_candidate = np.empty((0,), dtype=np.float64)

    champ_thres_info = compute_effective_threshold(champ_raw_thres)
    cand_thres_info = load_candidate_threshold(bundle_dir)

    def _build_model_classification(pred_test_arr, pred_b_arr, thres_dict):
        return _evaluation_classification(y_test, pred_test_arr, y_natural_b, pred_b_arr, thres_dict,
                                          labeled_eval["natural_b_timestamps"])

    cls_champion = _build_model_classification(pred_champion, pred_b_champion, champ_thres_info)
    cls_candidate = _build_model_classification(pred_candidate, pred_b_candidate, cand_thres_info)

    eval_champion = metrics_summary(y_test, pred_champion, ms_champion, champ_thres_info, cls_champion)
    eval_candidate = metrics_summary(y_test, pred_candidate, ms_candidate, cand_thres_info, cls_candidate)
    for evaluation, prediction in ((eval_champion, pred_champion), (eval_candidate, pred_candidate)):
        evaluation["trend_reversal"] = trend_reversal_diagnostics(
            x_test, y_test, prediction, evaluation["threshold"]["effective_threshold_cm"])

    np.savez_compressed(
        npz_path,
        y_true=y_test,
        champion_2025=pred_champion,
        candidate=pred_candidate,
        anomaly_y_true=y_natural_b,
        anomaly_timestamps=np.asarray(labeled_eval["natural_b_timestamps"]),
        anomaly_candidate=pred_b_candidate,
        anomaly_champion_2025=pred_b_champion,
        timestamps=np.asarray(test_times),
        candidate_effective_threshold_cm=np.asarray([cand_thres_info["effective_threshold_cm"]]),
        threshold_signature=np.asarray([sha256(bundle_dir / "threshold_metadata.json") if (bundle_dir / "threshold_metadata.json").is_file() else sha256(cand_thres_path)]),
    )

    series_payload = _build_comparison_series_payload(
        station=station,
        sensor=sensor,
        sea=champ_pair["sea"],
        eval_times=test_times,
        eval_src_times=test_src_times,
        y_eval=y_test,
        pred_champion=pred_champion,
        pred_candidate=pred_candidate,
        natural_b_timestamps=labeled_eval.get("natural_b_timestamps") or [],
        y_natural_b=y_natural_b,
        pred_b_champion=pred_b_champion,
        pred_b_candidate=pred_b_candidate,
        champ_eff_cm=float(champ_thres_info["effective_threshold_cm"]),
        cand_eff_cm=float(cand_thres_info["effective_threshold_cm"]),
        model_thresholds={"candidate": cand_thres_info["effective_threshold_cm"], "champion_2025": champ_thres_info["effective_threshold_cm"]},
        eval_prd=_target_prd(splits, test_times),
        natural_b_prd=labeled_eval.get("natural_b_prd"),
    )
    write_json(run_folder / "series_comparison.json", series_payload)

    # Determine winner by TEST MAE and F1-Score and compare candidate vs champion_2025
    models_map = {
        "champion_2025": eval_champion,
        "candidate": eval_candidate,
    }
    best_model_name = min(models_map.keys(), key=lambda k: models_map[k]["mae"])
    best_model_by_f1 = max(models_map.keys(), key=lambda k: (_classification_score(models_map[k]), -models_map[k]["mae"]))
    mae_improvement_cm = round(eval_champion["mae"] - eval_candidate["mae"], 6)
    rmse_improvement_cm = round(eval_champion["rmse"] - eval_candidate["rmse"], 6)
    f1_100_improvement = (round(100.0 * (_classification_score(eval_candidate) - _classification_score(eval_champion)), 2) if natural_b_count else None)

    comparison = {
        "schema_version": "ocean-ai-comparison-1",
        "evaluation_contract_version": EVALUATION_CONTRACT_VERSION,
        "threshold_signature": sha256(bundle_dir / "threshold_metadata.json") if (bundle_dir / "threshold_metadata.json").is_file() else sha256(cand_thres_path),
        "domain": "fixed_station",
        "item_id": "tide",
        "target_variable": "TIDE_LEVEL",
        "station": station,
        "sensor": sensor,
        "sea": champ_pair["sea"],
        "snapshot_id": snapshot_manifest["snapshot_id"],
        "dataset_id": snapshot_manifest["dataset_id"],
        "test_window_count": int(len(y_test)),
        "anomaly_evaluation": {
            "evaluation_mode": cls_candidate["evaluation_mode"],
            "natural_mqc_b_windows": natural_b_count,
            "total_anomaly_rows_in_snapshot": int(labeled_eval["total_anomaly_rows"]),
            "test_normal_g_windows": int(len(y_test)),
        },
        "models": models_map,
        "best_model_by_test_mae": best_model_name,
        "best_model_by_f1_score": best_model_by_f1,
        "candidate_vs_champion_2025": {
            **honest_promotion_verdict(eval_candidate, eval_champion, natural_b_count),
            "candidate_better_or_equal_mae": bool(eval_candidate["mae"] <= eval_champion["mae"]),
            "mae_delta_cm": round(eval_candidate["mae"] - eval_champion["mae"], 6),
            "mae_improvement_cm": mae_improvement_cm,
            "rmse_delta_cm": round(eval_candidate["rmse"] - eval_champion["rmse"], 6),
            "rmse_improvement_cm": rmse_improvement_cm,
            "candidate_f1_score_100": eval_candidate["classification"]["f1_score_100"],
            "champion_2025_f1_score_100": eval_champion["classification"]["f1_score_100"],
            "f1_score_100_improvement": f1_100_improvement,
            "candidate_threshold": cand_thres_info,
            "champion_2025_threshold": champ_thres_info,
        },
        "paired_digests": paired_digests,
        "paired_predictions_npz": {
            "path": str(npz_path),
            "sha256": sha256(npz_path),
            "bytes": npz_path.stat().st_size,
        },
    }
    return comparison


def evaluate_bundle_on_snapshot(
    run_folder: Path,
    manifest: dict,
    eval_snapshot_id: str,
    eval_scope: str = "AUTO",
) -> dict:
    """Evaluate Champion 2025 and Candidate on a target snapshot/period."""
    artifact_path = run_folder / "artifact.json"
    if not artifact_path.is_file():
        raise ValueError(f"후보 실행 산출물이 없습니다: {run_folder.name}")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    train_snapshot_id = artifact["snapshot_id"]
    station = artifact["station"]
    sensor = artifact["sensor"]

    bundle_dir = run_folder / "bundle"
    cand_model_path = bundle_dir / "residual_lstm_forecast.h5"
    cand_scaler_path = bundle_dir / "scaler.forecast.gz"
    cand_thres_path = bundle_dir / "Thres.forecast.DEV"
    for p in (cand_model_path, cand_scaler_path, cand_thres_path):
        if not p.is_file():
            raise ValueError(f"번들 산출물이 누락되었습니다: {p.name}")

    authority = ParquetSnapshotAuthority()
    eval_snap_manifest, eval_splits = authority.extract_split_windows(eval_snapshot_id)
    if eval_snap_manifest["station"] != station or eval_snap_manifest["sensor"] != sensor:
        raise ValueError(
            f"평가 스냅샷의 관측소/센서({eval_snap_manifest['station']}/{eval_snap_manifest['sensor']})가 "
            f"학습된 후보 모델({station}/{sensor})과 일치하지 않습니다."
        )

    scope_norm = (eval_scope or "AUTO").strip().upper()
    if scope_norm not in {"AUTO", "ALL", "TEST"}:
        raise ValueError("eval_scope는 AUTO, ALL, TEST 중 하나여야 합니다.")
    actual_scope = (
        ("TEST" if eval_snapshot_id == train_snapshot_id else "ALL")
        if scope_norm == "AUTO"
        else scope_norm
    )
    train_manifest, _ = authority.load_snapshot(train_snapshot_id)
    validate_independent_evaluation(artifact, train_manifest, eval_snap_manifest, actual_scope)
    load_candidate_threshold(bundle_dir)
    current_threshold_signature = sha256(bundle_dir / "threshold_metadata.json") if (bundle_dir / "threshold_metadata.json").is_file() else sha256(cand_thres_path)

    # Ensure original training TEST comparison is backed up before any cross-evaluation overwrite
    orig_comp_backup = run_folder / "comparison_train_test.json"
    orig_series_backup = run_folder / "series_train_test.json"
    if not orig_comp_backup.is_file() and (run_folder / "comparison.json").is_file():
        write_json(orig_comp_backup, json.loads((run_folder / "comparison.json").read_text(encoding="utf-8")))
    if not orig_series_backup.is_file() and (run_folder / "series_comparison.json").is_file():
        write_json(orig_series_backup, json.loads((run_folder / "series_comparison.json").read_text(encoding="utf-8")))

    # If user requests original training snapshot + TEST scope and backup exists with anomaly_points, restore and return it
    if eval_snapshot_id == train_snapshot_id and actual_scope == "TEST" and orig_comp_backup.is_file() and orig_series_backup.is_file():
        restored_series = duel_series(json.loads(orig_series_backup.read_text(encoding="utf-8")))
        cached_comparison = json.loads(orig_comp_backup.read_text(encoding="utf-8"))
        if (restored_series.get("schema_version") == "ocean-ai-series-2"
                and cached_comparison.get("evaluation_contract_version") == EVALUATION_CONTRACT_VERSION
                and cached_comparison.get("threshold_signature") == current_threshold_signature):
            restored_comp = duel_comparison(json.loads(orig_comp_backup.read_text(encoding="utf-8")))
            restored_comp["evaluated_snapshot_id"] = train_snapshot_id
            restored_comp["eval_snapshot_id"] = train_snapshot_id
            restored_comp["evaluated_scope"] = "TEST"
            restored_comp["eval_scope"] = "TEST"
            restored_comp["is_cross_evaluation"] = False
            restored_comp["evaluated_period"] = f"{eval_snap_manifest.get('date_start', '')} ~ {eval_snap_manifest.get('date_end', '')}"
            restored_comp["training_snapshot_id"] = train_snapshot_id
            write_json(run_folder / "comparison.json", restored_comp)
            write_json(run_folder / "series_comparison.json", restored_series)
            artifact["comparison_sha256"] = sha256(run_folder / "comparison.json")
            cross_evals = list(artifact.get("cross_evaluations") or [])
            restored_entry = dict(next(
                (e for e in cross_evals if e.get("eval_snapshot_id") == train_snapshot_id and e.get("eval_scope") == "TEST"),
                {
                    "eval_snapshot_id": train_snapshot_id,
                    "eval_scope": "TEST",
                    "is_cross_evaluation": False,
                    "evaluated_period": restored_comp["evaluated_period"],
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                    "window_count": int(restored_comp.get("test_window_count", 0)),
                    "natural_mqc_b_windows": int((restored_comp.get("anomaly_evaluation") or {}).get("natural_mqc_b_windows", 0)),
                    "candidate_mae": restored_comp["models"]["candidate"]["mae"],
                    "champion_2025_mae": restored_comp["models"]["champion_2025"]["mae"],
                    "candidate_f1_score_100": restored_comp["models"]["candidate"]["classification"]["f1_score_100"],
                    "champion_2025_f1_score_100": restored_comp["models"]["champion_2025"]["classification"]["f1_score_100"],
                    "report_file": f"evaluations/eval_{train_snapshot_id}_TEST.json",
                },
            ))
            restored_entry["is_cross_evaluation"] = False
            artifact["active_evaluation"] = restored_entry
            write_json(artifact_path, artifact)
            return restored_comp

    tf = tensorflow_engine()
    cand_model = tf.keras.models.load_model(str(cand_model_path), compile=False)
    cand_scaler = joblib.load(cand_scaler_path)

    champ_model, champ_scaler, champ_raw_thres, champ_pair = load_champion_2025_assets(
        manifest, station, sensor
    )

    champ_thres_info = compute_effective_threshold(champ_raw_thres)
    cand_thres_info = load_candidate_threshold(bundle_dir)

    x_eval, y_eval, eval_times, eval_src_times = _evaluation_windows(eval_splits, actual_scope)

    if len(x_eval) < 1:
        raise ValueError(f"선택한 평가 스냅샷({eval_snapshot_id})의 {actual_scope} 구간에 유효한 평가 입력창이 없습니다.")

    pred_champion, ms_champion = predict_keras_model(champ_model, champ_scaler, x_eval)
    pred_candidate, ms_candidate = predict_keras_model(cand_model, cand_scaler, x_eval)

    # Verify deterministic replay on external evaluation windows
    pred_candidate_replay, _ = predict_keras_model(cand_model, cand_scaler, x_eval)
    bitwise_identical = bool(np.array_equal(pred_candidate, pred_candidate_replay))

    labeled_eval = authority.extract_labeled_evaluation_windows(
        eval_snapshot_id,
        manifest=eval_snap_manifest,
        splits=eval_splits,
        target_intervals=(authority.split_target_intervals(eval_snapshot_id, "TEST", manifest=eval_snap_manifest)
                          if actual_scope == "TEST" else [(eval_snap_manifest["date_start"],
                              str(pd.Timestamp(eval_snap_manifest["date_end"]) + pd.Timedelta(days=1)))]),
    )
    x_natural_b = labeled_eval["X_natural_b"]
    y_natural_b = (
        labeled_eval["y_natural_b"][:, 0]
        if len(labeled_eval["y_natural_b"]) > 0
        else np.empty((0,), dtype=np.float64)
    )
    natural_b_count = int(len(x_natural_b))

    if natural_b_count > 0:
        pred_b_champion, _ = predict_keras_model(champ_model, champ_scaler, x_natural_b)
        pred_b_candidate, _ = predict_keras_model(cand_model, cand_scaler, x_natural_b)
    else:
        pred_b_champion = np.empty((0,), dtype=np.float64)
        pred_b_candidate = np.empty((0,), dtype=np.float64)

    def _build_model_classification(pred_test_arr, pred_b_arr, thres_dict):
        return _evaluation_classification(y_eval, pred_test_arr, y_natural_b, pred_b_arr, thres_dict,
                                          labeled_eval["natural_b_timestamps"])

    cls_champion = _build_model_classification(pred_champion, pred_b_champion, champ_thres_info)
    cls_candidate = _build_model_classification(pred_candidate, pred_b_candidate, cand_thres_info)

    eval_champion = metrics_summary(y_eval, pred_champion, ms_champion, champ_thres_info, cls_champion)
    eval_candidate = metrics_summary(y_eval, pred_candidate, ms_candidate, cand_thres_info, cls_candidate)
    for evaluation, prediction in ((eval_champion, pred_champion), (eval_candidate, pred_candidate)):
        evaluation["trend_reversal"] = trend_reversal_diagnostics(
            x_eval, y_eval, prediction, evaluation["threshold"]["effective_threshold_cm"])

    paired_digests = {
        "y_true_sha256": array_sha256(y_eval),
        "champion_2025_sha256": array_sha256(pred_champion),
        "candidate_sha256": array_sha256(pred_candidate),
    }

    evals_dir = run_folder / "evaluations"
    evals_dir.mkdir(parents=True, exist_ok=True)
    eval_tag = f"{eval_snapshot_id}_{actual_scope}"

    series_payload = _build_comparison_series_payload(
        station=station,
        sensor=sensor,
        sea=champ_pair["sea"],
        eval_times=eval_times,
        eval_src_times=eval_src_times,
        y_eval=y_eval,
        pred_champion=pred_champion,
        pred_candidate=pred_candidate,
        natural_b_timestamps=labeled_eval.get("natural_b_timestamps") or [],
        y_natural_b=y_natural_b,
        pred_b_champion=pred_b_champion,
        pred_b_candidate=pred_b_candidate,
        champ_eff_cm=float(champ_thres_info["effective_threshold_cm"]),
        cand_eff_cm=float(cand_thres_info["effective_threshold_cm"]),
        model_thresholds={"candidate": cand_thres_info["effective_threshold_cm"], "champion_2025": champ_thres_info["effective_threshold_cm"]},
        eval_prd=_target_prd(eval_splits, eval_times),
        natural_b_prd=labeled_eval.get("natural_b_prd"),
        extra_meta={
            "evaluated_snapshot_id": eval_snapshot_id,
            "evaluated_scope": actual_scope,
            "evaluated_period": f"{eval_snap_manifest.get('date_start', '')} ~ {eval_snap_manifest.get('date_end', '')}",
        },
    )
    write_json(evals_dir / f"series_{eval_tag}.json", series_payload)
    write_json(run_folder / "series_comparison.json", series_payload)
    if eval_snapshot_id == train_snapshot_id and actual_scope == "TEST":
        write_json(orig_series_backup, series_payload)

    models_map = {
        "champion_2025": eval_champion,
        "candidate": eval_candidate,
    }
    best_model_name = min(models_map.keys(), key=lambda k: models_map[k]["mae"])
    best_model_by_f1 = max(models_map.keys(), key=lambda k: (_classification_score(models_map[k]), -models_map[k]["mae"]))
    mae_improvement_cm = round(eval_champion["mae"] - eval_candidate["mae"], 6)
    rmse_improvement_cm = round(eval_champion["rmse"] - eval_candidate["rmse"], 6)
    f1_100_improvement = (round(100.0 * (_classification_score(eval_candidate) - _classification_score(eval_champion)), 2) if natural_b_count else None)

    existing_comp = (
        json.loads((run_folder / "comparison.json").read_text(encoding="utf-8"))
        if (run_folder / "comparison.json").is_file()
        else {}
    )
    comparison = {
        "schema_version": "ocean-ai-comparison-1",
        "evaluation_contract_version": EVALUATION_CONTRACT_VERSION,
        "threshold_signature": sha256(bundle_dir / "threshold_metadata.json") if (bundle_dir / "threshold_metadata.json").is_file() else sha256(cand_thres_path),
        "domain": "fixed_station",
        "item_id": "tide",
        "target_variable": "TIDE_LEVEL",
        "station": station,
        "sensor": sensor,
        "sea": champ_pair["sea"],
        "training_snapshot_id": train_snapshot_id,
        "snapshot_id": eval_snapshot_id,
        "evaluated_snapshot_id": eval_snapshot_id,
        "eval_snapshot_id": eval_snapshot_id,
        "evaluated_scope": actual_scope,
        "eval_scope": actual_scope,
        "is_cross_evaluation": bool(eval_snapshot_id != train_snapshot_id or actual_scope == "ALL"),
        "evaluated_period": f"{eval_snap_manifest.get('date_start', '')} ~ {eval_snap_manifest.get('date_end', '')}",
        "dataset_id": eval_snap_manifest["dataset_id"],
        "test_window_count": int(len(y_eval)),
        "anomaly_evaluation": {
            "evaluation_mode": cls_candidate["evaluation_mode"],
            "natural_mqc_b_windows": natural_b_count,
            "total_anomaly_rows_in_snapshot": int(labeled_eval["total_anomaly_rows"]),
            "test_normal_g_windows": int(len(y_eval)),
        },
        "models": models_map,
        "best_model_by_test_mae": best_model_name,
        "best_model_by_f1_score": best_model_by_f1,
        "candidate_vs_champion_2025": {
            **honest_promotion_verdict(eval_candidate, eval_champion, natural_b_count),
            "candidate_better_or_equal_mae": bool(eval_candidate["mae"] <= eval_champion["mae"]),
            "mae_delta_cm": round(eval_candidate["mae"] - eval_champion["mae"], 6),
            "mae_improvement_cm": mae_improvement_cm,
            "rmse_delta_cm": round(eval_candidate["rmse"] - eval_champion["rmse"], 6),
            "rmse_improvement_cm": rmse_improvement_cm,
            "candidate_f1_score_100": eval_candidate["classification"]["f1_score_100"],
            "champion_2025_f1_score_100": eval_champion["classification"]["f1_score_100"],
            "f1_score_100_improvement": f1_100_improvement,
            "candidate_threshold": cand_thres_info,
            "champion_2025_threshold": champ_thres_info,
        },
        "paired_digests": paired_digests,
        "paired_predictions_npz": existing_comp.get("paired_predictions_npz"),
        "validation_summary": existing_comp.get("validation_summary"),
        "replay_verification": {
            "passed": bitwise_identical,
            "replay_mode": True,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "bitwise_identical": bitwise_identical,
            "evaluated_snapshot_id": eval_snapshot_id,
            "evaluated_scope": actual_scope,
            "test_window_count": int(len(y_eval)),
        },
    }
    write_json(evals_dir / f"eval_{eval_tag}.json", comparison)
    write_json(run_folder / "comparison.json", comparison)

    cross_evals = list(artifact.get("cross_evaluations") or [])
    eval_entry = {
        "eval_snapshot_id": eval_snapshot_id,
        "eval_scope": actual_scope,
        "is_cross_evaluation": comparison["is_cross_evaluation"],
        "evaluated_period": comparison["evaluated_period"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "window_count": int(len(y_eval)),
        "natural_mqc_b_windows": natural_b_count,
        "candidate_mae": eval_candidate["mae"],
        "champion_2025_mae": eval_champion["mae"],
        "candidate_f1_score_100": eval_candidate["classification"]["f1_score_100"],
        "champion_2025_f1_score_100": eval_champion["classification"]["f1_score_100"],
        "report_file": f"evaluations/eval_{eval_tag}.json",
    }
    cross_evals = [e for e in cross_evals if not (e.get("eval_snapshot_id") == eval_snapshot_id and e.get("eval_scope") == actual_scope)]
    cross_evals.insert(0, eval_entry)
    artifact["comparison_sha256"] = sha256(run_folder / "comparison.json")
    artifact["cross_evaluations"] = cross_evals[:20]
    artifact["active_evaluation"] = eval_entry
    write_json(artifact_path, artifact)
    return comparison


def train_and_evaluate(
    snapshot_id: str,
    manifest_path: Path = MANIFEST_PATH,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    seed: int = 42,
    run_id: str | None = None,
    eval_snapshot_id: str | None = None,
    eval_scope: str = "AUTO",
    progress=lambda _: None,
) -> dict:
    if epochs < 1 or epochs > 200:
        raise ValueError("epochs는 1~200 사이여야 합니다.")
    if batch_size < 8 or batch_size > 1024:
        raise ValueError("batch_size는 8~1024 사이여야 합니다.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before_integrity = validate(manifest)

    authority = ParquetSnapshotAuthority()
    snapshot_manifest, splits = authority.extract_split_windows(snapshot_id)
    station = snapshot_manifest["station"]
    sensor = snapshot_manifest["sensor"]

    train_split = splits["TRAIN"]
    val_split = splits["VALIDATION"]
    test_split = splits["TEST"]

    if len(train_split["X_raw"]) < batch_size:
        raise ValueError(f"TRAIN 입력창 수({len(train_split['X_raw'])})가 batch_size({batch_size})보다 적습니다.")
    if len(val_split["X_raw"]) < 5 or len(test_split["X_raw"]) < 5:
        raise ValueError("VALIDATION 및 TEST 입력창 수가 최소 5개 이상이어야 합니다.")

    actual_run_id = run_id or (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    run_folder = CANDIDATE_RUNS_ROOT / actual_run_id
    bundle_dir = run_folder / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=False)

    random.seed(seed)
    np.random.seed(seed)
    record_training_stage(run_folder, "tensorflow_init_start", runtime=runtime_diagnostics())
    tf = tensorflow_engine()
    record_training_stage(run_folder, "tensorflow_init_end", tensorflow_version=tf.__version__,
        tensorflow_import_path=tf.__file__, tensorflow_build=tf.sysconfig.get_build_info(), runtime=runtime_diagnostics())
    tf.keras.utils.set_random_seed(seed)

    started_wall = time.perf_counter()
    record_training_stage(run_folder, "scaler_fit", stage_index=1, stage_total=4, percent=10.0, epochs_total=epochs)
    progress({
        "stage": "scaler_fit",
        "stage_index": 1,
        "stage_total": 4,
        "percent": 10.0,
        "epochs_total": epochs,
        "message": "TRAIN 전용 RobustScaler 적합 중",
    })

    # 1. Fit RobustScaler ONLY on TRAIN frame rows
    train_frame_2col = train_split["frame"][["OBS", "PRD"]].reset_index(drop=True)
    scaler = sklearn_prep.RobustScaler()
    scaler.fit(train_frame_2col)
    if getattr(scaler, "n_features_in_", None) != 2:
        raise ValueError("학습된 RobustScaler의 n_features_in_이 2가 아닙니다.")

    x_train_scaled = scale_windows(scaler, train_split["X_raw"])
    y_train_scaled = scaler.transform(
        pd.DataFrame(
            np.column_stack([train_split["y_raw"][:, 0], np.zeros(len(train_split["y_raw"]))]),
            columns=["OBS", "PRD"],
        )
    )[:, 0].reshape(-1, 1).astype(np.float32)

    x_val_scaled = scale_windows(scaler, val_split["X_raw"])
    y_val_scaled = scaler.transform(
        pd.DataFrame(
            np.column_stack([val_split["y_raw"][:, 0], np.zeros(len(val_split["y_raw"]))]),
            columns=["OBS", "PRD"],
        )
    )[:, 0].reshape(-1, 1).astype(np.float32)

    y_val_true_cm = val_split["y_raw"][:, 0]

    # 3. Build and train operational-identical Keras LSTM candidate model: (batch, 4, 2) -> (batch, 1)
    progress({
        "stage": "lstm_train",
        "stage_index": 2,
        "stage_total": 4,
        "percent": 25.0,
        "epoch": 0,
        "epochs_total": epochs,
        "message": f"Keras LSTM 후보 모델 학습 중 (epochs={epochs}, batch_size={batch_size})",
    })
    record_training_stage(run_folder, "model_build_start", stage_index=2, stage_total=4, percent=25.0, epochs_total=epochs)
    inputs = tf.keras.layers.Input(shape=(4, 2))
    lstm_out = tf.keras.layers.LSTM(64, activation="tanh", recurrent_activation="sigmoid")(inputs)
    outputs = tf.keras.layers.Dense(1)(lstm_out)
    model = tf.keras.models.Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    record_training_stage(run_folder, "model_build_end", input_shape=list(model.input_shape), output_shape=list(model.output_shape))

    early_stop, reduce_lr = build_training_callbacks(tf)
    perm = np.random.default_rng(seed).permutation(len(x_train_scaled))
    x_train_shuf = np.ascontiguousarray(x_train_scaled[perm], dtype=np.float32)
    y_train_shuf = np.ascontiguousarray(y_train_scaled[perm], dtype=np.float32)
    x_val_contig = np.ascontiguousarray(x_val_scaled, dtype=np.float32)
    y_val_contig = np.ascontiguousarray(y_val_scaled, dtype=np.float32)
    input_stats = validate_training_arrays({"x_train": x_train_shuf, "y_train": y_train_shuf,
        "x_validation": x_val_contig, "y_validation": y_val_contig})
    record_training_stage(run_folder, "inputs_validated", arrays=input_stats)

    class TrainingStageCallback(tf.keras.callbacks.Callback):
        first_batch_done = False

        def on_train_batch_begin(self, batch, logs=None):
            if not self.first_batch_done:
                record_training_stage(run_folder, "first_batch_start", batch=int(batch))

        def on_train_batch_end(self, batch, logs=None):
            if not self.first_batch_done:
                self.first_batch_done = True
                record_training_stage(run_folder, "first_batch_end", batch=int(batch),
                    metrics={key: float(value) for key, value in (logs or {}).items()})

        def on_epoch_end(self, epoch, logs=None):
            ep_num = int(epoch) + 1
            metrics_map = {key: round(float(value), 6) for key, value in (logs or {}).items()}
            pct = round(25.0 + 50.0 * (ep_num / max(1, epochs)), 1)
            record_training_stage(
                run_folder,
                "epoch_end",
                epoch=ep_num,
                epochs_total=epochs,
                stage_index=2,
                stage_total=4,
                percent=pct,
                metrics=metrics_map,
            )
            progress({
                "stage": "epoch_end",
                "stage_index": 2,
                "stage_total": 4,
                "percent": pct,
                "epoch": ep_num,
                "epochs_total": epochs,
                "metrics": metrics_map,
                "loss": metrics_map.get("loss"),
                "val_loss": metrics_map.get("val_loss"),
                "mae": metrics_map.get("mae"),
                "val_mae": metrics_map.get("val_mae"),
                "message": f"Keras LSTM 후보 모델 학습 중 (Epoch {ep_num}/{epochs})",
            })

    record_training_stage(run_folder, "fit_start", epochs=epochs, batch_size=batch_size, seed=seed, stage_index=2, stage_total=4, percent=25.0)
    tf.keras.utils.set_random_seed(seed)
    history = model.fit(
        x_train_shuf,
        y_train_shuf,
        validation_data=(x_val_contig, y_val_contig),
        epochs=epochs,
        batch_size=batch_size,
        shuffle=True,
        callbacks=[early_stop, reduce_lr, TrainingStageCallback()],
        verbose=0,
    )
    restoration_info = restore_best_training_weights(model, early_stop)
    restoration_info["best_validation_loss"] = float(early_stop.best)
    record_training_stage(run_folder, "fit_end", epochs_trained=len(history.history["loss"]), epochs_total=epochs, stage_index=2, stage_total=4, percent=75.0, **restoration_info)
    history_dict = {
        "loss": [round(float(x), 6) for x in history.history["loss"]],
        "val_loss": [round(float(x), 6) for x in history.history["val_loss"]],
        "mae": [round(float(x), 6) for x in history.history["mae"]],
        "val_mae": [round(float(x), 6) for x in history.history["val_mae"]],
    }
    epochs_trained = len(history_dict["loss"])

    # 4. Compute validation error & threshold (Thres.forecast.DEV)
    val_preds_cm, val_ms = predict_keras_model(model, scaler, val_split["X_raw"])
    val_errors_cm = np.abs(y_val_true_cm - val_preds_cm)
    raw_threshold_3sigma_cm = float(val_errors_cm.mean() + 3.0 * val_errors_cm.std())
    excluded_yms = []
    if eval_snapshot_id and eval_snapshot_id != snapshot_id:
        external_manifest, _ = authority.load_snapshot(eval_snapshot_id)
        excluded_yms = _period_yms(external_manifest["date_start"], external_manifest["date_end"])
    record_training_stage(run_folder, "threshold_calibration_start", stage_index=3, stage_total=4, percent=80.0, epoch=epochs_trained, epochs_total=epochs)
    progress({
        "stage": "threshold_calibration",
        "stage_index": 3,
        "stage_total": 4,
        "percent": 80.0,
        "epoch": epochs_trained,
        "epochs_total": epochs,
        "message": "VALIDATION 오차 임계값(F1/3σ) 탐색 중",
    })
    calibration = collect_calibration_anomalies(authority, snapshot_manifest, splits, excluded_yms)
    if len(calibration["X_raw"]):
        b_prediction, _ = predict_keras_model(model, scaler, calibration["X_raw"])
        b_errors = np.abs(calibration["y_raw"][:, 0] - b_prediction)
    else:
        b_errors = np.empty((0,), dtype=np.float64)
    reference_model, reference_scaler, reference_raw, _ = load_champion_2025_assets(manifest, station, sensor)
    reference_val_pred, _ = predict_keras_model(reference_model, reference_scaler, val_split["X_raw"])
    if len(calibration["X_raw"]):
        reference_b_pred, _ = predict_keras_model(reference_model, reference_scaler, calibration["X_raw"])
        reference_b_errors = np.abs(calibration["y_raw"][:, 0] - reference_b_pred)
    else:
        reference_b_errors = np.empty((0,), dtype=np.float64)
    threshold_info = optimize_f1_threshold_sigma(
        val_errors_cm, b_errors, anomaly_timestamps=calibration["calibration_timestamps"],
        specificity_floor=0.9998, reference_normal_errors=np.abs(y_val_true_cm - reference_val_pred),
        reference_anomaly_errors=reference_b_errors,
        reference_threshold_cm=compute_effective_threshold(reference_raw)["effective_threshold_cm"])
    # Keep the statistical estimate at full precision; TEST is never used here.
    threshold_info["raw_threshold_3sigma_cm"] = raw_threshold_3sigma_cm
    threshold_info = finalize_operational_calibration(
        threshold_info, val_errors_cm, b_errors,
        champion_raw_threshold_3sigma_cm=reference_raw,
        champion_effective_threshold_cm=compute_effective_threshold(reference_raw)["effective_threshold_cm"],
        anomaly_timestamps=calibration["calibration_timestamps"])
    del reference_model
    threshold_info.update({key: value for key, value in calibration.items() if key not in {"X_raw", "y_raw"}})
    record_training_stage(run_folder, "threshold_calibration_end", threshold_mode=threshold_info["threshold_optimization_mode"], b_windows=int(len(b_errors)), stage_index=3, stage_total=4, percent=83.0)
    val_metrics = metrics_summary(y_val_true_cm, val_preds_cm, val_ms, threshold_info)

    # 5. Save immutable bundle artifacts
    cand_model_path = bundle_dir / "residual_lstm_forecast.h5"
    cand_scaler_path = bundle_dir / "scaler.forecast.gz"
    cand_thres_path = bundle_dir / "Thres.forecast.DEV"
    threshold_metadata_path = bundle_dir / "threshold_metadata.json"

    record_training_stage(run_folder, "save_start", stage_index=3, stage_total=4, percent=84.0)
    model.save(str(cand_model_path))
    joblib.dump(scaler, cand_scaler_path)
    write_candidate_threshold(bundle_dir, threshold_info)
    record_training_stage(run_folder, "save_end", threshold_metadata_sha256=sha256(threshold_metadata_path), stage_index=3, stage_total=4, percent=85.0)

    # 6. Evaluate Champion 2025 and Candidate on TEST split and run immediate deterministic replay verification
    progress({
        "stage": "evaluate_test",
        "stage_index": 3,
        "stage_total": 4,
        "percent": 86.0,
        "epoch": epochs_trained,
        "epochs_total": epochs,
        "message": "동일 TEST 구간 Champion 2025와 신규 후보 비교 평가 중",
    })
    record_training_stage(run_folder, "evaluate_start", stage_index=3, stage_total=4, percent=86.0, epoch=epochs_trained, epochs_total=epochs)
    comparison = evaluate_bundle_on_test(run_folder, manifest, snapshot_manifest, splits, replay=False)
    progress({
        "stage": "replay_verify",
        "stage_index": 4,
        "stage_total": 4,
        "percent": 92.0,
        "epoch": epochs_trained,
        "epochs_total": epochs,
        "message": "결정론적 재현(replay=True) 비트 일치 검증 중",
    })
    record_training_stage(run_folder, "replay_start", stage_index=4, stage_total=4, percent=92.0, epoch=epochs_trained, epochs_total=epochs)
    replay_verification = evaluate_bundle_on_test(run_folder, manifest, snapshot_manifest, splits, replay=True)
    record_training_stage(run_folder, "evaluate_end", replay_passed=bool(replay_verification["passed"]), stage_index=4, stage_total=4, percent=95.0)

    comparison["training_snapshot_id"] = snapshot_id
    comparison["evaluated_snapshot_id"] = snapshot_id
    comparison["evaluated_scope"] = "TEST"
    comparison["evaluated_period"] = f"{snapshot_manifest.get('date_start', '')} ~ {snapshot_manifest.get('date_end', '')}"
    comparison["validation_summary"] = {
        "candidate": val_metrics,
    }
    comparison["replay_verification"] = replay_verification
    write_json(run_folder / "comparison.json", comparison)
    write_json(run_folder / "comparison_train_test.json", comparison)
    if (run_folder / "series_comparison.json").is_file():
        write_json(
            run_folder / "series_train_test.json",
            json.loads((run_folder / "series_comparison.json").read_text(encoding="utf-8")),
        )

    after_integrity = validate(manifest)
    elapsed_total_sec = round(time.perf_counter() - started_wall, 4)

    bundle_files = {}
    for role, p in (
        ("model", cand_model_path),
        ("scaler", cand_scaler_path),
        ("threshold", cand_thres_path),
        ("threshold_metadata", threshold_metadata_path),
    ):
        bundle_files[role] = {
            "path": str(p),
            "relative_path": p.relative_to(run_folder).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
        }

    threshold_passed = all(math.isfinite(float(threshold_info[key])) and
                           0 <= float(threshold_info[key]) <= MAX_THRESHOLD_CM
                           for key in ("raw_threshold_3sigma_cm", "operational_deploy_threshold_3sigma_cm",
                                       "effective_threshold_cm"))
    artifact_record = {
        "schema_version": "ocean-ai-artifact-1",
        "run_id": actual_run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "domain": "fixed_station",
        "item_id": "tide",
        "target_variable": "TIDE_LEVEL",
        "station": station,
        "sensor": sensor,
        "sea": comparison["sea"],
        "snapshot_id": snapshot_id,
        "dataset_id": snapshot_manifest["dataset_id"],
        "train_date_start": snapshot_manifest["date_start"],
        "train_date_end": snapshot_manifest["date_end"],
        "train_selected_yms": sorted({str(ts)[:7].replace("-", "") for split in splits.values() for ts in split["frame"]["OBS_TIME"].tolist()}),
        "status": "FINISHED" if (threshold_passed and replay_verification["passed"]) else "FAILED",
        "threshold_sanity_passed": bool(threshold_passed),
        "max_allowed_threshold_cm": MAX_THRESHOLD_CM,
        "hyperparameters": {
            "input_window_minutes": 4,
            "horizon_minutes": 1,
            "n_features_in": 2,
            "features": ["OBS", "PRD"],
            "lstm_units": 64,
            "activation": "tanh",
            "recurrent_activation": "sigmoid",
            "optimizer": "adam",
            "loss": "mse",
            "epochs_requested": epochs,
            "epochs_trained": epochs_trained,
            "batch_size": batch_size,
            "early_stopping_patience": 6,
            "shuffle": True,
            "reduce_lr": {"factor": 0.5, "patience": 2, "min_delta": 1e-6, "min_lr": 1e-5},
            **restoration_info,
            "seed": seed,
        },
        "training_history": history_dict,
        "training_selection": restoration_info,
        "scaler_stats": {
            "n_features_in": int(scaler.n_features_in_),
            "center": [round(float(x), 6) for x in scaler.center_],
            "scale": [round(float(x), 6) for x in scaler.scale_],
            "fitted_on_split": "TRAIN_ONLY",
            "train_rows_count": int(len(train_frame_2col)),
        },
        "threshold": threshold_info,
        "bundle": bundle_files,
        "comparison_sha256": sha256(run_folder / "comparison.json"),
        "replay_verified": bool(replay_verification["passed"]),
        "elapsed_seconds": elapsed_total_sec,
        "inputs_before": before_integrity,
        "inputs_after": after_integrity,
        "operational_database_used": False,
        "legacy_ai_modified": False,
    }
    write_json(run_folder / "artifact.json", artifact_record)
    record_training_stage(run_folder, "finished", status=artifact_record["status"])

    if eval_snapshot_id and eval_snapshot_id.strip():
        target_eval_id = eval_snapshot_id.strip()
        if target_eval_id != snapshot_id or (eval_scope and eval_scope.upper() == "ALL"):
            progress({"stage": "cross_evaluate", "message": f"외부 평가 스냅샷({target_eval_id}) Champion 2025와 신규 후보 교차 평가 중"})
            comparison = evaluate_bundle_on_snapshot(
                run_folder=run_folder,
                manifest=manifest,
                eval_snapshot_id=target_eval_id,
                eval_scope=eval_scope,
            )
            artifact_record = json.loads((run_folder / "artifact.json").read_text(encoding="utf-8"))

    return {
        "run_id": actual_run_id,
        "run_folder": str(run_folder),
        "artifact": artifact_record,
        "comparison": comparison,
    }


def main() -> int:
    import gc
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["train", "replay", "evaluate"], default="train")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--eval-snapshot-id", default="")
    parser.add_argument("--eval-scope", choices=["AUTO", "ALL", "TEST"], default="AUTO")
    parser.add_argument("--run-id")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()

    if os.name == "nt":
        ctypes.windll.kernel32.SetErrorMode(0x0002)
    faulthandler.enable()
    gc.disable()

    if args.mode == "train":
        out = train_and_evaluate(
            snapshot_id=args.snapshot_id,
            manifest_path=args.manifest.resolve(),
            epochs=args.epochs,
            batch_size=args.batch_size,
            seed=args.seed,
            run_id=args.run_id,
            eval_snapshot_id=args.eval_snapshot_id or None,
            eval_scope=args.eval_scope,
        )
        print(json.dumps({
            "run_id": out["run_id"],
            "status": out["artifact"]["status"],
            "candidate_test_mae": out["comparison"]["models"]["candidate"]["mae"],
            "champion_2025_test_mae": out["comparison"]["models"]["champion_2025"]["mae"],
            "replay_verified": out["artifact"]["replay_verified"],
        }, ensure_ascii=False))
        return 0 if out["artifact"]["status"] == "FINISHED" else 1

    if args.mode == "evaluate":
        if not args.run_id:
            raise ValueError("--mode evaluate 실행 시 --run-id가 필요합니다.")
        target_eval_snap = (args.eval_snapshot_id or args.snapshot_id).strip()
        manifest = json.loads(args.manifest.resolve().read_text(encoding="utf-8"))
        validate(manifest)
        run_folder = CANDIDATE_RUNS_ROOT / args.run_id
        comp_res = evaluate_bundle_on_snapshot(
            run_folder=run_folder,
            manifest=manifest,
            eval_snapshot_id=target_eval_snap,
            eval_scope=args.eval_scope,
        )
        print(json.dumps({
            "run_id": args.run_id,
            "evaluated_snapshot_id": comp_res.get("evaluated_snapshot_id"),
            "evaluated_scope": comp_res.get("evaluated_scope"),
            "candidate_mae": comp_res["models"]["candidate"]["mae"],
            "candidate_f1_score_100": comp_res["models"]["candidate"]["classification"]["f1_score_100"],
        }, ensure_ascii=False))
        return 0

    if not args.run_id:
        raise ValueError("--mode replay 실행 시 --run-id가 필요합니다.")
    manifest = json.loads(args.manifest.resolve().read_text(encoding="utf-8"))
    validate(manifest)
    authority = ParquetSnapshotAuthority()
    snapshot_manifest, splits = authority.extract_split_windows(args.snapshot_id)
    run_folder = CANDIDATE_RUNS_ROOT / args.run_id
    replay_res = evaluate_bundle_on_test(run_folder, manifest, snapshot_manifest, splits, replay=True)
    print(json.dumps(replay_res, ensure_ascii=False))
    return 0 if replay_res["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
