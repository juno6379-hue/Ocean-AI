# 파일 역할: 백엔드 API·실행 수명주기·예외 처리를 구성합니다.
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import contextlib
import json
import logging
import time
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    BackgroundScheduler = None
from app.core.security import authorize_api, current_actor, Actor
from app.core.database import SessionLocal

from app.api import routes_stations, routes_observations, routes_qc, routes_dashboard, routes_rag, routes_mlops, routes_reports, routes_equipment, routes_test_auto, routes_features, routes_approvals, routes_datasets
from app.api import routes_alerts, routes_tide_analysis, routes_service_monitoring, routes_ai_insights, routes_agents, routes_events, routes_datalake, routes_imputation, routes_forecasting
from app.api import routes_foundation
from app.api import routes_technical_review
from app.api import routes_source_contracts
from app.api import routes_integrations
from app.api import routes_anomaly_analysis
from app.api import routes_model_development
from app.api import routes_development_stages
from app.api import routes_operation_simulation
from app.api import routes_qc_workspace
from app.api import routes_qc_candidates
from app.core.database import engine, Base
from app.core.config import settings
from app.models import domain  # Ensure models are loaded before create_all
from app.models import agent_workflow  # Durable recommendation approval boundary
from app.services.http_request_metrics import request_metrics

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    scheduler = None
    if settings.MDC_SYNC_ENABLED:
        if settings.DATA_MODE != "live":
            raise RuntimeError("MDC synchronization requires live mode; use a separate demo database")
        if BackgroundScheduler is None:
            raise RuntimeError("MDC synchronization requires APScheduler")
        from app.scripts.sync_mdc_db import sync_job, sync_metadata, sync_today_bulk, init_oracle
        init_oracle()
        with SessionLocal() as db:
            sync_metadata(db)
            sync_today_bulk(db)
        scheduler = BackgroundScheduler()
        scheduler.add_job(sync_job, 'interval', seconds=10, max_instances=1, coalesce=True)
        scheduler.start()
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown()

app = FastAPI(
    title="Ocean AI Platform API",
    description="AI 기반 해양관측 업무혁신 플랫폼 API",
    version="0.1.0",
    dependencies=[Depends(authorize_api)],
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.CORS_ORIGINS.split(',') if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_stations.router)
app.include_router(routes_observations.router)
app.include_router(routes_qc.router)
app.include_router(routes_dashboard.router, prefix="/api/dashboard")
app.include_router(routes_rag.router)
app.include_router(routes_mlops.router, prefix="/api/mlops")
app.include_router(routes_reports.router, prefix="/api/reports")
app.include_router(routes_equipment.router)
app.include_router(routes_test_auto.router, prefix="/api/test-auto")
app.include_router(routes_alerts.router, prefix="/api/alerts")
app.include_router(routes_tide_analysis.router, prefix="/api/tide")
app.include_router(routes_service_monitoring.router, prefix="/api/service-monitoring")
app.include_router(routes_features.router)
app.include_router(routes_approvals.router)
app.include_router(routes_datasets.router)
app.include_router(routes_ai_insights.router)
app.include_router(routes_agents.router)
app.include_router(routes_events.router)
app.include_router(routes_datalake.router)
app.include_router(routes_foundation.router)
app.include_router(routes_technical_review.router)
app.include_router(routes_source_contracts.router)
app.include_router(routes_integrations.router)
app.include_router(routes_anomaly_analysis.router)
app.include_router(routes_model_development.router)
app.include_router(routes_development_stages.router)
app.include_router(routes_operation_simulation.router)
app.include_router(routes_qc_workspace.router)
app.include_router(routes_qc_candidates.router)
app.include_router(routes_imputation.router)
app.include_router(routes_forecasting.router)

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO), format="%(message)s")
logger = logging.getLogger("ocean_ai")

@app.middleware("http")
async def request_logging(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
        request_metrics.record(response.status_code, (time.perf_counter()-started)*1000)
        logger.info(json.dumps({"event":"http_request", "method":request.method, "path":request.url.path, "status":response.status_code, "duration_ms":round((time.perf_counter()-started)*1000, 2)}))
        return response
    except Exception:
        request_metrics.record(500, (time.perf_counter()-started)*1000)
        logger.exception(json.dumps({"event":"http_exception", "method":request.method, "path":request.url.path}))
        raise

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(json.dumps({"event":"unhandled_exception", "path":request.url.path, "error":str(exc)}))
    return JSONResponse(status_code=500, content={"detail":"Internal server error"})

@app.get("/health")
def health():
    return {"status":"ok", "environment":settings.ENVIRONMENT}

@app.get("/readiness")
def readiness():
    from sqlalchemy import text
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status":"ready", "database":"ok"}
    except Exception as exc:
        logger.error(json.dumps({"event":"readiness_failed", "error":str(exc)}))
        return JSONResponse(status_code=503, content={"status":"not_ready", "database":"unavailable"})

@app.get("/")
def read_root():
    return {"message": "Welcome to Ocean AI Platform API"}


@app.get("/api/session")
def session(actor: Actor = Depends(current_actor)):
    return {"user_id": actor.user_id, "role": actor.role}


@app.get("/api/runtime")
def runtime():
    return {"data_mode": settings.DATA_MODE, "is_demo": settings.DATA_MODE == "demo", "mdc_sync_enabled": settings.MDC_SYNC_ENABLED}

# Shared real-file route; no simulated PostgreSQL fallback.
from app.api import routes_lake_browser
app.include_router(routes_lake_browser.router)
