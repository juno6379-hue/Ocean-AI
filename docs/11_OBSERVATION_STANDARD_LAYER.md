# Observation 표준화 계층

작성일: 2026-09-16

## 목적

`observation_raw`는 MDC 원시 수집값을 보존하고, `observation_standard`는 단위와 변수 코드 표준화가 완료된 값을 저장한다. 두 계층을 분리해 원본 재현성과 표준화 규칙 변경 이력을 함께 보장한다.

## 저장 구조

`ObservationStandard`는 다음 필드를 사용한다.

| 필드 | 설명 |
|---|---|
| `observation_id` | 자연키를 SHA-256으로 만든 안정적 식별자 |
| `station_id`, `sensor_id` | 표준 관측소·센서 식별자 |
| `variable_code` | 대문자로 정규화한 관측항목 코드 |
| `timestamp_utc` | UTC 기준 관측시각 |
| `value_raw` | 표준화 전 숫자값 |
| `value_standard` | 표준 단위로 변환한 값 |
| `source_unit`, `standard_unit` | 원천·표준 단위 |
| `conversion_rule` | 적용 규칙 또는 `IDENTITY_UNMAPPED_UNIT` |
| `standardization_version` | 현재 `OBS-STD-1.0` |
| `created_at` | 표준화 행 생성시각 |

관측소·센서·항목·UTC 시각 복합키에 유일 제약을 적용해 재실행 중복을 방지한다.

## 현재 변환 규칙

- `TIDE`, `cm` → `cm`, `IDENTITY_CM`
- `WAVE`, `m` → `m`, `IDENTITY_M`
- 등록되지 않은 조합 → 원천 단위를 보존하고 `IDENTITY_UNMAPPED_UNIT`로 표시

현재 MDC 수집 경로는 Raw 적재 직후 같은 배치의 Standard 적재를 수행한다. 기존 Raw 데이터도 백필했으며, 2026-09-16 기준 Standard 4,072건이 생성됐다(TIDE 212건, WAVE 3,860건).

조회 API는 `GET /api/observations/standard?station_id=...&limit=100`이며, 기존 `GET /api/observations` Raw API와 분리되어 있다.

## 운영 규칙

Raw 행을 수정하지 않는다. 변환 규칙이 변경되면 `standardization_version`을 올리고 새 Standard 배치를 생성한다. QC·AI·학습 파이프라인은 Standard를 입력으로 사용하고, 원본 확인이 필요할 때 `observation_id`와 Raw 자연키로 역추적한다.
