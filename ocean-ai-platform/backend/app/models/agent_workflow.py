"""Additive PostgreSQL workflow state; SQLite is only used by isolated tests."""
from sqlalchemy import Column,String,Integer,JSON,DateTime,ForeignKey,UniqueConstraint,CheckConstraint,func
from app.core.database import Base

class AgentWorkflowRun(Base):
    __tablename__='agent_workflow_run'
    __table_args__=(CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED','RESUMING','COMPLETED')",name='ck_agent_workflow_status'),)
    workflow_id=Column(String(36),primary_key=True)
    request_key=Column(String(128),nullable=False,unique=True)
    requested_by=Column(String,nullable=False)
    input_sha256=Column(String(64),nullable=False)
    recommendation_sha256=Column(String(64),nullable=False)
    payload=Column(JSON,nullable=False)
    recommendation=Column(JSON,nullable=False)
    status=Column(String(20),nullable=False,default='PENDING')
    revision=Column(Integer,nullable=False,default=0)
    approval_history_id=Column(Integer,ForeignKey('approval_history.id'))
    result=Column(JSON)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())

class AgentWorkflowTransition(Base):
    __tablename__='agent_workflow_transition'
    __table_args__=(UniqueConstraint('workflow_id','request_key',name='uq_workflow_transition_request'),UniqueConstraint('workflow_id','revision',name='uq_workflow_transition_revision'))
    id=Column(Integer,primary_key=True)
    workflow_id=Column(String(36),ForeignKey('agent_workflow_run.workflow_id'),nullable=False,index=True)
    request_key=Column(String(128),nullable=False)
    revision=Column(Integer,nullable=False)
    actor_id=Column(String,nullable=False)
    actor_role=Column(String(20),nullable=False)
    from_status=Column(String(20),nullable=False)
    to_status=Column(String(20),nullable=False)
    action=Column(String(20),nullable=False)
    request_sha256=Column(String(64),nullable=False)
    recommendation_sha256=Column(String(64),nullable=False)
    approval_history_id=Column(Integer,ForeignKey('approval_history.id'))
    record=Column(JSON,nullable=False)
    record_sha256=Column(String(64),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now())
