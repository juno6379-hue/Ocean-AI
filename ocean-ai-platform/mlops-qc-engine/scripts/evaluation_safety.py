"""Promotion checks and event metrics based on unweighted evaluation observations."""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from fractions import Fraction
from numbers import Integral, Real


def _count(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} 원시 건수가 없거나 정수가 아닙니다.")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} 원시 건수는 0 이상의 유한한 정수여야 합니다.")
    count = int(value) if isinstance(value, Integral) else int(float(value))
    if count != value:
        raise ValueError(f"{label} 원시 건수는 0 이상의 유한한 정수여야 합니다.")
    return count


def _verified_metrics(metrics: dict | None, label: str) -> tuple[dict[str, int], float]:
    if not isinstance(metrics, dict) or not isinstance(metrics.get("classification"), dict):
        raise ValueError(f"{label}의 원시 분류 건수가 없습니다.")
    counts = {key: _count(metrics["classification"].get(key), f"{label} {key.upper()}")
              for key in ("tp", "fp", "tn", "fn")}
    mae = metrics.get("mae")
    if isinstance(mae, bool) or not isinstance(mae, Real) or not math.isfinite(mae) or mae < 0:
        raise ValueError(f"{label} MAE가 없거나 0 이상의 유한한 수가 아닙니다.")
    return counts, float(mae)


def honest_promotion_verdict(candidate: dict | None, champion: dict | None,
                             natural_b_windows: int | None) -> dict:
    """Recompute the recommendation; persisted scores cannot bypass FP/FN checks."""
    guardrails = {"passed": False, "counts_verified": False, "fp_not_worse": None,
                  "fn_not_worse": None, "mae_not_worse": None,
                  "anomaly_recall_verified": False, "scope": "unverified", "reasons": []}
    metric = "f1_score_100" if natural_b_windows else "normal_f1_score_100"
    result = {"promotion_recommended": False, "promotion_allowed": False,
              "recommendation_metric": metric, "promotion_guardrails": guardrails}
    try:
        natural_b = _count(natural_b_windows, "실제 B")
        c, c_mae = _verified_metrics(candidate, "후보")
        h, h_mae = _verified_metrics(champion, "기존 모델")
        if c["tp"] + c["fn"] != natural_b or h["tp"] + h["fn"] != natural_b:
            raise ValueError("후보와 기존 모델의 TP+FN이 실제 B 건수와 일치하지 않습니다.")
        normal_count = c["tn"] + c["fp"]
        if normal_count != h["tn"] + h["fp"] or normal_count <= 0:
            raise ValueError("후보와 기존 모델의 정상 관측값 건수가 다르거나 정상 자료가 없습니다.")
    except ValueError as exc:
        guardrails["reasons"] = [str(exc)]
        result["recommendation_reason"] = f"승격 보류: {exc} 평가 자료를 다시 확인해 주세요."
        return result

    fp_ok, fn_ok, mae_ok = c["fp"] <= h["fp"], c["fn"] <= h["fn"], c_mae <= h_mae
    guardrails.update(counts_verified=True, fp_not_worse=fp_ok, fn_not_worse=fn_ok,
                      mae_not_worse=mae_ok, anomaly_recall_verified=natural_b > 0,
                      scope="normal_and_anomaly" if natural_b else "normal_only")
    reasons = []
    if not fp_ok:
        reasons.append(f"후보 FP {c['fp']}건이 기존 모델 {h['fp']}건보다 많습니다.")
    if natural_b and not fn_ok:
        reasons.append(f"후보 FN {c['fn']}건이 기존 모델 {h['fn']}건보다 많습니다.")
    if not natural_b and not mae_ok:
        reasons.append(f"후보 MAE {c_mae:g}가 기존 모델 {h_mae:g}보다 큽니다.")
    guardrails["passed"] = not reasons
    guardrails["reasons"] = reasons

    def exact_score(counts):
        positive = counts["tp"] if natural_b else counts["tn"]
        denominator = 2 * positive + counts["fp"] + counts["fn"]
        return Fraction(2 * positive, denominator) if denominator else Fraction(0)

    c_score, h_score = exact_score(c), exact_score(h)
    better = c_score > h_score or (c_score == h_score and c_mae < h_mae)
    recommended = bool(guardrails["passed"] and better)
    result.update(promotion_recommended=recommended, promotion_allowed=recommended)
    if reasons:
        reason = "승격 보류: " + " ".join(reasons)
    elif recommended:
        reason = "후보의 우위와 FP·FN 증가 없음이 확인되어 승격을 권장합니다."
    else:
        reason = "기존 모델 유지 권장: 후보의 F1 개선 또는 동점 시 MAE 개선이 확인되지 않았습니다."
    if not natural_b:
        reason += " 실제 B가 없어 이상치 탐지율은 미검증입니다. 정상 자료의 FP와 MAE만 비교했습니다."
    result["recommendation_reason"] = reason
    return result


