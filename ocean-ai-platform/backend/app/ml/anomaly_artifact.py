"""Bounded numeric JSON development artifacts; no executable deserialization."""
from __future__ import annotations

import hashlib
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCHEMA = "ocean-anomaly-statistical-artifact-1"
MAX_ROWS = 10_000
MAX_JSON_BYTES = 4 * 1024 * 1024


class AnomalyContractError(ValueError):
    def __init__(self, code, detail=""):
        self.code, self.detail = code, str(detail)
        super().__init__(code + (": " + self.detail if detail else ""))


def canonical_bytes(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > MAX_JSON_BYTES:
            raise AnomalyContractError("JSON_INPUT_EXCEEDS_4_MIB")
        return raw
    except AnomalyContractError:
        raise
    except (TypeError, ValueError) as exc:
        raise AnomalyContractError("NONFINITE_OR_NON_JSON_INPUT") from exc


def sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def number(value, field):
    if type(value) not in {int, float} or not math.isfinite(value):
        raise AnomalyContractError("FINITE_NUMERIC_VALUE_REQUIRED", field)
    return float(value)


def clock(value):
    if not isinstance(value, str):
        raise AnomalyContractError("EXPLICIT_OFFSET_CLOCK_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except ValueError as exc:
        raise AnomalyContractError("EXPLICIT_OFFSET_CLOCK_REQUIRED", value) from exc


def evidence(items):
    if not isinstance(items, list) or not items or len(items) > 100:
        return False
    return all(isinstance(e, dict) and isinstance(e.get("sha256"), str)
        and len(e["sha256"]) == 64 and all(c in "0123456789abcdef" for c in e["sha256"])
        and isinstance(e.get("locator"), str) and 0 < len(e["locator"]) <= 1024
        for e in items)


def fingerprint():
    service = Path(__file__).parents[1] / "services" / "anomaly_analysis.py"
    return sha256({"schema": SCHEMA, "python":platform.python_version(),"numpy": np.__version__, "code": {
        "artifact": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "analysis": hashlib.sha256(service.read_bytes()).hexdigest(),
        "fact_contract": hashlib.sha256(service.with_name("qc_analysis_readiness.py").read_bytes()).hexdigest()}})


def envelope(body):
    return {"artifact": body, "sha256": sha256(body)}


def verify(enveloped):
    if not isinstance(enveloped, dict) or not isinstance(enveloped.get("artifact"), dict):
        raise AnomalyContractError("NUMERIC_ARTIFACT_REQUIRED")
    body = enveloped["artifact"]
    if sha256(body) != enveloped.get("sha256"):
        raise AnomalyContractError("ARTIFACT_HASH_MISMATCH")
    if body.get("schema_version") != SCHEMA or body.get("code_sha256") != fingerprint():
        raise AnomalyContractError("ARTIFACT_SCHEMA_OR_CODE_CHANGED")
    if body.get("approved") is not False or body.get("production_eligible") is not False:
        raise AnomalyContractError("DEVELOPMENT_ARTIFACT_CANNOT_AUTHORIZE_PRODUCTION")
    return body
