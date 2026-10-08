"""Fail-closed invariants; no database setup or source mutations required."""
from copy import deepcopy
import unittest
from app.services.qc_review_agent import digest, review_bundle, load_registry_evidence
from app.agents.qc_copilot_agent import detect_anomalies_node


def evidence():
    return dict(status="LOADED_REVIEW_ONLY", run_id="fixture", as_of="2026-07-31",
        scope=dict(station_id="DT_0001", item_code="AIR_PRES", start_month="2025-01",
                   end_month="2025-01", source_group="fixture-source"), tables={
        "facility": [dict(record_id="f", station_code="DT_0001")],
        "channel_month": [dict(record_id="c", station_code="DT_0001", item_code="AIR_PRES",
             month="2025-01", last_clock="2025-01-31", physical_sensor_id=None,
             valid_from=None, valid_to=None, nominal_interval_seconds=None,
             approval_status="UNAPPROVED", payload={"depth_step": 0})],
        "lifecycle_claim": [], "equipment_claim": [], "document_link": [], "document": []})


class QCReviewTests(unittest.TestCase):
    def test_empty_is_not_good(self):
        result = review_bundle([])
        self.assertEqual(result["recommended_flag"], "NOT_EVALUATED")
        self.assertIsNone(result["current_recheck"]["normal_ratio"])
        self.assertIn("NO_OBSERVATIONS_SUPPLIED", result["blockers"])

    def test_source_flags_preserved_never_promoted(self):
        rows = [{"qc_flag": "OK", "mqc_flag": "G", "value": 15}, {"qc_flag": "0", "mqc_flag": None}]
        before = deepcopy(rows)
        result = review_bundle(rows, evidence())
        self.assertEqual(result["source_qc"]["counts"]["qc_flag"], {"0": 1, "OK": 1})
        self.assertEqual(result["source_qc"]["counts"]["mqc_flag"], {"<NULL>": 1, "G": 1})
        self.assertIsNone(result["final_flag"])
        self.assertEqual(rows, before)

    def test_unknown_sensor_and_depth_preserved(self):
        result = review_bundle([], evidence())
        row = result["interval_evidence"]["channels"][0]
        self.assertIsNone(row["physical_sensor_id"])
        self.assertEqual(row["payload"]["depth_step"], 0)
        self.assertIn("SENSOR_INTERVAL_OR_CADENCE_UNRESOLVED", result["blockers"])

    def test_retirement_conflict_not_bad_label(self):
        ev = evidence()
        ev["tables"]["lifecycle_claim"] = [dict(record_id="event", event_type="RETIRED", date_latest="2024-12-31")]
        result = review_bundle([], ev)
        self.assertEqual(result["conflicts"][0]["channel_ids"], ["c"])
        self.assertEqual(result["recommended_flag"], "NOT_EVALUATED")
        self.assertEqual(result["documentary_event_support"][0]["sensor_causation"], "NOT_ESTABLISHED")

    def test_hash_deterministic_and_content_sensitive(self):
        rows = [{"value": 15, "timestamp": "2025-01-01"}]
        one = review_bundle(rows, evidence())
        self.assertEqual(one, review_bundle(rows, evidence()))
        altered = review_bundle([{**rows[0], "value": 16}], evidence())
        self.assertNotEqual(one["audit"]["input_sha256"], altered["audit"]["input_sha256"])
        claimed = one["audit"].pop("result_sha256")
        self.assertEqual(claimed, digest(one))
        self.assertEqual(one["audit"]["mutations"], [])

    def test_stored_not_evaluated_remains_stored_not_new_evaluation(self):
        checks = [dict(result_flag="NOT_EVALUATED", qc_rule_id="r", rule_version="1")]
        result = detect_anomalies_node({"raw_data": [{"value": 9999}], "qc_rechecks": checks})
        self.assertEqual(result["anomalies"], [])
        metrics = result["qc_metrics"]
        self.assertIsNone(metrics["ai_accuracy"])
        self.assertIsNone(metrics["normal_ratio"])
        self.assertEqual(metrics["review"]["current_recheck"]["results"], checks)

    def test_truncated_evidence_and_unit_blockers(self):
        ev = evidence(); ev["truncated_tables"] = ["channel_month"]
        row = dict(station_id="DT_0001", variable_code="AIR_PRES", timestamp="2025-01-01")
        result = review_bundle([row], ev)
        self.assertIn("EVIDENCE_TRUNCATED", result["blockers"])
        self.assertIn("OBSERVATION_UNIT_UNRESOLVED", result["blockers"])
        self.assertEqual(result["observation_scope_problem_indices"], [])

    def test_invalid_query_rejected_before_database_call(self):
        for args in [("", "AIR_PRES", "2025-01", "2025-02"),
                     ("DT_0001", "AIR_PRES", "2025-13", "2025-14"),
                     ("DT_0001", "AIR_PRES", "2025-02", "2025-01")]:
            with self.assertRaises(ValueError):
                load_registry_evidence(None, *args)


if __name__ == "__main__":
    unittest.main()
