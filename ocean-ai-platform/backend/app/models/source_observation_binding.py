"""Exact approved source lineage for an ingested standard observation."""
from sqlalchemy import Column,String,Integer,ForeignKey,JSON,DateTime,UniqueConstraint,func
from sqlalchemy.types import TypeDecorator
from datetime import datetime, timezone
from app.core.database import Base


class ExplicitUTCBindingClock(TypeDecorator):
    """New binding clock only; never reinterpret legacy created_at.

    PostgreSQL uses timestamptz. SQLite's isolated fixture storage loses the
    offset, so this type restores UTC only for this new, explicitly UTC column.
    Every write must already carry an offset; there is no server default.
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('BINDING_CLOCK_EXPLICIT_OFFSET_REQUIRED')
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            if dialect.name != 'sqlite':
                raise ValueError('BINDING_CLOCK_STORAGE_POLICY_MISMATCH')
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


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
    # Additive, nullable, without a default/backfill: legacy bindings remain
    # unverified until an independently authorized availability proof exists.
    bound_at_utc=Column(ExplicitUTCBindingClock(),nullable=True)
