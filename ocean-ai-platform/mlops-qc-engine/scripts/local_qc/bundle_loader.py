"""Verified local bundles for replay; no active release or database access."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
import math
from pathlib import Path
from typing import Any

from scripts.tensorflow_runtime import resolve_tensorflow_python
from scripts.workspace_paths import resolve_backup_code_root
from scripts.local_qc.legacy import build_config, normalize_sea

BASE = Path(__file__).resolve().parents[2]
LEGACY_STEPPED_3SIGMA = "LEGACY_STEPPED_3SIGMA"
FROZEN_EFFECTIVE_THRESHOLD_DIRECT = "FROZEN_EFFECTIVE_THRESHOLD_DIRECT"
OPERATIONAL_LEGACY_STEPPED_3SIGMA = "OPERATIONAL_LEGACY_STEPPED_3SIGMA"
_tf_engine: Any = None
_BUNDLE_NAMES = {"model": "residual_lstm_forecast.h5", "scaler": "scaler.forecast.gz",
                 "threshold": "Thres.forecast.DEV", "threshold_metadata": "threshold_metadata.json"}


@dataclass
class QCBundle:
    """One sensor's model and immutable threshold decision inputs."""

    station: str
    sensor: str
    role: str
    sea: str
    model: Any
    scaler: Any
    raw_threshold_3sigma_cm: float
    effective_lstm_threshold_cm: float
    metadata: dict[str, Any]
    operational_deploy_threshold_3sigma_cm: float | None = None


def _json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"JSON에 유한하지 않은 숫자가 있습니다: {value}")

    document = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(document, dict):
        raise ValueError(f"JSON 최상위 값이 객체가 아닙니다: {path}")
    return document


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _confined(root: Path, raw: str) -> Path:
    path = (root / raw).resolve(strict=True)
    if not path.is_relative_to(root.resolve(strict=True)):
        raise ValueError(f"번들 루트를 벗어난 경로입니다: {raw}")
    if not path.is_file():
        raise ValueError(f"번들 자산이 파일이 아닙니다: {path}")
    return path


def _verified_file(root: Path, record: dict[str, Any], *, relative_key: str = "path") -> tuple[Path, dict[str, Any]]:
    raw = record.get(relative_key)
    expected = record.get("sha256")
    if not isinstance(raw, str) or not raw or not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("번들 파일의 경로와 SHA-256 기록이 필요합니다.")
    path = _confined(root, raw)
    actual = _sha256(path)
    if actual.lower() != expected.lower():
        raise ValueError(f"번들 파일 SHA-256이 기록과 다릅니다: {path}")
    size = record.get("size_bytes", record.get("bytes"))
    if size is not None and path.stat().st_size != size:
        raise ValueError(f"번들 파일 크기가 기록과 다릅니다: {path}")
    return path, {"path": str(path), "sha256": actual, "size_bytes": path.stat().st_size}


def _nonnegative_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name}은 유한한 0 이상의 숫자여야 합니다.")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name}은 유한한 0 이상의 숫자여야 합니다.")
    return number


def legacy_stepped_threshold(raw_threshold_3sigma_cm: float) -> tuple[float, int]:
    """Apply the exact operational step rule without rounding its result."""
    raw = _nonnegative_number(raw_threshold_3sigma_cm, "DEV 원시 3σ")
    sigma = 6 if raw <= 5 else 5 if raw <= 7 else 4 if raw <= 9 else 3 if raw <= 12 else 2 if raw <= 14 else 1
    return (raw / 3.0) * sigma, sigma


def _load_models(model_path: Path, scaler_path: Path) -> tuple[Any, Any]:
    global _tf_engine
    if _tf_engine is None:
        engine: Any = importlib.import_module("tensorflow")
        engine.config.set_visible_devices([], "GPU")
        engine.config.threading.set_inter_op_parallelism_threads(1)
        engine.config.threading.set_intra_op_parallelism_threads(1)
        _tf_engine = engine
    model = _tf_engine.keras.models.load_model(str(model_path), compile=False)
    scaler = importlib.import_module("joblib").load(scaler_path)
    if tuple(model.input_shape[1:]) != (4, 2) or tuple(model.output_shape[1:]) != (1,):
        raise ValueError("QC 모델 입출력 구조가 (4, 2) -> (1,)이 아닙니다.")
    if getattr(scaler, "n_features_in_", None) != 2:
        raise ValueError("QC 스케일러의 피처 수가 2가 아닙니다.")
    return model, scaler


