"""Bijection to the reviewed 72 task keys; code coverage is not model approval."""
import hashlib
import json
from pathlib import Path


def adapter_coverage():
    path = Path(__file__).with_name("model_scope_matrix.json")
    raw = path.read_bytes()
    matrix = json.loads(raw)
    rows = []
    for original in matrix["rows"]:
        domain, representation = original["domain"], original["representation"]
        kind = "SCALAR"
        if representation == "circular_direction_with_paired_magnitude":
            kind = "CIRCULAR_DEGREES"
        elif domain == "hf_radial":
            kind = "SIGNED_RADIAL"
        elif domain == "hf_total":
            kind = "VECTOR_UV"
        elif domain == "drifter":
            kind = "TRAJECTORY"
        elif domain in {"coastal_manual", "ship_ADCP", "CTD_profile", "survey_current_multilayer", "survey_current_single_layer"}:
            kind = "PROFILE_BINS"
        task = original["task"].upper()
        rows.append({"domain": domain, "item_id": original["item_id"], "task": original["task"], "runtime_task": task,
            "registry_target_task": "FORECASTING" if task == "FORECASTING" else "CLASSIFICATION",
            "quantity_kind": kind, "code_status": "REPRESENTATION_BASELINE_SCOPE_PARTIAL",
            "candidate_target_channels": original["item_id"].split(";"),
            "supported_target_channels": ["position"] if domain == "drifter" else original["item_id"].split(";"),
            "supported_scope": "EXPLICIT_SINGLE_CHANNEL_FIXED_BINS" if kind == "PROFILE_BINS" else "APPROVED_GRID_CELL_VECTOR_NOT_FULL_FIELD" if domain == "hf_total" else "EXPLICIT_TYPED_SINGLE_ORIGIN_TARGET",
            "training_status": "NOT_EXECUTED_ON_APPROVED_SOURCE", "operating_model_selected": False,
            "source_contract_required": "DIRECT_APPROVED_TYPED_COLUMN_BINDINGS" if kind != "SCALAR" else "APPROVED_SOURCE_ROW_QUANTITY_SEMANTICS",
            "forecast_target_definition_required": original["task"] == "forecasting",
            "baseline": "REPRESENTATION_PERSISTENCE" if task == "FORECASTING" else "ALL_NORMAL_AND_FROZEN_GUIDE_RULE_EVIDENCE" if task == "QUALITY_REVIEW" else "ALL_NORMAL",
            "candidate": "CAUSAL_TYPED_RIDGE" if task == "FORECASTING" else "TRAIN_NORMAL_ROBUST_FEATURE_SCORE",
            "metric_contract": {"CIRCULAR_DEGREES": "WRAPPED_DEGREE_ERROR", "VECTOR_UV": "UV_AND_VECTOR_NORM_ERROR", "PROFILE_BINS": "EXPLICIT_EQUAL_WEIGHT_BIN_ERROR_NO_INTERPOLATION", "TRAJECTORY": "SPHERICAL_ENDPOINT_METERS_LATITUDE_LT85"}.get(kind, "APPROVED_UNIT_ABSOLUTE_ERROR") if task == "FORECASTING" else "UNADJUSTED_POINT_AND_EVENT_BINARY_METRICS_NOT_CAUSE_OR_FINAL_QC",
            "limitations": ["No implicit joining, bin interpolation or forward-fill", "Reviewed labels and immutable same holdout required", "Quality evidence does not mutate source QC", "No unverified legacy weights loaded"] + (["This trajectory adapter evaluates position; derived-current and optional-channel adapters require their own explicit contracts"] if domain == "drifter" else [])})
    keys = {(r["domain"], r["item_id"], r["task"]) for r in rows}
    if len(keys) != 72 or len(rows) != 72:
        raise ValueError("72_TASK_KEY_BIJECTION_FAILED")
    return {"schema_version": "model-adapter-coverage-1", "source_matrix_sha256": hashlib.sha256(raw).hexdigest(),
            "task_keys": len(rows), "code_implementations": 6, "task_algorithms": 3, "registered_models_by_coverage": 0,
            "operational_completion": False, "rows": rows}
