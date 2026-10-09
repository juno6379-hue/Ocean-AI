# 02. 설치 및 실행

기준일: 2026-10-08. Windows PowerShell 기준이며, [현재 문서 안내](README.md)와 [구현 경계](01_SYSTEM_ARCHITECTURE.md)를 함께 읽는다. 아래 기본 절차는 Oracle 수집, 운영 DDL, seed, 모델 학습을 자동으로 시작하지 않는다.

## 요구 환경과 가져오기

이전 tree는 Python 3.14.2와 Node 24.13.0에서 검증했고 이번 전체 회귀 결과는 [10/8 감사](10_IMPLEMENTATION_AUDIT.md)를 따른다. 깨끗한 `npm ci --ignore-scripts` 후 TypeScript/Vite build 통과를 검증했다. Backend requirements는 완전한 버전 lock 파일이 아니므로 재설치한 dependency 조합은 다시 검증한다. 다른 Python 버전의 호환성도 별도 확인한다. [잠금 파일](../ocean-ai-platform/frontend/package-lock.json)의 Vite 요구사항은 Node.js `^20.19.0 || >=22.12.0`이다. Node 18은 현재 설치 기준이 아니다. PostgreSQL 15와 Git이 필요하다. Ollama와 Chroma는 문서 검색을 사용할 때 추가한다.

```powershell
git clone https://github.com/juno6379-hue/Ocean-AI.git
Set-Location .\Ocean-AI\ocean-ai-platform
```

저장소에는 원천 데이터, 운영 비밀값, 승인 receipt, 대용량 문서·벡터·학습 artifact가 포함되지 않는다. 소스를 받은 것만으로 기존 운영 데이터나 모델이 복원되지 않는다.

## PostgreSQL과 backend 환경파일

[Compose 파일](../ocean-ai-platform/docker-compose.yml)은 PostgreSQL만 기동한다. 사용할 로컬 비밀번호를 현재 PowerShell 세션의 `POSTGRES_PASSWORD`에 안전하게 설정한 후 실행한다. 저장소에 비밀번호를 쓰거나 commit하지 않는다. 동일한 값으로 backend의 `DATABASE_URL`을 설정한다. 이미 5432에서 DB가 실행 중이면 별도 인스턴스의 포트와 데이터 볼륨을 먼저 구분한다.

```powershell
# 현재 세션에 POSTGRES_PASSWORD를 설정한 뒤 실행한다.
docker compose up -d db
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 예제의 POSTGRES_PASSWORD는 Compose 전용이다. backend Settings 입력에서 제외한다.
Get-Content .env.example |
  Where-Object { $_ -notmatch '^\s*POSTGRES_PASSWORD=' } |
  Set-Content -Encoding utf8 .env
```

현재 [`.env.example`](../ocean-ai-platform/backend/.env.example)에 있는 `POSTGRES_PASSWORD`를 그대로 backend `.env`에 복사하면 [Settings](../ocean-ai-platform/backend/app/core/config.py)가 `extra_forbidden`으로 거부한다. Compose 비밀번호는 shell 환경 또는 Compose가 읽는 별도 로컬 환경파일로 관리한다. Backend `.env`에는 설정 모델에 정의된 키만 넣는다. `DATABASE_URL`의 placeholder를 실제 개발 DB 주소와 URL-encoded 비밀번호로 바꾼다.

| 설정 | 기본값 또는 역할 |
|---|---|
| `DATABASE_URL` | PostgreSQL 업무 DB. 예제 `change-me`는 교체해야 하는 placeholder다. |
| `TEST_DATABASE_URL` | 격리 시험용 `sqlite://`. 운영 DB를 시험 대상으로 지정하지 않는다. |
| `DATA_MODE` | `live`. Demo prototype을 쓰려면 별도의 demo 환경을 명시한다. |
| `MDC_SYNC_ENABLED` | `false`. Oracle 권한·clock·단위·수집 계획 검토 후 명시적으로 켠다. |
| `AUTO_CREATE_TABLES` | `false`. 서버 시작으로 운영 스키마를 수정하지 않는다. |
| `API_IDENTITIES` | `{}`. 쓰기와 승인에는 실제 사용자별 token과 role 등록이 필요하다. |
| `DATASET_SNAPSHOT_DIR` | `data/dataset_snapshots`. 불변 dataset/dependency 파일 저장소다. |
| `DOCUMENT_CHROMA_HOST/PORT/SSL` | Chroma 서버 연결. 기본 `127.0.0.1:8001`, SSL false. |
| `MDC_DSN/MDC_USER/MDC_PWD` | Oracle 연결 정보. 기본은 비어 있다. |
| `ORACLE_CLIENT_LIB_DIR` | 지정 시 Oracle thick client 사용. 비어 있으면 thin 모드다. |