def _tier2_view_verdict(cand_view: dict | None, champ_view: dict | None,
                        view_label: str, c_mae: float | None = None,
                        h_mae: float | None = None) -> dict:
    """Verify a single Tier 2 QC view (online or consolidated) without conflating views."""
    guardrails = {
        "passed": False,
        "counts_verified": False,
        "fp_not_worse": None,
        "fn_not_worse": None,
        "anomaly_recall_verified": False,
        "scope": "unverified",
        "reasons": [],
    }
    result = {
        "view": view_label,
        "promotion_recommended": False,
        "promotion_allowed": False,
        "f1_score_100": None,
        "champion_f1_score_100": None,
        "event_recall_100": None,
        "champion_event_recall_100": None,
        "guardrails": guardrails,
        "recommendation_reason": "",
    }
    try:
        if not isinstance(cand_view, dict) or not isinstance(cand_view.get("classification"), dict):
            raise ValueError(f"{view_label} 후보 분류 집계가 없습니다.")
        if not isinstance(champ_view, dict) or not isinstance(champ_view.get("classification"), dict):
            raise ValueError(f"{view_label} 기존 모델 분류 집계가 없습니다.")
        c_cls = cand_view["classification"]
        h_cls = champ_view["classification"]
        c = {key: _count(c_cls.get(key), f"{view_label} 후보 {key.upper()}") for key in ("tp", "fp", "tn", "fn")}
        h = {key: _count(h_cls.get(key), f"{view_label} 기존 모델 {key.upper()}") for key in ("tp", "fp", "tn", "fn")}
        natural_b = _count(c_cls.get("labeled_b_count", c["tp"] + c["fn"]), f"{view_label} 실제 B")
        champ_b = _count(h_cls.get("labeled_b_count", h["tp"] + h["fn"]), f"{view_label} 기존 실제 B")
        if natural_b != champ_b or c["tp"] + c["fn"] != natural_b or h["tp"] + h["fn"] != natural_b:
            raise ValueError(f"{view_label} 후보와 기존 모델의 실제 B 건수(TP+FN)가 일치하지 않습니다.")
        normal_g = c["tn"] + c["fp"]
        if normal_g != h["tn"] + h["fp"] or normal_g <= 0:
            raise ValueError(f"{view_label} 후보와 기존 모델의 정상 관측 건수(TN+FP)가 다르거나 0건입니다.")
    except ValueError as exc:
        guardrails["reasons"] = [str(exc)]
        result["recommendation_reason"] = f"승격 보류 ({view_label}): {exc}"
        return result

    fp_ok = c["fp"] <= h["fp"]
    fn_ok = c["fn"] <= h["fn"]
    mae_ok = (c_mae <= h_mae) if (c_mae is not None and h_mae is not None) else True
    guardrails.update(
        counts_verified=True,
        fp_not_worse=fp_ok,
        fn_not_worse=fn_ok,
        anomaly_recall_verified=natural_b > 0,
        scope="normal_and_anomaly" if natural_b > 0 else "normal_only",
    )
    reasons = []
    if not fp_ok:
        reasons.append(f"{view_label} 후보 FP {c['fp']}건이 기존 모델 {h['fp']}건보다 많습니다.")
    if natural_b > 0 and not fn_ok:
        reasons.append(f"{view_label} 후보 FN {c['fn']}건이 기존 모델 {h['fn']}건보다 많습니다.")
    if natural_b == 0 and c_mae is not None and h_mae is not None and not mae_ok:
        reasons.append(f"공통 창 후보 MAE {c_mae:g}가 기존 모델 {h_mae:g}보다 큽니다.")
    guardrails["passed"] = not reasons
    guardrails["reasons"] = reasons

    if natural_b > 0:
        c_denom = 2 * c["tp"] + c["fp"] + c["fn"]
        h_denom = 2 * h["tp"] + h["fp"] + h["fn"]
        c_f1 = Fraction(2 * c["tp"], c_denom) if c_denom else Fraction(0)
        h_f1 = Fraction(2 * h["tp"], h_denom) if h_denom else Fraction(0)
        result["f1_score_100"] = float(c_f1 * 100)
        result["champion_f1_score_100"] = float(h_f1 * 100)
        better = c_f1 > h_f1 or (
            c_f1 == h_f1 and (
                (c["fp"] + c["fn"] < h["fp"] + h["fn"])
                or (c_mae is not None and h_mae is not None and c_mae < h_mae)
            )
        )
    else:
        c_denom = 2 * c["tn"] + c["fp"] + c["fn"]
        h_denom = 2 * h["tn"] + h["fp"] + h["fn"]
        c_nf1 = Fraction(2 * c["tn"], c_denom) if c_denom else Fraction(0)
        h_nf1 = Fraction(2 * h["tn"], h_denom) if h_denom else Fraction(0)
        better = c_nf1 > h_nf1 or (
            c_nf1 == h_nf1 and c_mae is not None and h_mae is not None and c_mae < h_mae
        )

    c_ev_raw = (cand_view or {}).get("events")
    h_ev_raw = (champ_view or {}).get("events")
    c_ev = c_ev_raw if isinstance(c_ev_raw, dict) else {}
    h_ev = h_ev_raw if isinstance(h_ev_raw, dict) else {}
    if natural_b > 0:
        result["event_recall_100"] = c_ev.get("event_recall_100")
        result["champion_event_recall_100"] = h_ev.get("event_recall_100")

    allowed = bool(guardrails["passed"] and better)
    result.update(promotion_recommended=allowed, promotion_allowed=allowed)
    if reasons:
        reason = f"승격 보류 ({view_label}): " + " ".join(reasons)
    elif allowed:
        reason = f"{view_label} 기준 후보 우위 및 FP·FN 악화 없음이 확인되었습니다."
    else:
        reason = f"기존 모델 유지 권장 ({view_label}): 후보의 QC 판정 개선이 확인되지 않았습니다."
    if natural_b == 0:
        reason += " 실제 B가 없어 이상치 F1 및 사건 탐지율은 미검증(null)입니다."
    result["recommendation_reason"] = reason
    return result


