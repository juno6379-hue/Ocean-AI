"""Fail-closed comparison on hash-bound reviewed v2 source/dataset/protocols.

V1 snapshots remain blocked. Numeric JSON candidates need a separately authorized
independent review and deployment; no uploaded executable or legacy weight is loaded.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import sklearn
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.evaluator import regression_metrics

SCHEMA = "scalar-forecast-comparison-1"
SPLITS = ("TRAIN", "VALIDATION", "TEST")
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_SAMPLES = 250_000


class ComparisonBlocked(ValueError):
    """An evidence/contract failure, never a retryable training error."""

    def __init__(self, code, detail=""):
        self.code = code
        self.detail = str(detail)
        super().__init__(code + (": " + self.detail if detail else ""))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, default=str).encode("utf-8")).hexdigest()


def read_json(path):
    try:
        return _read_json(path)
    except ComparisonBlocked:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ComparisonBlocked("INPUT_JSON_INVALID_OR_UNREADABLE", type(exc).__name__) from exc


def _read_json(path):
    """Read only bounded, stable JSON, rejecting duplicate keys and nonfinite literals."""
    path = Path(path)
    reject_reparse(path)
    before = path.stat()
    if not path.is_file() or before.st_size > MAX_JSON_BYTES or path.is_symlink():
        raise ComparisonBlocked("INPUT_NOT_BOUNDED_REGULAR_JSON", str(path))
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ComparisonBlocked("INPUT_CHANGED_DURING_READ", str(path))

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ComparisonBlocked("DUPLICATE_JSON_KEY", key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ComparisonBlocked("NONFINITE_JSON_LITERAL", value)

    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
        parse_constant=invalid_constant), hashlib.sha256(raw).hexdigest()


def clock(value, external=False):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise ComparisonBlocked("INVALID_CLOCK", value)
    if parsed.tzinfo is None:
        if external:
            raise ComparisonBlocked("CLOCK_OFFSET_REQUIRED", value)
        # Existing database snapshot fields are explicitly named timestamp_utc.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ComparisonBlocked("NONFINITE_NUMERIC_INPUT", name)
    return float(value)


def hash_file(path, expected):
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ComparisonBlocked("INVALID_SOURCE_DIGEST", str(path))
    path = Path(path)
    reject_reparse(path)
    if not path.is_file() or path.is_symlink():
        raise ComparisonBlocked("SOURCE_FILE_MISSING", str(path))
    before = path.stat()
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ComparisonBlocked("SOURCE_FILE_CHANGED", str(path))
    if actual != expected:
        raise ComparisonBlocked("SOURCE_HASH_MISMATCH", str(path))


def reject_reparse(path):
    """Reject links/junctions at the file and every existing ancestor."""
    import stat
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if not part.exists() and not part.is_symlink(): continue
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ComparisonBlocked("REPARSE_PATH_FORBIDDEN", str(part))


class DatabaseAuthority:
    """Read-only adapter to the existing approval ledger, not an approval service."""
    evidence_mode = "LIVE_READ_ONLY_DATASET_AUTHORITY"

    def __init__(self, db, snapshot_root):
        self.db = db
        reject_reparse(snapshot_root)
        self.snapshot_root = Path(snapshot_root).resolve()

    def snapshot(self, reference, split):
        from app.models.domain import DatasetRegistry, ApprovalHistory
        from app.models.evidence import DatasetMembership
        from app.api.routes_datasets import _dataset_content

        dataset = self.db.get(DatasetRegistry, reference["dataset_id"])
        if dataset is None:
            raise ComparisonBlocked("APPROVED_DATASET_NOT_FOUND", reference["dataset_id"])
        approval = self.db.query(ApprovalHistory).filter_by(approval_type="DATASET",
            target_id=dataset.dataset_id).order_by(ApprovalHistory.id.desc()).first()
        if not (dataset.status == "APPROVED" and dataset.approved_by and approval
                and approval.approval_status == "APPROVED"
                and approval.approved_by == dataset.approved_by
                and approval.comment == "snapshot_sha256=" + (dataset.data_hash or "")):
            raise ComparisonBlocked("DATASET_APPROVAL_MISSING", dataset.dataset_id)
        if dataset.dataset_split != split or dataset.data_hash != reference["sha256"]:
            raise ComparisonBlocked("FIXED_SNAPSHOT_REFERENCE_MISMATCH", dataset.dataset_id)
        path = self.snapshot_root / (reference["sha256"] + ".json")
        if not path.resolve().is_relative_to(self.snapshot_root):
            raise ComparisonBlocked("SNAPSHOT_PATH_OUTSIDE_ROOT")
        snapshot, actual = read_json(path)
        if actual != dataset.data_hash:
            raise ComparisonBlocked("APPROVED_SNAPSHOT_HASH_MISMATCH", dataset.dataset_id)
        members = self.db.query(DatasetMembership).filter_by(dataset_id=dataset.dataset_id).all()
        stored = {(r.observation_id, r.label_id, r.event_id, r.snapshot_hash) for r in members}
        expected = {(r["id"], r["label"]["label_id"], r["event_id"], dataset.data_hash)
                    for r in snapshot.get("records", [])}
        if stored != expected or len(members) != len(snapshot.get("records", [])):
            raise ComparisonBlocked("FROZEN_MEMBERSHIP_MISMATCH", dataset.dataset_id)
        # The current builder has no reviewed source-contract dependency freeze.
        # Refusing it here prevents receipt.json's self-declared APPROVED from
        # becoming human approval of a dataset outside the approved content hash.
        if not snapshot.get("source_contracts"):
            raise ComparisonBlocked("SOURCE_CONTRACT_NOT_FROZEN_IN_DATASET",
                "Legacy dataset snapshots lack reviewed unit/QC/physical-sensor/period/as-of dependencies")
        _, rebuilt, counts = _dataset_content(self.db, dataset)
        if digest(rebuilt) != dataset.data_hash or counts.get("UNREVIEWED") or rebuilt["validation_errors"]:
            raise ComparisonBlocked("LIVE_LINEAGE_CHANGED_OR_UNREVIEWED", dataset.dataset_id)
        from app.services.source_contract_authority import verify_approved_receipt, SourceContractError
        for dependency in snapshot["source_contracts"]:
            reject_reparse(Path(snapshot["source_contract_root"]) / dependency["path"])
            dependency_path = (Path(snapshot["source_contract_root"]) / dependency["path"]).resolve()
            if not dependency_path.is_relative_to(Path(snapshot["source_contract_root"]).resolve()):
                raise ComparisonBlocked("SOURCE_CONTRACT_PATH_INVALID")
            receipt, sha = read_json(dependency_path)
            if sha != dependency["sha256"]:
                raise ComparisonBlocked("SOURCE_CONTRACT_HASH_MISMATCH")
            try:
                verify_approved_receipt(self.db, receipt, sha)
            except SourceContractError as exc:
                raise ComparisonBlocked("SOURCE_CONTRACT_AUTHORITY_INVALID", str(exc)) from exc
        from app.ml.protocols import frozen_protocols
        snapshot["_protocols"] = frozen_protocols(self.db, snapshot)
        snapshot["_source_authority_verified"] = True
        snapshot["_approval_actor"] = dataset.approved_by
        return snapshot


def _proofs(snapshot, input_root):
    dependencies = snapshot.get("source_contracts")
    if not dependencies:
        raise ComparisonBlocked("SOURCE_CONTRACT_NOT_FROZEN_IN_DATASET")
    # A future dependency freezer must bind this root in the approved snapshot;
    # callers must not have to duplicate terabytes under a small request file.
    if snapshot.get("source_contract_root"):
        configured = Path(snapshot["source_contract_root"])
        if not configured.is_absolute():
            raise ComparisonBlocked("SOURCE_CONTRACT_ROOT_NOT_ABSOLUTE")
        input_root = configured.resolve()
    proofs = {}
    for dep in dependencies:
        reject_reparse(input_root / dep["path"])
        path = (input_root / dep["path"]).resolve()
        if not path.is_relative_to(input_root):
            raise ComparisonBlocked("CONTRACT_PATH_OUTSIDE_INPUT_ROOT")
        receipt, sha = read_json(path)
        if sha != dep["sha256"]:
            raise ComparisonBlocked("SOURCE_CONTRACT_HASH_MISMATCH")
        if (receipt.get("schema_version") != "source-semantics-identity-period-event-1"
                or receipt.get("status") != "APPROVED" or receipt.get("approval_complete") is not True
                or not receipt.get("approved_by") or (not snapshot.get("_source_authority_verified") and receipt.get("approved_by") != snapshot.get("_approval_actor"))
                or receipt.get("validation_errors") != []):
            raise ComparisonBlocked("SOURCE_CONTRACT_REVIEW_INCOMPLETE")
        policy = receipt.get("source_availability_policy")
        if policy not in {"RAW_AND_TRANSFORM_REQUIRED", "APPROVED_TRANSFORM_ONLY"}:
            raise ComparisonBlocked("SOURCE_AVAILABILITY_POLICY_NOT_REVIEWED")
        files = receipt.get("files", [])
        if not files or not any(f.get("role") == "PARQUET" for f in files):
            raise ComparisonBlocked("TRANSFORM_SOURCE_PROOF_MISSING")
        for file in files:
            if file.get("role") not in {"RAW", "PARQUET", "QC_CODEBOOK", "SOURCE_MANIFEST", "EVIDENCE", "DOCUMENT", "SCHEMA", "SENSOR_METADATA", "SOURCE_TRANSFORM"}:
                raise ComparisonBlocked("UNSUPPORTED_SOURCE_ROLE")
            if (file["role"] == "RAW" and policy == "APPROVED_TRANSFORM_ONLY" and file.get("availability") == "ORIGINAL_DELETED" and file.get("path") is None):
                continue
            roots = [Path(p).resolve() for p in snapshot.get("verified_source_roots", [str(input_root)])]
            file_base = roots[0] if snapshot.get("schema_version") == "event-evidence-dataset-2" else input_root
            reject_reparse(file_base / file["path"])
            file_path = (file_base / file["path"]).resolve()
            if not any(file_path.is_relative_to(r) for r in roots):
                raise ComparisonBlocked("SOURCE_PATH_OUTSIDE_INPUT_ROOT")
            hash_file(file_path, file["sha256"])
        if policy == "RAW_AND_TRANSFORM_REQUIRED" and not any(f.get("role") == "RAW" for f in files):
            raise ComparisonBlocked("RAW_SOURCE_PROOF_MISSING")
        for oid, proof in receipt.get("observations", {}).items():
            if oid in proofs:
                raise ComparisonBlocked("AMBIGUOUS_SOURCE_CONTRACT", oid)
            raw_hashes = {f["sha256"] for f in files if f["role"] == "RAW"}
            parquet_hashes = {f["sha256"] for f in files if f["role"] == "PARQUET"}
            codebook_hashes = {f["sha256"] for f in files if f["role"] == "QC_CODEBOOK"}
            if proof.get("source_qc_codebook_sha256") not in codebook_hashes:
                raise ComparisonBlocked("QC_CODEBOOK_HASH_NOT_IN_CONTRACT", oid)
            if proof.get("source_sha256") not in raw_hashes or proof.get("parquet_sha256") not in parquet_hashes:
                raise ComparisonBlocked("OBSERVATION_SOURCE_HASH_NOT_IN_CONTRACT", oid)
            proofs[oid] = {**proof, "source_availability_policy": policy}
    return proofs


def _validate_proof(record, proof, snapshot):
    required = ("physical_sensor_id", "sensor_episode_id", "source_group", "source_item_code",
        "source_station_code", "source_month", "source_row_locator", "timezone", "source_clock_semantics", "qc_rule_version", "event_id")
    if any(not isinstance(proof.get(k), str) or not proof[k].strip() for k in required):
        raise ComparisonBlocked("INCOMPLETE_OBSERVATION_IDENTITY", record["id"])
    if proof.get("validation_errors") != [] or proof["source_clock_semantics"] != "OBSERVED_AT":
        raise ComparisonBlocked("OBSERVATION_SEMANTICS_UNREVIEWED", record["id"])
    try:
        ZoneInfo(proof["timezone"])
    except ZoneInfoNotFoundError:
        raise ComparisonBlocked("SOURCE_TIMEZONE_UNDEFINED", record["id"])
    for key in ("source_sha256", "parquet_sha256", "source_qc_codebook_sha256"):
        sha = proof.get(key, "")
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ComparisonBlocked("OBSERVATION_LINEAGE_HASH_MISSING", record["id"])
    depth = proof.get("depth")
    if not isinstance(depth, dict) or set(depth) != {"step", "from", "to"}:
        raise ComparisonBlocked("DEPTH_REPRESENTATION_MISSING", record["id"])
    raw = record.get("raw") or {}
    if not raw.get("source_station_code"):
        raise ComparisonBlocked("SOURCE_STATION_LITERAL_NOT_FROZEN", record["id"])
    if proof["source_station_code"] != raw["source_station_code"]:
        raise ComparisonBlocked("SOURCE_STATION_LITERAL_MISMATCH", record["id"])
    if snapshot.get("schema_version") == "event-evidence-dataset-2":
        for field in ("source_station_literal", "source_item_literal", "source_identifier_transform"):
            if field not in raw or raw[field] != proof.get(field):
                raise ComparisonBlocked("SOURCE_IDENTIFIER_LITERAL_TRANSFORM_NOT_FROZEN", field)
    for key in ("source_row_locator", "source_sha256", "parquet_sha256", "source_timezone_name", "source_clock_semantics", "physical_sensor_id"):
        expected_key = "timezone" if key == "source_timezone_name" else key
        if not raw.get(key) or raw[key] != proof.get(expected_key):
            raise ComparisonBlocked("FROZEN_SOURCE_LINEAGE_MISSING_OR_MISMATCH", record["id"] + ":" + key)
    if proof["source_group"] != raw.get("source_system"):
        raise ComparisonBlocked("SOURCE_NAMESPACE_MISMATCH", record["id"])
    if proof.get("canonical_station_id") != record["station_id"] or proof.get("canonical_sensor_id") != record["sensor_id"]:
        raise ComparisonBlocked("SOURCE_CANONICAL_ID_BINDING_MISMATCH", record["id"])
    if any(raw.get(k) != record.get(k) for k in ("station_id", "sensor_id", "variable_code")):
        raise ComparisonBlocked("RAW_STANDARD_IDENTITY_MISMATCH", record["id"])
    if clock(raw.get("timestamp_utc"), True) != clock(record.get("timestamp"), True):
        raise ComparisonBlocked("RAW_STANDARD_CLOCK_MISMATCH", record["id"])
    if proof.get("source_unit") != raw.get("value_unit"):
        raise ComparisonBlocked("SOURCE_UNIT_CONTRACT_MISMATCH", record["id"])
    raw_depth = {"step": raw.get("water_step"), "from": raw.get("from_depth"), "to": raw.get("to_depth")}
    if depth != raw_depth or any(type(depth[k]) is not type(raw_depth[k]) for k in depth):
        raise ComparisonBlocked("SOURCE_DEPTH_MISMATCH", record["id"])
    from app.services.source_contract_review import exact_scope_key
    source_month = clock(record["timestamp"], True).astimezone(ZoneInfo(proof["timezone"])).strftime("%Y-%m")
    scope_key = exact_scope_key({"source_group": proof["source_group"], "station_code": proof["source_station_code"],
        "item_code": proof["source_item_code"], "depth_step": depth["step"], "depth_from": depth["from"], "depth_to": depth["to"], "month": source_month})
    if proof["source_month"] != source_month or proof.get("exact_scope_key") != scope_key:
        raise ComparisonBlocked("EXACT_SOURCE_SCOPE_KEY_MISMATCH", record["id"])
    if proof["event_id"] != record.get("event_id") or proof.get("unit") != record.get("unit"):
        raise ComparisonBlocked("SOURCE_EVENT_OR_UNIT_MISMATCH", record["id"])
    if proof.get("standard_variable") != record.get("variable_code") or proof["qc_rule_version"] != snapshot.get("qc_rule_version"):
        raise ComparisonBlocked("SOURCE_VARIABLE_OR_QC_VERSION_MISMATCH", record["id"])
    if raw.get("source_item_code") != proof["source_item_code"] or raw.get("physical_sensor_id") != proof["physical_sensor_id"]:
        raise ComparisonBlocked("PHYSICAL_SENSOR_OR_SOURCE_ITEM_MISMATCH", record["id"])
    if (proof.get("source_qc_raw") != raw.get("qc_flag") or proof.get("source_mqc_raw") != raw.get("mqc_flag")
            or type(proof.get("source_qc_raw")) is not type(raw.get("qc_flag"))
            or type(proof.get("source_mqc_raw")) is not type(raw.get("mqc_flag"))):
        raise ComparisonBlocked("SOURCE_QC_RAW_VALUE_CHANGED", record["id"])
    if proof.get("training_value_status") != "ACCEPTED":
        raise ComparisonBlocked("TRAINING_VALUE_NOT_REVIEWED", record["id"])
    t = clock(record["timestamp"], True)
    start, end = clock(proof.get("effective_start"), True), clock(proof.get("effective_end"), True)
    if not start <= t < end:
        raise ComparisonBlocked("SENSOR_EPISODE_PERIOD_MISMATCH", record["id"])
    if not clock(proof.get("qc_effective_start"), True) <= t < clock(proof.get("qc_effective_end"), True):
        raise ComparisonBlocked("QC_RULE_PERIOD_MISMATCH", record["id"])
    clock(proof.get("available_at"), True)
    clock(proof.get("qc_available_at"), True)
    if raw.get("receive_time") and clock(raw["receive_time"], True) > clock(proof["available_at"], True):
        raise ComparisonBlocked("OBSERVATION_AVAILABLE_BEFORE_RECEIVED", record["id"])


def _preflight(manifest_path, authority):
    """Derive all eligible forecast origins from each fixed snapshot, never ratio splits."""
    reject_reparse(manifest_path)
    manifest_path = Path(manifest_path).resolve()
    manifest, manifest_sha = read_json(manifest_path)
    if manifest.get("schema_version") not in {SCHEMA, "typed-model-comparison-2"} or manifest.get("task") not in {"FORECASTING", "ANOMALY_DETECTION", "QUALITY_REVIEW"}:
        raise ComparisonBlocked("UNSUPPORTED_TASK_ADAPTER")
    if manifest.get("schema_version") == SCHEMA and (manifest.get("data_domain") != "SCALAR" or manifest["task"] != "FORECASTING"):
        raise ComparisonBlocked("LEGACY_ADAPTER_SCALAR_FORECAST_ONLY")
    if manifest.get("schema_version") == "typed-model-comparison-2":
        from app.ml.adapter_registry import adapter_coverage
        candidates = [r for r in adapter_coverage()["rows"] if (r["domain"], r["item_id"], r["runtime_task"]) == (manifest.get("domain"), manifest.get("item_id"), manifest["task"])]
        if len(candidates) != 1 or candidates[0]["quantity_kind"] != manifest.get("quantity_kind"):
            raise ComparisonBlocked("TASK_DOMAIN_TYPED_ADAPTER_CONTRACT_MISMATCH")
        if manifest["quantity_kind"] == "PROFILE_BINS" and manifest.get("target_variable") not in candidates[0]["supported_target_channels"]:
            raise ComparisonBlocked("PROFILE_EXPLICIT_SINGLE_TARGET_CHANNEL_REQUIRED")
        if manifest.get("domain") == "drifter" and (manifest.get("target_variable") != "position" or manifest.get("unit") != "meter_spherical_endpoint"):
            raise ComparisonBlocked("TRAJECTORY_POSITION_ENDPOINT_SCOPE_REQUIRED")
    if manifest.get("acceptance_criteria_status") != "NOT_DEFINED":
        raise ComparisonBlocked("OPERATING_SELECTION_NOT_IMPLEMENTED")
    if set(manifest.get("splits", {})) != set(SPLITS):
        raise ComparisonBlocked("THREE_FIXED_APPROVED_SPLITS_REQUIRED")
    if manifest.get("locked_holdout_sha256") != manifest["splits"]["TEST"].get("sha256"):
        raise ComparisonBlocked("LOCKED_HOLDOUT_MISMATCH")
    horizon = manifest.get("horizon_seconds")
    pointwise = manifest["task"] != "FORECASTING"
    if isinstance(horizon, bool) or not isinstance(horizon, int) or (horizon != 0 if pointwise else horizon <= 0):
        raise ComparisonBlocked("EXPLICIT_POSITIVE_HORIZON_REQUIRED")
    features = manifest.get("feature_ids")
    if not isinstance(features, list) or not features or len(features) != len(set(features)) or any(not isinstance(f, str) or not f for f in features):
        raise ComparisonBlocked("FIXED_FEATURE_IDS_REQUIRED")
    alphas = manifest.get("ridge_alphas", [1.0] if pointwise else None)
    if not isinstance(alphas, list) or not alphas or len(alphas) > 16:
        raise ComparisonBlocked("BOUNDED_CANDIDATE_CONFIGURATION_REQUIRED")
    alphas = [finite(a, "ridge_alpha") for a in alphas]
    if any(a <= 0 for a in alphas) or len(set(alphas)) != len(alphas):
        raise ComparisonBlocked("INVALID_RIDGE_ALPHA")
    if not isinstance(manifest.get("refit_train_validation"), bool):
        raise ComparisonBlocked("REFIT_POLICY_REQUIRED")
    rows, snapshots, events_by_split, episodes_by_split, documents_by_split, stations_by_split = {}, {}, {}, {}, {}, {}
    protocol_digests = None
    all_ids, all_keys, all_source_rows, versions, family = set(), set(), set(), None, None
    typed_component_splits = {}
    episode_contracts, physical_episode_intervals = {}, {}
    previous_end = None
    for split in SPLITS:
        reference = manifest["splits"][split]
        snapshot = authority.snapshot(reference, split)
        protocols = snapshot.get("_protocols")
        if protocols:
            protocol_ids = {k: v["sha256"] for k, v in protocols.items()}
            if protocol_digests is not None and protocol_ids != protocol_digests:
                raise ComparisonBlocked("SPLIT_PROTOCOL_DEPENDENCIES_DIFFER")
            protocol_digests = protocol_ids
            sp, ep = protocols["SPLIT_PROTOCOL"]["body"], protocols["EVALUATION_PROTOCOL"]["body"]
            if sp["dataset_ids"][split] != reference["dataset_id"] or digest(sorted(r["id"] for r in snapshot["records"])) != sp["member_ids_sha256"][split]:
                raise ComparisonBlocked("FIXED_PROTOCOL_MEMBERSHIP_MISMATCH")
            if clock(sp["periods"][split]["start"], True) != clock(snapshot["period_start"], True) or clock(sp["periods"][split]["end"], True) != clock(snapshot["period_end"], True):
                raise ComparisonBlocked("PROTOCOL_DATASET_PERIOD_MISMATCH")
            for field in ("task", "domain", "item_id", "quantity_kind", "target_variable", "unit", "horizon_seconds", "lookback_seconds", "feature_ids"):
                if manifest.get(field) != ep.get(field):
                    raise ComparisonBlocked("EVALUATION_MANIFEST_NOT_APPROVED", field)
            for role in ("SPLIT_PROTOCOL", "ACCEPTANCE_POLICY"):
                for field in ("task", "domain", "item_id", "quantity_kind", "target_variable", "unit"):
                    if protocols[role]["body"].get(field) != manifest.get(field):
                        raise ComparisonBlocked("PROTOCOL_TASK_SCOPE_MISMATCH", role + ":" + field)
            if pointwise and manifest.get("normal_quantiles") != ep.get("normal_quantiles"):
                raise ComparisonBlocked("APPROVED_THRESHOLD_CANDIDATES_MISMATCH")
            if manifest["refit_train_validation"] != (ep["preprocessing_fit"] == "TRAIN_VALIDATION_REFIT"):
                raise ComparisonBlocked("APPROVED_REFIT_POLICY_MISMATCH")
            if manifest.get("ridge_alphas") != ep.get("ridge_alphas") and not pointwise:
                raise ComparisonBlocked("APPROVED_CANDIDATE_CONFIGURATION_MISMATCH")
        snapshots[split] = snapshot
        if snapshot.get("split") != split or snapshot.get("validation_errors") != []:
            raise ComparisonBlocked("SNAPSHOT_SPLIT_OR_VALIDATION_INVALID", split)
        if snapshot.get("clock_contract") != "UTC_WITH_EXPLICIT_OFFSET":
            raise ComparisonBlocked("SNAPSHOT_CLOCK_CONTRACT_NOT_FROZEN", split)
        current_versions = tuple(snapshot.get(k) for k in ("feature_version", "label_version", "preprocessing_version", "qc_rule_version"))
        if not all(current_versions) or (versions and current_versions != versions):
            raise ComparisonBlocked("SPLIT_VERSION_MISMATCH")
        if family and snapshot["dataset_name"] != family:
            raise ComparisonBlocked("SPLIT_FAMILY_MISMATCH")
        versions, family = current_versions, snapshot["dataset_name"]
        start, end = clock(snapshot["period_start"], True), clock(snapshot["period_end"], True)
        embargo = protocols["SPLIT_PROTOCOL"]["body"]["embargo_seconds"] if protocols else 0
        if start >= end or (previous_end and start < previous_end + timedelta(seconds=embargo)):
            raise ComparisonBlocked("TEMPORAL_SPLIT_LEAKAGE", split)
        previous_end = end
        proofs = _proofs(snapshot, manifest_path.parent)
        records = snapshot.get("records", [])
        if not records or len(records) > MAX_SAMPLES:
            raise ComparisonBlocked("SNAPSHOT_EMPTY_OR_ADAPTER_CAPACITY_EXCEEDED", split)
        lookup = {}
        own_ids = {r["id"] for r in records}
        source_by_id = {r["id"]: r for r in records}
        events_by_split[split], episodes_by_split[split] = set(), set()
        documents_by_split[split] = set()
        stations_by_split[split] = set()
        for record in records:
            oid = record["id"]
            if oid in all_ids:
                raise ComparisonBlocked("OBSERVATION_MEMBERSHIP_OVERLAP", oid)
            all_ids.add(oid)
            key = (record["station_id"], record["sensor_id"], record["variable_code"], clock(record["timestamp"], True))
            if key in all_keys:
                raise ComparisonBlocked("DUPLICATE_OBSERVATION_GRAIN", oid)
            all_keys.add(key)
            if not start <= key[3] < end or record.get("validation_errors") != []:
                raise ComparisonBlocked("RECORD_OUTSIDE_APPROVED_PERIOD", oid)
            if record.get("variable_code") != manifest.get("target_variable") or record.get("unit") != manifest.get("unit"):
                raise ComparisonBlocked("MIXED_TARGET_VARIABLE_OR_UNIT", oid)
            if oid not in proofs:
                raise ComparisonBlocked("SOURCE_CONTRACT_COVERAGE_MISSING", oid)
            _validate_proof(record, proofs[oid], snapshot)
            proof = proofs[oid]
            episode = proof["sensor_episode_id"]
            binding = (proof["physical_sensor_id"], record["station_id"], record["sensor_id"],
                clock(proof["effective_start"], True), clock(proof["effective_end"], True))
            if episode in episode_contracts and episode_contracts[episode] != binding:
                raise ComparisonBlocked("SENSOR_EPISODE_IDENTITY_VALIDITY_INCONSISTENT")
            if episode not in episode_contracts:
                physical = binding[:3]
                for other_episode, start_interval, end_interval in physical_episode_intervals.get(physical, []):
                    if max(binding[3], start_interval) < min(binding[4], end_interval):
                        raise ComparisonBlocked("PHYSICAL_SENSOR_OVERLAPPING_EPISODE_IDENTITIES", other_episode + "/" + episode)
                physical_episode_intervals.setdefault(physical, []).append((episode, binding[3], binding[4]))
                episode_contracts[episode] = binding
            source_key = tuple(proofs[oid][k] for k in ("source_group", "source_sha256", "source_row_locator"))
            if source_key in all_source_rows:
                raise ComparisonBlocked("SOURCE_RECORD_MEMBERSHIP_OVERLAP", oid)
            all_source_rows.add(source_key)
            def component_keys(value):
                if isinstance(value, dict):
                    if all(k in value for k in ("file_sha256", "row_group", "row_index", "column")):
                        yield (value["file_sha256"], value["row_group"], value["row_index"], value["column"])
                    for nested in value.values():
                        yield from component_keys(nested)
                elif isinstance(value, list):
                    for nested in value:
                        yield from component_keys(nested)
            for component in component_keys(proofs[oid].get("typed_payload_bindings")):
                if component in typed_component_splits and typed_component_splits[component] != split:
                    raise ComparisonBlocked("TYPED_COMPONENT_SOURCE_SPLIT_LEAKAGE")
                typed_component_splits[component] = split
            events_by_split[split].add(record["event_id"])
            stations_by_split[split].add(record["station_id"])
            episodes_by_split[split].add(proofs[oid]["sensor_episode_id"])
            documents_by_split[split].update(proofs[oid].get("document_family_ids", []))
            if protocols and not proofs[oid].get("document_family_ids"):
                raise ComparisonBlocked("DOCUMENT_FAMILY_SPLIT_PROOF_MISSING", oid)
            lookup[key] = record
        eligible = []
        # Every possible same-event/episode horizon pair is evaluated. Missing
        # targets are counted as boundary/missing-horizon origins, not hidden.
        for key, origin in sorted(lookup.items(), key=lambda entry: (entry[0][3], entry[1]["id"])):
            target = origin if pointwise else lookup.get((*key[:3], key[3] + timedelta(seconds=horizon)))
            if target is None:
                continue
            op, tp = proofs[origin["id"]], proofs[target["id"]]
            if origin["event_id"] != target["event_id"] or op["sensor_episode_id"] != tp["sensor_episode_id"]:
                raise ComparisonBlocked("FORECAST_CROSSES_EVENT_OR_SENSOR_EPISODE", origin["id"])
            if clock(op["available_at"], True) > key[3]:
                raise ComparisonBlocked("ORIGIN_VALUE_AVAILABLE_IN_FUTURE", origin["id"])
            if clock(op["qc_available_at"], True) > key[3]:
                raise ComparisonBlocked("ORIGIN_QC_AVAILABLE_IN_FUTURE", origin["id"])
            feature_map = {f["feature_id"]: f for f in origin.get("features", [])}
            if len(feature_map) != len(origin.get("features", [])):
                raise ComparisonBlocked("DUPLICATE_FEATURE_ID", origin["id"])
            values = []
            for fid in features:
                feature = feature_map.get(fid)
                if feature is None or feature.get("feature_version") != versions[0]:
                    raise ComparisonBlocked("APPROVED_FEATURE_MISSING", fid)
                p = feature.get("provenance") or {}
                if (clock(p.get("available_at"), True) > key[3] or clock(p.get("window_end"), True) > key[3]
                        or clock(p.get("window_start"), True) > clock(p.get("window_end"), True)
                        or clock(p.get("window_start"), True) < start):
                    raise ComparisonBlocked("FEATURE_AS_OF_LEAKAGE", origin["id"] + ":" + fid)
                if protocols and (key[3] - clock(p["window_start"], True)).total_seconds() > protocols["EVALUATION_PROTOCOL"]["body"]["lookback_seconds"]:
                    raise ComparisonBlocked("FEATURE_WINDOW_EXCEEDS_APPROVED_LOOKBACK")
                # A fixed snapshot may not use features from another split.
                source_ids = p.get("source_observation_ids")
                if not source_ids or not set(source_ids) <= own_ids:
                    raise ComparisonBlocked("FEATURE_SOURCE_MEMBERSHIP_LEAKAGE", fid)
                if any(clock(proofs[source]["available_at"], True) > key[3] for source in source_ids):
                    raise ComparisonBlocked("FEATURE_SOURCE_AVAILABLE_IN_FUTURE", fid)
                if any(clock(proofs[source]["qc_available_at"], True) > key[3] for source in source_ids):
                    raise ComparisonBlocked("FEATURE_SOURCE_QC_AVAILABLE_IN_FUTURE", fid)
                if any(not clock(p["window_start"], True) <= clock(source_by_id[source]["timestamp"], True) <= clock(p["window_end"], True) for source in source_ids):
                    raise ComparisonBlocked("FEATURE_SOURCE_TIME_OUTSIDE_WINDOW", fid)
                if any(source_by_id[source]["station_id"] != origin["station_id"] or
                        source_by_id[source]["sensor_id"] != origin["sensor_id"] or
                        source_by_id[source]["variable_code"] != origin["variable_code"] or
                        source_by_id[source]["unit"] != origin["unit"] or
                        source_by_id[source]["event_id"] != origin["event_id"] or
                        proofs[source]["sensor_episode_id"] != op["sensor_episode_id"] for source in source_ids):
                    raise ComparisonBlocked("FEATURE_SOURCE_SENSOR_EPISODE_MISMATCH", fid)
                if not clock(op["effective_start"], True) <= clock(p["window_start"], True) <= clock(p["window_end"], True) < clock(op["effective_end"], True):
                    raise ComparisonBlocked("FEATURE_WINDOW_CROSSES_SENSOR_EPISODE", fid)
                values.append(finite(feature.get("value"), fid))
            typed = manifest.get("schema_version") == "typed-model-comparison-2"
            value = None if typed else finite(target.get("value_standard"), target["id"])
            if pointwise:
                labels = {"NORMAL", "BAD", "SUSPECT", "MISSING"} if manifest["task"] == "QUALITY_REVIEW" else {"NORMAL", "BAD"}
                if origin.get("quality_label") not in labels:
                    raise ComparisonBlocked("BINARY_LABEL_REVIEW_REQUIRED", origin["id"])
                value = int(origin["quality_label"] == "BAD") if origin["quality_label"] in {"NORMAL", "BAD"} else -1
            sample = {"origin_id": origin["id"], "target_id": target["id"],
                "forecast_origin": key[3].isoformat(), "target_time": clock(target["timestamp"], True).isoformat(),
                "event_id": origin["event_id"], "sensor_episode_id": op["sensor_episode_id"],
                "exact_source_scope_key": op["exact_scope_key"],
                "x": values, "y": value,
                "human_quality_label": origin.get("quality_label"),
                "persistence": None if typed else finite(origin.get("value_standard"), origin["id"]),
                "source_availability_policy": op["source_availability_policy"]}
            if manifest.get("schema_version") == "typed-model-comparison-2":
                from app.ml.typed_adapters import validate_payload, signature
                payload, target_payload = origin.get("typed_payload"), target.get("typed_payload")
                if not isinstance(payload, dict) or not isinstance(target_payload, dict) or payload.get("representation") != manifest.get("quantity_kind"):
                    raise ComparisonBlocked("REVIEWED_TYPED_PAYLOAD_MISSING", origin["id"])
                validate_payload(payload); validate_payload(target_payload)
                if manifest["quantity_kind"] == "PROFILE_BINS" and (payload["target_variable"] != manifest["target_variable"] or payload["unit"] != manifest["unit"]):
                    raise ComparisonBlocked("PROFILE_SINGLE_CHANNEL_UNIT_MISMATCH")
                if signature(payload) != signature(target_payload):
                    raise ComparisonBlocked("TYPED_TARGET_ORIGIN_ALIGNMENT_CHANGED")
                sample.update(origin_payload=payload, target_payload=target_payload)
                if manifest["task"] == "QUALITY_REVIEW":
                    rule = origin.get("rule_qc")
                    if not isinstance(rule, dict) or rule.get("flag") not in {"NORMAL", "BAD", "SUSPECT", "MISSING", "NOT_EVALUATED"} or rule.get("rule_version") != snapshot["qc_rule_version"]:
                        raise ComparisonBlocked("REVIEWED_GUIDE_RULE_EXECUTION_OR_EXCLUSION_REQUIRED")
                    sample["rule_qc"] = rule
            eligible.append(sample)
        if len(eligible) < 2:
            raise ComparisonBlocked("INSUFFICIENT_FIXED_HORIZON_PAIRS", split)
        rows[split] = eligible
    for i, left in enumerate(SPLITS):
        for right in SPLITS[i + 1:]:
            if events_by_split[left] & events_by_split[right]:
                raise ComparisonBlocked("EVENT_GROUP_SPLIT_LEAKAGE", left + "/" + right)
            split_strategy = protocols["SPLIT_PROTOCOL"]["body"]["split_strategy"] if protocols else "legacy_strict"
            if split_strategy != "temporal_with_purge" and episodes_by_split[left] & episodes_by_split[right]:
                raise ComparisonBlocked("SENSOR_EPISODE_SPLIT_LEAKAGE", left + "/" + right)
            if split_strategy == "station_holdout" and stations_by_split[left] & stations_by_split[right]:
                raise ComparisonBlocked("STATION_HOLDOUT_LEAKAGE", left + "/" + right)
            if documents_by_split[left] & documents_by_split[right]:
                raise ComparisonBlocked("DOCUMENT_FAMILY_SPLIT_LEAKAGE", left + "/" + right)
    return {"manifest": manifest, "manifest_sha256": manifest_sha, "rows": rows,
        "evidence_mode": getattr(authority, "evidence_mode", "CALLER_SUPPLIED_AUTHORITY_NOT_PRODUCTION_VERIFIED"),
        "protocols": snapshots["TRAIN"].get("_protocols"),
        "origin_membership_sha256": digest(rows), "snapshot_hashes": {s: manifest["splits"][s]["sha256"] for s in SPLITS},
        "coverage": {s: {"snapshot_records": len(snapshots[s]["records"]), "eligible_origins": len(rows[s]),
            "missing_horizon_or_boundary_origins": len(snapshots[s]["records"]) - len(rows[s])} for s in SPLITS}}


def preflight(manifest_path, authority):
    try:
        return _preflight(manifest_path, authority)
    except ComparisonBlocked:
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ComparisonBlocked("INPUT_CONTRACT_INVALID", type(exc).__name__) from exc


def compare(prepared):
    """Tune alpha on validation, then compare on identical locked test origins."""
    manifest, rows = prepared["manifest"], prepared["rows"]
    if manifest.get("schema_version") == "typed-model-comparison-2":
        from app.ml.typed_adapters import compare_typed
        return compare_typed(prepared)
    x = {s: np.asarray([r["x"] for r in rows[s]], dtype=float) for s in SPLITS}
    y = {s: np.asarray([r["y"] for r in rows[s]], dtype=float) for s in SPLITS}
    started = time.perf_counter()
    tuning = []
    for alpha in manifest["ridge_alphas"]:
        candidate = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        candidate.fit(x["TRAIN"], y["TRAIN"])
        tuning.append({"alpha": alpha, "validation": regression_metrics(y["VALIDATION"], candidate.predict(x["VALIDATION"]))})
    best = min(tuning, key=lambda entry: (entry["validation"]["mae"], entry["alpha"]))
    final = make_pipeline(StandardScaler(), Ridge(alpha=best["alpha"]))
    fit_x, fit_y = x["TRAIN"], y["TRAIN"]
    if manifest["refit_train_validation"]:
        fit_x, fit_y = np.concatenate([fit_x, x["VALIDATION"]]), np.concatenate([fit_y, y["VALIDATION"]])
    final.fit(fit_x, fit_y)
    training_seconds = time.perf_counter() - started
    started = time.perf_counter()
    predictions = final.predict(x["TEST"])
    latency_ms = 1000 * (time.perf_counter() - started) / len(predictions)
    baseline = np.asarray([r["persistence"] for r in rows["TEST"]], dtype=float)
    model = final.named_steps["ridge"]
    scaler = final.named_steps["standardscaler"]
    # Portable numerical data only, with a direct prediction roundtrip; no pickle.
    artifact = {"schema_version": "standard-scaled-ridge-json-1", "features": manifest["feature_ids"],
        "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
        "coef": model.coef_.tolist(), "intercept": float(model.intercept_), "alpha": best["alpha"]}
    replay = ((x["TEST"] - np.asarray(artifact["mean"])) / np.asarray(artifact["scale"])) @ np.asarray(artifact["coef"]) + artifact["intercept"]
    if not np.allclose(replay, predictions, rtol=1e-12, atol=1e-12):
        raise ComparisonBlocked("JSON_ARTIFACT_PREDICTION_ROUNDTRIP_FAILED")
    paired = [{**{k: row[k] for k in ("origin_id", "target_id", "forecast_origin", "target_time", "event_id", "sensor_episode_id")},
        "actual": row["y"], "ridge": float(pred), "persistence": row["persistence"]}
        for row, pred in zip(rows["TEST"], predictions)]
    return {"status": "COMPARISON_COMPLETE_CANDIDATE_ONLY", "task": "FORECASTING", "adapter_scope": "SCALAR_RIDGE_AND_PERSISTENCE_ONLY",
        "evidence_mode": prepared["evidence_mode"],
        "selected_operating_model": None, "registered_models": 0, "deployed_models": 0,
        "champion_status": "NO_CHAMPION_COMPARISON_ADAPTER", "acceptance_criteria_status": "NOT_DEFINED",
        "operating_registration_gate": "BLOCKED_REQUIRES_INDEPENDENT_REVIEW_ACCEPTANCE_AND_RUNTIME_RECEIPT",
        "manifest_sha256": prepared["manifest_sha256"], "snapshot_hashes": prepared["snapshot_hashes"],
        "origin_membership_sha256": prepared["origin_membership_sha256"], "coverage": prepared["coverage"],
        "validation_tuning": tuning, "selected_ridge_alpha": best["alpha"],
        "test_metrics": {"ridge": regression_metrics(y["TEST"], predictions), "persistence": regression_metrics(y["TEST"], baseline)},
        "training_seconds": training_seconds, "batch_inference_ms_per_sample": latency_ms,
        "service_latency": "NOT_MEASURED", "cost": "NOT_MEASURED", "artifact": artifact,
        "paired_test_predictions": paired, "test_prediction_roundtrip_verified": True}


def _atomic_json(path, data):
    path = Path(path)
    reject_reparse(path)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_manual(manifest_path, authority, job_root, execute=False):
    """Durable single-attempt manual jobs. Crashed locks require operator recovery.

    Blocked preflight does not create a training job. A previously successful job
    is reused only after current approvals, snapshots and source hashes revalidate.
    There is no scheduler, automatic retry, DB write, registration or deployment.
    """
    try:
        prepared = preflight(manifest_path, authority)
    except ComparisonBlocked as exc:
        return {"status": "BLOCKED", "training_started": False, "blockers": [{"code": exc.code, "detail": exc.detail}],
            "operating_registration_gate": "BLOCKED", "registered_models": 0, "deployed_models": 0}
    if not execute:
        return {"status": "PREFLIGHT_VERIFIED_CANDIDATE_INPUT_ONLY", "training_started": False,
            "manifest_sha256": prepared["manifest_sha256"], "coverage": prepared["coverage"],
            "evidence_mode": prepared["evidence_mode"],
            "operating_registration_gate": "BLOCKED", "acceptance_criteria_status": "NOT_DEFINED"}
    reject_reparse(job_root)
    root = Path(job_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    environment = {"python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__}
    from app.services import source_contract_review
    code_sha = digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       (Path(__file__), Path(__file__).with_name("evaluator.py"), Path(source_contract_review.__file__))})
    job_id = digest({"manifest_sha256": prepared["manifest_sha256"], "origins": prepared["origin_membership_sha256"],
                     "code_sha256": code_sha, "environment": environment})
    scope = digest({k: prepared["manifest"].get(k) for k in ("task", "target_variable", "unit", "horizon_seconds")})
    ledger = sqlite3.connect(root / "comparison_jobs.sqlite3", timeout=30)
    ledger.execute("PRAGMA journal_mode=WAL")
    ledger.executescript("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, state TEXT NOT NULL, report_path TEXT, report_sha256 TEXT, error TEXT, created_at TEXT NOT NULL, finished_at TEXT); CREATE TABLE IF NOT EXISTS scope_locks (scope TEXT PRIMARY KEY, job_id TEXT NOT NULL, owner_pid INTEGER NOT NULL, acquired_at TEXT NOT NULL);")
    now = datetime.now(timezone.utc).isoformat()
    acquired = False
    output = root / job_id
    try:
        ledger.execute("BEGIN IMMEDIATE")
        previous = ledger.execute("SELECT state,report_path,report_sha256,error FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if previous:
            ledger.rollback()
            if previous[0] == "COMPLETED_CANDIDATE":
                saved, sha = read_json(previous[1])
                if sha != previous[2]:
                    raise ComparisonBlocked("COMPLETED_JOB_REPORT_HASH_MISMATCH")
                return {**saved, "idempotent_reuse": True}
            return {"status": "RECOVERY_REQUIRED", "job_id": job_id, "prior_state": previous[0], "training_started": False}
        if ledger.execute("SELECT job_id FROM scope_locks WHERE scope=?", (scope,)).fetchone():
            ledger.rollback()
            return {"status": "SCOPE_BUSY_OR_RECOVERY_REQUIRED", "training_started": False}
        ledger.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", (job_id, "RUNNING", None, None, None, now, None))
        ledger.execute("INSERT INTO scope_locks VALUES (?,?,?,?)", (scope, job_id, os.getpid(), now))
        ledger.commit()
        acquired = True
        output.mkdir(exist_ok=False)
        _atomic_json(output / "job-input.json", {"job_id": job_id, "code_sha256": code_sha, "environment": environment,
            "manifest_sha256": prepared["manifest_sha256"], "origin_membership_sha256": prepared["origin_membership_sha256"]})
        result = compare(prepared)
        # Changed approval, source or holdout after fitting invalidates the attempt.
        after = preflight(manifest_path, authority)
        if (after["manifest_sha256"], after["origin_membership_sha256"]) != (prepared["manifest_sha256"], prepared["origin_membership_sha256"]):
            raise ComparisonBlocked("INPUT_CHANGED_DURING_COMPARISON")
        result.update({"job_id": job_id, "training_started": True, "code_sha256": code_sha, "environment": environment,
                       "automatic_retry": "DISABLED", "scheduler": "NOT_CONFIGURED", "crash_recovery": "MANUAL_ONLY"})
        report = output / "comparison.json"
        _atomic_json(report, result)
        ledger.execute("UPDATE jobs SET state=?,report_path=?,report_sha256=?,finished_at=? WHERE job_id=?",
            ("COMPLETED_CANDIDATE", str(report), hashlib.sha256(report.read_bytes()).hexdigest(), datetime.now(timezone.utc).isoformat(), job_id))
        ledger.commit()
        return result
    except Exception as exc:
        code = exc.code if isinstance(exc, ComparisonBlocked) else "COMPARISON_EXECUTION_FAILED"
        # Preserve attempt files for review; never touch original/champion assets.
        result = {"status": "FAILED_QUARANTINED", "job_id": job_id, "training_started": acquired,
                  "blockers": [{"code": code, "detail": str(exc)}], "registered_models": 0, "deployed_models": 0}
        if acquired:
            ledger.execute("UPDATE jobs SET state=?,error=?,finished_at=? WHERE job_id=?",
                ("FAILED_QUARANTINED", code, datetime.now(timezone.utc).isoformat(), job_id))
            ledger.commit()
            if output.is_dir():
                try:
                    _atomic_json(output / "failure.json", result)
                except OSError:
                    result["failure_receipt_write_status"] = "IO_FAILED_LEDGER_PRESERVED"
        return result
    finally:
        if acquired:
            ledger.execute("DELETE FROM scope_locks WHERE scope=? AND job_id=?", (scope, job_id))
            ledger.commit()
        ledger.close()
