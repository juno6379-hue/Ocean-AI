"""CPU model tests and limited historical inference replay, without database I/O."""
from __future__ import annotations

import argparse
import ctypes
import faulthandler
import importlib
import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Any

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("offline_model_suite", sys.modules[__name__])
sys.modules.setdefault("scripts.offline_model_suite", sys.modules[__name__])

# Resolve these at runtime: this harness uses a restored interpreter separate
# from the editor and MLflow interpreter. Import errors are deliberately fatal.
joblib: Any = importlib.import_module("joblib")
np: Any = importlib.import_module("numpy")
pd: Any = importlib.import_module("pandas")
from scripts.local_trial_manifest import confined_path, sha256, validate, write_json
from scripts.workspace_paths import resolve_manifest_root

_tensorflow_runtime = None


def tensorflow_runtime():
    global _tensorflow_runtime
    if _tensorflow_runtime is None:
        engine = importlib.import_module("tensorflow")
        engine.config.set_visible_devices([], "GPU")
        engine.config.threading.set_inter_op_parallelism_threads(1)
        engine.config.threading.set_intra_op_parallelism_threads(1)
        _tensorflow_runtime = engine
    return _tensorflow_runtime


def assets(root: Path, pair: dict):
    tf = tensorflow_runtime()
    model = tf.keras.models.load_model(str(confined_path(root, pair["model"])), compile=False)
    scaler = joblib.load(confined_path(root, pair["scaler"]))
    threshold = float(confined_path(root, pair["threshold"]).read_text(encoding="utf-8").strip())
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("Invalid DEV threshold")
    if tuple(model.input_shape[1:]) != (4, 2) or tuple(model.output_shape[1:]) != (1,):
        raise ValueError(f"Unexpected model shape: {model.input_shape}, {model.output_shape}")
    if getattr(scaler, "n_features_in_", None) != 2:
        raise ValueError("Scaler must have exactly two features")
    return model, scaler, threshold


def predict(model, scaler, raw):
    frame = pd.DataFrame(raw.reshape(-1, 2), columns=["OBS", "PRD"])
    scaled = scaler.transform(frame).reshape(-1, 4, 2)
    if not np.isfinite(scaled).all():
        raise ValueError("Non-finite scaled input")
    output = np.asarray(model(scaled.astype(np.float32), training=False))
    physical = scaler.inverse_transform(np.column_stack([output[:, 0], np.zeros(len(output))]))[:, 0]
    if not np.isfinite(physical).all():
        raise ValueError("Non-finite prediction")
    return physical


def model_test(manifest: dict) -> dict:
    tf = tensorflow_runtime()
    root = resolve_manifest_root(manifest, BASE)
    rows = []
    for pair in manifest["models"]:
        row = {"station": pair["station"], "sensor": pair["sensor"], "sea": pair["sea"]}
        try:
            model, scaler, threshold = assets(root, pair)
            # A deterministic load/inference probe, not a real observation or accuracy score.
            center = np.asarray(scaler.center_, dtype=float)
            raw = np.tile(center, (1, 4, 1))
            first, second = predict(model, scaler, raw), predict(model, scaler, raw)
            if not np.allclose(first, second, rtol=0, atol=1e-6):
                raise ValueError("Repeated inference differs")
            row.update({"passed": True, "input_shape": list(model.input_shape),
                        "output_shape": list(model.output_shape), "threshold": threshold,
                        "fixed_input_prediction": float(first[0])})
        except Exception as error:
            row.update({"passed": False, "error": f"{type(error).__name__}: {error}"})
        finally:
            tf.keras.backend.clear_session()
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return {"kind": "ALL_MODEL_CPU_LOAD_AND_FIXED_INPUT", "passed": all(r["passed"] for r in rows),
            "model_count": len(rows), "passed_count": sum(r["passed"] for r in rows),
            "tensorflow_version": tf.__version__, "database_used": False,
            "accuracy_evaluated": False, "models": rows}


def select_normal_windows(frame, limit: int = 128):
    """Use only contiguous input windows whose preceding flags are all normal."""
    frame = frame.sort_values("timestamp").drop_duplicates("timestamp", keep=False)
    values = frame[["real_obs", "tide_pre_val"]].to_numpy(dtype=float)
    times = pd.to_datetime(frame["timestamp"], format="ISO8601", errors="raise").to_numpy()
    flags = frame["final_flag"].astype(str).to_numpy()
    expected = frame["predicted_obs"].to_numpy(dtype=float)
    eligible = np.isfinite(expected)
    # Vectorized checks apply to the four preceding rows, not the target flag.
    for offset in range(1, 5):
        prior_ok = (flags == "1") & np.isfinite(values).all(axis=1)
        eligible &= np.roll(prior_ok, offset)
        eligible &= (times - np.roll(times, offset)) == np.timedelta64(offset, "m")
    eligible[:4] = False
    indices = np.flatnonzero(eligible)[-limit:]
    windows = np.asarray([values[index - 4:index] for index in indices])
    return windows, expected[indices], [str(times[index]) for index in indices]