TIERED_PROMOTION_POLICY = "tiered-promotion-2026-10-20-v1"


def _finite_metric(value, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{label} 값이 없거나 유한한 수가 아닙니다.")
    if nonnegative and value < 0:
        raise ValueError(f"{label} 값은 0 이상이어야 합니다.")
    return float(value)


def _primary_prediction_verdict(tier1: dict | None) -> dict:
    """Normal prediction is primary; residual anomaly scores have their own denominator."""
    result = {"passed": False, "promotion_allowed": False, "promotion_recommended": False,
              "normal_prediction_improved": False, "anomaly_recall_verified": False,
              "labeled_b_count": None,
              "f1_score_100": None, "champion_f1_score_100": None,
              "event_recall_100": None, "champion_event_recall_100": None,
              "scope": "COMMON_NORMAL_INPUT_WINDOWS_G_TARGETS", "reasons": []}
    reasons = result["reasons"]
    try:
        if not isinstance(tier1, dict):
            raise ValueError("Tier 1 공통 정상창 평가 자료가 없습니다.")
        models = (tier1 or {}).get("models") or {}
        if not isinstance(models, dict):
            raise ValueError("Tier 1 모델 평가 자료 형식이 올바르지 않습니다.")
        candidate, champion = models.get("candidate"), models.get("champion_2025")
        if not isinstance(candidate, dict) or not isinstance(champion, dict):
            raise ValueError("Tier 1 후보와 기존 모델의 공통 정상창 지표가 없습니다.")
        c_normal = candidate.get("normal_prediction") or candidate.get("primary_prediction_metrics") or candidate.get("normal_g")
        h_normal = champion.get("normal_prediction") or champion.get("primary_prediction_metrics") or champion.get("normal_g")
        if not isinstance(c_normal, dict) or not isinstance(h_normal, dict):
            raise ValueError("Tier 1 공통 정상창 MAE·RMSE·R²가 없습니다.")
        c_count = _count(c_normal.get("sample_count", c_normal.get("count")), "후보 공통 정상창")
        h_count = _count(h_normal.get("sample_count", h_normal.get("count")), "기존 모델 공통 정상창")
        if c_count < 2 or c_count != h_count:
            raise ValueError("Tier 1 공통 정상창 건수가 다르거나 R²를 검증할 자료가 부족합니다.")
        c_values, h_values = {}, {}
        improved = False
        for key in ("mae", "rmse", "r2"):
            c_values[key] = _finite_metric(c_normal.get(key), f"후보 정상창 {key}", nonnegative=key != "r2")
            h_values[key] = _finite_metric(h_normal.get(key), f"기존 모델 정상창 {key}", nonnegative=key != "r2")
            delta = h_values[key] - c_values[key] if key != "r2" else c_values[key] - h_values[key]
            if delta < -1e-12:
                reasons.append(f"Tier 1 공통 정상창 {key.upper()}가 기존 모델보다 나빠졌습니다.")
            improved = improved or delta > 1e-12
        result.update(candidate_normal_prediction={"sample_count": c_count, **c_values},
                      champion_normal_prediction={"sample_count": h_count, **h_values},
                      normal_prediction_improved=improved)
        if not improved:
            reasons.append("Tier 1 공통 정상창 MAE·RMSE·R²의 개선이 확인되지 않았습니다.")
        c, _ = _verified_metrics(candidate, "Tier 1 후보")
        h, _ = _verified_metrics(champion, "Tier 1 기존 모델")
        c_cls, h_cls = candidate["classification"], champion["classification"]
        natural_b = _count(c_cls.get("labeled_b_count"), "Tier 1 실제 B")
        if (natural_b != _count(h_cls.get("labeled_b_count"), "Tier 1 기존 실제 B")
                or c["tp"] + c["fn"] != natural_b or h["tp"] + h["fn"] != natural_b
                or c["tn"] + c["fp"] != h["tn"] + h["fp"] or c["tn"] + c["fp"] <= 0):
            raise ValueError("Tier 1 후보와 기존 모델의 원시 G/B 분모가 일치하지 않습니다.")
        if c_count != c["tn"] + c["fp"]:
            raise ValueError("Tier 1 공통 정상창 예측 건수가 실제 G 분모와 다릅니다.")
        result["labeled_b_count"] = natural_b
        result["anomaly_recall_verified"] = natural_b > 0
        if natural_b:
            c_score = Fraction(2 * c["tp"], 2 * c["tp"] + c["fp"] + c["fn"])
            h_score = Fraction(2 * h["tp"], 2 * h["tp"] + h["fp"] + h["fn"])
            event_scores = []
            event_totals = []
            for model, label in ((candidate, "후보"), (champion, "기존 모델")):
                event = model.get("events") or {}
                total = _count(event.get("event_total"), f"Tier 1 {label} 사건 전체")
                detected = _count(event.get("event_detected"), f"Tier 1 {label} 탐지 사건")
                missed = _count(event.get("event_missed"), f"Tier 1 {label} 미탐 사건")
                if total <= 0 or detected + missed != total:
                    raise ValueError(f"Tier 1 {label} 사건 탐지 원시 건수가 맞지 않습니다.")
                event_scores.append(Fraction(detected, total))
                event_totals.append(total)
            if event_totals[0] != event_totals[1]:
                raise ValueError("Tier 1 후보와 기존 모델의 사건 분모가 다릅니다.")
            result.update(f1_score_100=float(c_score * 100), champion_f1_score_100=float(h_score * 100),
                          event_recall_100=float(event_scores[0] * 100),
                          champion_event_recall_100=float(event_scores[1] * 100))
            if c_score < h_score:
                reasons.append("Tier 1 순수 LSTM 잔차 F1이 기존 모델보다 낮습니다.")
            if event_scores[0] < event_scores[1]:
                reasons.append("Tier 1 순수 LSTM 잔차 사건 탐지율이 기존 모델보다 낮습니다.")
    except (ValueError, TypeError) as exc:
        reasons.append(str(exc))
    passed = not reasons
    result.update(passed=passed, promotion_allowed=passed, promotion_recommended=passed)
    result["recommendation_reason"] = ("Tier 1 공통 정상창 예측 개선을 확인했습니다." if passed
                                        else "Tier 1 주 평가지표 미통과: " + " ".join(reasons))
    if result["labeled_b_count"] == 0:
        result["recommendation_reason"] += " 실제 B가 없어 잔차 F1·사건 탐지율은 미검증(null)입니다."
    elif result["labeled_b_count"] is None:
        result["recommendation_reason"] += " 실제 B 집계를 확인하지 못해 잔차 이상 탐지율은 미검증입니다."
    result["promotion_guardrails"] = {"passed": passed, "reasons": list(reasons)}
    return result


def _deployment_equivalence_verdict(bundle_metadata: dict | None) -> dict:
    reasons = []
    try:
        if not isinstance(bundle_metadata, dict):
            raise ValueError("운영 배포 동등성을 확인할 번들 메타데이터가 없습니다.")
        candidate = (bundle_metadata or {}).get("candidate") or {}
        if not isinstance(candidate, dict):
            raise ValueError("운영 배포 후보 번들 메타데이터 형식이 올바르지 않습니다.")
        if candidate.get("deployment_equivalent") is not True:
            raise ValueError("운영 DEV 파일과 시뮬레이터의 임계값 적용 동등성이 검증되지 않았습니다.")
        _finite_metric(candidate.get("raw_threshold_3sigma_cm"), "순수 통계 3σ", nonnegative=True)
        operational = _finite_metric(candidate.get("operational_deploy_threshold_3sigma_cm"), "운영 배포 3σ", nonnegative=True)
        dev = _finite_metric(candidate.get("dev_file_threshold_cm"), "시뮬레이터 DEV", nonnegative=True)
        effective = _finite_metric(candidate.get("effective_lstm_threshold_cm"), "유효 LSTM 임계값", nonnegative=True)
        if min(operational, dev, effective) <= 0:
            raise ValueError("운영 DEV와 유효 LSTM 임계값은 양수여야 합니다.")
        sigma = next(s for upper, s in ((5, 6), (7, 5), (9, 4), (12, 3), (14, 2), (math.inf, 1)) if operational <= upper)
        if dev != operational or not math.isclose(effective, operational / 3.0 * sigma, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("운영 DEV와 LSTM 계단식 변환값이 시뮬레이터 임계값과 다릅니다.")
    except (ValueError, TypeError) as exc:
        reasons.append(str(exc))
    return {"passed": not reasons, "reasons": reasons}


def compute_tiered_promotion_verdict(tier1: dict | None, tier2: dict | None, *,
                                    bundle_metadata: dict | None = None) -> dict:
    """One gate for model improvement and operational do-no-harm, never score overrides."""
    primary = _primary_prediction_verdict(tier1)
    models = tier2.get("models") if isinstance(tier2, dict) else None
    models = models if isinstance(models, dict) else {}
    candidate, champion = models.get("candidate") or {}, models.get("champion_2025") or {}
    candidate = candidate if isinstance(candidate, dict) else {}
    champion = champion if isinstance(champion, dict) else {}
    online = _tier2_view_verdict(candidate.get("online"), champion.get("online"), "Tier 2 실시간(online)")
    consolidated = _tier2_view_verdict(candidate.get("consolidated"), champion.get("consolidated"), "Tier 2 사후최종(consolidated)")
    for view in (online, consolidated):
        passed = bool(view["guardrails"]["passed"])
        view.update(promotion_allowed=passed, promotion_recommended=passed,
                    decision_role="OPERATIONAL_DO_NO_HARM_GUARDRAIL")
        if passed:
            view["recommendation_reason"] = f"{view['view']} FP·FN 비악화를 확인했습니다."
            if not view["guardrails"]["anomaly_recall_verified"]:
                view["recommendation_reason"] += " 실제 B가 없어 이상치 F1·사건 탐지율은 미검증(null)입니다."
    operational_passed = bool(online["guardrails"]["passed"] and consolidated["guardrails"]["passed"])
    operational_reasons = list(online["guardrails"]["reasons"]) + list(consolidated["guardrails"]["reasons"])
    operational = {"passed": operational_passed, "online_verdict": online,
                   "consolidated_verdict": consolidated, "reasons": operational_reasons}
    deployment = _deployment_equivalence_verdict(bundle_metadata)
    reasons = list(dict.fromkeys(primary["reasons"] + operational_reasons + deployment["reasons"]))
    allowed = bool(primary["passed"] and operational_passed and deployment["passed"])
    reason = ("Tier 1 공통 정상창 예측 개선과 Tier 2 실시간·사후최종 FP·FN 비악화를 확인했습니다."
              if allowed else "승격 보류: " + " / ".join(reasons))
    if primary["labeled_b_count"] == 0:
        reason += " 실제 B가 없어 잔차 이상 탐지율은 미검증(null)입니다."
    elif primary["labeled_b_count"] is None:
        reason += " 실제 B 집계를 확인하지 못해 잔차 이상 탐지율은 미검증입니다."
    return {"policy_version": TIERED_PROMOTION_POLICY, "policy_current": True,
            "promotion_recommended": allowed, "promotion_allowed": allowed,
            "primary_metric_scope": {"prediction": "COMMON_NORMAL_INPUT_WINDOWS_G_TARGETS",
                                     "anomaly": "RAW_LSTM_RESIDUAL_COMMON_INPUT_WINDOWS"},
            "primary_tier1_verdict": primary, "tier1_verdict": primary,
            "operational_tier2_verdict": operational, "deployment_equivalence": deployment,
            "tier2_guardrails_passed": operational_passed, "online_verdict": online,
            "consolidated_verdict": consolidated, "reasons": reasons,
            "recommendation_reason": reason,
            "promotion_guardrails": {"passed": allowed, "reasons": reasons}}

def local_qc_promotion_verdict(qc_comparison: dict | None) -> dict:
    """Recompute current policy; retain old evidence as history without authorizing promotion."""
    comp = qc_comparison if isinstance(qc_comparison, dict) else {}
    result = compute_tiered_promotion_verdict(comp.get("tier1"), comp.get("tier2"),
                                            bundle_metadata=comp.get("bundle_metadata"))
    result.update(available=isinstance(qc_comparison, dict), simulation_id=comp.get("simulation_id"),
                  scope=comp.get("scope"), evaluated_snapshot_id=comp.get("evaluated_snapshot_id"))
    current = comp.get("policy_version") == TIERED_PROMOTION_POLICY
    result["policy_current"] = current
    if not current:
        message = "이전 정책의 시뮬레이션이거나 현재 정책 검증 결과가 없습니다. 현재 번들로 다시 실행해 주세요."
        result["reasons"].append(message)
        result.update(promotion_allowed=False, promotion_recommended=False,
                      recommendation_reason="승격 보류: " + " / ".join(result["reasons"]))
        result["promotion_guardrails"] = {"passed": False, "reasons": result["reasons"]}
    return result


def trend_reversal_diagnostics(x_raw, y_true, predictions, threshold_cm) -> dict:
    """Describe normal-target reversals after prediction without changing any decision."""
    try:
        windows, targets, estimates = list(x_raw), list(y_true), list(predictions)
    except TypeError as exc:
        raise ValueError("방향 전환 진단의 입력·실제값·예측값은 배열이어야 합니다.") from exc
    if len(windows) != len(targets) or len(windows) != len(estimates):
        raise ValueError("방향 전환 진단의 입력·실제값·예측값 길이가 다릅니다.")

    def finite(value, label):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(f"방향 전환 진단의 {label}은 유한한 숫자여야 합니다.")
        return float(value)

    threshold = finite(threshold_cm, "임계값")
    if threshold < 0:
        raise ValueError("방향 전환 진단의 임계값은 0 이상이어야 합니다.")
    errors = []
    for index, window in enumerate(windows):
        try:
            rows = list(window)
            if len(rows) != 4 or any(len(row) != 2 for row in rows):
                raise ValueError("방향 전환 진단의 입력 모양은 (N, 4, 2)여야 합니다.")
        except TypeError as exc:
            raise ValueError("방향 전환 진단의 입력 모양은 (N, 4, 2)여야 합니다.") from exc
        values = [[finite(value, "입력값") for value in row] for row in rows]
        target = finite(targets[index], "실제값")
        estimate = finite(estimates[index], "예측값")
        input_step = values[-1][0] - values[-2][0]
        target_step = target - values[-1][0]
        if (input_step < 0 < target_step) or (target_step < 0 < input_step):
            errors.append(abs(estimate - target))
    count = len(errors)
    fp = sum(error > threshold for error in errors)
    return {"normal_reversal_windows": count, "normal_reversal_fp": fp,
            "normal_reversal_fp_rate": fp / count if count else None,
            "normal_reversal_mae": sum(errors) / count if count else None,
            "label": "POST_HOC_NORMAL_REVERSAL_DIAGNOSTIC",
            "definition": "정상 G의 마지막 입력 OBS 변화와 실제 다음 OBS 변화가 모두 0이 아니고 방향이 반대인 관측값을 사후 집계합니다. FP는 절대 예측오차가 임계값보다 큰 경우입니다. 예측과 판정을 바꾸지 않습니다."}


def event_detection_metrics(timestamps, is_anomaly, detected) -> dict:
    """Count events formed only by consecutive B targets exactly one minute apart."""
    times, flags, decisions = list(timestamps), list(is_anomaly), list(detected)
    if len(times) != len(flags) or len(times) != len(decisions):
        raise ValueError("사건 평가의 시각·B 여부·탐지 여부 길이가 다릅니다.")
    parsed = []
    for value in times:
        if value is None:
            raise ValueError("사건 평가에 시각이 없는 관측값이 있습니다.")
        try:
            stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed and stamp <= parsed[-1]:
                raise ValueError("사건 평가 시각은 중복 없이 오름차순이어야 합니다.")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"사건 평가 시각이 올바르지 않습니다: {value}") from exc
        parsed.append(stamp)
    if any(value not in (True, False) for value in flags + decisions):
        raise ValueError("사건 평가의 B 여부와 탐지 여부는 참 또는 거짓이어야 합니다.")

    events = []
    for index, abnormal in enumerate(flags):
        if not abnormal:
            continue
        if events and index == events[-1][-1] + 1 and parsed[index] - parsed[index - 1] == timedelta(minutes=1):
            events[-1].append(index)
        else:
            events.append([index])
    latencies = []
    for event in events:
        first_detection = next((index for index in event if decisions[index]), None)
        if first_detection is not None:
            latencies.append((parsed[first_detection] - parsed[event[0]]).total_seconds() / 60.0)
    total, found = len(events), len(latencies)
    return {"event_total": total, "event_detected": found, "event_missed": total - found,
            "event_recall": found / total if total else None,
            "event_recall_100": 100.0 * found / total if total else None,
            "mean_detection_latency_minutes": sum(latencies) / found if found else None}
