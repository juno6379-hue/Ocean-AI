# 34. 목적별 데이터셋·모델 학습·평가 준비도 검토

검토 기준: **2026-10-09 18:15 KST**(읽기 전용 HTTP 근거 `2026-10-09T09:15:24.255804+00:00`). [기계 판독 결과](34_PURPOSE_DATASET_MODEL_READINESS_REVIEW.json). 이 문서는 다음 개발 범위를 결정하기 위한 현재 코드·DB·실행 검토이며, 새 실제 원천 학습·등록·승인·배포를 수행한 보고서가 아니다.

**개발용 학습·평가 경로는 있지만 목적별 운영 모델 전체가 완성된 상태는 아니다.** 별도 시험 서버의 실제 원시 예측 모델은 기압·수온·염분 3개이고, 운영 Model Registry와 승인 Dataset은 각각 0건이다. 예측과 이상탐지의 제한된 비교 어댑터, 조건부 드리프트 엔진은 구현되어 있다. 여러 관측소·공간장을 함께 학습하는 전용 시공간 모델은 구현되어 있지 않다. 72개 키는 자료형 6종·과업 3종의 표현 기준선 연결이며 72개 학습·선정·운영 모델을 뜻하지 않는다.

## 1. 현재 실행·원장 사실

아래 결과는 14개 GET 응답과 별도 PostgreSQL 읽기 전용 count를 대조했다. 프로세스별 설정을 섞지 않는다. 실제 계정·승인은 사용자가 운영 시점으로 유예했으며 이 검토에서 생성하지 않았다.

| 확인 대상 | 현재 확인값 | 해석 |
|---|---|---|
| 승인 source packet / decision / observation binding | 0 / 0 / 0 | 실제 원천의 의미·단위·시계·QC·센서 구간 승인 입력 없음 |
| Dataset Registry / 승인 Dataset / Model Registry | 0 / 0 / 0 | 고정된 승인 세 분할이나 운영 모델이 준비됐다는 근거 없음 |
| RetrainingHistory / ApprovalHistory / AI Label / RetrainingPool | 모두 0 | 실제 승인 학습·재학습·검토 정답 원장 없음 |
| FeatureDefinition / FeatureValue | 9 / 0 | 특성 정의 이름은 있지만 실제 학습 특성값은 없음 |
| 고정 training manifest / training-ready 업무 키 | 0 / 0 | `/model-development/training-manifests`는 `NO_REQUESTS`; 72개 중 검증된 고정 입력 0개 |
| canonical `8000` | readiness `BLOCKED`; worker 설정 true, 현재 실행 검증 false(`STALE_OR_CHANGED`); serving 설정 true | 10/8의 worker RUNNING 기록을 현재 실행으로 재사용할 수 없음. serving health는 `409 NO_ACTIVE_LOCAL_MODEL` |
| review `8010` | readiness `BLOCKED`; worker·serving 설정 false; 운영 검증 모델 0 | serving health는 `409 LOCAL_JSON_SERVING_DISABLED` |
| `8000`·`8010` training queue | 전체 조회 대상 작업 0, initialized true | GET은 상태 필터 없는 최근 최대 100건이다. 응답이 빈 배열이므로 그 조회 시점에는 작업 자체가 없음. 완료를 뜻하지 않음 |
| 개발 시험 `8011` | `READY`, 실제 release 모델 3개 | `experimental=true`, `nonoperational=true`, `approved=false`, `production_eligible=false` |
| `/mlops/adapters` | task keys 72 / code implementations 6 / task algorithms 3 | `registered_models_by_coverage=0`, `operational_completion=false` |

DB의 `ObservationRaw` 13,621행은 source system이 모두 `MDC_WEB_OBS_ST_SIMULATED` 714행과 `MDC_WEB_OBS_VBU_SIMULATED` 12,907행이며 2026년 9월 시각이다. `ObservationStandard` 4,074행도 9월의 `OBS-STD-1.0` 기록이다. 이 DB 행 수를 실제 7월 원천의 승인 학습 준비량으로 사용하지 않는다. 실제 7월 보존 자료는 별도 Parquet 원천이며 source 계약·Dataset 동결은 아직 없다.