def _metadata(base: Path, role: str, station: str, sensor: str, sea: str,
              files: dict[str, dict[str, Any]], method: str) -> dict[str, Any]:
    return {"role": role, "station": station, "sensor": sensor, "sea": sea,
            "artifacts": files, "model_path": files["model"]["path"], "model_sha256": files["model"]["sha256"],
            "scaler_path": files["scaler"]["path"], "scaler_sha256": files["scaler"]["sha256"],
            "threshold_path": files["threshold"]["path"], "threshold_sha256": files["threshold"]["sha256"],
            "threshold_application_method": method, "threshold_method": method,
            "tensorflow_python": str(resolve_tensorflow_python(base)), "operational_database_used": False}


def load_champion_bundle(station: str, sensor: str, *, base: Path = BASE, load_models: bool = True) -> QCBundle:
    """Load only the frozen 2025 operational manifest, ignoring release pointers."""
    base = Path(base).resolve()
    manifest_path = base / "manifests/2025_operation_64_manifest.json"
    manifest = _json(manifest_path)
    matches = [pair for pair in manifest["models"]
               if pair.get("station_code") == station and pair.get("sensor_code") == sensor]
    if len(matches) != 1:
        raise ValueError(f"동결된 2025 매핑에 관측소/센서가 정확히 한 건 있어야 합니다: {station}/{sensor}")
    pair = matches[0]
    root = resolve_backup_code_root(base).resolve(strict=True)
    files: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    for role in ("model", "scaler", "threshold"):
        paths[role], files[role] = _verified_file(root, pair["artifacts"][_BUNDLE_NAMES[role]])
    raw = _nonnegative_number(paths["threshold"].read_text(encoding="utf-8").strip(), "DEV 원시 3σ")
    effective, sigma = legacy_stepped_threshold(raw)
    sea = normalize_sea(pair["sea_info"])
    config = build_config(sea, base=base)
    if (station, sensor) not in config["station_sensor_pairs"]:
        raise ValueError("동결된 2025 모델과 실제 해역별 CSV 매핑이 다릅니다.")
    metadata = _metadata(base, "champion_2025", station, sensor, sea, files, LEGACY_STEPPED_3SIGMA)
    metadata.update({"manifest_path": str(manifest_path), "manifest_sha256": _sha256(manifest_path),
                     "baseline_id": manifest.get("baseline_id"), "source_root": str(root),
                     "raw_threshold_3sigma_cm": raw, "effective_lstm_threshold_cm": effective,
                     "operational_deploy_threshold_3sigma_cm": raw, "dev_file_threshold_cm": raw,
                     "deployment_equivalent": True,
                     "effective_threshold_cm": effective, "effective_sigma": sigma,
                     "configuration": config["metadata"], "calibration_guardrails": None,
                     "calibration_guardrails_passed": None})
    model, scaler = _load_models(paths["model"], paths["scaler"]) if load_models else (None, None)
    json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    return QCBundle(station, sensor, "champion_2025", sea, model, scaler, raw, effective, metadata, raw)


