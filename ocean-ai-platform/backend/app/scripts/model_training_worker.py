"""Idle-safe local worker CLI. It never grants approvals or deploys candidates."""
import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.config import settings
from app.ml.comparison_runner import DatabaseAuthority, _atomic_json
from app.ml.job_queue import DurableQueue, code_fingerprint
from app.ml.serving import runtime_root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    if os.environ.get("OCEAN_TRAINING_WORKER_ENABLED", "0") != "1":
        print(json.dumps({"status": "WORKER_DISABLED", "training_started": False})); return 2
    if not 1 <= args.poll_seconds <= 60:
        raise SystemExit("poll-seconds must be between 1 and 60")
    queue = DurableQueue(runtime_root() / "worker")
    identity = {"worker_instance_id": uuid.uuid4().hex, "pid": os.getpid(), "executable": sys.executable,
        "started_at": datetime.now(timezone.utc).isoformat(), "code_sha256": code_fingerprint(), "queue_root": str(queue.root),
        "process_creation_token": process_creation_token(os.getpid()), "mode": "LOCAL_APPROVED_INPUT_ONLY"}
    try:
        while True:
            if code_fingerprint() != identity["code_sha256"]:
                print(json.dumps({"status": "WORKER_CODE_CHANGED_RESTART_REQUIRED"})); return 2
            _atomic_json(queue.root / "heartbeat.json", {**identity, "checked_at": datetime.now(timezone.utc).isoformat(), "status": "RUNNING"})
            with SessionLocal() as db:
                if db.bind.dialect.name == "postgresql":
                    db.execute(text("SET TRANSACTION READ ONLY"))
                with db.no_autoflush:
                    result = queue.run_once(DatabaseAuthority(db, settings.DATASET_SNAPSHOT_DIR))
                db.rollback()
            _atomic_json(queue.root / "last-worker-result.json", {"checked_at": datetime.now(timezone.utc).isoformat(), **result})
            if args.once:
                print(json.dumps({"status": result["status"], "job_id": result.get("job_id")}, ensure_ascii=False)); return 0
            time.sleep(args.poll_seconds)
    finally:
        _atomic_json(queue.root / "heartbeat.json", {**identity, "checked_at": datetime.now(timezone.utc).isoformat(), "status": "STOPPED"})


def process_creation_token(pid):
    """Query Windows process creation time without os.kill/termination APIs."""
    if os.name != "nt":
        path = Path("/proc") / str(pid) / "stat"
        return path.read_text().split(")", 1)[1].split()[19] if path.exists() else None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return None
    class FILETIME(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]
    created, exited, system, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(FILETIME)] * 4
    try:
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(system), ctypes.byref(user)):
            return None
        return str((created.high << 32) | created.low)
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    raise SystemExit(main())
