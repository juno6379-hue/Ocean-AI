"""Causal fitted anomaly evidence, separated from source/QC/model approval.

Source facts below are a declared development contract, not a server-verified
SOURCE_CONTRACT receipt. Missing facts fail closed. Real production continues to
require the existing source/dataset/model authority and independent review.
"""
from __future__ import annotations

import copy
from datetime import timedelta

import numpy as np

from app.ml.anomaly_artifact import (
    SCHEMA, MAX_ROWS, AnomalyContractError, canonical_bytes, clock, envelope,
    evidence, fingerprint, number, sha256, verify,
)

MODES = {"SPIKE", "PERSISTENCE", "TIDE_RESIDUAL", "DRIFT",
         "BIOFOULING_CANDIDATE", "SENSOR_DEGRADATION_CANDIDATE"}
REFERENCE_MODES = MODES - {"SPIKE", "PERSISTENCE"}
FACT_NAMES = {"semantic", "unit", "clock", "qc", "sensor_episode"}
CAUSAL_FEATURE_VERSION = "causal-robust-reference-1"
FAMILY_UNITS={"TIDE":{"m","meter","cm","mm"},"TEMP":{"degree_C","℃","°C","K","degree_F","°F"},
              "SAL":{"psu","PSS-78","1","g/kg","g_kg-1"}}
MAX_WINDOW_WORK=2_000_000


def _scope(series):
    scope = series.get("scope")
    keys = ("station_id", "sensor_id", "variable_code", "unit", "sensor_episode_id")
    if not isinstance(scope, dict) or set(scope) != set(keys) or any(
            not isinstance(scope[k], str) or not scope[k].strip() or len(scope[k]) > 160 for k in keys):
        raise AnomalyContractError("EXACT_SINGLE_SENSOR_SCOPE_REQUIRED")
    return scope


def _fact_errors(series):
    scope, facts = _scope(series), series.get("facts", {})
    errors = []
    if not isinstance(facts, dict):
        return ["SOURCE_FACTS_NOT_DOCUMENTED"]
    for key in sorted(FACT_NAMES):
        item = facts.get(key, {})
        if not isinstance(item, dict) or item.get("documented") is not True or not evidence(item.get("evidence")):
            errors.append("SOURCE_" + key.upper() + "_NOT_DOCUMENTED")
    for key, expected in (("semantic", scope["variable_code"]), ("unit", scope["unit"]),
                          ("clock", "UTC_WITH_EXPLICIT_OFFSET"), ("sensor_episode", scope["sensor_episode_id"])):
        if isinstance(facts.get(key), dict) and facts[key].get("value") != expected:
            errors.append("SOURCE_" + key.upper() + "_SCOPE_MISMATCH")
    if not isinstance(facts.get("qc", {}).get("value"), str) or not facts["qc"]["value"]:
        errors.append("SOURCE_QC_CODEBOOK_VERSION_MISSING")
    if facts.get("sensor_episode", {}).get("physical_sensor_id") != scope["sensor_id"]:
        errors.append("SOURCE_PHYSICAL_SENSOR_MISMATCH")
    return errors


def _reference_error(series, mode, family):
    if mode not in REFERENCE_MODES:
        return None
    ref = series.get("reference_contract", {})
    if not isinstance(ref, dict) or not evidence(ref.get("evidence")):
        return "PAIRED_REFERENCE_CONTRACT_MISSING"
    scope = series["scope"]
    if ref.get("unit") != scope["unit"] or ref.get("station_id") != scope["station_id"] or ref.get("variable_code") != scope["variable_code"]:
        return "REFERENCE_UNIT_OR_EXACT_SCOPE_MISMATCH"
    if mode == "TIDE_RESIDUAL":
        datum = series["facts"].get("datum", {})
        if family != "TIDE" or ref.get("kind") != "PREDICTED_TIDE":
            return "EXPLICIT_PREDICTED_TIDE_REQUIRED"
        if not isinstance(datum, dict) or datum.get("documented") is not True or not evidence(datum.get("evidence")) or not datum.get("value") or ref.get("datum") != datum["value"]:
            return "COMMON_TIDE_DATUM_NOT_DOCUMENTED"
    else:
        if family not in {"TEMP", "SAL"} or ref.get("kind") != "INDEPENDENT_SENSOR" or not ref.get("sensor_id") or ref.get("sensor_id") == scope["sensor_id"]:
            return "INDEPENDENT_TEMP_SAL_REFERENCE_REQUIRED"
        if not isinstance(ref.get("sensor_episode_id"), str) or not ref["sensor_episode_id"]:
            return "REFERENCE_PHYSICAL_EPISODE_MISSING"
    if mode.endswith("CANDIDATE"):
        context = series.get("candidate_context", {}).get(mode, {})
        if not isinstance(context, dict) or context.get("applicable") is not True or not evidence(context.get("evidence")):
            return "EQUIPMENT_MECHANISM_CONTEXT_NOT_DOCUMENTED"
    return None


