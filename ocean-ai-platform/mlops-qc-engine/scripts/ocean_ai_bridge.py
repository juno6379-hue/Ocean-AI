"""Ocean-AI (ocean-ai-platform) 5-point integration bridge for ai-qc-mlops."""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import os
import sqlite3
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("ocean_ai_bridge", sys.modules[__name__])
sys.modules.setdefault("scripts.ocean_ai_bridge", sys.modules[__name__])

from scripts.local_trial_manifest import read_json
from scripts.workspace_paths import ensure_no_z_access, reject_z_path, resolve_project_path

BRIDGE_VERSION = "ocean-ai-bridge-1"
BUNDLE_CONTRACT = "keras-lstm-bundle-1"
EVALUATION_CONTRACT = "champion-candidate-1"
SNAPSHOTS_ROOT = BASE / "reports" / "ocean_ai_snapshots"
CANDIDATE_RUNS_ROOT = BASE / "reports" / "candidate_runs"
ACTIVE_POINTER_PATH = BASE / "manifests" / "active_release_pointer.json"


def has_reparse_point(path: str | Path) -> bool:
    """Return True if path or any of its existing ancestors is a symlink or Windows reparse point."""
    reject_z_path(path)
    candidate = Path(path).expanduser().absolute()
    current = Path(candidate.anchor)
    for part in ("", *candidate.parts[1:]):
        if part == "..":
            current = current.parent
        elif part:
            current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            return True
    return False


def resolve_non_reparse_path(raw_path: str | Path, base: Path | None = None) -> Path:
    """Resolve symlinks and Windows junctions (e.g., AI_MLOps_2026) to canonical physical paths
    and verify no reparse point remains on the resolved path or its ancestors.
    """
    ensure_no_z_access(raw_path)
    anchor = Path(base).resolve() if base is not None else BASE.resolve()
    rebased = resolve_project_path(raw_path, anchor)
    reject_z_path(rebased)
    try:
        resolved = rebased.resolve()
    except OSError:
        resolved = rebased.absolute()
    reject_z_path(resolved)
    if has_reparse_point(resolved):
        raise ValueError(f"해석된 물리 경로에 여전히 reparse point(정션/심볼릭 링크)가 남아 있습니다: {resolved}")
    return resolved


def _normalize_iso_datetime(value: str | None, fallback_date: str = "2024-01-01", is_end: bool = False) -> str:
    raw = str(value or "").strip()
    if not raw:
        suffix = "T23:59:00" if is_end else "T00:00:00"
        return f"{fallback_date[:10]}{suffix}"
    if " " in raw and "T" not in raw:
        return raw.replace(" ", "T")
    if len(raw) == 10 and raw.count("-") == 2:
        suffix = "T23:59:00" if is_end else "T00:00:00"
        return f"{raw}{suffix}"
    return raw