## 2. 목적별 비교

| 목적 | 현재 실행 가능한 코드·후보 | 실제 데이터셋·실행 근거 | 현재 가능한 학습·평가 | 미완성 및 다음 필수 입력 |
|---|---|---|---|---|
| **Forecasting** | 고정 승인 manifest의 Scalar/typed Ridge 후보와 persistence 기준선 비교. 별도 raw-next-row 학습 서비스는 persistence와 Ridge 5개 alpha를 비교 | 2026-07 GR 인천 `DT_0001` AIR_PRES·WATER_TEMP·SALINITY 133,876행의 개발 실험·시험 release 3개. 운영 승인 입력은 0 | raw-next-row는 고정 TRAIN으로 적합, VALIDATION MAE로 선택, TEST에서 MAE/RMSE 비교한 실제 결과가 있음. 승인 입력을 준비하면 worker의 typed 비교·독립 replay·후보 등록 경로 이용 가능 | 물리 시간 horizon, 단위·배율·기준면, 시계, 센서 episode, causal features, 고정 세 Dataset 및 split/evaluation/acceptance 정책. 현재 3개는 다음 **관측 행**의 원시 숫자 예측이며 1분·72시간 조위 운영 예측이 아님 |
| **Anomaly detection / 품질 검토** | TRAIN NORMAL의 median/MAD 특성 score와 ALL_NORMAL 기준선 비교; VALIDATION 라벨로 threshold 선택. 별도 fitted 엔진의 SPIKE·PERSISTENCE·TIDE_RESIDUAL·DRIFT·BIOFOULING_CANDIDATE·SENSOR_DEGRADATION_CANDIDATE | 실제 2023-01 native 3항목의 raw SPIKE/PERSISTENCE 실험은 600건 중 552건 평가·48건 warm-up. 물리 QC·실제 원인 정답은 미평가. 운영 라벨·Dataset 0 | raw fit/calibration/test 수치 분석 가능. 물리 개발 엔진은 명시한 JSON 사실 계약이 필요하고 `ANALYSIS_ONLY`. 승인 비교 worker는 NORMAL/BAD의 point 지표와 사건 탐지 지연, QUALITY_REVIEW의 전체 QC 라벨 대조를 구현 | 정상 학습 구간 오염 검토, 담당 NORMAL/BAD/SUSPECT/MISSING 정답·사건, 원문 QC 코드북 판본·시행기간, 고정 reference/표본·false alarm 수용 기준. 후보 건수는 정확도·고장 건수가 아님 |
| **Drift detection** | 수온·염분의 독립 reference에 대한 trailing residual median 편차를 train robust scale·calibration threshold와 비교하는 `DRIFT` 모드 | 합성 paired-reference 시험 코드 있음. 실제 원천의 독립 기준 센서·동일 단위·QC·episode·가용 시각 계약은 미확정; 운영 drift 모델 0 | 검증 가능한 declared paired-reference 입력이 있으면 순수 개발 fit/analyze 가능. 합성 테스트 성능을 실제 관측소 성능으로 바꾸지 않음 | 주 센서와 **다른 물리 기준 센서**의 동일시각·항목·단위·QC와 유효기간, 교정·교체·세척 사건, drift truth와 지연·오경보 기준. 독립적인 분포 변화 감시나 drift-trigger 자동 재학습 worker는 아직 미구현 |
| **Spatio-temporal analysis** | signed radial, 명시된 단일 grid-cell UV vector, fixed profile bins, 위치 trajectory의 typed 표현·Ridge/persistence·오차 계산 | 승인 geometry/grid/cell·coordinate/bin/cast/trajectory 계약 Dataset 0. 원천 종류 존재와 공동 공간장 학습 준비는 별개 | 승인된 **명시 단일 origin/target** 입력의 제한된 표현 기준선은 가능. vector norm·방향 원주 오차·고정 bin 오차·궤적 endpoint 거리 지원 | 공간장·다중 관측소 이웃 연결, 좌표계·고정 grid·공간/시간 분할과 관측소 holdout, 결측 mask·causal 공변량, 과업별 horizon·metric·수용 기준. 전용 공간장/graph 학습·평가·serving 경로 및 실제 선정 모델은 없음 |

