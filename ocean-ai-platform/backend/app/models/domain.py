# 파일 역할: 관측·품질검사·라벨·문서·모델 등의 관계형 저장 구조를 정의합니다.
from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, ForeignKey, Boolean, Text, JSON, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import func
import datetime
from app.core.database import Base
from app.models.evidence import SensorAlias, EventEvidence, LabelReviewSnapshot, FeatureProvenance, DatasetMembership

class StationMetadata(Base):
    __tablename__ = "station_metadata"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String, unique=True, index=True, nullable=False) # e.g. DT_0001
    station_name = Column(String, nullable=False)
    network_type = Column(String)
    sea_area = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    datum_info = Column(String)
    install_date = Column(DateTime)
    status = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class SensorMetadata(Base):
    __tablename__ = "sensor_metadata"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String, ForeignKey("station_metadata.station_id"), index=True)
    sensor_id = Column(String, unique=True, index=True, nullable=False) # e.g. TIDE_LEVEL_VEGA
    sensor_type = Column(String)
    manufacturer = Column(String)
    variable_code = Column(String)
    install_date = Column(DateTime)
    calibration_date = Column(DateTime)
    replacement_date = Column(DateTime)
    status = Column(String)

class ObservationRaw(Base):
    __tablename__ = "observation_raw"
    __table_args__ = (
        UniqueConstraint(
            "station_id",
            "sensor_id",
            "variable_code",
            "timestamp_utc",
            name="uq_observation_raw_natural_key",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String, index=True, nullable=False)
    sensor_id = Column(String, index=True, nullable=False)
    timestamp_kst = Column(DateTime, index=True)
    timestamp_utc = Column(DateTime, index=True)
    variable_code = Column(String)
    value_raw = Column(Float)
    value_unit = Column(String)
    source_system = Column(String)
    ingest_time = Column(DateTime, server_default=func.now())
    value_status = Column(String)
    qc_flag = Column(String)
    mqc_flag = Column(String)
    water_step = Column(Float)
    from_depth = Column(Float)
    to_depth = Column(Float)
    receive_time = Column(DateTime)
    source_item_code = Column(String, index=True)


class ObservationStandard(Base):
    """단위·변수 코드 표준화가 완료된 관측값 저장소."""
    __tablename__ = "observation_standard"
    __table_args__ = (
        UniqueConstraint(
            "station_id",
            "sensor_id",
            "variable_code",
            "timestamp_utc",
            name="uq_observation_standard_natural_key",
        ),
    )

    observation_id = Column(String(128), primary_key=True)
    station_id = Column(String, index=True, nullable=False)
    sensor_id = Column(String, index=True, nullable=False)
    variable_code = Column(String, index=True, nullable=False)
    timestamp_utc = Column(DateTime, index=True, nullable=False)
    value_raw = Column(Float)
    value_standard = Column(Float)
    source_unit = Column(String)
    standard_unit = Column(String)
    conversion_rule = Column(String)
    standardization_version = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    qc_flag = Column(String)
    mqc_flag = Column(String)
    water_step = Column(Float)
    from_depth = Column(Float)
    to_depth = Column(Float)
    receive_time = Column(DateTime)
    source_item_code = Column(String, index=True)

class MDCItemMapping(Base):
    __tablename__ = "mdc_item_mapping"
    id = Column(Integer, primary_key=True)
    source_item_code = Column(String, unique=True, nullable=False, index=True)
    standard_variable_code = Column(String, nullable=False, index=True)
    standard_unit = Column(String)
    sensor_type = Column(String)
    network_type = Column(String)
    active = Column(Boolean, default=True)
    mapping_version = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class ObservationImputation(Base):
    __tablename__ = "observation_imputation"
    imputation_id = Column(String(128), primary_key=True)
    station_id = Column(String, index=True, nullable=False)
    sensor_id = Column(String, index=True, nullable=False)
    variable_code = Column(String, index=True, nullable=False)
    timestamp_utc = Column(DateTime, index=True, nullable=False)
    value_imputed = Column(Float)
    method = Column(String, nullable=False)
    confidence = Column(Float)
    gap_length = Column(Integer)
    model_version = Column(String, nullable=False)
    source_observation_before = Column(String)
    source_observation_after = Column(String)
    approval_status = Column(String, default="PENDING")
    created_at = Column(DateTime, server_default=func.now())


class QCRuleResult(Base):
    """관측값에 적용된 개별 QC 규칙의 판정 결과."""
    __tablename__ = "qc_rule_result"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "qc_rule_id",
            "rule_version",
            name="uq_qc_rule_result_observation_rule_version",
        ),
    )

    qc_result_id = Column(String(128), primary_key=True)
    observation_id = Column(String(128), ForeignKey("observation_standard.observation_id"), index=True, nullable=False)
    station_id = Column(String, index=True, nullable=False)
    sensor_id = Column(String, index=True, nullable=False)
    variable_code = Column(String, index=True, nullable=False)
    timestamp_utc = Column(DateTime, index=True, nullable=False)
    qc_rule_id = Column(String, index=True, nullable=False)
    qc_rule_name = Column(String, nullable=False)
    qc_stage = Column(String, nullable=False)
    input_value = Column(Float)
    threshold_value = Column(Float)
    result_flag = Column(String, nullable=False)
    result_score = Column(Float)
    rule_version = Column(String, nullable=False)
    executed_at = Column(DateTime, nullable=False, server_default=func.now())


