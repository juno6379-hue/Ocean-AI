"""No network or production writes: evidence gaps must preserve registry state."""
import hashlib
import os
import uuid
from datetime import datetime
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
from app.models.domain import ApprovalHistory, DatasetRegistry, ModelRegistry
from app.services.mlops_readiness import get_mlops_readiness, model_readiness


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    scratch = Path(os.environ.get("OCEAN_TEST_WORKDIR", str(Path(__file__).parent / ".work"))) / uuid.uuid4().hex
    scratch.mkdir(parents=True)
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


def add_model(db, **overrides):
    fields = dict(model_name="fixture", model_type="ridge", model_version="M1", target_task="FORECASTING",
                  target_variable="TIDE", dataset_version="D1", feature_version="F1", label_version="L1",
                  preprocessing_version="P1", metrics_json={"mae": 2.5, "rmse": 3.0, "latency": .1},
                  status="APPROVED", deployment_status="CANDIDATE", is_champion=False)
    model = ModelRegistry(**(fields | overrides))
    db.add(model)
    db.commit()
    return model


def add_dataset(db, scratch, name="fixture", **overrides):
    payload = b'{"records": [{"id": "fixture-only"}]}'
    digest = hashlib.sha256(payload).hexdigest()
    (scratch / f"{digest}.json").write_bytes(payload)
    fields = dict(dataset_id=name, dataset_name=name, dataset_version="D1", dataset_split="TRAIN",
                  station_scope=["TEST"], variable_scope=["TIDE"], period_start=datetime(2020, 1, 1),
                  period_end=datetime(2020, 2, 1), sample_count=1, feature_version="F1", label_version="L1",
                  preprocessing_version="P1", data_hash=digest, status="APPROVED", approved_by="fixture-reviewer")
    dataset = DatasetRegistry(**(fields | overrides))
    db.add(dataset)
    db.add(ApprovalHistory(approval_type="DATASET", target_id=name, approved_by="fixture-reviewer",
                           approval_status="APPROVED", comment="snapshot_sha256=" + digest))
    db.commit()
    return dataset


def codes(result):
    return {item["code"] for item in result["blockers"]}


def test_empty_registry_is_blocked_and_read_only(env):
    client, sessions, _ = env
    response = client.get("/api/mlops/readiness")
    assert response.status_code == 200
    result = response.json()
    assert result["operational_model_count"] == 0 and result["ready_for_deployment"] is False
    assert {"NO_REGISTERED_MODELS", "NO_APPROVED_DATASETS", "DEPLOYMENT_RUNTIME_NOT_CONFIGURED"} <= codes(result)
    with sessions() as db:
        assert db.query(ModelRegistry).count() == db.query(ApprovalHistory).count() == 0


def test_approved_candidate_cannot_mutate_champion_without_execution(env):
    client, sessions, scratch = env
    with sessions() as db:
        add_dataset(db, scratch)
        artifact = scratch / "not-a-real-model.joblib"
        artifact.write_bytes(b"Do not deserialize this fixture")
        add_model(db, artifact_path=str(artifact))
        add_model(db, model_version="M0", status="PRODUCTION", deployment_status="PRODUCTION", is_champion=True)
        db.add(ApprovalHistory(approval_type="MODEL_DEPLOY", target_id="M1", approval_status="APPROVED", approved_by="reviewer"))
        db.commit()
    result = client.post("/api/mlops/models/M1/deploy", json={})
    assert result.status_code == 409 and result.json()["detail"]["mutation_performed"] is False
    checks = result.json()["detail"]["readiness"]["checks"]
    assert checks["dataset"]["status"] == "SNAPSHOT_HASH_MATCH"
    assert checks["dataset"]["evidence_lineage_verified"] is False
    assert checks["artifact"]["status"] == "PRESENT_UNVERIFIED"
    assert checks["evaluation"]["status"] == "DECLARED_UNVERIFIED"
    assert checks["acceptance_criteria"]["status"] == "NOT_DEFINED"
    with sessions() as db:
        models = {m.model_version: m for m in db.query(ModelRegistry).all()}
        assert models["M0"].is_champion and models["M0"].status == "PRODUCTION"
        assert models["M1"].status == "APPROVED" and not models["M1"].is_champion
        assert models["M1"].deployed_at is None
    summary = client.get("/api/mlops/summary").json()
    assert summary["counts"]["PRODUCTION"] == 1
    assert summary["readiness"]["operational_model_count"] == 0
    assert all(not m["readiness"]["operational_verified"] for m in summary["models"])


def test_runtime_rollback_preserves_both_registry_rows(env):
    client, sessions, _ = env
    with sessions() as db:
        add_model(db, status="PRODUCTION", deployment_status="PRODUCTION", is_champion=True, rolled_back_from="M0")
        add_model(db, model_version="M0", status="ARCHIVED", deployment_status="ARCHIVED")
    response = client.post("/api/mlops/models/M1/rollback")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ROLLBACK_RUNTIME_NOT_CONFIGURED"
    with sessions() as db:
        models = {m.model_version: m for m in db.query(ModelRegistry).all()}
        assert models["M1"].is_champion and models["M1"].status == "PRODUCTION"
        assert not models["M0"].is_champion and models["M0"].status == "ARCHIVED"


def test_snapshot_tamper_ambiguous_version_and_lineage_are_blocked(env):
    _, sessions, scratch = env
    with sessions() as db:
        model = add_model(db)
        dataset = add_dataset(db, scratch, feature_version="OTHER")
        (scratch / f"{dataset.data_hash}.json").write_bytes(b"tampered")
        result = model_readiness(db, model)
        assert {"DATASET_SNAPSHOT_INVALID", "DATASET_LINEAGE_MISMATCH"} <= codes(result)
        add_dataset(db, scratch, name="other-family")
        assert "DATASET_REFERENCE_AMBIGUOUS" in codes(model_readiness(db, model))


def test_latest_rejection_invalid_metrics_and_missing_artifact(env):
    _, sessions, _ = env
    with sessions() as db:
        model = add_model(db, metrics_json={"mae": True, "rmse": -1})
        db.add(ApprovalHistory(approval_type="MODEL_DEPLOY", target_id="M1", approval_status="APPROVED", approved_by="reviewer"))
        db.flush()
        db.add(ApprovalHistory(approval_type="MODEL_DEPLOY", target_id="M1", approval_status="REJECTED", approved_by="reviewer"))
        db.commit()
        result = model_readiness(db, model)
        assert {"MODEL_APPROVAL_MISSING", "ARTIFACT_MISSING", "EVALUATION_METRICS_INVALID"} <= codes(result)
        assert result["checks"]["approval"]["status"] == "MISSING"


def test_dataset_approver_identity_must_match_record(env):
    _, sessions, scratch = env
    with sessions() as db:
        model = add_model(db)
        dataset = add_dataset(db, scratch)
        dataset.approved_by = "different-reviewer"
        db.commit()
        assert "DATASET_APPROVAL_MISSING" in codes(model_readiness(db, model))


def test_unconfigured_retraining_does_not_claim_a_queued_job(env):
    client, _, _ = env
    assert client.post("/api/mlops/retrain", json={"model_id": "M1"}).status_code == 501


def test_readiness_does_not_autoflush_callers_pending_rows(env):
    _, sessions, _ = env
    with sessions() as db:
        pending = ModelRegistry(model_version="NOT_PERSISTED")
        db.add(pending)
        assert get_mlops_readiness(db)["counts"]["models"] == 0
        assert pending in db.new and pending.id is None
