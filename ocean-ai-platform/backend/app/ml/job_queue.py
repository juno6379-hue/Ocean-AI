"""Fenced SQLite durable queue; independent workers, bounded leases, no approvals."""
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from app.ml.comparison_runner import ComparisonBlocked, _atomic_json, compare, digest, preflight


class DurableQueue:
    def __init__(self, root, clock=time.time):
        from app.ml.comparison_runner import reject_reparse
        reject_reparse(root)
        self.root, self.clock = Path(root).resolve(), clock
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS queue_jobs (
                job_id TEXT PRIMARY KEY, scope TEXT NOT NULL, manifest_path TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
                state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
                lease_seconds INTEGER NOT NULL, token TEXT, lease_until REAL, available_at REAL NOT NULL,
                receipt_path TEXT, receipt_sha256 TEXT, code_sha256 TEXT, reason TEXT, created_at REAL NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_scope ON queue_jobs(scope) WHERE state IN ('QUEUED','RUNNING');""")

    def connect(self):
        db = sqlite3.connect(self.root / "worker-queue.sqlite3", timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def enqueue(self, manifest_path, authority, expected_sha256=None):
        prepared = preflight(manifest_path, authority)
        if expected_sha256 is not None and prepared['manifest_sha256'] != expected_sha256:
            raise ComparisonBlocked('REVIEWED_MANIFEST_CHANGED')
        protocols = prepared.get("protocols")
        if not protocols:
            raise ComparisonBlocked("APPROVED_TRAINING_PROTOCOLS_REQUIRED")
        evaluation = protocols["EVALUATION_PROTOCOL"]["body"]
        retry = evaluation.get("worker_policy")
        if not isinstance(retry, dict) or type(retry.get("max_attempts")) is not int or not 1 <= retry["max_attempts"] <= 3 or type(retry.get("lease_seconds")) is not int or not 30 <= retry["lease_seconds"] <= 3600:
            raise ComparisonBlocked("REVIEWED_BOUNDED_WORKER_POLICY_REQUIRED")
        code_sha = code_fingerprint()
        key = digest({"manifest": prepared["manifest_sha256"], "origins": prepared["origin_membership_sha256"], "protocols": {k: v["sha256"] for k, v in protocols.items()}, "code": code_sha})
        scope = digest({k: prepared["manifest"].get(k) for k in ("domain", "item_id", "task", "target_variable", "unit")})
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM queue_jobs WHERE job_id=?", (key,)).fetchone()
            if existing:
                return {"job_id": key, "state": existing["state"], "idempotent_reuse": True}
            if db.execute("SELECT job_id FROM queue_jobs WHERE scope=? AND state IN ('QUEUED','RUNNING')", (scope,)).fetchone():
                raise ComparisonBlocked("TRAINING_SCOPE_ALREADY_QUEUED")
            db.execute("INSERT INTO queue_jobs(job_id,scope,manifest_path,manifest_sha256,state,max_attempts,lease_seconds,available_at,created_at,code_sha256) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (key, scope, str(Path(manifest_path).resolve()), prepared["manifest_sha256"], "QUEUED", retry["max_attempts"], retry["lease_seconds"], self.clock(), self.clock(), code_sha))
        return {"job_id": key, "state": "QUEUED", "training_started": False}

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self.clock()
            for expired in db.execute("SELECT * FROM queue_jobs WHERE state='RUNNING' AND lease_until<?", (now,)).fetchall():
                state = "QUARANTINED" if expired["attempts"] >= expired["max_attempts"] else "QUEUED"
                db.execute("UPDATE queue_jobs SET state=?,token=NULL,lease_until=NULL,reason='LEASE_EXPIRED',available_at=? WHERE job_id=?",
                           (state, now + 30, expired["job_id"]))
            row = db.execute("SELECT * FROM queue_jobs WHERE state='QUEUED' AND available_at<=? ORDER BY created_at,job_id LIMIT 1", (now,)).fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            db.execute("UPDATE queue_jobs SET state='RUNNING',token=?,lease_until=?,attempts=attempts+1 WHERE job_id=?",
                       (token, now + row["lease_seconds"], row["job_id"]))
            return {**dict(row), "token": token, "attempts": row["attempts"] + 1}

    def heartbeat(self, job):
        with self.connect() as db:
            return db.execute("UPDATE queue_jobs SET lease_until=? WHERE job_id=? AND token=? AND state='RUNNING' AND lease_until>=?",
                (self.clock() + job["lease_seconds"], job["job_id"], job["token"], self.clock())).rowcount == 1

    def finish(self, job, state, path, reason=None):
        import hashlib
        sha = hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None
        with self.connect() as db:
            changed = db.execute("UPDATE queue_jobs SET state=?,receipt_path=?,receipt_sha256=?,reason=?,lease_until=NULL WHERE job_id=? AND token=? AND state='RUNNING' AND lease_until>=?",
                (state, str(path) if path else None, sha, reason, job["job_id"], job["token"], self.clock())).rowcount
        if changed != 1:
            raise ComparisonBlocked("WORKER_LEASE_FENCED")

    def run_once(self, authority):
        job = self.claim()
        if job is None:
            return {"status": "IDLE"}
        # The full job identity remains in the ledger/receipt. A unique fencing
        # token directory avoids Windows path limits under lengthy work roots.
        output = self.root / "attempts" / job["token"]
        output.mkdir(parents=True, exist_ok=False)
        stop, lost = threading.Event(), threading.Event()
        def maintain():
            while not stop.wait(max(1, min(10, job["lease_seconds"] / 3))):
                if not self.heartbeat(job):
                    lost.set(); return
                heartbeat_path = self.root / "heartbeat.json"
                if heartbeat_path.exists():
                    from app.ml.comparison_runner import read_json
                    from datetime import datetime, timezone
                    pulse, _ = read_json(heartbeat_path)
                    _atomic_json(heartbeat_path, {**pulse, "checked_at": datetime.now(timezone.utc).isoformat(), "active_job_id": job["job_id"]})
        thread = threading.Thread(target=maintain, daemon=True)
        thread.start()
        try:
            if code_fingerprint() != job["code_sha256"]:
                raise ComparisonBlocked("QUEUED_RUNNER_CODE_CHANGED")
            prepared = preflight(job["manifest_path"], authority)
            if prepared["manifest_sha256"] != job["manifest_sha256"]:
                raise ComparisonBlocked("QUEUED_INPUT_CHANGED")
            from datetime import datetime, timezone
            started_at = datetime.now(timezone.utc).isoformat()
            result = compare(prepared)
            from app.ml.serving import predict_artifact
            durations = []
            for row in prepared["rows"]["TEST"][:200]:
                started = time.perf_counter()
                predict_artifact(result["artifact"], row["x"], row.get("origin_payload"))
                durations.append(1000 * (time.perf_counter() - started))
            import numpy as np
            result["local_call_p95_ms"] = float(np.percentile(durations, 95))
            from app.ml.protocols import evaluate_acceptance
            result["acceptance"] = evaluate_acceptance(result, prepared["protocols"]["ACCEPTANCE_POLICY"]["body"])
            after = preflight(job["manifest_path"], authority)
            if lost.is_set() or code_fingerprint() != job["code_sha256"] or after["origin_membership_sha256"] != prepared["origin_membership_sha256"] or after["manifest_sha256"] != prepared["manifest_sha256"]:
                raise ComparisonBlocked("INPUT_CHANGED_OR_WORKER_LEASE_LOST")
            result.update(job_id=job["job_id"], attempt=job["attempts"], fencing_token=job["token"], training_started=True,
                          manifest_path=job["manifest_path"], protocol_hashes={k: v["sha256"] for k, v in prepared["protocols"].items()},
                          code_sha256=job["code_sha256"], training_started_at=started_at, training_finished_at=datetime.now(timezone.utc).isoformat())
            row = prepared["rows"]["TEST"][0]
            result["serving_smoke_sample"] = {"features": row["x"], "typed_payload": row.get("origin_payload")}
            artifact_path = output / "artifact.json"
            _atomic_json(artifact_path, result["artifact"])
            import hashlib
            result["artifact_path"], result["artifact_sha256"] = str(artifact_path), hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            receipt_path = output / "comparison.json"
            _atomic_json(receipt_path, result)
            self.finish(job, "COMPLETED_CANDIDATE", receipt_path)
            return result
        except Exception as exc:
            reason = exc.code if isinstance(exc, ComparisonBlocked) else type(exc).__name__
            failure = {"status": "FAILED_QUARANTINED", "job_id": job["job_id"], "reason": reason, "registered_models": 0, "deployed_models": 0}
            _atomic_json(output / "failure.json", failure)
            try:
                self.finish(job, "QUARANTINED", output / "failure.json", reason)
            except ComparisonBlocked:
                failure["status"] = "STALE_WORKER_FENCED"
            return failure
        finally:
            stop.set(); thread.join(timeout=1)


def code_fingerprint():
    import hashlib
    import platform
    import numpy, sklearn
    app = Path(__file__).parent.parent
    files = list(Path(__file__).parent.glob("*.py")) + [Path(__file__).with_name("model_scope_matrix.json")]
    for name in ("services/source_contract_authority.py", "services/source_contract_snapshot.py", "services/dataset_lineage.py",
                 "services/source_contract_review.py", "services/identity_link_review.py", "api/routes_datasets.py", "scripts/model_training_worker.py"):
        files.append(app / name)
    return digest({"python": platform.python_version(), "numpy": numpy.__version__, "sklearn": sklearn.__version__,
        "code_dependencies": {str(p.relative_to(app)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