`API_IDENTITIES`의 role은 viewer/operator/reviewer/admin이며 token은 서버에만 둔다. 화면은 사용자가 제공한 bearer를 메모리에서 사용한다. Frontend 환경파일에 운영 token을 넣지 않는다. `API_IDENTITIES={}`인 상태에서 인증이 필요한 요청의 503은 의도된 차단이다. [인증 구현](../ocean-ai-platform/backend/app/core/security.py)을 참조한다.

## 스키마 준비

기존 운영 DB는 백업·스키마 대조·DDL 검토 후 개별 migration을 적용한다. `AUTO_CREATE_TABLES=true`, seed 또는 `migrate_process_schema.py`를 공통 설치 단계로 사용하지 않는다. 특히 [기존 중복 정리 script](../ocean-ai-platform/backend/app/scripts/migrate_process_schema.py)는 관측 중복을 삭제하므로 [검토 절차 07](07_MDC_DEDUPLICATION_MIGRATION.md)가 먼저다.

새로 만든 **비어 있는 개발 DB**에서는 연결 대상이 개발 DB인지 확인한 후 아래처럼 현재 ORM 테이블을 명시 생성할 수 있다. 이 작업은 DDL을 수행한다. 기존 테이블의 열·제약 변경을 해결하는 migration 대용으로 사용하지 않는다.

```powershell
python -c "from app.core.database import Base,engine; from app.models import domain,source_contracts,source_observation_binding,agent_workflow; Base.metadata.create_all(bind=engine)"
```

기존 DB에 필요한 추가 스키마는 [event/evidence migration](../ocean-ai-platform/backend/app/scripts/migrate_event_evidence.py), [source contract migration](../ocean-ai-platform/backend/app/scripts/migrate_source_contracts.py), [source binding SQL](../ocean-ai-platform/backend/migrations/20261007_source_observation_binding.sql), [registry migration](../ocean-ai-platform/backend/app/scripts/migrate_mlops_registry.py)을 각각 검토한다. Source contract script는 기본 dry-run, `--apply`일 때 두 테이블만 생성한다. Binding은 Standard/SourcePacket/ApprovalHistory FK를 먼저 요구한다. `mdc_sensor_catalog`는 [카탈로그 reconcile](../ocean-ai-platform/backend/app/scripts/reconcile_mdc_sensors.py)의 별도 명시 적용 경로이며 현재 운영에 미생성이다.

## 10/8 QC·workflow 추가 스키마와 분석

기존 PostgreSQL에는 [QC evidence nullable3열](../ocean-ai-platform/backend/migrations/20261008_qc_rule_evidence.sql)과 [workflow run/transition2테이블](../ocean-ai-platform/backend/migrations/20261008_agent_workflow.sql)을 명시 적용한다. 파일은 additive·멱등 DDL이며 기존 결과를 EVALUATED 또는 APPROVED로 backfill하지 않는다. ApprovalHistory/QCRuleResult 등 기존 FK 대상이 먼저 있어야 한다. 검토한 DB 연결에서 각 SQL을 적용하고 열·제약을 확인한다.

10/9 일일 QC reader에는 [binding clock migration](../ocean-ai-platform/backend/app/scripts/migrate_binding_clock_20261009.py)의 `source_observation_binding.bound_at_utc`도 필요하다. PostgreSQL nullable timestamptz이며 기본값·소급 채움이 없다. 기존 `created_at`과 승인 payload를 유지하고 신규 승인 ingest만 같은 트랜잭션에서 명시 UTC를 저장한다. 예전 binding의 NULL 시각은 미확인으로 남는다. schema migration을 먼저 확인한 뒤 새 reader/writer를 실행한다.

