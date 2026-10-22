"""TDD tests for AI-QC-MLOps <-> Ocean-AI registry synchronization and status bridge."""
import os
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite://")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_mlops import router
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import Actor, require_reviewer
from app.models.domain import (
    ApprovalHistory,
    DatasetRegistry,
    ModelRegistry,
    RetrainingHistory,
)
from app.services.qc_mlops_bridge import get_qc_engine_status, sync_qc_mlops_artifacts


@pytest.fixture
def bridge_env(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    scratch = (
        Path(os.environ.get("OCEAN_TEST_WORKDIR", str(Path(__file__).parent / ".work")))
        / f"qc_bridge_{uuid.uuid4().hex}"
    )
    scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "DATASET_SNAPSHOT_DIR", str(scratch))

    app = FastAPI()
    app.include_router(router, prefix="/api/mlops")

    def isolated_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    app.dependency_overrides[require_reviewer] = lambda: Actor("test-reviewer", "reviewer")
    with TestClient(app) as client:
        yield client, sessions, scratch
    engine.dispose()


def test_qc_engine_status_endpoint_returns_metadata(bridge_env):
    client, sessions, _ = bridge_env
    res = client.get("/api/mlops/qc-engine/status")
    assert res.status_code == 200
    body = res.json()
    assert body["schema_version"] == "1.0"
    assert isinstance(body["engine_available"], bool)
    assert "ui_urls" in body
    assert body["ui_urls"]["workbench"] == "/qc-mlops-ui/?embed=1"
    assert body["ui_urls"]["data_preview"] == "/qc-mlops-ui/data?embed=1"

    with sessions() as db:
        direct = get_qc_engine_status(db)
        assert direct["schema_version"] == "1.0"
        assert "registry_counts" in direct


def test_sync_qc_mlops_artifacts_populates_four_tables_idempotently(bridge_env):
    client, sessions, scratch = bridge_env

    res1 = client.post("/api/mlops/qc-engine/sync")
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["ok"] is True
    assert body1["synced_counts"]["datasets"] >= 1
    assert body1["synced_counts"]["models"] >= 2
    assert body1["synced_counts"]["retraining_runs"] >= 1
    assert body1["synced_counts"]["approvals"] >= 1

    with sessions() as db:
        ds_count_1 = db.query(DatasetRegistry).count()
        m_count_1 = db.query(ModelRegistry).count()
        rt_count_1 = db.query(RetrainingHistory).count()
        ap_count_1 = db.query(ApprovalHistory).count()
        assert ds_count_1 >= 1
        assert m_count_1 >= 2
        assert rt_count_1 >= 1
        assert ap_count_1 >= 1

        # Verify snapshot files materialized in DATASET_SNAPSHOT_DIR
        for ds in db.query(DatasetRegistry).all():
            snap_file = scratch / f"{ds.data_hash}.json"
            assert snap_file.is_file()

    # Second call must be idempotent (no duplicate rows)
    res2 = client.post("/api/mlops/qc-engine/sync")
    assert res2.status_code == 200
    with sessions() as db:
        assert db.query(DatasetRegistry).count() == ds_count_1
        assert db.query(ModelRegistry).count() == m_count_1
        assert db.query(RetrainingHistory).count() == rt_count_1
        assert db.query(ApprovalHistory).count() == ap_count_1
        sync_direct = sync_qc_mlops_artifacts(db)
        assert sync_direct["ok"] is True

    # Verify /api/mlops/summary, /api/mlops/retrain-history, and /api/mlops/readiness work cleanly after sync
    models_res = client.get("/api/mlops/summary")
    assert models_res.status_code == 200
    models_body = models_res.json()
    assert models_body["total"] == m_count_1

    hist_res = client.get("/api/mlops/retrain-history")
    assert hist_res.status_code == 200
    assert len(hist_res.json()["history"]) == rt_count_1

    readiness_res = client.get("/api/mlops/readiness")
    assert readiness_res.status_code == 200
    assert readiness_res.json()["counts"]["models"] == m_count_1


