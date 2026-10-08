"""Read-only analysis and authenticated PostgreSQL workflow decisions/resume."""
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from app.core.database import get_db
from app.core.security import Actor,current_actor,require_reviewer
from app.agents import multi_agent_workflow as workflow
from app.models.agent_workflow import AgentWorkflowRun
from app.services.evidence_fusion import FusionError,digest

router=APIRouter(prefix='/api/agents',tags=['Multi-Agent Workflow'])
class Scope(BaseModel):
    model_config=ConfigDict(extra='forbid')
    station_id:str=Field(min_length=1,max_length=128)
    sensor_id:str=Field(min_length=1,max_length=128)
    variable_code:str=Field(min_length=1,max_length=128)
    unit:str=Field(min_length=1,max_length=64)
    period_start:str
    period_end:str
    as_of:str
    sensor_episode_id:str|None=None
class AnalysisRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    scope:Scope
    query:str=Field(default='',max_length=4000)
    declared_evidence:list[dict]=Field(default_factory=list,max_length=5000)
    rule_report:dict|None=None
    ai_report:dict|None=None
    file_dependencies:list[dict]=Field(default_factory=list,max_length=64)
class StartRequest(AnalysisRequest):
    request_key:str=Field(min_length=1,max_length=128)
class TransitionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:str=Field(min_length=1,max_length=128)
    expected_recommendation_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    expected_revision:int=Field(ge=0)
    comment:str=Field(default='',max_length=4000)
class DecisionRequest(TransitionRequest):
    decision:Literal['APPROVED','REJECTED']
class WorkflowRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    station_id:str
    sensor_id:str
    variable_code:str
    unit:str
    period_start:str
    period_end:str
    as_of:str
    query:str=''

def _error(exc):
    code=getattr(exc,'code','INVALID_ANALYSIS_INPUT')
    status=404 if code=='WORKFLOW_NOT_FOUND' else 403 if code in {'REVIEWER_REQUIRED','OPERATOR_REQUIRED','OWNER_OR_REVIEWER_REQUIRED'} else 422 if isinstance(exc,FusionError) else 409
    raise HTTPException(status,{'code':code,'mutation_performed':False})
def _analyze(db,req):
    return workflow.analyze_inputs(db,req.scope.model_dump(exclude_none=True),req.query,req.declared_evidence,req.rule_report,req.ai_report,file_dependencies=req.file_dependencies)
def _write(db,fn):
    try:result=fn();db.commit();return result
    except (workflow.WorkflowError,FusionError,ValueError,TypeError,KeyError) as exc:db.rollback();_error(exc)
    except IntegrityError:db.rollback();raise HTTPException(409,{'code':'WORKFLOW_CONCURRENT_OR_REPLAY_CONFLICT','mutation_performed':False})
    except SQLAlchemyError:db.rollback();raise HTTPException(503,{'code':'WORKFLOW_STORAGE_UNAVAILABLE','mutation_performed':False})

@router.post('/evidence/analyze')
def evidence_analysis(req:AnalysisRequest,db:Session=Depends(get_db)):
    try:
        payload,result=_analyze(db,req)
        return result|{'input_sha256':digest(payload),'input_scope_description':payload['bundle']['scope_description'],'input_truncated_sections':payload['bundle']['truncated_sections']}
    except (workflow.WorkflowError,FusionError,ValueError,TypeError,KeyError) as exc:_error(exc)
    except SQLAlchemyError:raise HTTPException(503,{'code':'ANALYSIS_STORAGE_UNAVAILABLE'})

@router.post('/workflows')
def start(req:StartRequest,db:Session=Depends(get_db),actor:Actor=Depends(current_actor)):
    def operation():
        payload,result=_analyze(db,req)
        return workflow.start_workflow(db,payload,result,actor,req.request_key)
    return _write(db,operation)
@router.get('/workflows')
def list_workflows(station_id:str|None=None,sensor_id:str|None=None,variable_code:str|None=None,unit:str|None=None,db:Session=Depends(get_db)):
    try:
        query=db.query(AgentWorkflowRun)
        for key,value in {'station_id':station_id,'sensor_id':sensor_id,'variable_code':variable_code,'unit':unit}.items():
            if value is not None:query=query.filter(AgentWorkflowRun.payload['scope'][key].as_string()==value)
        return [workflow.view(r) for r in query.order_by(AgentWorkflowRun.created_at.desc(),AgentWorkflowRun.workflow_id).limit(200).all()]
    except SQLAlchemyError:raise HTTPException(503,{'code':'WORKFLOW_STORAGE_UNAVAILABLE'})
@router.get('/workflows/{workflow_id}')
def get_workflow(workflow_id:str,db:Session=Depends(get_db)):
    try:return workflow.view(workflow._load(db,workflow_id,lock=False))
    except workflow.WorkflowError as exc:_error(exc)
    except SQLAlchemyError:raise HTTPException(503,{'code':'WORKFLOW_STORAGE_UNAVAILABLE'})
@router.post('/workflows/{workflow_id}/decision')
def decision(workflow_id:str,req:DecisionRequest,db:Session=Depends(get_db),actor:Actor=Depends(require_reviewer)):
    return _write(db,lambda:workflow.decide_workflow(db,workflow_id,actor,req.request_key,req.expected_recommendation_sha256,req.expected_revision,req.decision,req.comment))
@router.post('/workflows/{workflow_id}/resume')
def resume(workflow_id:str,req:TransitionRequest,db:Session=Depends(get_db),actor:Actor=Depends(current_actor)):
    return _write(db,lambda:workflow.resume_workflow(db,workflow_id,actor,req.request_key,req.expected_recommendation_sha256,req.expected_revision,req.comment))
@router.post('/workflows/{workflow_id}/cancel')
def cancel(workflow_id:str,req:TransitionRequest,db:Session=Depends(get_db),actor:Actor=Depends(current_actor)):
    return _write(db,lambda:workflow.cancel_workflow(db,workflow_id,actor,req.request_key,req.expected_recommendation_sha256,req.expected_revision,req.comment))
@router.post('/workflow')
def demo_workflow(req:WorkflowRequest):
    try:return workflow.run_multi_agent_workflow(**req.model_dump())
    except (workflow.WorkflowError,FusionError,ValueError) as exc:_error(exc)
@router.get('/workflow/stages')
def workflow_stages():
    return {'stages':workflow.STAGES,'approval_boundary':'Human Approval','pending_stops_execution':True,
        'production_persistence':'PostgreSQL agent_workflow_run/transition','downstream_scope':'DRAFT_AND_MLOPS_RECOMMENDATION_ONLY',
        'definitive_qc':False,'training_started':False,'deployment_performed':False}
