# 파일 역할: 환경변수와 실행 환경 설정을 읽습니다.
from pydantic_settings import BaseSettings
from typing import Dict, Literal

class Settings(BaseSettings):
    PROJECT_NAME: str = "Ocean AI Platform"
    # 운영 환경 기본값 (PostgreSQL로 변경됨)
    DATABASE_URL: str = "postgresql://ocean_ai_user:change-me@127.0.0.1:5432/ocean_ai_db"
    
    # 테스트 환경 분리 플래그
    TEST_MODE: bool = False
    TEST_DATABASE_URL: str = "sqlite://"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    LOG_LEVEL: str = "INFO"
    # Per-user bearer tokens are configured on the server, never in frontend env.
    API_IDENTITIES: Dict[str, Dict[str, str]] = {}
    DATA_MODE: Literal["live", "demo"] = "live"
    # Opt-in, process-memory QC samples. These never use the operational database.
    QC_SAMPLE_ENABLED: bool = False
    AI_INSIGHTS_SAMPLE_ENABLED: bool = False
    MDC_SYNC_ENABLED: bool = False
    AUTO_CREATE_TABLES: bool = False
    VECTOR_SEARCH_ENABLED: bool = True
    # 문서 배치와 API가 공유하는 벡터 서버 주소를 .env에서도 읽는다.
    DOCUMENT_CHROMA_HOST: str = "127.0.0.1"
    DOCUMENT_CHROMA_PORT: int = 8001
    DOCUMENT_CHROMA_SSL: bool = False
    DATASET_SNAPSHOT_DIR: str = "data/dataset_snapshots"
    # File-only validation outputs are separate from operational PostgreSQL rows.
    FOUNDATION_OUTPUT_ROOT: str = "D:/AI_Observation/outputs/share-validation"
    LAKE_WEB_POSTGRES_CATALOG: bool = True
    INTEGRATED_LAKE_ROOT: str = "D:/AI_Observation/data_lake/spool_2001_2026"
    SHARE_MONTHLY_LAKE_ROOT: str = "D:/AI_Observation/data_lake/share_monthly_2023_2026"
    MONTHLY_REPORT_MATCHING_ROOT: str = "D:/AI_Observation/outputs/monthly-report-matching"
    DEVELOPMENT_STAGES_ROOT: str = "D:/AI_Observation/outputs/development-stages-20261008"
    # Additional administrator-registered databases refer to server environment
    # secrets by name. Credentials are never returned to the browser.
    EXTERNAL_SOURCE_CONNECTIONS: Dict[str, Dict[str, str]] = {}
    MDC_DSN: str = ""
    MDC_USER: str = ""
    MDC_PWD: str = ""
    ORACLE_CLIENT_LIB_DIR: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings()

    