def _candidate_threshold_inputs(threshold, dev, station, sensor, base):
    """Validate the one DEV value actually consumed by an unmodified script."""
    from scripts.calibration_policy import encode_operational_threshold
    statistical = _nonnegative_number(threshold["raw_threshold_3sigma_cm"], "통계 raw 3σ")
    effective = _nonnegative_number(threshold["effective_threshold_cm"], "유효 LSTM 임계값")
    method = threshold.get("threshold_application_method")
    encoded = "operational_deploy_threshold_3sigma_cm" in threshold or method == OPERATIONAL_LEGACY_STEPPED_3SIGMA
    if not encoded:
        if not math.isclose(dev, statistical, rel_tol=0, abs_tol=1e-6):
            raise ValueError("이전 후보의 DEV와 통계 raw 3σ가 다릅니다.")
        return statistical, effective, FROZEN_EFFECTIVE_THRESHOLD_DIRECT, {
            "operational_deploy_threshold_3sigma_cm": dev, "dev_file_threshold_cm": dev,
            "deployment_equivalent": False, "deployment_equivalence_reason": "LEGACY_DIRECT_EFFECTIVE_POLICY"}
    if method != OPERATIONAL_LEGACY_STEPPED_3SIGMA:
        raise ValueError("운영 배포 임계값의 소비 정책이 필요합니다.")
    required = ("operational_deploy_threshold_3sigma_cm", "calibrated_effective_threshold_cm",
                "champion_raw_threshold_3sigma_cm", "champion_effective_threshold_cm")
    if any(threshold.get(key) is None for key in required):
        raise ValueError("운영 호환 임계값의 DEV·보정 목표·챔피언 근거가 필요합니다.")
    operational = _nonnegative_number(threshold["operational_deploy_threshold_3sigma_cm"], "운영 DEV")
    if dev != operational:
        raise ValueError("실제 DEV와 운영 배포 임계값 메타데이터가 다릅니다.")
    champion = load_champion_bundle(station, sensor, base=base, load_models=False)
    if (threshold["champion_raw_threshold_3sigma_cm"] != champion.raw_threshold_3sigma_cm or
            threshold["champion_effective_threshold_cm"] != champion.effective_lstm_threshold_cm):
        raise ValueError("운영 배포 임계값의 챔피언 근거가 동결 매니페스트와 다릅니다.")
    expected = encode_operational_threshold(raw_threshold_3sigma_cm=statistical,
        effective_threshold_cm=threshold["calibrated_effective_threshold_cm"],
        champion_raw_threshold_3sigma_cm=champion.raw_threshold_3sigma_cm,
        champion_effective_threshold_cm=champion.effective_lstm_threshold_cm)
    if operational != expected["operational_deploy_threshold_3sigma_cm"] or effective != expected["effective_threshold_cm"]:
        raise ValueError("운영 DEV 계단식 계산과 유효 LSTM 임계값이 일치하지 않습니다.")
    if "effective_lstm_threshold_cm" in threshold and threshold["effective_lstm_threshold_cm"] != effective:
        raise ValueError("유효 LSTM 임계값의 두 메타데이터 필드가 다릅니다.")
    return statistical, effective, OPERATIONAL_LEGACY_STEPPED_3SIGMA, {
        "operational_deploy_threshold_3sigma_cm": operational, "dev_file_threshold_cm": dev,
        "calibrated_effective_threshold_cm": expected["calibrated_effective_threshold_cm"],
        "champion_raw_threshold_3sigma_cm": champion.raw_threshold_3sigma_cm,
        "champion_effective_threshold_cm": champion.effective_lstm_threshold_cm,
        "deployment_equivalent": True, "operational_encoding": expected["operational_encoding"]}


