"""Technical evidence review; never creates events, aliases or approval rows."""
import json
import re
from collections import Counter
from pathlib import Path

from app.rag.ingestion_recovery import canonical, guarded, now, sha_file
from app.rag.report_parser import parse


def native_serial_claims(path, expected_sha, serials=("1276", "1326")):
    source = guarded(path)
    if sha_file(source) != expected_sha:
        raise ValueError("NATIVE_HISTORY_SOURCE_CHANGED")
    units = parse(source)
    claims = []
    heading = None
    date = None
    for index, unit in enumerate(units):
        text = unit.text.strip()
        if re.fullmatch(r"[가-힣\s]+조위관측소", text):
            heading = {"literal": text, "locator": unit.locator, "unit_index": index}
            date = None
        if re.fullmatch(r"[‘’'`]?\d{2,4}\.\d{2}\.\d{2}\.(?:-\d{2}\.\d{2}\.)?", text):
            date = {"literal": text, "locator": unit.locator, "unit_index": index,
                    "precision": "DAY_OR_HEADER_DAY_RANGE", "timezone": None, "utc": None}
        if not any(re.search(r"(?<!\d)" + re.escape(serial) + r"(?!\d)", text) for serial in serials):
            continue
        # Serial cell followed by a date is an inventory date claim, not the
        # most recent maintenance header encountered elsewhere in the document.
        inventory_date = None
        if text in serials and index + 1 < len(units) and re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.", units[index + 1].text.strip()):
            inventory_date = {"literal": units[index + 1].text.strip(), "locator": units[index + 1].locator,
                              "precision": "DAY", "timezone": None, "utc": None}
        claims.append({"claim_id": sha_file_claim(expected_sha, unit.locator), "source_sha256": expected_sha,
                       "source_path": str(source), "locator": unit.locator, "unit_index": index,
                       "text": text, "station_heading": heading, "reported_action_date_or_header": None if inventory_date else date,
                       "inventory_date_claim": inventory_date, "approved": False,
                       "physical_serial_identity": "UNAPPROVED_SERIAL_LITERAL_ONLY",
                       "station_qualified_instrument_candidate": sha_file_claim(expected_sha,
                           (heading or {}).get("literal", "UNKNOWN_STATION") + ":" + ",".join(s for s in serials if s in text))})
    if sha_file(source) != expected_sha:
        raise ValueError("NATIVE_HISTORY_SOURCE_CHANGED_DURING_REVIEW")
    return {"schema_version": "native-sensor-history-technical-review-v1", "checked_at": now(),
            "source_path": str(source), "source_sha256": expected_sha, "native_units_reviewed": len(units),
            "serial_literals": list(serials), "claims": claims, "approved": False}


def sha_file_claim(sha, locator):
    import hashlib
    return hashlib.sha256(canonical([sha, locator])).hexdigest()