```powershell
python -m app.scripts.migrate_binding_clock_20261009
# 검토한 DB 연결에만 명시 적용
python -m app.scripts.migrate_binding_clock_20261009 --apply
```

기본 명령은 DDL 문자열만 출력한다. 10/9 시험 DB는 기존 binding 0건을 확인한 뒤 이 nullable 열만 추가하고 재적용 멱등성과 전체 원장 건수 불변을 대조했다. 실제 원천·승인·QC/모델 기록을 만들거나 기존 시간대를 확정한 작업은 아니다. [36 검증·schema 변경 기록](36_QC_OPERATIONAL_DASHBOARD_EXECUTION.md)을 따른다.

실제 계정은 사용자 지시로 업무 수행 시점에 설정한다. `API_IDENTITIES={}`에서도 readonly QC 평가·loopback anomaly fit/analyze·Evidence Fusion을 검토할 수 있다. 실제 workflow 생성/승인/재개는 계정/role을 요구한다. 개발 선언과 JSON artifact는 source/dataset/model 승인 원장에 적재되지 않는다.

현재 최신 개발 웹은 별도 backend8010·frontend5174다. `VITE_API_BASE_URL=http://127.0.0.1:8010/api`를 해당 Vite 세션에 설정한다. Chroma 기본8001과 겹치지 않는다. 일반 신규 설치의 기본8000/5173은 아래와 같다.

## API와 화면 실행

Backend 디렉터리에서 실행한다. [run_local.ps1](../ocean-ai-platform/backend/run_local.ps1)은 loopback을 사용한다. 정상 설치에서는 requirements의 DuckDB를 사용하며 로컬 vendor fallback을 준비할 필요가 없다.

```powershell
.\run_local.ps1 -Port 8000
# 또는
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

별도 PowerShell에서 `ocean-ai-platform/frontend`로 이동한다.

```powershell
npm ci --ignore-scripts
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Frontend 기본 `/api`는 [Vite proxy](../ocean-ai-platform/frontend/vite.config.ts)로 `http://127.0.0.1:8000`에 전달한다. `API_PROXY_TARGET`으로 개발 proxy 대상을 바꿀 수 있고, 배포용 API base는 `VITE_API_BASE_URL`이다. 기본 화면은 `http://127.0.0.1:5173`, Swagger는 `http://127.0.0.1:8000/docs`다. `/health`는 프로세스, `/readiness`는 DB 연결을 확인한다. 둘 다 모델 배포나 실제 원천 승인 완료를 뜻하지 않는다.

상위 [start_web_local.ps1](../ocean-ai-platform/start_web_local.ps1)은 기존 문서 contract를 요구하는 운영 편의 wrapper다. `DocumentDataRoot` 기본값은 기존 C 드라이브 경로이므로 보존된 실제 문서 저장소를 명시해야 한다. 없는 contract를 새 빈 벡터 저장소로 대체하지 않는다. 원천 검토와 lake 기본 경로에는 `D:\AI_Observation` 의존성이 남아 있으므로 새 개발 환경에서는 해당 데이터·보존 계보를 별도로 준비해야 한다.

## 문서 검색과 모델 worker

Ollama endpoint는 기본 `http://localhost:11434`, chat 모델 기본은 `llama3`다. 활성 문서 인덱스는 [문서 contract](../ocean-ai-platform/backend/app/rag/document_contract.py)에 기록된 embedding 모델·digest·dimension·버전을 따른다. 신규 contract 기본 모델은 `mxbai-embed-large:latest`이며 HuggingFace 임베딩을 자동으로 다운로드하는 설치 흐름이 아니다. 기존 contract가 있으면 그 모델을 먼저 확인하고 보존한다. 모델 부재 시 일부 chat 경로의 명시적 Mock 응답을 실제 진단으로 사용하지 않는다.

