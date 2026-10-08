# MLOps 버전·비교·등록·배포

현행화: 2026-10-08 · [상세 릴리스 범위](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)

## 버전 추적과 후보의 근거

`ModelRegistry`는 모델·Dataset·Feature·Label·전처리 버전, 지표, artifact 경로, 배포 상태·대상·시각과 Champion 상태를 보존한다. 새 비교 경로는 committed job ID, report/artifact SHA, 분할 snapshot·정책 hash와 독립 검토 이력을 `metrics_json.provenance`로 연결한다. `RetrainingHistory`는 이 검증된 후보 등록 단계에서 실제 worker 학습 시작·종료 시각과 비교 결과를 기록한다.

클라이언트가 제출한 지표나 업로드 경로만으로 `/models`에 모델을 적재하지 않는다. `/candidates/register`와 호환 `/models`는 검증된 비교 영수증 및 해당 모델 버전의 실제 독립 검토를 요구한다. 등록 결과는 `PENDING_APPROVAL`/`CANDIDATE`이며 등록만으로 serving하지 않는다.

## 비교 실행과 정책

[preflight](../ocean-ai-platform/backend/app/ml/comparison_runner.py)는 [승인 Dataset v2](18_DATASET_REGISTRY.md), 원천 receipt, 고정 세 분할, 동일 test origin/target, source/feature as-of와 정확한 입력 hash를 확인한다. 정책에는 과업·domain·item·target·단위·자료형·horizon·lookback·Feature ID와 아래 내용이 고정된다.

| 정책 | 고정하는 내용 |
|---|---|
| `SPLIT_PROTOCOL` | 분할 전략, Dataset ID·참여 digest·기간, 잠긴 holdout, embargo·분리 그룹 |
| `EVALUATION_PROTOCOL` | train-only 전처리, validation 후보 선택, 명시적 train+validation 재fit 선택, 후보 파라미터, 동일 test pair, worker의 한정 lease/시도 정책 |
| `ACCEPTANCE_POLICY` | 과업별 표본·성능·오류·수치 호출 지연 및 비용 조건 |

최종 test를 tuning에 사용하지 않는다. 수용 임계값은 versioned 정책 초안과 실제 reviewer 승인을 구분한다. 예를 들어 5% 개선폭은 공학적 제안이며 가이드 규정이나 사용자 승인값이 아니다. 승인 기준이 없으면 `NOT_DEFINED` 또는 구체적 blocker로 남긴다.

## 자료형과 평가 범위

72개 `(domain,item,task)` 키는 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이다. 자료형 6종·업무 알고리즘 3종의 연결이며 72개 업무 전체의 운영 적합성 또는 72개 학습 모델이 아니다.

| 자료형 | 현재 기준선/평가 범위 |
|---|---|
| Scalar | persistence와 train 전처리·validation 선택 Ridge, 승인 단위의 MAE/RMSE/bias |
| Circular direction | cos/sin 표현과 wrapped degree error, 명시된 paired magnitude |
| Signed HF radial | 부호를 보존한 값, 승인 geometry/QC/coverage |
| Vector UV | 승인된 명시적 grid cell·좌표계의 UV와 vector norm error; 전체 공간장 예측은 별도 |
| Profile bins | 단일 target/unit과 고정된 bin 대응; 방향 bin은 원주 오차, 임의 혼합 단위·보간 없음 |
| Trajectory | 명시된 WGS84 position endpoint와 위도 절댓값 85도 미만 범위, dateline 처리·구면 근사 거리; 유도 유속·추가 channel은 별도 계약 필요 |

Forecast는 기준선·Ridge를 같은 잠긴 test pair에서 평가한다. 이상탐지는 NORMAL/BAD 근거에 맞춘 robust score와 조정하지 않은 point/event 지표를 사용한다. 품질검토는 NORMAL/SUSPECT/BAD/MISSING 담당 Label과 규칙 결과·`NOT_EVALUATED`의 전체 비교, agreement·false-good 등을 보고한다. 학습 점수의 이진 성능은 NORMAL/BAD 부분집합임을 표시하고 최종 QC 판정을 만들지 않는다.

`validate_metrics` 호환 helper는 FORECASTING의 MAE/RMSE/latency와 분류의 precision/recall/F1/AUROC/FPR/FNR/latency, 유한수·범위를 검사한다. helper 통과만으로 비교·수용·승인을 증명하지 않는다. `/champion-challenger`는 저장 지표 두 개를 조회하는 API이며 동일 holdout의 기존 Champion 재평가 실행기가 아니다. 현재 비교 adapter의 기준선·후보 평가와 기존 운영 모델의 paired 재평가는 구분한다.

## Durable worker와 API

[job_queue.py](../ocean-ai-platform/backend/app/ml/job_queue.py)는 SQLite WAL 큐의 멱등 job ID·동일 scope 중복 방지, lease·fencing token·heartbeat, 한정 시도·quarantine을 구현한다. 결과 확정 전에 원천·입력·코드를 다시 검사한다. stale worker는 결과를 확정할 수 없다. 큐 완료는 모델 자동 등록·승인이 아니다.