def review_event_cases(case_path, conflict_path, native_path):
    cases = json.loads(guarded(case_path).read_bytes())
    conflict = json.loads(guarded(conflict_path).read_bytes())
    native = json.loads(guarded(native_path).read_bytes())
    if not isinstance(cases, list) or len({c.get("case_id") for c in cases}) != len(cases):
        raise ValueError("EVENT_CASE_IDS_INVALID")
    histories = native_serial_claims(native["path"], native["sha256"])
    receipts = []
    cache = {}
    for case in cases:
        evidence = case["evidence"]
        checks = []
        for path, expected in ((evidence["document_path"], evidence["source_sha256"]),
                               (evidence["dictionary_path"], evidence["dictionary_sha256"])):
            key = (path, expected)
            if key not in cache:
                try:
                    cache[key] = sha_file(guarded(path)) == expected
                except (OSError, ValueError):
                    cache[key] = False
            checks.append({"path": path, "sha256": expected, "passed": cache[key]})
        receipts.append({"case_id": case["case_id"], "reported_name": case["reported_name"],
            "reported_facility_type": case["reported_facility_type"], "reported_item": case["reported_item"],
            "report_locator": evidence["locator"], "preservation_checks": checks,
            "technical_reason": case["technical_reason"], "source_candidate_grains": case.get("candidate_item_grains", 0),
            "reported_months": case["degradation_months"],
            "reported_condition_and_action_dates": case["reported_condition_and_action_dates"],
            "missing": case["missing"], "next_required": case["reviewer_question"],
            "technical_state": "EVIDENCE_REVERIFIED_REVIEW_REQUIRED" if all(c["passed"] for c in checks) else "EVIDENCE_CHANGED_OR_MISSING",
            "authority_state": "PENDING_NO_HUMAN_APPROVAL", "approved": False})
    installation = [c for c in histories["claims"] if "118→1276" in c["text"] and (c.get("station_heading") or {}).get("literal") == "인천 조위관측소"]
    cross_facility = [c for c in histories["claims"] if "1326" in c["text"] and (c.get("station_heading") or {}).get("literal") != "인천 조위관측소"]
    conflict_review = {"case_id": conflict["case"]["id"], "distinct_cases": conflict["distinct_cases"],
        "affected_month_grains": conflict["affected_month_grains"], "affected_scope_keys": conflict["affected_scope_keys"],
        "original_facts": conflict["facts"], "new_history_claims": histories["claims"],
        "technically_resolved_missing": ["SERIAL1276_PRE2021_INSTALL_RECORD_FOUND_AT_DAY_PRECISION"] if installation else [],
        "serial_cross_facility_references": cross_facility,
        "missing": ["SERIAL1326_HISTORY_OR_INVENTORY_CORRECTION_REVIEW", "SERIAL_LITERAL_CROSS_FACILITY_PHYSICAL_IDENTITY",
                    "EXACT_SENSOR_INTERVAL_ENDPOINT_CLOCK", "POST2021_CONTINUOUS_DEPLOYMENT_END_BOUNDARY", "SOURCE_CHANNEL_ID_AND_CLOCK_BINDING"],
        "technical_conclusion": "ADDITIONAL_SERIAL_HISTORY_FOUND_CONTINUOUS_EPISODE_AND_INVENTORY_DATE_STILL_UNRESOLVED",
        "authority_state": "PENDING_NO_HUMAN_APPROVAL", "approved": False}
    conflict_review["scope_decisions"] = [{"exact_scope_key": key,
        "technical_state": "ADDITIONAL_DAY_GRAIN_HISTORY_FOUND_INTERVAL_STILL_AMBIGUOUS",
        "left_boundary": "INVENTORY2019_DATE_CONFLICTS_WITH1276_REPLACEMENT_HISTORY",
        "right_boundary": "POST2021_DEPLOYMENT_END_UNPROVEN",
        "utc_episode": None, "physical_sensor_id": None, "approved": False,
        "evidence_claim_ids": [c["claim_id"] for c in histories["claims"]]}
        for key in conflict_review["affected_scope_keys"]]
    summary = {"schema_version": "event-case-review-v2", "checked_at": now(), "reported_cases": len(receipts),
        "reverified_case_sources": sum(r["technical_state"] == "EVIDENCE_REVERIFIED_REVIEW_REQUIRED" for r in receipts),
        "technical_reason_counts": dict(Counter(r["technical_reason"] for r in receipts)),
        "distinct_period_conflicts": conflict_review["distinct_cases"], "affected_month_grains": conflict_review["affected_month_grains"],
        "native_history_claim_count": len(histories["claims"]), "new_pre2021_installation_claims": len(installation),
        "cross_facility_serial_claims": len(cross_facility), "approved": False, "events_created": 0,
        "status": "PASS" if all(c["passed"] for r in receipts for c in r["preservation_checks"]) else "FAILED",
        "failed": sum(not c["passed"] for r in receipts for c in r["preservation_checks"]),
        "passed": sum(c["passed"] for r in receipts for c in r["preservation_checks"])}
    return {"summary": summary, "cases": receipts, "period_conflict": conflict_review, "native_history": histories}
