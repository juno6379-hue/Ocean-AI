"""Record separate offline jobs without importing or executing legacy AI code."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
for _path_entry in (str(WORKSPACE), str(WORKSPACE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("run_record_wrapper", sys.modules[__name__])
sys.modules.setdefault("scripts.run_record_wrapper", sys.modules[__name__])

from scripts.local_trial_manifest import sha256, validate, write_json


def run_job(manifest_path: Path, python: Path, job: str, timeout: int = 1800) -> tuple[Path, int]:
    if job not in {"models", "replay"} or timeout <= 0:
        raise ValueError("Only bounded offline model/replay jobs are allowed")
    manifest_path = manifest_path.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = validate(manifest)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:10]
    folder = WORKSPACE / "reports" / "local_runs" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    output = folder / "results.json"
    script = WORKSPACE / "scripts" / "offline_model_suite.py"
    worker_script = WORKSPACE / "scripts" / "replay_prediction_worker.py" if job == "replay" else None
    command = [str(python.resolve(strict=True)), "-X", "utf8", str(script), job,
               "--manifest", str(manifest_path), "--output", str(output)]
    record = {"run_id": run_id, "job": job, "status": "RUNNING",
              "started_at": datetime.now(timezone.utc).isoformat(),
              "command": command, "cwd": str(folder), "timeout_seconds": timeout,
              "manifest_sha256": sha256(manifest_path), "inputs_before": before,
              "source_script_sha256": sha256(script), "database_used": False,
              "live_operation": False}
    if worker_script is not None:
        record["worker_script_sha256"] = sha256(worker_script)
    write_json(folder / "run.json", record)
    environment = os.environ.copy()
    environment.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2",
                        "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    started = time.monotonic()
    returncode = 1
    try:
        with (folder / "stdout.log").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
            result = subprocess.run(command, cwd=folder, env=environment, stdout=stdout,
                                    stderr=stderr, timeout=timeout, check=False, shell=False)
        returncode = result.returncode
        record["child_returncode"] = returncode
        if not output.is_file():
            raise RuntimeError("Child did not write a result report")
        report = json.loads(output.read_text(encoding="utf-8"))
        if report.get("passed") is not True:
            returncode = returncode or 1
        record["status"] = "FINISHED" if returncode == 0 else "FAILED"
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        record["status"] = "FAILED"
        record["error"] = f"{type(error).__name__}: {error}"
        returncode = 1
    finally:
        try:
            record["inputs_after"] = validate(manifest)
            record["manifest_unchanged"] = sha256(manifest_path) == record["manifest_sha256"]
            record["job_script_unchanged"] = sha256(script) == record["source_script_sha256"]
            if worker_script is not None:
                record["worker_script_unchanged"] = sha256(worker_script) == record["worker_script_sha256"]
                if not record["worker_script_unchanged"]:
                    raise ValueError("Prediction worker script changed during execution")
            if not record["manifest_unchanged"] or not record["job_script_unchanged"]:
                raise ValueError("Manifest or job script changed during execution")
        except (OSError, ValueError, KeyError) as error:
            record["status"] = "FAILED"
            record["integrity_error"] = str(error)
            returncode = 1
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        record["elapsed_seconds"] = time.monotonic() - started
        record["returncode"] = returncode
        record["outputs"] = [{"path": p.relative_to(folder).as_posix(), "bytes": p.stat().st_size,
                              "sha256": sha256(p)} for p in sorted(folder.rglob("*"))
                             if p.is_file() and p.name != "run.json"]
        write_json(folder / "run.json", record)
    return folder, returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=["models", "replay"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    folder, code = run_job(args.manifest, args.python, args.job, args.timeout)
    print(json.dumps({"run_folder": str(folder), "returncode": code}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
