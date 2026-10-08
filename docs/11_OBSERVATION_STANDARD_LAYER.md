# Observation 표준화 계층

현행화: 2026-10-08

## 세 가지 저장 역할

| 계층 | 역할 | 코드 |
|---|---|---|
| `observation_raw` | 저장된 원시 숫자값, 원천 item/QC/MQC, 수심 및 시각 보존 | [domain 모델](../ocean-ai-platform/backend/app/models/domain.py) |
| `observation_standard` | 표준 변수·단위·변환 규칙·버전을 가진 관측 행 | 같은 모델의 `ObservationStandard` |
| `source_observation_binding` | 승인 원천 receipt와 정확한 파일·행·원천 literal·typed proof를 불변 payload로 연결 | [SourceObservationBinding 모델](../ocean-ai-platform/backend/app/models/source_observation_binding.py) |

Raw/Standard의 자연키는 관측소·센서·변수·UTC 시각이다. 원천 literal, typed depth, 파일 해시·locator, 물리 센서 episode 등의 전체 계약은 ORM의 숫자 필드만으로 보존할 수 없으므로 binding과 동결 receipt도 함께 검증한다.

## 승인 원천 경로

1. [source_contract_authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py)의 `source_contract_v2` packet에 원천 grain, 증거 파일 역할·SHA·locator, 물리 센서·유효기간 및 변환 계약을 제출한다.
2. [source-contract API](../ocean-ai-platform/backend/app/api/routes_source_contracts.py)로 실제 operator가 요청한다. reviewer/admin은 예상 packet SHA를 지정해 판정한다. 파일에 `APPROVED`라고 쓰거나 agent가 검토한 사실만으로 승인되지 않는다.
3. `verify_approved_receipt(..., verify_sources=True)`는 최신 `SOURCE_CONTRACT` 원장, 판정 actor, packet/receipt hash 및 실제 원문·manifest·Parquet 행을 다시 확인한다. 취소·다른 snapshot·내용 변경은 차단한다.
4. [source_contract_snapshot](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py)의 `ingest_approved_source()`가 Raw/Standard와 binding을 한 트랜잭션에서 멱등 적재한다. 기존 자연키나 binding의 내용이 다르면 덮어쓰지 않는다.

이 적재는 label, event, feature, dataset membership을 자동 생성하지 않는다. 각각의 검토와 승인 연결은 [라벨 분리](13_AI_LABEL_SEPARATION.md), [Feature](14_FEATURE_STORE.md), [Dataset](18_DATASET_REGISTRY.md)에서 다룬다.

## 필수 의미·수치·시각 계약

| 계약 | 검증 내용 |
|---|---|
| 식별자 | 원천 코드와 원문 literal을 분리한다. SQL*Plus padding 제거는 명시된 `source_identifier_transform`을 검증하며 원본 literal을 보존한다. `exact_scope_key`에는 source/관측소/item/타입 보존 수심/월이 포함된다. |
| 물리 센서·기간 | canonical sensor ID와 실제 physical sensor ID를 분리하고 episode·유효 시작/종료·관측 시각을 대조한다. 사전 시트의 item 설명만으로 설치 이력을 확정하지 않는다. |
| 단위·배율·기준면 | `source_unit`, 표준 `unit`, quantity kind, observation role, `quantity_transform.scale/offset/datum`과 근거를 요구한다. 조위에 기준면 미적용을 임의 지정하지 않는다. |
| 시계 | 원천 literal, timezone, clock semantics, 명시적 UTC 관측 시각을 대조한다. DST 중복/존재하지 않는 local 시각을 임의 fold로 결정하지 않는다. |
| 수신·가용 시각 | receive 원문/UTC/clock policy와 원천·QC의 `available_at`을 검증한다. 실제 수신보다 먼저 가용했다고 선언할 수 없다. |
| 원천 QC | QC/MQC/N1 literal의 공백까지 유지하며 실제 codebook SHA, rule version과 시행기간, 승인 해석을 요구한다. `G `를 단순 GOOD으로 바꾸지 않는다. |

상세 근거의 hash/locator는 검토 대상을 고정한다. 그 참조 자체가 단위·시간대·센서 사실의 인간 승인까지 생성하지 않는다.

## Scalar와 구성형 관측

SCALAR 외 CIRCULAR_DEGREES, SIGNED_RADIAL, VECTOR_UV, PROFILE_BINS, TRAJECTORY는 명시적 성분 binding을 요구한다. 각 성분의 원천 파일·행·열·literal QC·수신/가용 시각·sensor episode·시행기간을 확인하고 aggregate 가용 시각은 모든 성분을 포함해야 한다. non-profile은 anchor와 타입을 보존한 depth가 같아야 하고 profile은 명시된 bin 순서와 실제 depth를 대조한다. 원천 row/cell 재사용은 선언된 정책에 따라 검증한다.

구성형 Standard의 `value_standard`는 `None`이며 임의 대표 scalar를 만들지 않는다. 원래 수치 구조는 binding과 snapshot의 `typed_payload`에 보존한다. `FR_DEPTH`/`FROM_DEPTH`는 승인된 column map을 사용하며 두 열이 충돌하면 거부한다.

## 기존 MDC 호환 경로와 한계

[sync_mdc_db](../ocean-ai-platform/backend/app/scripts/sync_mdc_db.py)의 기존 매핑은 `TIDE_LEVEL*`→TIDE, 일부 WAVE/기상/수질 item의 단위 기본값, TIDE m→cm, 미매핑 단위의 `IDENTITY_UNMAPPED_UNIT`을 포함한다. 여기서 만든 합성 sensor ID나 고정 시간 변환은 승인 원천 계약의 증거가 아니다. [observation_provenance](../ocean-ai-platform/backend/app/services/observation_provenance.py)는 SIMULATED/DEMO source를 운영 사건·학습 계보에서 배제한다.

Standard 자연키에는 버전이 들어 있지 않다. `standardization_version`만 변경해 같은 자연키의 과거 값을 무제한 재적재하는 버전 이력 저장소로 해석하지 않는다. 변환 변경은 새 검토 계약·snapshot 및 충돌 처리 검토가 필요하다.

## 조회·현재 적용 상태

`GET /api/observations`와 `GET /api/observations/standard`는 [조회 API](../ocean-ai-platform/backend/app/api/routes_observations.py)에서 분리되어 있다. 실제 원천 candidate 생성은 승인 적재와 별도이며 null 미확정 필드를 유지한다. 2026-10-08 읽기 전용 운영 확인에서 source packet/decision/binding은 모두 0이었다. AIR_PRES 500행 원문·Parquet 일치 검토는 2026-10-07의 미승인 초안이며 18,502개 항목이 미확정이었다.

원천 승인·적재·frozen snapshot 시험은 [source authority 시험](../ocean-ai-platform/backend/tests/test_source_contract_authority.py)과 [snapshot 시험](../ocean-ai-platform/backend/tests/test_source_contract_snapshot.py)에 있다. 구현 시험을 전체 원천 승인으로 확대하지 않는다.