현재 worker가 받는 과업은 `FORECASTING`, `ANOMALY_DETECTION`, `QUALITY_REVIEW` 세 가지다. `DRIFT_DETECTION`과 `SPATIO_TEMPORAL_ANALYSIS`라는 별도 학습 과업이 연결된 것으로 표시하면 안 된다. DRIFT는 조건부 이상탐지 엔진의 모드이고, 공간 표현 지원은 전체 공간장 모델 지원과 다르다.

## 3. 실제 시험 예측 모델 3개

개발 `8011 /release`의 현재 release ID는 `6a1e751fbbd9b2a28cc8cecd228e5eda4283872c38dc39e9950065b3fac20989`, release manifest SHA는 `76cf46101c1d5e69e99bf083922c77942c2aec3f42f9205417d0a5e6d83a7e1d`이다. 원문 시각·단위의 승인 없이 수치만 평가했으므로 오차는 원시 숫자 단위다.

| 항목 | TRAIN / VALIDATION / TEST 행 | TEST 평가 쌍 | VALIDATION MAE: persistence / Ridge | TEST MAE: persistence / Ridge | TEST RMSE: persistence / Ridge | 선정 |
|---|---|---:|---|---|---|---|
| AIR_PRES | 25,920 / 8,640 / 10,065 | 10,062 | 0.01457682 / 0.01588385 | 0.01069370 / 0.01193873 | 0.03270122 / 0.03254729 | PERSISTENCE |
| WATER_TEMP | 25,920 / 8,640 / 10,066 | 10,063 | 0.01039944 / 0.01071352 | 0.01210077 / 0.01275996 | 0.02379126 / 0.02403739 | PERSISTENCE |
| SALINITY | 25,920 / 8,640 / 10,065 | 10,062 | 0.02510478 / 0.09956007 | 0.02106639 / 0.11733347 | 0.31945007 / 0.33298166 | PERSISTENCE |

분할은 원문 날짜의 TRAIN `[7/1,7/19)`, VALIDATION `[7/19,7/25)`, TEST `[7/25,8/1)`이다. 각 입력은 최근 3개 원시 숫자이고, split 경계를 넘거나 수치·시각 조건이 맞지 않는 쌍은 제외한다. 새 비교·학습을 이 검토에서 실행하지 않았다. 모델 선택은 VALIDATION만 사용했으며 TEST에서 더 좋은 수치를 보고 선택을 바꾸지 않는다. 세 모델의 artifact·membership SHA와 정확 지표는 JSON에 보존했다.

**이 release는 7월 후반 학습·선정 자료를 포함하므로 7월 9일 당시 가용했던 모델로 사용할 수 없다.** 7월 9일 QC 화면의 실제 온라인 AI 점수나 원인 판정으로 연결하지 않는다. 개발 실험 결과 패널에서 훈련 기간과 `nonoperational` 상태를 따로 표시할 수 있다.

`/api/forecasting/baseline`은 별도 경로다. DB의 마지막 `TIDE` 값을 매 시간 반복하며 `trained_model=false`, `method=PERSISTENCE_BASELINE`을 반환한다. 원천·기간·cutoff 필터가 없고 `is_demo=false`가 고정되어 있으므로 이 필드를 실제 7월 원천 학습의 증거로 사용하면 안 된다. 현재 9월 DB 이력과 실제 7월 Parquet를 섞은 QC 예측으로 연결하지 않는다.

## 4. 후보 이름과 구현을 구분

