# 42. 조위 AI-QC MLOps 엔진 통합 및 5대 연동 브리지

기준일: 2026-10-22. [19. 모델 버전·평가](19_MLOPS_VERSION_AND_EVALUATION.md) 및 [30. 실제 원시 학습·시험 배포](30_EXPERIMENTAL_TRAIN_DEPLOYMENT.md)와 함께 읽는다. 조위 이상치 품질처리(AI-QC) MLOps 엔진(`ocean-ai-platform/mlops-qc-engine/`)을 `Ocean-AI` 플랫폼 내에 통합하고, 로컬 스냅샷·후보 LSTM 학습·1:1 비교 평가(`champion_2025` vs `candidate`)·로컬 QC 시뮬레이터(Tier 1/Tier 2)·승격 포인터를 `Ocean-AI` PostgreSQL 메타데이터 및 MLOps 화면과 연결하는 5대 연동 브리지(`qc_mlops_bridge.py`)를 구현했다.

## 1. 5대 연동 아키텍처 (5-Point Integration)

`ocean-ai-platform/backend/app/services/qc_mlops_bridge.py`와 `routes_mlops.py`는 `ocean-ai-platform/mlops-qc-engine/`의 기준선 매니페스트 및 실행 산출물을 읽어 `Ocean-AI` 플랫폼의 5개 계층과 동기화한다.

| 연동 지점 | 소스 (`mlops-qc-engine/`) | 대상 (`Ocean-AI` Backend / DB / UI) | 동작 요약 |
|---|---|---|---|
| **① Dataset Registry** | `reports/ocean_ai_snapshots/*/snapshot_manifest.json` (부재 시 `2025_operation_64_manifest.json` 기준선 시드) | `DatasetVersion` (`event-evidence-dataset-2` 호환 메타데이터) | 관측·예측조위 결합 Parquet 스냅샷의 행 수, 기간, `TRAIN/VALIDATION/TEST` 분할 비율과 SHA-256 해시를 등록한다. |
| **② Model Registry** | `manifests/2025_operation_64_manifest.json` 및 `reports/candidate_runs/*/artifact.json` | `ModelRegistryEntry` | 49개 관측소·64개 조위 센서 기준선(`champion_2025`)과 신규 후보(`candidate`) LSTM 번들(HDF5, RobustScaler, `Thres.forecast.DEV`)을 등록한다. |
| **③ Evaluation Metrics** | `reports/candidate_runs/*/comparison.json` 및 `reports/local_qc_simulations/*/comparison.json` | `ModelRegistryEntry.metrics` (`champion-candidate-1` 계약) | Tier 1 정상 목표 예측 지표(`MAE`, `RMSE`, `R²`)와 Tier 2 전체 QC 재생(`online` / `consolidated` FP·FN 비악화) 결과를 통합 기록한다. |
| **④ Deployment Pointer** | `manifests/active_release_pointer.json` 및 `manifests/releases/*.json` | `/api/mlops/qc-engine/status` (`active_pointer`) | 현재 활성 릴리스(`2025_OPERATION_64_BASELINE` 또는 승격된 릴리스)와 관측소·센서별 런타임 번들 해석 상태를 노출한다. |
| **⑤ MLOps Workbench UI** | `ui/dashboard.html` (`/`), `ui/data_preview.html` (`/data`), `scripts/local_dashboard.py` (`8765`) | `frontend/src/pages/MLOps.tsx` (`조위 AI-QC 학습·승격 워크벤치`) | `Ocean-AI` MLOps 화면에서 브리지 동기화, `8765` 워크벤치 서버 원클릭 기동(`POST /api/mlops/qc-engine/start`), 임베디드 워크벤치 조작을 제공한다. |

## 2. 로컬 클린 환경 실행 절차

저장소를 새로 클론한 환경에서 대용량 실행 산출물(`reports/`, `manifests/releases/`)이나 외부 원본 백업(`2026년_AI_품질처리_데이터백업`)이 없더라도 서버 기동과 브리지 동기화가 즉시 동작하도록 설계되어 있다.

### 2.1 Ocean-AI Backend (8000) 및 Frontend (5173) 기동

```powershell
# 1) Backend 실행 (ocean-ai-platform/backend)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2) Frontend 실행 (ocean-ai-platform/frontend)
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 2.2 조위 AI-QC 워크벤치 (8765) 기동 (웹 원클릭 또는 CLI)

- **웹 화면에서 원클릭 기동 (권장)**:
  1. 브라우저에서 `http://127.0.0.1:5173/mlops`에 접속한다.
  2. 상단 **조위 AI-QC 학습·승격 워크벤치 (ai-qc-mlops 5대 연동)** 카드에서 **`8765 워크벤치 서버 기동`** 버튼을 클릭한다(`POST /api/mlops/qc-engine/start`).
  3. 백엔드가 `ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py`를 백그라운드 데몬으로 기동하고 `127.0.0.1:8765` 리스닝을 확인한 뒤 하단 워크벤치 화면(Iframe)을 자동으로 새로고침한다.
  4. **`산출물 → Ocean-AI DB 동기화`** 버튼을 누르면(`POST /api/mlops/qc-engine/sync`) `reports/` 폴더가 비어 있는 초기 상태에서도 `manifests/2025_operation_64_manifest.json`(64개 센서 기준선)을 기반으로 기준선 Dataset 1건과 Champion 모델 1건을 안전하게 시드(Seed) 등록한다.