def _protocol(protocol):
    if not isinstance(protocol, dict) or protocol.get("schema_version") != "ocean-anomaly-protocol-1":
        raise AnomalyContractError("VERSIONED_ANOMALY_PROTOCOL_REQUIRED")
    for key in ("protocol_id", "version"):
        if not isinstance(protocol.get(key), str) or not protocol[key]:
            raise AnomalyContractError("PROTOCOL_ID_VERSION_REQUIRED")
    modes = protocol.get("modes")
    if not isinstance(modes, list) or not modes or not all(isinstance(x, str) for x in modes) or len(set(modes)) != len(modes) or not set(modes) <= MODES:
        raise AnomalyContractError("SUPPORTED_UNIQUE_MODES_REQUIRED")
    if protocol.get("variable_family") not in {"TIDE", "TEMP", "SAL", "OTHER"}:
        raise AnomalyContractError("EXPLICIT_VARIABLE_FAMILY_REQUIRED")
    for key, low, high in (("cadence_seconds", 1, 86400), ("window_samples", 4, 1000),
                           ("min_train_samples", 8, MAX_ROWS), ("min_calibration_samples", 8, MAX_ROWS)):
        if type(protocol.get(key)) is not int or not low <= protocol[key] <= high:
            raise AnomalyContractError("PROTOCOL_INTEGER_OUT_OF_RANGE", key)
    for key in ("scale_floor", "persistence_epsilon"):
        if number(protocol.get(key), key) <= 0:
            raise AnomalyContractError("EXPLICIT_POSITIVE_UNIT_RESOLUTION_REQUIRED", key)
    quantile = number(protocol.get("calibration_quantile"), "calibration_quantile")
    if not .5 < quantile < 1:
        raise AnomalyContractError("CALIBRATION_QUANTILE_OUT_OF_RANGE")
    previous_end = None
    for split in ("TRAIN", "CALIBRATION"):
        span = protocol.get("periods", {}).get(split, {})
        start, end = clock(span.get("start")), clock(span.get("end"))
        if start >= end or previous_end and start < previous_end:
            raise AnomalyContractError("FIXED_TEMPORAL_SPLIT_OVERLAP")
        previous_end = end
        digest = protocol.get("membership_sha256", {}).get(split)
        if not evidence([{"sha256": digest, "locator": "membership"}]):
            raise AnomalyContractError("FIXED_ROW_MEMBERSHIP_DIGEST_REQUIRED", split)
    canonical_bytes(protocol)
    return protocol