| 구분 | 후보·방법 | 현재 근거 |
|---|---|---|
| 실행 구현 | persistence / StandardScaler + Ridge / train-normal robust feature score | 실제 numeric fit·validation 선택·동일 holdout 평가 코드 있음. raw-next-row에서는 실제 3항목 실행 |
| 조건부 개발 구현 | SPIKE·PERSISTENCE·TIDE_RESIDUAL·DRIFT·오염/열화 후보의 median/MAD·보정 분위수 | 명시 사실·시계·reference가 없으면 NOT_EVALUATED. 원인·최종 QC·Registry를 변경하지 않음 |
| 설계 문서 후보 | Isolation Forest, 계절 기준선, SARIMAX/Prophet, LightGBM/XGBoost, TCN/LSTM/GRU/Autoencoder, TFT/Transformer, TranAD, PatchTST 등 | 기존 [모델 계획](../ocean-ai-platform/docs/30_AI_TIME_SERIES_MODEL_PLAN.md)·[소스 감사](../ocean-ai-platform/docs/81_MODEL_TRAINING_AUTOMATION_AND_SOURCE_AUDIT.md)의 후보 이름. 현재 비교 runner의 학습 가능한 후보 구현·선정·배포 목록으로 바꾸지 않음 |
| 과거 자산 기록 | 조위 LSTM H5·scaler·추론 소스 | 과거 bounded 감사 기록은 있음. 이 검토는 H5 로드·가중치 학습 membership·독립 재현·현재 운영 배포를 확인하지 않았다. 다른 관측항목으로 재사용 근거 없음 |
| 아직 별도 미정의 | 전용 공간장/graph 모델, 운영 분포 drift detector | 실행 어댑터·고정 평가 입력·수용 정책·학습/serving 근거 없음 |

현재 production 비교 경로는 Ridge의 alpha나 robust score threshold를 validation에서 선정하고 기준선과 대조한다. 후보를 등록하면 `PENDING_APPROVAL/CANDIDATE`이고 자동 serving되지 않는다. `/champion-challenger`는 저장 지표 조회이며 현재 운영 Champion을 동일 holdout에서 재실행하는 비교기가 아니다.

## 5. 데이터셋별 준비 단계와 gate

| 단계 | 현재 | 다음 검증 조건 |
|---|---|---|
| 원천 발견·보존 | 실제 Parquet와 native clock·typed grain·원문 QC 존재 | source row/cell SHA·locator를 유지하고 source·station·item·typed depth를 확정 |
| 물리 사실 계약 | 단위/배율/기준면·시계·QC 판본/시행기간·physical sensor episode 미확정 | 명시 근거와 유효기간을 검토. 원문 naive 시각을 UTC/KST로 추정하지 않음 |
| 개발 raw 실험 | 3항목의 제한된 실제 fit/평가·개발 release 있음 | 승인 물리 성능과 별도 상태·모집단·원시 단위·제외 사유 표시 |
| 조건부 물리 개발 분석 | 코드 구현; 실제 입력 부족 | exact sensor scope, 사실별 유효기간·explicit offset·QC/가용 시각, drift/reference·조위 datum·issued-at를 준비. 선언 근거는 source 승인과 별개 |
| production Dataset v2 | 현재 등록 0 | 승인 source receipt와 고정 split/evaluation/acceptance 의존 SHA를 snapshot에 동결; 현행 원장 권위를 다시 검증 |
| worker 비교 | 구현, 입력·manifest·큐 작업 0 | 서로 다른 명시 TRAIN/VALIDATION/TEST Dataset, locked test hash, 고정 feature IDs·행 membership·horizon/lookback·센서/사건 embargo, train-only 전처리·동일 test origin/target |
| 평가·선정 | 목적별 계산 코드 있음; 운영 수용 기준 NOT_DEFINED | 예측 MAE/RMSE/bias; 이상 point precision/recall/F1/AUROC/FPR/FNR와 사건 지연; 전체 QC agreement/false-good/NOT_EVALUATED 분모를 고정. latency·비용·오경보 임계값도 명시 검토 |
| registry·serving | 구현, 운영 후보/배포 0 | committed job·report/artifact SHA, 독립 replay, 후보 등록, 정확 model-deploy identity 승인과 loopback smoke test. 실제 계정 설정·승인은 운영 실행 시점에 별도로 수행 |

