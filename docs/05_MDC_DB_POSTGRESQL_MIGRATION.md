# 05. MDC DB 실시간 연동 및 PostgreSQL 마이그레이션 가이드

본 문서는 플랫폼의 데이터베이스를 기본 SQLite에서 운영용 **PostgreSQL**로 교체하고, 외부 관측망 오라클 DB(MDC)와 백엔드를 실시간으로 연동(ETL)하도록 수정한 개발 내역을 기록한 문서입니다.

---

## 🚀 1. 주요 변경 내역 요약

1. **DB 엔진 교체 (SQLite ➡️ PostgreSQL 15)**
   - 대규모 시계열 관측 데이터 수용을 위해 도커(Docker) 기반의 PostgreSQL 15 컨테이너를 도입했습니다.
   - `docker-compose.yml`이 프로젝트 루트에 추가되었습니다.
2. **동기화 파이프라인 자동화 (APScheduler 연동)**
   - 수동으로 실행되던 `sync_mdc_db.py` 스크립트를 리팩토링(`sync_job` 함수 추가)했습니다.
   - 백엔드(FastAPI) 구동 시 `main.py`의 `lifespan` 이벤트를 통해 매 5분마다 백그라운드에서 오라클 DB의 데이터를 긁어와 로컬 PostgreSQL에 적재하도록 스케줄러를 연동했습니다.

---

## 🛠️ 2. 상세 변경 파일 및 역할

### 1) `docker-compose.yml` (신규 추가)
- 로컬 또는 서버 환경에서 명령어 한 번(`docker-compose up -d`)으로 PostgreSQL DB를 띄울 수 있도록 구성했습니다.
- 기본 접속 정보: `postgresql://ocean_ai_user:ocean_ai_password@localhost:5432/ocean_ai_db`

### 2) `backend/app/core/config.py`
- 기존 `sqlite:///./ocean_ai.db` 였던 `DATABASE_URL`을 위 PostgreSQL 접속 URI로 변경했습니다.

### 3) `backend/app/core/database.py`
- SQLite 환경에서만 필요했던 `check_same_thread=False` 옵션을 제거했습니다.
- 끊어진 커넥션을 방지하기 위해 `pool_pre_ping=True` 옵션을 적용하여 안정성을 높였습니다.

### 4) `backend/requirements.txt`
- 백그라운드 스케줄러 구현을 위해 `apscheduler` 패키지 의존성을 추가했습니다. (`psycopg2-binary`는 이미 포함되어 있었습니다.)

### 5) `backend/app/scripts/sync_mdc_db.py`
- 기존에는 `main()`을 통해서만 실행되던 코드를 `sync_job()` 이라는 별도의 함수로 분리했습니다.
- 이를 통해 백엔드 서버에서 스크립트를 독립적으로 모듈화하여 호출할 수 있게 되었습니다.

### 6) `backend/app/main.py`
- FastAPI의 최신 `lifespan` 관리자를 통해, 서버가 `startup` 될 때 `BackgroundScheduler` 인스턴스를 생성하고 5분 주기로 `sync_job`을 실행하도록 등록했습니다.
- 서버가 멈출 때 스케줄러도 우아하게(graceful) 종료되도록 처리했습니다.

---

## ⚠️ 3. 연동 시 주의사항 (사전 준비)

실제 오라클 DB(MDC)와 성공적으로 통신하려면 아래 조건이 반드시 충족되어야 합니다.

1. **Oracle Instant Client 23.0**
   - 현재 백엔드가 구동되는 PC/서버의 `C:\Oracle\instantclient_23_0` 경로에 오라클 클라이언트가 설치되어 있어야 Thick Mode 접속이 가능합니다.
2. **PostgreSQL 컨테이너 실행**
   - 백엔드를 구동하기 전, 반드시 루트 폴더에서 `docker-compose up -d`를 실행하여 DB를 먼저 띄워주세요.
3. **네트워크/방화벽 확인**
   - MDC DB IP (`119.195.114.103:31000`)와의 통신이 사내 망이나 방화벽에 의해 차단되지 않았는지 확인해야 합니다.