```text
GET  /api/mlops/summary
GET  /api/mlops/readiness
GET  /api/mlops/adapters
GET  /api/mlops/retrain-history
POST /api/mlops/protocols/draft
POST /api/mlops/protocols/{sha256}/decision
POST /api/mlops/training/enqueue
GET  /api/mlops/training/jobs
POST /api/mlops/candidates/review
POST /api/mlops/candidates/register
POST /api/mlops/models/{model_version}/decision
POST /api/mlops/models/{model_version}/deploy
POST /api/mlops/models/{model_version}/rollback
GET  /api/mlops/serving/health?scope_key=...
POST /api/mlops/serving/predict
```

`POST /api/mlops/retrain`은 worker 사용이 꺼져 있으면 501이다. 켜져 있어도 고정 승인 manifest가 없으면 `FIXED_APPROVED_MANIFEST_REQUIRED` 409이며 임의 split이나 가짜 PENDING 학습 이력을 만들지 않는다. manifest가 있으면 승인 입력 큐 경로로 위임한다. 현재 MLOps 화면의 재학습 버튼은 입력 선택·승인 연결 UI가 없어 비활성화돼 있다.

worker CLI는 backend에서 `python -m app.scripts.model_training_worker --poll-seconds 10`이다. `OCEAN_TRAINING_WORKER_ENABLED` 기본값은 0이며 운영자가 명시적으로 설정해야 한다. worker는 application DB를 읽기 전용으로 사용하고 승인·등록·배포를 하지 않는다. 자동 학습 일정·신규 자료/drift trigger는 별도 운영 연결이며 main의 MDC scheduler와 다르다.

## 독립 검토·serving·rollback

1. worker의 실제 committed report/artifact와 동일 test pair를 독립 재현한다. reviewer의 `MODEL_INDEPENDENT_REVIEW`는 정확한 report SHA와 모델 버전에 결합된다.
2. 후보를 등록한 뒤 전용 model decision으로 report·artifact가 포함된 배포 identity를 승인한다. 일반 승인 화면에서 Registry 문자열을 `APPROVED`로 바꾸는 것만으로 이 gate를 통과하지 못한다.
3. `deployment_target=loopback`인 수치 JSON pilot을 명시적으로 배포한다. 실제 수치 smoke test 후 pointer·Registry를 변경하고, DB commit 실패 시 이전 pointer를 복원한다. 임의 H5/pickle을 실행하지 않는다.
4. serving health는 현재 프로세스에서 정확한 artifact의 예측과 승인·원천·코드 무결성을 확인한다. serving API는 loopback으로 제한된다. 최신 승인 철회 또는 코드 fingerprint 변경 시 거부한다.
5. 이전 scope identity의 `MODEL_ROLLBACK` 승인이 있어야 rollback한다. 이전 artifact를 보존하고, 승인 없는 rollback은 pointer/DB를 변경하지 않는다.

현재 정책은 `(domain,item,task,target_variable)`마다 한 Champion이다. horizon·단위는 정확한 report SHA에 포함되지만 여러 horizon Champion을 동시에 운영하는 기능은 아니다. worker의 `local_call_p95_ms`는 수치 함수 호출 시간이며 전체 API p95·throughput·운영 비용의 실증과 다르다.

2026-10-08 13:09 KST 운영 DB에서 source 승인·Dataset·Model Registry·RetrainingHistory·ApprovalHistory는 모두 0이다. 13:10:55 KST GET 검증에서는 canonical worker의 설정·fresh heartbeat·실제 프로세스가 확인됐고 큐는 비어 있다. readiness는 `BLOCKED`, `approved_input_ready=false`, 수용 기준 `NOT_DEFINED`, serving health는 409 `NO_ACTIVE_LOCAL_MODEL`이다. 공개 복사본이 실행 중인 것이 아니라 기존 canonical worker의 상태이며, 코드와 시험 통과를 실제 학습·운영 모델 선정·배포 완료로 세지 않는다.

근거 코드: [routes_mlops.py](../ocean-ai-platform/backend/app/api/routes_mlops.py), [실행 route](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py), [candidate 권위](../ocean-ai-platform/backend/app/ml/candidate_authority.py), [serving](../ocean-ai-platform/backend/app/ml/serving.py). 최신 전체 회귀는 [10/8 감사](10_IMPLEMENTATION_AUDIT.md)와 [current_status.json](current_status.json)을 따른다.

새 [fitted anomaly6모드](25_ANOMALY_AI.md)는 별도 개발 JSON artifact이며 실제 source 승인·72업무 비교·ModelRegistry를 우회하지 않는다. workflow resume 역시 MLOps 추천만 반환하고 training_enqueued/model_registered/deployment_performed는 false다. 실제 계정 설정은 사용자 지시로 운영 시점에 수행한다.
