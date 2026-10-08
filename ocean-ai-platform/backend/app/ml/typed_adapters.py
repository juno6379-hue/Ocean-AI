"""Typed baselines/metrics; no invented spatial, depth or temporal alignment."""
import math
import time
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix
from app.ml.comparison_runner import ComparisonBlocked, finite

KINDS = {"SCALAR", "CIRCULAR_DEGREES", "SIGNED_RADIAL", "VECTOR_UV", "PROFILE_BINS", "TRAJECTORY"}
EARTH_RADIUS_M = 6371008.8


def validate_payload(payload):
    kind = payload.get("representation")
    if kind not in KINDS:
        raise ComparisonBlocked("TYPED_REPRESENTATION_NOT_DEFINED")
    if kind == "SCALAR":
        return np.array([finite(payload.get("value"), "value")])
    if kind == "CIRCULAR_DEGREES":
        angle = finite(payload.get("value"), "direction")
        if not 0 <= angle < 360 or finite(payload.get("magnitude"), "paired_magnitude") < 0 or not payload.get("magnitude_unit"):
            raise ComparisonBlocked("CIRCULAR_ANGLE_OR_PAIRED_MAGNITUDE_INVALID")
        return np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
    if kind == "SIGNED_RADIAL":
        if not payload.get("coordinate_frame") or not payload.get("site_geometry_version") or payload.get("qc_eligible") is not True:
            raise ComparisonBlocked("HF_RADIAL_GEOMETRY_OR_APPROVED_QC_SCOPE_MISSING")
        coverage = finite(payload.get("coverage_fraction"), "coverage")
        if not 0 <= coverage <= 1:
            raise ComparisonBlocked("HF_COVERAGE_INVALID")
        return np.array([finite(payload.get("value"), "signed_radial_velocity")])
    if kind == "VECTOR_UV":
        if not all(payload.get(k) for k in ("coordinate_frame", "grid_cell_id", "geometry_version")):
            raise ComparisonBlocked("VECTOR_FRAME_GRID_GEOMETRY_MISSING")
        return np.array([finite(payload.get("u"), "u"), finite(payload.get("v"), "v")])
    if kind == "PROFILE_BINS":
        bins, depths, values = payload.get("bin_ids"), payload.get("depths"), payload.get("values")
        if (not isinstance(bins, list) or not bins or len(bins) != len(set(bins)) or not isinstance(depths, list)
                or not isinstance(values, list) or len(bins) != len(depths) or len(bins) != len(values)
                or not payload.get("layout_version") or not payload.get("coordinate_frame") or not payload.get("target_variable") or not payload.get("unit")
                or payload.get("value_representation") not in {"SCALAR", "CIRCULAR_DEGREES"}):
            raise ComparisonBlocked("PROFILE_FIXED_BIN_LAYOUT_MISSING")
        for d in depths:
            finite(d, "explicit_depth")
        numeric = np.array([finite(v, "bin_value") for v in values])
        if payload["value_representation"] == "CIRCULAR_DEGREES":
            if payload["unit"] != "degree" or ((numeric < 0) | (numeric >= 360)).any():
                raise ComparisonBlocked("PROFILE_DIRECTION_UNIT_OR_VALUE_INVALID")
            return np.column_stack((np.cos(np.radians(numeric)), np.sin(np.radians(numeric)))).ravel()
        return numeric
    lon, lat = finite(payload.get("longitude"), "longitude"), finite(payload.get("latitude"), "latitude")
    if payload.get("coordinate_frame") != "WGS84" or not payload.get("trajectory_id") or not -180 <= lon < 180 or abs(lat) >= 85:
        raise ComparisonBlocked("TRAJECTORY_FRAME_OR_LOCAL_SPHERICAL_SCOPE_UNSUPPORTED")
    return np.array([lon, lat])


def signature(payload):
    kind = payload["representation"]
    fields = {"SIGNED_RADIAL": ("coordinate_frame", "site_geometry_version"),
        "VECTOR_UV": ("coordinate_frame", "grid_cell_id", "geometry_version"),
        "PROFILE_BINS": ("coordinate_frame", "layout_version", "bin_ids", "depths", "target_variable", "unit", "value_representation"),
        "TRAJECTORY": ("coordinate_frame", "trajectory_id"), "CIRCULAR_DEGREES": ("magnitude_unit",)}.get(kind, ())
    from app.ml.comparison_runner import digest
    return digest({"representation": kind, **{k: payload.get(k) for k in fields}})