def test_sync_qc_mlops_artifacts_with_clean_engine_without_reports(bridge_env, monkeypatch):
    client, sessions, scratch = bridge_env
    import shutil

    clean_engine = scratch / "clean_mlops_qc_engine"
    (clean_engine / "scripts").mkdir(parents=True, exist_ok=True)
    (clean_engine / "manifests").mkdir(parents=True, exist_ok=True)
    bundled_root = Path(__file__).resolve().parents[2] / "mlops-qc-engine"

    for script_file in (bundled_root / "scripts").glob("*.py"):
        shutil.copy2(script_file, clean_engine / "scripts" / script_file.name)
    for manifest_name in (
        "2025_operation_64_manifest.json",
        "2025_training_archive_inventory.json",
        "20261006_local_trial_manifest.json",
    ):
        shutil.copy2(
            bundled_root / "manifests" / manifest_name,
            clean_engine / "manifests" / manifest_name,
        )
    (clean_engine / "manifests" / "active_release_pointer.json").write_text(
        '{"active_release_id": "2025_OPERATION_64_BASELINE", "active_release_path": null, "station_overrides": {}, "history": []}',
        encoding="utf-8",
    )

    monkeypatch.setenv("OCEAN_AI_QC_ENGINE_ROOT", str(clean_engine))
    assert not (clean_engine / "reports").exists()

    status_res = client.get("/api/mlops/qc-engine/status")
    assert status_res.status_code == 200
    status_body = status_res.json()
    assert status_body["engine_available"] is True
    assert "workbench_running" in status_body
    assert status_body["bundle_counts"]["datasets"] >= 1
    assert status_body["bundle_counts"]["models"] >= 2
    assert status_body["bundle_counts"]["retraining_runs"] >= 1
    assert status_body["bundle_counts"]["approvals"] >= 1

    sync_res = client.post("/api/mlops/qc-engine/sync")
    assert sync_res.status_code == 200
    sync_body = sync_res.json()
    assert sync_body["ok"] is True
    assert sync_body["synced_counts"]["datasets"] >= 1
    assert sync_body["synced_counts"]["models"] >= 2
    assert sync_body["synced_counts"]["retraining_runs"] >= 1
    assert sync_body["synced_counts"]["approvals"] >= 1


def test_qc_engine_start_endpoint_returns_workbench_state(bridge_env, monkeypatch):
    client, _, _ = bridge_env
    from app.services import qc_mlops_bridge

    monkeypatch.setattr(qc_mlops_bridge, "is_qc_workbench_running", lambda port=8765: True)
    res = client.post("/api/mlops/qc-engine/start")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["workbench_running"] is True
    assert body["workbench_port"] == 8765


