# Feature Store 구조

현행화: 2026-10-08

## 정의·값·계보

Feature는 계산 숫자뿐 아니라 의미·알고리즘·버전과 실제 사용한 원천을 함께 보존한다.

| 모델 | 저장 내용 |
|---|---|
| [FeatureDefinition](../ocean-ai-platform/backend/app/models/domain.py) | feature ID/버전, 그룹, 설명, calculation logic, source fields, window size |
| `FeatureValue` | 관측소·센서·변수·시각·feature ID/버전별 값과 observation ID |
| [FeatureProvenance](../ocean-ai-platform/backend/app/models/evidence.py) | observation/feature/버전, window start/end, available_at, source observation IDs 및 source hash |

허용 그룹은 Raw, Rule QC, Temporal, Spatial, Metadata, Operation, Event Feature다. 정의와 값의 버전은 복합키로 관리한다. 초기 seed의 9개 예시 정의가 모두 실제 계산 엔진으로 구현됐다는 의미는 아니다.

## 현재 계산 경로

[evidence_features](../ocean-ai-platform/backend/app/services/evidence_features.py)의 `generate_event_features()`는 닫힌 사건에 연결된 Standard를 시각순으로 사용한다. 모의/DEMO 또는 원본이 없는 자료는 거부한다. `event-causal-1`의 실제 계산은 세 가지다.

| Feature | 입력·범위 |
|---|---|
| `evidence_value` | 현재 표준 관측값 |
| `evidence_moving_mean` | 사건에 연결된 관측 중 현재 시각 이전·현재의 최근 60분 평균 |
| `evidence_moving_std` | 같은 구간의 모집단 표준편차 |

없는 값·비유한 값은 계산에서 제외하고 source IDs/hash와 window를 저장한다. 최종 QC나 승인 Label을 이 계산 입력으로 사용하지 않는다. 이미 저장한 값의 원천 hash/계산값 또는 같은 정의 버전의 계산식이 달라지면 새 버전이 필요하며 덮어쓰지 않는다.

[feature_generator](../ocean-ai-platform/backend/app/ml/feature_generator.py)는 별도의 시간별 예측 실험 함수다. `prepare_hourly()`는 구간 종료시각에 평균을 놓고 기본 최소 6개 표본을 요구한다. 같은 시각의 서로 다른 값은 검토 오류이며 결측 구간은 보간하지 않는다. `make_features()`는 과거 lag 1/2/3/6/12/24/48시간과 `shift(1)`한 6시간 통계, 시계 주기를 사용한다. 이 함수의 버전과 전처리는 모든 원천·업무에 자동 적용되는 운영 정책이 아니다.

## As-of 누출 차단

관측 시각이 과거여도 수신 또는 QC 결정은 뒤늦게 도착할 수 있다. 미래 timestamp만 제거하는 것으로 충분하지 않다.

1. [dataset_lineage](../ocean-ai-platform/backend/app/services/dataset_lineage.py)는 feature와 provenance의 존재, 정의/버전, 유한 값, 원천 scope·window·source hash를 검증한다. window end와 선언 available_at이 해당 관측 시각보다 뒤이면 차단한다.
2. [source_contract_snapshot](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py)의 `overlay_proofs()`는 모든 feature source observation이 실제 승인 source binding으로 고정됐는지 확인한다. 각 원천의 실제 `available_at` 및 `qc_available_at`이 feature 선언 시각과 기존 origin보다 늦으면 차단한다.
3. [source_contract_authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py)는 원문 receive literal/clock policy와 관측·수신·QC 가용 시각, 물리 sensor episode 및 QC 시행기간을 다시 검증한다. typed 자료의 auxiliary 성분도 별도 가용 시각을 가진다.
4. v2 snapshot은 feature와 source/protocol dependency bytes/hash를 동결한다. 학습은 승인된 고정 분할·평가 계약을 소비하며 같은 원천 row/cell의 분할 간 재사용을 검사한다.

사건 Feature 생성기의 `available_at=observation timestamp` 기록만으로 실제 수신시각 검증을 마친 것으로 보지 않는다. 늦게 수신된 자료는 source proof 대조 단계에서 차단되어야 한다. 실제 가용 시각이 없으면 임의로 생성하지 않는다.

## API와 학습 연결

[Feature API](../ocean-ai-platform/backend/app/api/routes_features.py)는 `GET/POST /api/features/definitions`, `GET/POST /api/features/values`를 제공한다. 직접 value POST는 정의·버전 존재와 중복을 확인하지만 전체 원천 provenance를 자동 생성하지 않는다. FeatureValue가 있다는 사실만으로 학습 입력이 승인되지 않는다.

실제 학습은 [원천 계약](11_OBSERVATION_STANDARD_LAYER.md) → 승인 ingest → 사건/라벨/feature 계보 → [Dataset v2](18_DATASET_REGISTRY.md) → 고정 프로토콜 승인 → [모델 비교](19_MLOPS_VERSION_AND_EVALUATION.md) 순서다. PROFILE/VECTOR/TRAJECTORY 등 구성형 자료를 임의 scalar로 축약하거나 서로 다른 수심·센서를 이름으로 짝짓지 않는다.

## 검증·적용 상태

[event evidence 시험](../ocean-ai-platform/backend/tests/test_event_evidence.py)과 [source snapshot 시험](../ocean-ai-platform/backend/tests/test_source_contract_snapshot.py)은 과거/현재 입력, source hash 변경, 실제 수신·QC 가용 시각이 선언보다 늦은 경우를 검증한다. 공개 작업본의 전체 시험 통과는 Feature의 실제 업무별 의미·가용성 승인과 별개다.

2026-10-08 읽기 전용 운영 확인에서 source binding·Dataset·학습 이력은 0이었다. 실제 승인 원천의 feature와 고정 평가 snapshot을 완성한 운영 학습은 아직 확인되지 않았다. 과거 “정의 9·값 0” seed 기록은 현재 DB 측정값으로 재사용하지 않는다.
