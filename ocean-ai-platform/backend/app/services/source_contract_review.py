"""Evidence-scoped source dictionary review; never grants operational approval.

The dictionary's station and item columns are independent lists.  A shared row
does not establish a station-to-item, sensor, unit, period, or QC relationship.
Source families must be supplied with an explicit, hashed adapter contract.
There is deliberately no cross-sheet or station-prefix fallback.
"""
from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
import re

VERSION = "source-contract-review-v1"
GRAIN = ("source_group", "station_code", "item_code", "depth_step", "depth_from", "depth_to", "month")


def _value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_value(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(_value(value), sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def exact_scope_key(row):
    """Type-sensitive and NULL-preserving; caller must supply canonical month."""
    return digest([[k, type(row.get(k)).__name__, _value(row.get(k))] for k in GRAIN])


def _family(sheet):
    return str(sheet or "").split("(", 1)[0]


def review_contracts(rows, dictionary, source_adapters, verified_evidence_shas,
                     guide_items=(), lexical_candidates=(), guide_sha256=None,
                     open_rule_issues=()):
    """Review every supplied channel-month, with a reproducible universe receipt.

    An adapter entry is {family, evidence_sha256}.  The evidence must itself be
    verified.  Dictionary references also require a current verified source hash.
    A guide item is only a reference candidate and can never populate source unit.
    Input approvals, source flags, and historical checks remain input claims.
    """
    rows = [_value(dict(r)) for r in rows]
    station_index, item_index = defaultdict(list), defaultdict(list)
    for row in dictionary.get("stations", ()):
        station_index[row.get("code")].append(row)
    for row in dictionary.get("items", ()):
        item_index[row.get("code")].append(row)
    guide_index = {r["item_id"]: r for r in guide_items}
    lexical_index = defaultdict(list)
    for candidate in lexical_candidates:
        for code in candidate.get("lexical_code_candidates", ()):
            lexical_index[code].append(candidate["item_id"])
    keys = [exact_scope_key(r) for r in rows]
    key_counts = Counter(keys)
    verified_evidence_shas = set(verified_evidence_shas)
    output = []
    for row, key in zip(rows, keys):
        adapter = source_adapters.get(row.get("source_group"), {})
        family = adapter.get("family")
        adapter_verified = adapter.get("evidence_sha256") in verified_evidence_shas and bool(family)
        station_sheets = {r.get("sheet") for r in station_index[row.get("station_code")]
                          if _family(r.get("sheet")) == family
                          and r.get("sha256") in verified_evidence_shas} if adapter_verified else set()
        family_sheets = {r.get("sheet") for r in dictionary.get("items", ())
                         if _family(r.get("sheet")) == family}
        # One source-family worksheet is sufficient for its item dictionary.
        # A family with multiple worksheets needs the exact station's worksheet.
        allowed_sheets = station_sheets or (family_sheets if len(family_sheets) == 1 else set())
        entries = [r for r in item_index[row.get("item_code")]
                   if adapter_verified and r.get("sheet") in allowed_sheets]
        unverified = [r for r in entries if r.get("sha256") not in verified_evidence_shas]
        entries = [r for r in entries if r.get("sha256") in verified_evidence_shas]
        # Different source labels or explicit source units are a conflict.  Do not
        # collapse two units merely because the display labels happen to match.
        signatures = {(r.get("report_label") or r.get("label"), r.get("source_unit")) for r in entries}
        if not adapter_verified:
            state = "SOURCE_ADAPTER_UNVERIFIED"
        elif not allowed_sheets:
            state = "WORKSHEET_SCOPE_UNRESOLVED"
        elif unverified:
            state = "DICTIONARY_SOURCE_HASH_UNVERIFIED"
        elif not entries:
            state = "EXACT_SOURCE_ITEM_NOT_IN_DICTIONARY"
        elif len(signatures) != 1:
            state = "DICTIONARY_REFERENCE_CONFLICT"
        else:
            state = "AUTO_VERIFIED_DICTIONARY_REFERENCE"
        candidates = sorted(set(lexical_index[row.get("item_code")]))
        reference_units = [dict(item_id=k, unit_reference=guide_index[k].get("unit_reference"),
                                pdf_pages=guide_index[k].get("reference_pages", []),
                                source_sha256=guide_sha256,
                                status="GUIDE_REFERENCE_NOT_SOURCE_UNIT_OR_ADOPTION")
                           for k in candidates if k in guide_index]
        blockers = ["SOURCE_SEMANTICS_NOT_APPROVED", "SOURCE_UNIT_APPLICATION_UNRESOLVED",
                    "SOURCE_CLOCK_TIMEZONE_UNRESOLVED", "SOURCE_QC_CODEBOOK_UNVERIFIED",
                    "ADOPTED_RULE_VERSION_AND_EFFECTIVE_INTERVAL_UNVERIFIED", "QC_APPROVAL_REQUIRED"]
        required_key_missing = any(row.get(k) is None or row.get(k) == "" for k in
                                   ("source_group", "station_code", "item_code"))
        month_invalid = not isinstance(row.get("month"), str) or not re.fullmatch(
            r"\d{4}-(0[1-9]|1[0-2])", row.get("month") or "")
        if required_key_missing or month_invalid:
            blockers.append("EXACT_CHANNEL_MONTH_KEY_INCOMPLETE_OR_INVALID")
        if state != "AUTO_VERIFIED_DICTIONARY_REFERENCE":
            blockers.append(state)
        if key_counts[key] != 1:
            blockers.append("DUPLICATE_EXACT_CHANNEL_MONTH_GRAIN")
        if not row.get("physical_sensor_id"):
            blockers.append("PHYSICAL_SENSOR_ID_UNRESOLVED")
        if not row.get("valid_from") or not row.get("valid_to"):
            blockers.append("SENSOR_VALID_INTERVAL_UNRESOLVED")
        if row.get("period_decision") == "충돌" or row.get("overall_decision") == "충돌":
            blockers.append("INPUT_EVIDENCE_CONFLICT_REQUIRES_REVIEW")
        record = dict(scope={k: row.get(k) for k in GRAIN}, exact_scope_key=key,
                      source_record_id=row.get("record_id"), input_record_sha256=digest(row),
                      status="BLOCKED_DRAFT", approved=False,
                      grain_validation="INVALID_KEY" if required_key_missing or month_invalid else
                      "AUTO_VERIFIED_UNIQUE" if key_counts[key] == 1 else "CONFLICT_DUPLICATE",
                      dictionary_reference=dict(status=state, source_family=family,
                                                adapter_evidence_sha256=adapter.get("evidence_sha256"),
                                                worksheet_candidates=sorted(allowed_sheets),
                                                source_label_candidates=sorted(str(s[0]) for s in signatures),
                                                evidence=[{k: r.get(k) for k in ("sha256", "sheet", "row", "column")}
                                                          for r in entries]),
                      semantic_mapping=dict(status="LEXICAL_CANDIDATE_ONLY", candidates=candidates,
                                            approved_standard_variable=None),
                      unit=dict(source_unit=None, approved_standard_unit=None, reference_candidates=reference_units),
                      timezone_name=None, adopted_rule_version=None, approved_qc_valid_rows=None,
                      source_qc=dict(status="PRESERVED_UNINTERPRETED",
                                     source_qc_present_rows=row.get("source_qc_present_rows"),
                                     source_mq_present_rows=row.get("source_mq_present_rows"),
                                     literal_flags=row.get("literal_flags")),
                      prior_input_approval_status=row.get("approval_status"),
                      held_rows=row.get("held_rows"), blockers=sorted(set(blockers)))
        record["record_sha256"] = digest(record)
        output.append(record)
    counts = Counter(r["dictionary_reference"]["status"] for r in output)
    invalid_grain_rows = sum(r["grain_validation"] == "INVALID_KEY" for r in output)
    unique_coverage = bool(rows) and not any(v > 1 for v in key_counts.values()) and not invalid_grain_rows
    summary = dict(contract_version=VERSION, status="BLOCKED_DRAFT", approved=False,
                   scope="ALL_SUPPLIED_CHANNEL_MONTHS_NOT_ALL_DOCUMENTS_OR_ALL_HISTORICAL_OBSERVATIONS",
                   enumeration_complete=len(rows) == len(output),
                   unique_grain_coverage_complete=unique_coverage,
                   coverage_complete=unique_coverage, input_rows=len(rows), output_rows=len(output),
                   exact_scope_keys=len(key_counts), duplicate_scope_keys=sum(v > 1 for v in key_counts.values()),
                   invalid_grain_rows=invalid_grain_rows,
                   universe_sha256=digest(sorted(keys)), held_rows=sum(r.get("held_rows") or 0 for r in rows),
                   held_row_semantics="SOURCE_HELD_ROWS_NOT_DEDUPLICATED_OBSERVATIONS",
                   dictionary_reference_counts=dict(sorted(counts.items())),
                   semantic_approvals=0, unit_application_approvals=0, timezone_approvals=0, qc_approvals=0,
                   operational_rule_approvals=0,
                   open_reference_rule_issues=list(open_rule_issues), mutations=[])
    summary["receipt_sha256"] = digest(dict(summary=summary, record_shas=[r["record_sha256"] for r in output]))
    return dict(summary=summary, contracts=output)