def test_workbench_state_and_catalog_without_reports_or_external_backup(bridge_env, monkeypatch):
    _, _, scratch = bridge_env
    empty_ws = scratch / "empty_data_workspace"
    empty_ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AI_QC_DATA_WORKSPACE", str(empty_ws))

    import sys
    bundled_root = Path(__file__).resolve().parents[2] / "mlops-qc-engine"
    for p in (str(bundled_root), str(bundled_root / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)

    import scripts.dataset_preview as preview
    import scripts.local_dashboard as local_dashboard

    # Without monkeypatching preview.WORKSPACE, allowed_roots() and catalog() must honor AI_QC_DATA_WORKSPACE
    assert any(Path(r).resolve() == empty_ws.resolve() for r in preview.allowed_roots())
    cat = preview.catalog()
    assert isinstance(cat["mapping"], list)
    assert len(cat["mapping"]) >= 49

    state = local_dashboard.snapshot()
    assert state["application_id"] == "oceandb-local-trial-dashboard"
    assert len(state["models"]) == 64
    assert "station_display" in state["models"][0]

    # Step 4 runtime bundle resolution must not crash with 500 FileNotFoundError on a clean clone
    with TestClient(local_dashboard.app, base_url="http://127.0.0.1:8765") as wb_client:
        res = wb_client.get("/api/deployments/resolve/DT_0001/TIDE_LEVEL_VEGA")
        assert res.status_code == 200
        bundle = res.json()
        assert bundle["station"] == "DT_0001"
        assert bundle["sensor"] == "TIDE_LEVEL_VEGA"
        assert bundle["source_mode"] == "BASELINE_2025"
        assert bundle["hash_verified"] is False
        assert bundle["assets"]["model"]["bytes"] > 0

    # Baseline manifest files entries without optional 'bytes' key must not raise KeyError
    import json
    import scripts.release_pointer_consumer as consumer

    pointer_file = scratch / "active_release_pointer.json"
    pointer_file.write_text(
        json.dumps(
            {
                "active_release_id": "2025_OPERATION_64_BASELINE",
                "active_release_path": None,
                "station_overrides": {},
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    minimal_manifest = scratch / "minimal_baseline.json"
    minimal_manifest.write_text(
        json.dumps(
            {
                "root": str(scratch / "missing_backup"),
                "models": [
                    {
                        "station": "DT_0006",
                        "sensor": "TIDE_LEVEL_LASER",
                        "model": "m.h5",
                        "scaler": "s.gz",
                        "threshold": "Thres.forecast.DEV",
                    }
                ],
                "files": [
                    {"path": "m.h5", "sha256": "a" * 64},
                    {"path": "s.gz", "sha256": "b" * 64},
                    {"path": "Thres.forecast.DEV", "sha256": "c" * 64},
                ],
            }
        ),
        encoding="utf-8",
    )
    resolved_min = consumer.resolve_runtime_bundle(
        "DT_0006",
        "TIDE_LEVEL_LASER",
        pointer_path=pointer_file,
        baseline_manifest_path=minimal_manifest,
        verify_hash=True,
    )
    assert resolved_min["assets"]["model"]["bytes"] == 0
    assert resolved_min["assets"]["scaler"]["bytes"] == 0
    assert resolved_min["assets"]["threshold"]["bytes"] == 0


def test_clean_core_manifests_cli_and_docs_integrity():
    import re
    import sys
    repo_root = Path(__file__).resolve().parents[3]
    bundled_root = repo_root / "ocean-ai-platform" / "mlops-qc-engine"
    for p in (str(bundled_root), str(bundled_root / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)

    # 1. No hardcoded GB-PC-002 paths in manifests
    trial_manifest_text = (bundled_root / "manifests" / "20261006_local_trial_manifest.json").read_text(encoding="utf-8")
    assert "GB-PC-002" not in trial_manifest_text

    # 2. local_dashboard.py CLI supports documented --host, --port, --no-browser flags
    import scripts.local_dashboard as local_dashboard
    parsed = local_dashboard.build_arg_parser().parse_args(
        ["--host", "127.0.0.1", "--port", "8765", "--no-browser"]
    )
    assert parsed.host == "127.0.0.1"
    assert parsed.port == 8765
    assert parsed.no_browser is True

    # 3. All relative markdown links in docs/42_*.md and docs/ml-ops-docs/*.md resolve to existing files
    doc_files = [
        repo_root / "docs" / "42_AI_QC_MLOPS_ENGINE_INTEGRATION.md",
        *sorted((repo_root / "docs" / "ml-ops-docs").glob("*.md")),
    ]
    assert len(doc_files) == 7
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for doc_file in doc_files:
        content = doc_file.read_text(encoding="utf-8")
        assert "09_codex_antigravity_collaboration_manual" not in content
        assert "AI 모델 시험실 열기.cmd" not in content
        for raw_target in link_pattern.findall(content):
            target = raw_target.split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (doc_file.parent / target).resolve()
            assert resolved.exists(), f"Broken link in {doc_file.name}: {raw_target} -> {resolved}"

