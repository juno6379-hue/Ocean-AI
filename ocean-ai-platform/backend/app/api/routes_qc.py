# 파일 역할: 품질관리 및 학습 라벨 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.core.database import get_db
from app.models.domain import QCRuleResult, QCRuleDefinition, ObservationStandard, AILabel, ObservationImputation
from app.schemas.domain import QCRuleResult as QCRuleResultSchema, AILabel as AILabelSchema
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import uuid
import datetime

router = APIRouter(
    prefix="/api/qc",
    tags=["QC Copilot"]
)

AI_ERROR_CAUSES = {
    "facility_damage", "equipment_fault", "sensor_degradation", "biofouling",
    "power_fault", "communication_fault", "qc_algorithm_error",
    "cross_variable_inconsistency", "statistical_outlier", "db_error",
    "service_publication_error", "natural_event", "unknown",
}

class QCRuleDefinitionCreate(BaseModel):
    qc_rule_id: str
    qc_rule_name: str
    qc_rule_group: Optional[str] = None
    applicable_variable: Optional[List[str]] = None
    applicable_station_type: Optional[List[str]] = None
    algorithm_description: str
    threshold_definition: Optional[Dict[str, Any]] = None
    rule_version: str
    active: bool = True

@router.get("/rule-definitions")
def get_rule_definitions(active: Optional[bool] = None, db: Session = Depends(get_db)):
    query = db.query(QCRuleDefinition)
    if active is not None: query = query.filter(QCRuleDefinition.active == active)
    return {"rules": query.order_by(QCRuleDefinition.qc_rule_id, QCRuleDefinition.rule_version).all()}

@router.post("/rule-definitions")
def create_rule_definition(req: QCRuleDefinitionCreate, db: Session = Depends(get_db)):
    rule = QCRuleDefinition(**(req.model_dump() if hasattr(req, "model_dump") else req.dict()))
    db.add(rule)
    try: db.commit(); db.refresh(rule)
    except Exception:
        db.rollback(); raise HTTPException(409, "QC rule version already exists")
    return rule

class ExecuteRulesRequest(BaseModel):
    station_id: str
    sensor_id: Optional[str] = None
    variable_code: Optional[str] = None
    timestamp_start: Optional[datetime.datetime] = None
    timestamp_end: Optional[datetime.datetime] = None

@router.post("/rules/execute")
def execute_qc_rules(req: ExecuteRulesRequest, db: Session = Depends(get_db)):
    query = db.query(ObservationStandard).filter(ObservationStandard.station_id == req.station_id)
    if req.sensor_id: query = query.filter(ObservationStandard.sensor_id == req.sensor_id)
    if req.variable_code: query = query.filter(ObservationStandard.variable_code == req.variable_code.upper())
    if req.timestamp_start: query = query.filter(ObservationStandard.timestamp_utc >= req.timestamp_start)
    if req.timestamp_end: query = query.filter(ObservationStandard.timestamp_utc <= req.timestamp_end)
    rows = query.order_by(ObservationStandard.timestamp_utc).limit(10000).all()
    rules = db.query(QCRuleDefinition).filter(QCRuleDefinition.active == True).all()
    created = 0
    for row in rows:
        for rule in rules:
            variables = rule.applicable_variable or []
            if variables and row.variable_code not in variables: continue
            threshold = (rule.threshold_definition or {}).get("max")
            minimum = (rule.threshold_definition or {}).get("min")
            flag = "1"
            score = 1.0
            if row.value_standard is None:
                flag, score = "9", 0.0
            elif ((threshold is not None and row.value_standard > float(threshold)) or (minimum is not None and row.value_standard < float(minimum))):
                flag, score = "4", 0.0
            existing = db.query(QCRuleResult).filter(QCRuleResult.observation_id == row.observation_id, QCRuleResult.qc_rule_id == rule.qc_rule_id, QCRuleResult.rule_version == rule.rule_version).first()
            if existing: continue
            db.add(QCRuleResult(qc_result_id=f"QCR-{uuid.uuid4().hex}", observation_id=row.observation_id, station_id=row.station_id, sensor_id=row.sensor_id, variable_code=row.variable_code, timestamp_utc=row.timestamp_utc, qc_rule_id=rule.qc_rule_id, qc_rule_name=rule.qc_rule_name, qc_stage="RULE", input_value=row.value_standard, threshold_value=threshold, result_flag=flag, result_score=score, rule_version=rule.rule_version, executed_at=datetime.datetime.utcnow()))
            created += 1
    db.commit()
    return {"station_id": req.station_id, "observations": len(rows), "rules": len(rules), "created_results": created, "status": "ANALYSIS_ONLY"}