def replay_test(manifest: dict, output_folder: Path, manifest_path: Path) -> dict:
    root = resolve_manifest_root(manifest, BASE)
    targets = {(p["station"], p["sensor"]): p for p in manifest["models"]}
    selected, source_files, parsing_errors = {}, [], []
    columns = ["timestamp", "station", "sensor", "real_obs", "tide_pre_val", "predicted_obs", "final_flag"]
    # Latest execution filenames first. Timestamps come from CSV rows, never filenames.
    for path in sorted((root / "debug_logs").glob("debug_log_*.csv"), reverse=True):
        if len(selected) == len(targets):
            break
        before_hash = sha256(path)
        try:
            for chunk in pd.read_csv(path, usecols=columns, dtype={"station": str, "sensor": str, "final_flag": str}, chunksize=100000):
                for key, group in chunk.groupby(["station", "sensor"], sort=False):
                    if key not in targets or key in selected:
                        continue
                    x, y, times = select_normal_windows(group)
                    if len(x) >= 16:
                        selected[key] = (x, y, times, path.relative_to(root).as_posix())
        except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
            parsing_errors.append({"file": path.name, "error": str(error)})
        if sha256(path) != before_hash:
            raise ValueError(f"Replay input changed while reading: {path.name}")
        source_files.append({"path": path.relative_to(root).as_posix(), "sha256": before_hash})
    rows = []
    snapshot = output_folder / "replay_inputs"
    snapshot.mkdir(exist_ok=False)
    for key, pair in targets.items():
        row = {"station": key[0], "sensor": key[1], "sea": pair["sea"]}
        if key not in selected:
            row.update({"status": "NO_ELIGIBLE_NORMAL_WINDOWS", "sample_count": 0})
            rows.append(row)
            continue
        x, expected, times, source = selected[key]
        np.savez_compressed(snapshot / f"{key[0]}_{key[1]}.npz", raw_inputs=x,
                            historical_predictions=expected, timestamps=np.asarray(times))
        try:
            series_path = snapshot / f"{key[0]}_{key[1]}.json"
            worker_command = [sys.executable, "-X", "utf8", "-X", "faulthandler",
                              str(Path(__file__).with_name("replay_prediction_worker.py")),
                              "--manifest", str(manifest_path.resolve()),
                              "--input", str(snapshot / f"{key[0]}_{key[1]}.npz"),
                              "--output", str(series_path), "--station", key[0], "--sensor", key[1]]
            with series_path.with_suffix(".stdout.log").open("wb") as out, series_path.with_suffix(".stderr.log").open("wb") as err:
                worker = subprocess.run(worker_command, stdout=out, stderr=err, timeout=60,
                                        check=False, shell=False)
            if worker.returncode != 0:
                raise RuntimeError(f"Prediction worker exited with code {worker.returncode}; see {series_path.with_suffix('.stderr.log').name}")
            series = json.loads(series_path.read_text(encoding="utf-8"))
            actual = np.asarray(series["recomputed"])
            difference = np.abs(actual - expected)
            if actual.shape != expected.shape or not np.isfinite(actual).all():
                raise ValueError("Invalid isolated worker predictions")
            row.update({"status": "PASS" if np.all(difference <= 0.01) else "MISMATCH",
                        "sample_count": len(expected), "source": source,
                        "timestamp_min": min(times), "timestamp_max": max(times),
                        "prediction_abs_difference_max_cm": float(difference.max()),
                        "prediction_abs_difference_mean_cm": float(difference.mean())})
        except Exception as error:
            row.update({"status": "ERROR", "sample_count": len(expected),
                        "error": f"{type(error).__name__}: {error}"})
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    mismatches = sum(r["status"] in {"MISMATCH", "ERROR"} for r in rows)
    evaluated = sum(r["status"] in {"PASS", "MISMATCH"} for r in rows)
    return {"kind": "LIMITED_NORMAL_WINDOW_HISTORICAL_PREDICTION_REPLAY",
            "passed": mismatches == 0 and evaluated > 0 and not parsing_errors,
            "complete_64_coverage": evaluated == len(targets), "evaluated_models": evaluated,
            "model_count": len(targets), "mismatch_or_error_count": mismatches,
            "total_samples": sum(r["sample_count"] for r in rows), "tolerance_cm": 0.01,
            "database_used": False, "live_parallel_operation": False,
            "seven_day_operation_verified": False, "full_flag_state_replay": False,
            "limitation": "Only normal, contiguous 4-minute inputs; drift/interpolation and full QC state are not replayed.",
            "input_files": source_files, "parsing_errors": parsing_errors, "models": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=["models", "replay"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate(manifest)
    root = resolve_manifest_root(manifest, BASE)
    if args.output.exists() or args.output.resolve().is_relative_to(root):
        raise ValueError("Output must be new and outside protected input")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = model_test(manifest) if args.job == "models" else replay_test(manifest, args.output.parent, args.manifest)
    report["inputs_after"] = validate(manifest)
    write_json(args.output, report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    if os.name == "nt":
        ctypes.windll.kernel32.SetErrorMode(0x0002)
    faulthandler.enable()
    raise SystemExit(main())