class QCRuleDefinition(Base):
    __tablename__ = "qc_rule_definition"
    __table_args__ = (UniqueConstraint("qc_rule_id", "rule_version", name="uq_qc_rule_definition_version"),)
    qc_rule_id = Column(String(128), primary_key=True)
    qc_rule_name = Column(String, nullable=False)
    qc_rule_group = Column(String)
    applicable_variable = Column(JSON)
    applicable_station_type = Column(JSON)
    algorithm_description = Column(Text, nullable=False)
    threshold_definition = Column(JSON)
    rule_version = Column(String, primary_key=True)
    active = Column(Boolean, nullable=False, default=True)


class AILabel(Base):
    """QC 판정과 분리된 AI 학습용 사건·원인 라벨."""
    __tablename__ = "ai_label"
    __table_args__ = (
        CheckConstraint(
            "error_cause IN ('facility_damage','equipment_fault','sensor_degradation',"
            "'biofouling','power_fault','communication_fault','qc_algorithm_error',"
            "'cross_variable_inconsistency','statistical_outlier','db_error',"
            "'service_publication_error','natural_event','unknown')",
            name="ck_ai_label_error_cause",
        ),
    )

    label_id = Column(String(128), primary_key=True)
    station_id = Column(String, index=True, nullable=False)
    sensor_id = Column(String, index=True, nullable=False)
    variable_code = Column(String, index=True, nullable=False)
    event_start = Column(DateTime, nullable=False)
    event_end = Column(DateTime)
    quality_label = Column(String, nullable=False)
    error_type = Column(String)
    error_cause = Column(String, nullable=False, default="unknown")
    label_source = Column(String, nullable=False)
    label_confidence = Column(Float)
    review_status = Column(String, nullable=False, default="PENDING")
    reviewer_id = Column(String)
    review_comment = Column(Text)
    label_version = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RetrainingPool(Base):
    """검토 완료된 AI Label/QC 사건을 다음 학습 데이터 후보로 관리한다."""
    __tablename__ = "retraining_pool"

    pool_id = Column(String(128), primary_key=True)
    source_type = Column(String, nullable=False)
    source_id = Column(String, nullable=False, index=True)
    station_id = Column(String, index=True)
    sensor_id = Column(String)
    variable_code = Column(String)
    label_id = Column(String, ForeignKey("ai_label.label_id"), nullable=True)
    pool_status = Column(String, nullable=False, default="PENDING")
    added_by = Column(String, nullable=False)
    reviewed_at = Column(DateTime)
    metadata_json = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())


