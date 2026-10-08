"""Exact approved source lineage for an ingested standard observation."""
from sqlalchemy import Column,String,Integer,ForeignKey,JSON,DateTime,UniqueConstraint,func
from app.core.database import Base


class SourceObservationBinding(Base):
    __tablename__='source_observation_binding'
    __table_args__=(UniqueConstraint('parquet_sha256','source_row_locator',name='uq_source_observation_row'),)
    observation_id=Column(String(128),ForeignKey('observation_standard.observation_id'),primary_key=True)
    contract_id=Column(String(128),ForeignKey('source_contract_packets.contract_id'),nullable=False)
    approval_history_id=Column(Integer,ForeignKey('approval_history.id'),nullable=False)
    receipt_sha256=Column(String(64),nullable=False)
    source_sha256=Column(String(64),nullable=False)
    parquet_sha256=Column(String(64),nullable=False)
    source_row_locator=Column(String,nullable=False)
    exact_scope_key=Column(String(64),nullable=False,index=True)
    payload=Column(JSON,nullable=False)
    created_by=Column(String,nullable=False)
    created_at=Column(DateTime,server_default=func.now())
