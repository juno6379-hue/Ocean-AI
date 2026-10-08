# 파일 역할: 관측 품질 분석 및 추천 관련 요청을 검증하고 API 응답을 제공합니다.
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import (
    AILabel, AIPredictionResult, OperationLog, QCFlagHistory, QCRuleResult,
    StationMetadata,
)

router = APIRouter(prefix="/api/ai-insights", tags=["AI Insights"])

@router.get("/long-term")
def long_term_insights(station_id: Optional[str] = None, variable_code: str = "TIDE", db: Session = Depends(get_db)):
    from app.models.domain import ObservationStandard
    from sqlalchemy import func
    q=db.query(ObservationStandard).filter(ObservationStandard.variable_code==variable_code.upper())
    if station_id: q=q.filter(ObservationStandard.station_id==station_id)
    rows=q.all(); by_station={}
    for r in rows: by_station.setdefault(r.station_id,[]).append(r)
    results=[]
    for station,vals in by_station.items():
        vals=sorted([v for v in vals if v.value_standard is not None],key=lambda x:x.timestamp_utc)
        slope=0.0
        if len(vals)>1:
            days=(vals[-1].timestamp_utc-vals[0].timestamp_utc).total_seconds()/86400
            slope=(vals[-1].value_standard-vals[0].value_standard)/days*365.25 if days else 0
        results.append({"station_id":station,"sample_count":len(vals),"annual_slope":slope,"period_start":vals[0].timestamp_utc if vals else None,"period_end":vals[-1].timestamp_utc if vals else None,"status":"ANALYSIS"})
    return {"variable_code":variable_code.upper(),"results":results,"status":"ANALYSIS_ONLY","is_demo":False}

def _score(bad: int, suspect: int, total: int) -> float:
    if not total: return 0.0
    return round(min(100.0, (bad * 1.0 + suspect * 0.5) / total * 100), 1)

def _recommendation(score: float) -> str:
    if score >= 70: return "재학습 우선 검토"
    if score >= 40: return "원인 확인 권고"
    return "관찰"

@router.get("/summary")
def insights_summary(station_id: Optional[str] = None, db: Session = Depends(get_db)):
    stations = db.query(StationMetadata).filter(StationMetadata.station_id == station_id).all() if station_id else db.query(StationMetadata).all()
    qc = db.query(QCFlagHistory).all()
    labels = db.query(AILabel).all()
    predictions = db.query(AIPredictionResult).all()
    rules = db.query(QCRuleResult).all()
    operations = db.query(OperationLog).all()
    if station_id:
        qc = [x for x in qc if x.station_id == station_id]
        labels = [x for x in labels if x.station_id == station_id]
        predictions = [x for x in predictions if x.station_id == station_id]
        rules = [x for x in rules if x.station_id == station_id]
        operations = [x for x in operations if x.station_id == station_id]

    station_stats = defaultdict(lambda: Counter())
    variable_stats = defaultdict(lambda: Counter())
    for row in qc:
        key = row.station_id
        station_stats[key]["total"] += 1; station_stats[key][str(row.qc_flag_final)] += 1
        variable_stats[row.variable_code or "UNKNOWN"]["total"] += 1; variable_stats[row.variable_code or "UNKNOWN"][str(row.qc_flag_final)] += 1
    for row in labels:
        station_stats[row.station_id]["labels"] += 1
        variable_stats[row.variable_code or "UNKNOWN"]["labels"] += 1
    for row in predictions:
        station_stats[row.station_id]["anomalies"] += int(row.recommended_flag in ("BAD", "SUSPECT"))
        variable_stats[row.variable_code or "UNKNOWN"]["anomalies"] += int(row.recommended_flag in ("BAD", "SUSPECT"))

    station_quality_risk = []
    for station in stations:
        stat = station_stats[station.station_id]
        total = stat["total"] or stat["labels"] or 0
        score = _score(stat["4"], stat["3"], total) + min(20, stat["anomalies"] * 2)
        score = round(min(100, score), 1)
        station_quality_risk.append({"station_id": station.station_id, "station_name": station.station_name, "risk_score": score, "status": "ANALYSIS", "recommendation": _recommendation(score)})
    station_quality_risk.sort(key=lambda x: x["risk_score"], reverse=True)

    variable_quality_score = []
    for variable, stat in variable_stats.items():
        total = stat["total"] or stat["labels"]
        risk = _score(stat["4"], stat["3"], total) + min(20, stat["anomalies"] * 2)
        variable_quality_score.append({"variable_code": variable, "quality_score": round(max(0, 100 - min(100, risk)), 1), "risk_score": round(min(100, risk), 1), "status": "ANALYSIS"})
    variable_quality_score.sort(key=lambda x: x["risk_score"], reverse=True)

    pattern_counts = Counter()
    for row in predictions:
        if row.recommended_flag in ("BAD", "SUSPECT") and row.timestamp_utc:
            pattern_counts[(row.station_id, row.variable_code or "UNKNOWN", row.timestamp_utc.hour)] += 1
    recurring_patterns = [{"station_id": s, "variable_code": v, "hour_utc": h, "occurrences": n, "status": "ANALYSIS"} for (s, v, h), n in pattern_counts.most_common(20) if n >= 2]

    sensor_candidates = [{"station_id": x.station_id, "sensor_id": x.sensor_id, "variable_code": x.variable_code, "evidence": x.error_cause, "confidence": x.label_confidence, "status": "CANDIDATE"} for x in labels if x.error_cause == "sensor_degradation"]
    communication_counts = Counter((x.station_id, x.sensor_id) for x in operations if "COMMUNICATION" in (x.event_type or "").upper() or "통신" in (x.event_type or ""))
    repeated_communication = [{"station_id": s, "sensor_id": sensor, "occurrences": n, "status": "ANALYSIS"} for (s, sensor), n in communication_counts.items() if n >= 2]
    false_positive_counts = Counter(x.station_id for x in labels if x.error_cause == "qc_algorithm_error")
    repeated_false_positive = [{"station_id": s, "occurrences": n, "status": "ANALYSIS"} for s, n in false_positive_counts.items() if n >= 2]

    trend = Counter()
    for row in qc:
        if row.timestamp_utc: trend[row.timestamp_utc.date().isoformat()] += int(str(row.qc_flag_final) in ("3", "4"))
    quality_trend = [{"date": day, "issue_count": count, "status": "ANALYSIS"} for day, count in sorted(trend.items())]

    priorities = []
    for item in station_quality_risk:
        evidence = ["station_risk"]
        if any(x["station_id"] == item["station_id"] for x in sensor_candidates): evidence.append("sensor_degradation_candidate")
        if any(x["station_id"] == item["station_id"] for x in repeated_communication): evidence.append("repeated_communication_failure")
        if any(x["station_id"] == item["station_id"] for x in repeated_false_positive): evidence.append("repeated_qc_false_positive")
        if item["risk_score"] > 0 or len(evidence) > 1:
            priorities.append({"station_id": item["station_id"], "priority_score": item["risk_score"], "evidence": evidence, "status": "RECOMMENDATION"})

    return {"status": "ANALYSIS_ONLY", "station_quality_risk": station_quality_risk, "variable_quality_score": variable_quality_score, "recurring_anomaly_pattern": recurring_patterns, "sensor_degradation_candidate": sensor_candidates, "repeated_communication_failure": repeated_communication, "repeated_qc_false_positive": repeated_false_positive, "quality_trend": quality_trend, "retraining_priority": priorities}
