"""Read-only asset manifest for local trials; never an operational release."""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from scripts.workspace_paths import resolve_backup_code_root, resolve_manifest_root

ARTIFACT_NAMES = {
    "model": "residual_lstm_forecast.h5",
    "scaler": "scaler.forecast.gz",
    "threshold": "Thres.forecast.DEV",
}
_JSON_LOCK = threading.RLock()


def _is_retryable_permission_error(error: OSError) -> bool:
    return isinstance(error, PermissionError) or getattr(error, "winerror", None) in {5, 32, 33}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    """Read UTF-8 JSON while serializing with in-process writers and retrying brief Windows locks."""
    path = Path(path)
    for attempt in range(16):
        try:
            with _JSON_LOCK:
                text = path.read_text(encoding="utf-8")
            return json.loads(text)
        except OSError as error:
            if not _is_retryable_permission_error(error) or attempt == 15:
                raise
            time.sleep(0.05)
    raise RuntimeError(f"Unreachable read_json retry exhaustion for {path}")


def write_json(path: Path, value: dict) -> None:
    """Keep atomic UTF-8 replacement, retrying short Windows access/sharing/lock violations."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tid = threading.get_ident()
    temporary = path.with_name(f"{path.name}.part.{tid}.{uuid.uuid4().hex[:8]}")
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    try:
        with _JSON_LOCK:
            temporary.write_text(payload, encoding="utf-8")
        # An open Windows reader may deny renaming (WinError 5, 32, 33 / PermissionError) until its handle closes.
        # Sixteen attempts cap deliberate waiting at ~3 seconds; all other errors propagate.
        for attempt in range(16):
            try:
                with _JSON_LOCK:
                    temporary.replace(path)
                return
            except OSError as error:
                if not _is_retryable_permission_error(error) or attempt == 15:
                    raise
                time.sleep(0.2)
    finally:
        with contextlib.suppress(OSError):
            temporary.unlink(missing_ok=True)


def confined_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Invalid manifest path")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or any(p in {"..", "."} or ":" in p for p in parts.parts):
        raise ValueError(f"Path traversal rejected: {relative}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside input root: {relative}")
    return path


def mapping_pairs(path: Path) -> list[dict]:
    pairs = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            for column in ("TIDE1(MAIN)", "TIDE2", "TIDE3"):
                sensor = row[column].strip()
                if sensor and sensor != "-":
                    pairs.append({"station": row["CODE"], "sensor": "TIDE_LEVEL_" + sensor,
                                  "sea": row["SEA_INFO"]})
    keys = [(p["station"], p["sensor"]) for p in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate mapping pair")
    return pairs


def build(root: Path, expected_count: int = 64) -> dict:
    root = root.resolve()
    pairs = mapping_pairs(root / "mappingBySea.csv")
    if len(pairs) != expected_count:
        raise ValueError(f"Mapping count {len(pairs)} != {expected_count}")
    paths = {p.relative_to(root).as_posix() for p in root.iterdir()
             if p.is_file() and p.suffix.lower() in {".py", ".bat"}}
    paths.add("mappingBySea.csv")
    for name in ("threshold_multiplier.sneaky", "residual_std_thresholds.csv"):
        paths.add("model_output_forecast/" + name)
    for pair in pairs:
        for role, name in ARTIFACT_NAMES.items():
            relative = f"model_output_forecast/{pair['station']}/{pair['sensor']}/{name}"
            pair[role] = relative
            paths.add(relative)
    files = []
    for relative in sorted(paths):
        path = confined_path(root, relative)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing or empty input: {relative}")
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"schema_version": "local-trial-1", "purpose": "OFFLINE_TRIAL_ONLY",
            "created_at": datetime.now(timezone.utc).isoformat(), "root": str(root),
            "expected_pair_count": expected_count, "ai_flag_position": 11,
            "operational_deployment": False, "files": files, "models": pairs}


def validate(manifest: dict) -> dict:
    if manifest.get("schema_version") != "local-trial-1" or manifest.get("purpose") != "OFFLINE_TRIAL_ONLY":
        raise ValueError("Not a supported local trial manifest")
    if manifest.get("operational_deployment") is not False or manifest.get("ai_flag_position") != 11:
        raise ValueError("Operational scope or AI flag position changed")
    root = resolve_manifest_root(manifest, BASE)
    records = manifest["files"]
    if not records or len({r["path"].casefold() for r in records}) != len(records):
        raise ValueError("Empty or duplicate file records")
    indexed = {}
    for record in records:
        path = confined_path(root, record["path"])
        if not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
            raise ValueError("Invalid SHA-256")
        if not isinstance(record["bytes"], int) or record["bytes"] <= 0:
            raise ValueError("Invalid size")
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise ValueError(f"Input integrity failure: {record['path']}")
        indexed[record["path"]] = record
    if "mappingBySea.csv" not in indexed:
        raise ValueError("Mapping is not hashed")
    pairs = mapping_pairs(root / "mappingBySea.csv")
    models = manifest["models"]
    if len(models) != manifest["expected_pair_count"] or len(pairs) != len(models):
        raise ValueError("Model count mismatch")
    expected = {(p["station"], p["sensor"], p["sea"]) for p in pairs}
    actual = {(p["station"], p["sensor"], p["sea"]) for p in models}
    if actual != expected or len(actual) != len(models):
        raise ValueError("Model identity mismatch")
    for pair in models:
        for role, name in ARTIFACT_NAMES.items():
            expected_path = f"model_output_forecast/{pair['station']}/{pair['sensor']}/{name}"
            if pair[role] != expected_path or pair[role] not in indexed:
                raise ValueError(f"Invalid or unhashed {role}")
    return {"passed": True, "checked_files": len(records), "model_count": len(models)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "validate"])
    parser.add_argument("--root", type=Path, default=resolve_backup_code_root(BASE))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=BASE / "manifests/20261006_local_trial_manifest.json",
    )
    args = parser.parse_args()
    if args.action == "build":
        if args.manifest.exists() or args.root is None:
            parser.error("Build requires --root and a new manifest path")
        manifest = build(args.root)
        result = validate(manifest)
        write_json(args.manifest, manifest)
    else:
        result = validate(json.loads(args.manifest.read_text(encoding="utf-8")))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