Chroma는 기존 데이터 디렉터리를 소유하는 **한 서버**로 실행하고 API는 HttpClient로 연결한다. Backend에서 `OCEAN_APP_DATA_DIR`/`DOCUMENT_PIPELINE_DIR`과 Chroma 설정을 실제 보존 위치에 맞춘 뒤 다음 실행 경로를 사용한다.

```powershell
python -m app.scripts.serve_document_vectors
```

인덱스 삭제, `rag_initializer`, reindex/ingest는 설치 확인 명령이 아니다. [문서 검색](15_DOCUMENT_INDEX_INGESTION.md)과 기존 contract·원문 hash를 먼저 대조한다.

Worker는 API와 별도 프로세스다. `OCEAN_TRAINING_WORKER_ENABLED=1`을 명시한 운영 환경에서 `python -m app.scripts.model_training_worker --once` 또는 `--poll-seconds 10`으로 실행한다. 승인 원천·dataset·프로토콜이 없으면 실행 preflight가 차단한다. 로컬 serving은 `OCEAN_LOCAL_MODEL_SERVING_ENABLED=1`과 별도 배포 승인·artifact 무결성을 요구한다. 단순 flag 설정으로 모델을 만들거나 승인하지 않는다.

## 설치 확인

시험은 별도 PowerShell에서 backend로 이동하고 아래 임시 파일 저장소를 설정한 뒤 실행한다. 이 세 키는 Settings 필드가 아니므로 backend `.env`에 추가하지 않고 `$env:`로 설정한다. 시험 파일과 운영 큐·문서 원장을 분리한다.

```powershell
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('ocean-ai-tests-' + [guid]::NewGuid().ToString('N'))
$env:OCEAN_MLOPS_ROOT = Join-Path $testRoot 'mlops'
$env:OCEAN_APP_DATA_DIR = Join-Path $testRoot 'app-data'
$env:DOCUMENT_PIPELINE_DIR = Join-Path $testRoot 'document-pipeline'
New-Item -ItemType Directory -Force -Path $env:OCEAN_MLOPS_ROOT, $env:OCEAN_APP_DATA_DIR, $env:DOCUMENT_PIPELINE_DIR | Out-Null
python -B -m pytest tests -q -p no:cacheprovider
```

Frontend에서는 `npm run build`를 실행한다. [test conftest](../ocean-ai-platform/backend/tests/conftest.py)는 DB를 격리하고 sync/자동 DDL을 끈다. API 조회와 UI 확인 후 실제 source owner/센서 구간/clock/단위/QC 승인, 사건·라벨·Feature, 고정 분할을 준비해야 학습 운영으로 이어진다. 현재 운영 현황은 [docs 안내](README.md)에서 확인한다.
## 10/8 단계별 보완 결과

`DEVELOPMENT_STAGES_ROOT` 기본값은 `D:/AI_Observation/outputs/development-stages-20261008`이다. root stage-index와 receipt SHA가 있어야 기술 현황을 확인할 수 있다. 공개 clone만으로 로컬 증거를 생성하지 않으며 누락은 UNKNOWN이다.

backend CLI: `python -m app.scripts.review_document_backlog --help`, `resume_document_recovery --help`, `promote_document_recovery --help`, `operational_state_backup --help`, `review_actual_analysis --help`, `run_raw_model_comparison --help`. 각각 `app.scripts.` 접두를 사용한다. source/config와 private output을 명시하며 원문·token·DB dump는 저장소 밖에 보존한다. [29](29_DEVELOPMENT_STAGE_EXECUTION.md), [복구85](85_OPERATIONS_RECOVERY_REVIEW.md).

개발용 실제 원시 학습·게시 묶음·별도8011 서버의 명령은 [30](30_EXPERIMENTAL_TRAIN_DEPLOYMENT.md)을 따른다. CLI는 `train_raw_next_row`, `publish_raw_training_release`, `raw_forecast_development_server`이며 Windows background 실행 helper는 `app/scripts/start_raw_forecast_development_server.ps1`이다. 기존8011 listener가 있으면 보존하고 중단한다. 기본5174 Vite의 `/experimental-api` proxy만 새 서버를 사용하고 기존 `/api` 대상은 유지한다. 실제 운영 worker/serving 설정을 활성화하는 절차가 아니다.
