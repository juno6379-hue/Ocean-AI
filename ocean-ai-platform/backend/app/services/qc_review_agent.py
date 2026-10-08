"""Read-only, deterministic review. Source flags and claims never grant approval."""
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import math
import re
from sqlalchemy import text

VERSION = "qc-review-v1"
TABLES = ("facility", "channel_month", "equipment_claim", "lifecycle_claim", "document_link", "document")
SPEC_FIELDS = ("measurement_method", "accuracy", "measurement_range", "operating_environment")
REFERENCE_REVIEW = {
    "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
    "guide_edition": "2023-12", "operational_adoption": "UNVERIFIED",
    "guide_pages": [15, 18, 20, 21, 23, 35, 36, 38, 44, 45, 81, 82, 87, 93, 94],
    "report_chapter3_sha256": "953f341a53450695a0c28d92f1a18cb58d5ff0f5fd740526347875c06e0ce06c",
    "report_chapter3_pages": [7, 8, 28, 33, 34, 35, 37],
    "open_rule_issues": ["RR_PR_CODE_CONFLICT", "PRESSURE_SPIKE_UNIT_CONFLICT",
                         "VARIATION_OR_AND_CONFLICT", "FLAT_BOUNDARY_UNAPPROVED",
                         "RANGE_ENDPOINT_CONFLICT", "SPIKE_TWO_VS_THREE_POINT"],
    "review_scope": "BOUNDED_REFERENCE_REVIEW_NOT_COMPLETE_DOCUMENT_REVIEW",
}


def _json(value):
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return {"non_finite": str(value)}
    return value


