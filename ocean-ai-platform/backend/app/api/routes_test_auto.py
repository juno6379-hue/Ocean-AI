# 파일 역할: 자동 검증 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.agents.automation_test_agent import AutomationTestAgent
from app.models.domain import AutomationTestResult
from pydantic import BaseModel

router = APIRouter(tags=["TestAutomation"])

class TestRunRequest(BaseModel):
    test_type: str = "ALL"
    scenario_name: str = None
    report_type: str = None

@router.post("/run")
def run_tests(req: TestRunRequest, db: Session = Depends(get_db)):
    agent = AutomationTestAgent(db)
    results = agent.run_e2e_scenarios()
    return {"status": "success", "results": results}

@router.get("/results")
def get_test_results(db: Session = Depends(get_db)):
    results = db.query(AutomationTestResult).order_by(AutomationTestResult.created_at.desc()).limit(50).all()
    return {"results": results}

@router.get("/results/{test_id}")
def get_test_result(test_id: str, db: Session = Depends(get_db)):
    result = db.query(AutomationTestResult).filter(AutomationTestResult.test_id == test_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Test result not found")
    return {"result": result}
