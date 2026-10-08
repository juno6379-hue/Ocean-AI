# 파일 역할: 다중 에이전트 업무 흐름 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter
from pydantic import BaseModel
from app.agents.multi_agent_workflow import run_multi_agent_workflow

router = APIRouter(prefix="/api/agents", tags=["Multi-Agent Workflow"])

class WorkflowRequest(BaseModel):
    station_id: str
    sensor_id: str = ""
    query: str = ""

@router.post("/workflow")
def execute_workflow(req: WorkflowRequest):
    return run_multi_agent_workflow(req.station_id, req.sensor_id, req.query)

@router.get("/workflow/stages")
def workflow_stages():
    return {"stages": ["Anomaly Detected", "QC Analysis Agent", "Root Cause Agent", "RAG Evidence Agent", "Recommendation", "Human Approval", "Report Draft Agent", "MLOps Agent"]}