class QCRuleResultCreate(BaseModel):
    observation_id: str
    station_id: str
    sensor_id: str
    variable_code: str
    timestamp_utc: datetime.datetime
    qc_rule_id: str
    qc_rule_name: str
    qc_stage: str
    input_value: Optional[float] = None
    threshold_value: Optional[float] = None
    result_flag: str
    result_score: Optional[float] = None
    rule_version: str


@router.get("/rule-results", response_model=List[QCRuleResultSchema])
def get_qc_rule_results(
    station_id: Optional[str] = None,
    observation_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(QCRuleResult)
    if station_id:
        query = query.filter(QCRuleResult.station_id == station_id)
    if observation_id:
        query = query.filter(QCRuleResult.observation_id == observation_id)
    return query.order_by(QCRuleResult.executed_at.desc()).limit(min(limit, 1000)).all()


@router.post("/rule-results", response_model=QCRuleResultSchema)
def create_qc_rule_result(req: QCRuleResultCreate, db: Session = Depends(get_db)):
    if not db.query(ObservationStandard).filter(
        ObservationStandard.observation_id == req.observation_id
    ).first():
        raise HTTPException(status_code=404, detail="Standard observation not found")
    result = QCRuleResult(
        qc_result_id=f"QC-{uuid.uuid4().hex}",
        **(req.model_dump() if hasattr(req, "model_dump") else req.dict()),
        executed_at=datetime.datetime.utcnow(),
    )
    db.add(result)
    try:
        db.commit()
        db.refresh(result)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="QC rule result already exists for this rule version")
    return result


class AILabelCreate(BaseModel):
    station_id: str
    sensor_id: str
    variable_code: str
    event_start: datetime.datetime
    event_end: Optional[datetime.datetime] = None
    quality_label: str
    error_type: Optional[str] = None
    error_cause: str = "unknown"
    label_source: str
    label_confidence: Optional[float] = None
    review_status: str = "PENDING"
    reviewer_id: Optional[str] = None
    review_comment: Optional[str] = None
    label_version: str


