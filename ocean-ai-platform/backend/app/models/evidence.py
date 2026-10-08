# 파일 역할: 사건과 문서·관측·QC·운영·라벨의 근거 관계 및 학습 계보를 저장합니다.
from sqlalchemy import (Column, String, Integer, DateTime, JSON, ForeignKey,
                        ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Boolean)
from sqlalchemy.sql import func
from app.core.database import Base


class SensorAlias(Base):
    """관측소별로 검토한 문서 장비 표현과 실제 센서의 대응표."""
    __tablename__ = 'sensor_alias'
    alias_id = Column(String(128), primary_key=True)
    station_id = Column(String, ForeignKey('station_metadata.station_id'), nullable=False)
    sensor_id = Column(String, ForeignKey('sensor_metadata.sensor_id'), nullable=False)
    variable_code = Column(String, nullable=False)
    alias_text = Column(String, nullable=False, index=True)
    mapping_version = Column(String, nullable=False)
    valid_start = Column(DateTime, nullable=False)
    valid_end = Column(DateTime)
    reviewed_by = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint('station_id','sensor_id','alias_text','mapping_version',name='uq_sensor_alias_version'),)


class MDCSensorCatalog(Base):
    """MDC 장비·항목 조합을 원본 스냅샷으로 보존한다. 물리 센서 이력 확정과 구별한다."""
    __tablename__ = 'mdc_sensor_catalog'
    sensor_id = Column(String, ForeignKey('sensor_metadata.sensor_id'), primary_key=True)
    catalog_version = Column(String(64), primary_key=True)
    station_id = Column(String, ForeignKey('station_metadata.station_id'), nullable=False, index=True)
    te_code = Column(String, nullable=False)
    source_item_code = Column(String, nullable=False, index=True)
    variable_code = Column(String, nullable=False)
    source_unit = Column(String)
    normalized_unit = Column(String)
    valid_start = Column(DateTime)
    valid_end = Column(DateTime)
    issues = Column(JSON, nullable=False)
    source_payload = Column(JSON, nullable=False)
    source_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class EventEvidence(Base):
    """다형 문자열 ID 대신 실제 FK 하나를 선택하는 다대다 근거 링크."""
    __tablename__ = 'event_evidence'
    link_id = Column(String(128), primary_key=True)
    event_id = Column(String(128), ForeignKey('event_registry.event_id'), nullable=False, index=True)
    chunk_id = Column(String(128), ForeignKey('document_index.chunk_id'), index=True)
    observation_id = Column(String(128), ForeignKey('observation_standard.observation_id'), index=True)
    qc_result_id = Column(String(128), ForeignKey('qc_rule_result.qc_result_id'), index=True)
    operation_id = Column(Integer, ForeignKey('operation_log.id'), index=True)
    label_id = Column(String(128), ForeignKey('ai_label.label_id'), index=True)
    provenance = Column(JSON, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (
        CheckConstraint('(CASE WHEN chunk_id IS NULL THEN 0 ELSE 1 END + '
            'CASE WHEN observation_id IS NULL THEN 0 ELSE 1 END + '
            'CASE WHEN qc_result_id IS NULL THEN 0 ELSE 1 END + '
            'CASE WHEN operation_id IS NULL THEN 0 ELSE 1 END + '
            'CASE WHEN label_id IS NULL THEN 0 ELSE 1 END) = 1', name='ck_event_evidence_one_target'),
        *(UniqueConstraint('event_id', key, name='uq_event_evidence_'+key)
          for key in ['chunk_id','observation_id','qc_result_id','operation_id','label_id']),
    )


class LabelReviewSnapshot(Base):
    """승인 시점의 라벨 내용을 보존해 승인 후 변경을 탐지한다."""
    __tablename__ = 'label_review_snapshot'
    approval_id = Column(Integer, ForeignKey('approval_history.id'), primary_key=True)
    label_id = Column(String(128), ForeignKey('ai_label.label_id'), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class FeatureProvenance(Base):
    """Feature 값의 원본 관측과 계산 구간을 보존한다."""
    __tablename__ = 'feature_provenance'
    observation_id = Column(String(128), ForeignKey('observation_standard.observation_id'), primary_key=True)
    feature_id = Column(String(128), primary_key=True)
    feature_version = Column(String, primary_key=True)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    available_at = Column(DateTime, nullable=False)
    source_observation_ids = Column(JSON, nullable=False)
    source_hash = Column(String(64), nullable=False)
    __table_args__ = (ForeignKeyConstraint(['feature_id','feature_version'],
        ['feature_definition.feature_id','feature_definition.feature_version']),)


class DatasetMembership(Base):
    """관측/라벨에서 데이터셋으로 역추적하기 위한 고정 snapshot 참여 목록."""
    __tablename__ = 'dataset_membership'
    dataset_id = Column(String(128), ForeignKey('dataset_registry.dataset_id'), primary_key=True)
    observation_id = Column(String(128), ForeignKey('observation_standard.observation_id'), primary_key=True)
    label_id = Column(String(128), ForeignKey('ai_label.label_id'), nullable=False, index=True)
    event_id = Column(String(128), ForeignKey('event_registry.event_id'), nullable=False, index=True)
    snapshot_hash = Column(String(64), nullable=False)
