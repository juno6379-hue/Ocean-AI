> **상위 통합 문서**: [42. 조위 AI-QC MLOps 엔진 통합 및 5대 연동 브리지](../42_AI_QC_MLOPS_ENGINE_INTEGRATION.md)  
> **문서 세트 목차**: [00 개요](00_OVERVIEW_AND_INDEX.md) · [01 아키텍처·1:1 비교](01_ARCHITECTURE_AND_FEATURES.md) · [02 웹 운영 가이드](02_USER_WEB_OPERATION_GUIDE.md) · [03 Local QC·임계값 평가](03_LOCAL_QC_SIMULATOR_AND_EVALUATION.md) · [04 한계·상용화 로드맵](04_LIMITATIONS_AND_PRODUCTION_ROADMAP.md) · [05 MLOps 거버넌스](05_MLOPS_GOVERNANCE_AND_POLICY.md)

---

# 시스템 아키텍처 및 전체 기능 상세 명세 (`01_architecture_and_features.md`)

2026-10-21 자료 표준화는 관측 월별 파일을 `정형데이터/GD_OBS_ST/GD_OBS_ST_YYYYMM.csv`로, 예측 월별 파일을 `정형데이터/GO_TIDE_PRE_DATA/GO_TIDE_PRE_DATA_YYYYMM.csv`로 통합한다. 관측 범위는 2023-01~2026-07의 43개월, 예측은 2023-01~2026-09의 45개월이다. 2023년 예측 원본은 `D:\20261021_greenblue\GO_TIDE_PRE_DATA`, 이후 33개월은 `D:\261008_gb_temp\output\GO_TIDE_PRE_DATA`이며 두 원본 폴더는 읽기 전용으로 유지한다. 다년도 파일 두 개는 기존 자료를 수정하지 않고 표준 폴더에 하드링크로 연결한다. 실제 실행 결과와 검증 수치는 `00_OVERVIEW_AND_INDEX.md`의 Item 2 절과 `reports/20261021_data_standardization/standardization_manifest.json`에 기록한다.

관측 월별 CSV의 첫 줄은 `OBS_POST_ID,OBS_ITEM_CODE,OBS_TIME,OBS_VALUE,QC_FLAG,MQC_FLAG,N1_AQC_FLAG`, 예측은 `OBS_POST_ID,OBS_TIME,TIDE_PRE_VAL`이며 CRLF로 끝난다. `scripts/standardize_training_data.py`는 64MiB 단위로 프리앰블·반복 헤더·구분선·SQL*Plus 빈 줄을 제거한다. 별도 검증기가 원본의 데이터 부분과 출력의 모든 바이트·순서·행 수를 비교하고, 검증한 파일 정보가 변하지 않았는지 다시 확인한다. 출력은 기존 파일을 덮어쓰지 않고 확정하며, 삭제 전 저널을 디스크에 기록한 뒤 승인된 로컬 `data_YYYYMM.csv`만 삭제한다. 데이터 값·공백·MQC 판정과 원래 초 단위 시각은 바꾸지 않는다.

연결 경로는 두 UI의 월 선택 → 카탈로그·자료 검사·빠른 준비 API → `workspace_paths.resolve_training_csv_path`와 `dataset_preview`의 형식 감지·월별 우선순위 → 로컬 표준 CSV·검사 결과·Parquet 학습 자료 묶음이다. 표준 로컬 파일을 먼저 고르고, 없으면 외부 원본과 기존 파일명을 지원한다. 과거 이력의 `data_YYYYMM.csv` 요청은 삭제된 경우에만 새 표준 경로로 해석하며 임시 시험의 반대 방향도 지원한다. 파서는 정식 헤더와 레거시 SQL*Plus 헤더를 두 모드에서 모두 인식하되 원본 형식 정보도 따로 보존한다. 정식 헤더에 일괄 `skiprows=7`을 적용하지 않는다. 월별 빠른 준비의 기본 시각 정렬은 헤더 정리 전과 같은 `minute_floor`를 유지하고, 명시적으로 지정한 옵션을 우선한다.

`scripts/refresh_standardized_month_index.py`는 표준 월 파일을 한 번씩 읽어 기존 여섯 관측소·센서 범위를 함께 집계한다. 동일한 분의 G/B 중복을 제거하고 서로 다른 판정이 겹치면 충돌로 제외하는 기존 기준을 따른다. 파일의 실제 경로·크기·`mtime_ns`로 fingerprint를 만들며 확인하지 않은 수치를 0이나 완료로 채우지 않는다. `reports/monthly_anomaly_index.json`을 사용하므로 이 경로는 로컬 파일 저장소이며 운영 DB에 값을 반영하지 않는다. Z: 접근과 보호 백업·D: 원본의 변경은 실행 시 I/O 보호 장치로 차단한다.

2026-10-22 경로 검사 보완은 `workspace_paths.ensure_no_z_access`를 사용한다. 루트·CSV 별칭·자료 검사·월 스캐너가 경로 해석이나 존재 조회를 하기 전에 루트부터 연결을 확인하고, Z: 대상 문자열을 거부한다. 카탈로그는 각 하위 경로를 검사한 뒤 디렉터리에 들어가며 연결 순환과 읽을 수 없는 연결을 명시 오류로 알린다. 안전한 C: 연결·하드링크와 기존 D: 예측 경로 지원은 유지한다. 변환기는 기존 연결 경로 거부 정책을 유지하고 검사 순서를 루트부터로 바꿨다. 이 사전검사는 검사 직후 다른 프로세스가 링크를 교체하는 상황을 원자적으로 막지는 않는다.

실제 변환 결과는 월별 관측 43개·예측 45개와 다년도 하드링크 2개, 총 90개다. 관측 데이터 1,017,630,666행과 예측 데이터 365,997,600행의 바이트·순서를 보존했고, 검증한 C:의 기존 월별 관측 43개만 삭제했다. 여섯 조합의 43개월, 총 258개 인덱스 기록을 실제 스캔으로 완료했으며 추천 함수도 모든 조합에서 43개월과 대기 0개를 반환했다. 카탈로그는 D: 원본을 포함한 서로 다른 파일 경로를 보존하고 표준 파일을 먼저 표시하며, 자동 월 매칭에서만 우선 경로 하나를 고른다.

2026-10-20 현재 후보 비교는 동결된 `champion_2025`와 `candidate` 두 LSTM으로 통일한다. `scripts/comparison_contract.py`는 과거 JSON·시계열에서 두 모델의 필드만 선택하고, 학습 워커도 과거 NPZ의 추가 예측 배열을 사용하지 않는다. 원본 파일은 보존한다. API·화면·MLflow도 같은 두 모델을 사용하며, 기존 번들 재평가·재현에 `ridge_model.joblib`은 필요하지 않다. 새 번들에는 Ridge 파일을 만들지 않는다. 학습 진행은 전처리·Scaler, LSTM 학습, 두 모델 평가·임계값 탐색, Replay·MLflow 등록의 네 단계다. 과거 `ridge_fit` 기록은 전처리로 표시한다. 본 [01 문서](01_ARCHITECTURE_AND_FEATURES.md) 부록에 변경 범위와 검증을 기록하며, 학습 조건·운영 호환 DEV·승격 기준과 실제 운영 상태는 유지한다.