def _rows(series):
    _scope(series)
    if series.get("schema_version") != "ocean-anomaly-series-1":
        raise AnomalyContractError("VERSIONED_SERIES_REQUIRED")
    rows = series.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS:
        raise AnomalyContractError("BOUNDED_NONEMPTY_SERIES_REQUIRED")
    as_of, ids, cells, reference_cells, previous = clock(series.get("as_of")), set(), set(), set(), None
    result = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("row_id"), str) or not row["row_id"] or row["row_id"] in ids:
            raise AnomalyContractError("UNIQUE_SOURCE_ROW_ID_REQUIRED")
        if row.get("scope") != series["scope"]:
            raise AnomalyContractError("ROW_EXACT_PHYSICAL_SCOPE_MISMATCH",row["row_id"])
        t, availability = clock(row.get("timestamp")), clock(row.get("available_at"))
        qc_available = clock(row.get("qc_available_at"))
        if previous and t <= previous:
            raise AnomalyContractError("STRICT_TIME_ORDER_NO_DUPLICATE_TIMESTAMP_REQUIRED")
        previous = t; ids.add(row["row_id"])
        source = row.get("source")
        if not evidence([source]):
            raise AnomalyContractError("SOURCE_SHA_LOCATOR_REQUIRED", row["row_id"])
        cell = (source["sha256"], source["locator"])
        if cell in cells or cell in reference_cells:
            raise AnomalyContractError("DUPLICATE_SOURCE_RECORD_REUSE")
        cells.add(cell)
        errors = []
        if row.get("value") is None: errors.append("MISSING_VALUE")
        else: number(row["value"], "value")
        if row.get("qc_eligible") is not True: errors.append("SOURCE_QC_NOT_USABLE")
        if availability < t: errors.append("OBSERVATION_AVAILABLE_BEFORE_OBSERVED_CLOCK")
        if t > as_of or availability > as_of or qc_available > as_of: errors.append("SOURCE_NOT_AVAILABLE_AS_OF")
        for key in sorted(FACT_NAMES):
            fact=series.get("facts", {}).get(key, {}); name=key.upper()+"_CONTRACT"
            try:
                if not clock(fact.get("start")) <= t < clock(fact.get("end")):
                    errors.append(name + "_OUTSIDE_EFFECTIVE_INTERVAL")
            except AnomalyContractError:
                errors.append(name + "_EFFECTIVE_INTERVAL_NOT_DOCUMENTED")
        reference_error=None
        ref_source=row.get("reference",{}).get("source") if isinstance(row.get("reference"),dict) else None
        if evidence([ref_source]):
            ref_cell=(ref_source["sha256"],ref_source["locator"])
            if ref_cell in reference_cells or ref_cell in cells:
                reference_error="REFERENCE_SOURCE_RECORD_REUSE"
            reference_cells.add(ref_cell)
        result.append({"raw": row, "time": t, "available": max(availability,qc_available), "errors": errors,"reference_error":reference_error})
    canonical_bytes(series)
    return result


def _reference(row, series):
    ref = row["raw"].get("reference")
    contract = series.get("reference_contract", {})
    if not isinstance(ref, dict):
        return None, "PAIRED_REFERENCE_ROW_MISSING"
    if row.get("reference_error"):
        return None,row["reference_error"]
    try:
        value = number(ref.get("value"), "reference.value")
        if clock(ref.get("timestamp")) != row["time"] or ref.get("unit") != series["scope"]["unit"]:
            return None, "REFERENCE_TIME_OR_UNIT_MISMATCH"
        if ref.get("station_id")!=contract.get("station_id") or ref.get("variable_code")!=contract.get("variable_code"):
            return None,"REFERENCE_STATION_OR_VARIABLE_MISMATCH"
        if not evidence([ref.get("source")]) or ref.get("qc_eligible") is not True:
            return None, "REFERENCE_SOURCE_OR_QC_NOT_DOCUMENTED"
        if not isinstance(contract.get("qc_version"),str) or not contract["qc_version"] or not clock(contract.get("qc_effective_start"))<=row["time"]<clock(contract.get("qc_effective_end")):
            return None,"REFERENCE_QC_EFFECTIVE_CONTRACT_MISSING"
        if max(clock(ref.get("available_at")),clock(ref.get("qc_available_at"))) > clock(series["as_of"]):
            return None, "REFERENCE_NOT_AVAILABLE_AS_OF"
        if contract.get("kind") == "INDEPENDENT_SENSOR" and (ref.get("sensor_id") != contract.get("sensor_id") or ref.get("sensor_episode_id") != contract.get("sensor_episode_id")):
            return None, "REFERENCE_PHYSICAL_SCOPE_MISMATCH"
        if contract.get("kind") == "INDEPENDENT_SENSOR" and (not clock(contract.get("effective_start"))<=row["time"]<clock(contract.get("effective_end")) or clock(ref["available_at"])<row["time"]):
            return None, "REFERENCE_EFFECTIVE_INTERVAL_OR_RECEIVE_CLOCK_INVALID"
        if contract.get("kind") == "PREDICTED_TIDE" and ref.get("datum") != contract.get("datum"):
            return None, "REFERENCE_DATUM_MISMATCH"
        if contract.get("kind") == "PREDICTED_TIDE":
            if clock(ref.get("issued_at"))>row["time"] or clock(ref["available_at"])>row["time"] or clock(contract.get("model_training_end"))>clock(ref["issued_at"]):
                return None,"TIDE_PREDICTION_NOT_AVAILABLE_CAUSALLY"
            datum=series["facts"].get("datum",{})
            if not clock(datum.get("start"))<=row["time"]<clock(datum.get("end")):
                return None,"TIDE_DATUM_EFFECTIVE_INTERVAL_MISSING"
        return value, None
    except AnomalyContractError as exc:
        return None, exc.code


