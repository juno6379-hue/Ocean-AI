"""HTTP controls for the independent local CSV inspector."""
import contextlib
import csv
import importlib
import json
import re
import secrets
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

_BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(_BASE), str(_BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("dataset_routes", sys.modules[__name__])
sys.modules.setdefault("scripts.dataset_routes", sys.modules[__name__])

import scripts.dataset_preview as preview
from scripts.local_trial_manifest import _JSON_LOCK, _is_retryable_permission_error, read_json
from scripts.ocean_ai_snapshot import CHRONOLOGICAL_SPLIT_POLICY, ParquetSnapshotAuthority

fastapi: Any = importlib.import_module("fastapi")
responses: Any = importlib.import_module("fastapi.responses")
JOBS = preview.BASE / "reports/dataset_jobs"
active_job_id: str | None = None
active_job_record: dict[str, Any] | None = None


def _snapshot_job_record(record: dict[str, Any]) -> dict[str, Any]:
    with _JSON_LOCK:
        copied = dict(record)
        if isinstance(copied.get("progress"), dict):
            copied["progress"] = dict(copied["progress"])
        return copied


def write_record(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tid = threading.get_ident()
    temporary = path.with_name(f"{path.name}.part.{tid}.{uuid.uuid4().hex[:8]}")
    payload = json.dumps(record, ensure_ascii=False, indent=2)
    try:
        with _JSON_LOCK:
            temporary.write_text(payload, encoding="utf-8")
        deadline = time.monotonic() + 3.0
        while True:
            try:
                with _JSON_LOCK:
                    temporary.replace(path)
                return
            except OSError as exc:
                # A Windows reader can briefly deny replacement of our own job.json.
                # Never release another process's lock or hide a persistent error.
                if not _is_retryable_permission_error(exc) or time.monotonic() >= deadline:
                    raise
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    finally:
        with contextlib.suppress(OSError):
            temporary.unlink(missing_ok=True)


def register_routes(app, token, lock):
    def authorized(supplied):
        if not secrets.compare_digest(supplied, token):
            raise fastapi.HTTPException(status_code=403, detail="자료 검사 화면에서 버튼을 눌러 주세요.")

    @app.get("/data")
    def data_page():
        html = (preview.BASE / "ui/data_preview.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
        return responses.HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/api/data/catalog")
    def data_catalog():
        return preview.catalog()

    @app.post("/api/data/profile")
    def data_profile(payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
        authorized(x_dashboard_token)
        try:
            return preview.profile(
                payload.get("path"),
                payload.get("encoding", "utf-8-sig"),
                payload.get("column_normalization", "strict"),
            )
        except (ValueError, OSError, UnicodeError, csv.Error) as exc:
            raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/data/analyze")
    def data_analyze(payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
        global active_job_id, active_job_record
        authorized(x_dashboard_token)
        if not lock.acquire(blocking=False):
            raise fastapi.HTTPException(status_code=409, detail="진행 중인 검사가 끝난 뒤 실행해 주세요.")
        job_id = uuid.uuid4().hex
        folder = JOBS / job_id
        try:
            folder.mkdir(parents=True, exist_ok=False)
            started_at = time.time()
            record: dict[str, Any] = {
                "job_id": job_id,
                "status": "RUNNING",
                "started_at": started_at,
                "request": payload,
                "progress": {
                    "stage": "hash",
                    "stage_index": 1,
                    "stage_total": 4,
                    "percent": 2.0,
                    "rows_scanned": 0,
                    "elapsed_seconds": 0.0,
                },
            }
            write_record(folder / "job.json", record)
            active_job_id = job_id
            active_job_record = _snapshot_job_record(record)

            def worker():
                global active_job_id, active_job_record
                last_flush = 0.0
                last_key: tuple[Any, ...] | None = None
                try:
                    def progress(value):
                        global active_job_record
                        nonlocal last_flush, last_key
                        enriched: dict[str, Any] = dict(value) if isinstance(value, dict) else {"stage": str(value)}
                        if "elapsed_seconds" not in enriched:
                            enriched["elapsed_seconds"] = round(max(0.0, time.time() - started_at), 1)
                        with _JSON_LOCK:
                            record["progress"] = enriched
                            active_job_record = _snapshot_job_record(record)
                        now = time.monotonic()
                        cur_key = (enriched.get("stage"), enriched.get("file"), enriched.get("file_index"))
                        if cur_key != last_key or (now - last_flush) >= 0.25:
                            last_key = cur_key
                            last_flush = now
                            try:
                                write_record(folder / "job.json", record)
                            except OSError:
                                pass
                    result = preview.analyze(payload, progress)
                    elapsed = round(max(0.0, time.time() - started_at), 1)
                    prev_prog: dict[str, Any] = dict(record.get("progress") or {})
                    prev_prog.update({
                        "stage": "finished",
                        "stage_index": 4,
                        "stage_total": 4,
                        "percent": 100.0,
                        "elapsed_seconds": elapsed,
                    })
                    with _JSON_LOCK:
                        record.update({
                            "status": "FINISHED",
                            "dataset_id": result["dataset_id"],
                            "progress": prev_prog,
                            "elapsed_seconds": elapsed,
                        })
                        active_job_record = _snapshot_job_record(record)
                except Exception as exc:
                    elapsed = round(max(0.0, time.time() - started_at), 1)
                    prev_prog = dict(record.get("progress") or {})
                    prev_prog["elapsed_seconds"] = elapsed
                    with _JSON_LOCK:
                        record.update({
                            "status": "FAILED",
                            "error": str(exc),
                            "progress": prev_prog,
                            "elapsed_seconds": elapsed,
                        })
                        active_job_record = _snapshot_job_record(record)
                    (folder / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
                finally:
                    try:
                        with _JSON_LOCK:
                            record["finished_at"] = time.time()
                        write_record(folder / "job.json", record)
                    finally:
                        active_job_id = None
                        active_job_record = None
                        lock.release()
            threading.Thread(target=worker, daemon=False).start()
            return {"job_id": job_id, "status": "RUNNING"}
        except Exception:
            active_job_id = None
            active_job_record = None
            lock.release()
            raise

    @app.get("/api/data/jobs")
    def data_jobs():
        items: list[dict[str, Any]] = []
        is_busy = lock.locked()
        current_active_id = active_job_id if is_busy else None
        if JOBS.exists():
            paths = sorted(JOBS.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
            for p in paths:
                try:
                    rec = read_json(p)
                    if not isinstance(rec, dict):
                        continue
                    if is_busy and rec.get("job_id") == current_active_id and isinstance(active_job_record, dict):
                        rec = _snapshot_job_record(active_job_record)
                    if rec.get("status") == "RUNNING" and not (is_busy and rec.get("job_id") == current_active_id):
                        rec["status"] = "FAILED"
                        rec["orphaned"] = True
                        rec.setdefault("error", "이전 실행이 중단되어 완료 기록이 없습니다.")
                    items.append(rec)
                except (OSError, ValueError):
                    continue
        active = next(
            (
                j for j in items
                if is_busy and current_active_id and j.get("job_id") == current_active_id and j.get("status") == "RUNNING"
            ),
            None,
        )
        return {"active_job": active, "jobs": items}

    @app.get("/api/data/jobs/{job_id}")
    def data_job(job_id: str):
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise fastapi.HTTPException(status_code=404, detail="검사 기록을 찾지 못했습니다.")
        path = JOBS / job_id / "job.json"
        if not path.exists():
            raise fastapi.HTTPException(status_code=404, detail="검사 기록을 찾지 못했습니다.")
        try:
            record = read_json(path)
        except OSError:
            if lock.locked() and job_id == active_job_id and isinstance(active_job_record, dict):
                record = _snapshot_job_record(active_job_record)
            else:
                raise
        if lock.locked() and job_id == active_job_id and isinstance(active_job_record, dict) and record.get("status") == "RUNNING":
            record = _snapshot_job_record(active_job_record)
        if record.get("status") == "FINISHED":
            record["result"] = preview.load_result(record["dataset_id"])
        elif record.get("status") == "RUNNING" and not (lock.locked() and job_id == active_job_id):
            record["status"] = "FAILED"
            record["orphaned"] = True
            record.setdefault("error", "이전 실행이 중단되어 완료 기록이 없습니다.")
        return record

    @app.get("/api/data/result/{data_id}/{kind}")
    def data_download(data_id: str, kind: str):
        try:
            result = preview.load_result(data_id)
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc
        if kind not in {"csv", "provenance_csv", "labeled_csv", "manifest"}:
            raise fastapi.HTTPException(status_code=404, detail="다운로드할 파일을 찾지 못했습니다.")
        filename = (
            "joined.csv"
            if kind == "csv"
            else "joined_provenance.csv"
            if kind == "provenance_csv"
            else "joined_labeled.csv"
            if kind == "labeled_csv"
            else "dataset_manifest.json"
        )
        path = preview.OUTPUT / data_id / filename
        if not path.is_file():
            raise fastapi.HTTPException(status_code=404, detail="파일을 찾지 못했습니다.")
        if kind == "csv" and preview.sha256(path) != result["joined_csv"]["sha256"]:
            raise fastapi.HTTPException(status_code=409, detail="저장된 결합 CSV가 검사 기록과 다릅니다.")
        if kind == "provenance_csv" and "joined_provenance_csv" in result:
            if preview.sha256(path) != result["joined_provenance_csv"]["sha256"]:
                raise fastapi.HTTPException(status_code=409, detail="저장된 출처 보존 CSV가 검사 기록과 다릅니다.")
        if kind == "labeled_csv" and "joined_labeled_csv" in result:
            if preview.sha256(path) != result["joined_labeled_csv"]["sha256"]:
                raise fastapi.HTTPException(status_code=409, detail="저장된 MQC 라벨 보존 CSV가 검사 기록과 다릅니다.")
        return responses.FileResponse(path, filename=path.name)

    @app.get("/api/data/history")
    def data_history():
        paths = sorted(preview.OUTPUT.glob("*/dataset_manifest.json"), reverse=True)[:30]
        items = []
        for p in paths:
            try:
                d = read_json(p)
            except (OSError, ValueError):
                continue
            items.append({
                "dataset_id": p.parent.name,
                "station": d["station"],
                "sensor": d["sensor"],
                "date_start": d.get("date_start"),
                "date_end": d.get("date_end"),
                "valid_minutes": d["valid_minutes"],
                "anomaly_minutes": d.get("anomaly_minutes"),
                "contiguous_windows": d.get("continuity", {}).get("contiguous_4_input_1_target_windows", 0),
                "contiguous_anomaly_windows": d.get("contiguous_labeled_4g_input_1b_target_windows"),
                "mode": d["mode"],
                "time_alignment": d.get("time_alignment", "exact_minute"),
                "column_normalization": d.get("column_normalization", "strict"),
            })
        return items

    @app.get("/api/data/results/{data_id}")
    def data_result(data_id: str):
        try:
            return preview.load_result(data_id)
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/data/snapshots")
    def list_snapshots():
        return ParquetSnapshotAuthority(preview_output=preview.OUTPUT).list_snapshots()

    @app.post("/api/data/snapshots")
    def create_snapshot(payload: dict = fastapi.Body(), x_dashboard_token: str = fastapi.Header(default="")):
        authorized(x_dashboard_token)
        if not lock.acquire(blocking=False):
            raise fastapi.HTTPException(status_code=409, detail="진행 중인 작업이 끝난 뒤 스냅샷을 생성해 주세요.")
        raw_ids = payload.get("dataset_ids")
        dataset_id = str(payload.get("dataset_id", "")).strip()
        ratios = payload.get("split_ratios", [0.70, 0.15, 0.15])
        try:
            if not isinstance(ratios, list) or len(ratios) != 3:
                raise ValueError("split_ratios는 [train, validation, test] 3개 비율이어야 합니다.")
            auth = ParquetSnapshotAuthority(preview_output=preview.OUTPUT)
            if isinstance(raw_ids, list) and raw_ids:
                snap = auth.build_from_datasets(
                    [str(x).strip() for x in raw_ids if str(x).strip()],
                    split_ratios=(float(ratios[0]), float(ratios[1]), float(ratios[2])),
                    split_policy=payload.get("split_policy", CHRONOLOGICAL_SPLIT_POLICY),
                )
            else:
                snap = auth.build_from_dataset(
                    dataset_id,
                    split_ratios=(float(ratios[0]), float(ratios[1]), float(ratios[2])),
                    split_policy=payload.get("split_policy", CHRONOLOGICAL_SPLIT_POLICY),
                )
            return snap
        except (ValueError, OSError) as exc:
            raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            lock.release()

    @app.get("/api/data/snapshots/{snapshot_id}")
    def get_snapshot(snapshot_id: str):
        try:
            auth = ParquetSnapshotAuthority(preview_output=preview.OUTPUT)
            auth.validate_snapshot(snapshot_id)
            path = auth.root / snapshot_id / "snapshot_manifest.json"
            return read_json(path)
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/data/snapshots/{snapshot_id}/download/{kind}")
    def download_snapshot(snapshot_id: str, kind: str):
        if kind not in {"parquet", "manifest"}:
            raise fastapi.HTTPException(status_code=404, detail="다운로드할 스냅샷 파일 종류가 올바르지 않습니다.")
        try:
            auth = ParquetSnapshotAuthority(preview_output=preview.OUTPUT)
            auth.validate_snapshot(snapshot_id)
            filename = "snapshot.parquet" if kind == "parquet" else "snapshot_manifest.json"
            path = auth.root / snapshot_id / filename
            return responses.FileResponse(path, filename=f"{snapshot_id}_{filename}")
        except ValueError as exc:
            raise fastapi.HTTPException(status_code=404, detail=str(exc)) from exc

