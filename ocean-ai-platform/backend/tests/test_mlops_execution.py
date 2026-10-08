"""Isolated numeric/ledger/worker tests; no real ocean approval or production writes."""
import copy
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.domain import ApprovalHistory
from app.ml.comparison_runner import ComparisonBlocked, digest, preflight, read_json
from app.ml.protocols import canonical_bytes, validate_protocol, validate_approved_protocol
from app.ml.typed_adapters import compare_typed, typed_metrics, validate_payload
from app.ml.serving import predict_artifact
from app.ml.job_queue import DurableQueue, code_fingerprint
from app.ml.adapter_registry import adapter_coverage
from comparison_fixture import make_fixture, write_json, refresh, mutate_receipt


def protocol(role="EVALUATION_PROTOCOL", task="FORECASTING"):
    result = {"schema_version":"ocean-model-protocol-1","role":role,"status":"DRAFT","protocol_id":"SYNTHETIC-"+role,
        "version":"test-1","domain":"fixed_station","item_id":"water_temperature","target_variable":"FIXTURE_TEMPERATURE","unit":"C",
        "quantity_kind":"SCALAR","task":task}
    if role == "EVALUATION_PROTOCOL":
        result.update(feature_ids=["fixture_current_value"],horizon_seconds=3600 if task=="FORECASTING" else 0,
            lookback_seconds=0,test_pair_policy="ALL_APPROVED_COMMON_ORIGINS",preprocessing_fit="TRAIN_ONLY",
            worker_policy={"max_attempts":1,"lease_seconds":30})
        if task=="FORECASTING": result["ridge_alphas"]=[.1,1.,10.]
        else: result.update(positive_labels=["BAD"],normal_quantiles=[.8,.95],zero_mad_policy="UNIT_SCALE_ONE_EXPLICIT_ENGINEERING_BASELINE")
        if task=="QUALITY_REVIEW": result["human_label_policy"]="PRESERVE_ALL_QC_LABELS_BINARY_SCORE_ONLY_NORMAL_BAD"
    elif role=="ACCEPTANCE_POLICY":
        result.update(limits={"min_test_samples":2,"max_local_p95_ms":10000,"min_mae_improvement_fraction":0.,"max_rmse_regression_fraction":1.},cost_policy="LOCAL_PILOT_COST_NOT_REQUIRED")
    return result


def queue_fixture(root):
    path, authority=make_fixture(root)
    sp=protocol("SPLIT_PROTOCOL")
    sp.update(split_strategy="station_holdout",holdout_locked=True,embargo_seconds=0,
        disjoint_groups=["STATION","SENSOR_EPISODE","EVENT","SOURCE_RECORD","DOCUMENT_FAMILY"],
        dataset_ids={s:a["dataset_id"] for s,a in authority.snapshots.items()},
        periods={s:{"start":a["period_start"],"end":a["period_end"]} for s,a in authority.snapshots.items()},
        member_ids_sha256={s:digest(sorted(r["id"] for r in a["records"])) for s,a in authority.snapshots.items()})
    ps={r:{"body":b,"sha256":hashlib.sha256(canonical_bytes(b)).hexdigest()} for r,b in
        (("SPLIT_PROTOCOL",sp),("EVALUATION_PROTOCOL",protocol()),("ACCEPTANCE_POLICY",protocol("ACCEPTANCE_POLICY")))}
    for role,entry in ps.items():validate_protocol(entry["body"],role,True)
    for s in authority.snapshots:
        mutate_receipt(path,authority,s,lambda receipt,s=s:[p.update(document_family_ids=["synthetic-doc-"+s]) for p in receipt["observations"].values()])
        authority.snapshots[s]["_protocols"]=copy.deepcopy(ps)
    manifest=json.loads(path.read_text())
    manifest.update(domain="fixed_station",item_id="water_temperature",quantity_kind="SCALAR",lookback_seconds=0)
    write_json(path,manifest);refresh(path,authority)
    return path,authority


