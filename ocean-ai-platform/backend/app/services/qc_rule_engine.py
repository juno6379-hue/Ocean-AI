"""Deterministic, conditional analysis of the guide's twelve first-stage QC tests.

All metadata/configuration is supplied evidence, not an approval. This module has
no database, clock, network, flag-finalization, or training side effects.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import re
from collections import Counter
from functools import lru_cache
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

GUIDE_SHA256 = "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9"
ENGINE_VERSION = "guide-existing-12-v1"
KINDS = ("WT", "LO", "ER", "GR", "GD", "RL", "SP", "RR", "SR", "ST", "DE", "PO")
HARD = {"WT", "LO", "ER", "GR", "GD"}
HEX = re.compile(r"^[0-9a-f]{64}$")
SCOPE_FIELDS = ("station_id", "sensor_id", "variable_code", "unit")
UNIT_CONVERSIONS = {("m", "cm"): ("100", "0"), ("cm", "m"): ("0.01", "0"),
    ("Pa", "hPa"): ("0.01", "0"), ("hPa", "Pa"): ("100", "0"),
    ("m/s", "cm/s"): ("100", "0"), ("cm/s", "m/s"): ("0.01", "0")}


class NotEvaluated(ValueError):
    pass


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name("qc_rule_catalog.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def implementation_hashes():
    return {"implementation_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "catalog_sha256": sha256(Path(__file__).with_name("qc_rule_catalog.json").read_bytes()).hexdigest()}


def utc(value):
    if not isinstance(value, str):
        raise NotEvaluated("AWARE_TIMESTAMP_REQUIRED")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise NotEvaluated("INVALID_TIMESTAMP") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise NotEvaluated("AWARE_TIMESTAMP_REQUIRED")
    return stamp.astimezone(timezone.utc)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise NotEvaluated("FINITE_NUMERIC_VALUE_REQUIRED")
    return float(value)


def obj(value, reason):
    if not isinstance(value, dict):
        raise NotEvaluated(reason)
    return value


def evidence(value):
    value = obj(value, "EVIDENCE_REFERENCE_REQUIRED")
    if not isinstance(value.get("sha256"), str) or not HEX.fullmatch(value["sha256"]) or not isinstance(value.get("locator"), str) or not value["locator"].strip():
        raise NotEvaluated("EVIDENCE_REFERENCE_REQUIRED")
    return value


def positive(parameters, field):
    val = number(parameters.get(field))
    if val <= 0:
        raise NotEvaluated("POSITIVE_PARAMETER_REQUIRED:" + field)
    return val


def _record(row, context, *, numeric=True, clock_diagnostic=False):
    obj(row, "RECORD_OBJECT_REQUIRED")
    if row.get("_normalization_error"):
        raise NotEvaluated(row["_normalization_error"])
    if not isinstance(row.get("observation_id"), str) or not row["observation_id"].strip():
        raise NotEvaluated("EXACT_OBSERVATION_ID_REQUIRED")
    if not all(isinstance(row.get(k), str) and row[k].strip() for k in SCOPE_FIELDS):
        raise NotEvaluated("EXACT_SCOPE_AND_UNIT_REQUIRED")
    when = utc(row.get("timestamp_utc"))
    available = utc(row.get("available_at"))
    if available > context["as_of"]:
        raise NotEvaluated("INPUT_NOT_AVAILABLE_AS_OF")
    if available < when and not clock_diagnostic:
        raise NotEvaluated("INPUT_AVAILABLE_BEFORE_OBSERVED_CLOCK")
    if when > context["as_of"] and not clock_diagnostic:
        raise NotEvaluated("OBSERVATION_AFTER_AS_OF")
    facts = obj(row.get("source_facts"), "SOURCE_FACTS_REQUIRED")
    for field in ("physical_sensor_id", "sensor_episode_id", "quantity_kind", "clock_semantics"):
        if not isinstance(facts.get(field), str) or not facts[field].strip():
            raise NotEvaluated("SOURCE_FACT_REQUIRED:" + field)
    evidence(facts.get("evidence"))
    if row["variable_code"] == "TIDE" and (not isinstance(facts.get("reference_datum"), str) or not facts["reference_datum"].strip()):
        raise NotEvaluated("TIDE_REFERENCE_DATUM_REQUIRED")
    start, end = utc(facts.get("effective_start")), utc(facts.get("effective_end"))
    if not start <= when < end:
        raise NotEvaluated("SOURCE_EPISODE_OUTSIDE_EFFECTIVE_PERIOD")
    if numeric and row.get("value") is not None:
        number(row["value"])
    return when


def _scope(row):
    facts = obj(row.get("source_facts"), "SOURCE_FACTS_REQUIRED")
    normalization = obj(row.get("normalization") or {}, "MALFORMED_NORMALIZATION")
    return tuple(row.get(k) for k in SCOPE_FIELDS) + tuple(facts.get(k) for k in ("physical_sensor_id", "sensor_episode_id", "quantity_kind", "reference_datum", "clock_semantics")) + (normalization.get("from_unit", row.get("unit")),)


def _normalized_record(row, rule):
    """Explicit dimensional conversion of a copy, preserving source bytes/value."""
    obj(row, "RECORD_OBJECT_REQUIRED")
    parameters = obj(rule.get("parameters"), "RULE_PARAMETERS_REQUIRED")
    if not isinstance(row.get("unit"), str) or not row["unit"].strip():
        return row
    if row.get("variable_code") != parameters.get("variable_code") or row.get("unit") == parameters.get("unit"):
        return row
    conversion = obj(parameters.get("unit_conversion"), "EXPLICIT_UNIT_CONVERSION_REQUIRED")
    pair = (row.get("unit"), parameters.get("unit"))
    expected = UNIT_CONVERSIONS.get(pair)
    if not expected or conversion.get("from") != pair[0] or conversion.get("to") != pair[1]:
        raise NotEvaluated("UNSUPPORTED_OR_MISMATCHED_UNIT_CONVERSION")
    evidence(conversion.get("evidence"))
    try:
        scale, offset = Decimal(str(conversion.get("scale"))), Decimal(str(conversion.get("offset")))
    except InvalidOperation:
        raise NotEvaluated("INVALID_UNIT_CONVERSION_PARAMETERS") from None
    if not scale.is_finite() or not offset.is_finite() or scale != Decimal(expected[0]) or offset != Decimal(expected[1]):
        raise NotEvaluated("UNIT_CONVERSION_FACTOR_MISMATCH")
    prepared = deepcopy(row)
    prepared["unit"] = pair[1]
    if row.get("value") is not None:
        prepared["value"] = float(Decimal(str(number(row["value"]))) * scale + offset)
    prepared["normalization"] = {"from_unit": pair[0], "to_unit": pair[1], "scale": str(scale), "offset": str(offset),
        "source_value": row.get("value"), "source_record_sha256": digest(row), "evidence": conversion["evidence"]}
    baseline = prepared.get("baseline")
    if isinstance(baseline, dict):
        if baseline.get("unit") != pair[0]:
            raise NotEvaluated("BASELINE_SOURCE_UNIT_MISMATCH")
        baseline["unit"] = pair[1]
        for key in ("min", "max", "mean"):
            if key in baseline:
                baseline[key] = float(Decimal(str(number(baseline[key]))) * scale + offset)
        if "std" in baseline:
            baseline["std"] = float(Decimal(str(number(baseline["std"]))) * abs(scale))
    return prepared


def _config(rule, row):
    kind = rule.get("kind")
    if kind not in KINDS:
        raise NotEvaluated("UNSUPPORTED_RULE_KIND")
    if not isinstance(rule.get("qc_rule_id"), str) or not rule["qc_rule_id"] or not isinstance(rule.get("rule_version"), str) or not rule["rule_version"]:
        raise NotEvaluated("RULE_ID_AND_VERSION_REQUIRED")
    p = obj(rule.get("parameters"), "RULE_PARAMETERS_REQUIRED")
    prov = obj(rule.get("provenance"), "RULE_PROVENANCE_REQUIRED")
    if prov.get("guide_sha256") != GUIDE_SHA256:
        raise NotEvaluated("GUIDE_VERSION_MISMATCH")
    pages = prov.get("pdf_pages")
    if not isinstance(pages, list) or not pages or any(type(x) is not int or not 1 <= x <= 118 for x in pages):
        raise NotEvaluated("GUIDE_PAGE_LOCATOR_REQUIRED")
    if not isinstance(prov.get("profile_id"), str) or not prov["profile_id"]:
        raise NotEvaluated("EXPLICIT_PROFILE_SELECTION_REQUIRED")
    evidence(prov.get("configuration_reference"))
    if p.get("unit") != row.get("unit") or p.get("variable_code") != row.get("variable_code"):
        raise NotEvaluated("RULE_QUANTITY_OR_UNIT_MISMATCH")
    item = catalog()["items"].get(row.get("variable_code"))
    if not item:
        raise NotEvaluated("UNSUPPORTED_SOURCE_QUANTITY")
    if p.get("quantity_kind") != item["quantity_kind"] or row["source_facts"]["quantity_kind"] != item["quantity_kind"]:
        raise NotEvaluated("SOURCE_QUANTITY_KIND_MISMATCH")
    if kind not in item["applicable_rules"] and kind not in {"LO", "DE", "PO"}:
        raise NotEvaluated("NOT_APPLICABLE_IN_TABLE_2_9")
    conflicts = item.get("conflicts", {}).get(kind, []) + catalog()["common_conflicts"].get(kind, [])
    if conflicts:
        evidence(prov.get("conflict_resolution"))
    if prov["profile_id"] == "APPENDIX1_SUMMARY_P81":
        ref = item["summary_profile"]
        if kind in {"ER", "GR", "GD", "SP"} and p.get("unit") != item["reference_unit"]:
            raise NotEvaluated("GUIDE_PROFILE_UNIT_MISMATCH")
        checks = {
            "ER": p.get("sentinels") == ref["missing_sentinels"],
            "GR": p.get("min") == ref["range_min"] and p.get("max") == ref["range_max"],
            "GD": ref["flat_duration_minutes"] is not None and p.get("duration_seconds") == ref["flat_duration_minutes"] * 60,
            "SP": [p.get("interval_seconds"), p.get("max_delta")] in ref["spike_interval_seconds_max_delta"],
            "DE": p.get("max_delay_seconds") == 86400,
        }
        if kind in checks and not checks[kind]:
            raise NotEvaluated("GUIDE_SELECTED_PROFILE_PARAMETER_MISMATCH")
    return p


def _history(records, index, p, context, duration):
    """Backward-only complete regular window; never bridge gaps/missing/episodes."""
    target = records[index]
    interval = positive(p, "interval_seconds")
    tolerance = number(p.get("interval_tolerance_seconds", 0))
    if tolerance < 0 or tolerance >= interval:
        raise NotEvaluated("INVALID_INTERVAL_TOLERANCE")
    end = utc(target["timestamp_utc"])
    window = [target]
    previous_time = end
    for earlier in reversed(records[:index]):
        if not isinstance(earlier, dict):
            raise NotEvaluated("RECORD_OBJECT_REQUIRED")
        # Other quantities may be interleaved. Same logical channel with a
        # different episode/unit is an explicit boundary, not an ignorable row.
        if tuple(earlier.get(k) for k in SCOPE_FIELDS[:3]) != tuple(target.get(k) for k in SCOPE_FIELDS[:3]):
            continue
        if _scope(earlier) != _scope(target):
            raise NotEvaluated("SOURCE_SCOPE_OR_EPISODE_CHANGED")
        t = _record(earlier, context)
        if abs((previous_time - t).total_seconds() - interval) > tolerance:
            raise NotEvaluated("INPUT_INTERVAL_GAP_DUPLICATE_OR_REVERSED")
        if earlier.get("value") is None:
            raise NotEvaluated("MISSING_VALUE_IN_WINDOW")
        if number(earlier["value"]) in [number(v) for v in p.get("missing_sentinels", [])]:
            raise NotEvaluated("MISSING_SENTINEL_IN_WINDOW")
        window.append(earlier)
        previous_time = t
        if (end - t).total_seconds() >= duration:
            return list(reversed(window))
    raise NotEvaluated("INSUFFICIENT_CAUSAL_WINDOW")


def _bound(value, lo, hi, boundary):
    if lo > hi:
        raise NotEvaluated("INVALID_LIMIT_ORDER")
    if boundary == "CLOSED":
        return value < lo or value > hi
    if boundary == "OPEN":
        return value <= lo or value >= hi
    raise NotEvaluated("EXPLICIT_BOUNDARY_POLICY_REQUIRED")


def _related(row, name, context):
    values = obj(row.get("auxiliary"), "RELATED_OBSERVATION_REQUIRED")
    related = obj(values.get(name), "RELATED_OBSERVATION_REQUIRED:" + name)
    when = _record(related, context)
    if when != utc(row["timestamp_utc"]):
        raise NotEvaluated("RELATED_TIMESTAMP_MISMATCH")
    if related["station_id"] != row["station_id"]:
        raise NotEvaluated("RELATED_STATION_MISMATCH")
    pairing = obj(row.get("pairing"), "REVIEWED_PAIRING_REQUIRED")
    evidence(pairing.get("evidence"))
    if pairing.get(name) != related["sensor_id"]:
        raise NotEvaluated("RELATED_SENSOR_PAIRING_MISMATCH")
    if related.get("value") is None:
        raise NotEvaluated("RELATED_VALUE_MISSING")
    return related


def _baseline(row, p, context, kind):
    baseline = obj(row.get("baseline"), "PAST_BASELINE_REQUIRED")
    evidence(baseline.get("evidence"))
    if tuple(baseline.get(k) for k in SCOPE_FIELDS) != tuple(row.get(k) for k in SCOPE_FIELDS):
        raise NotEvaluated("BASELINE_SCOPE_OR_UNIT_MISMATCH")
    if baseline.get("source_episode_policy") != "EXPLICIT_REVIEWED_REFERENCE":
        raise NotEvaluated("BASELINE_EPISODE_POLICY_REQUIRED")
    evidence(baseline.get("qc_exclusion_evidence"))
    when = utc(row["timestamp_utc"])
    start, end = utc(baseline.get("period_start")), utc(baseline.get("period_end"))
    if start > end or end >= when or utc(baseline.get("available_at")) > context["as_of"]:
        raise NotEvaluated("FUTURE_OR_UNAVAILABLE_BASELINE")
    calendar_timezone = p.get("calendar_timezone")
    if not isinstance(calendar_timezone, str) or not calendar_timezone or calendar_timezone != row["source_facts"].get("source_timezone_name") or calendar_timezone != baseline.get("calendar_timezone"):
        raise NotEvaluated("EXPLICIT_COMMON_SOURCE_CALENDAR_REQUIRED")
    try:
        zone = ZoneInfo(calendar_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise NotEvaluated("VALID_CALENDAR_TIMEZONE_REQUIRED") from None
    calendar_when, calendar_start, calendar_end = (stamp.astimezone(zone) for stamp in (when, start, end))
    if kind in {"RR", "SR"}:
        if p.get("baseline_policy") == "PREVIOUS_YEAR":
            if calendar_start.year != calendar_when.year - 1 or calendar_end.year != calendar_when.year - 1:
                raise NotEvaluated("PREVIOUS_YEAR_BASELINE_REQUIRED")
        elif p.get("baseline_policy") != "EXPLICIT_HISTORICAL_EXTREMES":
            raise NotEvaluated("BASELINE_POLICY_REQUIRED")
    if kind in {"SR", "ST"} and baseline.get("month") != calendar_when.month:
        raise NotEvaluated("SAME_MONTH_BASELINE_REQUIRED")
    if kind == "ST":
        years = baseline.get("years")
        if not isinstance(years, list) or any(type(y) is not int or y >= calendar_when.year or y < calendar_start.year or y > calendar_end.year for y in years) or len(set(years)) < 10:
            raise NotEvaluated("TEN_PRIOR_YEARS_REQUIRED")
        if baseline.get("statistic") != "MONTHLY_MEAN_STD" or not isinstance(baseline.get("sample_count"), int) or isinstance(baseline.get("sample_count"), bool) or baseline["sample_count"] < 2:
            raise NotEvaluated("BASELINE_STATISTIC_REQUIRED")
    return baseline


def _evaluate(records, index, rule, context):
    row = records[index]
    _record(row, context, clock_diagnostic=rule.get("kind") == "WT")
    p = _config(rule, row)
    kind = rule["kind"]
    used = [row]
    value_dependent = kind not in {"WT", "LO", "DE", "PO"}
    if row.get("value") is None and value_dependent:
        return "9", "MISSING", "NULL_VALUE", None, used
    value = number(row["value"]) if row.get("value") is not None else 0
    if value_dependent and kind != "ER":
        sentinels = p.get("missing_sentinels")
        if not isinstance(sentinels, list):
            raise NotEvaluated("EXPLICIT_MISSING_SENTINEL_POLICY_REQUIRED")
        if value in [number(v) for v in sentinels]:
            return "9", "MISSING", "DECLARED_MISSING_SENTINEL", None, used
    threshold = None
    fail = False
    if kind in {"WT", "DE"}:
        received = utc(row.get("received_at"))
        evidence(row.get("receive_evidence"))
        if received > utc(row["available_at"]):
            raise NotEvaluated("RECEIVE_TIME_AFTER_AVAILABLE_AT")
        delta = (received - utc(row["timestamp_utc"])).total_seconds()
        if kind == "WT":
            fail = delta < 0
        else:
            threshold = positive(p, "max_delay_seconds")
            fail = delta > threshold
    elif kind == "LO":
        location = obj(row.get("location"), "LOCATION_REQUIRED")
        evidence(location.get("evidence"))
        if location.get("coordinate_frame") != "WGS84" or p.get("method") != "WGS84_RECTANGLE":
            raise NotEvaluated("EXPLICIT_LOCATION_METHOD_REQUIRED")
        lat, lon = number(location.get("latitude")), number(location.get("longitude"))
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise NotEvaluated("INVALID_LOCATION_COORDINATES")
        if p.get("station_type") != row.get("station_type") or not row.get("station_type"):
            raise NotEvaluated("LOCATION_STATION_TYPE_REQUIRED")
        fail = _bound(lat, number(p.get("latitude_min")), number(p.get("latitude_max")), "CLOSED") or _bound(lon, number(p.get("longitude_min")), number(p.get("longitude_max")), "CLOSED")
    elif kind == "ER":
        sentinels = p.get("sentinels")
        if not isinstance(sentinels, list) or not sentinels:
            raise NotEvaluated("ITEM_SPECIFIC_SENTINELS_REQUIRED")
        fail = value in [number(x) for x in sentinels]
        if fail:
            return "9", "MISSING", "DECLARED_MISSING_SENTINEL", None, used
    elif kind == "GR":
        threshold = number(p.get("max"))
        fail = _bound(value, number(p.get("min")), threshold, p.get("boundary"))
    elif kind in {"GD", "SP"}:
        duration = positive(p, "duration_seconds") if kind == "GD" else positive(p, "interval_seconds")
        window_duration = duration + positive(p, "interval_seconds") if kind == "GD" and p.get("duration_boundary") == "GREATER_THAN" else duration
        used = _history(records, index, p, context, window_duration)
        if kind == "GD":
            tolerance = number(p.get("value_tolerance", 0))
            if tolerance < 0:
                raise NotEvaluated("INVALID_VALUE_TOLERANCE")
            elapsed = (utc(used[-1]["timestamp_utc"]) - utc(used[0]["timestamp_utc"])).total_seconds()
            boundary = p.get("duration_boundary")
            if boundary not in {"AT_LEAST", "GREATER_THAN"}:
                raise NotEvaluated("EXPLICIT_DURATION_BOUNDARY_REQUIRED")
            fail = (elapsed >= duration if boundary == "AT_LEAST" else elapsed > duration) and all(abs(Decimal(str(number(x["value"]))) - Decimal(str(value))) <= Decimal(str(tolerance)) for x in used)
            threshold = duration
        else:
            threshold = positive(p, "max_delta")
            delta = abs(Decimal(str(value)) - Decimal(str(number(used[-2]["value"]))))
            if p.get("difference") == "CIRCULAR_DEGREES":
                if row["unit"] != "degree" or not all(0 <= number(x["value"]) <= 360 for x in used):
                    raise NotEvaluated("ANGULAR_DEGREES_REQUIRED")
                delta = min(delta, Decimal(360) - delta)
            elif p.get("difference") != "LINEAR":
                raise NotEvaluated("EXPLICIT_DIFFERENCE_POLICY_REQUIRED")
            fail = delta > Decimal(str(threshold))
    elif kind == "RL":
        if p.get("failure_flag") not in {"3", "4"}:
            raise NotEvaluated("INTERNAL_CONSISTENCY_SEVERITY_POLICY_REQUIRED")
        method = p.get("method")
        related = _related(row, p.get("related_name"), context)
        used.append(related)
        other = number(related["value"])
        if related["variable_code"] != p.get("related_variable_code") or related["unit"] != p.get("related_unit"):
            raise NotEvaluated("RELATED_QUANTITY_OR_UNIT_MISMATCH")
        if method == "GUST_GE_WIND_SPEED":
            if row["unit"] != related["unit"]:
                raise NotEvaluated("RELATED_UNIT_MISMATCH")
            fail = other < value
        elif method == "CIRCULAR_DIRECTION_DIFFERENCE":
            if row["unit"] != "degree" or related["unit"] != "degree" or not 0 <= value <= 360 or not 0 <= other <= 360:
                raise NotEvaluated("ANGULAR_DEGREES_REQUIRED")
            threshold = positive(p, "max_delta")
            distance = abs(value - other)
            fail = min(distance, 360 - distance) > threshold
        elif method == "WAVE_HEIGHT_PERIOD":
            if row["variable_code"] != "WAVE_HEIGHT" or row["unit"] != "m" or related["variable_code"] != "WAVE_PERIOD" or related["unit"] != "s":
                raise NotEvaluated("WAVE_QUANTITY_AND_UNITS_REQUIRED")
            branch = p.get("period_equal_five")
            if branch not in {"LONG_PERIOD", "SHORT_PERIOD", "NOT_EVALUATED"}:
                raise NotEvaluated("WAVE_BRANCH_BOUNDARY_POLICY_REQUIRED")
            if other == 5 and branch == "NOT_EVALUATED":
                raise NotEvaluated("GUIDE_PERIOD_EQUAL_FIVE_UNSPECIFIED")
            threshold = 2.55 + other / 4 if other > 5 or (other == 5 and branch == "LONG_PERIOD") else 1.16 * other - 2
            fail = value >= threshold
        else:
            raise NotEvaluated("UNSUPPORTED_INTERNAL_CONSISTENCY_METHOD")
    elif kind in {"RR", "SR", "ST"}:
        baseline = _baseline(row, p, context, kind)
        used.append({"baseline": baseline})
        if kind == "ST":
            mean, std = number(baseline.get("mean")), number(baseline.get("std"))
            if std < 0:
                raise NotEvaluated("INVALID_BASELINE_STD")
            multiplier = positive(p, "std_multiplier")
            if not multiplier.is_integer():
                raise NotEvaluated("GUIDE_INTEGER_STD_MULTIPLIER_REQUIRED")
            threshold = multiplier * std
            fail = abs(value - mean) > threshold
        else:
            minimum, maximum = number(baseline.get("min")), number(baseline.get("max"))
            if p.get("limit_method") == "MULTIPLY_EXTREMES":
                lo = minimum * number(p.get("minimum_multiplier"))
                hi = maximum * number(p.get("maximum_multiplier"))
            elif p.get("limit_method") == "EXACT_EXTREMES":
                lo, hi = minimum, maximum
            else:
                raise NotEvaluated("EXPLICIT_BASELINE_LIMIT_METHOD_REQUIRED")
            threshold = hi
            fail = _bound(value, lo, hi, p.get("boundary"))
    elif kind == "PO":
        power = _related(row, p.get("related_name"), context)
        used.append(power)
        if power["unit"] != "V" or power["variable_code"] != p.get("related_variable_code"):
            raise NotEvaluated("POWER_VOLTAGE_QUANTITY_REQUIRED")
        threshold = number(p.get("minimum_voltage"))
        fail = number(power["value"]) < threshold
    failure_flag = p["failure_flag"] if kind == "RL" else "4" if kind in HARD else "3"
    return failure_flag if fail else "1", "EVALUATED", "LIMIT_EXCEEDED" if fail else "WITHIN_CONFIGURED_TEST", threshold, used


def execute_rules(records, rules, context):
    """Return one result for every requested record/rule, including non-evaluation.

    Explicit source facts are conditional inputs. A source approval is neither
    consumed nor created here; authoritative ingestion validates them separately.
    """
    if not isinstance(records, list) or not isinstance(rules, list) or not isinstance(context, dict):
        raise ValueError("records/rules must be lists and context an object")
    if len(records) * len(rules) > 120000 or len(rules) > 100 or len(records) > 10000:
        raise ValueError("analysis size limit exceeded")
    try:
        digest({"records": records, "rules": rules, "context": context})
        runtime = {"as_of": utc(context.get("as_of")), "executed_at": utc(context.get("executed_at"))}
    except (ValueError, TypeError, NotEvaluated) as exc:
        raise ValueError("invalid JSON or analysis clock: " + str(exc)) from None
    if runtime["executed_at"] < runtime["as_of"]:
        raise ValueError("executed_at cannot precede as_of")
    results, normalization_cache = [], {}
    for index, raw_row in enumerate(records):
        row = raw_row if isinstance(raw_row, dict) else {}
        for raw_rule in rules:
            rule = raw_rule if isinstance(raw_rule, dict) else {}
            flag, status, reason, threshold, used = "NOT_EVALUATED", "NOT_EVALUATED", "", None, [raw_row]
            try:
                # Normalize only the requested target and preceding rows of
                # that channel. Other quantities remain their original type.
                key = digest(raw_rule)
                if key not in normalization_cache:
                    prepared_records = []
                    for original in records:
                        try:
                            prepared_records.append(_normalized_record(original, rule))
                        except NotEvaluated as exc:
                            prepared_records.append(dict(original, _normalization_error=str(exc)) if isinstance(original, dict) else {"_normalization_error": str(exc)})
                    normalization_cache[key] = prepared_records
                prepared_records = normalization_cache[key]
                flag, status, reason, threshold, used = _evaluate(prepared_records, index, rule, runtime)
            except NotEvaluated as exc:
                reason = str(exc)
            except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
                reason = "MALFORMED_INPUT_OR_RULE_CONFIGURATION"
            prov = rule.get("provenance") if isinstance(rule.get("provenance"), dict) else {}
            scope = {k: row.get(k) for k in SCOPE_FIELDS}
            facts = row.get("source_facts") if isinstance(row.get("source_facts"), dict) else {}
            if isinstance(facts.get("sensor_episode_id"), str) and facts["sensor_episode_id"]:
                scope["sensor_episode_id"] = facts["sensor_episode_id"]
            results.append({
                "observation_id": row.get("observation_id"), "qc_rule_id": rule.get("qc_rule_id"),
                "rule_version": rule.get("rule_version"), "kind": rule.get("kind"),
                "scope": scope, "event_at": row.get("timestamp_utc"),
                "available_at": runtime["executed_at"].isoformat(), "input_value": row.get("value") if isinstance(row.get("value"), (float, int)) and not isinstance(row.get("value"), bool) else None,
                "threshold_value": threshold, "result_flag": flag, "evaluation_status": status,
                "result_reason": reason, "result_score": None,
                "provenance_json": {"engine_version": ENGINE_VERSION, "guide_sha256": GUIDE_SHA256,
                    **implementation_hashes(),
                    "pdf_pages": prov.get("pdf_pages", []), "profile_id": prov.get("profile_id"),
                    "rule_spec_sha256": digest(raw_rule), "input_window_sha256": digest(used),
                    "input_observation_ids": [x.get("observation_id") for x in used if isinstance(x, dict) and "observation_id" in x],
                    "evidence_scope": {k: row.get(k) for k in SCOPE_FIELDS},
                    "source_facts": row.get("source_facts"), "event_at": row.get("timestamp_utc"),
                    "available_at": runtime["executed_at"].isoformat(), "executed_at_utc": runtime["executed_at"].isoformat(),
                    "event_clock_policy": "EXPLICIT_OFFSET_INSTANT",
                    "input_available_at": row.get("available_at"),
                    "evaluation_unit": (rule.get("parameters") or {}).get("unit") if isinstance(rule.get("parameters"), dict) else None,
                    "input_normalization": next((x.get("normalization") for x in used if isinstance(x, dict) and x.get("observation_id") == row.get("observation_id")), None),
                    "as_of": runtime["as_of"].isoformat(), "metadata_authority": "SUPPLIED_CONDITIONAL_ANALYSIS_INPUT",
                    "configuration": rule, "approval_created": False},
                "approved": False, "analysis_only": True,
            })
    report = {"schema_version": "guide-qc-report-v1", "engine_version": ENGINE_VERSION,
        "status": "ANALYSIS_ONLY", "approved": False, "record_count": len(records), "requested_rule_count": len(rules),
        "summary": dict(Counter(r["evaluation_status"] for r in results)), "results": results}
    report["result_sha256"] = digest(report)
    return report


def to_fusion_evidence(result):
    """Rule severity is supporting evidence, never a fault probability."""
    evaluated = result["evaluation_status"] == "EVALUATED"
    anomaly = evaluated and result["result_flag"] in {"3", "4"}
    strength = 1.0 if evaluated and result["result_flag"] in {"1", "4"} else 0.5 if anomaly else 0.0
    return {"category": "RULE", "source_kind": "GUIDE_RULE_RESULT", "source_id": f'{result["observation_id"]}:{result["qc_rule_id"]}:{result["rule_version"]}',
        "source_sha256": digest(result), "locator": {"observation_id": result["observation_id"], "rule_spec_sha256": result["provenance_json"]["rule_spec_sha256"]},
        "scope": result["scope"], "event_at": result["event_at"], "available_at": result["available_at"],
        "claim": "OBSERVATION_ANOMALY" if anomaly else "NORMAL" if evaluated else None,
        "assessment": "ANOMALY" if anomaly else "NORMAL" if evaluated and result["result_flag"] == "1" else "UNKNOWN",
        "result_reason": result["result_reason"], "support_strength": strength,
        "result_status": result["evaluation_status"], "approved": False}
