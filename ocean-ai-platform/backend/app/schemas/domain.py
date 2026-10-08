# 파일 역할: 요청·응답 데이터의 필드와 검증 구조를 정의합니다.
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Station
class StationBase(BaseModel):
    station_id: str
    station_name: str
    network_type: Optional[str] = None
    sea_area: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    datum_info: Optional[str] = None
    status: Optional[str] = None

class Station(StationBase):
    id: int
    install_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ObservationRaw
class ObservationRawBase(BaseModel):
    station_id: str
    sensor_id: str
    timestamp_kst: Optional[datetime] = None
    timestamp_utc: Optional[datetime] = None
    variable_code: Optional[str] = None
    value_raw: Optional[float] = None
    value_unit: Optional[str] = None
    source_system: Optional[str] = None
    value_status: Optional[str] = None

class ObservationRaw(ObservationRawBase):
    id: int
    ingest_time: datetime

    class Config:
        from_attributes = True

# ObservationStandard
class ObservationStandardBase(BaseModel):
    observation_id: str
    station_id: str
    sensor_id: str
    variable_code: str
    timestamp_utc: datetime
    value_raw: Optional[float] = None
    value_standard: Optional[float] = None
    source_unit: Optional[str] = None
    standard_unit: Optional[str] = None
    conversion_rule: Optional[str] = None
    standardization_version: str

class ObservationStandard(ObservationStandardBase):
    created_at: datetime

    class Config:
        from_attributes = True

# QCRuleResult
class QCRuleResultBase(BaseModel):
    qc_result_id: str
    observation_id: str
    station_id: str
    sensor_id: str
    variable_code: str
    timestamp_utc: datetime
    qc_rule_id: str
    qc_rule_name: str
    qc_stage: str
    input_value: Optional[float] = None
    threshold_value: Optional[float] = None
    result_flag: str
    result_score: Optional[float] = None
    evaluation_status: Optional[str] = None
    result_reason: Optional[str] = None
    provenance_json: Optional[Dict[str, Any]] = None
    rule_version: str
    executed_at: datetime

class QCRuleResult(QCRuleResultBase):
    class Config:
        from_attributes = True

# AILabel
class AILabelBase(BaseModel):
    label_id: str
    station_id: str
    sensor_id: str
    variable_code: str
    event_start: datetime
    event_end: Optional[datetime] = None
    quality_label: str
    error_type: Optional[str] = None
    error_cause: str = "unknown"
    label_source: str
    label_confidence: Optional[float] = None
    review_status: str = "PENDING"
    reviewer_id: Optional[str] = None
    review_comment: Optional[str] = None
    label_version: str

class AILabel(AILabelBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Feature Store
class FeatureDefinitionBase(BaseModel):
    feature_id: str
    feature_name: str
    feature_group: str
    description: Optional[str] = None
    calculation_logic: str
    source_fields: List[str]
    window_size: Optional[str] = None
    feature_version: str

class FeatureDefinition(FeatureDefinitionBase):
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class FeatureValueBase(BaseModel):
    observation_id: Optional[str] = None
    station_id: str
    sensor_id: str
    variable_code: str
    timestamp_utc: datetime
    feature_id: str
    feature_value: Optional[float] = None
    feature_version: str

class FeatureValue(FeatureValueBase):
    class Config:
        from_attributes = True

# Dataset Registry
class DatasetRegistryBase(BaseModel):
    dataset_id: str
    dataset_name: str
    dataset_version: str
    dataset_split: str
    station_scope: List[str]
    sensor_scope: Optional[List[str]] = None
    variable_scope: List[str]
    period_start: datetime
    period_end: datetime
    sample_count: int = 0
    normal_count: int = 0
    suspect_count: int = 0
    bad_count: int = 0
    missing_count: int = 0
    feature_version: str
    label_version: str
    preprocessing_version: str
    qc_rule_version: Optional[str] = None
    data_hash: Optional[str] = None
    status: str = "DRAFT"
    created_by: Optional[str] = None
    approved_by: Optional[str] = None

class DatasetRegistry(DatasetRegistryBase):
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# QCFlagHistory
class QCFlagHistoryBase(BaseModel):
    station_id: str
    sensor_id: str
    timestamp_utc: Optional[datetime] = None
    variable_code: Optional[str] = None
    qc_stage: Optional[str] = None
    qc_test_name: Optional[str] = None
    qc_flag_1st: Optional[str] = None
    qc_flag_2nd: Optional[str] = None
    qc_flag_final: Optional[str] = None
    ai_flag_candidate: Optional[str] = None
    qc_confidence: Optional[float] = None
    reviewer_id: Optional[str] = None
    review_comment: Optional[str] = None
    qc_version: Optional[str] = None

class QCFlagHistory(QCFlagHistoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ApprovalHistory
class ApprovalHistoryBase(BaseModel):
    approval_type: str
    target_id: str
    requested_by: str
    approved_by: Optional[str] = None
    approval_status: str
    comment: Optional[str] = None

class ApprovalHistory(ApprovalHistoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
