"""Exhaustive conditional-analysis requirements, never a source approval.

References, current metadata and raw native clocks are retained by callers; this
module does not convert them into historical facts, UTC or sensor identities.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

FACTS = ("semantic", "unit", "clock", "qc", "sensor_episode")
MATERIALS = {
    "semantic": "source table/item dictionary and its exact valid interval",
    "unit": "historical unit, scale/offset/datum and valid interval",
    "clock": "OBS/RECEIVE storage-clock and extraction-conversion policy",
    "qc": "literal codebook, whitespace/NULL meanings, adopted revision and valid interval",
    "sensor_episode": "physical instrument/channel installation/change/removal interval",
}


def _clock(value):
    try:
        t = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo is not None and t.utcoffset() is not None else None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None


class FactPeriodError(ValueError):
    """A supplied interval fails its explicitly selected schema, never an approval."""


def fact_period(fact, fields=("start", "end"), *, when=None, as_of=None, expected_scope=None):
    """Validate explicit offset instants and [start,end), with no alias fallback.

    Anomaly-series facts use start/end. Rule source facts are an explicit
    effective_start/effective_end schema. Both use this same interval codec.
    Declared metadata availability, when supplied, must also be causal. Missing
    availability is not synthesized or promoted to a production authority.
    """
    pairs=(("start", "end"), ("effective_start", "effective_end"))
    if fields not in pairs or not isinstance(fact, dict):
        raise FactPeriodError("FACT_PERIOD_SCHEMA_REQUIRED")
    alternate=pairs[1] if fields==pairs[0] else pairs[0]
    if any(key in fact for key in alternate):
        raise FactPeriodError("AMBIGUOUS_FACT_PERIOD_FIELDS")
    start,end=(_clock(fact.get(field)) for field in fields)
    if start is None or end is None:
        raise FactPeriodError("FACT_PERIOD_OFFSET_REQUIRED")
    if start>=end:
        raise FactPeriodError("FACT_PERIOD_NOT_ORDERED")
    if "scope" in fact and expected_scope is not None and fact["scope"]!=expected_scope:
        raise FactPeriodError("FACT_EXACT_SCOPE_MISMATCH")
    point=_clock(when) if when is not None else None
    if when is not None and point is None:
        raise FactPeriodError("FACT_EVENT_OFFSET_REQUIRED")
    if point is not None and not start<=point<end:
        raise FactPeriodError("FACT_OUTSIDE_EFFECTIVE_INTERVAL")
    cutoff=_clock(as_of) if as_of is not None else None
    if as_of is not None and cutoff is None:
        raise FactPeriodError("FACT_AS_OF_OFFSET_REQUIRED")
    availability=[]
    for key in ("available_at", "version_available_at"):
        if key not in fact:continue
        available=_clock(fact[key])
        if available is None:
            raise FactPeriodError("FACT_AVAILABILITY_OFFSET_REQUIRED")
        if cutoff is None or available>cutoff:
            raise FactPeriodError("FACT_VERSION_NOT_AVAILABLE_AS_OF")
        availability.append(available)
    return start,end,tuple(availability)


def _reference(value):
    return isinstance(value, list) and 1 <= len(value) <= 100 and all(isinstance(e, dict)
        and isinstance(e.get("sha256"), str) and len(e["sha256"]) == 64
        and all(c in "0123456789abcdef" for c in e["sha256"])
        and isinstance(e.get("locator"), str) and bool(e["locator"].strip()) for e in value)


def inspect_source_inputs(series):
    """List all missing fields even when the first scope/clock is unresolved.

    A zero blocker count means only that the declared conditional input shape
    can be examined by the engine. The engine still performs its strict
    semantic/time/period validation. Hash/locator presence is not fact authority.
    """
    series = series if isinstance(series, dict) else {}
    scope = series.get("scope") if isinstance(series.get("scope"), dict) else {}
    facts = series.get("facts") if isinstance(series.get("facts"), dict) else {}
    fields = []
    def add(path, code, material, row_id=None):
        fields.append({"path": path, "code": code, "required_material": material, "row_id": row_id})
    if series.get("schema_version") != "ocean-anomaly-series-1":
        add("/schema_version", "ANOMALY_SERIES_SCHEMA_REQUIRED", "explicit conditional series schema")
    for key in ("station_id", "sensor_id", "variable_code", "unit", "sensor_episode_id"):
        if not isinstance(scope.get(key), str) or not scope[key].strip():
            add("/scope/" + key, "SOURCE_SCOPE_FIELD_REQUIRED:" + key,
                "exact canonical binding; source code/name is not a physical sensor")
    if _clock(series.get("as_of")) is None:
        add("/as_of", "ANALYSIS_AS_OF_OFFSET_REQUIRED", "explicit analysis clock")
    for name in FACTS:
        fact = facts.get(name) if isinstance(facts.get(name), dict) else {}
        if fact.get("documented") is not True:
            add("/facts/" + name + "/documented", "SOURCE_" + name.upper() + "_NOT_DOCUMENTED", MATERIALS[name])
        if not _reference(fact.get("evidence")):
            add("/facts/" + name + "/evidence", "SOURCE_FACT_EVIDENCE_REQUIRED:" + name, MATERIALS[name])
        for boundary in ("start", "end"):
            if _clock(fact.get(boundary)) is None:
                add("/facts/" + name + "/" + boundary, "SOURCE_FACT_PERIOD_REQUIRED:" + name, MATERIALS[name])
        try:
            fact_period(fact, as_of=series.get("as_of"), expected_scope=scope)
        except FactPeriodError as exc:
            add("/facts/" + name, str(exc)+":"+name, MATERIALS[name])
    rows = series.get("rows")
    if not isinstance(rows, list) or not rows:
        add("/rows", "OBSERVATION_ROWS_REQUIRED", "exact source row membership")
        rows = []
    if len(rows) > 10000:
        add("/rows", "ANALYSIS_ROW_LIMIT_EXCEEDED", "bounded exact source review membership (max 10000)")
        rows = rows[:10000]
    for index, row in enumerate(rows):
        r = row if isinstance(row, dict) else {}
        for key in ("timestamp", "available_at", "qc_available_at"):
            if _clock(r.get(key)) is None:
                add(f"/rows/{index}/{key}", "SOURCE_ROW_CLOCK_REQUIRED:" + key,
                    "documented observation, receipt and QC availability clock", r.get("row_id") if isinstance(r.get("row_id"), str) else None)
        if r.get("qc_eligible") is not True:
            add(f"/rows/{index}/qc_eligible", "SOURCE_QC_NOT_USABLE", MATERIALS["qc"], r.get("row_id") if isinstance(r.get("row_id"), str) else None)
        if not _reference([r.get("source")]):
            add(f"/rows/{index}/source", "SOURCE_ROW_REFERENCE_REQUIRED", "immutable source SHA and exact cell locator", r.get("row_id") if isinstance(r.get("row_id"), str) else None)
    result = {"schema_version": "conditional-analysis-requirements-v1",
        "status": "NOT_EVALUATED" if fields else "DECLARED_SHAPE_READY_REQUIRES_ENGINE_VALIDATION",
        "requirements": fields, "blocker_counts": dict(sorted(Counter(x["code"] for x in fields).items())),
        "approved": False, "production_eligible": False, "fact_authority": "UNVERIFIED_DECLARED_INPUT",
        "note": "Reference presence does not establish facts, adoption, period validity or human approval."}
    result["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return result
