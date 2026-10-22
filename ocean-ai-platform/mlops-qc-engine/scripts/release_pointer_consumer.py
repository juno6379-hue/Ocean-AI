"""Runtime release-pointer consumer that resolves active model/scaler/threshold assets without modifying legacy files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("release_pointer_consumer", sys.modules[__name__])
sys.modules.setdefault("scripts.release_pointer_consumer", sys.modules[__name__])

from scripts.candidate_training_worker import compute_effective_threshold, load_candidate_threshold
from scripts.local_trial_manifest import confined_path, sha256
from scripts.workspace_paths import resolve_backup_code_root, resolve_manifest_root, resolve_project_path

ACTIVE_POINTER_PATH = BASE / "manifests/active_release_pointer.json"
BASELINE_MANIFEST_PATH = BASE / "manifests/20261006_local_trial_manifest.json"


def resolve_runtime_bundle(
    station: str,
    sensor: str,
    verify_hash: bool = True,
    pointer_path: Path = ACTIVE_POINTER_PATH,
    baseline_manifest_path: Path = BASELINE_MANIFEST_PATH,
) -> dict:
    """Resolve the active operational model, scaler, and threshold bundle for (station, sensor).

    Reads `manifests/active_release_pointer.json` and its referenced `operational_release_manifest`
    when available, falling back to the 64-model 2025 baseline manifest otherwise.
    """
    station = str(station or "").strip()
    sensor = str(sensor or "").strip()
    if not station or not sensor:
        raise ValueError("관측소(station)와 센서(sensor) 코드를 모두 입력해 주세요.")

    baseline = json.loads(Path(baseline_manifest_path).read_text(encoding="utf-8"))
    try:
        baseline_root = resolve_manifest_root(baseline, BASE)
    except FileNotFoundError:
        baseline_root = resolve_backup_code_root(BASE)
    base_pair = next(
        (p for p in baseline.get("models", []) if p["station"] == station and p["sensor"] == sensor),
        None,
    )
    if base_pair is None:
        raise ValueError(f"64개 운영 매핑 대상에 없는 관측소/센서 조합입니다: {station} / {sensor}")

    sea = base_pair.get("sea", "")
    active_release_id = "2025_OPERATION_64_BASELINE"
    run_id = "2025_OPERATION_64_BASELINE"
    champion_version = None
    rollback_version = None
    promoted_at = None
    source_mode = "BASELINE_2025"
    threshold_metadata_entry = None

    indexed_files = {f["path"]: f for f in baseline.get("files", [])}
    model_entry = {
        "uri": str(confined_path(baseline_root, base_pair["model"])),
        "sha256": indexed_files[base_pair["model"]]["sha256"],
        "bytes": int(indexed_files[base_pair["model"]].get("bytes") or 0),
    }
    scaler_entry = {
        "uri": str(confined_path(baseline_root, base_pair["scaler"])),
        "sha256": indexed_files[base_pair["scaler"]]["sha256"],
        "bytes": int(indexed_files[base_pair["scaler"]].get("bytes") or 0),
    }
    thres_entry = {
        "uri": str(confined_path(baseline_root, base_pair["threshold"])),
        "sha256": indexed_files[base_pair["threshold"]]["sha256"],
        "bytes": int(indexed_files[base_pair["threshold"]].get("bytes") or 0),
    }

    ptr_file = Path(pointer_path)
    if ptr_file.is_file():
        pointer = json.loads(ptr_file.read_text(encoding="utf-8"))
        active_release_id = pointer.get("active_release_id") or active_release_id
        rel_raw_path = pointer.get("active_release_path", "")
        if rel_raw_path:
            rel_path = resolve_project_path(rel_raw_path, BASE)
            if not rel_path.is_file():
                raise ValueError(f"활성 릴리스 매니페스트 파일을 찾을 수 없습니다: {rel_path}")
            if verify_hash and pointer.get("active_release_sha256"):
                actual_rel_sha = sha256(rel_path)
                if actual_rel_sha != pointer["active_release_sha256"]:
                    raise ValueError("활성 릴리스 매니페스트 파일의 SHA-256 해시가 포인터 기록과 다릅니다.")
            rel_manifest = json.loads(rel_path.read_text(encoding="utf-8"))
            rel_pair = next(
                (
                    m
                    for m in rel_manifest.get("models", [])
                    if m.get("station_code") == station and m.get("sensor_code") == sensor
                ),
                None,
            )
            if rel_pair is not None:
                run_id = rel_pair.get("run_id", run_id)
                model_entry = rel_pair["model"]
                scaler_entry = rel_pair["scaler"]
                thres_entry = rel_pair["threshold"]
                threshold_metadata_entry = rel_pair.get("threshold_metadata")
                if run_id != "2025_OPERATION_64_BASELINE":
                    source_mode = "PROMOTED_OVERRIDE"

        override = (pointer.get("station_overrides") or {}).get(f"{station}|{sensor}")
        if isinstance(override, dict):
            source_mode = "PROMOTED_OVERRIDE"
            run_id = override.get("run_id", run_id)
            champion_version = override.get("champion_version")
            rollback_version = override.get("rollback_version")
            promoted_at = override.get("promoted_at")

    resolved_assets = {}
    asset_entries = [
        ("model", model_entry),
        ("scaler", scaler_entry),
        ("threshold", thres_entry),
    ]
    if threshold_metadata_entry is not None:
        asset_entries.append(("threshold_metadata", threshold_metadata_entry))

    clean_baseline_without_backup = source_mode == "BASELINE_2025" and not baseline_root.exists()
    effective_hash_verified = bool(verify_hash) and not clean_baseline_without_backup

    for role, entry in asset_entries:
        asset_path = resolve_project_path(entry["uri"], BASE)
        expected_sha = entry["sha256"]
        if clean_baseline_without_backup and not asset_path.is_file():
            resolved_assets[role] = {
                "path": str(asset_path),
                "sha256": expected_sha,
                "bytes": int(entry.get("bytes") or 0),
            }
            continue
        if not asset_path.is_file():
            raise ValueError(f"활성 {role} 산출물 파일을 찾을 수 없습니다: {asset_path}")
        if verify_hash:
            actual_sha = sha256(asset_path)
            if actual_sha != expected_sha:
                raise ValueError(f"활성 {role} 산출물 SHA-256 불일치 ({station}/{sensor}): {asset_path}")
        resolved_assets[role] = {
            "path": str(asset_path),
            "sha256": expected_sha,
            "bytes": asset_path.stat().st_size,
        }

    thres_disk_path = Path(resolved_assets["threshold"]["path"])
    if not thres_disk_path.is_file() and clean_baseline_without_backup:
        threshold_info = {
            "raw_dev_value": None,
            "effective_threshold_cm": None,
            "mode": "manifest_only",
        }
    else:
        raw_thres = float(thres_disk_path.read_text(encoding="utf-8").strip())
        if "threshold_metadata" in resolved_assets:
            metadata_path = Path(resolved_assets["threshold_metadata"]["path"])
            metadata_document = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata_document.get("schema_version") != "ocean-ai-threshold-2":
                raise ValueError("활성 임계값 메타데이터 버전이 올바르지 않습니다.")
            if metadata_document.get("dev_sha256") and metadata_document["dev_sha256"] != resolved_assets["threshold"]["sha256"]:
                raise ValueError("활성 임계값 메타데이터의 DEV SHA-256이 다릅니다.")
            threshold_info = load_candidate_threshold(
                thres_disk_path.parent,
                metadata=metadata_document["threshold"],
            )
        else:
            threshold_info = compute_effective_threshold(raw_thres)

    return {
        "station": station,
        "sensor": sensor,
        "sea": sea,
        "source_mode": source_mode,
        "active_release_id": active_release_id,
        "run_id": run_id,
        "champion_version": champion_version,
        "rollback_version": rollback_version,
        "promoted_at": promoted_at,
        "hash_verified": effective_hash_verified,
        "threshold": threshold_info,
        "assets": resolved_assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve active runtime model/scaler/threshold paths via release pointer.")
    parser.add_argument("--station", required=True)
    parser.add_argument("--sensor", required=True)
    parser.add_argument("--no-verify-hash", action="store_true")
    args = parser.parse_args()
    bundle = resolve_runtime_bundle(
        station=args.station,
        sensor=args.sensor,
        verify_hash=not args.no_verify_hash,
    )
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