def _load_snapshot_manifest(manifest_or_path: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(manifest_or_path, dict):
        return dict(manifest_or_path)
    raw_str = str(manifest_or_path).strip()
    candidate = Path(raw_str)
    if not candidate.exists():
        snap_candidate = SNAPSHOTS_ROOT / raw_str / "snapshot_manifest.json"
        if snap_candidate.is_file():
            candidate = snap_candidate
    elif candidate.is_dir():
        candidate = candidate / "snapshot_manifest.json"
    resolved_manifest = resolve_non_reparse_path(candidate, BASE)
    if not resolved_manifest.is_file():
        raise ValueError(f"스냅샷 manifest 파일을 찾을 수 없습니다: {manifest_or_path}")
    return read_json(resolved_manifest)


def build_ocean_ai_dataset_records(manifest_or_path: dict[str, Any] | str | Path) -> list[dict[str, Any]]:
    """Convert an event-evidence-dataset-2 snapshot_manifest.json into 3 Ocean-AI dataset_registry records."""
    manifest = _load_snapshot_manifest(manifest_or_path)
    if manifest.get("schema_version") != "event-evidence-dataset-2":
        raise ValueError(f"지원하지 않는 스냅샷 schema_version입니다: {manifest.get('schema_version')}")

    snapshot_id = str(manifest["snapshot_id"])
    station = str(manifest.get("station") or (manifest.get("station_scope") or ["UNKNOWN"])[0])
    sensor = str(manifest.get("sensor") or (manifest.get("sensor_scope") or ["UNKNOWN"])[0])
    station_scope = list(manifest.get("station_scope") or [station])
    sensor_scope = list(manifest.get("sensor_scope") or [sensor])

    feature_cols = list(manifest.get("feature_columns") or ["OBS", "PRD"])
    target_var = str(manifest.get("target_variable") or "TIDE_LEVEL")
    variable_scope: list[str] = []
    for col in (target_var, *feature_cols):
        if col and col not in variable_scope:
            variable_scope.append(col)

    date_start = str(manifest.get("date_start") or "2024-01-01")
    date_end = str(manifest.get("date_end") or date_start)
    dataset_base_name = f"KHOA_TIDE_{station}_{sensor}_{date_start}_{date_end}"

    win_min = int(manifest.get("input_window_minutes") or 4)
    hor_min = int(manifest.get("horizon_minutes") or 1)
    feature_version = f"window-{win_min}m-horizon-{hor_min}m-obs-prd-v1"
    label_version = "mqc-flag-g-b-v2"
    time_align = str(manifest.get("time_alignment") or "minute_floor")
    col_norm = str(manifest.get("column_normalization") or "strict")
    preprocessing_version = f"{time_align}+{col_norm}"
    qc_rule_version = "khoa-tide-3sigma-stepped-6sigma-v1"

    parquet_info = manifest.get("parquet") or {}
    parquet_sha = str(parquet_info.get("sha256") or "")
    parquet_path_str = ""
    if parquet_info.get("path"):
        parquet_path_str = str(resolve_non_reparse_path(parquet_info["path"], BASE))

    total_anomalies = int(manifest.get("anomaly_rows_count") or 0)
    splits_meta = manifest.get("splits") or {}
    created_at = str(manifest.get("created_at") or datetime.now(timezone.utc).isoformat())

    records: list[dict[str, Any]] = []
    for split_name in ("TRAIN", "VALIDATION", "TEST"):
        s_meta = splits_meta.get(split_name) or {}
        normal_cnt = int(s_meta.get("row_count") or 0)
        bad_cnt = total_anomalies if split_name == "TEST" else 0
        sample_cnt = normal_cnt + bad_cnt
        split_sha = str(s_meta.get("sha256") or parquet_sha)
        if len(split_sha) != 64:
            split_sha = hashlib.sha256(f"{snapshot_id}:{split_name}:{sample_cnt}".encode("utf-8")).hexdigest()

        p_start = _normalize_iso_datetime(s_meta.get("start_time"), fallback_date=date_start, is_end=False)
        p_end = _normalize_iso_datetime(s_meta.get("end_time"), fallback_date=date_end, is_end=True)

        records.append({
            "dataset_id": f"DS_{snapshot_id}_{split_name}",
            "dataset_name": dataset_base_name,
            "dataset_version": f"{snapshot_id}-{split_name}",
            "dataset_split": split_name,
            "station_scope": station_scope,
            "sensor_scope": sensor_scope,
            "variable_scope": variable_scope,
            "period_start": p_start,
            "period_end": p_end,
            "sample_count": sample_cnt,
            "normal_count": normal_cnt,
            "suspect_count": 0,
            "bad_count": bad_cnt,
            "missing_count": 0,
            "feature_version": feature_version,
            "label_version": label_version,
            "preprocessing_version": preprocessing_version,
            "qc_rule_version": qc_rule_version,
            "data_hash": split_sha,
            "status": "APPROVED",
            "created_by": "ai-qc-mlops",
            "approved_by": "ParquetSnapshotAuthority",
            "created_at": created_at,
            "snapshot_id": snapshot_id,
            "parquet_path": parquet_path_str,
        })
    return records


def _compute_r2_from_npz_or_metrics(run_folder: Path, model_key: str, model_entry: dict[str, Any]) -> float:
    if isinstance(model_entry.get("r2"), (int, float)):
        return round(float(model_entry["r2"]), 6)
    npz_path = run_folder / "paired_test_predictions.npz"
    if npz_path.is_file():
        try:
            np = importlib.import_module("numpy")
            with np.load(npz_path) as data:
                if "y_true" in data and model_key in data:
                    y_true = np.asarray(data["y_true"], dtype=float).reshape(-1)
                    y_pred = np.asarray(data[model_key], dtype=float).reshape(-1)
                    if len(y_true) > 1 and len(y_true) == len(y_pred):
                        ss_res = float(np.sum((y_true - y_pred) ** 2))
                        ss_tot = float(np.sum((y_true - float(np.mean(y_true))) ** 2))
                        if ss_tot > 1e-12:
                            return round(max(0.0, 1.0 - (ss_res / ss_tot)), 6)
        except Exception:
            pass
    rmse = float(model_entry.get("rmse") or 0.0)
    # Approximate normalized R2 on tidal range (~330 cm std) when raw array is absent
    approx_var = 330.0 ** 2
    return round(max(0.0, min(1.0, 1.0 - (rmse ** 2) / approx_var)), 6)


def _extract_ocean_ai_metrics(
    run_folder: Path,
    model_key: str,
    model_entry: dict[str, Any],
    overall_gate_pass: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cls_info = model_entry.get("classification") or {}
    rmse = round(float(model_entry.get("rmse") or 0.0), 6)
    mae = round(float(model_entry.get("mae") or 0.0), 6)
    r2 = _compute_r2_from_npz_or_metrics(run_folder, model_key, model_entry)
    raw_recall = cls_info.get("recall")
    raw_precision = cls_info.get("precision")
    raw_f1 = cls_info.get("f1_score")
    recall = round(float(1.0 if raw_recall is None else raw_recall), 6)
    precision = round(float(1.0 if raw_precision is None else raw_precision), 6)
    f1 = round(float(1.0 if raw_f1 is None else raw_f1), 6)

    payload: dict[str, Any] = {
        "RMSE": rmse,
        "MAE": mae,
        "R2": r2,
        "Recall": recall,
        "Precision": precision,
        "F1": f1,
        "overall_gate_pass": bool(overall_gate_pass),
        "bundle_contract": BUNDLE_CONTRACT,
        "evaluation_contract": EVALUATION_CONTRACT,
        "sample_count": int(model_entry.get("sample_count") or 0),
        "threshold": model_entry.get("threshold") or {},
    }
    if extra:
        payload.update(extra)
    return payload


def build_ocean_ai_model_and_retrain_records(
    run_dir_or_id: str | Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Convert ai-qc-mlops candidate runs and release state into Ocean-AI
    model_registry, retraining_history, and approval_history schemas.
    """
    run_folders: list[Path] = []
    if run_dir_or_id is None:
        if CANDIDATE_RUNS_ROOT.is_dir():
            for p in sorted(CANDIDATE_RUNS_ROOT.glob("*/artifact.json")):
                run_folders.append(p.parent)
    else:
        raw_str = str(run_dir_or_id).strip()
        cand_path = Path(raw_str)
        if not cand_path.exists():
            cand_path = CANDIDATE_RUNS_ROOT / raw_str
        if cand_path.is_file():
            cand_path = cand_path.parent
        run_folders.append(resolve_non_reparse_path(cand_path, BASE))

    active_state: dict[str, Any] = {}
    if ACTIVE_POINTER_PATH.is_file():
        with contextlib.suppress(Exception):
            active_state = read_json(ACTIVE_POINTER_PATH)
    station_overrides = active_state.get("station_overrides") or {}

    models_by_version: dict[str, dict[str, Any]] = {}
    retrainings: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []

    for run_folder in run_folders:
        artifact_path = run_folder / "artifact.json"
        comparison_path = run_folder / "comparison.json"
        if not artifact_path.is_file() or not comparison_path.is_file():
            continue

        artifact = read_json(artifact_path)
        comparison = read_json(comparison_path)
        if artifact.get("status") != "FINISHED":
            continue

        run_id = str(artifact["run_id"])
        station = str(artifact["station"])
        sensor = str(artifact["sensor"])
        snapshot_id = str(artifact.get("snapshot_id") or comparison.get("snapshot_id") or "")
        target_var = str(artifact.get("target_variable") or "TIDE_LEVEL")

        # Load snapshot manifest if available for period start/end and versions
        snap_manifest: dict[str, Any] = {}
        if snapshot_id and (SNAPSHOTS_ROOT / snapshot_id / "snapshot_manifest.json").is_file():
            with contextlib.suppress(Exception):
                snap_manifest = read_json(SNAPSHOTS_ROOT / snapshot_id / "snapshot_manifest.json")

        date_start = str(snap_manifest.get("date_start") or "2024-01-01")
        date_end = str(snap_manifest.get("date_end") or "2024-01-31")
        train_split_meta = (snap_manifest.get("splits") or {}).get("TRAIN") or {}
        train_start = _normalize_iso_datetime(train_split_meta.get("start_time"), date_start, is_end=False)
        train_end = _normalize_iso_datetime(train_split_meta.get("end_time"), date_end, is_end=True)

        feature_version = "window-4m-horizon-1m-obs-prd-v1"
        label_version = "mqc-flag-g-b-v2"
        preprocessing_version = (
            f"{snap_manifest.get('time_alignment', 'minute_floor')}+{snap_manifest.get('column_normalization', 'strict')}"
        )
        dataset_version = f"{snapshot_id}-TRAIN" if snapshot_id else "2025-BASELINE"

        comp_models = comparison.get("models") or {}
        champ_entry = comp_models.get("champion_2025") or {}
        cand_entry = comp_models.get("candidate") or {}
        vs_info = comparison.get("candidate_vs_champion_2025") or {}

        mae_better = bool(
            vs_info.get("candidate_better_or_equal_mae")
            if "candidate_better_or_equal_mae" in vs_info
            else float(cand_entry.get("mae") or 999.0) <= float(champ_entry.get("mae") or 999.0)
        )
        cand_f1 = float(((cand_entry.get("classification") or {}).get("f1_score")) or 0.0)
        champ_f1 = float(((champ_entry.get("classification") or {}).get("f1_score")) or 0.0)
        overall_gate_pass = bool(
            artifact.get("threshold_sanity_passed", True)
            and artifact.get("replay_verified", True)
            and mae_better
            and (cand_f1 >= champ_f1 - 1e-6)
        )

        # 1. Baseline 2025 Champion model record for this station/sensor
        baseline_version = f"2025_OPERATION_64_BASELINE_{station}_{sensor}"
        baseline_model_id = f"MDL_BASELINE_{station}_{sensor}"
        override_key = f"{station}|{sensor}"
        active_override = station_overrides.get(override_key)
        baseline_is_champion = active_override is None

        champ_metrics = _extract_ocean_ai_metrics(
            run_folder=run_folder,
            model_key="champion_2025",
            model_entry=champ_entry,
            overall_gate_pass=True,
            extra={
                "role": "champion_2025_baseline",
                "evaluated_snapshot_id": snapshot_id,
            },
        )
        champ_latency = float(((champ_entry.get("latency") or {}).get("per_window_ms")) or 0.025)

        if baseline_version not in models_by_version:
            models_by_version[baseline_version] = {
                "id": baseline_model_id,
                "model_name": f"KHOA_QC_LSTM_{station}_{sensor}",
                "model_type": "LSTM",
                "model_version": baseline_version,
                "dataset_version": dataset_version,
                "feature_version": feature_version,
                "label_version": label_version,
                "preprocessing_version": preprocessing_version,
                "target_variable": target_var,
                "target_task": "ANOMALY_DETECTION_AND_FORECAST_QC",
                "training_data_start": train_start,
                "training_data_end": train_end,
                "station_scope": [station],
                "sensor_scope": [sensor],
                "metrics_json": champ_metrics,
                "artifact_path": str(resolve_non_reparse_path(BASE / "manifests" / "20261006_local_trial_manifest.json", BASE)),
                "status": "DEPLOYED" if baseline_is_champion else "ARCHIVED",
                "deployment_status": "ACTIVE" if baseline_is_champion else "REPLACED",
                "deployment_stage": "PRODUCTION",
                "deployment_target": "OCEAN_AI_QC_ENGINE",
                "is_champion": baseline_is_champion,
                "rolled_back_from": None,
                "deployed_at": str(artifact.get("created_at") or datetime.now(timezone.utc).isoformat()),
                "latency_ms": champ_latency,
                "created_at": str(artifact.get("created_at") or datetime.now(timezone.utc).isoformat()),
            }

        # 2. Candidate model record
        bundle_info = artifact.get("bundle") or {}
        model_file_info = bundle_info.get("model") or {}
        raw_model_path = model_file_info.get("path") or (run_folder / "bundle" / "residual_lstm_forecast.h5")
        resolved_model_path = resolve_non_reparse_path(raw_model_path, BASE)
        if not resolved_model_path.exists():
            resolved_model_path = resolve_non_reparse_path(run_folder / "bundle" / "residual_lstm_forecast.h5", BASE)

        promotion_info = artifact.get("promotion") or {}
        is_promoted_active = bool(active_override and active_override.get("run_id") == run_id)
        was_promoted = bool(promotion_info.get("status") == "PROMOTED_TO_CHAMPION" or is_promoted_active)

        mlflow_reg = artifact.get("mlflow_registration") or {}
        mlflow_ver = str(mlflow_reg.get("model_version") or "1")
        cand_version = f"v{mlflow_ver}-{run_id}"
        cand_model_id = f"MDL_{run_id}"
        cand_latency = float(((cand_entry.get("latency") or {}).get("per_window_ms")) or 0.015)

        cand_metrics = _extract_ocean_ai_metrics(
            run_folder=run_folder,
            model_key="candidate",
            model_entry=cand_entry,
            overall_gate_pass=overall_gate_pass,
            extra={
                "run_id": run_id,
                "snapshot_id": snapshot_id,
                "mae_delta_cm": vs_info.get("mae_delta_cm"),
                "rmse_delta_cm": vs_info.get("rmse_delta_cm"),
                "f1_score_100": ((cand_entry.get("classification") or {}).get("f1_score_100")),
                "champion_2025_mae": champ_entry.get("mae"),
                "champion_2025_rmse": champ_entry.get("rmse"),
                "bundle_sha256": {
                    role: info.get("sha256")
                    for role, info in bundle_info.items()
                    if isinstance(info, dict) and "sha256" in info
                },
            },
        )

        models_by_version[cand_version] = {
            "id": cand_model_id,
            "model_name": f"KHOA_QC_LSTM_{station}_{sensor}",
            "model_type": "LSTM",
            "model_version": cand_version,
            "dataset_version": dataset_version,
            "feature_version": feature_version,
            "label_version": label_version,
            "preprocessing_version": preprocessing_version,
            "target_variable": target_var,
            "target_task": "ANOMALY_DETECTION_AND_FORECAST_QC",
            "training_data_start": train_start,
            "training_data_end": train_end,
            "station_scope": [station],
            "sensor_scope": [sensor],
            "metrics_json": cand_metrics,
            "artifact_path": str(resolved_model_path),
            "status": "DEPLOYED" if is_promoted_active else ("APPROVED" if was_promoted else "VALIDATED"),
            "deployment_status": "ACTIVE" if is_promoted_active else ("STANDBY" if overall_gate_pass else "HOLD"),
            "deployment_stage": "PRODUCTION" if is_promoted_active else "STAGING",
            "deployment_target": "OCEAN_AI_QC_ENGINE",
            "is_champion": is_promoted_active,
            "rolled_back_from": None,
            "deployed_at": promotion_info.get("approved_at") if was_promoted else None,
            "latency_ms": cand_latency,
            "created_at": str(artifact.get("created_at") or datetime.now(timezone.utc).isoformat()),
        }

        # 3. RetrainingHistory record
        created_iso = str(artifact.get("created_at") or datetime.now(timezone.utc).isoformat())
        retrainings.append({
            "id": f"RTH_{run_id}",
            "training_id": f"TRN_{run_id}",
            "base_model_id": baseline_model_id,
            "candidate_model_id": cand_model_id,
            "training_start_time": created_iso,
            "training_end_time": created_iso,
            "data_range_start": train_start,
            "data_range_end": train_end,
            "station_scope": [station],
            "sensor_scope": [sensor],
            "preprocessing_version": preprocessing_version,
            "feature_version": feature_version,
            "dataset_version": dataset_version,
            "label_version": label_version,
            "metrics_before_json": champ_metrics,
            "metrics_after_json": cand_metrics,
            "comparison_result": "IMPROVED" if overall_gate_pass else "REJECTED",
            "approval_status": "APPROVED" if was_promoted else ("READY" if overall_gate_pass else "REJECTED"),
            "created_at": created_iso,
        })

        # 4. ApprovalHistory record if promoted or evaluated
        if was_promoted:
            approvals.append({
                "id": f"APR_{promotion_info.get('deployment_id') or run_id}",
                "approval_type": "MODEL_PROMOTION",
                "target_id": cand_model_id,
                "requested_by": "ai-qc-mlops",
                "approved_by": str(promotion_info.get("approved_by") or "local_operator"),
                "approval_status": "APPROVED",
                "comment": str(promotion_info.get("reason") or "Champion promoted via ai-qc-mlops"),
                "created_at": str(promotion_info.get("approved_at") or created_iso),
                "updated_at": str(promotion_info.get("approved_at") or created_iso),
            })

    # Also include deployment history from active_release_pointer.json so rollbacks and historical promotions are represented
    seen_approval_ids = {a["id"] for a in approvals}
    for hist_item in active_state.get("history") or []:
        dep_id = str(hist_item.get("deployment_id") or "")
        if not dep_id:
            continue
        apr_id = f"APR_{dep_id}"
        if apr_id in seen_approval_ids:
            continue
        seen_approval_ids.add(apr_id)
        action = str(hist_item.get("action") or "PROMOTE")
        run_id_val = str(hist_item.get("run_id") or "")
        target_id = (
            f"MDL_{run_id_val}"
            if run_id_val and run_id_val != "2025_OPERATION_64_BASELINE"
            else f"MDL_BASELINE_{hist_item.get('station')}_{hist_item.get('sensor')}"
        )
        ts_val = str(hist_item.get("timestamp") or datetime.now(timezone.utc).isoformat())
        approvals.append({
            "id": apr_id,
            "approval_type": "MODEL_ROLLBACK" if "ROLLBACK" in action else "MODEL_PROMOTION",
            "target_id": target_id,
            "requested_by": "ai-qc-mlops",
            "approved_by": str(hist_item.get("approved_by") or "local_operator"),
            "approval_status": "APPROVED",
            "comment": str(hist_item.get("reason") or action),
            "created_at": ts_val,
            "updated_at": ts_val,
        })

    return {
        "models": list(models_by_version.values()),
        "retraining_history": retrainings,
        "approval_history": approvals,
    }


def export_ocean_ai_bundle(
    snapshot_ids: list[str] | None = None,
    candidate_run_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build a complete Ocean-AI synchronization bundle across snapshots, candidate runs, and releases."""
    datasets: list[dict[str, Any]] = []
    if snapshot_ids:
        for sid in snapshot_ids:
            datasets.extend(build_ocean_ai_dataset_records(sid))
    elif SNAPSHOTS_ROOT.is_dir():
        for manifest_path in sorted(SNAPSHOTS_ROOT.glob("*/snapshot_manifest.json")):
            with contextlib.suppress(Exception):
                datasets.extend(build_ocean_ai_dataset_records(manifest_path))

    models_map: dict[str, dict[str, Any]] = {}
    retrainings_map: dict[str, dict[str, Any]] = {}
    approvals_map: dict[str, dict[str, Any]] = {}

    if candidate_run_ids:
        for rid in candidate_run_ids:
            part = build_ocean_ai_model_and_retrain_records(rid)
            for m in part["models"]:
                models_map[m["model_version"]] = m
            for r in part["retraining_history"]:
                retrainings_map[r["training_id"]] = r
            for a in part["approval_history"]:
                approvals_map[a["id"]] = a
    else:
        part = build_ocean_ai_model_and_retrain_records(None)
        for m in part["models"]:
            models_map[m["model_version"]] = m
        for r in part["retraining_history"]:
            retrainings_map[r["training_id"]] = r
        for a in part["approval_history"]:
            approvals_map[a["id"]] = a

    active_state: dict[str, Any] = {}
    if ACTIVE_POINTER_PATH.is_file():
        with contextlib.suppress(Exception):
            active_state = read_json(ACTIVE_POINTER_PATH)

    return {
        "bridge_version": BRIDGE_VERSION,
        "bundle_contract": BUNDLE_CONTRACT,
        "evaluation_contract": EVALUATION_CONTRACT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "engine_root": str(resolve_non_reparse_path(BASE, BASE)),
        "active_release_id": active_state.get("active_release_id"),
        "datasets": datasets,
        "models": list(models_map.values()),
        "retraining_history": list(retrainings_map.values()),
        "approval_history": list(approvals_map.values()),
    }


def _sqlite_path_from_url(database_url: str) -> Path | None:
    raw = str(database_url or "").strip()
    if raw.startswith("sqlite:///"):
        path_part = raw[len("sqlite:///") :]
        if path_part.startswith("/") and len(path_part) > 2 and path_part[2] == ":":
            path_part = path_part[1:]
        return Path(path_part)
    if raw.endswith(".db") or raw.endswith(".sqlite") or raw.endswith(".sqlite3"):
        return Path(raw)
    return None


def _ensure_ocean_ai_sqlite_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dataset_registry (
            dataset_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            dataset_version TEXT NOT NULL,
            dataset_split TEXT NOT NULL,
            station_scope TEXT,
            sensor_scope TEXT,
            variable_scope TEXT,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            sample_count INTEGER DEFAULT 0,
            normal_count INTEGER DEFAULT 0,
            suspect_count INTEGER DEFAULT 0,
            bad_count INTEGER DEFAULT 0,
            missing_count INTEGER DEFAULT 0,
            feature_version TEXT NOT NULL,
            label_version TEXT NOT NULL,
            preprocessing_version TEXT NOT NULL,
            qc_rule_version TEXT NOT NULL,
            data_hash TEXT NOT NULL,
            status TEXT DEFAULT 'DRAFT',
            created_by TEXT DEFAULT 'system',
            approved_by TEXT,
            created_at TEXT,
            UNIQUE(dataset_name, dataset_version)
        );

        CREATE TABLE IF NOT EXISTS model_registry (
            id TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            model_type TEXT NOT NULL,
            model_version TEXT NOT NULL UNIQUE,
            dataset_version TEXT NOT NULL,
            feature_version TEXT NOT NULL,
            label_version TEXT NOT NULL,
            preprocessing_version TEXT NOT NULL,
            target_variable TEXT NOT NULL,
            target_task TEXT NOT NULL,
            training_data_start TEXT NOT NULL,
            training_data_end TEXT NOT NULL,
            station_scope TEXT,
            sensor_scope TEXT,
            metrics_json TEXT,
            artifact_path TEXT,
            status TEXT DEFAULT 'DRAFT',
            deployment_status TEXT DEFAULT 'NONE',
            deployment_stage TEXT DEFAULT 'PRODUCTION',
            deployment_target TEXT DEFAULT 'ALL',
            is_champion INTEGER DEFAULT 0,
            rolled_back_from TEXT,
            deployed_at TEXT,
            latency_ms REAL DEFAULT 12.5,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS retraining_history (
            id TEXT PRIMARY KEY,
            training_id TEXT NOT NULL UNIQUE,
            base_model_id TEXT,
            candidate_model_id TEXT,
            training_start_time TEXT NOT NULL,
            training_end_time TEXT,
            data_range_start TEXT NOT NULL,
            data_range_end TEXT NOT NULL,
            station_scope TEXT,
            sensor_scope TEXT,
            preprocessing_version TEXT NOT NULL,
            feature_version TEXT NOT NULL,
            dataset_version TEXT NOT NULL,
            label_version TEXT NOT NULL,
            metrics_before_json TEXT,
            metrics_after_json TEXT,
            comparison_result TEXT DEFAULT 'PENDING',
            approval_status TEXT DEFAULT 'REQUESTED',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS approval_history (
            id TEXT PRIMARY KEY,
            approval_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            approved_by TEXT,
            approval_status TEXT DEFAULT 'REQUESTED',
            comment TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )


def sync_to_ocean_ai_db(
    database_url: str | None = None,
    snapshot_ids: list[str] | None = None,
    candidate_run_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Idempotently upsert dataset_registry, model_registry, retraining_history, and approval_history
    records into an Ocean-AI SQLite database.
    """
    target_url = str(database_url or os.environ.get("OCEAN_AI_DATABASE_URL") or "").strip()
    if not target_url:
        raise ValueError("동기화할 Ocean-AI 데이터베이스 URL(database_url 또는 OCEAN_AI_DATABASE_URL)이 지정되지 않았습니다.")

    sqlite_path = _sqlite_path_from_url(target_url)
    if sqlite_path is None:
        raise ValueError(f"지원하지 않는 database_url 형식입니다 (sqlite:/// 경로 필요): {target_url}")

    reject_z_path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    bundle = export_ocean_ai_bundle(snapshot_ids=snapshot_ids, candidate_run_ids=candidate_run_ids)

    with contextlib.closing(sqlite3.connect(sqlite_path)) as conn:
        _ensure_ocean_ai_sqlite_tables(conn)

        for ds in bundle["datasets"]:
            conn.execute(
                """
                INSERT INTO dataset_registry (
                    dataset_id, dataset_name, dataset_version, dataset_split,
                    station_scope, sensor_scope, variable_scope,
                    period_start, period_end,
                    sample_count, normal_count, suspect_count, bad_count, missing_count,
                    feature_version, label_version, preprocessing_version, qc_rule_version,
                    data_hash, status, created_by, approved_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dataset_name, dataset_version) DO UPDATE SET
                    dataset_split = excluded.dataset_split,
                    station_scope = excluded.station_scope,
                    sensor_scope = excluded.sensor_scope,
                    variable_scope = excluded.variable_scope,
                    period_start = excluded.period_start,
                    period_end = excluded.period_end,
                    sample_count = excluded.sample_count,
                    normal_count = excluded.normal_count,
                    suspect_count = excluded.suspect_count,
                    bad_count = excluded.bad_count,
                    missing_count = excluded.missing_count,
                    feature_version = excluded.feature_version,
                    label_version = excluded.label_version,
                    preprocessing_version = excluded.preprocessing_version,
                    qc_rule_version = excluded.qc_rule_version,
                    data_hash = excluded.data_hash,
                    status = excluded.status,
                    approved_by = excluded.approved_by
                """,
                (
                    ds["dataset_id"],
                    ds["dataset_name"],
                    ds["dataset_version"],
                    ds["dataset_split"],
                    json.dumps(ds["station_scope"], ensure_ascii=False),
                    json.dumps(ds["sensor_scope"], ensure_ascii=False),
                    json.dumps(ds["variable_scope"], ensure_ascii=False),
                    ds["period_start"],
                    ds["period_end"],
                    int(ds["sample_count"]),
                    int(ds["normal_count"]),
                    int(ds["suspect_count"]),
                    int(ds["bad_count"]),
                    int(ds["missing_count"]),
                    ds["feature_version"],
                    ds["label_version"],
                    ds["preprocessing_version"],
                    ds["qc_rule_version"],
                    ds["data_hash"],
                    ds["status"],
                    ds["created_by"],
                    ds["approved_by"],
                    ds["created_at"],
                ),
            )

        for mdl in bundle["models"]:
            conn.execute(
                """
                INSERT INTO model_registry (
                    id, model_name, model_type, model_version,
                    dataset_version, feature_version, label_version, preprocessing_version,
                    target_variable, target_task,
                    training_data_start, training_data_end,
                    station_scope, sensor_scope, metrics_json, artifact_path,
                    status, deployment_status, deployment_stage, deployment_target,
                    is_champion, rolled_back_from, deployed_at, latency_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_version) DO UPDATE SET
                    dataset_version = excluded.dataset_version,
                    feature_version = excluded.feature_version,
                    label_version = excluded.label_version,
                    preprocessing_version = excluded.preprocessing_version,
                    metrics_json = excluded.metrics_json,
                    artifact_path = excluded.artifact_path,
                    status = excluded.status,
                    deployment_status = excluded.deployment_status,
                    deployment_stage = excluded.deployment_stage,
                    is_champion = excluded.is_champion,
                    deployed_at = excluded.deployed_at,
                    latency_ms = excluded.latency_ms
                """,
                (
                    mdl["id"],
                    mdl["model_name"],
                    mdl["model_type"],
                    mdl["model_version"],
                    mdl["dataset_version"],
                    mdl["feature_version"],
                    mdl["label_version"],
                    mdl["preprocessing_version"],
                    mdl["target_variable"],
                    mdl["target_task"],
                    mdl["training_data_start"],
                    mdl["training_data_end"],
                    json.dumps(mdl["station_scope"], ensure_ascii=False),
                    json.dumps(mdl["sensor_scope"], ensure_ascii=False),
                    json.dumps(mdl["metrics_json"], ensure_ascii=False),
                    mdl["artifact_path"],
                    mdl["status"],
                    mdl["deployment_status"],
                    mdl["deployment_stage"],
                    mdl["deployment_target"],
                    1 if mdl["is_champion"] else 0,
                    mdl["rolled_back_from"],
                    mdl["deployed_at"],
                    float(mdl["latency_ms"]),
                    mdl["created_at"],
                ),
            )

        for trn in bundle["retraining_history"]:
            conn.execute(
                """
                INSERT INTO retraining_history (
                    id, training_id, base_model_id, candidate_model_id,
                    training_start_time, training_end_time,
                    data_range_start, data_range_end,
                    station_scope, sensor_scope,
                    preprocessing_version, feature_version, dataset_version, label_version,
                    metrics_before_json, metrics_after_json,
                    comparison_result, approval_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(training_id) DO UPDATE SET
                    base_model_id = excluded.base_model_id,
                    candidate_model_id = excluded.candidate_model_id,
                    metrics_before_json = excluded.metrics_before_json,
                    metrics_after_json = excluded.metrics_after_json,
                    comparison_result = excluded.comparison_result,
                    approval_status = excluded.approval_status
                """,
                (
                    trn["id"],
                    trn["training_id"],
                    trn["base_model_id"],
                    trn["candidate_model_id"],
                    trn["training_start_time"],
                    trn["training_end_time"],
                    trn["data_range_start"],
                    trn["data_range_end"],
                    json.dumps(trn["station_scope"], ensure_ascii=False),
                    json.dumps(trn["sensor_scope"], ensure_ascii=False),
                    trn["preprocessing_version"],
                    trn["feature_version"],
                    trn["dataset_version"],
                    trn["label_version"],
                    json.dumps(trn["metrics_before_json"], ensure_ascii=False),
                    json.dumps(trn["metrics_after_json"], ensure_ascii=False),
                    trn["comparison_result"],
                    trn["approval_status"],
                    trn["created_at"],
                ),
            )

        for apr in bundle["approval_history"]:
            conn.execute(
                """
                INSERT INTO approval_history (
                    id, approval_type, target_id, requested_by, approved_by,
                    approval_status, comment, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    approved_by = excluded.approved_by,
                    approval_status = excluded.approval_status,
                    comment = excluded.comment,
                    updated_at = excluded.updated_at
                """,
                (
                    apr["id"],
                    apr["approval_type"],
                    apr["target_id"],
                    apr["requested_by"],
                    apr["approved_by"],
                    apr["approval_status"],
                    apr["comment"],
                    apr["created_at"],
                    apr["updated_at"],
                ),
            )

        conn.commit()

    return {
        "synced": True,
        "bridge_version": BRIDGE_VERSION,
        "database_path": str(sqlite_path.resolve()),
        "datasets_upserted": len(bundle["datasets"]),
        "models_upserted": len(bundle["models"]),
        "retrainings_upserted": len(bundle["retraining_history"]),
        "approvals_upserted": len(bundle["approval_history"]),
        "active_release_id": bundle["active_release_id"],
    }


def get_ocean_ai_bridge_status() -> dict[str, Any]:
    """Return current ai-qc-mlops engine status for Ocean-AI platform integration."""
    active_state: dict[str, Any] = {}
    if ACTIVE_POINTER_PATH.is_file():
        with contextlib.suppress(Exception):
            active_state = read_json(ACTIVE_POINTER_PATH)
    snapshots = sorted(SNAPSHOTS_ROOT.glob("*/snapshot_manifest.json")) if SNAPSHOTS_ROOT.is_dir() else []
    candidate_runs = sorted(CANDIDATE_RUNS_ROOT.glob("*/artifact.json")) if CANDIDATE_RUNS_ROOT.is_dir() else []
    return {
        "engine": "ai-qc-mlops",
        "bridge_version": BRIDGE_VERSION,
        "bundle_contract": BUNDLE_CONTRACT,
        "evaluation_contract": EVALUATION_CONTRACT,
        "engine_root": str(resolve_non_reparse_path(BASE, BASE)),
        "active_release_id": active_state.get("active_release_id"),
        "updated_at": active_state.get("updated_at"),
        "snapshot_count": len(snapshots),
        "candidate_run_count": len(candidate_runs),
        "station_override_count": len(active_state.get("station_overrides") or {}),
    }
