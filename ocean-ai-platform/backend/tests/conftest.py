# 파일 역할: 테스트를 운영 DB와 분리하고 공통 실행 환경을 설정합니다.
"""Local unit/integration tests must never connect to the operational database."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["TEST_DATABASE_URL"] = "sqlite://"
os.environ["MDC_SYNC_ENABLED"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "false"