- **터미널에서 직접 기동**:
  ```powershell
  python ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py --host 127.0.0.1 --port 8765 --no-browser
  ```
  - 워크벤치 대시보드(Step 1~4 및 Local QC Step 6): `http://127.0.0.1:8765/`
  - 학습자료 확인 및 스냅샷 생성 화면: `http://127.0.0.1:8765/data`

### 2.3 외부 데이터 연결 (선택 사항)

신규 CSV 프로파일링이나 실제 LSTM 재학습을 실행할 때는 아래 환경변수로 원본 데이터 위치를 지정할 수 있다(미지정 시 `manifests/2025_operation_64_manifest.json`에 내장된 64개 관측소·센서 카탈로그로 기본 화면이 구동됨):

- `AI_QC_DATA_WORKSPACE`: `2026년_AI_품질처리_데이터백업` 루트 경로
- `AI_QC_STANDARDIZED_CSV_DIR`: 월별 정형 관측 CSV(`data_YYYYMM.csv`) 폴더 경로
- `AI_QC_EXTERNAL_PRED_CSV_DIR`: 월별 예측조위 CSV(`GO_TIDE_PRE_DATA_YYYYMM.csv`) 폴더 경로

## 3. Clean Core 보존 범위 (`ocean-ai-platform/mlops-qc-engine/`)

저장소 용량 최적화와 재현성 유지를 위해 로컬 일회성 검증 리포트(`reports/`), 과거 릴리스 사본(`manifests/releases/`), 일회성 점검 스크립트는 제외하고 **핵심 엔진 파일만 정제하여 보존**한다.

- `scripts/` (33개 코어 모듈):
  - 최상위 24개: `local_dashboard.py`, `dataset_routes.py`, `dataset_preview.py`, `ocean_ai_snapshot.py`, `ocean_ai_bridge.py`, `candidate_training_worker.py`, `model_lifecycle.py`, `comparison_contract.py`, `calibration_policy.py`, `evaluation_safety.py`, `local_qc_simulator.py`, `release_pointer_consumer.py`, `offline_model_suite.py`, `replay_prediction_worker.py`, `register_mlflow_trial.py`, `run_record_wrapper.py`, `local_trial_manifest.py`, `refresh_standardized_month_index.py`, `standardize_training_data.py`, `tensorflow_runtime.py`, `training_control.py`, `training_diagnostics.py`, `workspace_paths.py`, `__init__.py`
  - `scripts/local_qc/` (5개): `bundle_loader.py`, `data_source.py`, `evaluation.py`, `replay.py`, `__init__.py`
  - `scripts/local_qc/legacy/` (4개): `east_sea.py`, `west_sea.py`, `south_sea.py`, `__init__.py`
- `ui/` (2개): `dashboard.html`, `data_preview.html`
- `schemas/` (1개): `operational_release_manifest.schema.json`
- `manifests/` (4개): `active_release_pointer.json`(초기값 `2025_OPERATION_64_BASELINE`), `2025_operation_64_manifest.json`, `2025_training_archive_inventory.json`, `20261006_local_trial_manifest.json`

## 4. 조위 AI-QC MLOps 상세 기술 문서 (`docs/ml-ops-docs/`)

`mlops-qc-engine`의 아키텍처, 웹 워크벤치 조작법, Local QC 시뮬레이터(Tier 1/Tier 2) 수식과 승격 전략, 운영 거버넌스는 [`docs/ml-ops-docs/`](ml-ops-docs/00_OVERVIEW_AND_INDEX.md) 하위 6개 번호 문서에서 상세히 다룬다.

| 번호 | 문서 | 핵심 내용 |
|---|---|---|
| `00` | [전체 개요 및 인덱스](ml-ops-docs/00_OVERVIEW_AND_INDEX.md) | 프로젝트 배경·목적, 6대 보호 원칙, 4계층 아키텍처 다이어그램, 단계별 구현 요약 |
| `01` | [시스템 아키텍처 및 1:1 비교 명세](ml-ops-docs/01_ARCHITECTURE_AND_FEATURES.md) | 이중 가상환경 격리, HTTP API 엔드포인트 4계층 추적표, 코어 스크립트 명세, `champion_2025` vs `candidate` 1:1 비교 구조 |
| `02` | [로컬 웹 워크벤치 운영 가이드](ml-ops-docs/02_USER_WEB_OPERATION_GUIDE.md) | `/` 대시보드(Step 1~4 위저드, 이상치 차트) 및 `/data` 화면(센서 카드, 드래그 월 선택기, Parquet 스냅샷) 조작 안내 |
| `03` | [Local QC 시뮬레이터 및 임계값·승격 평가](ml-ops-docs/03_LOCAL_QC_SIMULATOR_AND_EVALUATION.md) | 6단계 Local QC 재생기, 운영 호환 `Thres.forecast.DEV` 역산 인코딩, Tier 1 정상 예측 주 지표 및 Tier 2 비악화 승격 게이트 |
| `04` | [한계점 해소 현황 및 상용화 로드맵](ml-ops-docs/04_LIMITATIONS_AND_PRODUCTION_ROADMAP.md) | 아키텍처·데이터 한계 해소 내역, 회귀·분류 평가 분석, 실운영 서버(Production) 단계별 적용 로드맵 |
| `05` | [MLOps 운영 거버넌스 및 기술 기준](ml-ops-docs/05_MLOPS_GOVERNANCE_AND_POLICY.md) | 데이터 버전 고정, MLflow 추적 규격, 별칭(`candidate`/`champion`/`rollback`) 관리, 정기·조건 기반 재학습 및 배포 정책 |
