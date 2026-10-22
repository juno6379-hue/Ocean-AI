"""Pure, label-aware scoring for local QC simulations.

Labels are used only here, after replay.  A GAP is coverage loss, never a
normal decision.  Event boundaries come from the original minute timeline,
before warmup, common-window, or GAP exclusions are applied.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
import math
from numbers import Integral, Real


ANOMALY_FLAGS = frozenset({4, 5, 6, 7, 8})
NON_LSTM_FLAGS = frozenset({5, 6, 7, 8})
VALID_FLAGS = ANOMALY_FLAGS | {1, 9}


def _timestamp(value) -> datetime:
    if value is None:
        raise ValueError("An evaluation timestamp is missing.")
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else parsed
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid evaluation timestamp: {value!r}") from exc


def _timeline(values) -> list[datetime]:
    times = [_timestamp(value) for value in values]
    try:
        if any(right <= left for left, right in zip(times, times[1:])):
            raise ValueError("Evaluation timestamps must be unique and increasing.")
    except TypeError as exc:
        raise ValueError("Evaluation timestamps mix aware and naive times.") from exc
    return times


def _number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite numeric scalar.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite numeric scalar.")
    return result


def _boolean(value, name: str) -> bool:
    # Equality also accepts scalar Boolean values supplied by array callers.
    if isinstance(value, (str, bytes)) or value is None or value not in (True, False):
        raise ValueError(f"{name} must be a Boolean scalar.")
    return bool(value)


def _labels_for_times(labels, times: Sequence[datetime]) -> list[str]:
    if isinstance(labels, Mapping):
        by_time = {}
        for timestamp, value in labels.items():
            key = _timestamp(timestamp)
            label = str(value).strip().upper() if value is not None else ""
            if key in by_time and by_time[key] != label:
                raise ValueError(f"Conflicting labels for {key.isoformat()}.")
            by_time[key] = label
        return [by_time.get(timestamp, "") for timestamp in times]
    values = list(labels)
    if len(values) != len(times):
        raise ValueError("Label and timestamp lengths differ.")
    return [str(value).strip().upper() if value is not None else "" for value in values]


def _classification(labels: Sequence[str], decisions: Sequence[bool], eligible) -> dict:
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for label, detected, included in zip(labels, decisions, eligible):
        if not included or label not in {"G", "B"}:
            continue
        key = ("tp" if detected else "fn") if label == "B" else ("fp" if detected else "tn")
        counts[key] += 1
    tp, fp, tn, fn = (counts[name] for name in ("tp", "fp", "tn", "fn"))
    positives = tp + fn
    # Without actual B, anomaly precision/F1 do not establish detection skill.
    precision = tp / (tp + fp) if positives and tp + fp else (0.0 if positives else None)
    recall = tp / positives if positives else None
    f1 = 2.0 * tp / (2 * tp + fp + fn) if positives else None
    total = tp + fp + tn + fn
    return {
        **counts, "sample_count": total, "labeled_g_count": tn + fp,
        "labeled_b_count": positives, "precision": precision, "recall": recall,
        "f1": f1, "f1_score": f1,
        "precision_100": precision * 100 if precision is not None else None,
        "recall_100": recall * 100 if recall is not None else None,
        "f1_100": f1 * 100 if f1 is not None else None,
        "f1_score_100": f1 * 100 if f1 is not None else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "accuracy": (tp + tn) / total if total else None,
        "anomaly_metrics_verified": bool(positives),
    }


def _quantile(ordered: Sequence[float], probability: float) -> float | None:
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return (1 - weight) * ordered[lower] + weight * ordered[upper]


def _error_summary(errors: Sequence[float]) -> dict:
    if not errors:
        return {"sample_count": 0, "mae": None, "rmse": None, "mean": None,
                "std_population": None, "min": None, "max": None,
                "quantiles": {key: None for key in ("p01", "p05", "p25", "p50", "p75", "p95", "p99")},
                "absolute_quantiles": {key: None for key in ("p50", "p90", "p95", "p99")}}
    count = len(errors)
    scale = max(abs(error) for error in errors)
    mean = math.fsum(error / count for error in errors)
    mae = math.fsum(abs(error) / count for error in errors)
    rmse = scale * math.sqrt(math.fsum((error / scale) ** 2 for error in errors) / count) if scale else 0.0
    # Scale before centering to avoid overflow with otherwise finite inputs.
    normalized_mean = mean / scale if scale else 0.0
    std = scale * math.sqrt(math.fsum((error / scale - normalized_mean) ** 2 for error in errors) / count) if scale else 0.0
    ordered, absolute = sorted(errors), sorted(abs(error) for error in errors)
    result = {
        "sample_count": count, "mae": mae, "rmse": rmse, "mean": mean,
        "std_population": std, "min": ordered[0], "max": ordered[-1],
        "quantiles": {f"p{int(p * 100):02d}": _quantile(ordered, p)
                      for p in (0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99)},
        "absolute_quantiles": {f"p{int(p * 100):02d}": _quantile(absolute, p)
                               for p in (0.50, 0.90, 0.95, 0.99)},
    }
    if not all(math.isfinite(result[key]) for key in ("mae", "rmse", "mean", "std_population")):
        raise ValueError("Error statistics exceed the finite numeric range.")
    return result


def _events(times, labels, scope, eligible, decisions, notification_times=None,
            online_decisions=None) -> dict:
    raw_events = []
    for index, label in enumerate(labels):
        if label != "B":
            continue
        if (raw_events and index == raw_events[-1][-1] + 1
                and times[index] - times[index - 1] == timedelta(minutes=1)):
            raw_events[-1].append(index)
        else:
            raw_events.append([index])
    details, latencies, target_latencies = [], [], []
    for event in raw_events:
        scoped = [index for index in event if scope[index]]
        if not scoped:
            continue
        covered = [index for index in scoped if eligible[index]]
        detected = [index for index in covered if decisions[index]]
        start, end = times[event[0]], times[event[-1]]
        first_target = times[detected[0]] if detected else None
        notifications = [notification_times[index] if notification_times is not None else times[index]
                         for index in detected]
        notifications = [stamp for stamp in notifications if stamp is not None]
        first_notification = min(notifications) if notifications else None
        online_alerts = [times[index] for index in scoped
                         if online_decisions is not None and online_decisions[index]]
        target_latency = (first_target - start).total_seconds() / 60 if first_target is not None else None
        latency = (first_notification - start).total_seconds() / 60 if first_notification is not None else None
        if latency is not None:
            latencies.append(latency)
        if target_latency is not None:
            target_latencies.append(target_latency)
        details.append({
            "start_time": start.isoformat(), "end_time": end.isoformat(),
            "raw_b_count": len(event), "scoped_b_count": len(scoped),
            "eligible_b_count": len(covered), "excluded_b_count": len(scoped) - len(covered),
            "detected": bool(detected), "first_flagged_target_time": first_target.isoformat() if first_target else None,
            "first_notification_time": first_notification.isoformat() if first_notification else None,
            "first_online_alert_time": min(online_alerts).isoformat() if online_alerts else None,
            "detection_latency_minutes": latency, "flagged_target_latency_minutes": target_latency,
        })
    total = len(details)
    detected_count = sum(event["detected"] for event in details)
    covered_count = sum(event["eligible_b_count"] > 0 for event in details)
    fully_covered = sum(event["eligible_b_count"] == event["scoped_b_count"] for event in details)
    return {
        "boundary_definition": "CONSECUTIVE_RAW_B_ROWS_EXACTLY_ONE_MINUTE_APART",
        "denominator_definition": "ALL_RAW_B_EVENTS_WITH_AT_LEAST_ONE_SCOPED_B_ROW",
        "latency_definition": "EARLIEST_RECORDED_NOTIFICATION_MINUS_RAW_EVENT_START",
        "raw_event_total": len(raw_events), "excluded_event_count": len(raw_events) - total,
        "event_total": total, "event_detected": detected_count, "event_missed": total - detected_count,
        "event_recall": detected_count / total if total else None,
        "event_recall_100": 100 * detected_count / total if total else None,
        "eligible_covered_event_total": covered_count, "fully_covered_event_total": fully_covered,
        "partially_covered_event_total": covered_count - fully_covered,
        "uncovered_event_total": total - covered_count,
        "eligible_covered_event_recall": detected_count / covered_count if covered_count else None,
        "eligible_covered_event_recall_100": 100 * detected_count / covered_count if covered_count else None,
        "mean_detection_latency_minutes": math.fsum(latencies) / len(latencies) if latencies else None,
        "mean_flagged_target_latency_minutes": math.fsum(target_latencies) / len(target_latencies) if target_latencies else None,
        "detection_latency_sample_count": len(latencies),
        "notification_timing_unavailable_event_count": detected_count - len(latencies),
        "details": details,
    }


def _r_squared(targets: Sequence[float], errors: Sequence[float]) -> dict:
    """Keep undefined R² explicit instead of manufacturing a finite score."""
    if len(targets) < 2:
        return {"r2": None, "r2_status": "UNDEFINED_INSUFFICIENT_SAMPLES"}
    if all(value == targets[0] for value in targets):
        return {"r2": None, "r2_status": "UNDEFINED_CONSTANT_TARGET"}
    scale = max(max(abs(value) for value in targets), max(abs(value) for value in errors))
    normalized_mean = math.fsum(value / scale / len(targets) for value in targets)
    denominator = math.fsum((value / scale - normalized_mean) ** 2 for value in targets)
    if denominator == 0.:
        return {"r2": None, "r2_status": "UNDEFINED_NUMERIC_RANGE"}
    value = 1. - math.fsum((error / scale) ** 2 for error in errors) / denominator
    return {"r2": value if math.isfinite(value) else None,
            "r2_status": "DEFINED" if math.isfinite(value) else "UNDEFINED_NUMERIC_RANGE"}


def evaluate_tier1(timestamps, actual_obs, prd_values, predictions_by_model,
                   thresholds_by_model, labels, *, common_mask=None) -> dict:
    """Score forecasts on an explicit, model-independent normal-input mask.

    The caller constructs the mask from four preceding raw normal G inputs
    and the finite target requirement.  Current targets may be G or B.  This
    function does not infer input-window eligibility from target labels.  If
    no mask is supplied, the caller must already have selected eligible rows.
    """
    times = _timeline(timestamps)
    count = len(times)
    actual, prd = list(actual_obs), list(prd_values)
    if len(actual) != count or len(prd) != count:
        raise ValueError("Tier1 timestamp, OBS, and PRD lengths differ.")
    if not isinstance(predictions_by_model, Mapping) or not predictions_by_model:
        raise ValueError("Tier1 requires model predictions.")
    if set(predictions_by_model) != set(thresholds_by_model):
        raise ValueError("Tier1 prediction and threshold model keys differ.")
    mask = [True] * count if common_mask is None else list(common_mask)
    if len(mask) != count:
        raise ValueError("Tier1 common mask length differs from the timeline.")
    scope = [_boolean(value, "common_mask") for value in mask]
    label_values = _labels_for_times(labels, times)
    eligible = [included and label in {"G", "B"} for included, label in zip(scope, label_values)]
    selected = [index for index, included in enumerate(eligible) if included]
    targets = {index: _number(actual[index], f"OBS[{index}]") for index in selected}
    predictions = {index: _number(prd[index], f"PRD[{index}]") for index in selected}
    prd_errors = [_number(targets[index] - predictions[index], "OBS-PRD") for index in selected]
    models = {}
    for model_name, values in predictions_by_model.items():
        predicted = list(values)
        if len(predicted) != count:
            raise ValueError(f"Tier1 {model_name} prediction length differs.")
        raw_threshold = thresholds_by_model[model_name]
        if isinstance(raw_threshold, Real) and not isinstance(raw_threshold, bool):
            threshold = _number(raw_threshold, f"{model_name} threshold")
            if threshold < 0:
                raise ValueError(f"Tier1 {model_name} threshold is negative.")
            thresholds = [threshold] * count
        else:
            try:
                thresholds = list(raw_threshold)
            except TypeError as exc:
                raise ValueError(f"Tier1 {model_name} threshold must be a scalar or aligned sequence.") from exc
            if len(thresholds) != count:
                raise ValueError(f"Tier1 {model_name} threshold length differs.")
            threshold = None
        errors, normal_errors, normal_targets = [], [], []
        decisions = [False] * count
        for index in selected:
            prediction = _number(predicted[index], f"{model_name} yhat[{index}]")
            limit = _number(thresholds[index], f"{model_name} threshold[{index}]")
            if limit < 0:
                raise ValueError(f"Tier1 {model_name} threshold is negative.")
            error = _number(targets[index] - prediction, "OBS-yhat")
            decisions[index] = abs(error) > limit
            errors.append(error)
            if label_values[index] == "G":
                normal_errors.append(error)
                normal_targets.append(targets[index])
        summary = _error_summary(errors)
        normal = {**_error_summary(normal_errors), **_r_squared(normal_targets, normal_errors),
                  "scope": "COMMON_NORMAL_INPUT_WINDOWS_G_TARGETS", "target_label": "G"}
        models[str(model_name)] = {
            "sample_count": len(selected), "threshold": threshold,
            "threshold_comparison": "abs(OBS-yhat) > threshold",
            "mae": summary["mae"], "rmse": summary["rmse"],
            **_r_squared([targets[index] for index in selected], errors),
            "normal_g": normal, "normal_prediction": dict(normal),
            "error_distributions": {"obs_minus_yhat": summary, "obs_minus_prd": _error_summary(prd_errors)},
            "classification": _classification(label_values, decisions, eligible),
            "events": _events(times, label_values, scope, eligible, decisions),
        }
    return {
        "scope": "COMMON_NORMAL_INPUT_WINDOWS", "raw_count": count,
        "primary_prediction_scope": "COMMON_NORMAL_INPUT_WINDOWS_G_TARGETS",
        "anomaly_scope": "COMMON_NORMAL_INPUT_WINDOWS_G_AND_B_TARGETS",
        "sample_count": len(selected), "common_mask_count": sum(scope),
        "common_mask_excluded_count": count - sum(scope),
        "unlabeled_excluded_count": sum(included and label not in {"G", "B"}
                                        for included, label in zip(scope, label_values)),
        "input_window_eligibility": "CALLER_SUPPLIED_COMMON_MASK" if common_mask is not None else "CALLER_PRESELECTED_ROWS",
        "models": models,
    }


def _flag(value, name: str, *, warmup: bool) -> int | None:
    if value is None and warmup:
        return None
    # Original QC flags are canonical single-character strings.  Normalize
    # only that declared representation at the scoring boundary.
    if isinstance(value, str):
        if value in {"1", "4", "5", "6", "7", "8", "9"}:
            return int(value)
        raise ValueError(f"{name} must be one of 1, 4, 5, 6, 7, 8, 9.")
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) not in VALID_FLAGS:
        raise ValueError(f"{name} must be one of 1, 4, 5, 6, 7, 8, 9.")
    return int(value)


def _distribution(values) -> dict[str, int]:
    counts = Counter("UNSPECIFIED" if value is None else str(value) for value in values)
    return dict(sorted(counts.items()))


def _retroactive_summary(rows, times, online_flags) -> tuple[dict, list]:
    first_notifications = [timestamp if flag in ANOMALY_FLAGS else None
                           for timestamp, flag in zip(times, online_flags)]
    indices = {timestamp: index for index, timestamp in enumerate(times)}
    pairs, sources = Counter(), Counter()
    retro_count = current_count = outside_count = 0
    for row, current_time in zip(rows, times):
        changes = row.get("retroactive_changes")
        if not isinstance(changes, list):
            raise ValueError("Each replay row requires a retroactive_changes list.")
        for change in changes:
            if not isinstance(change, Mapping):
                raise ValueError("A retroactive change must be a mapping.")
            target = _timestamp(change.get("timestamp"))
            notification = _timestamp(change.get("notification_time", current_time))
            if notification != current_time or target > current_time:
                raise ValueError("A buffer change must be recorded at its notification row and cannot target the future.")
            old_flag = _flag(change.get("old_flag"), "old_flag", warmup=False)
            new_flag = _flag(change.get("new_flag"), "new_flag", warmup=False)
            is_retroactive = target < current_time
            if "is_retroactive" in change and _boolean(change["is_retroactive"], "is_retroactive") != is_retroactive:
                raise ValueError("is_retroactive disagrees with the target/notification times.")
            if is_retroactive:
                retro_count += 1
                pairs[f"{old_flag}->{new_flag}"] += 1
                sources[str(change.get("source", "UNSPECIFIED"))] += 1
            else:
                current_count += 1
            if target not in indices:
                outside_count += 1
                continue
            index = indices[target]
            if new_flag in ANOMALY_FLAGS:
                previous = first_notifications[index]
                first_notifications[index] = min(previous, notification) if previous is not None else notification
    return {
        "retroactive_mutation_count": retro_count, "change_pairs": dict(sorted(pairs.items())),
        "source_distribution": dict(sorted(sources.items())),
        "current_row_override_count": current_count, "outside_replay_target_count": outside_count,
        "count_definition": "RECORDED_BUFFER_CHANGES_WITH_TARGET_TIME_BEFORE_NOTIFICATION_TIME",
    }, first_notifications


def _replay_view(rows, times, labels, warmup, flags, sources, raw_lstm,
                 notification_times, online_flags) -> dict:
    scope = [not value for value in warmup]
    eligible = [included and flag != 9 and label in {"G", "B"}
                for included, flag, label in zip(scope, flags, labels)]
    decisions = [flag in ANOMALY_FLAGS for flag in flags]
    raw_counts = Counter(labels)
    scoped_counts = Counter(label for label, included in zip(labels, scope) if included)
    gap_counts = Counter(label for label, flag, included in zip(labels, flags, scope) if included and flag == 9)
    counts: dict[str, int | float | None] = {
        "raw_count": len(rows), "warmup_excluded_count": sum(warmup),
        "post_warmup_count": sum(scope), "gap_count": sum(gap_counts.values()),
        "gap_labeled_g_count": gap_counts["G"], "gap_labeled_b_count": gap_counts["B"],
        "gap_unlabeled_count": sum(value for label, value in gap_counts.items() if label not in {"G", "B"}),
        "evaluated_count": sum(eligible),
        "labeled_g_count": sum(included and label == "G" for included, label in zip(eligible, labels)),
        "labeled_b_count": sum(included and label == "B" for included, label in zip(eligible, labels)),
        "unlabeled_excluded_count": sum(included and flag != 9 and label not in {"G", "B"}
                                         for included, flag, label in zip(scope, flags, labels)),
        "raw_labeled_g_count": raw_counts["G"], "raw_labeled_b_count": raw_counts["B"],
        "raw_unlabeled_count": sum(value for label, value in raw_counts.items() if label not in {"G", "B"}),
        "post_warmup_labeled_g_count": scoped_counts["G"], "post_warmup_labeled_b_count": scoped_counts["B"],
        "post_warmup_unlabeled_count": sum(value for label, value in scoped_counts.items() if label not in {"G", "B"}),
    }
    post_warmup_count = sum(scope)
    counts["coverage_fraction"] = (post_warmup_count - sum(gap_counts.values())) / post_warmup_count if post_warmup_count else None
    return {
        "counts": counts, "classification": _classification(labels, decisions, eligible),
        "coverage": {
            "raw_minutes": counts["raw_count"],
            "warmup_minutes": counts["warmup_excluded_count"],
            "evaluated_minutes": counts["evaluated_count"],
            "gap_minutes": counts["gap_count"],
            "labeled_g_minutes": counts["labeled_g_count"],
            "labeled_b_minutes": counts["labeled_b_count"],
            "unlabeled_or_excluded_minutes": counts["unlabeled_excluded_count"],
            "definitions": {
                "unit": "Minute counts are replay row counts; absent timestamps are not inferred.",
                "raw_minutes": "All replay rows, including warmup.",
                "warmup_minutes": "Rows marked warmup, excluded before GAP or label scoring.",
                "evaluated_minutes": "Non-warmup, non-GAP rows labeled G or B.",
                "gap_minutes": "Non-warmup rows flagged 9, including every label.",
                "labeled_g_minutes": "Evaluated rows labeled G.",
                "labeled_b_minutes": "Evaluated rows labeled B.",
                "unlabeled_or_excluded_minutes": "Non-warmup, non-GAP rows without a G or B label; excludes warmup and GAP counts.",
                "partition": "raw_minutes = warmup_minutes + gap_minutes + evaluated_minutes + unlabeled_or_excluded_minutes",
            },
        },
        "events": _events(times, labels, scope, eligible, decisions, notification_times,
                          [flag in ANOMALY_FLAGS for flag in online_flags]),
        "distribution_scope": "POST_WARMUP_ALL_LABELS_INCLUDING_GAP",
        "flag_distribution": _distribution(flag for flag, included in zip(flags, scope) if included),
        "source_distribution": _distribution(source for source, included in zip(sources, scope) if included),
        "raw_flag_distribution": _distribution(flags), "raw_source_distribution": _distribution(sources),
        "non_lstm_caught_b_count": sum(included and label == "B" and not raw and flag in NON_LSTM_FLAGS
                                       for included, label, raw, flag in zip(eligible, labels, raw_lstm, flags)),
    }


def evaluate_replay(replay_result, labels, *, source_metadata=None) -> dict:
    """Evaluate recorded online and consolidated decisions without running QC."""
    if (not isinstance(replay_result, Mapping)
            or not isinstance(replay_result.get("models"), Mapping)
            or not replay_result["models"]):
        raise ValueError("Replay result requires a nonempty models mapping.")
    models = {}
    common_times = None
    label_values: list[str] = []
    for name, model in replay_result["models"].items():
        if not isinstance(model, Mapping) or not isinstance(model.get("rows"), list):
            raise ValueError(f"Replay model {name} requires a rows list.")
        rows = model["rows"]
        times = _timeline(row.get("timestamp") for row in rows)
        if common_times is None:
            common_times = times
            label_values = _labels_for_times(labels, times)
        elif times != common_times:
            raise ValueError("Replay models do not share the same physical timeline.")
        warmup = [_boolean(row.get("warmup"), "warmup") for row in rows]
        online_flags = [_flag(row.get("online_flag"), "online_flag", warmup=value)
                        for row, value in zip(rows, warmup)]
        consolidated_flags = [_flag(row.get("consolidated_flag"), "consolidated_flag", warmup=value)
                              for row, value in zip(rows, warmup)]
        raw_lstm = [_boolean(row.get("raw_lstm_anomaly"), "raw_lstm_anomaly") for row in rows]
        reversed_flags = [_boolean(row.get("trend_reversed"), "trend_reversed") for row in rows]
        interpolate_counts = []
        for row in rows:
            value = row.get("interpolate_count")
            if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
                raise ValueError("interpolate_count must be a nonnegative integer.")
            interpolate_counts.append(int(value))
        retroactive, notifications = _retroactive_summary(rows, times, online_flags)
        trend_labels = Counter(label for label, reversed_, excluded in zip(label_values, reversed_flags, warmup)
                               if reversed_ and not excluded)
        models[str(name)] = {
            "metadata": model.get("metadata", {}),
            "online": _replay_view(rows, times, label_values, warmup, online_flags,
                                   [row.get("online_source") for row in rows], raw_lstm,
                                   [timestamp if flag in ANOMALY_FLAGS else None for timestamp, flag in zip(times, online_flags)], online_flags),
            "consolidated": _replay_view(rows, times, label_values, warmup, consolidated_flags,
                                         [row.get("consolidated_source") for row in rows], raw_lstm,
                                         notifications, online_flags),
            "trend_reversal": {
                "scope": "POST_WARMUP_ALL_ROWS", "count": sum(trend_labels.values()),
                "labeled_g_count": trend_labels["G"], "labeled_b_count": trend_labels["B"],
                "unlabeled_count": sum(value for label, value in trend_labels.items() if label not in {"G", "B"}),
            },
            "trend_reversed_count": sum(trend_labels.values()),
            "trend_reversed_g_false_alarm_defense_count": trend_labels["G"],
            "trend_reversed_b_missed_count": trend_labels["B"],
            "trend_reversed_alias_definition": "Post-warmup LSTM anomaly decisions reversed to normal, separated by actual G/B labels; later QC decisions are scored independently in each view.",
            "interpolation": {
                "scope": "POST_WARMUP_ALL_ROWS",
                "input_window_with_interpolation_count": sum(count > 0 and not excluded for count, excluded in zip(interpolate_counts, warmup)),
                "interpolated_window_element_count": sum(count for count, excluded in zip(interpolate_counts, warmup) if not excluded),
                "count_definition": "RECORDED_ANALYSIS_LOG_INTERPOLATE_COUNT_PER_WINDOW",
            },
            "retroactive_mutations": retroactive,
        }
    return {
        "scope": "ACTUAL_QC_REPLAY", "station": replay_result.get("station"),
        "sensor": replay_result.get("sensor"), "start_time": replay_result.get("start_time"),
        "end_time": replay_result.get("end_time"), "metadata": replay_result.get("metadata", {}),
        "source_metadata": source_metadata if source_metadata is not None else {},
        "anomaly_flags": sorted(ANOMALY_FLAGS), "gap_flag": 9,
        "labels_used_only_for_scoring": True, "models": models,
    }