def test_protocol_body_is_bound_to_actual_authority_hash():
    engine=create_engine("sqlite://")
    Base.metadata.create_all(engine)
    body=protocol(); sha=hashlib.sha256(canonical_bytes(body)).hexdigest()
    with Session(engine) as db:
        db.add(ApprovalHistory(approval_type="MODEL_PROTOCOL",target_id=sha,approval_status="APPROVED",approved_by="SYNTHETIC-REVIEWER",comment="snapshot_sha256="+sha));db.commit()
        assert validate_approved_protocol(db,body,sha,"EVALUATION_PROTOCOL")["sha256"]==sha
        forged=copy.deepcopy(body);forged["horizon_seconds"]=7200
        with pytest.raises(ComparisonBlocked,match="APPROVED_PROTOCOL_BODY_HASH_MISMATCH"):
            validate_approved_protocol(db,forged,sha,"EVALUATION_PROTOCOL")
        db.add(ApprovalHistory(approval_type="MODEL_PROTOCOL",target_id=sha,approval_status="REVOKED",approved_by="SYNTHETIC-REVIEWER",comment="snapshot_sha256="+sha));db.commit()
        with pytest.raises(ComparisonBlocked,match="MODEL_PROTOCOL_APPROVAL_MISSING"):
            validate_approved_protocol(db,body,sha,"EVALUATION_PROTOCOL")
    engine.dispose()


@pytest.mark.parametrize("patch",[{"worker_policy":[]},{"feature_ids":[{}]},{"lookback_seconds":True},{"ridge_alphas":[float('inf')]},{"quantity_kind":{}},{"horizon_seconds":True}])
def test_malformed_nested_protocol_is_structured_block(patch):
    body=protocol();body.update(patch)
    with pytest.raises(ComparisonBlocked):validate_protocol(body,"EVALUATION_PROTOCOL",True)


def payload(kind,i):
    if kind=="SCALAR":return {"representation":kind,"value":i*.4-3}
    if kind=="CIRCULAR_DEGREES":return {"representation":kind,"value":(350+i*.6)%360,"magnitude":1.,"magnitude_unit":"m/s"}
    if kind=="SIGNED_RADIAL":return {"representation":kind,"value":i*.4-13,"coordinate_frame":"positive_away","site_geometry_version":"TEST","qc_eligible":True,"coverage_fraction":.7}
    if kind=="VECTOR_UV":return {"representation":kind,"u":i*.4,"v":-i*.2,"coordinate_frame":"east_north","grid_cell_id":"TEST","geometry_version":"TEST"}
    if kind=="PROFILE_BINS":return {"representation":kind,"bin_ids":["A","B"],"depths":[1.,3.],"values":[i*.4,3-i*.2],"coordinate_frame":"depth_m","layout_version":"TEST","target_variable":"water_temperature","unit":"C","value_representation":"SCALAR"}
    return {"representation":kind,"longitude":((179.99+i*.001+180)%360)-180,"latitude":35+i*.0002,"coordinate_frame":"WGS84","trajectory_id":"TEST"}


