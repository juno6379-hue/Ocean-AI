"""Immutable source packets and authenticated decisions, separate from drafts."""
from sqlalchemy import Column, String, Integer, JSON, DateTime, ForeignKey, func
from app.core.database import Base


class SourceContractPacket(Base):
    __tablename__ = 'source_contract_packets'
    contract_id = Column(String(128), primary_key=True)
    packet_sha256 = Column(String(64), nullable=False, unique=True)
    payload = Column(JSON, nullable=False)
    requested_by = Column(String, nullable=False)
    status = Column(String(20), nullable=False, default='PENDING')
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SourceContractDecision(Base):
    __tablename__ = 'source_contract_decisions'
    approval_history_id = Column(Integer, ForeignKey('approval_history.id'), primary_key=True)
    contract_id = Column(String(128), ForeignKey('source_contract_packets.contract_id'), nullable=False, index=True)
    packet_sha256 = Column(String(64), nullable=False)
    decision = Column(String(20), nullable=False)
    reviewer_id = Column(String, nullable=False)
    reviewer_role = Column(String(20), nullable=False)
    receipt_sha256 = Column(String(64), nullable=False, unique=True)
    receipt = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