def _window(rows, index, count, cadence):
    window = rows[max(0, index-count+1):index+1]
    if len(window) != count: return None, "CAUSAL_WINDOW_WARMUP"
    if any(r["errors"] for r in window): return None, "WINDOW_SOURCE_NOT_USABLE"
    if any((right["time"]-left["time"]).total_seconds() != cadence for left,right in zip(window,window[1:])):
        return None, "GAP_IN_EXACT_CADENCE_WINDOW"
    return window, None


def _robust(values, floor):
    center = float(np.median(values))
    return center, max(float(np.median(np.abs(np.array(values)-center))) * 1.4826, floor)


def _feature(rows, index, mode, series, policy, fitted):
    row = rows[index]
    if row["errors"]: return None, row["errors"][0], [row]
    width = 2 if mode == "SPIKE" else (1 if mode == "TIDE_RESIDUAL" else policy["window_samples"])
    window, error = _window(rows,index,width,policy["cadence_seconds"])
    if error: return None, error, [row]
    values = np.array([r["raw"]["value"] for r in window],float)
    if mode == "SPIKE": return float(abs(values[-1]-values[-2])/fitted["delta_scale"]), None, window
    if mode == "PERSISTENCE":
        spread = float(np.ptp(values))
        return fitted["normal_window_range"] / max(spread, policy["persistence_epsilon"]), None, window
    refs=[]
    for part in window:
        value, error = _reference(part,series)
        if error: return None,error,window
        refs.append(value)
    residual = values-np.array(refs)
    if mode == "TIDE_RESIDUAL":
        return float(abs(residual[-1]-fitted["residual_center"])/fitted["residual_scale"]),None,window
    drift = float(abs(np.median(residual)-fitted["residual_center"])/fitted["residual_scale"])
    if mode == "DRIFT": return drift,None,window
    if mode == "SENSOR_DEGRADATION_CANDIDATE":
        noise = float(np.median(np.abs(residual-np.median(residual)))) * 1.4826
        return max(drift,noise/fitted["residual_scale"]),None,window
    ref_change = float(np.std(np.diff(refs)))
    if ref_change <= policy["scale_floor"]: return None,"REFERENCE_RESPONSE_VARIATION_INSUFFICIENT",window
    ratio = float(np.std(np.diff(values)))/ref_change
    # This floor guards numeric division of a dimensionless response ratio.
    # The physical source resolution remains separately frozen in scale_floor.
    damping = fitted["normal_response_ratio"] / max(ratio,1e-12)
    return drift*max(1.,damping),None,window


def _contract(series):
    return {key:series.get(key) for key in ("scope","facts","reference_contract","candidate_context")}


def _work_limit(count,policy,fit=False):
    width=lambda mode:2 if mode=="SPIKE" else 1 if mode=="TIDE_RESIDUAL" else policy["window_samples"]
    work=count*sum(width(mode) for mode in policy["modes"])
    if fit and set(policy["modes"]) & {"PERSISTENCE","BIOFOULING_CANDIDATE"}:
        work+=count*policy["window_samples"]
    if work>MAX_WINDOW_WORK:
        raise AnomalyContractError("CAUSAL_WINDOW_WORK_BUDGET_EXCEEDED")


def source_requirements(series):
    """Inspect a supplied series before defining any train/calibration membership.

    Useful for real-source read-only smoke checks: preserve unresolved clocks and
    units rather than inventing a UTC mapping or a training split to run fit.
    """
    try:
        errors=_fact_errors(series)
        try:
            rows=_rows(series)
            errors+=sorted({reason for row in rows for reason in row["errors"]})
        except AnomalyContractError as exc:
            errors.append(exc.code)
        return {"status":"NOT_EVALUATED" if errors else "CONDITIONAL_INPUT_READY",
            "source_authority":"DECLARED_DEVELOPMENT_CONTRACT","approved":False,
            "production_eligible":False,"input_sha256":sha256(series),
            "blockers":sorted(set(errors)),"training_executed":False}
    except (AnomalyContractError,KeyError,TypeError,ValueError,AttributeError,OverflowError) as exc:
        return {"status":"NOT_EVALUATED","source_authority":"DECLARED_DEVELOPMENT_CONTRACT",
            "approved":False,"production_eligible":False,"training_executed":False,
            "blockers":[exc.code if isinstance(exc,AnomalyContractError) else "MALFORMED_ANOMALY_INPUT"]}