def typed_prepared(kind,task="FORECASTING"):
    rows={}
    for split,steps in {"TRAIN":range(20),"VALIDATION":range(20,28),"TEST":range(28,36)}.items():
        records=[]
        for i in steps:
            label=["NORMAL","BAD","SUSPECT","MISSING"][i%4] if task=="QUALITY_REVIEW" else "NORMAL" if i%2==0 else "BAD"
            records.append({"x":[float(i%2*10)],"y":int(label=="BAD") if label in {"NORMAL","BAD"} else -1,
                "origin_payload":payload(kind,i),"target_payload":payload(kind,i+1),"origin_id":"TEST-"+str(i),"target_id":"TEST-"+str(i+1),
                "event_id":"TEST-EVENT-"+str(i//4),"human_quality_label":label,
                "forecast_origin":(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat(),
                "rule_qc":{"flag":"NOT_EVALUATED" if label=="MISSING" else "NORMAL" if label=="SUSPECT" else label,"rule_version":"TEST"}})
        rows[split]=records
    return {"rows":rows,"manifest":{"task":task,"quantity_kind":kind,"feature_ids":["test-value"],"ridge_alphas":[.1,1.],
                "refit_train_validation":False,"normal_quantiles":[.8,.95]},"evidence_mode":"SYNTHETIC_TEST_ONLY",
            "manifest_sha256":"TEST","snapshot_hashes":{},"origin_membership_sha256":"TEST","coverage":{}}


@pytest.mark.parametrize("kind",["SCALAR","CIRCULAR_DEGREES","SIGNED_RADIAL","VECTOR_UV","PROFILE_BINS","TRAJECTORY"])
def test_typed_forecast_runs_and_exact_numeric_serving_matches(kind):
    p=typed_prepared(kind);result=compare_typed(p)
    row=p["rows"]["TEST"][0]
    actual=predict_artifact(result["artifact"],row["x"],row["origin_payload"])["prediction"]
    assert np.allclose(actual,result["paired_test_predictions"][0]["prediction"])
    assert result["test_metrics"]["ridge"]["sample_count"]==8
    assert result["deployed_models"]==0


def test_profile_channel_unit_and_circular_bin_metrics():
    p=payload("PROFILE_BINS",0);p.update(target_variable="current_direction",unit="degree",value_representation="CIRCULAR_DEGREES",values=[359.,1.])
    q=copy.deepcopy(p);q["values"]=[1.,359.]
    m=typed_metrics([validate_payload(p)],[validate_payload(q)],"PROFILE_BINS",[p])
    assert m["mae"]==pytest.approx(2.)
    q["unit"]="m/s"
    with pytest.raises(ComparisonBlocked):validate_payload(q)


def test_full_qc_labels_and_exclusions_do_not_become_good():
    result=compare_typed(typed_prepared("SCALAR","QUALITY_REVIEW"))
    qc=result["test_metrics"]["full_qc_review"]
    assert qc["human_label_counts"]==dict(NORMAL=2,BAD=2,SUSPECT=2,MISSING=2)
    assert qc["not_evaluated_count"]==2 and qc["binary_score_evaluation_count"]==4
    assert qc["human_label_rule_flag_confusion"]["MISSING"]["NOT_EVALUATED"]==2
    assert qc["false_good_rate"]==.5 and not qc["source_qc_mutation"]


def test_anomaly_event_metrics_are_observed_and_unadjusted():
    result=compare_typed(typed_prepared("SCALAR","ANOMALY_DETECTION"))
    assert result["test_metrics"]["candidate"]["point_adjustment"] is False
    assert result["test_metrics"]["event_detection"]["unobserved_event_start_not_inferred"] is True


def test_durable_queue_finishes_same_holdout_and_is_idempotent(tmp_path):
    path,authority=queue_fixture(tmp_path/"input");q=DurableQueue(tmp_path/"queue")
    original=(path.parent/"synthetic-raw.bin").read_bytes()
    first=q.enqueue(path,authority);again=q.enqueue(path,authority)
    assert first["job_id"]==again["job_id"] and again["idempotent_reuse"]
    result=q.run_once(authority)
    assert result["status"]=="COMPARISON_COMPLETE_CANDIDATE_ONLY"
    assert result["acceptance"]["status"]=="PASS" and result["registered_models"]==result["deployed_models"]==0
    with q.connect() as db:
        row=db.execute("SELECT * FROM queue_jobs").fetchone()
        assert row["state"]=="COMPLETED_CANDIDATE"
        assert row["receipt_sha256"]==hashlib.sha256(open(row["receipt_path"],"rb").read()).hexdigest()
    assert (path.parent/"synthetic-raw.bin").read_bytes()==original


def test_queued_input_change_is_quarantined_without_overwriting_assets(tmp_path):
    path,authority=queue_fixture(tmp_path/"input");q=DurableQueue(tmp_path/"queue");q.enqueue(path,authority)
    with path.open("a") as stream:stream.write(" ")
    result=q.run_once(authority)
    assert result["status"]=="FAILED_QUARANTINED" and result["reason"]=="QUEUED_INPUT_CHANGED"
    assert (path.parent/"synthetic-raw.bin").exists()


def test_expired_lease_fences_old_worker_and_bounded_retry(tmp_path):
    now=[0.];path,authority=queue_fixture(tmp_path/"input");q=DurableQueue(tmp_path/"queue",lambda:now[0]);q.enqueue(path,authority)
    job=q.claim();now[0]=31;assert q.claim() is None
    with pytest.raises(ComparisonBlocked,match="WORKER_LEASE_FENCED"):q.finish(job,"COMPLETED_CANDIDATE",None)
    with q.connect() as db:assert db.execute("SELECT state FROM queue_jobs").fetchone()[0]=="QUARANTINED"


def test_holdout_protocol_mismatch_and_embargo_fail(tmp_path):
    path,authority=queue_fixture(tmp_path/"input")
    for s in authority.snapshots:authority.snapshots[s]["_protocols"]["SPLIT_PROTOCOL"]["body"]["embargo_seconds"]=999999
    refresh(path,authority)
    with pytest.raises(ComparisonBlocked,match="TEMPORAL_SPLIT_LEAKAGE"):preflight(path,authority)


def temporal_fixture(root,fake_episode=False):
    path,authority=queue_fixture(root)
    for s,a in authority.snapshots.items():
        for r in a["records"]:
            r["station_id"]=r["raw"]["station_id"]="ONE_STATION"
            r["sensor_id"]=r["raw"]["sensor_id"]="ONE_SENSOR"
            r["raw"]["physical_sensor_id"]="ONE_PHYSICAL_SENSOR"
        def change(receipt,s=s):
            for p in receipt["observations"].values():
                p.update(canonical_station_id="ONE_STATION",canonical_sensor_id="ONE_SENSOR",physical_sensor_id="ONE_PHYSICAL_SENSOR",
                    sensor_episode_id="FAKE_EPISODE_"+s if fake_episode else "ONE_ACTUAL_EPISODE",
                    effective_start="2020-01-01T00:00:00Z",effective_end="2020-02-01T00:00:00Z")
        mutate_receipt(path,authority,s,change)
        sp=a["_protocols"]["SPLIT_PROTOCOL"]
        sp["body"].update(split_strategy="temporal_with_purge",disjoint_groups=["EVENT","SOURCE_RECORD","DOCUMENT_FAMILY"])
        sp["sha256"]=hashlib.sha256(canonical_bytes(sp["body"])).hexdigest()
    refresh(path,authority)
    return path,authority


def test_explicit_temporal_protocol_allows_same_real_sensor_episode(tmp_path):
    path,authority=temporal_fixture(tmp_path/"input")
    p=preflight(path,authority)
    assert len(p["rows"]["TEST"])==11


def test_fake_episode_ids_cannot_hide_overlapping_sensor_validity(tmp_path):
    path,authority=temporal_fixture(tmp_path/"input",True)
    with pytest.raises(ComparisonBlocked,match="PHYSICAL_SENSOR_OVERLAPPING_EPISODE_IDENTITIES"):preflight(path,authority)


def test_ancestor_junction_cannot_hide_request_or_source_path(tmp_path):
    import os,subprocess
    path,authority=queue_fixture(tmp_path/"real")
    alias=tmp_path/"alias"
    if os.name=="nt":
        result=subprocess.run(["cmd","/c","mklink","/J",str(alias),str(path.parent)],capture_output=True)
        if result.returncode:pytest.skip("Host does not allow junction creation")
    else:alias.symlink_to(path.parent,target_is_directory=True)
    with pytest.raises(ComparisonBlocked,match="REPARSE_PATH_FORBIDDEN"):preflight(alias/path.name,authority)
    with pytest.raises(ComparisonBlocked,match="REPARSE_PATH_FORBIDDEN"):DurableQueue(alias/"worker")


def test_coverage_exact_72_keys_is_partial_representation_scope():
    coverage=adapter_coverage();assert coverage["task_keys"]==72 and coverage["operational_completion"] is False
    assert len({(r["domain"],r["item_id"],r["task"]) for r in coverage["rows"]})==72
    assert {r["code_status"] for r in coverage["rows"]}=={"REPRESENTATION_BASELINE_SCOPE_PARTIAL"}


def test_serving_malformed_coefficients_are_structured_blocked():
    with pytest.raises(ComparisonBlocked,match="SERVING_NUMERIC_ARTIFACT_INVALID"):
        predict_artifact({"schema_version":"typed-ridge-json-1","features":["x"],"representation":"SCALAR"},[1.],payload("SCALAR",1))


def test_independent_review_registration_actual_numeric_serving_and_revocation(tmp_path,monkeypatch):
    """Synthetic source adapter with actual isolated approvals, never the live DB."""
    import app.ml.comparison_runner as runner
    from app.ml.candidate_authority import verified_worker_receipt,register_candidate
    from app.ml.serving import deploy,health,deployment_identity,scope_key,rollback_previous
    from app.models.domain import DatasetRegistry,ModelRegistry
    monkeypatch.setenv("OCEAN_MLOPS_ROOT",str(tmp_path/"runtime"))
    monkeypatch.setenv("OCEAN_LOCAL_MODEL_SERVING_ENABLED","1")
    path,authority=queue_fixture(tmp_path/"input")
    monkeypatch.setattr(runner,"DatabaseAuthority",lambda *a:authority)
    import app.ml.candidate_authority as candidate_authority
    monkeypatch.setattr(candidate_authority,"DatabaseAuthority",lambda *a:authority)
    q=DurableQueue(tmp_path/"runtime"/"worker");job=q.enqueue(path,authority);result=q.run_once(authority)
    with q.connect() as ledger:receipt=ledger.execute("SELECT receipt_path FROM queue_jobs WHERE job_id=?",(job["job_id"],)).fetchone()[0]
    engine=create_engine("sqlite://");Base.metadata.create_all(engine)
    with Session(engine) as db:
        for s,a in authority.snapshots.items():
            db.add(DatasetRegistry(dataset_id=a["dataset_id"],dataset_name=a["dataset_name"],dataset_version=s,
                dataset_split=s,station_scope=["SYNTHETIC"],sensor_scope=["SYNTHETIC"],variable_scope=["FIXTURE_TEMPERATURE"],
                period_start=datetime.fromisoformat(a["period_start"]),period_end=datetime.fromisoformat(a["period_end"]),
                feature_version=a["feature_version"],label_version=a["label_version"],preprocessing_version=a["preprocessing_version"]))
        db.commit()
        report,sha,_=verified_worker_receipt(db,receipt,replay=True)
        with pytest.raises(ComparisonBlocked,match="MODEL_INDEPENDENT_REVIEW_APPROVAL_MISSING"):register_candidate(db,receipt,"SYNTHETIC-1")
        db.add(ApprovalHistory(approval_type="MODEL_INDEPENDENT_REVIEW",target_id="SYNTHETIC-1",approval_status="APPROVED",approved_by="SYNTHETIC-TEST-ACTOR",comment="snapshot_sha256="+sha));db.commit()
        model=register_candidate(db,receipt,"SYNTHETIC-1")
        assert model.status=="PENDING_APPROVAL" and not model.is_champion
        model.status="APPROVED";db.commit()
        with pytest.raises(ComparisonBlocked,match="MODEL_DEPLOY_APPROVAL_MISSING"):deploy(db,model)
        identity=deployment_identity(model,sha,report["artifact_sha256"]);exact=digest(identity)
        db.add(ApprovalHistory(approval_type="MODEL_DEPLOY",target_id=model.model_version,approval_status="APPROVED",approved_by="SYNTHETIC-TEST-ACTOR",comment="snapshot_sha256="+exact));db.commit()
        receipt=deploy(db,model);probe=health(db,scope_key(identity))
        assert probe["healthy"] and probe["numerical_probe_executed"] and model.status=="PRODUCTION"
        assert probe["full_api_p95_status"]=="NOT_MEASURED"
        import app.ml.job_queue as worker_queue
        with monkeypatch.context() as m:
            m.setattr(worker_queue,"code_fingerprint",lambda:"0"*64)
            with pytest.raises(ComparisonBlocked,match="CANDIDATE_EXECUTION_CODE_CHANGED_REVIEW_REQUIRED"):health(db,scope_key(identity))
        # A distinct committed run creates a separately reviewed candidate.
        manifest=json.loads(path.read_text());manifest["repeat_request_notice"]="SYNTHETIC_SECOND_COMMITTED_RUN";write_json(path,manifest)
        # The first model retains an immutable request file; changing its path
        # would correctly invalidate the existing candidate's source preflight.
        first_manifest=path.parent/"first-immutable-request.json"
        first_body=copy.deepcopy(manifest);first_body.pop("repeat_request_notice");write_json(first_manifest,first_body)
        # Restore first report's original manifest bytes at its referenced path,
        # and create a new request path for the second run instead.
        second_manifest=path.parent/"second-request.json";write_json(second_manifest,manifest)
        write_json(path,first_body)
        second_job=q.enqueue(second_manifest,authority);second_result=q.run_once(authority)
        with q.connect() as ledger:second_path=ledger.execute("SELECT receipt_path FROM queue_jobs WHERE job_id=?",(second_job["job_id"],)).fetchone()[0]
        second_report,second_sha,_=verified_worker_receipt(db,second_path,replay=True)
        db.add(ApprovalHistory(approval_type="MODEL_INDEPENDENT_REVIEW",target_id="SYNTHETIC-2",approval_status="APPROVED",approved_by="SYNTHETIC-TEST-ACTOR",comment="snapshot_sha256="+second_sha));db.commit()
        second=register_candidate(db,second_path,"SYNTHETIC-2");second.status="APPROVED";db.commit()
        second_identity=deployment_identity(second,second_sha,second_report["artifact_sha256"])
        db.add(ApprovalHistory(approval_type="MODEL_DEPLOY",target_id=second.model_version,approval_status="APPROVED",approved_by="SYNTHETIC-TEST-ACTOR",comment="snapshot_sha256="+digest(second_identity)));db.commit()
        pointer=tmp_path/"runtime"/"serving"/(scope_key(identity)+".json")
        original_pointer=pointer.read_bytes()
        commit=db.commit
        def failed_commit():raise RuntimeError("SYNTHETIC_DATABASE_COMMIT_FAILURE")
        with monkeypatch.context() as m:
            m.setattr(db,"commit",failed_commit)
            with pytest.raises(RuntimeError,match="SYNTHETIC_DATABASE_COMMIT_FAILURE"):deploy(db,second)
        assert pointer.read_bytes()==original_pointer and model.is_champion and second.status=="APPROVED"
        deploy(db,second)
        assert second.is_champion and model.status=="ARCHIVED"
        second_pointer=pointer.read_bytes()
        with pytest.raises(ComparisonBlocked,match="MODEL_ROLLBACK_APPROVAL_MISSING"):rollback_previous(db,second)
        assert pointer.read_bytes()==second_pointer and second.is_champion and model.status=="ARCHIVED"
        db.add(ApprovalHistory(approval_type="MODEL_ROLLBACK",target_id=model.model_version,approval_status="APPROVED",approved_by="SYNTHETIC-TEST-ACTOR",comment="snapshot_sha256="+exact));db.commit()
        restored=rollback_previous(db,second)
        assert restored["operation"]=="ROLLBACK" and model.is_champion and second.status=="ARCHIVED"
        assert health(db,scope_key(identity))["identity"]==identity
        db.add(ApprovalHistory(approval_type="MODEL_DEPLOY",target_id=model.model_version,approval_status="REVOKED",approved_by="SYNTHETIC-TEST-ACTOR",comment="snapshot_sha256="+exact));db.commit()
        # The active receipt is a rollback, so its own latest authority controls serving.
        db.add(ApprovalHistory(approval_type="MODEL_ROLLBACK",target_id=model.model_version,approval_status="REVOKED",approved_by="SYNTHETIC-TEST-ACTOR",comment="snapshot_sha256="+exact));db.commit()
        with pytest.raises(ComparisonBlocked,match="MODEL_ROLLBACK_APPROVAL_MISSING"):health(db,scope_key(identity))
        # The numeric artifact survives revocation; the active read refuses it.
        assert Path(model.artifact_path).exists()
    engine.dispose()
