# mlops-qc-engine (조위 AI 품질처리 MLOps 코어 엔진)

2025년 조위 AI 품질처리 운영본(49개 관측소·64개 조위 센서)을 변경하지 않고, 데이터 결합·`Ocean-AI` Parquet 스냅샷 생성·후보 LSTM 격리 학습·`champion_2025` vs `candidate` 1:1 비교·Local QC 시뮬레이터(Tier 1/Tier 2)·승격 및 롤백을 수행하는 코어 엔진이다.

`Ocean-AI` 플랫폼과의 5대 연동 구조 및 전체 실행 방법은 [`docs/42_AI_QC_MLOPS_ENGINE_INTEGRATION.md`](../../docs/42_AI_QC_MLOPS_ENGINE_INTEGRATION.md)와 [`docs/ml-ops-docs/00_OVERVIEW_AND_INDEX.md`](../../docs/ml-ops-docs/00_OVERVIEW_AND_INDEX.md)를 따른다.

## 1. 디렉터리 구조 (Clean Core)

- `scripts/`: 33개 코어 모듈
  - 최상위 24개: 웹 대시보드·데이터 라우트(`local_dashboard.py`, `dataset_routes.py`), 데이터 결합·스냅샷(`dataset_preview.py`, `ocean_ai_snapshot.py`, `standardize_training_data.py`, `refresh_standardized_month_index.py`), 후보 학습·평가·승격 생명주기(`candidate_training_worker.py`, `model_lifecycle.py`, `comparison_contract.py`, `calibration_policy.py`, `evaluation_safety.py`, `local_qc_simulator.py`, `release_pointer_consumer.py`), `Ocean-AI` 연동 브리지(`ocean_ai_bridge.py`), 오프라인 검증·MLflow 등록(`offline_model_suite.py`, `replay_prediction_worker.py`, `register_mlflow_trial.py`, `run_record_wrapper.py`, `local_trial_manifest.py`), 런타임·경로 제어(`tensorflow_runtime.py`, `training_control.py`, `training_diagnostics.py`, `workspace_paths.py`)
  - `scripts/local_qc/` (5개): `bundle_loader.py`, `data_source.py`, `evaluation.py`, `replay.py`, `__init__.py`
  - `scripts/local_qc/legacy/` (4개): 동해·서해·남해 레거시 QC 규칙 재생 모듈(`east_sea.py`, `west_sea.py`, `south_sea.py`, `__init__.py`)
- `ui/`: 로컬 웹 워크벤치(`dashboard.html`) 및 학습자료 확인·스냅샷 화면(`data_preview.html`)
- `schemas/`: 운영 배포 매니페스트 JSON 스키마(`operational_release_manifest.schema.json`)
- `manifests/`: 64개 센서 기준선 매니페스트(`2025_operation_64_manifest.json`), 학습 아카이브 인벤토리(`2025_training_archive_inventory.json`), 초기 기준선 매니페스트(`20261006_local_trial_manifest.json`), 활성 배포 포인터(`active_release_pointer.json`)
- `requirements-*.txt`: 제어 환경(`requirements-runtime.txt`, `requirements-mlflow.txt`) 및 CPU 학습 워커 환경(`requirements-cpu-runtime.txt`) 패키지 명세

## 2. 로컬 실행 방법

1. **`Ocean-AI` MLOps 웹 화면에서 원클릭 기동**:
   - `Ocean-AI` 백엔드(`8000`) 및 프론트엔드(`5173`) 실행 후 `http://127.0.0.1:5173/mlops` 상단 카드의 **`8765 워크벤치 서버 기동`** 버튼을 클릭한다.
2. **단독 CLI 기동**:
   ```powershell
   python ocean-ai-platform/mlops-qc-engine/scripts/local_dashboard.py --host 127.0.0.1 --port 8765 --no-browser
   ```
   - 워크벤치 대시보드(Step 1~4 및 Step 6 Local QC): `http://127.0.0.1:8765/`
   - 학습자료 확인 및 스냅샷 생성: `http://127.0.0.1:8765/data`

외부 원본 데이터(`AI_QC_DATA_WORKSPACE`)나 `reports/` 폴더가 없는 클린 상태에서도 `manifests/2025_operation_64_manifest.json`의 64개 센서 기준선을 사용하여 카탈로그 조회(`/api/state`, `/api/data/catalog`)와 `Ocean-AI` DB 시드 동기화(`POST /api/mlops/qc-engine/sync`)가 정상 동작한다.

## 3. 상세 기술 문서 (`docs/ml-ops-docs/`)

- [00. 전체 개요 및 인덱스](../../docs/ml-ops-docs/00_OVERVIEW_AND_INDEX.md)
- [01. 시스템 아키텍처 및 1:1 비교 명세](../../docs/ml-ops-docs/01_ARCHITECTURE_AND_FEATURES.md)
- [02. 로컬 웹 워크벤치 운영 가이드](../../docs/ml-ops-docs/02_USER_WEB_OPERATION_GUIDE.md)
- [03. Local QC 시뮬레이터 및 임계값·승격 평가](../../docs/ml-ops-docs/03_LOCAL_QC_SIMULATOR_AND_EVALUATION.md)
- [04. 한계점 해소 현황 및 상용화 로드맵](../../docs/ml-ops-docs/04_LIMITATIONS_AND_PRODUCTION_ROADMAP.md)
- [05. MLOps 운영 거버넌스 및 기술 기준](../../docs/ml-ops-docs/05_MLOPS_GOVERNANCE_AND_POLICY.md)