def digest(value):
    return hashlib.sha256(json.dumps(_json(value), ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_registry_evidence(db, station_id, item_code, start_month, end_month, source_group=None, limit=1000):
    """SELECT one published snapshot; caller owns the transaction. No MDC calls.

    Item code must be the exact registry item; no alias/name-based sensor join.
    Tables are bounded independently and truncation is reported as a blocker.
    """
    if not station_id or not item_code:
        raise ValueError("station_id and exact registry item_code are required")
    for value in (start_month, end_month):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
            raise ValueError("month must be YYYY-MM")
    if start_month > end_month or not 1 <= limit <= 1000:
        raise ValueError("invalid month interval or limit")
    scope = dict(station_id=station_id, item_code=item_code, start_month=start_month,
                 end_month=end_month, source_group=source_group)
    out = dict(scope=scope, status="UNAVAILABLE", tables={}, truncated_tables=[])
    missing = [t for t in ("run", *TABLES) if not db.execute(text("SELECT to_regclass(:name)"),
                              {"name": "facility_registry." + t}).scalar()]
    if missing:
        out["missing_tables"] = missing
        return out
    run = db.execute(text("SELECT run_id,as_of,manifest FROM facility_registry.run "
                          "WHERE manifest->>'status'='PUBLISHED_REVIEW_ONLY' ORDER BY run_id DESC LIMIT 1")).mappings().first()
    if not run:
        return out
    out.update(status="LOADED_REVIEW_ONLY", run_id=run["run_id"], as_of=str(run["as_of"]),
               manifest_sha256=digest(run["manifest"]))
    params = dict(r=run["run_id"], s=station_id, i=item_code, a=start_month,
                  b=end_month, source=source_group, n=limit + 1)
    for table in TABLES:
        predicate = "run_id=:r AND station_code=:s"
        if table == "channel_month":
            predicate += " AND item_code=:i AND month>=:a AND month<=:b"
            if source_group:
                predicate += " AND source_group=:source"
        elif table == "document_link":
            predicate += " AND (item_code=:i OR item_code IS NULL)"
        elif table == "document":
            params["shas"] = sorted({r["source_sha256"] for rows in out["tables"].values()
                                     for r in rows if r.get("source_sha256")})
            predicate = "run_id=:r AND source_sha256=ANY(:shas)"
        rows = [dict(r) for r in db.execute(text(f"SELECT * FROM facility_registry.{table} "
                    f"WHERE {predicate} ORDER BY record_id LIMIT :n"), params).mappings()]
        if len(rows) > limit:
            out["truncated_tables"].append(table)
        out["tables"][table] = rows[:limit]
    return _json(out)


def review_bundle(observations, evidence=None, rechecks=None):
    """Replayable analysis of supplied rows; stored rechecks are not rerun.

    Numeric values alone do not imply normality. Missing codebooks, physical
    sensors, rule versions and intervals cannot be filled with generic defaults.
    """
    observations = _json(list(observations))
    evidence = _json(evidence or {"status": "UNAVAILABLE", "tables": {}})
    rechecks = _json(list(rechecks or []))
    tables = evidence.get("tables", {})
    channels = tables.get("channel_month", [])
    blockers = []
    if not observations:
        blockers.append("NO_OBSERVATIONS_SUPPLIED")
    if evidence.get("status") != "LOADED_REVIEW_ONLY":
        blockers.append("REGISTRY_EVIDENCE_UNAVAILABLE")
    if evidence.get("truncated_tables"):
        blockers.append("EVIDENCE_TRUNCATED")
    if not tables.get("facility"):
        blockers.append("FACILITY_IDENTITY_UNRESOLVED")
    if not channels:
        blockers.append("NO_CHANNEL_IN_REQUESTED_SCOPE")
    scope = evidence.get("scope", {})
    if not scope.get("source_group"):
        blockers.append("SOURCE_GROUP_UNRESOLVED")
    problems = []
    for index, row in enumerate(observations):
        station = row.get("station_id") or row.get("station_code")
        item = row.get("item_code") or row.get("source_item_code") or row.get("variable_code")
        timestamp = row.get("timestamp_utc") or row.get("timestamp")
        month = str(timestamp)[:7] if timestamp else ""
        if station != scope.get("station_id") or item != scope.get("item_code") or not month or not (
                scope.get("start_month", "9999") <= month <= scope.get("end_month", "0000")):
            problems.append(index)
    if problems:
        blockers.append("OBSERVATION_SCOPE_UNVERIFIED_OR_MISMATCHED")
    if any(not (r.get("value_unit") or r.get("standard_unit")) for r in observations):
        blockers.append("OBSERVATION_UNIT_UNRESOLVED")
    incomplete = [r.get("record_id") for r in channels if not r.get("physical_sensor_id")
                  or not r.get("valid_from") or not r.get("valid_to") or not r.get("nominal_interval_seconds")]
    if incomplete:
        blockers.append("SENSOR_INTERVAL_OR_CADENCE_UNRESOLVED")
    if any(r.get("approval_status") != "APPROVED" for r in channels):
        blockers.append("CHANNEL_LINK_NOT_APPROVED")
    equipment = tables.get("equipment_claim", [])
    if not equipment:
        blockers.append("EQUIPMENT_EVIDENCE_MISSING")
    if any(any(not r.get(k) for k in SPEC_FIELDS) for r in equipment):
        blockers.append("EQUIPMENT_SPECIFICATIONS_INCOMPLETE")
    # The registry currently has no approved equipment-to-channel relation.
    blockers.append("EQUIPMENT_CHANNEL_PERIOD_LINK_UNVERIFIED")
    documents = tables.get("document", [])
    if not documents:
        blockers.append("DOCUMENT_EVIDENCE_MISSING")
    if any(r.get("vector_state") != "SQL_VECTOR_IDS_MATCH" for r in documents):
        blockers.append("DOCUMENT_VECTOR_RECONCILIATION_INCOMPLETE")
    blockers.append("SOURCE_QC_CODE_CONTRACT_UNVERIFIED")
    blockers.append("APPROVED_RULE_VERSION_AND_EFFECTIVE_INTERVAL_REQUIRED")
    blockers.append("RECORDED_RECHECK_APPLICABILITY_NOT_REVALIDATED" if rechecks else "CURRENT_RECHECK_NOT_EXECUTED")
    events, conflicts = [], []
    for claim in tables.get("lifecycle_claim", []):
        events.append(dict(claim, support_status="DOCUMENT_ASSERTION_CODE_LINK_CANDIDATE",
                           sensor_causation="NOT_ESTABLISHED"))
        latest = claim.get("date_latest")
        if claim.get("event_type") == "RETIRED" and latest:
            later = [r.get("record_id") for r in channels if r.get("last_clock") and str(r["last_clock"])[:10] > latest]
            if later:
                conflicts.append(dict(kind="COVERAGE_AFTER_REPORTED_RETIREMENT", claim_id=claim.get("record_id"),
                                      channel_ids=later, resolution="REOPENING_IDENTITY_OR_SOURCE_REVIEW_REQUIRED"))
    if conflicts:
        blockers.append("UNRESOLVED_EVIDENCE_CONFLICT")
    source_flags = {key: dict(sorted(Counter(str(r[key]) if r.get(key) is not None else "<NULL>"
                         for r in observations).items())) for key in ("qc_flag", "mqc_flag")}
    result = dict(contract_version=VERSION, status="REVIEW_REQUIRED", approval_required=True,
                  final_flag=None, recommended_flag="NOT_EVALUATED", scope=scope,
                  source_qc=dict(status="PRESERVED_UNINTERPRETED", counts=source_flags,
                                 observation_count=len(observations), source_code_contract="NOT_VERIFIED"),
                  current_recheck=dict(status="RECORDED_RESULTS_ONLY" if rechecks else "NOT_EXECUTED",
                                       results=rechecks, normal_ratio=None, accuracy=None),
                  documentary_event_support=events, conflicts=conflicts,
                  reference_review=_json(REFERENCE_REVIEW), facilities=tables.get("facility", []),
                  interval_evidence=dict(status="INSUFFICIENT" if incomplete or not channels else "RECORDED_LINKS_REQUIRE_REVIEW",
                                         unresolved_channel_ids=incomplete, channels=channels),
                  equipment_claims=equipment, document_links=tables.get("document_link", []), documents=documents,
                  document_verification="REGISTRY_SNAPSHOT_ONLY_NOT_LIVE_RECONCILIATION",
                  blockers=sorted(set(blockers)), observation_scope_problem_indices=problems,
                  missing_evidence_actions=["시설·항목·실물 센서·유효기간·관측간격 연결을 확인합니다.",
                                            "원천 QC 코드표와 적용 규칙·단위·시행기간을 확인한 뒤 재검사합니다.",
                                            "문서 사건의 원인 지지와 담당자 승인을 별도로 검토합니다."])
    result["audit"] = dict(run_id=evidence.get("run_id"), as_of=evidence.get("as_of"),
                           manifest_sha256=evidence.get("manifest_sha256"),
                           input_sha256=digest(dict(observations=observations, evidence=evidence, rechecks=rechecks)),
                           observation_records=[dict(index=i, sha256=digest(r)) for i, r in enumerate(observations)],
                           evidence_records=[dict(table=t, record_id=r.get("record_id"), sha256=digest(r))
                                             for t in sorted(tables) for r in tables[t]],
                           mutations=[], evaluator=VERSION)
    result["audit"]["result_sha256"] = digest(result)
    return result