현재 Local QC Simulator의 6단계와 추가 4계층 경로는 [03 문서](03_LOCAL_QC_SIMULATOR_AND_EVALUATION.md)에 기록했다. `scripts/local_qc/`와 `scripts/local_qc_simulator.py`가 실제 재생과 두 계층 평가를 맡고, `evaluation_safety.py`·`model_lifecycle.py`·`local_dashboard.py`·`ui/dashboard.html`이 조회·실행·승격 검사를 연결한다. 저장소는 `reports/local_qc_simulations/<simulation_id>/`의 JSON·CSV이며 운영 DB를 사용하지 않는다.

이전 v2의 CPU 실행 환경·임계값 메타데이터·월별 집계·작업 잠금 및 학습·보정·분할 개선도 본 문서 세트(`01~04`)에 통합되어 있다. 아래 기존 API 개수와 모듈 목록은 2026-10-16 기준 기록에 Clean Core 구성을 반영한 것이다.

작성·갱신일: 2026-10-22<br>
관련 인덱스: [00_OVERVIEW_AND_INDEX.md](00_OVERVIEW_AND_INDEX.md)

---

## 1. 디렉터리 및 저장소 구조

2026-10-20 추가한 QC 경로는 다음과 같다. `GET /api/candidates/{run_id}/local_qc`는 `candLocalQcSelect`의 선택을 `get_local_qc_simulation()`과 `comparison.json`에 연결한다. `GET /api/candidates/{run_id}/local_qc/series`는 `get_local_qc_simulation_series()`로 `series.json`과 기록된 해시를 확인한다. `POST /api/candidates/{run_id}/local_qc/simulate`는 `btnRunLocalQcSim`에서 토큰·LOCK·작업 기록을 거쳐 CPU 자식 프로세스의 CLI를 실행한다. 화면의 `localQcComparisonRows`는 Tier 1과 Tier 2 online/consolidated를 각각 표시한다.

현재 공통 승격 판정은 후보 목록과 실제 승격 전에 적용한다. 선택한 후보·평가 스냅샷·전체 구간·정책·번들이 일치하는 QC 근거를 요구하며, 근거가 없거나 정상 예측 개선·운영 FP/FN 비악화 기준을 통과하지 못하면 승격을 막는다. 조회한 JSON에는 메모리에서 현재 판정을 덧붙이고 원래 파일을 보존한다. 이번 두 모델 비교 전환에서 이 기준은 변경하지 않았다. 실행 범위 TEST·ALL과 UI/API의 더 넓은 선택지 차이는 [현재 제약](04_LIMITATIONS_AND_PRODUCTION_ROADMAP.md)에 기록한다.

프로젝트 루트(`ocean-ai-platform/mlops-qc-engine`)와 상위 문서 폴더(`Ocean-AI/docs/ml-ops-docs/`), 외부 읽기 전용 데이터 작업공간(`<AI_QC_DATA_WORKSPACE>`)은 다음과 같이 역할이 분리되어 있습니다.

```text
Ocean-AI/
├── docs/
│   ├── 42_AI_QC_MLOPS_ENGINE_INTEGRATION.md # Ocean-AI ↔ 조위 AI-QC MLOps 5대 연동 및 실행 명세
│   └── ml-ops-docs/                         # 4계층 검증 기반 상세 기술 문서 6종 (00~05)
│       ├── 00_OVERVIEW_AND_INDEX.md
│       ├── 01_ARCHITECTURE_AND_FEATURES.md
│       ├── 02_USER_WEB_OPERATION_GUIDE.md
│       ├── 03_LOCAL_QC_SIMULATOR_AND_EVALUATION.md
│       ├── 04_LIMITATIONS_AND_PRODUCTION_ROADMAP.md
│       └── 05_MLOPS_GOVERNANCE_AND_POLICY.md
└── ocean-ai-platform/mlops-qc-engine/
    ├── README.md                              # Clean Core 구조 및 단독/웹 기동 안내
    ├── requirements-runtime.txt               # TensorFlow 2.10 워커 환경 패키지 명세 (63개)
    ├── requirements-cpu-runtime.txt           # CPU 전용 학습/시뮬레이션 환경 패키지 명세
    ├── requirements-mlflow.txt                # FastAPI / MLflow 2.22.1 서버 환경 패키지 명세 (91개)
    ├── manifests/
    │   ├── 2025_operation_64_manifest.json    # 2025년 운영 64개 모델 기준선 매니페스트 (schema 1.0)
    │   ├── 2025_training_archive_inventory.json # 94개 모델 보관 폴더 분류 인벤토리
    │   ├── 20261006_local_trial_manifest.json # 로컬 시험용 216개 파일 SHA-256 매니페스트 (local-trial-1)
    │   ├── active_release_pointer.json        # 현재 활성 Champion 배포 포인터 (초기값 2025_OPERATION_64_BASELINE)
    │   └── releases/                          # (.gitignore 제외, 런타임 생성) 승격/롤백 시 생성되는 REL_*.json
    ├── reports/                               # (.gitignore 제외, 런타임 생성) 스냅샷·후보 학습·시뮬레이션 산출물
    │   ├── candidate_runs/<run_id>/           # bundle/*, artifact.json, comparison.json, evaluations/*
    │   ├── local_qc_simulations/<sim_id>/     # comparison.json, series.json, receipt.json
    │   ├── dataset_previews/<dataset_id>/     # joined.csv, joined_provenance.csv, joined_labeled.csv
    │   ├── ocean_ai_snapshots/<snapshot_id>/  # snapshot.parquet, snapshot_manifest.json
    │   └── mlflow_trial/                      # 로컬 SQLite MLflow 저장소 (tracking.db)
    ├── runtime/                               # (.gitignore 제외) 격리 Python 가상환경 2종
    │   ├── python3_10_cpu_env/                # TensorFlow/Keras 2.10.0 추론·학습 워커 전용 환경
    │   └── mlflow_trial_env/                  # FastAPI + Uvicorn + MLflow 2.22.1 웹 서버·레지스트리 환경
    ├── schemas/
    │   └── operational_release_manifest.schema.json # 운영 배포 매니페스트 JSON Schema
    ├── scripts/                               # 33개 코어 모듈 (최상위 24 + local_qc/ 5 + local_qc/legacy/ 4)
    └── ui/                                    # 프론트엔드 단일 페이지 UI 2종
        ├── dashboard.html                     # 메인 AI 모델 시험실 화면 (/ · Step 1 ~ Step 4 위저드 & 드래그 월 선택기)
        └── data_preview.html                  # 학습자료 확인 및 드래그 월 선택/다중 CSV/다중 데이터셋 Ocean-AI 스냅샷 화면 (/data)
```

---

## 2. 이중 Python 가상환경 분리 아키텍처

본 시스템은 의존성 충돌 방지와 Windows 네이티브 메모리 안정성을 위해 **웹·레지스트리 제어 환경**과 **TensorFlow 모델 추론·학습 워커 환경**을 물리적으로 분리하여 운영합니다.

