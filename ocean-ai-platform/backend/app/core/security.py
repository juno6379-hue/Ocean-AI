# 파일 역할: 서버에 등록된 사용자 인증과 작업 권한을 검사합니다.
"""Server-configured identities for the internal pilot; no implicit admin user."""
from dataclasses import dataclass
from secrets import compare_digest
from fastapi import Depends, HTTPException, Request
from app.core.config import settings


@dataclass(frozen=True)
class Actor:
    user_id: str
    role: str


def current_actor(request: Request) -> Actor:
    if not settings.API_IDENTITIES:
        raise HTTPException(503, "Operator authentication is not configured")
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if token.startswith(("qc-sample-", "ai-sample-")):
        raise HTTPException(401, "Sample credentials cannot authorize operational actions")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Operator token required", headers={"WWW-Authenticate": "Bearer"})
    for user_id, identity in settings.API_IDENTITIES.items():
        expected = identity.get("token", "")
        role = identity.get("role", "")
        if expected and compare_digest(token.encode(), expected.encode()) and role in {"viewer", "operator", "reviewer", "admin"}:
            return Actor(user_id, role)
    raise HTTPException(401, "Invalid operator token", headers={"WWW-Authenticate": "Bearer"})


def require_reviewer(actor: Actor = Depends(current_actor)) -> Actor:
    if actor.role not in {"reviewer", "admin"}:
        raise HTTPException(403, "Reviewer role required")
    return actor


def authorize_api(request: Request):
    """Protect writes by default. These POST endpoints only return analysis."""
    sample_gates = {"/api/qc-sample/": settings.QC_SAMPLE_ENABLED,
                    "/api/ai-insights-sample/": settings.AI_INSIGHTS_SAMPLE_ENABLED}
    for prefix, enabled in sample_gates.items():
        if request.url.path.startswith(prefix):
            if not enabled or settings.ENVIRONMENT.lower() not in {"development", "test", "local"}:
                raise HTTPException(404, "Sample mode is disabled")
            # Each isolated router validates its own namespace-specific token.
            # This never grants operator identity or operational workflow access.
            return
    demo_paths = {"/api/qc/run-copilot", "/api/qc/ai-insights-summary", "/api/test-auto/run", "/api/agents/workflow"}
    if request.url.path in demo_paths and settings.DATA_MODE != "demo":
        raise HTTPException(409, "This prototype workflow is available only in demo mode")
    analysis_paths = {
        "/api/rag/chat", "/api/rag/hybrid-search", "/api/qc/copilot/analyze",
        "/api/qc/rules/evaluate", "/api/forecasting/baseline",
        "/api/agents/workflow", "/api/anomaly-analysis/fit",
        "/api/anomaly-analysis/analyze", "/api/agents/evidence/analyze",
        "/api/operation-simulation/run",
    }
    if request.method in {"GET", "HEAD", "OPTIONS"} or request.url.path in analysis_paths:
        return
    actor = current_actor(request)
    if actor.role not in {"operator", "reviewer", "admin"}:
        raise HTTPException(403, "Operator role required")