class FeatureDefinition(Base):
    """학습 Feature의 의미·계산식·버전을 관리한다."""
    __tablename__ = "feature_definition"
    __table_args__ = (
        UniqueConstraint("feature_id", "feature_version", name="uq_feature_definition_version"),
        CheckConstraint(
            "feature_group IN ('Raw Feature','Rule QC Feature','Temporal Feature',"
            "'Spatial Feature','Metadata Feature','Operation Feature','Event Feature')",
            name="ck_feature_definition_group",
        ),
    )

    feature_id = Column(String(128), primary_key=True)
    feature_name = Column(String, nullable=False)
    feature_group = Column(String, nullable=False)
    description = Column(Text)
    calculation_logic = Column(Text, nullable=False)
    source_fields = Column(JSON, nullable=False)
    window_size = Column(String)
    feature_version = Column(String, primary_key=True)
    created_at = Column(DateTime, server_default=func.now())


class FeatureValue(Base):
    """관측소·시각별로 계산된 Feature 값."""
    __tablename__ = "feature_value"
    __table_args__ = (
        UniqueConstraint(
            "station_id", "sensor_id", "variable_code", "timestamp_utc",
            "feature_id", "feature_version", name="uq_feature_value_key",
        ),
    )

    observation_id = Column(String, index=True)
    station_id = Column(String, primary_key=True)
    sensor_id = Column(String, primary_key=True)
    variable_code = Column(String, primary_key=True)
    timestamp_utc = Column(DateTime, primary_key=True)
    feature_id = Column(String, primary_key=True)
    feature_value = Column(Float)
    feature_version = Column(String, primary_key=True)


class DatasetRegistry(Base):
    """학습·검증 데이터셋의 범위와 버전을 기록한다."""
    __tablename__ = "dataset_registry"
    __table_args__ = (
        UniqueConstraint("dataset_name", "dataset_version", name="uq_dataset_registry_version"),
        CheckConstraint(
            "dataset_split IN ('TRAIN','VALIDATION','TEST','BLIND_TEST','RETRAINING_POOL')",
            name="ck_dataset_registry_split",
        ),
    )

    dataset_id = Column(String(128), primary_key=True)
    dataset_name = Column(String, nullable=False)
    dataset_version = Column(String, nullable=False)
    dataset_split = Column(String, nullable=False)
    station_scope = Column(JSON, nullable=False)
    sensor_scope = Column(JSON)
    variable_scope = Column(JSON, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    sample_count = Column(Integer, nullable=False, default=0)
    normal_count = Column(Integer, nullable=False, default=0)
    suspect_count = Column(Integer, nullable=False, default=0)
    bad_count = Column(Integer, nullable=False, default=0)
    missing_count = Column(Integer, nullable=False, default=0)
    feature_version = Column(String, nullable=False)
    label_version = Column(String, nullable=False)
    preprocessing_version = Column(String, nullable=False)
    qc_rule_version = Column(String)
    data_hash = Column(String)
    status = Column(String, default="DRAFT")
    created_by = Column(String)
    approved_by = Column(String)
    created_at = Column(DateTime, server_default=func.now())

class DataLakeStat(Base):
    __tablename__ = "data_lake_stat"
    id = Column(Integer, primary_key=True, index=True)
    lake_name = Column(String, index=True, nullable=False)
    partition_path = Column(String, nullable=False)
    station_id = Column(String, index=True)
    variable_code = Column(String, index=True, nullable=False)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    # A 20-year lake can exceed PostgreSQL's 32-bit integer range.
    row_count = Column(BigInteger, nullable=False, default=0)
    missing_count = Column(BigInteger, nullable=False, default=0)
    min_value = Column(Float)
    max_value = Column(Float)
    mean_value = Column(Float)
    qc_distribution = Column(JSON)
    source_file_count = Column(BigInteger, default=0)
    manifest_hash = Column(String)
    created_at = Column(DateTime, server_default=func.now())

class QCFlagHistory(Base):
    __tablename__ = "qc_flag_history"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String, index=True, nullable=False)
    sensor_id = Column(String, index=True, nullable=False)
    timestamp_utc = Column(DateTime, index=True)
    variable_code = Column(String)
    qc_stage = Column(String)
    qc_test_name = Column(String)
    qc_flag_1st = Column(String) # ì˜ˆ: OK
    qc_flag_2nd = Column(String) 
    qc_flag_final = Column(String) # ì˜ˆ: MQC_FLAG (G, S, B, 9 ë“±)
    ai_flag_candidate = Column(String) # ì˜ˆ: N1_AQC_FLAG
    qc_confidence = Column(Float)
    reviewer_id = Column(String)
    review_comment = Column(String)
    qc_version = Column(String)
    created_at = Column(DateTime, server_default=func.now())