def _fit_analysis(series, policy):
    policy = _protocol(policy)
    rows = _rows(series)
    _work_limit(len(rows),policy,True)
    errors = _fact_errors(series)
    if series.get("facts",{}).get("semantic",{}).get("variable_family")!=policy["variable_family"]:
        errors.append("SOURCE_VARIABLE_FAMILY_NOT_DOCUMENTED")
    if policy["variable_family"] in FAMILY_UNITS and series["scope"]["unit"] not in FAMILY_UNITS[policy["variable_family"]]:
        errors.append("UNIT_NOT_SUPPORTED_FOR_DECLARED_VARIABLE_FAMILY")
    if errors: return {"status":"NOT_EVALUATED","approved":False,"production_eligible":False,"blockers":errors}
    groups = {}
    for split in ("TRAIN","CALIBRATION"):
        span=policy["periods"][split]; start,end=clock(span["start"]),clock(span["end"])
        groups[split]=[r for r in rows if start<=r["time"]<end]
        if sha256(sorted(r["raw"]["row_id"] for r in groups[split])) != policy["membership_sha256"][split]:
            raise AnomalyContractError("FIXED_ROW_MEMBERSHIP_CHANGED",split)
    if len(groups["TRAIN"])+len(groups["CALIBRATION"]) != len(rows):
        raise AnomalyContractError("FIT_INPUT_OUTSIDE_FIXED_TRAIN_CALIBRATION")
    if clock(series["as_of"]) < clock(policy["periods"]["CALIBRATION"]["end"]):
        raise AnomalyContractError("FIT_AS_OF_BEFORE_CALIBRATION_COMPLETE")
    train = groups["TRAIN"]
    usable = [r for r in train if not r["errors"]]
    if len(usable)<policy["min_train_samples"]:
        return {"status":"NOT_EVALUATED","approved":False,"production_eligible":False,"blockers":["MINIMUM_USABLE_TRAIN_SAMPLES_NOT_MET"]}
    delta=[r["raw"]["value"]-l["raw"]["value"] for l,r in zip(train,train[1:]) if not l["errors"] and not r["errors"] and (r["time"]-l["time"]).total_seconds()==policy["cadence_seconds"]]
    _, delta_scale = _robust(delta,policy["scale_floor"]) if delta else (0.,policy["scale_floor"])
    residuals=[];ranges=[];ratios=[]
    for index,row in enumerate(train):
        if set(policy["modes"]) & REFERENCE_MODES:
            ref,error=_reference(row,series)
            if not error and not row["errors"]:residuals.append(row["raw"]["value"]-ref)
        if not set(policy["modes"]) & {"PERSISTENCE","BIOFOULING_CANDIDATE"}:
            continue
        window,error=_window(train,index,policy["window_samples"],policy["cadence_seconds"])
        if not error:
            values=np.array([r["raw"]["value"] for r in window],float);ranges.append(float(np.ptp(values)))
            refs=[_reference(r,series) for r in window]
            if all(error is None for _,error in refs):
                variation=float(np.std(np.diff([v for v,_ in refs])))
                if variation>policy["scale_floor"]:ratios.append(float(np.std(np.diff(values)))/variation)
    center,scale=_robust(residuals,policy["scale_floor"]) if residuals else (0.,policy["scale_floor"])
    fitted={"delta_scale":delta_scale,"residual_center":center,"residual_scale":scale,
        "normal_window_range":float(np.median(ranges)) if ranges else 0.,
        "normal_response_ratio":float(np.median(ratios)) if ratios else 0.}
    models={}; calibration=groups["CALIBRATION"]
    for mode in policy["modes"]:
        error=_reference_error(series,mode,policy["variable_family"])
        if mode=="PERSISTENCE" and fitted["normal_window_range"]<=policy["persistence_epsilon"]:
            error="NORMAL_TRAIN_RESPONSE_TOO_FLAT_FOR_PERSISTENCE_MODEL"
        if mode in REFERENCE_MODES and len(residuals)<policy["min_train_samples"]:
            error=error or "MINIMUM_USABLE_PAIRED_TRAIN_SAMPLES_NOT_MET"
        if mode=="BIOFOULING_CANDIDATE" and not ratios:
            error=error or "REFERENCE_TRAIN_RESPONSE_VARIATION_INSUFFICIENT"
        scores=[];excluded=[]
        for index,row in enumerate(calibration):
            value,reason,_=_feature(calibration,index,mode,series,policy,fitted) if not error else (None,error,None)
            if reason:excluded.append({"row_id":row["raw"]["row_id"],"reason":reason})
            else:scores.append(value)
        if len(scores)<policy["min_calibration_samples"]:error=error or "MINIMUM_USABLE_CALIBRATION_SAMPLES_NOT_MET"
        models[mode]={"status":"NOT_EVALUATED" if error else "FITTED","reason":error,
            "calibration_scores":sorted(scores),"calibration_count":len(scores),
            "threshold":None if error else float(np.quantile(scores,policy["calibration_quantile"],method="higher")),
            "calibration_exclusions":excluded}
    body={"schema_version":SCHEMA,"feature_version":CAUSAL_FEATURE_VERSION,"code_sha256":fingerprint(),
        "approved":False,"production_eligible":False,"authority":"DECLARED_DEVELOPMENT_CONTRACT",
        "fit_as_of":series["as_of"],"policy":copy.deepcopy(policy),"policy_sha256":sha256(policy),
        "contract":copy.deepcopy(_contract(series)),"contract_sha256":sha256(_contract(series)),
        "fit_data_sha256":sha256(series["rows"]),"split_data_sha256":{s:sha256([r["raw"] for r in rs]) for s,rs in groups.items()},
        "used_train_count":len(usable),"train_exclusions":[{"row_id":r["raw"]["row_id"],"reasons":r["errors"]} for r in train if r["errors"]],
        "fit_source_record_keys":[[source["sha256"],source["locator"]] for r in rows for source in
            [r["raw"]["source"],r["raw"].get("reference",{}).get("source") if isinstance(r["raw"].get("reference"),dict) else None] if evidence([source])],
        "fitted":fitted,"models":models,"score_kind":"EMPIRICAL_CALIBRATION_RANK_NOT_PROBABILITY",
        "cause_attribution":"NOT_ESTABLISHED","registered_models":0,"deployed_models":0}
    return {"status":"FITTED" if any(m["status"]=="FITTED" for m in models.values()) else "NOT_EVALUATED",
        "approved":False,"production_eligible":False,"artifact":envelope(body),
        "blockers":[{"mode":k,"reason":v["reason"]} for k,v in models.items() if v["reason"]]}