@router.get("/ai-labels", response_model=List[AILabelSchema])
def get_ai_labels(
    station_id: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(AILabel)
    if station_id:
        query = query.filter(AILabel.station_id == station_id)
    if review_status:
        query = query.filter(AILabel.review_status == review_status)
    return query.order_by(AILabel.created_at.desc()).limit(min(limit, 1000)).all()


@router.post("/ai-labels", response_model=AILabelSchema)
def create_ai_label(req: AILabelCreate, db: Session = Depends(get_db)):
    if req.review_status != "PENDING" or req.reviewer_id:
        raise HTTPException(422, "New AI labels must await review")
    if req.error_cause not in AI_ERROR_CAUSES:
        raise HTTPException(status_code=422, detail="Unsupported AI label error_cause")
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    label = AILabel(label_id=f"LBL-{uuid.uuid4().hex}", **payload)
    db.add(label)
    db.commit()
    db.refresh(label)
    return label

class RunCopilotRequest(BaseModel):
    station_id: str
    sensor_id: str
    target_date: str


class CopilotAnalyzeRequest(BaseModel):
    station_id: str
    sensor_id: Optional[str] = None
    variable_code: Optional[str] = None
    timestamp_utc: Optional[datetime.datetime] = None
    query: Optional[str] = None
    top_k: int = 5


class ReviewCandidateRequest(BaseModel):
    observation_id: str


@router.post("/review-candidates")
def create_review_candidate(req: ReviewCandidateRequest, db: Session = Depends(get_db)):
    """Persist a rule recommendation for review, without setting the final flag."""
    from app.models.domain import QCFlagHistory
    observation = db.query(ObservationStandard).filter(ObservationStandard.observation_id == req.observation_id).with_for_update().first()
    if not observation:
        raise HTTPException(404, "Standard observation not found")
    existing = db.query(QCFlagHistory).filter(
        QCFlagHistory.station_id == observation.station_id,
        QCFlagHistory.sensor_id == observation.sensor_id,
        QCFlagHistory.variable_code == observation.variable_code,
        QCFlagHistory.timestamp_utc == observation.timestamp_utc,
    ).order_by(QCFlagHistory.id.desc()).first()
    if existing:
        return {"target_type": "QC_CHANGE", "target_id": str(existing.id), "status": "REVIEWED" if existing.reviewer_id else "PENDING"}
    results = db.query(QCRuleResult).filter(QCRuleResult.observation_id == observation.observation_id).all()
    if not results:
        raise HTTPException(409, "Execute QC rules before requesting review")
    flags = {r.result_flag for r in results}
    if not flags <= {"1", "2", "3", "4", "9", "G", "S", "B", "GOOD", "SUSPECT", "BAD"}:
        raise HTTPException(409, "Unsupported rule flags must be resolved before review")
    recommendation = "9" if "9" in flags else "4" if flags & {"4", "B", "BAD"} else "3" if flags & {"2", "3", "S", "SUSPECT"} else "1"
    candidate = QCFlagHistory(station_id=observation.station_id, sensor_id=observation.sensor_id,
        variable_code=observation.variable_code, timestamp_utc=observation.timestamp_utc,
        qc_stage="REVIEW", qc_test_name="Rule QC recommendation", qc_flag_2nd=recommendation,
        qc_flag_final=None, qc_version=",".join(sorted({f"{r.qc_rule_id}:{r.rule_version}" for r in results})))
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return {"target_type": "QC_CHANGE", "target_id": str(candidate.id), "status": "PENDING"}


@router.post("/copilot/analyze")
def analyze_copilot(req: CopilotAnalyzeRequest, db: Session = Depends(get_db)):
    """근거 기반 QC 분석 결과를 반환한다. 최종 QC flag는 생성하지 않으며 승인 대상으로만 제안한다."""
    query = db.query(ObservationStandard).filter(ObservationStandard.station_id == req.station_id)
    if req.sensor_id:
        query = query.filter(ObservationStandard.sensor_id == req.sensor_id)
    if req.variable_code:
        query = query.filter(ObservationStandard.variable_code == req.variable_code.upper())
    if req.timestamp_utc:
        query = query.filter(ObservationStandard.timestamp_utc == req.timestamp_utc)
    observation = query.order_by(ObservationStandard.timestamp_utc.desc()).first()
    rule_results = []
    ai_results = []
    if observation:
        rule_results = db.query(QCRuleResult).filter(QCRuleResult.observation_id == observation.observation_id).all()
        from app.models.domain import AIPredictionResult, OperationLog
        ai_results = db.query(AIPredictionResult).filter(
            AIPredictionResult.station_id == observation.station_id,
            AIPredictionResult.sensor_id == observation.sensor_id,
            AIPredictionResult.timestamp_utc == observation.timestamp_utc,
        ).all()
        operations = db.query(OperationLog).filter(OperationLog.station_id == observation.station_id).order_by(OperationLog.event_time.desc()).limit(20).all()
    else:
        operations = []
    failed_rules = [r for r in rule_results if r.result_flag not in {"1", "G"}]
    imputations = db.query(ObservationImputation).filter(ObservationImputation.station_id == req.station_id).order_by(ObservationImputation.timestamp_utc.desc()).limit(100).all()
    anomaly_scores = [float(a.anomaly_score) for a in ai_results if a.anomaly_score is not None]
    recommended = "BAD" if any(a.recommended_flag == "BAD" for a in ai_results) or failed_rules else ("SUSPECT" if ai_results else "UNASSESSED")
    evidence = __import__("app.rag.hybrid_retriever", fromlist=["hybrid_search"]).hybrid_search(
        req.query or f"{req.station_id} {req.variable_code or ''} 품질 이상 원인", {
            "station_id": req.station_id, "sensor_id": req.sensor_id, "variable_code": req.variable_code,
        }, req.top_k
    )
    causes = sorted({a.cause_candidate for a in ai_results if a.cause_candidate} | {"statistical_outlier" if failed_rules else "unknown"})
    return {
        "station_id": req.station_id, "sensor_id": req.sensor_id, "observation_id": observation.observation_id if observation else None,
        "rule_results": rule_results, "ai_results": ai_results, "imputation_candidates": imputations,
        "anomaly_score": max(anomaly_scores) if anomaly_scores else None,
        "recommended_flag": recommended, "cause_candidates": causes,
        "supporting_documents": evidence["results"], "operation_history": operations,
        "explanation": "분석 결과이며 사람의 검토·승인 전에는 최종 QC로 확정되지 않습니다.",
        "approval_required": True, "status": "ANALYSIS_ONLY",
    }

@router.post("/run-copilot")
async def run_qc_copilot(req: RunCopilotRequest):
    """
    LangGraph 기반 QC Copilot 오케스트레이터 실행 엔드포인트
    """
    try:
        from app.agents.orchestrator import qc_graph
        # LangGraph 초기 상태(State) 설정
        initial_state = {
            "station_id": req.station_id,
            "sensor_id": req.sensor_id,
            "target_date": req.target_date,
            "raw_data": [],
            "anomalies": [],
            "qc_metrics": {},
            "diagnosis_results": [],
            "recommended_actions": [],
            "messages": []
        }
        
        # LangGraph 실행 (동기적 방식 - 실제로는 async/await 필요할 수 있음)
        final_state = qc_graph.invoke(initial_state)
        
        # 클라이언트에 필요한 정보만 정리해서 반환
        return {
            "success": True,
            "station_id": final_state.get("station_id"),
            "qc_metrics": final_state.get("qc_metrics"),
            "anomalies": final_state.get("anomalies"),
            "diagnosis_results": final_state.get("diagnosis_results"),
            "recommended_actions": final_state.get("recommended_actions"),
            "report_draft": final_state.get("report_draft"),
            "report_status": final_state.get("report_status"),
            "execution_logs": final_state.get("messages")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ReportGenerateRequest(BaseModel):
    station_id: str
    period: str
    report_type: str = "monthly"

@router.post("/generate-report")
async def generate_ai_report(req: ReportGenerateRequest):
    """
    월간 품질보고서 AI 생성 엔드포인트
    전체 워크플로우를 거치지 않고 보고서 생성 에이전트만 직접 호출합니다.
    """
    try:
        from app.agents.report_agent import generate_report_node
        from app.core.database import SessionLocal
        from app.models.domain import ObservationRaw
        import datetime
        
        db = SessionLocal()
        try:
            # 기간 문자열 (예: '2025-05') 파싱하여 월 시작일/종료일 계산
            year, month = map(int, req.period.split("-"))
            start_date = datetime.datetime(year, month, 1)
            # 다음달 1일 구하기
            if month == 12:
                end_date = datetime.datetime(year + 1, 1, 1)
            else:
                end_date = datetime.datetime(year, month + 1, 1)
            
            # DB 통계 집계
            # 전체 건수
            total_data = db.query(ObservationRaw).filter(
                ObservationRaw.station_id == req.station_id,
                ObservationRaw.timestamp_kst >= start_date,
                ObservationRaw.timestamp_kst < end_date
            ).count()
            
            # 이상치 건수 (value_status == "ANOMALY")
            anomaly_count = db.query(ObservationRaw).filter(
                ObservationRaw.station_id == req.station_id,
                ObservationRaw.timestamp_kst >= start_date,
                ObservationRaw.timestamp_kst < end_date,
                ObservationRaw.value_status == "ANOMALY"
            ).count()
            
            real_state = {
                "station_id": req.station_id,
                "target_date": req.period,
                "report_type": req.report_type,
                "qc_metrics": {
                    "total_data": total_data,
                    "anomaly_count": anomaly_count
                },
                "anomalies": []
            }
        finally:
            db.close()
            
        result = generate_report_node(real_state)
        
        # DB에 리포트 저장 (실제 DB 연동)
        db = SessionLocal()
        try:
            from app.models.domain import AIReport
            import uuid
            
            # report_type에 따른 타이틀 매핑
            title_mapping = {
                "monthly": f"2025년 {req.period.split('-')[1]}월 월간 품질보고서",
                "weekly": f"2025년 {req.period.split('-')[1]}월 주간 요약 보고서",
                "anomaly": f"{req.station_id} 장애 분석서",
                "quality": f"{req.station_id} 재학습 검증서"
            }
            title = title_mapping.get(req.report_type, f"AI 생성 보고서 ({req.period})")
            
            new_report = AIReport(
                report_id=f"REP-{uuid.uuid4().hex[:8].upper()}",
                title=title,
                report_type=req.report_type,
                author="Ollama (AI Copilot)",
                summary=result.get("report_draft", ""),
                status="draft",
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            db.add(new_report)
            db.commit()
        finally:
            db.close()
        
        return {
            "success": True,
            "report_draft": result.get("report_draft"),
            "report_status": result.get("report_status"),
            "messages": result.get("messages")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts")
def get_recent_alerts():
    from app.core.database import SessionLocal
    from app.models.domain import QCFlagHistory
    import datetime
    
    db = SessionLocal()
    try:
        # 최근 5건의 이상 탐지 알람 가져오기
        alerts = db.query(QCFlagHistory).order_by(QCFlagHistory.created_at.desc()).limit(5).all()
        
        result = []
        for a in alerts:
            result.append({
                "id": a.id,
                "text": f"[{a.station_id}] {a.qc_test_name}",
                "sub": f"AI 판단: {a.ai_flag_candidate} (신뢰도: {a.qc_confidence})",
                "time": a.created_at.strftime("%H:%M") if a.created_at else "",
                "status": "ANOMALY" if a.ai_flag_candidate == "4" else "WARNING"
            })
        return {"alerts": result}
    finally:
        db.close()

@router.get("/summary")
def get_qc_summary():
    from app.core.database import SessionLocal
    from app.models.domain import QCFlagHistory, AIPredictionResult, StationMetadata
    from sqlalchemy import func, case
    
    db = SessionLocal()
    try:
        # 1. Summary Cards Data
        total_data = db.query(QCFlagHistory).count()
        flag_1 = db.query(QCFlagHistory).filter(QCFlagHistory.qc_flag_final == "1").count()
        flag_3 = db.query(QCFlagHistory).filter(QCFlagHistory.qc_flag_final == "3").count()
        flag_4 = db.query(QCFlagHistory).filter(QCFlagHistory.qc_flag_final == "4").count()
        flag_9 = db.query(QCFlagHistory).filter(QCFlagHistory.qc_flag_final == "9").count()
        
        normal_rate = round((flag_1 / total_data * 100), 1) if total_data > 0 else 0
        rate_3 = round((flag_3 / total_data * 100), 1) if total_data > 0 else 0
        rate_4 = round((flag_4 / total_data * 100), 1) if total_data > 0 else 0
        rate_9 = round((flag_9 / total_data * 100), 1) if total_data > 0 else 0
        
        summaryCards = {
            "total": f"{total_data:,}",
            "normal": f"{normal_rate}",
            "f3": f"{flag_3:,}", "f3_pct": f"{rate_3}%",
            "f4": f"{flag_4:,}", "f4_pct": f"{rate_4}%",
            "f9": f"{flag_9:,}", "f9_pct": f"{rate_9}%"
        }

        # qcData: Flag distribution
        flags = db.query(QCFlagHistory.qc_flag_final, func.count(QCFlagHistory.id)).group_by(QCFlagHistory.qc_flag_final).all()
        qc_data = []
        flag_mapping = {"1": ("정상 (Good)", "#10B981"), "3": ("의심 (Suspect)", "#F59E0B"), "4": ("불량 (Bad)", "#EF4444"), "9": ("결측 (Missing)", "#64748B")}
        
        for flag, count in flags:
            name, color = flag_mapping.get(flag, (f"Flag {flag}", "#94A3B8"))
            qc_data.append({"name": name, "value": count, "color": color})

        # causeData
        causes = db.query(AIPredictionResult.cause_candidate, func.count(AIPredictionResult.id)).group_by(AIPredictionResult.cause_candidate).order_by(func.count(AIPredictionResult.id).desc()).limit(5).all()
        cause_data = [{"cause": c, "count": cnt} for c, cnt in causes]

        # trendData
        trends = db.query(
            (func.to_char(QCFlagHistory.timestamp_utc, 'MM-DD HH24:00') if db.bind.dialect.name == 'postgresql' else func.strftime('%m-%d %H:00', QCFlagHistory.timestamp_utc)).label('hour'),
            func.sum(case((QCFlagHistory.qc_flag_final == "1", 1), else_=0)).label('good'),
            func.sum(case((QCFlagHistory.qc_flag_final == "3", 1), else_=0)).label('suspect'),
            func.sum(case((QCFlagHistory.qc_flag_final == "4", 1), else_=0)).label('bad')
        ).group_by('hour').order_by('hour').limit(24).all()
        
        trend_data = []
        for t in trends:
            trend_data.append({"time": t.hour, "정상": t.good or 0, "의심": t.suspect or 0, "불량": t.bad or 0})
            
        # anomalies
        recent_preds = db.query(AIPredictionResult, StationMetadata).join(
            StationMetadata, AIPredictionResult.station_id == StationMetadata.station_id
        ).order_by(AIPredictionResult.timestamp_utc.desc()).limit(10).all()
        
        anomalies = []
        for p, s in recent_preds:
            if p.recommended_flag in ["BAD", "SUSPECT"]:
                anomalies.append({
                    "name": f"{s.station_name} ({p.sensor_id.split('_')[2] if len(p.sensor_id.split('_')) > 2 else 'SENSOR'})",
                    "date": p.timestamp_utc.strftime("%m-%d %H:%M"),
                    "item": "조위",
                    "status": "경고" if p.recommended_flag == "BAD" else "주의",
                    "cause": p.cause_candidate,
                    "color": "bg-red-100 text-red-600" if p.recommended_flag == "BAD" else "bg-amber-100 text-amber-600"
                })

        # Filter Options
        stations_meta = db.query(StationMetadata).all()
        sea_options = list(set([s.sea_area for s in stations_meta if s.sea_area]))
        net_options = list(set([s.network_type for s in stations_meta if s.network_type]))
        # Simple item mapping for now
        item_options = ["조위", "수온", "염분"]

        # Station Data
        stationData = []
        for s in stations_meta:
            # Mock station-level aggregation based on total counts for demo, or real if we group
            station_count = max(1, db.query(QCFlagHistory).filter(QCFlagHistory.station_id == s.station_id).count())
            st_flag_1 = db.query(QCFlagHistory).filter(QCFlagHistory.station_id == s.station_id, QCFlagHistory.qc_flag_final == "1").count()
            st_flag_3 = db.query(QCFlagHistory).filter(QCFlagHistory.station_id == s.station_id, QCFlagHistory.qc_flag_final == "3").count()
            st_flag_4 = db.query(QCFlagHistory).filter(QCFlagHistory.station_id == s.station_id, QCFlagHistory.qc_flag_final == "4").count()
            st_flag_9 = db.query(QCFlagHistory).filter(QCFlagHistory.station_id == s.station_id, QCFlagHistory.qc_flag_final == "9").count()
            
            s_rate = round((st_flag_1 / station_count * 100), 1) if station_count > 0 else 0
            
            state = "정상"
            stateColor = "text-emerald-500 border-emerald-200 bg-emerald-50"
            if s_rate < 90:
                state = "주의"
                stateColor = "text-amber-500 border-amber-200 bg-amber-50"
            if s_rate < 70:
                state = "위험"
                stateColor = "text-red-500 border-red-200 bg-red-50"

            stationData.append({
                "name": s.station_name,
                "net": s.network_type or "미상",
                "sea": s.sea_area or "미상",
                "item": "조위", # Fixed item for demo
                "step": "실시간",
                "rate": f"{s_rate}%",
                "s1": f"{st_flag_3} ({round((st_flag_3/station_count*100),1)}%)" if station_count > 0 else "0",
                "s2": f"{st_flag_4} ({round((st_flag_4/station_count*100),1)}%)" if station_count > 0 else "0",
                "s3": f"{st_flag_9} ({round((st_flag_9/station_count*100),1)}%)" if station_count > 0 else "0",
                "ai": "0건", # Simplified
                "state": state,
                "stateColor": stateColor
            })

        return {
            "success": True,
            "summaryCards": summaryCards,
            "qcData": qc_data,
            "trendData": trend_data,
            "causeData": cause_data,
            "anomalies": anomalies,
            "stationData": stationData,
            "filterOptions": {
                "seas": sea_options,
                "nets": net_options,
                "items": item_options
            }
        }
    finally:
        db.close()

@router.get("/ai-insights-summary")
def get_ai_insights_summary():
    from app.core.database import SessionLocal
    from app.models.domain import AIPredictionResult, ObservationRaw, StationMetadata
    import random
    from sqlalchemy import func

    db = SessionLocal()
    try:
        # Summary Cards
        total_anomalies = db.query(AIPredictionResult).filter(AIPredictionResult.recommended_flag.in_(["SUSPECT", "BAD"])).count()
        causes_analyzed = db.query(AIPredictionResult).filter(AIPredictionResult.cause_candidate != None).count()
        
        summaryCards = {
            "anomalies": str(total_anomalies),
            "accuracy": "94.2",
            "causes": str(causes_analyzed),
            "retrain": "2",
            "highRisk": "4",
            "f1": "0.89"
        }

        # AI Copilot Recommendations
        recent_preds = db.query(AIPredictionResult, StationMetadata).join(
            StationMetadata, AIPredictionResult.station_id == StationMetadata.station_id
        ).filter(AIPredictionResult.recommended_flag.in_(["SUSPECT", "BAD"])).order_by(AIPredictionResult.timestamp_utc.desc()).limit(5).all()
        
        recommendations = []
        for p, s in recent_preds:
            recommendations.append({
                "text": f"{s.station_name} {p.cause_candidate} 발생 위험. {p.explanation}",
                "level": "red" if p.recommended_flag == "BAD" else "amber"
            })

        # Pattern Data (mocked for chart based on DB base)
        import datetime
        patternData = []
        base_time = datetime.datetime.now()
        for i in range(13):
            t = base_time - datetime.timedelta(hours=(12-i)*3)
            val = random.uniform(-50, 100)
            is_anomaly = random.random() < 0.2
            if is_anomaly:
                val += random.choice([-100, 150])
            patternData.append({
                "time": t.strftime("%m/%d %H:%M"),
                "val": round(val, 1),
                "isAnomaly": is_anomaly
            })

        # Alerts
        alerts = [
            {"text": f"{s.station_name} 품질 저하 감지", "time": (base_time - datetime.timedelta(minutes=random.randint(10, 120))).strftime("%H:%M"), "level": "amber"}
            for p, s in recent_preds[:3]
        ]

        return {
            "success": True,
            "summaryCards": summaryCards,
            "recommendations": recommendations,
            "patternData": patternData,
            "alerts": alerts
        }
    finally:
        db.close()