사용자의 다음 결정 전에는 새 실제 원천 fit·큐 요청·Registry 적재·배포를 시작하지 않는다. 판단할 우선 범위는 **① 어떤 관측소/항목·목적을 먼저 다룰지 ② raw 실험과 물리 분석 중 어느 경로인지 ③ reference·정답·고정 분할·업무 수용 기준을 누가 어떤 근거로 검토할지**다. 공간장과 독립 기준 센서가 필요한 작업을 단변량 다음 행 예측으로 대신 완료 처리하지 않는다.

## 6. QC 화면에 연결할 정직한 표시 계약

첨부한 QC 디자인의 AI 검토·Rule·이상 패널에는 같은 source/snapshot/station/item/typed depth/기준시각의 평가 근거만 연결한다. 현재 `/lake/monitoring`은 월별 조회 경로이며 7월 9일 cutoff를 그대로 적용하지 않는다. `/qc/summary`의 DB 기록·현재 metadata 상태도 실제 7월 scoped QC 근거로 사용할 수 없다. 새 scoped 읽기 API는 native cutoff의 원천 지표·원문 QC 분포와 실행 Rule/모델 근거를 별도 반환해야 한다.

권장 목적별 준비도·학습평가 응답 필드는 다음과 같다. 아래 전체 목적별 모델 workspace는 **제안**이며 구현 완료가 아니다. 후속 일일 QC의 `/api/qc/context`, `/overview`, `/flag-catalog`, `/candidates/{id}`와 실제 상세 검토는 구현했고 [36](36_QC_OPERATIONAL_DASHBOARD_EXECUTION.md)에서 검증한다. 일일 QC 구현을 목적별 모델 학습·평가·serving 전체 완료로 확대하지 않는다.

- 조회 identity: source, snapshot SHA, station/item/typed depth, native window, clock basis, 확정 여부.
- 목적 준비도: family, 구현 후보와 설계 후보, 입력 부족 사유, raw/declared-physical/approved/simulation 경로.
- Dataset/분할: Dataset 버전·membership SHA·TRAIN/VALIDATION 또는 CALIBRATION/TEST 기간·locked holdout·정답판본·원문 locator.
- 학습·평가: fitting 여부, model/artifact/report SHA, metric 단위·평가 분모·제외·warm-up, 후보별 validation/test 결과. 근거 없으면 null/NOT_EVALUATED.
- 검토·통합: Rule의 규칙별 결과와 reason, AI의 통계 score·calibration rank, Metadata/Operation/RAG 근거와 충돌/coverage. score는 고장 확률이나 승인 confidence가 아니다.
- 운영 권위: approved/production_eligible/registry/serving 여부. 원문 QC 표기율·문서 사건 수·추정 자료 채움을 승인 정상률·실제 BAD 건수로 치환하지 않음.