class OperationLog(Base):
    __tablename__ = "operation_log"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String, index=True)
    sensor_id = Column(String)
    event_time = Column(DateTime, index=True)
    event_type = Column(String)
    event_detail = Column(Text)
    action_taken = Column(Text)
    operator = Column(String)
    related_document_id = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class EventRegistry(Base):
    __tablename__ = "event_registry"
    event_id = Column(String(128), primary_key=True)
    event_type = Column(String, nullable=False)
    station_id = Column(String, index=True)
    sensor_id = Column(String)
    variable_code = Column(String)
    event_start = Column(DateTime, nullable=False)
    event_end = Column(DateTime)
    severity = Column(String)
    source_type = Column(String)
    status = Column(String, default="OPEN")
    created_at = Column(DateTime, server_default=func.now())

class AIPredictionResult(Base):
    __tablename__ = "ai_prediction_result"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String, index=True)
    sensor_id = Column(String)
    timestamp_utc = Column(DateTime, index=True)
    variable_code = Column(String)
    model_id = Column(String)
    predicted_value = Column(Float)
    anomaly_score = Column(Float)
    recommended_flag = Column(String)
    confidence = Column(Float)
    cause_candidate = Column(String)
    explanation = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class DocumentIndex(Base):
    __tablename__ = "document_index"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(128), index=True, nullable=False)
    report_id = Column(String(128), index=True)
    chunk_id = Column(String(128), unique=True, index=True, nullable=False)
    document_type = Column(String, nullable=False)
    document_title = Column(String, nullable=False)
    document_date = Column(DateTime)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    related_station_id = Column(String)
    related_sensor_id = Column(String)
    related_variable_code = Column(String)
    event_id = Column(String, index=True)
    event_type = Column(String)
    error_type = Column(String)
    error_cause = Column(String)
    section_name = Column(String)
    page_no = Column(Integer)
    chunk_text = Column(Text)
    embedding_id = Column(String)
    embedding_model = Column(String)
    embedding_version = Column(String)
    parser_version = Column(String)
    metadata_json = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String)
    model_type = Column(String)
    model_version = Column(String, unique=True, index=True)
    dataset_version = Column(String)
    feature_version = Column(String)
    label_version = Column(String)
    preprocessing_version = Column(String)
    target_variable = Column(String)
    target_task = Column(String)
    training_data_start = Column(DateTime)
    training_data_end = Column(DateTime)
    station_scope = Column(String)
    sensor_scope = Column(String)
    metrics_json = Column(JSON)
    artifact_path = Column(String)
    status = Column(String)
    deployment_status = Column(String, default="CANDIDATE")
    deployment_stage = Column(String, default="CANDIDATE")
    deployment_target = Column(String)
    is_champion = Column(Boolean, default=False)
    rolled_back_from = Column(String)
    deployed_at = Column(DateTime)
    latency_ms = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

