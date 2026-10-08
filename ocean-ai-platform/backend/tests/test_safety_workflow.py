# 파일 역할: 권한·승인·데이터셋 및 운영 경로의 회귀를 검증합니다.
"""Isolated regression tests: no Oracle, production DB, LLM or network calls."""
import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["TEST_DATABASE_URL"] = "sqlite://"
os.environ["MDC_SYNC_ENABLED"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "false"

import sys
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.domain import (StationMetadata, ObservationRaw, ObservationStandard,
    QCFlagHistory, QCRuleDefinition, QCRuleResult, ApprovalHistory, AILabel,
    RetrainingPool, DocumentIndex, ModelRegistry, DatasetRegistry, ReportRegistry)
from app.rag import hybrid_retriever
from app.scripts import sync_mdc_db

REVIEWER = {"Authorization": "Bearer test-reviewer-token"}
OPERATOR = {"Authorization": "Bearer test-operator-token"}
TS = datetime(2026, 9, 29, 0)


@pytest.fixture
def env(monkeypatch):
    from pathlib import Path
    import uuid
    scratch = Path(os.environ.get("OCEAN_TEST_WORKDIR", str(Path(__file__).parent / ".work"))) / uuid.uuid4().hex
    monkeypatch.setattr(settings, "DATASET_SNAPSHOT_DIR", str(scratch / "snapshots"))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def isolated_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = isolated_db
    from app.api import routes_dashboard
    app.dependency_overrides[routes_dashboard.get_db] = isolated_db
    for name, module in list(sys.modules.items()):
        if name.startswith("app.") and hasattr(module, "SessionLocal"):
            monkeypatch.setattr(module, "SessionLocal", sessions)
    monkeypatch.setattr(settings, "API_IDENTITIES", {
        "reviewer-alice": {"token": "test-reviewer-token", "role": "reviewer"},
        "operator-bob": {"token": "test-operator-token", "role": "operator"},
    })
    monkeypatch.setattr(settings, "DATA_MODE", "live")
    monkeypatch.setattr(settings, "VECTOR_SEARCH_ENABLED", False)
    with TestClient(app) as client:
        yield client, sessions
    app.dependency_overrides.clear()
    engine.dispose()


def qc_row(db, final="1"):
    row = QCFlagHistory(station_id="TEST_1", sensor_id="S1", variable_code="TIDE", timestamp_utc=TS,
                        qc_flag_1st="1", qc_flag_2nd="4", qc_flag_final=final, qc_version="1")
    db.add(row); db.commit()
    return row.id


def test_reject_preserves_final_and_prevents_duplicate_review(env):
    client, sessions = env
    with sessions() as db:
        target = qc_row(db)
    payload = {"target_type": "QC_CHANGE", "target_id": str(target), "user_id": "spoofed", "changes": {"qc_flag_final": "4"}}
    assert client.post("/api/approvals/reject", json=payload).status_code == 401
    assert client.post("/api/approvals/reject", json=payload, headers=OPERATOR).status_code == 403
    assert client.post("/api/approvals/reject", json=payload, headers=REVIEWER).status_code == 200
    assert client.post("/api/approvals/approve", json=payload, headers=REVIEWER).status_code == 409
    with sessions() as db:
        row = db.get(QCFlagHistory, target)
        assert row.qc_flag_final == "1"
        assert row.reviewer_id == "reviewer-alice"
        history = db.query(ApprovalHistory).one()
        assert history.approval_status == "REJECTED"
        assert history.requested_by == "reviewer-alice"


def test_modify_and_model_deploy_cannot_bypass_approval(env):
    client, sessions = env
    with sessions() as db:
        db.add(ModelRegistry(model_name="test", model_type="baseline", model_version="V1", target_variable="TIDE", status="PENDING_APPROVAL")); db.commit()
    payload = {"target_type": "MODEL_DEPLOY", "target_id": "V1", "changes": {"status": "PRODUCTION"}}
    assert client.post("/api/approvals/modify", json=payload, headers=REVIEWER).status_code == 422
    assert client.post("/api/mlops/models/V1/deploy", json={}, headers=REVIEWER).status_code == 409
    payload["changes"] = {}
    assert client.post("/api/approvals/approve", json=payload, headers=REVIEWER).status_code == 200
    with sessions() as db:
        assert db.query(ModelRegistry).one().status == "APPROVED"
    assert client.post("/api/mlops/models/V1/deploy", json={}, headers=OPERATOR).status_code == 403
    deployed = client.post("/api/mlops/models/V1/deploy", json={}, headers=REVIEWER)
    assert deployed.status_code == 409
    assert deployed.json()["detail"]["mutation_performed"] is False
    with sessions() as db:
        model = db.query(ModelRegistry).one()
        assert model.status == "APPROVED" and not model.is_champion and model.deployed_at is None
    assert client.post("/api/mlops/retrain", json={"model_id": "V1"}, headers=OPERATOR).status_code == 501


def test_report_compatibility_route_uses_same_review_gate(env):
    client, sessions = env
    with sessions() as db:
        db.add(ReportRegistry(report_id="R1", report_title="Test", report_type="DAILY", status="DRAFT")); db.commit()
    assert client.get("/api/reports/list").status_code == 200
    assert client.get("/api/reports/stats").status_code == 200
    assert client.post("/api/reports/R1/approve", json={"user_id": "spoofed"}, headers=OPERATOR).status_code == 403
    assert client.post("/api/reports/R1/reject", json={"user_id": "spoofed"}, headers=REVIEWER).status_code == 200
    assert client.post("/api/reports/R1/review", headers=OPERATOR).status_code == 409
    assert client.post("/api/reports/R1/approve", json={"user_id": "spoofed"}, headers=REVIEWER).status_code == 409


def test_data_mode_and_source_timestamp(env, monkeypatch):
    client, _ = env
    historical = datetime(2018, 9, 29, 9)
    assert sync_mdc_db.shift_time_to_present(historical) == historical
    start, end = sync_mdc_db.get_simulated_time_range(10)
    assert end.year == datetime.now().year
    assert (end - start).total_seconds() == 10
    with pytest.raises(ValueError):
        sync_mdc_db.shift_time_to_present(None)
    assert client.get("/api/runtime").json()["is_demo"] is False
    assert client.post("/api/qc/run-copilot", json={}, headers=OPERATOR).status_code == 409
    assert client.post("/api/test-auto/run", json={}, headers=OPERATOR).status_code == 409
    monkeypatch.setattr(settings, "API_IDENTITIES", {})
    assert client.post("/api/approvals/approve", json={}, headers=REVIEWER).status_code == 503


def test_raw_to_qc_evidence_approval_label_dataset(env):
    client, sessions = env
    with sessions() as db:
        db.add(StationMetadata(station_id="TEST_1", station_name="Isolated test station"))
        raw = ObservationRaw(station_id="TEST_1", sensor_id="S1", variable_code="TIDE", value_unit="cm", value_raw=150.0, timestamp_utc=TS, timestamp_kst=TS + timedelta(hours=9))
        db.add(raw)
        standard = sync_mdc_db.standardize_observation(raw)
        db.add(standard)
        db.add(QCRuleDefinition(qc_rule_id="RANGE", qc_rule_name="Range", applicable_variable=["TIDE"], algorithm_description="min/max", threshold_definition={"min": 0, "max": 100}, rule_version="1", active=True))
        db.add(DocumentIndex(document_id="DOC1", chunk_id="CHUNK1", document_title="QC manual", document_type="MANUAL", related_station_id="TEST_1", related_variable_code="TIDE", chunk_text="조위 범위 이상은 담당자가 검토합니다.", page_no=1))
        db.commit()
        standard_id = standard.observation_id
    result = client.post("/api/qc/rules/execute", json={"station_id": "TEST_1", "variable_code": "TIDE"}, headers=OPERATOR)
    assert result.status_code == 200, result.text
    assert result.json()["created_results"] == 1
    result = client.post("/api/qc/copilot/analyze", json={"station_id": "TEST_1", "variable_code": "TIDE", "query": "조위 범위"})
    assert result.status_code == 200, result.text
    assert result.json()["recommended_flag"] == "BAD"
    assert result.json()["supporting_documents"][0]["chunk_id"] == "CHUNK1"
    with sessions() as db:
        assert db.query(QCFlagHistory).count() == 0  # Analysis does not finalize QC.
        assert db.query(QCRuleResult).one().result_flag == "4"
    candidate = client.post("/api/qc/review-candidates", json={"observation_id": standard_id}, headers=OPERATOR)
    assert candidate.status_code == 200, candidate.text
    target = candidate.json()["target_id"]
    repeated = client.post("/api/qc/review-candidates", json={"observation_id": standard_id}, headers=OPERATOR)
    assert repeated.json()["target_id"] == target
    with sessions() as db:
        assert db.query(QCFlagHistory).one().qc_flag_final is None
    response = client.post("/api/approvals/approve", json={"target_type": "QC_CHANGE", "target_id": str(target)}, headers=REVIEWER)
    assert response.status_code == 200, response.text
    label = {"station_id": "TEST_1", "sensor_id": "S1", "variable_code": "TIDE", "event_start": TS.isoformat(), "quality_label": "BAD", "error_cause": "statistical_outlier", "label_source": "RULE_QC", "label_version": "1"}
    assert client.post("/api/qc/ai-labels", json={**label, "review_status": "APPROVED"}, headers=OPERATOR).status_code == 422
    response = client.post("/api/qc/ai-labels", json=label, headers=OPERATOR)
    assert response.status_code == 200, response.text
    label_id = response.json()["label_id"]
    assert client.post("/api/approvals/approve", json={"target_type": "AI_LABEL", "target_id": label_id}, headers=REVIEWER).status_code == 200
    assert client.post("/api/approvals/approve", json={"target_type": "AI_LABEL", "target_id": label_id}, headers=REVIEWER).status_code == 409
    with sessions() as db:
        assert db.query(RetrainingPool).count() == 1
        db.add(DatasetRegistry(dataset_id="D1", dataset_name="test", dataset_version="1", dataset_split="TRAIN", station_scope=["TEST_1"], sensor_scope=["S1"], variable_scope=["TIDE"], period_start=TS, period_end=TS + timedelta(days=1), feature_version="1", label_version="1", preprocessing_version="1", status="DRAFT")); db.commit()
    built = client.post("/api/datasets/D1/build", headers=OPERATOR)
    assert built.status_code == 200, built.text
    # 레거시 QC 승인/라벨만으로 사건·Feature 근거가 없는 데이터를 학습 가능으로 처리하지 않는다.
    assert built.json()["unreviewed_count"] == 1
    from pathlib import Path
    import hashlib
    snapshot = Path(settings.DATASET_SNAPSHOT_DIR) / f"{built.json()['data_hash']}.json"
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == built.json()["data_hash"]
    assert client.post("/api/datasets/D1/validate", headers=OPERATOR).json()["status"] == "INVALID"
    with sessions() as db:
        db.get(ObservationStandard, standard_id).value_standard = 160; db.commit()
    assert client.post("/api/datasets/D1/approve", headers=REVIEWER).status_code == 409
    rebuilt = client.post("/api/datasets/D1/build", headers=OPERATOR).json()
    assert rebuilt["data_hash"] != built.json()["data_hash"]
    assert client.post("/api/datasets/D1/validate", headers=OPERATOR).json()["status"] == "INVALID"
    assert client.post("/api/datasets/D1/approve", headers=REVIEWER).status_code == 409


def test_no_evidence_and_unreviewed_data_are_not_good(env):
    client, sessions = env
    with sessions() as db:
        db.add(ObservationStandard(observation_id="O2", station_id="TEST_1", sensor_id="S1", variable_code="TIDE", timestamp_utc=TS, value_standard=None, standardization_version="1"))
        db.add(DatasetRegistry(dataset_id="D2", dataset_name="test", dataset_version="2", dataset_split="TRAIN", station_scope=["TEST_1"], variable_scope=["TIDE"], period_start=TS, period_end=TS+timedelta(days=1), feature_version="1", label_version="1", preprocessing_version="1"))
        db.add(DocumentIndex(document_id="DOC2", chunk_id="CHUNK2", document_title="Unrelated", document_type="MANUAL", chunk_text="무관한 내용"))
        db.commit()
    result = client.post("/api/rag/hybrid-search", json={"query": "조위"}).json()
    assert result["results"] == []
    assert result["evidence_status"] == "NO_RELEVANT_EVIDENCE"
    assert client.post("/api/datasets/D2/build", headers=OPERATOR).json()["unreviewed_count"] == 1
    assert client.post("/api/datasets/D2/validate", headers=OPERATOR).json()["status"] == "INVALID"


@pytest.mark.parametrize("path", ["/api/dashboard/summary", "/api/dashboard/performance", "/api/observations/summary", "/api/equipment/status", "/api/qc/summary", "/api/reports/list", "/api/reports/stats", "/api/approvals/pending"])
def test_empty_database_read_routes(env, path):
    response = env[0].get(path)
    assert response.status_code == 200, response.text


def test_parquet_timezone_and_same_name_sources():
    # Avoid pytest's mode=0700 temp directory on managed Windows ACLs.
    from pathlib import Path
    import uuid
    tmp_path = Path(os.environ.get("OCEAN_TEST_WORKDIR", str(Path(__file__).parent / ".work"))) / uuid.uuid4().hex
    tmp_path.mkdir(parents=True)
    import pandas as pd
    from app.scripts.build_datalake import build, normalize
    data = pd.DataFrame({"station_id": ["TEST"], "timestamp_local": ["2018-01-01 09:00:00"], "variable_code": ["TIDE"], "value_raw": [12.0]})
    source = tmp_path / "source"
    for directory in ["a", "b"]:
        folder = source / directory
        folder.mkdir(parents=True)
        data.to_csv(folder / "same.csv", index=False)
    normalized = normalize(data.copy(), source / "a" / "same.csv")
    assert normalized.timestamp_utc.iloc[0] == pd.Timestamp("2018-01-01T00:00:00Z")
    lake = tmp_path / "lake"
    build(source, lake)
    outputs = list(lake.rglob("*.parquet"))
    assert len(outputs) == 2
    assert sum(len(pd.read_parquet(path)) for path in outputs) == 2
