"""Loopback-only controls for the separate offline trial tools; no original AI execution."""
import argparse
import contextlib
import csv
import importlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("local_dashboard", sys.modules[__name__])
sys.modules.setdefault("scripts.local_dashboard", sys.modules[__name__])

import scripts.dataset_preview as preview
from scripts.local_trial_manifest import _JSON_LOCK, read_json, validate, write_json
from scripts.run_record_wrapper import run_job
from scripts.dataset_routes import register_routes
from scripts.ocean_ai_snapshot import CHRONOLOGICAL_SPLIT_POLICY, ParquetSnapshotAuthority
from scripts.release_pointer_consumer import resolve_runtime_bundle
from scripts.workspace_paths import resolve_manifest_root
from scripts.tensorflow_runtime import resolve_tensorflow_python
from scripts.training_control import DEFAULT_BATCH_SIZE, DEFAULT_EPOCHS
from scripts.comparison_contract import duel_series
from scripts.ocean_ai_bridge import (
    export_ocean_ai_bundle,
    get_ocean_ai_bridge_status,
    sync_to_ocean_ai_db,
)
import scripts.model_lifecycle as lifecycle

fastapi: Any = importlib.import_module("fastapi")
cors: Any = importlib.import_module("fastapi.middleware.cors")
responses: Any = importlib.import_module("fastapi.responses")
trustedhost: Any = importlib.import_module("starlette.middleware.trustedhost")
MANIFEST = BASE / "manifests/20261006_local_trial_manifest.json"
RUNS = BASE / "reports/local_runs"
STORE = BASE / "reports/mlflow_trial"
JOBS = BASE / "reports/dashboard_jobs"
PYTHON = resolve_tensorflow_python(BASE)
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
active_job = None
active_job_record: dict[str, Any] | None = None
app = fastapi.FastAPI(docs_url=None, redoc_url=None)
app.add_middleware(trustedhost.TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
app.add_middleware(
    cors.CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_routes(app, TOKEN, LOCK)


def _verify_dashboard_or_bridge_token(
    x_dashboard_token: str = "",
    x_local_token: str = "",
    x_ocean_ai_bridge_token: str = "",
    authorization: str = "",
) -> bool:
    candidates: list[str] = []
    for raw in (x_dashboard_token, x_local_token, x_ocean_ai_bridge_token):
        if raw and raw.strip():
            candidates.append(raw.strip())
    if authorization and authorization.lower().startswith("bearer "):
        bearer_val = authorization[7:].strip()
        if bearer_val:
            candidates.append(bearer_val)
    expected_tokens = [TOKEN]
    env_bridge = os.environ.get("OCEAN_AI_BRIDGE_TOKEN", "").strip()
    if env_bridge:
        expected_tokens.append(env_bridge)
    for cand in candidates:
        for exp in expected_tokens:
            if secrets.compare_digest(cand, exp):
                return True
    return False


def _snapshot_job_record(record: dict[str, Any]) -> dict[str, Any]:
    with _JSON_LOCK:
        copied = dict(record)
        if isinstance(copied.get("progress"), dict):
            copied["progress"] = dict(copied["progress"])
        return copied


def snapshot() -> dict:
    manifest = read_json(MANIFEST)
    station_names: dict[str, str] = {}
    with contextlib.suppress(Exception):
        manifest_root = resolve_manifest_root(manifest, BASE)
        mapping_file = manifest_root / "mappingBySea.csv"
        if mapping_file.is_file():
            with mapping_file.open(encoding="utf-8-sig", newline="") as mapping:
                station_names = {row["CODE"]: row["NAME"] for row in csv.DictReader(mapping)}
    if not station_names:
        station_names = {
            row["CODE"]: row["NAME"]
            for row in preview._fallback_mapping_rows_from_manifest()
            if row.get("CODE")
        }
    for model in manifest["models"]:
        model["station_name"] = station_names.get(model["station"], model["station"])
        model["station_display"] = preview.friendly_station_label(model["station"], model["station_name"])
        model["sensor_display"] = preview.friendly_sensor_label(model["sensor"])
    runs = []
    for path in sorted(RUNS.glob("*/run.json"), reverse=True):
        record = read_json(path)
        result_path = path.parent / "results.json"
        runs.append({"id": record["run_id"], "job": record["job"],
                     "status": record["status"], "started_at": record["started_at"],
                     "elapsed_seconds": record.get("elapsed_seconds"),
                     "error": record.get("error") or record.get("integrity_error"),
                     "result": read_json(result_path) if result_path.exists() else None})
    registry = {"available": False}
    database = STORE / "tracking.db"
    if database.exists():
        with contextlib.closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            registry = {"available": True, "models": db.execute("SELECT count(*) FROM registered_models").fetchone()[0],
                        "versions": db.execute("SELECT count(*) FROM model_versions").fetchone()[0],
                        "runs": db.execute("SELECT count(*) FROM runs").fetchone()[0],
                        "aliases": db.execute("SELECT count(*) FROM registered_model_aliases").fetchone()[0]}
    is_busy = LOCK.locked()
    current_active = active_job if is_busy else None
    jobs = []
    for p in sorted(JOBS.glob("*/job.json"), reverse=True)[:20]:
        try:
            j_rec = read_json(p)
        except (OSError, ValueError):
            if is_busy and isinstance(active_job_record, dict) and p.parent.name == current_active:
                j_rec = _snapshot_job_record(active_job_record)
            else:
                continue
        if is_busy and j_rec.get("id") == current_active and isinstance(active_job_record, dict) and j_rec.get("status") == "RUNNING":
            j_rec = _snapshot_job_record(active_job_record)
        jobs.append(j_rec)
    progress = 0
    running = next((r for r in runs if r["status"] == "RUNNING"), None)
    if running is not None:
        log_path = RUNS / running["id"] / "stdout.log"
        if log_path.exists():
            progress = sum(line.startswith('{"station":') for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines())
    for job in jobs:
        run = next((r for r in runs if r["id"] == job.get("run_id")), None)
        if run and run.get("error"):
            job["error"] = run["error"]
        if job.get("status") == "RUNNING" and not (is_busy and job.get("id") == current_active):
            job["orphaned"] = True
            job.setdefault("error", "이전 실행이 중단되어 완료 기록이 없습니다.")
    cand_runs = lifecycle.list_candidate_runs(store=STORE)
    for cr in cand_runs:
        st_name = station_names.get(cr.get("station", ""), cr.get("station", ""))
        cr["station_name"] = st_name
        cr["station_display"] = preview.friendly_station_label(cr.get("station", ""), st_name)
        cr["sensor_display"] = preview.friendly_sensor_label(cr.get("sensor", ""))
    snaps = ParquetSnapshotAuthority().list_snapshots()
    for sp in snaps:
        st_name = station_names.get(sp.get("station", ""), sp.get("station", ""))
        sp["station_name"] = st_name
        sp["station_display"] = preview.friendly_station_label(sp.get("station", ""), st_name)
        sp["sensor_display"] = preview.friendly_sensor_label(sp.get("sensor", ""))
    return {"application_id": "oceandb-local-trial-dashboard",
            "models": manifest["models"], "runs": runs, "registry": registry,
            "jobs": jobs, "busy": is_busy, "active_job": current_active,
            "progress_models": progress, "replay_blocked": (BASE / "reports/replay_paused.json").exists(),
            "training_available": True, "operational_database_used": False,
            "candidate_runs": cand_runs,
            "snapshots": snaps,
            "active_release": lifecycle.active_release_state()}


def execute_job(kind: str, folder: Path, payload: dict | None = None) -> None:
    global active_job, active_job_record
    record = read_json(folder / "job.json")
    active_job_record = _snapshot_job_record(record)
    start = time.monotonic()
    last_flush = 0.0
    last_key: tuple[Any, ...] | None = None

    def _update_progress(value: dict) -> None:
        global active_job_record
        nonlocal last_flush, last_key
        with _JSON_LOCK:
            enriched = dict(record.get("progress") or {})
            if isinstance(value, dict):
                enriched.update(value)
            else:
                enriched["stage"] = str(value)
            enriched["elapsed_seconds"] = round(max(0.0, time.monotonic() - start), 1)
            record["progress"] = enriched
            active_job_record = _snapshot_job_record(record)
        now = time.monotonic()
        cur_key = (
            enriched.get("stage"),
            enriched.get("file"),
            enriched.get("file_index"),
            enriched.get("epoch"),
            enriched.get("ym"),
        )
        if cur_key != last_key or (now - last_flush) >= 0.25:
            last_key = cur_key
            last_flush = now
            try:
                write_json(folder / "job.json", record)
            except OSError:
                pass

    try:
        if kind == "validate":
            record["result"] = validate(read_json(MANIFEST))
            record["status"] = "FINISHED"
        elif kind in {"models", "replay"}:
            run_folder, code = run_job(MANIFEST, PYTHON, kind)
            record.update(status="FINISHED" if code == 0 else "FAILED", run_id=run_folder.name)
            wrapper_record = read_json(run_folder / "run.json")
            record["error"] = wrapper_record.get("error") or wrapper_record.get("integrity_error")
            record["child_returncode"] = wrapper_record.get("child_returncode")
        elif kind == "register":
            command = [sys.executable, "-X", "utf8", str(BASE / "scripts/register_mlflow_trial.py"),
                       "--manifest", str(MANIFEST), "--runs-root", str(RUNS), "--store", str(STORE)]
            with (folder / "stdout.log").open("wb") as out, (folder / "stderr.log").open("wb") as err:
                completed = subprocess.run(command, cwd=BASE, stdout=out, stderr=err,
                                           timeout=1800, check=False, shell=False)
            record["status"] = "FINISHED" if completed.returncode == 0 else "FAILED"
            record["returncode"] = completed.returncode
            if completed.returncode:
                record["error"] = (folder / "stderr.log").read_text(encoding="utf-8", errors="replace")[-3000:]
            else:
                record["result"] = read_json(STORE / "registration_report.json")
        elif kind == "candidate_train":
            req = payload or {}
            snapshot_id = str(req.get("snapshot_id", "")).strip()
            dataset_id = str(req.get("dataset_id", "")).strip()
            epochs = int(req.get("epochs", DEFAULT_EPOCHS))
            batch_size = int(req.get("batch_size", DEFAULT_BATCH_SIZE))
            seed = int(req.get("seed", 42))
            if not snapshot_id:
                if not dataset_id:
                    raise ValueError("학습에 사용할 스냅샷 ID 또는 데이터셋 ID를 선택해 주세요.")
                _update_progress({
                    "stage": "building_snapshot",
                    "stage_index": 1,
                    "stage_total": 5,
                    "percent": 3.0,
                    "epoch": 0,
                    "epochs_total": epochs,
                    "message": "데이터셋에서 학습용 Parquet 스냅샷 생성 중",
                })
                snap = ParquetSnapshotAuthority().build_from_dataset(
                    dataset_id,
                    split_policy=req.get("split_policy", CHRONOLOGICAL_SPLIT_POLICY),
                )
                snapshot_id = snap["snapshot_id"]
            eval_snapshot_id = str(req.get("eval_snapshot_id", "")).strip() or None
            eval_scope = str(req.get("eval_scope", "AUTO")).strip() or "AUTO"
            train_out = lifecycle.run_candidate_training_subprocess(
                snapshot_id=snapshot_id,
                epochs=epochs,
                batch_size=batch_size,
                seed=seed,
                eval_snapshot_id=eval_snapshot_id,
                eval_scope=eval_scope,
                store=STORE,
                manifest_path=MANIFEST,
                tf_python=PYTHON,
                progress=_update_progress,
            )
            with _JSON_LOCK:
                record["status"] = "FINISHED"
                record["candidate_run_id"] = train_out["run_id"]
                record["snapshot_id"] = snapshot_id
                record["eval_snapshot_id"] = eval_snapshot_id or snapshot_id
                active_job_record = _snapshot_job_record(record)
        elif kind == "month_index":
            req = payload or {}
            station, sensor = str(req.get("station") or ""), str(req.get("sensor") or "")
            if not re.fullmatch(r"DT_\d{4}", station) or not re.fullmatch(r"[A-Z0-9_]+", sensor):
                raise ValueError("관측소와 센서를 선택해 주세요.")
            selected_yms = req.get("selected_yms")
            if selected_yms is not None:
                if not isinstance(selected_yms, list) or not selected_yms:
                    raise ValueError("집계할 연·월을 하나 이상 선택해 주세요.")
                for ym in selected_yms:
                    if not isinstance(ym, str) or not re.fullmatch(r"\d{6}", ym):
                        raise ValueError("연·월은 YYYYMM 형식이어야 합니다.")
                    datetime.strptime(ym, "%Y%m")
            result = preview.load_or_build_monthly_anomaly_index(
                station=station, sensor=sensor, selected_yms=selected_yms,
                source_budget_bytes=None, progress=_update_progress,
            )
            record["result"] = result
            if not result["index_complete"]:
                raise ValueError("월별 원본 집계 중 오류가 발생했습니다. index_errors를 확인해 주세요.")
            _update_progress({"stage": "finished", "percent": 100.0})
            record["status"] = "FINISHED"
        elif kind == "quick_prepare":
            req = payload or {}
            prep_res = _quick_prepare_snapshot_unlocked(req, progress=_update_progress)
            with _JSON_LOCK:
                record["result"] = prep_res
                record["snapshot_id"] = prep_res["snapshot"]["snapshot_id"]
                record["dataset_id"] = prep_res["dataset"]["dataset_id"]
                if isinstance(record.get("progress"), dict):
                    prog_done = dict(record["progress"])
                    prog_done.update({
                        "stage": "finished",
                        "stage_index": 4,
                        "stage_total": 4,
                        "percent": 100.0,
                        "snapshot_id": prep_res["snapshot"]["snapshot_id"],
                        "dataset_id": prep_res["dataset"]["dataset_id"],
                    })
                    record["progress"] = prog_done
                record["status"] = "FINISHED"
                active_job_record = _snapshot_job_record(record)
        elif kind == "local_qc_simulate":
            req = payload or {}
            run_id = str(req.get("run_id", "")).strip()
            snapshot_id = str(req.get("snapshot_id", "")).strip() or None
            scope = str(req.get("scope", "TEST")).strip().upper() or "TEST"
            simulation_id = str(req.get("simulation_id", "")).strip() or None
            _update_progress({
                "stage": "running_simulation",
                "stage_index": 1,
                "stage_total": 2,
                "percent": 15.0,
                "message": f"2-Tier 로컬 전체 QC 시뮬레이션 실행 중 ({run_id}, 범위: {scope})",
            })
            sim_out = lifecycle.run_local_qc_simulation_subprocess(
                run_id=run_id,
                snapshot_id=snapshot_id,
                scope=scope,
                simulation_id=simulation_id,
                tf_python=PYTHON,
            )
            with _JSON_LOCK:
                record["status"] = "FINISHED"
                record["candidate_run_id"] = run_id
                record["simulation_id"] = sim_out.get("simulation_id")
                record["result"] = sim_out
                if isinstance(record.get("progress"), dict):
                    prog_done = dict(record["progress"])
                    prog_done.update({
                        "stage": "finished",
                        "stage_index": 2,
                        "stage_total": 2,
                        "percent": 100.0,
                        "simulation_id": sim_out.get("simulation_id"),
                        "message": "2-Tier 로컬 전체 QC 시뮬레이션 완료",
                    })
                    record["progress"] = prog_done
                active_job_record = _snapshot_job_record(record)
        else:
            raise ValueError("Unsupported job")
    except Exception as error:
        with _JSON_LOCK:
            record.update(status="FAILED", error=f"{type(error).__name__}: {error}")
            if isinstance(error, lifecycle.WorkerExecutionError):
                record.update(error.as_dict())
            active_job_record = _snapshot_job_record(record)
    finally:
        with _JSON_LOCK:
            record["elapsed_seconds"] = time.monotonic() - start
            if isinstance(record.get("progress"), dict):
                prog_final = dict(record["progress"])
                prog_final["elapsed_seconds"] = round(max(0.0, record["elapsed_seconds"]), 1)
                record["progress"] = prog_final
            active_job_record = _snapshot_job_record(record)
        try:
            write_json(folder / "job.json", record)
        finally:
            active_job = None
            active_job_record = None
            LOCK.release()


@app.get("/")
def home():
    html = (BASE / "ui/dashboard.html").read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
    return responses.HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/api/state")
def state():
    return snapshot()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if not re.fullmatch(r"\d+_[0-9a-f]{8}", job_id):
        raise fastapi.HTTPException(status_code=404, detail="작업 기록을 찾을 수 없습니다.")
    path = JOBS / job_id / "job.json"
    if not path.is_file():
        raise fastapi.HTTPException(status_code=404, detail="작업 기록을 찾을 수 없습니다.")
    try:
        record = read_json(path)
    except OSError:
        if LOCK.locked() and active_job == job_id and isinstance(active_job_record, dict):
            record = _snapshot_job_record(active_job_record)
        else:
            raise
    if LOCK.locked() and active_job == job_id and isinstance(active_job_record, dict) and record.get("status") == "RUNNING":
        record = _snapshot_job_record(active_job_record)
    if record.get("status") == "RUNNING" and not (LOCK.locked() and record.get("id") == active_job):
        record["status"] = "FAILED"
        record["orphaned"] = True
        record.setdefault("error", "이전 실행이 중단되어 완료 기록이 없습니다.")
    return record


@app.post("/api/jobs/{kind}")
def start_job(
    kind: str,
    x_dashboard_token: str = fastapi.Header(default=""),
    payload: dict | None = fastapi.Body(default=None),
):
    global active_job, active_job_record
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 실행 버튼을 눌러 주세요.")
    if kind not in {"validate", "models", "replay", "register", "quick_prepare"}:
        raise fastapi.HTTPException(status_code=400, detail="지원하지 않는 작업입니다.")
    if kind == "replay" and (BASE / "reports/replay_paused.json").exists():
        raise fastapi.HTTPException(status_code=409, detail="과거 비교 실행은 오류 점검 중입니다.")
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 검사가 끝난 뒤 다시 실행해 주세요.")
    try:
        job_id = f"{time.time_ns()}_{uuid.uuid4().hex[:8]}"
        folder = JOBS / job_id
        folder.mkdir(parents=True, exist_ok=False)
        req_payload = payload if isinstance(payload, dict) else None
        record = {"id": job_id, "job": kind, "status": "RUNNING", "started_at": time.time()}
        if req_payload is not None:
            record["request"] = req_payload
        if kind == "quick_prepare":
            record["progress"] = {
                "stage": "hash",
                "stage_index": 1,
                "stage_total": 4,
                "percent": 2.0,
                "rows_scanned": 0,
                "elapsed_seconds": 0.0,
            }
        write_json(folder / "job.json", record)
        active_job = job_id
        active_job_record = _snapshot_job_record(record)
        threading.Thread(target=execute_job, args=(kind, folder, req_payload), daemon=False).start()
        return record
    except Exception:
        active_job = None
        active_job_record = None
        LOCK.release()
        raise


@app.post("/api/candidates/train")
def start_candidate_train(payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
    global active_job, active_job_record
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 실행 버튼을 눌러 주세요.")
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 진행 중인 작업이 끝난 뒤 다시 실행해 주세요.")
    try:
        job_id = f"{time.time_ns()}_{uuid.uuid4().hex[:8]}"
        folder = JOBS / job_id
        folder.mkdir(parents=True, exist_ok=False)
        epochs_req = int((payload or {}).get("epochs", DEFAULT_EPOCHS) or DEFAULT_EPOCHS)
        record = {
            "id": job_id,
            "job": "candidate_train",
            "status": "RUNNING",
            "started_at": time.time(),
            "request": payload,
            "progress": {
                "stage": "worker_start",
                "stage_index": 1,
                "stage_total": 5,
                "percent": 3.0,
                "epoch": 0,
                "epochs_total": epochs_req,
                "elapsed_seconds": 0.0,
                "message": "TensorFlow 워커 프로세스 준비 중",
            },
        }
        write_json(folder / "job.json", record)
        active_job = job_id
        active_job_record = _snapshot_job_record(record)
        threading.Thread(target=execute_job, args=("candidate_train", folder, payload), daemon=False).start()
        return record
    except Exception:
        active_job = None
        active_job_record = None
        LOCK.release()
        raise


@app.get("/api/candidates")
def get_candidates():
    return lifecycle.list_candidate_runs(store=STORE)


@app.get("/api/candidates/{run_id}/series")
def get_candidate_series(run_id: str):
    if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    path = lifecycle.CANDIDATE_RUNS_ROOT / run_id / "series_comparison.json"
    if not path.is_file():
        return {"available": False, "message": "시계열 비교 그래프 파일이 없습니다."}
    return {"available": True, **duel_series(read_json(path))}


@app.get("/api/v2/simulations")
def get_v2_simulations(candidate_run_id: str = "", evaluated_snapshot_id: str = "",
                       scope: str = "", current_only: bool = False):
    if candidate_run_id and not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", candidate_run_id):
        raise fastapi.HTTPException(status_code=400, detail="후보 실행 ID 형식이 올바르지 않습니다.")
    simulations = lifecycle.list_local_qc_simulations(candidate_run_id=candidate_run_id or None)
    if evaluated_snapshot_id:
        simulations = [item for item in simulations if item.get("evaluated_snapshot_id") == evaluated_snapshot_id]
    if scope:
        simulations = [item for item in simulations if str(item.get("scope") or "").upper() == scope.upper()]
    if current_only:
        simulations = [item for item in simulations if item.get("policy_current") and item.get("bundle_current")
                       and item.get("evaluation_scope_current") is True]
    return {"policy_version": lifecycle.TIERED_PROMOTION_POLICY, "simulations": simulations, "count": len(simulations)}


@app.get("/api/v2/simulations/{simulation_id}")
def get_v2_simulation(simulation_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", simulation_id):
        raise fastapi.HTTPException(status_code=400, detail="시뮬레이션 ID 형식이 올바르지 않습니다.")
    target = next((item for item in lifecycle.list_local_qc_simulations()
                   if item.get("simulation_id") == simulation_id), None)
    if target is None:
        raise fastapi.HTTPException(status_code=404, detail="로컬 QC 시뮬레이션을 찾을 수 없습니다.")
    try:
        return lifecycle.get_local_qc_simulation(target["candidate_run_id"], simulation_id=simulation_id)
    except (ValueError, OSError) as exc:
        raise fastapi.HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v2/simulations/{simulation_id}/series")
def get_v2_simulation_series(simulation_id: str):
    detail = get_v2_simulation(simulation_id)
    try:
        return lifecycle.get_local_qc_simulation_series(detail["candidate_run_id"], simulation_id=simulation_id)
    except (ValueError, OSError) as exc:
        raise fastapi.HTTPException(status_code=409, detail=str(exc)) from exc

@app.get("/api/candidates/{run_id}/local_qc")
def get_candidate_local_qc(run_id: str, simulation_id: str = ""):
    if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    if not (lifecycle.CANDIDATE_RUNS_ROOT / run_id / "artifact.json").is_file():
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    return lifecycle.get_local_qc_simulation(
        run_id,
        simulation_id=simulation_id.strip() or None,
    )


@app.get("/api/candidates/{run_id}/local_qc/series")
def get_candidate_local_qc_series(run_id: str, simulation_id: str = ""):
    if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    if not (lifecycle.CANDIDATE_RUNS_ROOT / run_id / "artifact.json").is_file():
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    return lifecycle.get_local_qc_simulation_series(
        run_id,
        simulation_id=simulation_id.strip() or None,
    )


@app.post("/api/candidates/{run_id}/local_qc/simulate")
def start_candidate_local_qc_simulation(
    run_id: str,
    payload: dict | None = fastapi.Body(default=None),
    x_dashboard_token: str = fastapi.Header(default=""),
):
    global active_job, active_job_record
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 실행 버튼을 눌러 주세요.")
    if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    artifact_path = lifecycle.CANDIDATE_RUNS_ROOT / run_id / "artifact.json"
    if not artifact_path.is_file():
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    req = dict(payload or {})
    scope = str(req.get("scope") or "TEST").strip().upper()
    if scope not in {"TRAIN", "VALIDATION", "TEST", "ALL"}:
        raise fastapi.HTTPException(status_code=400, detail="시뮬레이션 범위는 TRAIN, VALIDATION, TEST, ALL 중 하나여야 합니다.")
    snapshot_id = str(req.get("snapshot_id") or "").strip() or None
    simulation_id = str(req.get("simulation_id") or "").strip() or None
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 진행 중인 작업이 끝난 뒤 다시 실행해 주세요.")
    try:
        job_id = f"{time.time_ns()}_{uuid.uuid4().hex[:8]}"
        folder = JOBS / job_id
        folder.mkdir(parents=True, exist_ok=False)
        job_payload = {
            "run_id": run_id,
            "snapshot_id": snapshot_id,
            "scope": scope,
            "simulation_id": simulation_id,
        }
        record = {
            "id": job_id,
            "job": "local_qc_simulate",
            "status": "RUNNING",
            "started_at": time.time(),
            "candidate_run_id": run_id,
            "request": job_payload,
            "progress": {
                "stage": "starting",
                "stage_index": 1,
                "stage_total": 2,
                "percent": 5.0,
                "elapsed_seconds": 0.0,
                "message": f"2-Tier 로컬 전체 QC 시뮬레이션 준비 중 ({run_id})",
            },
        }
        write_json(folder / "job.json", record)
        active_job = job_id
        active_job_record = _snapshot_job_record(record)
        threading.Thread(target=execute_job, args=("local_qc_simulate", folder, job_payload), daemon=False).start()
        return record
    except Exception:
        active_job = None
        active_job_record = None
        LOCK.release()
        raise


@app.post("/api/candidates/{run_id}/replay")
def verify_candidate_replay(run_id: str, x_dashboard_token: str = fastapi.Header(default="")):
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 실행 버튼을 눌러 주세요.")
    if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 진행 중인 작업이 끝난 뒤 다시 실행해 주세요.")
    try:
        return lifecycle.run_candidate_replay_subprocess(run_id, manifest_path=MANIFEST, tf_python=PYTHON)
    except (ValueError, RuntimeError) as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        LOCK.release()


@app.post("/api/candidates/{run_id}/evaluate")
def evaluate_candidate_on_snapshot(run_id: str, payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 실행 버튼을 눌러 주세요.")
    if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 진행 중인 작업이 끝난 뒤 다시 실행해 주세요.")
    try:
        artifact_path = lifecycle.CANDIDATE_RUNS_ROOT / run_id / "artifact.json"
        if not artifact_path.is_file():
            raise ValueError("후보 실행 기록을 찾을 수 없습니다.")
        artifact = read_json(artifact_path)
        station, sensor = artifact["station"], artifact["sensor"]
        for key, expected in (("station", station), ("sensor", sensor)):
            if key in payload and payload[key] != expected:
                raise ValueError("후보 모델과 평가 자료의 관측소·센서가 다릅니다.")
        kinds = [bool(payload.get("eval_snapshot_id")), "ym" in payload, "selected_yms" in payload,
                 "date_start" in payload or "date_end" in payload]
        if sum(kinds) != 1:
            raise ValueError("eval_snapshot_id, ym, selected_yms, 날짜 범위 중 하나만 지정해 주세요.")
        eval_scope = str(payload.get("eval_scope") or ("AUTO" if kinds[0] else "ALL")).strip().upper()
        if eval_scope not in {"AUTO", "TRAIN", "VALIDATION", "TEST", "ALL"}:
            raise ValueError("평가 범위가 올바르지 않습니다.")
        snapshots = ParquetSnapshotAuthority().list_snapshots()
        selected_yms = []
        if kinds[0]:
            eval_snap_id = str(payload["eval_snapshot_id"]).strip()
            target = next((item for item in snapshots if item["snapshot_id"] == eval_snap_id), None)
            if target is None:
                raise ValueError("평가할 스냅샷을 찾을 수 없습니다.")
            if target["station"] != station or target["sensor"] != sensor:
                raise ValueError("후보 모델과 평가 자료의 관측소·센서가 다릅니다.")
            date_start, date_end = target["date_start"], target["date_end"]
            selected_yms = target.get("selected_yms") or lifecycle._period_months(date_start, date_end)
        else:
            if kinds[1] or kinds[2]:
                raw_months = [payload["ym"]] if kinds[1] else payload["selected_yms"]
                if not isinstance(raw_months, list) or not raw_months:
                    raise ValueError("평가할 연·월을 하나 이상 선택해 주세요.")
                for value in raw_months:
                    if not isinstance(value, str) or not re.fullmatch(r"\d{6}", value):
                        raise ValueError("연·월은 YYYYMM 형식이어야 합니다.")
                    datetime.strptime(value, "%Y%m")
                selected_yms = sorted(set(raw_months))
                date_start = f"{selected_yms[0][:4]}-{selected_yms[0][4:]}-01"
                date_end = preview._last_day_of_ym(selected_yms[-1])
            else:
                date_start, date_end = str(payload.get("date_start") or ""), str(payload.get("date_end") or "")
                first = datetime.strptime(str(date_start), "%Y-%m-%d")
                last = datetime.strptime(str(date_end), "%Y-%m-%d")
                if first > last or (last - first).days > 366 * 5:
                    raise ValueError("평가 기간은 시작일 이상, 최대 5년으로 선택해 주세요.")
                selected_yms = lifecycle._period_months(date_start, date_end)
            target = next((item for item in snapshots
                           if item["station"] == station and item["sensor"] == sensor
                           and item["date_start"] == date_start and item["date_end"] == date_end
                           and sorted(item.get("selected_yms") or lifecycle._period_months(item["date_start"], item["date_end"])) == selected_yms), None)
            eval_snap_id = target["snapshot_id"] if target else None
        periods = lifecycle.candidate_training_periods(artifact)
        excluded = set(periods["training_yms"]) | set(periods["calibration_yms"])
        restore_internal_test = bool(kinds[0]) and eval_snap_id == artifact["snapshot_id"] and eval_scope in {"TEST", "AUTO"}
        if set(selected_yms) & excluded and not restore_internal_test:
            raise ValueError("평가 기간이 학습 또는 임계값 탐색에 사용한 달과 겹칩니다.")
        if eval_snap_id is None:
            # quick_prepare_snapshot shares this internal helper; no nested LOCK acquisition.
            prepared = _quick_prepare_snapshot_unlocked({
                "station": station, "sensor": sensor, "date_start": date_start,
                "date_end": date_end, "selected_yms": selected_yms,
            })
            eval_snap_id = prepared["snapshot"]["snapshot_id"]
        return lifecycle.run_candidate_evaluation_subprocess(
            run_id=run_id, eval_snapshot_id=eval_snap_id, eval_scope=eval_scope,
            manifest_path=MANIFEST, tf_python=PYTHON,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        LOCK.release()


@app.post("/api/candidates/{run_id}/promote")
def promote_candidate(run_id: str, payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 승인 버튼을 눌러 주세요.")
    if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
        raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 진행 중인 작업이 끝난 뒤 다시 실행해 주세요.")
    try:
        return lifecycle.promote_candidate_to_champion(
            run_id=run_id,
            approved_by=str(payload.get("approved_by", "")),
            reason=str(payload.get("reason", "")),
            store=STORE,
            manifest_path=MANIFEST,
        )
    except ValueError as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        LOCK.release()


@app.post("/api/deployments/rollback")
def rollback_deployment(payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 롤백 버튼을 눌러 주세요.")
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 진행 중인 작업이 끝난 뒤 다시 실행해 주세요.")
    try:
        return lifecycle.rollback_champion(
            station=str(payload.get("station", "")),
            sensor=str(payload.get("sensor", "")),
            approved_by=str(payload.get("approved_by", "")),
            reason=str(payload.get("reason", "")),
            store=STORE,
            manifest_path=MANIFEST,
        )
    except ValueError as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        LOCK.release()


@app.get("/api/deployments/active")
def get_active_deployment():
    return lifecycle.active_release_state()


@app.get("/api/deployments/resolve/{station}/{sensor}")
def resolve_active_bundle(station: str, sensor: str, verify_hash: bool = True):
    try:
        return resolve_runtime_bundle(station=station, sensor=sensor, verify_hash=verify_hash)
    except (ValueError, OSError) as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/pipeline/recommend_test_months")
def get_recommended_test_months(station: str = "", sensor: str = "", exclude_yms: str = "", run_id: str = ""):
    excl = [x.strip() for x in exclude_yms.split(",") if x.strip()] if exclude_yms else []
    if run_id:
        if not re.fullmatch(r"\d{8}T\d{6}Z_[0-9a-f]{8}", run_id):
            raise fastapi.HTTPException(status_code=400, detail="후보 실행 ID가 올바르지 않습니다.")
        path = lifecycle.CANDIDATE_RUNS_ROOT / run_id / "artifact.json"
        if not path.is_file():
            raise fastapi.HTTPException(status_code=404, detail="후보 실행 기록을 찾을 수 없습니다.")
        artifact = read_json(path)
        if (station and station != artifact["station"]) or (sensor and sensor != artifact["sensor"]):
            raise fastapi.HTTPException(status_code=400, detail="후보 모델의 관측소·센서와 다릅니다.")
        station, sensor = artifact["station"], artifact["sensor"]
        periods = lifecycle.candidate_training_periods(artifact)
        excl += periods["training_yms"] + periods["calibration_yms"]
    return preview.recommend_test_months(station=station, sensor=sensor, exclude_yms=excl)


@app.post("/api/pipeline/month_index")
def start_month_index(payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
    global active_job, active_job_record
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 실행 버튼을 눌러 주세요.")
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 진행 중인 작업이 끝난 뒤 다시 실행해 주세요.")
    try:
        job_id = f"{time.time_ns()}_{uuid.uuid4().hex[:8]}"
        folder = JOBS / job_id
        folder.mkdir(parents=True, exist_ok=False)
        record = {
            "id": job_id,
            "job": "month_index",
            "status": "RUNNING",
            "started_at": time.time(),
            "request": payload,
            "progress": {
                "stage": "month_index",
                "percent": 2.0,
                "elapsed_seconds": 0.0,
            },
        }
        write_json(folder / "job.json", record)
        active_job = job_id
        active_job_record = _snapshot_job_record(record)
        threading.Thread(target=execute_job, args=("month_index", folder, payload), daemon=False).start()
        return record
    except Exception:
        active_job = None
        active_job_record = None
        LOCK.release()
        raise


def _monthly_file_priority(path: str, kind: str) -> tuple[int, str]:
    """Rank monthly CSV names without accessing the referenced filesystem."""
    normalized = str(path).replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    if kind == "observation":
        rank = 0 if "/정형데이터/gd_obs_st/" in normalized else 1 if name.startswith("gd_obs_st_") else 2
    elif "/정형데이터/go_tide_pre_data/" in normalized:
        rank = 0
    elif name.startswith("pred_"):
        rank = 5
    elif "/20261021_greenblue/" in normalized:
        rank = 1
    elif "/261008_gb_temp/" in normalized:
        rank = 2
    elif "/go_tide_pre_data_utf8/" in normalized:
        rank = 3
    else:
        rank = 4
    return rank, normalized


def _quick_prepare_snapshot_unlocked(payload: dict, progress=None) -> dict:
    """Prepare CSV data and a snapshot while the caller holds the operation lock."""
    ratios = payload.get("split_ratios", [0.70, 0.15, 0.15])
    if not isinstance(ratios, (list, tuple)) or len(ratios) != 3:
        raise ValueError("split_ratios는 [train, validation, test] 3개 비율이어야 합니다.")
    try:
        ratio_tuple = (float(ratios[0]), float(ratios[1]), float(ratios[2]))
    except (TypeError, ValueError) as exc:
        raise ValueError("split_ratios는 숫자형 3개 비율이어야 합니다.") from exc

    mode = str(payload.get("mode", "paired")).strip() or "paired"
    station = str(payload.get("station", "")).strip()
    sensor = str(payload.get("sensor", "")).strip()
    date_start = str(payload.get("date_start", "2024-01-01")).strip()
    date_end = str(payload.get("date_end", "2024-01-31")).strip()
    obs_paths = list(payload.get("observation_paths") or [])
    prd_paths = list(payload.get("prediction_paths") or [])
    raw_selected_yms = payload.get("selected_yms") or []
    selected_yms = sorted({
        re.sub(r"[^0-9]", "", str(x))[:6]
        for x in raw_selected_yms
        if len(re.sub(r"[^0-9]", "", str(x))) >= 6
    })
    if selected_yms:
        if not payload.get("date_start"):
            date_start = f"{selected_yms[0][:4]}-{selected_yms[0][4:6]}-01"
        if not payload.get("date_end"):
            date_end = preview._last_day_of_ym(selected_yms[-1])

    if not obs_paths or not prd_paths:
        cat_files = preview.catalog()["files"]
        ym_start = date_start[:7].replace("-", "")
        ym_end = date_end[:7].replace("-", "")
        ym_filter_set = set(selected_yms) if selected_yms else None
        obs_by_ym: dict[str, str] = {}
        prd_by_ym: dict[str, str] = {}
        for item in cat_files:
            fname = Path(item["path"]).name.lower()
            m_obs = re.fullmatch(r"(?:gd_obs_st_|data_)(\d{6})\.csv", fname)
            if m_obs:
                ym_val = m_obs.group(1)
                if (ym_filter_set is not None and ym_val in ym_filter_set) or (ym_filter_set is None and ym_start <= ym_val <= ym_end):
                    if ym_val not in obs_by_ym or _monthly_file_priority(item["path"], "observation") < _monthly_file_priority(obs_by_ym[ym_val], "observation"):
                        obs_by_ym[ym_val] = item["path"]
            m_prd = re.fullmatch(r"(pred_|go_tide_pre_data_)(\d{6})\.csv", fname)
            if m_prd:
                ym_key = m_prd.group(2)
                if (ym_filter_set is not None and ym_key in ym_filter_set) or (ym_filter_set is None and ym_start <= ym_key <= ym_end):
                    if ym_key not in prd_by_ym or _monthly_file_priority(item["path"], "prediction") < _monthly_file_priority(prd_by_ym[ym_key], "prediction"):
                        prd_by_ym[ym_key] = item["path"]
        if mode == "paired" and not obs_paths and not prd_paths:
            common_yms = sorted(set(obs_by_ym) & set(prd_by_ym))
            matched_obs = [obs_by_ym[k] for k in common_yms]
            matched_prd = [prd_by_ym[k] for k in common_yms]
            if common_yms:
                if not selected_yms or set(obs_by_ym) != set(prd_by_ym):
                    selected_yms = common_yms
                if set(obs_by_ym) != set(prd_by_ym):
                    date_start = max(date_start, f"{common_yms[0][:4]}-{common_yms[0][4:6]}-01")
                    date_end = min(date_end, preview._last_day_of_ym(common_yms[-1]))
        else:
            matched_obs = [obs_by_ym[k] for k in sorted(obs_by_ym)]
            matched_prd = [prd_by_ym[k] for k in sorted(prd_by_ym)]
        if not matched_obs and ym_start <= "202212" and ym_end >= "202001":
            for item in cat_files:
                if item["path"].endswith("GD_OBS_ST_2020_2022_ALL_DT.csv"):
                    matched_obs.append(item["path"])
                elif item["path"].endswith("GO_TIDE_PRE_DATA_2020_2022_ALL_DT.csv"):
                    matched_prd.append(item["path"])
        if mode == "paired" and not obs_paths and not prd_paths and (not matched_obs or not matched_prd):
            if obs_by_ym and not prd_by_ym:
                obs_sorted = sorted(obs_by_ym)
                raise ValueError(
                    f"선택한 기간({date_start} ~ {date_end})에는 조위 예측 CSV(GO_TIDE_PRE_DATA_YYYYMM.csv)가 없어 "
                    f"관측+예측 짝 스냅샷을 준비할 수 없습니다. "
                    f"(관측만 존재하는 연월: {obs_sorted[0]}~{obs_sorted[-1]}, 표준 자료 범위 2023-01~2026-07의 예측 경로를 확인해 주세요.)"
                )
            if prd_by_ym and not obs_by_ym:
                prd_sorted = sorted(prd_by_ym)
                raise ValueError(
                    f"선택한 기간({date_start} ~ {date_end})에는 관측 CSV(GD_OBS_ST_YYYYMM.csv 또는 data_YYYYMM.csv)가 없어 "
                    f"관측+예측 짝 스냅샷을 준비할 수 없습니다. (예측만 존재하는 연월: {prd_sorted[0]}~{prd_sorted[-1]})"
                )
            if obs_by_ym and prd_by_ym:
                raise ValueError(
                    f"선택한 기간({date_start} ~ {date_end})에서 관측 CSV와 예측 CSV가 동시에 존재하는 연월(YYYYMM)이 없습니다."
                )
        if not obs_paths:
            obs_paths = matched_obs
        if not prd_paths:
            prd_paths = matched_prd
    if mode == "paired" and (obs_paths or prd_paths):
        exp_obs_by_ym: dict[str, str] = {}
        exp_prd_by_ym: dict[str, str] = {}
        all_monthly = True
        for p in obs_paths:
            m_obs = re.fullmatch(r"(?:gd_obs_st_|data_)(\d{6})\.csv", Path(str(p)).name.lower())
            if not m_obs:
                all_monthly = False
                break
            ym_k = m_obs.group(1)
            if ym_k not in exp_obs_by_ym or _monthly_file_priority(str(p), "observation") < _monthly_file_priority(exp_obs_by_ym[ym_k], "observation"):
                exp_obs_by_ym[ym_k] = str(p)
        if all_monthly:
            for p in prd_paths:
                m_prd = re.fullmatch(r"(pred_|go_tide_pre_data_)(\d{6})\.csv", Path(str(p)).name.lower())
                if not m_prd:
                    all_monthly = False
                    break
                ym_k = m_prd.group(2)
                if ym_k not in exp_prd_by_ym or _monthly_file_priority(str(p), "prediction") < _monthly_file_priority(exp_prd_by_ym[ym_k], "prediction"):
                    exp_prd_by_ym[ym_k] = str(p)
        if all_monthly:
            common_yms = sorted(set(exp_obs_by_ym) & set(exp_prd_by_ym))
            if set(exp_obs_by_ym) != set(exp_prd_by_ym):
                if not common_yms:
                    if exp_obs_by_ym and not exp_prd_by_ym:
                        obs_sorted = sorted(exp_obs_by_ym)
                        raise ValueError(
                            f"선택한 기간({date_start} ~ {date_end})에는 조위 예측 CSV(GO_TIDE_PRE_DATA_YYYYMM.csv)가 없어 "
                            f"관측+예측 짝 스냅샷을 준비할 수 없습니다. "
                            f"(관측만 존재하는 연월: {obs_sorted[0]}~{obs_sorted[-1]}, 표준 자료 범위 2023-01~2026-07의 예측 경로를 확인해 주세요.)"
                        )
                    if exp_prd_by_ym and not exp_obs_by_ym:
                        prd_sorted = sorted(exp_prd_by_ym)
                        raise ValueError(
                            f"선택한 기간({date_start} ~ {date_end})에는 관측 CSV(GD_OBS_ST_YYYYMM.csv 또는 data_YYYYMM.csv)가 없어 "
                            f"관측+예측 짝 스냅샷을 준비할 수 없습니다. (예측만 존재하는 연월: {prd_sorted[0]}~{prd_sorted[-1]})"
                        )
                    raise ValueError(
                        f"선택한 기간({date_start} ~ {date_end})에서 관측 CSV와 예측 CSV가 동시에 존재하는 연월(YYYYMM)이 없습니다."
                    )
                obs_paths = [exp_obs_by_ym[k] for k in common_yms]
                prd_paths = [exp_prd_by_ym[k] for k in common_yms]
                selected_yms = common_yms
                date_start = max(date_start, f"{common_yms[0][:4]}-{common_yms[0][4:6]}-01")
                date_end = min(date_end, preview._last_day_of_ym(common_yms[-1]))
            elif not selected_yms and common_yms:
                selected_yms = common_yms
            obs_paths = [exp_obs_by_ym[k] for k in common_yms]
            prd_paths = [exp_prd_by_ym[k] for k in common_yms]

    col_norm = payload.get("column_normalization")
    time_align = payload.get("time_alignment")
    if obs_paths and (not col_norm or not time_align):
        prof = preview.profile(obs_paths[0], payload.get("encoding", "utf-8-sig"), "strict")
        if prof.get("sqlplus_gd_obs_st_detected"):
            col_norm = col_norm or "sqlplus_gd_obs_st"
            time_align = time_align or "minute_floor"
        # Header cleanup leaves the monthly export's original seconds intact.
        # Keep its minute alignment when options are omitted, including aliases.
        if re.fullmatch(r"(?:gd_obs_st_|data_)\d{6}\.csv", Path(obs_paths[0]).name, re.I):
            time_align = time_align or "minute_floor"

    analyze_req = {
        "mode": mode,
        "station": station,
        "sensor": sensor,
        "date_start": date_start,
        "date_end": date_end,
        "observation_paths": obs_paths,
        "prediction_paths": prd_paths,
        "encoding": payload.get("encoding", "utf-8-sig"),
        "column_normalization": col_norm or "strict",
        "time_alignment": time_align or "exact_minute",
    }
    ds_res = preview.analyze(analyze_req, progress) if progress is not None else preview.analyze(analyze_req)
    ds_res["selected_yms"] = selected_yms
    dataset_manifest_path = preview.OUTPUT / ds_res["dataset_id"] / "dataset_manifest.json"
    if dataset_manifest_path.is_file():
        write_json(dataset_manifest_path, ds_res)
    if progress is not None:
        total_files = len(obs_paths) + len(prd_paths)
        total_rows = int((ds_res.get("observation") or {}).get("rows_scanned", 0)) + int((ds_res.get("prediction") or {}).get("rows_scanned", 0))
        progress({
            "stage": "building_snapshot",
            "stage_index": 4,
            "stage_total": 4,
            "percent": 94.0,
            "file": "snapshot.parquet",
            "file_index": total_files,
            "total_files": total_files,
            "stage_file_index": total_files,
            "stage_total_files": total_files,
            "rows_scanned": total_rows,
            "dataset_id": ds_res["dataset_id"],
            "valid_minutes": ds_res.get("valid_minutes", 0),
        })
    try:
        snap_res = ParquetSnapshotAuthority(preview_output=preview.OUTPUT).build_from_dataset(
            ds_res["dataset_id"],
            split_ratios=ratio_tuple,
            split_policy=payload.get("split_policy", CHRONOLOGICAL_SPLIT_POLICY),
        )
    except Exception:
        if ds_res.get("valid_minutes", 0) < 30:
            import shutil
            shutil.rmtree(preview.OUTPUT / ds_res["dataset_id"], ignore_errors=True)
        raise
    snap_res["selected_yms"] = selected_yms
    if snap_res.get("parquet", {}).get("path"):
        snapshot_path = Path(snap_res["parquet"]["path"]).parent / "snapshot_manifest.json"
        write_json(snapshot_path, snap_res)
    return {
        "dataset": ds_res,
        "snapshot": snap_res,
        "matched_observation_paths": obs_paths,
        "matched_prediction_paths": prd_paths,
        "selected_yms": selected_yms,
    }


@app.post("/api/pipeline/quick_prepare")
def quick_prepare_snapshot(payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
    if not secrets.compare_digest(x_dashboard_token, TOKEN):
        raise fastapi.HTTPException(status_code=403, detail="이 화면에서 실행 버튼을 눌러 주세요.")
    if not LOCK.acquire(blocking=False):
        raise fastapi.HTTPException(status_code=409, detail="현재 진행 중인 작업이 끝난 뒤 다시 실행해 주세요.")
    try:
        return _quick_prepare_snapshot_unlocked(payload)
    except (ValueError, OSError) as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        LOCK.release()


@app.get("/api/series/{run_id}/{station}/{sensor}")
def series(run_id: str, station: str, sensor: str):
    allowed_runs = {p.parent.name for p in RUNS.glob("*/run.json")}
    allowed_pairs = {(p["station"], p["sensor"]) for p in read_json(MANIFEST)["models"]}
    if run_id not in allowed_runs or (station, sensor) not in allowed_pairs:
        raise fastapi.HTTPException(status_code=404, detail="비교 자료를 찾을 수 없습니다.")
    path = RUNS / run_id / "replay_inputs" / f"{station}_{sensor}.json"
    if not path.exists():
        return {"available": False, "message": "이 기록에는 그래프 자료가 없습니다. 과거 결과 비교를 다시 실행해 주세요."}
    return {"available": True, **read_json(path)}


@app.get("/api/ocean_ai/status")
def ocean_ai_status():
    return get_ocean_ai_bridge_status()


@app.get("/api/ocean_ai/export_bundle")
def ocean_ai_export_bundle(snapshot_id: str = "", run_id: str = ""):
    snap_ids = [s.strip() for s in snapshot_id.split(",") if s.strip()] if snapshot_id else None
    run_ids = [r.strip() for r in run_id.split(",") if r.strip()] if run_id else None
    try:
        return export_ocean_ai_bundle(snapshot_ids=snap_ids, candidate_run_ids=run_ids)
    except ValueError as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ocean_ai/sync")
def ocean_ai_sync(
    payload: dict = fastapi.Body(default={}),
    x_dashboard_token: str = fastapi.Header(default=""),
    x_local_token: str = fastapi.Header(default=""),
    x_ocean_ai_bridge_token: str = fastapi.Header(default=""),
    authorization: str = fastapi.Header(default=""),
):
    if not _verify_dashboard_or_bridge_token(
        x_dashboard_token=x_dashboard_token,
        x_local_token=x_local_token,
        x_ocean_ai_bridge_token=x_ocean_ai_bridge_token,
        authorization=authorization,
    ):
        raise fastapi.HTTPException(status_code=403, detail="유효한 Ocean-AI 브리지 토큰 또는 로컬 토큰이 필요합니다.")
    snap_ids = payload.get("snapshot_ids") if isinstance(payload, dict) else None
    run_ids = payload.get("candidate_run_ids") if isinstance(payload, dict) else None
    db_url = payload.get("database_url") if isinstance(payload, dict) else None
    try:
        return sync_to_ocean_ai_db(
            database_url=str(db_url) if db_url else None,
            snapshot_ids=list(snap_ids) if isinstance(snap_ids, list) else None,
            candidate_run_ids=list(run_ids) if isinstance(run_ids, list) else None,
        )
    except ValueError as exc:
        raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the local AI-QC MLOps trial workbench server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    host = str(args.host or "127.0.0.1").strip()
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("로컬 워크벤치 서버는 루프백 주소(127.0.0.1 또는 localhost)에서만 실행할 수 있습니다.")
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run(app, host=host, port=args.port, workers=1)


if __name__ == "__main__":
    main()