def encode_target(origin, target):
    before, after = validate_payload(origin), validate_payload(target)
    if signature(origin) != signature(target):
        raise ComparisonBlocked("TYPED_TARGET_ORIGIN_ALIGNMENT_CHANGED")
    if origin["representation"] != "TRAJECTORY":
        return after, before
    lon_delta = (after[0] - before[0] + 180) % 360 - 180
    return np.array([EARTH_RADIUS_M * math.radians(lon_delta) * math.cos(math.radians(before[1])),
                     EARTH_RADIUS_M * math.radians(after[1] - before[1])]), np.zeros(2)


def endpoint(origin, delta):
    lon, lat = validate_payload(origin)
    return np.array([((lon + math.degrees(delta[0] / (EARTH_RADIUS_M * math.cos(math.radians(lat)))) + 180) % 360) - 180,
                     lat + math.degrees(delta[1] / EARTH_RADIUS_M)])


def haversine(left, right):
    left, right = np.radians(left), np.radians(right)
    delta = right - left
    a = np.sin(delta[:, 1] / 2) ** 2 + np.cos(left[:, 1]) * np.cos(right[:, 1]) * np.sin(delta[:, 0] / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def typed_metrics(actual, prediction, kind, origins=None):
    actual, prediction = np.asarray(actual), np.asarray(prediction)
    if actual.shape != prediction.shape or not np.isfinite([actual, prediction]).all():
        raise ComparisonBlocked("TYPED_PREDICTION_SHAPE_OR_FINITE_FAILURE")
    difference = prediction - actual
    extra = {}
    if kind == "CIRCULAR_DEGREES":
        norm = np.linalg.norm(prediction, axis=1)
        if (norm < 1e-12).any():
            raise ComparisonBlocked("CIRCULAR_PREDICTION_DIRECTION_UNDEFINED")
        expected = np.degrees(np.arctan2(actual[:, 1], actual[:, 0]))
        predicted = np.degrees(np.arctan2(prediction[:, 1], prediction[:, 0]))
        errors = (predicted - expected + 180) % 360 - 180
        extra["metric_unit"] = "degree_wrapped"
    elif kind == "TRAJECTORY":
        expected = np.array([endpoint(o, d) for o, d in zip(origins, actual)])
        predicted = np.array([endpoint(o, d) for o, d in zip(origins, prediction)])
        errors = haversine(expected, predicted)
        extra.update(metric_unit="meter_spherical_endpoint", geodesic_model="MEAN_RADIUS_SPHERE_APPROXIMATION", maximum_absolute_latitude=85)
    elif kind == "VECTOR_UV":
        errors = np.linalg.norm(difference, axis=1)
        extra.update(u_rmse=float(np.sqrt(np.mean(difference[:, 0] ** 2))), v_rmse=float(np.sqrt(np.mean(difference[:, 1] ** 2))))
    else:
        errors = difference
        if kind == "PROFILE_BINS":
            if origins and origins[0]["value_representation"] == "CIRCULAR_DEGREES":
                expected, predicted = actual.reshape(len(actual), -1, 2), prediction.reshape(len(prediction), -1, 2)
                if (np.linalg.norm(predicted, axis=2) < 1e-12).any():
                    raise ComparisonBlocked("PROFILE_DIRECTION_PREDICTION_UNDEFINED")
                errors = (np.degrees(np.arctan2(predicted[:,:,1], predicted[:,:,0])) - np.degrees(np.arctan2(expected[:,:,1], expected[:,:,0])) + 180) % 360 - 180
                difference = errors
                extra["metric_unit"] = "degree_wrapped_per_explicit_bin"
            extra["per_bin_mae"] = np.mean(np.abs(difference), axis=0).tolist()
            extra["aggregation"] = "EXPLICIT_FIXED_BINS_EQUAL_WEIGHT_NO_INTERPOLATION"
    return {"mae": float(np.mean(np.abs(errors))), "rmse": float(np.sqrt(np.mean(errors ** 2))),
            "bias": float(np.mean(errors)), "sample_count": len(actual), "coverage": 1.0, **extra}


def binary_metrics(actual, prediction, scores):
    actual, prediction = np.asarray(actual, int), np.asarray(prediction, int)
    if set(actual) != {0, 1}:
        raise ComparisonBlocked("BINARY_BOTH_NORMAL_AND_BAD_HOLDOUT_REQUIRED")
    tn, fp, fn, tp = confusion_matrix(actual, prediction, labels=[0, 1]).ravel()
    return {"precision": float(precision_score(actual, prediction, zero_division=0)), "recall": float(recall_score(actual, prediction, zero_division=0)),
        "f1": float(f1_score(actual, prediction, zero_division=0)), "auroc": float(roc_auc_score(actual, scores)),
        "false_positive_rate": float(fp / (fp + tn)), "false_negative_rate": float(fn / (fn + tp)),
        "sample_count": len(actual), "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp), "point_adjustment": False}


def full_qc_metrics(rows, predicted, scores):
    """Compare rule execution with every human QC label, keeping exclusions explicit.

    A BAD-only AI evidence score cannot assign SUSPECT/MISSING human labels or
    overwrite source flags. Its two-label quality is reported on a stated subset.
    """
    labels = ("NORMAL", "SUSPECT", "BAD", "MISSING")
    flags = labels + ("NOT_EVALUATED",)
    confusion = {label: {flag: 0 for flag in flags} for label in labels}
    for row in rows:
        confusion[row["human_quality_label"]][row["rule_qc"]["flag"]] += 1
    evaluated = [(r["human_quality_label"], r["rule_qc"]["flag"]) for r in rows if r["rule_qc"]["flag"] != "NOT_EVALUATED"]
    non_good = [(a, p) for a, p in evaluated if a != "NORMAL"]
    return {"human_label_rule_flag_confusion": confusion,
        "guide_rule_coverage": len(evaluated) / len(rows),
        "human_qc_agreement": sum(a == p for a, p in evaluated) / len(evaluated) if evaluated else None,
        "false_good_rate": sum(p == "NORMAL" for a, p in non_good) / len(non_good) if non_good else None,
        "false_good_denominator": "HUMAN_NON_NORMAL_AND_RULE_EVALUATED",
        "not_evaluated_count": len(rows) - len(evaluated),
        "human_label_counts": {label: sum(r["human_quality_label"] == label for r in rows) for label in labels},
        "binary_score_evaluation_count": sum(r["human_quality_label"] in {"NORMAL", "BAD"} for r in rows),
        "ai_role": "BAD_EVIDENCE_SCORE_ONLY_REVIEWER_DECIDES_FULL_QC", "source_qc_mutation": False}


def compare_typed(prepared):
    rows, manifest = prepared["rows"], prepared["manifest"]
    task, kind = manifest["task"], manifest["quantity_kind"]
    x = {s: np.array([r["x"] + validate_payload(r["origin_payload"]).tolist() for r in rows[s]]) for s in rows}
    if len({len(r) for values in x.values() for r in values}) != 1:
        raise ComparisonBlocked("TYPED_FEATURE_FIXED_SHAPE_REQUIRED")
    if kind == "PROFILE_BINS" and len({signature(r["origin_payload"]) for split in rows.values() for r in split}) != 1:
        raise ComparisonBlocked("PROFILE_SHARED_APPROVED_BIN_LAYOUT_REQUIRED")
    started = time.perf_counter()
    if task != "FORECASTING":
        y = {s: np.array([r["y"] for r in rows[s]], int) for s in rows}
        normal = x["TRAIN"][y["TRAIN"] == 0]
        masks = {s: y[s] >= 0 for s in rows}
        if len(normal) < 2 or set(y["VALIDATION"][masks["VALIDATION"]]) != {0, 1} or set(y["TEST"][masks["TEST"]]) != {0, 1}:
            raise ComparisonBlocked("NORMAL_TRAIN_AND_LABELED_VALIDATION_TEST_REQUIRED")
        median = np.median(normal, axis=0)
        scale = np.median(np.abs(normal - median), axis=0)
        scale = np.where(scale > 1e-12, scale, 1.0)
        score = {s: np.max(np.abs((x[s] - median) / scale), axis=1) for s in rows}
        threshold_candidates = sorted(set(float(v) for v in np.quantile(score["TRAIN"][y["TRAIN"] == 0], manifest["normal_quantiles"])))
        tuning = [{"threshold": t, "validation": binary_metrics(y["VALIDATION"][masks["VALIDATION"]], (score["VALIDATION"] > t)[masks["VALIDATION"]], score["VALIDATION"][masks["VALIDATION"]])} for t in threshold_candidates]
        best = max(tuning, key=lambda c: (c["validation"]["f1"], -c["validation"]["false_positive_rate"], c["threshold"]))
        threshold = best["threshold"]
        pred = (score["TEST"] > threshold).astype(int)
        artifact = {"schema_version": "robust-score-json-1", "features": manifest["feature_ids"], "representation": kind,
                    "median": median.tolist(), "scale": scale.tolist(), "threshold": threshold, "evidence_only": task == "QUALITY_REVIEW"}
        mask = masks["TEST"]
        metrics = {"candidate": binary_metrics(y["TEST"][mask], pred[mask], score["TEST"][mask]),
                   "all_normal_baseline": binary_metrics(y["TEST"][mask], np.zeros(sum(mask), int), np.zeros(sum(mask)))}
        paired = [{"origin_id": r["origin_id"], "actual": int(t), "score": float(s), "prediction": int(p),
                   "event_id": r["event_id"], "human_quality_label": r["human_quality_label"],
                   "rule_qc": r.get("rule_qc"), "binary_metric_eligible": t >= 0} for r, t, s, p in zip(rows["TEST"], y["TEST"], score["TEST"], pred)]
        if task == "QUALITY_REVIEW":
            metrics["full_qc_review"] = full_qc_metrics(rows["TEST"], pred, score["TEST"])
        events = sorted({r["event_id"] for r in rows["TEST"] if r["y"] == 1})
        delays = []
        from app.ml.comparison_runner import clock
        for event in events:
            indexes = [i for i, r in enumerate(rows["TEST"]) if r["event_id"] == event and r["y"] == 1]
            hits = [i for i in indexes if pred[i]]
            if hits:
                delays.append((min(clock(rows["TEST"][i]["forecast_origin"], True) for i in hits) - min(clock(rows["TEST"][i]["forecast_origin"], True) for i in indexes)).total_seconds())
        metrics["event_detection"] = {"observed_bad_event_count": len(events), "detected_event_count": len(delays), "delay_seconds_from_first_observed_bad": delays, "unobserved_event_start_not_inferred": True}
    else:
        y, baseline = {}, {}
        for split in rows:
            encoded = [encode_target(r["origin_payload"], r["target_payload"]) for r in rows[split]]
            y[split], baseline[split] = np.array([e[0] for e in encoded]), np.array([e[1] for e in encoded])
        tuning = []
        for alpha in manifest["ridge_alphas"]:
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(x["TRAIN"], y["TRAIN"])
            metrics = typed_metrics(y["VALIDATION"], np.asarray(model.predict(x["VALIDATION"])).reshape(len(x["VALIDATION"]), -1), kind, [r["origin_payload"] for r in rows["VALIDATION"]])
            tuning.append({"alpha": alpha, "validation": metrics})
        best = min(tuning, key=lambda c: (c["validation"]["mae"], c["alpha"]))
        model = make_pipeline(StandardScaler(), Ridge(alpha=best["alpha"]))
        fit_splits = ("TRAIN", "VALIDATION") if manifest["refit_train_validation"] else ("TRAIN",)
        model.fit(np.concatenate([x[s] for s in fit_splits]), np.concatenate([y[s] for s in fit_splits]))
        pred = np.asarray(model.predict(x["TEST"])).reshape(len(x["TEST"]), -1)
        scaler, ridge = model.named_steps["standardscaler"], model.named_steps["ridge"]
        artifact = {"schema_version": "typed-ridge-json-1", "features": manifest["feature_ids"], "representation": kind,
                    "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(), "coef": np.asarray(ridge.coef_).reshape(y["TRAIN"].shape[1], -1).tolist(), "intercept": np.asarray(ridge.intercept_).reshape(-1).tolist()}
        metrics = {"ridge": typed_metrics(y["TEST"], pred, kind, [r["origin_payload"] for r in rows["TEST"]]),
                   "persistence": typed_metrics(y["TEST"], baseline["TEST"], kind, [r["origin_payload"] for r in rows["TEST"]])}
        paired = [{"origin_id": r["origin_id"], "target_id": r["target_id"], "actual": a.tolist(), "prediction": p.tolist(), "baseline": b.tolist(), "origin_payload": r["origin_payload"]}
                  for r, a, p, b in zip(rows["TEST"], y["TEST"], pred, baseline["TEST"])]
    artifact["allowed_typed_signatures"] = sorted({signature(r["origin_payload"]) for split in rows.values() for r in split})
    return {"status": "COMPARISON_COMPLETE_CANDIDATE_ONLY", "task": task, "quantity_kind": kind,
        "adapter_scope": "TYPED_RIDGE_PERSISTENCE" if task == "FORECASTING" else "TYPED_ROBUST_SCORE_ALL_NORMAL_GUIDE_EVIDENCE",
        "evidence_mode": prepared["evidence_mode"], "manifest_sha256": prepared["manifest_sha256"], "snapshot_hashes": prepared["snapshot_hashes"],
        "origin_membership_sha256": prepared["origin_membership_sha256"], "coverage": prepared["coverage"], "validation_tuning": tuning,
        "test_metrics": metrics, "artifact": artifact, "paired_test_predictions": paired, "training_seconds": time.perf_counter() - started,
        "registered_models": 0, "deployed_models": 0, "selected_operating_model": None, "acceptance_criteria_status": "NOT_DEFINED",
        "cost": "NOT_MEASURED", "service_latency": "NOT_MEASURED", "operating_registration_gate": "REQUIRES_INDEPENDENT_REVIEW_AND_APPROVAL"}