def fit_analysis(series, protocol):
    """Fit train statistics and independent calibration thresholds; never test."""
    try:return _fit_analysis(series,protocol)
    except AnomalyContractError as exc:
        return {"status":"NOT_EVALUATED","approved":False,"production_eligible":False,"blockers":[exc.code],"detail":exc.detail}
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError) as exc:
        return {"status":"NOT_EVALUATED","approved":False,"production_eligible":False,"blockers":["MALFORMED_ANOMALY_INPUT"],"detail":type(exc).__name__}


def _analyze(series, enveloped):
    body=verify(enveloped);policy=_protocol(body["policy"]);rows=_rows(series)
    _work_limit(len(rows),policy)
    fitted=body.get("fitted",{})
    for key in ("delta_scale","residual_scale","normal_window_range","normal_response_ratio","residual_center"):
        value=number(fitted.get(key),"fitted."+key)
        if key in {"delta_scale","residual_scale"} and value<=0 or key in {"normal_window_range","normal_response_ratio"} and value<0:
            raise AnomalyContractError("ARTIFACT_NUMERIC_PARAMETER_INVALID",key)
    if body["policy_sha256"]!=sha256(policy) or body["contract_sha256"]!=sha256(_contract(series)) or body["contract_sha256"]!=sha256(body["contract"]):
        raise AnomalyContractError("FROZEN_SCOPE_OR_SOURCE_FACTS_CHANGED")
    if _fact_errors(series):raise AnomalyContractError("SOURCE_FACTS_NOT_DOCUMENTED")
    if rows[0]["time"]<max(clock(policy["periods"]["CALIBRATION"]["end"]),clock(body["fit_as_of"])) or clock(series["as_of"])<clock(body["fit_as_of"]):
        raise AnomalyContractError("ANALYSIS_MUST_FOLLOW_FIXED_CALIBRATION")
    fit_cells={tuple(x) for x in body["fit_source_record_keys"]}
    if any((source["sha256"],source["locator"]) in fit_cells for r in rows for source in
            [r["raw"]["source"],r["raw"].get("reference",{}).get("source") if isinstance(r["raw"].get("reference"),dict) else None] if evidence([source])):
        raise AnomalyContractError("FIT_TEST_SOURCE_RECORD_REUSE")
    results=[]
    for mode in policy["modes"]:
        model=body["models"][mode]
        calibration=model["calibration_scores"]
        if len(calibration)>MAX_ROWS or any(number(x,"calibration_score")<0 for x in calibration) or calibration!=sorted(calibration):
            raise AnomalyContractError("ARTIFACT_CALIBRATION_INVALID")
        if model["status"]=="FITTED" and (len(calibration)<policy["min_calibration_samples"] or model["threshold"]!=float(np.quantile(calibration,policy["calibration_quantile"],method="higher"))):
            raise AnomalyContractError("ARTIFACT_THRESHOLD_CALIBRATION_MISMATCH")
        for index,row in enumerate(rows):
            value,error,window=_feature(rows,index,mode,series,policy,body["fitted"]) if model["status"]=="FITTED" else (None,model["reason"],[row])
            triggered=not error and value>model["threshold"]
            if mode=="PERSISTENCE" and not error:
                triggered=triggered and np.ptp([r["raw"]["value"] for r in window])<=policy["persistence_epsilon"]
            availability=max(r["available"] for r in window)
            if mode in REFERENCE_MODES and not error:
                availability=max([availability]+[clock(r["raw"]["reference"][key]) for r in window for key in ("available_at","qc_available_at") if isinstance(r["raw"].get("reference"),dict) and r["raw"]["reference"].get(key)])
            rank=None if error else float(np.searchsorted(calibration,value,side="right")/len(calibration))
            result={"mode":mode,"row_id":row["raw"]["row_id"],"event_at":row["time"].isoformat(),"available_at":None if error else availability.isoformat(),
                "result_status":"NOT_EVALUATED" if error else "EVALUATED","assessment":"UNKNOWN" if error else ("ANOMALY" if triggered else "NORMAL"),
                "score":value,"threshold":model["threshold"],"calibration_rank":rank,
                "support_strength":None if error else (rank if triggered else 1-rank),
                "score_kind":"EMPIRICAL_CALIBRATION_RANK_NOT_PROBABILITY","reason":error,
                "candidate_only":True,"cause_attribution":"NOT_ESTABLISHED","final_qc_changed":False,
                "source_ids":[r["raw"]["row_id"] for r in window],"source_records":[r["raw"]["source"] for r in window],
                "reference_source_records":[r["raw"]["reference"]["source"] for r in window if isinstance(r["raw"].get("reference"),dict) and evidence([r["raw"]["reference"].get("source")])],
                "window_start":window[0]["time"].isoformat(),"window_end":window[-1]["time"].isoformat()}
            results.append(result)
    report={"status":"ANALYSIS_ONLY","approved":False,"production_eligible":False,"scope":series["scope"],
        "as_of":series["as_of"],"artifact_sha256":enveloped["sha256"],"input_sha256":sha256(series),
        "source_authority":"DECLARED_DEVELOPMENT_CONTRACT","results":results,"cause_attribution":"NOT_ESTABLISHED",
        "registered_models":0,"deployed_models":0}
    report["result_sha256"]=sha256(report)
    return report


def analyze_series(series, artifact):
    """Score only later observations, with past/current windows and fixed models."""
    try:return _analyze(series,artifact)
    except AnomalyContractError as exc:
        return {"status":"NOT_EVALUATED","approved":False,"production_eligible":False,"blockers":[exc.code],"detail":exc.detail}
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError) as exc:
        return {"status":"NOT_EVALUATED","approved":False,"production_eligible":False,"blockers":["MALFORMED_ANOMALY_INPUT"],"detail":type(exc).__name__}