def load_candidate_bundle(run_id: str, *, base: Path = BASE, load_models: bool = True) -> QCBundle:
    """Verify assets and distinguish historical direct T from operational DEV."""
    if not isinstance(run_id, str) or not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("후보 실행 ID는 경로가 아닌 단일 폴더 이름이어야 합니다.")
    base = Path(base).resolve()
    runs_root = (base / "reports/candidate_runs").resolve(strict=True)
    run_root = (runs_root / run_id).resolve(strict=True)
    if not run_root.is_relative_to(runs_root):
        raise ValueError("후보 실행 폴더가 candidate_runs 밖을 가리킵니다.")
    artifact_path = run_root / "artifact.json"
    artifact = _json(artifact_path)
    if artifact.get("run_id") != run_id:
        raise ValueError("후보 실행 ID와 artifact.json의 실행 ID가 다릅니다.")
    station, sensor = artifact.get("station"), artifact.get("sensor")
    if not isinstance(station, str) or not station or not isinstance(sensor, str) or not sensor:
        raise ValueError("후보 artifact.json에 관측소와 센서가 필요합니다.")
    sea = normalize_sea(artifact["sea"])
    records = artifact.get("bundle")
    if not isinstance(records, dict) or not set(_BUNDLE_NAMES).issubset(records):
        raise ValueError("후보 번들에는 모델, 스케일러, DEV, threshold_metadata.json의 SHA-256 기록이 필요합니다.")
    files: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    for role, record in records.items():
        if not isinstance(record, dict):
            raise ValueError(f"후보 자산 기록이 객체가 아닙니다: {role}")
        paths[role], files[role] = _verified_file(run_root, record, relative_key="relative_path")
        if role in _BUNDLE_NAMES and paths[role] != (run_root / "bundle" / _BUNDLE_NAMES[role]).resolve():
            raise ValueError(f"후보 자산의 역할과 파일명이 다릅니다: {role}")
        if record.get("path") and Path(record["path"]).resolve() != paths[role]:
            raise ValueError(f"후보 자산의 절대 경로와 상대 경로가 다릅니다: {role}")
    dev = _nonnegative_number(paths["threshold"].read_text(encoding="utf-8").strip(), "실제 DEV 값")
    sidecar = _json(paths["threshold_metadata"])
    if sidecar.get("schema_version") != "ocean-ai-threshold-2":
        raise ValueError("후보 임계값 메타데이터 버전이 올바르지 않습니다.")
    if str(sidecar.get("dev_sha256", "")).lower() != files["threshold"]["sha256"]:
        raise ValueError("후보 임계값 메타데이터의 DEV SHA-256이 다릅니다.")
    threshold = sidecar.get("threshold")
    if not isinstance(threshold, dict) or threshold != artifact.get("threshold"):
        raise ValueError("후보 artifact.json과 threshold_metadata.json의 임계값 정보가 다릅니다.")
    for identity, expected in (("run_id", run_id), ("station", station), ("sensor", sensor), ("sea", sea)):
        for document in (sidecar, threshold):
            if identity in document and document[identity] != expected:
                raise ValueError(f"후보 임계값 메타데이터의 {identity}가 모델 정보와 다릅니다.")
    raw, effective, method, consumption = _candidate_threshold_inputs(threshold, dev, station, sensor, base)
    mode = threshold.get("threshold_optimization_mode")
    if mode not in {"F1_GRID_SEARCH_OPTIMIZED", "STEPPED_3SIGMA_FALLBACK", "NORMAL_ONLY_GUARDRAIL_ADJUSTED"}:
        raise ValueError("후보 임계값 계산 모드를 확인할 수 없습니다.")
    config = build_config(sea, base=base)
    if (station, sensor) not in config["station_sensor_pairs"]:
        raise ValueError("후보 관측소/센서/해역이 실제 CSV 매핑과 다릅니다.")
    guardrails = threshold.get("calibration_guardrails", artifact.get("calibration_guardrails"))
    metadata = _metadata(base, "candidate", station, sensor, sea, files, method)
    metadata.update({"run_id": run_id, "artifact_path": str(artifact_path), "artifact_sha256": _sha256(artifact_path),
                     "raw_threshold_3sigma_cm": raw, "metadata_raw_threshold_3sigma_cm": raw,
                     "effective_lstm_threshold_cm": effective, "effective_threshold_cm": effective,
                     "threshold_optimization_mode": mode, "threshold_metadata": sidecar,
                     "threshold_metadata_path": str(paths["threshold_metadata"]),
                     "threshold_metadata_sha256": files["threshold_metadata"]["sha256"],
                     "configuration": config["metadata"], "calibration_guardrails": guardrails,
                     "calibration_guardrails_passed": (guardrails.get("passed") if isinstance(guardrails, dict)
                                                       else threshold.get("calibration_guardrails_passed")),
                     "calibration_guardrails_available": threshold.get("calibration_guardrails_available"),
                     "threshold_sanity_passed": artifact.get("threshold_sanity_passed")})
    metadata.update(consumption)
    model, scaler = _load_models(paths["model"], paths["scaler"]) if load_models else (None, None)
    json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    return QCBundle(station, sensor, "candidate", sea, model, scaler, raw, effective, metadata, dev)