class RetrainingHistory(Base):
    __tablename__ = "retraining_history"

    id = Column(Integer, primary_key=True, index=True)
    training_id = Column(String, unique=True, index=True)
    base_model_id = Column(String)
    candidate_model_id = Column(String)
    training_start_time = Column(DateTime)
    training_end_time = Column(DateTime)
    data_range_start = Column(DateTime)
    data_range_end = Column(DateTime)
    station_scope = Column(String)
    sensor_scope = Column(String)
    preprocessing_version = Column(String)
    feature_version = Column(String)
    dataset_version = Column(String)
    label_version = Column(String)
    metrics_before_json = Column(JSON)
    metrics_after_json = Column(JSON)
    comparison_result = Column(String)
    approval_status = Column(String)
    created_at = Column(DateTime, server_default=func.now())

class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id = Column(Integer, primary_key=True, index=True)
    approval_type = Column(String) # QC_CHANGE, REPORT, MODEL_DEPLOY
    target_id = Column(String)
    requested_by = Column(String)
    approved_by = Column(String)
    approval_status = Column(String) # PENDING, APPROVED, REJECTED
    comment = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String)
    action = Column(String, nullable=False)
    resource_type = Column(String)
    resource_id = Column(String)
    detail_json = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

class AIReport(Base):
    __tablename__ = 'ai_reports'
    
    report_id = Column(String(50), primary_key=True)
    title = Column(String(200), nullable=False)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(20)) # e.g., 'pending', 'published'
    author = Column(String(50))
    report_type = Column(String(50)) # e.g., 'weekly', 'anomaly'

class TestScenario(Base):
    __tablename__ = 'test_scenarios'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    trigger_condition = Column(String(100))
    expected_outcome = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class TestAutomationLog(Base):
    __tablename__ = 'test_automation_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, index=True)
    status = Column(String(50)) # SUCCESS, FAILED, RUNNING
    logs = Column(Text)
    execution_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AgentTaskApproval(Base):
    __tablename__ = 'agent_task_approvals'
    
    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String(50)) # ISSUE_REGISTRATION, ROOT_CAUSE_DIAGNOSIS, REPORT_DRAFT
    reference_id = Column(String(100)) # ID of related report/issue
    content_payload = Column(Text) # JSON string of the proposed content
    status = Column(String(50), default='PENDING') # PENDING, APPROVED, REJECTED
    reviewer_comment = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    reviewed_by = Column(String(100), nullable=True)

class ReportRegistry(Base):
    __tablename__ = 'report_registry'
    
    report_id = Column(String(50), primary_key=True)
    report_type = Column(String(50), index=True)
    report_title = Column(String(200))
    report_date = Column(DateTime)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    status = Column(String(20))
    created_by = Column(String(100))
    reviewed_by = Column(String(100))
    approved_by = Column(String(100))
    source_file_path = Column(String(255))
    generated_file_path = Column(String(255))
    summary = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class DailySituationReport(Base):
    __tablename__ = 'daily_situation_report'
    
    report_id = Column(String(50), ForeignKey('report_registry.report_id'), primary_key=True)
    report_date = Column(DateTime)
    station_total = Column(Integer)
    station_normal = Column(Integer)
    station_issue = Column(Integer)
    collection_rate_avg = Column(Float)
    missing_count = Column(Integer)
    bad_count = Column(Integer)
    major_issue_summary = Column(Text)
    action_summary = Column(Text)
    pending_action_summary = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class ServiceMonitoringLog(Base):
    __tablename__ = 'service_monitoring_log'
    
    service_log_id = Column(String(50), primary_key=True)
    service_name = Column(String(100))
    check_time = Column(DateTime)
    station_id = Column(String(50))
    station_name = Column(String(100))
    data_latest_time = Column(DateTime)
    api_status = Column(String(20))
    display_status = Column(String(20))
    delay_minutes = Column(Integer)
    issue_level = Column(String(20))
    issue_detail = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class SpringTideMonitoringReport(Base):
    __tablename__ = 'spring_tide_monitoring_report'
    
    report_id = Column(String(50), ForeignKey('report_registry.report_id'), primary_key=True)
    spring_tide_period = Column(String(50))
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    station_id = Column(String(50))
    station_name = Column(String(100))
    predicted_high_tide = Column(Float)
    observed_high_tide = Column(Float)
    tide_residual = Column(Float)
    risk_level = Column(String(20))
    alert_message = Column(Text)
    action_required = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class WeeklyTideResidualReport(Base):
    __tablename__ = 'weekly_tide_residual_report'
    
    report_id = Column(String(50), ForeignKey('report_registry.report_id'), primary_key=True)
    station_id = Column(String(50))
    station_name = Column(String(100))
    week_start = Column(DateTime)
    week_end = Column(DateTime)
    residual_mean = Column(Float)
    residual_max = Column(Float)
    residual_min = Column(Float)
    residual_trend = Column(String(20))
    anomaly_detected = Column(Boolean)
    analysis_comment = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class QualityCollectionReport(Base):
    __tablename__ = 'quality_collection_report'
    
    report_id = Column(String(50), ForeignKey('report_registry.report_id'), primary_key=True)
    station_id = Column(String(50))
    station_name = Column(String(100))
    variable_code = Column(String(50))
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    total_expected_count = Column(Integer)
    total_received_count = Column(Integer)
    collection_rate = Column(Float)
    qc_normal_count = Column(Integer)
    qc_suspect_count = Column(Integer)
    qc_bad_count = Column(Integer)
    qc_missing_count = Column(Integer)
    qc_completion_rate = Column(Float)
    created_at = Column(DateTime, server_default=func.now())