18:15 검토 당시 QC UI는 [QCCopilot](../ocean-ai-platform/frontend/src/pages/QCCopilot.tsx#L1)의 WorkflowReviewPanel과 [AnalysisWorkspace](../ocean-ai-platform/frontend/src/components/AnalysisWorkspace.tsx#L51)를 연결한다. 운영 학습 입력 검토는 [TrainingWorkbench](../ocean-ai-platform/frontend/src/components/TrainingWorkbench.tsx#L9), 실제 3개 시험 release는 [30번 문서](30_EXPERIMENTAL_TRAIN_DEPLOYMENT.md) 경로를 사용한다. 후속 `/api/qc/workspace`와 원문 QC 전용 UI를 개발·검증했고, 사용자가 추가한 오늘 중심 운영 대시보드·상세검토 요구는 [36](36_QC_OPERATIONAL_DASHBOARD_EXECUTION.md)에서 추적한다. 화면만 채우는 고정 AI 수치나 가짜 학습 완료 상태를 추가하지 않는다.

## 7. 검토에서 발견한 구체적 계약 오류

`anomaly_analysis._rows`는 anomaly-series facts의 `start/end`로 기간을 검사했지만 `qc_analysis_readiness.inspect_source_inputs`는 `effective_start/effective_end`만 읽었다. 합성 380행을 **fitting 없이** 확인했을 때 `_rows` 오류 0인 정상 선언 입력을 `source_requirements`가 5개 사실의 기간 누락으로 `NOT_EVALUATED` 처리했다. 실제 물리 원천 준비가 완료된다는 의미는 아니지만 올바른 개발 입력도 준비도 단계에서 거부될 수 있는 오류다.

공통 기간 codec 보완을 완료했다. anomaly-series는 `start/end`, Rule/source-binding은 명시된 `effective_start/effective_end`를 유지하며 자동 alias fallback을 허용하지 않는다. offset 시각·순서·`[start,end)`·선언한 범위·가용 시각을 같은 codec로 확인한다. **최종 기간 계약 테스트 36개와 관련 엔진·Rule·raw 진단 묶음 174개가 통과했다.** 두 묶음은 중복 검증을 포함하므로 합산하지 않는다. 합성 380행의 준비도는 `CONDITIONAL_INPUT_READY`로 정상화됐으며 `approved=false`, `production_eligible=false`, `training_executed=false`를 유지한다. 실제 source 사실·승인·DB 원장·모델 학습·serving을 변경한 것은 아니다.

## 8. 근거와 재현 범위

| 근거 | 확인 지점 |
|---|---|
| 실제 API·DB aggregate 증거 | private 증거 SHA `40f148b4818bd8a4bb1e06372a7164af3d07732134a7d11efad5bbe04d1849a1`; 14 GET·새 fitting/학습/배포/DB 쓰기 false. 공개 JSON에는 집계·SHA만 보존 |
| DB readonly count 증거 | SHA `715b23df418fd8da19ea63c568dce4ff181165deef7fda1f200d5ace75b8c16c` |
| 후보 72개와 구현 6종 | [adapter_registry.py:7](../ocean-ai-platform/backend/app/ml/adapter_registry.py#L7), [model_scope_matrix.json](../ocean-ai-platform/backend/app/ml/model_scope_matrix.json) |
| 고정 승인 입력·누수 gate | [comparison_runner.py:131](../ocean-ai-platform/backend/app/ml/comparison_runner.py#L131), [preflight:337](../ocean-ai-platform/backend/app/ml/comparison_runner.py#L337), [feature/as-of:499](../ocean-ai-platform/backend/app/ml/comparison_runner.py#L499) |
| 학습·평가 알고리즘 | [typed_adapters.py:165](../ocean-ai-platform/backend/app/ml/typed_adapters.py#L165), [raw_next_row_training.py:175](../ocean-ai-platform/backend/app/services/raw_next_row_training.py#L175), [anomaly_analysis.py:19](../ocean-ai-platform/backend/app/services/anomaly_analysis.py#L19), [qc_raw_diagnostic.py:248](../ocean-ai-platform/backend/app/services/qc_raw_diagnostic.py#L248) |
| worker·후보·승인·serving | [model_training_worker.py:18](../ocean-ai-platform/backend/app/scripts/model_training_worker.py#L18), [job_queue.py:30](../ocean-ai-platform/backend/app/ml/job_queue.py#L30), [candidate_authority.py:47](../ocean-ai-platform/backend/app/ml/candidate_authority.py#L47), [serving.py:102](../ocean-ai-platform/backend/app/ml/serving.py#L102) |
| 현재 준비도·baseline 한계 | [model_development.py:179](../ocean-ai-platform/backend/app/services/model_development.py#L179), [mlops_readiness.py:166](../ocean-ai-platform/backend/app/services/mlops_readiness.py#L166), [routes_forecasting.py:16](../ocean-ai-platform/backend/app/api/routes_forecasting.py#L16) |
| 이전 실제 raw 실험·분할 | [29](29_DEVELOPMENT_STAGE_EXECUTION.md), [30](30_EXPERIMENTAL_TRAIN_DEPLOYMENT.md), [25](25_ANOMALY_AI.md) |

이 검토는 현재 코드와 읽기 전용 실행 상태, 기존 실험 aggregate를 확인했다. 실제 원천 물리 사실 전체 승인, 기존 H5 학습 재현, 72개 업무별 운영 성능, 새 실제 fitting/배포를 확인한 것으로 확대하지 않는다.