| 구분 | 1. 모델 추론·학습 워커 환경 (`python3_10_env_restored`) | 2. 웹 대시보드 및 MLflow 서버 환경 (`mlflow_trial_env`) |
| :--- | :--- | :--- |
| **실행 파일 경로** | `runtime/python3_10_env_restored/python.exe` | `runtime/mlflow_trial_env/Scripts/python.exe` |
| **패키지 명세 파일** | [requirements-runtime.txt](../../ocean-ai-platform/mlops-qc-engine/requirements-runtime.txt) (63개 패키지) | [requirements-mlflow.txt](../../ocean-ai-platform/mlops-qc-engine/requirements-mlflow.txt) (91개 패키지) |
| **핵심 패키지 버전** | Python `3.10.16`, `tensorflow==2.10.0`, `keras==2.10.0`, **`protobuf==3.19.6`**, `numpy==1.23.5`, `scikit-learn==1.5.0`, `pandas==2.2.3`, `pyarrow==19.0.1`, `SQLAlchemy==2.0.40` | `fastapi==0.142.2`, `uvicorn==0.54.0`, `starlette==1.7.0`, `mlflow-skinny==2.22.1`, **`protobuf==6.33.6`**, `SQLAlchemy==2.0.40`, `alembic==1.20.0`, `pandas==2.2.3`, `pyarrow==19.0.1` |
| **분리 설계 이유** | TensorFlow/Keras `2.10.0`의 모델 호환 환경(`protobuf 3.19.6`)과 웹·MLflow 제어 환경(`MLflow 2.22.1`, `protobuf 6.33.6`)을 별도 프로세스로 분리한다. 학습·평가에서는 연속 입력 버퍼와 16,384윈도우 배치 추론을 유지한다. 2026-10-16의 1년치 524,845행 학습 실패와 CPU 환경 검증은 `05 문서`의 당시 기록을 따른다. 비교 모델 제거를 Windows 접근 위반의 원인 해결로 해석하지 않는다. | FastAPI 루프백 서버(`127.0.0.1:8765`), SQLite 기반 MLflow Tracking/Registry(`reports/mlflow_trial/tracking.db`) 제어, CSV 스트리밍 결합 및 Parquet 스냅샷 생성을 담당합니다. |

---

## 3. 경로 해석기 (`scripts/workspace_paths.py`) 설계

2026-10-15 사내 Gitea 표준 경로(`ocean-ai-platform/mlops-qc-engine`) 이전 및 외부 데이터 루트 설정 분리를 위해 [workspace_paths.py](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py)를 구성했습니다.

| 함수 심볼 | 동작 및 우선순위 규칙 |
| :--- | :--- |
| [`resolve_data_workspace(base)`](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py) | 읽기 전용 데이터 작업공간(`2026년_AI_품질처리_데이터백업`, `정형데이터`, `DB_Exporting` 포함 폴더)을 다음 우선순위로 해석:<br/>1) `AI_QC_DATA_WORKSPACE` 환경변수<br/>2) `base.parent` 및 상위 디렉터리 내 마커(`DATA_WORKSPACE_MARKERS`) 존재 여부(Junction 실행 호환)<br/>3) 기본 경로 `<AI_QC_DATA_WORKSPACE>` 폴백 |
| [`resolve_export_roots()`](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py) | 외부 DB 반출 CSV 루트 3종(`export_root`, `tide_export_root`, `tide_export_utf8_root`)을 환경변수(`AI_QC_EXPORT_ROOT`, `AI_QC_TIDE_EXPORT_ROOT`, `AI_QC_TIDE_EXPORT_UTF8_ROOT`) 우선으로 해석하고 미지정 시 로컬 기본 경로로 폴백 |
| [`resolve_additional_data_roots(base)`](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py) | `resolve_export_roots()` 3종과 `AI_QC_EXTRA_DATA_ROOTS`(`os.pathsep` 구분 다중 경로)를 중복 없이 결합하여 허용 루트 리스트로 반환 |
| [`resolve_backup_code_root(base)`](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py) | `<data_workspace>/2026년_AI_품질처리_데이터백업/운영코드/AI_anomaly_detection` 반환 |
| [`resolve_backup_source_root(base)`](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py) | `<data_workspace>/2026년_AI_품질처리_데이터백업/소스코드` 반환 |
| [`resolve_manifest_root(manifest, base)`](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py) | 매니페스트 JSON의 `"root"` 필드를 해석하되, `AI_QC_DATA_WORKSPACE` 오버라이드 또는 경로 이전 시 `resolve_backup_code_root(base)`로 안전하게 폴백 |
| [`resolve_project_path(raw_path, base)`](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py) | 매니페스트·보고서에 기록된 과거 경로(`/ai_mlops_2026/`, `/ai-qc-mlops/`, 대소문자·슬래시 변형, 임의의 Git 클론 폴더명 하위의 `manifests/`, `reports/`, `runtime/` 등 `PROJECT_SUBDIRS`)를 현재 `PROJECT_ROOT` 기준으로 자동 리베이스 |

---

## 4. 전체 27개 HTTP API 엔드포인트 4계층(`UI -> API -> Logic -> Storage`) 추적표

로컬 대시보드 서버는 루프백(`127.0.0.1`) 전용이며 `TrustedHostMiddleware(allowed_hosts=["127.0.0.1", "localhost"])`와 프로세스 기동 시 발급되는 난수 토큰(`X-Dashboard-Token`, `secrets.compare_digest`), 그리고 모든 변경/평가/재생 엔드포인트에 걸친 전역 `LOCK = threading.Lock()`(`409 Conflict` 반환)으로 보호됩니다.

### 4.1 메인 대시보드 라우트 (`scripts/local_dashboard.py` — 15개 엔드포인트)

