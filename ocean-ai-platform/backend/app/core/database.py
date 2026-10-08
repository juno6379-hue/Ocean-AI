# 파일 역할: 관계형 데이터베이스 연결과 요청별 세션을 관리합니다.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

import os

# TEST_MODE 환경 변수 우선 적용
is_test = os.environ.get("TEST_MODE", "0") == "1" or settings.TEST_MODE
active_db_url = settings.TEST_DATABASE_URL if is_test else settings.DATABASE_URL

# PostgreSQL 등 다중 쓰레드 연결을 지원하는 DB에서는 check_same_thread 옵션 불필요
connect_args = {}
# 운영 환경 시 connection pool 옵션 추가 가능 (예: pool_size=20, max_overflow=10)

engine = create_engine(
    active_db_url, connect_args=connect_args, pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
