# Ocean AI Platform

해양 관측 데이터를 수집·조회하고, 품질관리(QC), 이상 탐지, 문서 검색(RAG), 보고서 생성과 MLOps 현황을 한 곳에서 관리하기 위한 AI 기반 운영 플랫폼입니다.

## 주요 기능

- 관측소·센서·관측 원시 데이터 조회
- QC 플래그와 이상 데이터 모니터링
- LangGraph 기반 QC Copilot 및 원인 진단
- ChromaDB와 Ollama를 이용한 문서 검색·질의응답(RAG)
- AI 보고서 초안 생성과 검토·승인 흐름
- 모델 레지스트리와 재학습 이력 관리
- 장비·서비스 상태 및 알림 모니터링

## 기술 스택

- Frontend: React, TypeScript, Vite, Tailwind CSS, Recharts
- Backend: Python, FastAPI, Pydantic, SQLAlchemy
- Database: PostgreSQL(기본), SQLite(격리 테스트)
- AI: LangChain, LangGraph, Ollama, ChromaDB

## 디렉터리 구조

```text
ocean-ai-platform/
├─ backend/                 # FastAPI API 서버와 AI 에이전트
│  ├─ app/api/              # REST API 라우트
│  ├─ app/agents/           # QC, RAG, 보고서, 모니터링 에이전트
│  ├─ app/models/           # SQLAlchemy 모델
│  ├─ app/data/             # 문서와 로컬 RAG 데이터
│  ├─ sample_data/          # 개발용 CSV와 보고서 템플릿
│  └─ requirements.txt
├─ frontend/                # React 웹 애플리케이션
├─ docker-compose.yml
└─ test_*.py
```

## 데이터 문서

- [검증 자료–웹 메뉴–실시간 확장 전체 연관도](docs/67_DATA_TO_WEB_AND_REALTIME_ARCHITECTURE.md): 현재 연결과 후속 연결, 관리자 소스 시험, Parquet 활용 범위 및 실행 검증

- [데이터 분류 및 처리 계획](docs/06_DATA_CLASSIFICATION_AND_PROCESSING.md): 정형·비정형·요청자료·소스의 분류, 품질검사, 변환·적재·RAG 처리 순서
- [MDC 중복 방지 적용 내역](../docs/07_MDC_DEDUPLICATION_MIGRATION.md): 관측 자연키, PostgreSQL upsert, 기존 DB 마이그레이션 및 검증 절차

## 운영 안전성 설정

변경·승인 기능을 사용하기 전에 [실행 및 검증 가이드](docs/46_SAFETY_AND_WORKFLOW_FIXES.md)를 읽고 담당자 인증을 설정하세요. 기본 설정은 MDC 자동 동기화와 스키마 자동 생성을 실행하지 않습니다. 기존 재생 데이터의 관측시각은 자동 수정하지 않습니다.

## 로컬 실행

### 백엔드

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

백엔드 기본 주소는 `http://localhost:8000`이며 Swagger 문서는 `/docs`에서 확인할 수 있습니다.

### 프런트엔드

```bash
cd frontend
npm install
npm run dev
```

개발 서버는 Vite 기본 포트인 `5173`에서 실행됩니다.

## Docker 실행

```bash
docker compose up -d --build
```

현재 Docker 구성은 PostgreSQL만 실행합니다. FastAPI와 프런트엔드는 위 로컬 실행 절차로 별도 실행합니다. 배포 환경에서는 프런트엔드의 API 주소와 백엔드 포트(기본 `8000`)를 환경에 맞게 설정해야 합니다.

## Ollama 설정

Ollama를 사용하는 경우 다음 환경 변수를 설정할 수 있습니다.

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3
OLLAMA_EMBED_MODEL=jhgan/ko-sroberta-multitask
```

Ollama 서버 또는 지정 모델을 사용할 수 없으면 백엔드는 테스트용 Mock 응답으로 대체합니다.

## 테스트 및 빌드

```bash
# 백엔드 테스트
python -m pytest backend/tests -q -p no:cacheprovider

# 프런트엔드 타입 검사 및 프로덕션 빌드
cd frontend
npm run build
```

개발용 SQLite DB, ChromaDB 인덱스, `node_modules`, 빌드 산출물과 대용량 원본 자료는 Git에 포함하지 않습니다.

## 라이선스

현재 저장소는 내부 검토 및 개발용으로 관리됩니다. 별도 라이선스가 지정되기 전까지 무단 배포나 상업적 사용을 금합니다.

## 실제 MDC·Data Lake 학습 검증

조위·기압·풍속·수온의 Oracle→PostgreSQL 연계와 기존 Parquet 학습을 실행했다. [실제 검증 결과와 재현 명령](docs/47_LIVE_MDC_PARQUET_TRAINING_VERIFICATION.md), [집계·분할·해시](docs/47_validation_summary.json)를 참고한다. 모델은 승인 전 후보이며 예측 API에 자동 배포하지 않는다.

### 실측 Parquet 웹 연결 (2026-10-06)

대시보드·관측 현황·상세는 공통 실측 조회 API를 사용합니다. PostgreSQL의 계보·검증 기록과 Parquet 관측값을 연결하며 SIMULATED 값은 이 세 화면에서 제외합니다. [구현 범위·시작 방법·미완료 조건](docs/68_REAL_PARQUET_WEB_CONNECTION.md)을 확인하세요. 로컬 실행은 `backend/run_local.ps1`을 사용할 수 있습니다.

현재 단계와 다음 실행 순서는 [설명 가능한 AI 데이터 기반·통합 로드맵](docs/69_EXPLAINABLE_AI_FOUNDATION_STATUS_AND_ROADMAP.md)을 기준으로 합니다. 관측값은 Parquet, 연결·검토·승인은 PostgreSQL, 원문 근거 검색은 Vector DB가 담당합니다.


## 2026-10-08 게시 상태

승인 원천 계약, dataset snapshot 의존성 동결, 고정 평가 계약, 학습 worker/queue, 독립 비교 검토, registry 및 loopback JSON serving 연결을 포함합니다. 72개 업무는 자료형별 부분 기준선이며 운영 모델 완료로 해석하지 않습니다. 검증 결과·외부 자료 조건·실행 순서는 [82번 릴리스 문서](docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)를 확인하세요.