| # | HTTP Method & Path | UI 호출 지점 ([ui/dashboard.html](../../ocean-ai-platform/mlops-qc-engine/ui/dashboard.html)) | API 핸들러 ([scripts/local_dashboard.py](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py)) | 도메인/실행 로직 (Logic Tier) | 대상 DB 및 파일 저장소 (Storage Tier) |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 1 | `GET /` | 브라우저 초기 진입 | [`home()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) | `ui/dashboard.html` 로드 및 `__TOKEN__` 치환 | `ui/dashboard.html` (Read) |
| 2 | `GET /api/state` | [`refresh()`](../../ocean-ai-platform/mlops-qc-engine/ui/dashboard.html) (초기 로드 및 2.5초 주기 폴링) | [`state()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) → [`snapshot()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) | 매니페스트 64개 모델·관측소/센서 친화 한글명(`station_display`, `sensor_display`) 결합, 로컬 실행 이력, SQLite 레지스트리 카운트, `list_candidate_runs()`, `list_snapshots()`, `active_release_state()` 집계 | - `manifests/20261006_local_trial_manifest.json`<br/>- `reports/local_runs/*/run.json`, `results.json`<br/>- `reports/mlflow_trial/tracking.db` (`?mode=ro`)<br/>- `reports/dashboard_jobs/*/job.json`<br/>- `reports/candidate_runs/*/artifact.json`<br/>- `reports/ocean_ai_snapshots/*/snapshot_manifest.json`<br/>- `manifests/active_release_pointer.json` |
| 3 | `POST /api/jobs/{kind}` | `document.querySelectorAll('[data-job]')` 버튼 4종 (`validate`, `models`, `replay`, `register`) | [`start_job()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) (토큰 검증 + `LOCK.acquire(blocking=False)`) | 백그라운드 스레드 `execute_job()` 기동 (`validate`, `models`, `replay`, `register`) | - `reports/dashboard_jobs/<job_id>/job.json`<br/>- `reports/local_runs/<run_id>/*`<br/>- `reports/mlflow_trial/tracking.db` |
| 4 | `GET /api/pipeline/recommend_test_months` | `loadTestMonthRecommendations()` (`#testMonthRecommendBox`, `#testMonthRecommendCards`, `#step3RecommendHint`) | [`get_recommended_test_months()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) | [`preview.recommend_test_months(station, sensor, exclude_yms)`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_preview.py) (미학습 월 및 실제 `MQC_FLAG == 'B'` 이상치 다수 포함 추천 월·전체 최다 이상치 챔피언 산출) | `reports/dataset_previews/*/dataset_manifest.json`, `reports/ocean_ai_snapshots/*/snapshot_manifest.json`, 허용 CSV 카탈로그 |
| 5 | `POST /api/pipeline/quick_prepare` | `#btnQuickPrepareSnapshot` (`#quickMonthGrid` 마우스 드래그 `selected_yms` 및 다중 CSV 지원) | [`quick_prepare_snapshot()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) (토큰 검증 + `LOCK.acquire(blocking=False)`) | 선택한 관측소·센서·연월(`selected_yms` 배열 또는 `date_start`~`date_end`)의 `data_YYYYMM.csv` + `GO_TIDE_PRE_DATA_YYYYMM.csv`(또는 사용자 지정 `observation_paths`·`prediction_paths`)를 매칭하여 `dataset_preview.analyze()` 및 `ParquetSnapshotAuthority.build_from_dataset()` 일괄 실행 후 `{"dataset", "snapshot", "matched_observation_paths", "matched_prediction_paths", "selected_yms"}` 반환 | - `reports/dataset_previews/<dataset_id>/{joined.csv, joined_provenance.csv, joined_labeled.csv, dataset_manifest.json}`<br/>- `reports/ocean_ai_snapshots/<snapshot_id>/{snapshot.parquet, labeled_anomalies.csv, snapshot_manifest.json}` |
| 6 | `POST /api/candidates/train` | `#btnTrainCandidate` (`#candSnapshotSelect` 및 동일 관측소·센서로 필터링된 `#candTrainEvalSnapshotSelect` 포함) | [`start_candidate_train()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) (토큰 검증 + `LOCK.acquire(blocking=False)`) | `execute_job("candidate_train")` → `run_candidate_training_subprocess()` → `train_and_evaluate()`(회귀 + 100점 만점 F1 이상치 분류) + `register_candidate_in_mlflow()` + (지정 시) `run_candidate_evaluation_subprocess()` | - `reports/dashboard_jobs/<job_id>/job.json`<br/>- `reports/candidate_runs/<run_id>/bundle/*`, `artifact.json`, `comparison.json`, `comparison_train_test.json`, `replay_verification.json`, `series_comparison.json`, `paired_test_predictions.npz`<br/>- `reports/mlflow_trial/tracking.db` (`candidate` alias) |
| 7 | `GET /api/candidates` | API 직접 조회 | [`get_candidates()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) | `lifecycle.list_candidate_runs()` | `reports/candidate_runs/*/artifact.json`, `comparison.json`, `reports/mlflow_trial/tracking.db` |
| 8 | `GET /api/candidates/{run_id}/series` | `loadCandidateChart(runId, chartKey)` (`#candChartArea`, `#candChartAnomalySummary`) | [`get_candidate_series()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) | 정규식 검증 후 `series_comparison.json` 반환(정상 시계열 + `anomaly_points` 이상치 탐지 마커 포함) | `reports/candidate_runs/<run_id>/series_comparison.json` |
| 9 | `POST /api/candidates/{run_id}/replay` | `#btnVerifyReplay` (`재현성(Replay=True) 검증`) | [`verify_candidate_replay()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) (토큰 검증 + `LOCK.acquire(blocking=False)`) | `lifecycle.run_candidate_replay_subprocess()` → `evaluate_bundle_on_test(..., replay=True)` | `reports/candidate_runs/<run_id>/paired_test_predictions.npz` (대조), `replay_verification.json` (갱신) |
| 10 | `POST /api/candidates/{run_id}/evaluate` | `#btnEvaluateOnSnapshot` (`선택한 테스트 기간으로 기존 운영 모델과 비교 실행`) 및 `#btnRestoreTrainTestEval` (`원본 학습 TEST 결과로 복귀`) | [`evaluate_candidate_on_snapshot()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) (토큰 검증 + `LOCK.acquire(blocking=False)`) | `lifecycle.run_candidate_evaluation_subprocess(run_id, eval_snapshot_id, eval_scope)` → `evaluate_bundle_on_snapshot()` | `reports/candidate_runs/<run_id>/{comparison.json, comparison_train_test.json, series_comparison.json, series_train_test.json, evaluations/eval_*.json}` |
| 11 | `POST /api/candidates/{run_id}/promote` | `#btnPromoteCandidate` (`선택 후보를 Champion으로 승격`) | [`promote_candidate()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) (토큰 검증 + `LOCK.acquire(blocking=False)`) | `lifecycle.promote_candidate_to_champion()` → 스키마 검증 및 MLflow 별칭 전환(`candidate -> champion`, 이전 버전 `rollback`) | - `manifests/releases/<release_id>.json`<br/>- `manifests/active_release_pointer.json`<br/>- `reports/deployments/<deployment_id>.json`<br/>- `reports/mlflow_trial/tracking.db` |
| 12 | `POST /api/deployments/rollback` | `#btnRollbackModel` (`#rollbackTargetSelect` 기준) 및 `#activeReleaseRows` 행별 `즉시 롤백` 버튼 | [`rollback_deployment()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) (토큰 검증 + `LOCK.acquire(blocking=False)`) | `lifecycle.rollback_champion()` → MLflow 별칭 복구(`rollback -> champion`, 강등 버전 `candidate`) 및 롤백 릴리스 매니페스트 발행 | - `manifests/releases/REL_ROLLBACK_*.json`<br/>- `manifests/active_release_pointer.json`<br/>- `reports/deployments/DEP_ROLLBACK_*.json`<br/>- `reports/mlflow_trial/tracking.db` |
| 13 | `GET /api/deployments/active` | API 직접 조회 | [`get_active_deployment()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) | `lifecycle.active_release_state()` | `manifests/active_release_pointer.json` |
| 14 | `GET /api/deployments/resolve/{station}/{sensor}` | `#btnResolveBundle` (`#resolveTargetSelect` 기준 런타임 활성 번들 해석 및 해시 검증) | [`resolve_active_bundle()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) | [`release_pointer_consumer.resolve_runtime_bundle(station, sensor, verify_hash=True)`](../../ocean-ai-platform/mlops-qc-engine/scripts/release_pointer_consumer.py) | `manifests/active_release_pointer.json`, `manifests/releases/REL_*.json`, `manifests/20261006_local_trial_manifest.json` |
| 15 | `GET /api/series/{run_id}/{station}/{sensor}` | `detail()` (하단 모델 테이블 `#rows` 행 클릭 시) | [`series()`](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py) | 허용 `run_id` 및 64개 `(station, sensor)` 쌍 검증 후 재생 시계열 JSON 반환 | `reports/local_runs/<run_id>/replay_inputs/<station>_<sensor>.json` |

### 4.2 학습자료 및 스냅샷 라우트 (`scripts/dataset_routes.py` — 12개 엔드포인트)

| # | HTTP Method & Path | UI 호출 지점 ([ui/data_preview.html](../../ocean-ai-platform/mlops-qc-engine/ui/data_preview.html)) | API 핸들러 ([scripts/dataset_routes.py](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py)) | 도메인/실행 로직 (Logic Tier) | 대상 DB 및 파일 저장소 (Storage Tier) |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 16 | `GET /data` | 브라우저 `/data` 진입 | [`data_page()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | `ui/data_preview.html` 로드 및 `__TOKEN__` 치환 | `ui/data_preview.html` (Read) |
| 17 | `GET /api/data/catalog` | `init()` (페이지 초기 로드 시) | [`data_catalog()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | [`preview.catalog()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_preview.py) (환경변수 포함 허용 루트의 CSV 목록 및 `mappingBySea.csv` 로드, `station_display`·`sensor_display` 포함) | `D:\261002_greenblue\...`, `D:\261008_gb_temp\output`, `정형데이터`, `DB_Exporting`, `debug_logs`, `mappingBySea.csv` |
| 18 | `POST /api/data/profile` | `#inspect`, `#inspectPrediction`, 프리셋 버튼 | [`data_profile()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) (토큰 검증) | [`preview.profile()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_preview.py) (경로 검증, 상위 5행 스캔, `sqlplus_gd_obs_st_detected` 판별) | 선택된 로컬 CSV 파일 (Read-Only 상위 5행) |
| 19 | `POST /api/data/analyze` | `#analyze` (`자료 결합·검사 실행`, 단일/다중 `observation_paths`·`prediction_paths` 지원) | [`data_analyze()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) (토큰 검증 + `lock.acquire(blocking=False)`) | 백그라운드 스레드 `worker()` → [`preview.analyze()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_preview.py) (전후 SHA-256 검증, `MQC_FLAG=='G'` 정상 및 `'B'` 이상치 분리 보존, 시각 정렬, 중복 충돌 배제) | - `reports/dataset_jobs/<job_id>/job.json`<br/>- `reports/dataset_previews/<dataset_id>/{joined.csv, joined_provenance.csv, joined_labeled.csv, dataset_manifest.json}` |
| 20 | `GET /api/data/jobs/{job_id}` | `checkJob(id)` (1.5초 주기 폴링) | [`data_job()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | 진행 상태 조회 및 완료 시 `preview.load_result()` 결합 | `reports/dataset_jobs/<job_id>/job.json`, `reports/dataset_previews/<dataset_id>/dataset_manifest.json` |
| 21 | `GET /api/data/result/{data_id}/{kind}` | `#downloads` 내 다운로드 링크 4종 (`csv`, `provenance_csv`, `labeled_csv`, `manifest`) | [`data_download()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | 매니페스트 기록과 실제 파일 SHA-256 일치 검증 후 `FileResponse` 반환 | `reports/dataset_previews/<data_id>/{joined.csv, joined_provenance.csv, joined_labeled.csv, dataset_manifest.json}` |
| 22 | `GET /api/data/history` | `history()` (`#history` 및 `#multiDatasetCheckboxes` 갱신) | [`data_history()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | 최근 20개 `dataset_manifest.json` 요약 목록(`anomaly_minutes` 포함) 반환 | `reports/dataset_previews/*/dataset_manifest.json` |
| 23 | `GET /api/data/results/{data_id}` | `#history.onchange` | [`data_result()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | `preview.load_result(data_id)` | `reports/dataset_previews/<data_id>/dataset_manifest.json` |
| 24 | `GET /api/data/snapshots` | `history()` (`#snapshotRows` 테이블 갱신) | [`list_snapshots()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | `ParquetSnapshotAuthority.list_snapshots()` | `reports/ocean_ai_snapshots/*/snapshot_manifest.json` |
| 25 | `POST /api/data/snapshots` | `#buildSnapshotBtn` (단일 `dataset_id`) 및 `#buildMergedSnapshotBtn` (다중 `dataset_ids`) | [`create_snapshot()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) (토큰 검증 + `lock.acquire(blocking=False)`) | `dataset_ids` 배열이면 `build_from_datasets()`, 단일 `dataset_id`이면 `build_from_dataset()` 호출 | `reports/ocean_ai_snapshots/<snapshot_id>/{snapshot.parquet, labeled_anomalies.csv, snapshot_manifest.json}` |
| 26 | `GET /api/data/snapshots/{snapshot_id}` | API 직접 조회 | [`get_snapshot()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | `ParquetSnapshotAuthority.validate_snapshot()` 검증 후 매니페스트 반환 | `reports/ocean_ai_snapshots/<snapshot_id>/snapshot_manifest.json` |
| 27 | `GET /api/data/snapshots/{snapshot_id}/download/{kind}` | `#snapshotRows` 내 `Parquet` · `Manifest` 다운로드 링크 | [`download_snapshot()`](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py) | `validate_snapshot()` 통과 시 `snapshot.parquet` 또는 `snapshot_manifest.json` 반환 | `reports/ocean_ai_snapshots/<snapshot_id>/{snapshot.parquet, snapshot_manifest.json}` |

---

## 5. `scripts/` 내 19개 모듈별 상세 명세 (심볼 · 알고리즘 · 입출력)

### 5.1 패키지 및 경로 기반 모듈 (2개)
1. **[scripts/__init__.py](../../ocean-ai-platform/mlops-qc-engine/scripts/__init__.py)**
   - **역할**: `scripts` 디렉터리를 `sys.path`에 자동 등록하여 상위 모듈(`scripts.xxx`) 임포트와 직접 모듈(`xxx`) 임포트 양쪽 모두에서 `PYTHONPATH` 없이 동작하도록 보장합니다.
2. **[scripts/workspace_paths.py](../../ocean-ai-platform/mlops-qc-engine/scripts/workspace_paths.py)**
   - **핵심 심볼**: `PROJECT_ROOT`, `DEFAULT_DATA_WORKSPACE`, `resolve_data_workspace`, `resolve_export_roots`, `resolve_additional_data_roots`, `resolve_backup_code_root`, `resolve_backup_source_root`, `resolve_manifest_root`, `resolve_project_path`.
   - **역할**: 저장소 물리 이전, 환경변수 기반 외부 반출 루트 오버라이드, 타 PC 클론 시에도 외부 백업 루트와 내부 산출물 경로를 일관되게 해석합니다.

### 5.2 Phase 1 기준선 · 환경 복원 · 정적 분석 모듈 (3개)
3. **`scripts/build_baseline_manifest.py`**
   - **역할**: `2026년_AI_품질처리_데이터백업/소스코드`를 스캔하여 64개 운영 모델의 필수 파일 3종 해시를 기록한 [manifests/2025_operation_64_manifest.json](../../ocean-ai-platform/mlops-qc-engine/manifests/2025_operation_64_manifest.json)과 94개 보관 폴더 분류표 [manifests/2025_training_archive_inventory.json](../../ocean-ai-platform/mlops-qc-engine/manifests/2025_training_archive_inventory.json)을 생성합니다.
4. **`scripts/restore_and_smoke_test.py`**
   - **역할**: `python3_10_env.tar.gz`의 경로 이탈 여부를 사전 검사한 뒤 `runtime/python3_10_env_restored`에 안전하게 압축 해제하고, CPU 전용 단건 추론 프로브를 실행하여 `reports/environment_restore_smoke_test.json`에 기록합니다.
5. **`scripts/scan_legacy_configuration.py`**
   - **역할**: 레거시 Python 스크립트 9개를 Python `ast`로 파싱하여 설정 위치를 식별하되 실제 값은 모두 `"REDACTED"`로 마스킹하여 `reports/legacy_configuration_inventory.json`에 저장합니다.

### 5.3 로컬 시험 매니페스트 · 오프라인 모델/재생 검증 · MLflow 등록 모듈 (6개)
6. **[scripts/local_trial_manifest.py](../../ocean-ai-platform/mlops-qc-engine/scripts/local_trial_manifest.py)**
   - **역할**: `local-trial-1` 스키마 기준 64개 모델 및 소스·BAT·매핑·공통 임계값 총 **216개 파일**의 크기·SHA-256 해시·`ai_flag_position == 11`·`operational_deployment is False`를 검증합니다.
7. **[scripts/run_record_wrapper.py](../../ocean-ai-platform/mlops-qc-engine/scripts/run_record_wrapper.py)**
   - **역할**: 오프라인 시험(`models` 또는 `replay`) 실행 전후에 `validate(manifest)`와 스크립트 자체 SHA-256 해시 불변 여부를 대조하고, `reports/local_runs/<run_id>/run.json`, `stdout.log`, `stderr.log`를 기록합니다.
8. **[scripts/offline_model_suite.py](../../ocean-ai-platform/mlops-qc-engine/scripts/offline_model_suite.py)**
   - **역할**: 64개 모델 CPU 고정 입력 추론(`model_test`) 및 과거 상세 로그 정상 연속 4분 입력창 재생 비교(`replay_test`, 모델별 자식 프로세스 호출)를 수행합니다.
9. **[scripts/replay_prediction_worker.py](../../ocean-ai-platform/mlops-qc-engine/scripts/replay_prediction_worker.py)**
   - **역할**: 단일 `(station, sensor)` 모델만 독립 프로세스에서 로드·추론하고 `reports/local_runs/<run_id>/replay_inputs/<station>_<sensor>.json`을 생성합니다.
10. **`scripts/probe_replay_runtime.py`**
    - **역할**: 특정 관측소·센서 입력(`.npz`)과 `--onednn` 설정에 따른 네이티브 충돌 원인을 단독 프로세스에서 진단하는 CLI 도구입니다.
11. **[scripts/register_mlflow_trial.py](../../ocean-ai-platform/mlops-qc-engine/scripts/register_mlflow_trial.py)**
    - **역할**: 로컬 SQLite(`reports/mlflow_trial/tracking.db`)에 `OceanDB_AI_LOCAL_TRIAL` 실험 및 64개 `LOCAL_TRIAL_<station>_<sensor>` 모델을 등록(`trial` 별칭)하고 192개 아티팩트 다운로드 SHA-256 일치를 검증합니다.

### 5.4 Step 1 데이터셋 결합 · MQC_FLAG=B 보존 · 테스트 추천 달 · Ocean-AI 스냅샷 모듈 (3개)
12. **[scripts/dataset_preview.py](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_preview.py)**
    - **핵심 심볼**: `friendly_station_label`, `friendly_sensor_label`, `recommend_test_months`, `allowed_roots`, `source_path`, `normalize_header`, `rows`, `profile`, `catalog`, `timestamp`, `read_values`, `_read_multiple_values`, `continuity`, `_count_labeled_anomaly_eval_windows`, `analyze`, `load_result`.
    - **핵심 알고리즘**:
      - **친화적 한글 관측소·센서 명칭 및 추천 테스트 달 산출**: `friendly_station_label`(`DT_0001` → `인천 조위관측소`)과 `friendly_sensor_label`(`TIDE_LEVEL_LASER` → `LASER 센서`, `TIDE_LEVEL_LASER_1` → `LASER 1호 센서`), 그리고 학습 제외 월(`exclude_yms`) 외의 미학습 기간(예: `202601`, `202603`) 및 실제 `MQC_FLAG == 'B'` 최다 포함 달을 추천하는 `recommend_test_months()`를 제공합니다.
      - **허용 루트 제한**: `WORKSPACE`, `BASE` 및 `resolve_additional_data_roots()`가 반환하는 외부 반출 루트 하위의 `.csv` 파일만 읽습니다.
      - **SQL*Plus 정규화(`sqlplus_gd_obs_st`) 및 시각 정렬(`minute_floor`)**: 7컬럼 절단 헤더 정규화 및 비정각 시각 분 버킷 정렬(`source_obs_timestamp` 원본 보존)을 수행합니다.
      - **정상(`G`) 학습 데이터 + 이상치(`B`) 정답 라벨 분리 보존**: 기존 `joined.csv`와 `valid_minutes`는 `MQC_FLAG == 'G'`만 수록하여 학습 무결성을 100% 보존하고, 동시에 `MQC_FLAG in ('G', 'B')` 행을 `joined_labeled.csv`에 별도 기록하며 `anomaly_minutes` 및 `contiguous_labeled_4g_input_1b_target_windows`를 산출합니다.
13. **[scripts/ocean_ai_snapshot.py](../../ocean-ai-platform/mlops-qc-engine/scripts/ocean_ai_snapshot.py)**
    - **핵심 심볼**: `_contiguous_windows_for_frame`, `ParquetSnapshotAuthority` (`build_from_dataset`, `build_from_datasets`, `validate_snapshot`, `load_snapshot`, `extract_split_windows`, `extract_labeled_evaluation_windows`, `list_snapshots`).
    - **핵심 알고리즘**:
      - 정상(`G`) 행만을 시간순 `TRAIN (0.70) / VALIDATION (0.15) / TEST (0.15)`로 분할하고 분할 경계를 넘지 않는 4+1 연속창을 추출하여 `snapshot.parquet`에 저장합니다.
      - 원본 데이터셋들의 `joined_labeled.csv`에서 `MQC_FLAG == 'B'` 행을 병합하여 스냅샷 폴더 내 `labeled_anomalies.csv`에 별도 보존하고, `extract_labeled_evaluation_windows(snapshot_id, manifest=..., splits=...)` 호출 시 이상치가 0건이면 즉시 조기 반환하며, 이상치가 존재할 때는 `iterrows()` 없이 벡터화(`.tolist()` + `zip`)된 순회로 `TEST` 정상(`G`, label `0`) 윈도우와 이상치(`B`, label `1`) 평가 윈도우를 반환합니다.
14. **[scripts/dataset_routes.py](../../ocean-ai-platform/mlops-qc-engine/scripts/dataset_routes.py)**
    - **역할**: `/data` 화면 및 `/api/data/*` 12개 엔드포인트를 등록하며, `POST /api/data/analyze`와 `POST /api/data/snapshots` 모두 `lock.acquire(blocking=False)`로 보호합니다.

### 5.5 Step 2 ~ Step 4 후보 학습 · 두 LSTM 비교 · 이상치 시계열 · 교차 평가 · 승격/롤백 (2026-10-20 비교 범위 반영)
15. **[scripts/candidate_training_worker.py](../../ocean-ai-platform/mlops-qc-engine/scripts/candidate_training_worker.py)**
    - **핵심 심볼**: `compute_effective_threshold`, `scale_windows`, `inverse_obs`, `predict_keras_model`, `metrics_summary`, `classification_metrics_summary`, `_build_comparison_series_payload`, `load_champion_2025_assets`, `evaluate_bundle_on_test`, `evaluate_bundle_on_snapshot`, `train_and_evaluate`.
    - **핵심 알고리즘**:
      - **학습 자료만 사용하는 스케일링과 후보 LSTM 학습**: `TRAIN` 분할에만 `RobustScaler`를 맞추고, 연속 `np.float32` 입력으로 Keras LSTM(`(4,2) -> LSTM(64) -> Dense(1)`)을 학습하며 16,384윈도우 단위로 추론한다. 과거 1년치 학습의 367,045개 TRAIN 창은 2026-10-16 당시 검증 규모로 남긴다.
      - **임계값과 운영 호환 DEV**: 검증 구간 보정·실제 B가 없을 때의 계단형 대체 계산·배포 DEV 인코딩은 [03 문서](03_LOCAL_QC_SIMULATOR_AND_EVALUATION.md)의 기준을 유지한다. 두 모델 전환을 이유로 임계값이나 승격 검사를 완화하지 않는다.
      - **두 LSTM의 회귀·실제 이상치 분류·시계열·교차 평가**: 동일 TEST 또는 지정한 외부 스냅샷에서 `champion_2025`와 `candidate`만 추론한다. `comparison_train_test.json`, `evaluations/eval_<tag>.json`, `series_comparison.json`과 새 예측 NPZ에도 두 모델의 결과만 저장한다. 과거 네 모델 파일은 읽을 때 두 모델만 선택하며 원본을 다시 쓰지 않는다. `replay=True`의 두 LSTM 예측 일치와 필요한 모델·scaler·임계값 해시 검사는 유지한다.
16. **[scripts/model_lifecycle.py](../../ocean-ai-platform/mlops-qc-engine/scripts/model_lifecycle.py)**
    - **역할**: 후보 학습·외부 평가를 별도 프로세스에서 실행하고, 과거 결과도 두 LSTM만 조회·등록한다. MLflow의 새 비교 지표와 결과 파일에서 추가 모델은 제외하며 후보 LSTM 버전을 등록한다. 명시적으로 승격·롤백을 실행할 때만 기존 검사 기준에 따라 별칭·릴리스·활성 포인터를 갱신한다. 이번 1:1 전환에서는 실제 승격이나 운영 DB 갱신을 하지 않는다.
17. **[scripts/release_pointer_consumer.py](../../ocean-ai-platform/mlops-qc-engine/scripts/release_pointer_consumer.py)**
    - **핵심 심볼**: [`resolve_runtime_bundle(station, sensor, verify_hash=True)`](../../ocean-ai-platform/mlops-qc-engine/scripts/release_pointer_consumer.py), `main()`.
    - **역할**: 원본 레거시 추론 스크립트를 수정하지 않고 외부에서 `active_release_pointer.json` 및 활성 `operational_release_manifest`를 읽어, 관측소·센서별 현재 활성 모델(`model`), 스케일러(`scaler`), 임계값(`threshold`)의 실제 파일 경로와 SHA-256 무결성(`hash_verified: True`), 계단형 유효 임계값을 즉시 해석·반환합니다.
18. **[scripts/local_dashboard.py](../../ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py)**
    - **핵심 심볼**: `app`, `TOKEN`, `LOCK`, `snapshot`, `execute_job`, `build_arg_parser`, 라우트 핸들러(`get_recommended_test_months`, `evaluate_candidate_on_snapshot` 포함), `main`.
    - **역할**: `127.0.0.1:8765` 단일 워커(`workers=1`) Uvicorn 서버를 구동하며 메인 대시보드(Depth 1 현황판 + Step 1~4 위저드)와 데이터 라우트를 통합 제공합니다.
19. **[scripts/ocean_ai_bridge.py](../../ocean-ai-platform/mlops-qc-engine/scripts/ocean_ai_bridge.py)**
    - **역할**: `Ocean-AI` 플랫폼 백엔드([qc_mlops_bridge.py](../../ocean-ai-platform/backend/app/services/qc_mlops_bridge.py))와 연동하여 스냅샷·후보 모델·재학습 이력·승인 이력 번들을 추출(`export_ocean_ai_bundle()`)하고 `Ocean-AI` MLOps 화면(`http://127.0.0.1:5173/mlops`)에서 원클릭 동기화(`POST /api/mlops/qc-engine/sync`) 및 워크벤치 서버 기동(`POST /api/mlops/qc-engine/start`)을 지원합니다.



---

## 부록: Champion 2025 vs 신규 후보(Candidate) 1:1 LSTM 비교 구조 상세

# Champion 2025와 신규 후보 1:1 비교 구현 계획

> 구현에는 executing-plans와 test-driven-development 절차를 적용했으며 당시에는 사용자 지시에 따라 commit·push를 하지 않았다. 이후 별도 전송 요청의 결과는 [42_AI_QC_MLOPS_ENGINE_INTEGRATION.md](../42_AI_QC_MLOPS_ENGINE_INTEGRATION.md)에 기록한다.

이 문서의 `reports/` 링크는 작성 PC에 보존한 로컬 검증 근거다. 해당 결과 JSON·로그·모델·자료는 이번 소스 전송에 포함하지 않으므로 원격 저장소에서는 열리지 않을 수 있다.

**목표:** 현재 배포 후보인 LSTM 두 모델만 학습 결과·비교표·차트·조회 응답에서 비교한다.

**구조:** 새 워커는 `champion_2025`와 `candidate`만 추론·저장한다. 과거 네 모델 자료는 조회 시 두 모델로 투영하고 원본은 보존한다. 원본 운영 번들과 승격 기준은 바꾸지 않는다.

**기술:** Python unittest, TensorFlow/Keras 2.10 HDF5, NumPy, joblib scaler, MLflow, FastAPI, JavaScript.

**승인된 명세:** 2026-10-20 사용자 메시지의 구현 범위와 `00_OVERVIEW_AND_INDEX.md`의 같은 날짜 1:1 전환 항목.

## 공통 제약

- 원본 백업과 기존 `reports/candidate_runs/*`, `reports/local_qc_simulations/*` 파일은 수정하거나 삭제하지 않는다.
- 활성 릴리스·운영 DB·로컬 MLflow DB는 갱신하지 않는다. 새 회귀시험은 임시 경로와 가짜 등록 클라이언트를 사용한다.
- `champion_2025`는 동결된 2025 비교 기준이며, 현재 활성 포인터의 버전으로 바꾸지 않는다.
- 학습·임계값·Tier 1·Tier 2 검사 기준과 판정은 보존한다.
- 파일 수정 직후 자체 검토와 Serena 정적 진단을 수행한다. Python 텍스트 수정은 UTF-8을 명시한다.
- commit·push는 하지 않는다. 기존 변경된 문서 내용은 보존한다.

## 구현과 검증 순서

1. [x] 선행 시험: 새 비교·시계열은 두 모델만 포함하고, 과거 네 모델 자료도 두 모델로 조회되며 원본은 같고, Ridge 없는 번들 재현·재평가와 과거 `ridge_fit` 표시가 동작한다는 계약을 추가한다. 구현 전 실패를 확인한다.
2. [x] 워커: Persistence·Ridge 계산·저장·메타데이터를 제거하고 새 예측 배열·시계열·TEST·외부 평가·재현 검사를 두 모델로 통일한다. scaler·LSTM·DEV·검증 기준은 유지한다.
3. [x] 조회·등록: MLflow 지표·아티팩트 등록, 후보 요약·시계열 API에서 두 모델만 소비한다. 과거 Ridge 자산의 부재·손상을 두 LSTM 자산의 검증과 분리한다.
4. [x] 화면: 표·범례·선·툴팁·학습 상태·탭 문구를 두 모델로 통일한다. `ridge_fit`은 과거 기록 읽기용으로만 남긴다.
5. [x] 문서: 현재 설명을 두 모델로 갱신하고 이전 검증 수치·이력의 네 모델 설명은 과거 기록으로 표시한다.
6. [x] 검증: 두 환경에서 `AI_QC_ENFORCE_V2_TDD=1` 전체 unittest, Python 정적 진단, JavaScript `node --check`, UI/API/처리/저장 계약, 보호 파일 해시 대조와 독립 리뷰를 수행한다.

## 리뷰 초점

과거 JSON의 추가 모델 키, Ridge가 없는 번들, 과거 NPZ의 추가 배열, 늦게 도착한 UI 응답, 빈 시계열·B=0 자료를 확인한다. 해시 검증을 생략하거나 승격 기준을 완화하지 않는다.

## 진행·검증 결과

작업 전 변경 상태를 기록했다. `00_OVERVIEW_AND_INDEX.md`와 `documentation/README.md`의 기존 내용은 유지하면서 이번 명세를 추가했고, 기존 후보·활성 포인터의 변경 상태도 보존했다. 아래는 이번 작업에서 실제로 실행한 검증이다.

독립 리뷰에서 표시용 F1을 반올림한 뒤 순위를 매기면 실제 우열과 달라질 수 있는 문제를 확인했다. `duel_comparison()`은 원시 TP·FP·FN으로 계산한 점수를 우선하고, 실제 B가 없는 경우의 정상 점수와 누락 정보는 구분한다. 두 모델의 상태가 모두 TN이라고 확인된 진단 전용 이벤트만 제외하며, 상태가 빠진 과거 이벤트는 보존한다. 이 두 경우는 선행 실패 시험으로 재현한 뒤 수정했다.

과거 네 모델 MLflow 실행에 새 두 모델 태그만 붙이는 재사용도 막았다. `candidate_run_id`와 `comparison_contract='champion-candidate-1'`이 함께 일치하는 실행만 재사용한다. 과거 실행·버전·산출물은 보존하고 두 모델 전용 실행·버전을 별도로 등록하며, 이미 두 모델로 등록한 실행의 반복 호출은 같은 실행·버전을 사용한다. 이 경로도 가짜 클라이언트의 선행 실패 시험으로 확인했다.

임시 CSV 180행에서 스냅샷 생성, 실제 CPU LSTM 1epoch 학습, HDF5·scaler·DEV 저장과 재로딩, 두 모델 TEST 평가, 비트 단위 재현, 저장 TEST 재평가를 실행했다. 실제 운영 모델 학습이나 기존 후보 재학습은 실행하지 않았다. Python 15파일의 Serena 진단은 비어 있고, 추출한 화면 JavaScript의 `node --check`와 UI 동작 시험도 통과했다.

## 최종 전체 시험

다음 표는 1:1 비교 구현 당시의 검증 기록이다. 이후 2026-10-21 전송 전 등록 파일 해시 보완과 추가 회귀시험의 최종 결과는 [42_AI_QC_MLOPS_ENGINE_INTEGRATION.md](../42_AI_QC_MLOPS_ENGINE_INTEGRATION.md)에 기록한다.

두 환경에서 `AI_QC_ENFORCE_V2_TDD=1`을 설정하고 각 환경의 `Scripts/python.exe -X utf8 -m unittest discover -s tests -v`를 순차 실행했다.

| 환경 | 전체 | 통과 | 건너뜀 | 실패 | 오류 |
|---|---:|---:|---:|---:|---:|
| mlflow_trial_env | 291 | 281 | 10 | 0 | 0 |
| python3_10_cpu_env | 291 | 258 | 33 | 0 | 0 |

제어 환경의 TensorFlow 시험은 CPU 환경에서 실행하고, CPU 환경에서 필요한 FastAPI 시험은 제어 환경에서 확인한다. 환경 재호출 경계 시험도 해당 조건에 따라 건너뛴다. 실제 CPU 학습 시험은 CPU 환경에서 통과했다. 전체 명령·소요 시간·종료 코드와 원본 로그 경로는 `시험 집계`에 기록했다.

## UI → API → 처리 → 저장 변경

| 계층 | 파일 | 변경 |
|---|---|---|
| UI | `ui/dashboard.html` | 표·곡선·범례·툴팁·샘플링·이벤트를 두 LSTM으로 통일했다. 학습은 네 단계이며 과거 `ridge_fit`은 전처리로 표시한다. |
| API | `scripts/local_dashboard.py` | 후보 시계열 응답을 두 모델로 변환하며 저장 파일은 바꾸지 않는다. |
| 처리 | `scripts/candidate_training_worker.py` | Persistence·Ridge 함수·의존성·학습·추론·임계값 보정·저장과 관련 메타데이터를 제거했다. TEST·외부 평가·캐시 복원·재현을 두 모델로 통일했다. |
| 조회·등록 | `scripts/model_lifecycle.py`, `scripts/comparison_contract.py` | 과거 결과의 두 모델 조회, 정확한 F1 순위, 과거·현재 MLflow 등록 구분과 필수 자산 검증을 연결했다. 과거 Ridge 자산은 요구하지 않는다. |
| 저장 | 새 실행의 JSON·NPZ·번들·MLflow 등록 | 새 예측·지표에는 두 모델만 포함하며 새 Ridge 파일을 만들지 않는다. 모델·scaler·DEV·임계값 metadata는 함께 관리한다. |

시험 11파일을 수정·추가했다. 변경 파일 목록과 Python·JavaScript 문법 결과는 `정적 검사`, LSP 결과는 `Serena 진단`에 기록했다. 독립 리뷰에서 확인한 두 문제와 근거가 불완전한 이벤트 처리도 실패 시험을 먼저 실행한 뒤 수정했으며, 수정 후 위 전체 시험을 다시 통과했다.

## 기존 자료 보존과 실행 범위

보호 대상 8그룹의 23,999파일, 15,091,351,349 bytes를 SHA-256으로 작업 전후 대조했다. 원본 백업 23,336파일과 기존 후보 364파일, QC 결과 284파일, 활성 포인터·릴리스·배포 기록·기준 manifest·MLflow DB의 파일 이름과 해시가 모두 같았다. 결과는 `보존 검사`의 `all_unchanged=true`로 확인했다.

실제 MLflow 등록은 가짜 클라이언트 시험으로 격리했고, 모델 승격·배포·운영 DB 갱신·commit·push는 수행하지 않았다. Git HEAD도 작업 전후 `a03f13023c97f79e0c3c945a33f7457c4423f9cc`로 같다. 이미 실행 중인 웹 서버가 있으면 재시작해야 새 Python 처리 코드를 사용한다.

## 2026-10-21 전송 전 등록 파일 해시 보완

두 모델로 변환해 업로드하는 `comparison.json`과 등록용 `artifact.json`의 `comparison_sha256`이 어긋나는 결함을 전송 검토에서 확인했고, 사용자가 수정 후 커밋·push를 승인했다. 임시 비교 파일을 먼저 저장하고 실제 파일 해시를 등록용 artifact에 기록하도록 보완했다. `source_comparison_sha256`은 원본 비교 파일의 실제 해시이며 `comparison_sha256`은 업로드할 파일의 실제 해시다.

가짜 등록 클라이언트로 과거 네 모델 자료와 새 두 모델 자료를 각각 시험했다. 두 사례 모두 수정 전에는 해시 불일치로 실패했고 수정 후 통과했다. 원본 comparison·series·replay와 필수 모델·scaler·DEV 바이트는 유지되며, 로컬 artifact에는 기존 방식대로 등록 정보만 갱신한다. 관측/예측 배열·NPZ·DEV·보정 원본에 대한 다른 해시 참조는 바꾸지 않았다. 실제 MLflow DB에 등록하거나 운영 모델을 승격한 것은 아니다.