class DailyInspectionReport(Base):
    __tablename__ = 'daily_inspection_report'
    
    inspection_id = Column(String(50), primary_key=True)
    report_id = Column(String(50), ForeignKey('report_registry.report_id'), nullable=True)
    report_date = Column(DateTime)
    station_id = Column(String(50))
    station_name = Column(String(100))
    sensor_id = Column(String(50))
    equipment_status = Column(String(50))
    communication_status = Column(String(50))
    power_status = Column(String(50))
    issue_found = Column(Boolean)
    issue_detail = Column(Text)
    action_taken = Column(Text)
    inspector = Column(String(100))
    follow_up_required = Column(Boolean)
    created_at = Column(DateTime, server_default=func.now())

class ReportGenerationHistory(Base):
    __tablename__ = 'report_generation_history'
    
    generation_id = Column(String(50), primary_key=True)
    report_id = Column(String(50), index=True)
    report_type = Column(String(50))
    trigger_type = Column(String(50))
    input_data_range = Column(String(100))
    input_station_count = Column(Integer)
    input_issue_count = Column(Integer)
    generation_status = Column(String(50))
    generated_summary = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class ReportTestResult(Base):
    __tablename__ = 'report_test_result'
    
    test_id = Column(String(50), primary_key=True)
    report_id = Column(String(50))
    report_type = Column(String(50))
    test_name = Column(String(100))
    test_status = Column(String(20))
    expected_result = Column(Text)
    actual_result = Column(Text)
    validation_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class AutomationTestResult(Base):
    __tablename__ = 'automation_test_result'
    
    test_id = Column(String(50), primary_key=True)
    workflow_name = Column(String(100))
    test_scenario = Column(String(100))
    test_status = Column(String(20))
    input_condition = Column(Text)
    expected_action = Column(Text)
    actual_action = Column(Text)
    execution_time_ms = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

class Alert(Base):
    __tablename__ = 'alert'
    
    issue_id = Column(String(50), primary_key=True)
    issue_type = Column(String(50))
    issue_level = Column(String(20))
    station_id = Column(String(50))
    station_name = Column(String(100))
    title = Column(String(200))
    description = Column(Text)
    detected_at = Column(DateTime, server_default=func.now())
    assigned_to = Column(String(100))
    status = Column(String(20))
    related_report_id = Column(String(50))
    related_test_id = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
