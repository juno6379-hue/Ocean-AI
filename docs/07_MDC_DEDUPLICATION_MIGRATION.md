# 07. MDC 관측데이터 중복 방지 적용 내역

작성일: 2026-09-16

## 적용 범위

MDC Oracle의 `WEB_OBS_ST`, `WEB_OBS_VBU`에서 PostgreSQL `observation_raw`로 적재되는 관측 데이터에 적용한다. MDC가 2019년까지의 자료를 보유하므로 현재의 8년 시프트 시뮬레이션은 유지한다. 이 문서는 시간 보정이 아니라 재실행 시 중복 적재를 막기 위한 변경을 기록한다.

## 중복 판정 기준

한 관측값의 자연키는 다음 네 컬럼의 조합이다.

```text
station_id + sensor_id + variable_code + timestamp_utc
```

같은 키가 다시 들어오면 기존 행을 유지하고 새 행은 무시한다. 값이 변경된 경우까지 자동으로 덮어쓰지 않는 이유는 원시 관측값의 변경 이력을 보존하기 위해서다. 정정값 반영은 별도의 QC/보정 절차로 처리한다.

## 코드 변경

- `ObservationRaw` 모델에 `uq_observation_raw_natural_key` 복합 유니크 제약을 추가했다.
- `sync_mdc_db.py`에 `insert_observations_idempotent()`를 추가했다.
- 동기화 적재는 `bulk_save_objects()` 대신 PostgreSQL `INSERT ... ON CONFLICT DO NOTHING`을 사용한다.
- 로그에 조회(처리) 건수와 실제 신규 적재 건수를 분리해 기록한다.

## 기존 DB 적용 절차

새 제약을 적용하기 전에 기존 중복을 확인한다.

```sql
SELECT station_id, sensor_id, variable_code, timestamp_utc, COUNT(*) AS duplicate_count
FROM observation_raw
GROUP BY station_id, sensor_id, variable_code, timestamp_utc
HAVING COUNT(*) > 1;
```

중복이 확인되면 먼저 다음 기준으로 대표 행 1건만 남긴다. `ingest_time`이 가장 빠른 행을 대표로 사용하고, 삭제 전 백업과 건수 검증을 수행한다.

```sql
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY station_id, sensor_id, variable_code, timestamp_utc
               ORDER BY ingest_time NULLS LAST, id
           ) AS rn
    FROM observation_raw
)
DELETE FROM observation_raw o
USING ranked r
WHERE o.id = r.id AND r.rn > 1;

ALTER TABLE observation_raw
    ADD CONSTRAINT uq_observation_raw_natural_key
    UNIQUE (station_id, sensor_id, variable_code, timestamp_utc);
```

실제 운영 적용에서는 위 SQL을 트랜잭션·백업 정책에 맞는 별도 migration으로 실행한다. `create_all()`은 기존 테이블의 제약을 자동으로 추가하지 않으므로, 애플리케이션 재시작만으로 적용된다고 가정하면 안 된다.

## 검증 방법

1. 동일한 MDC 조회 구간을 두 번 실행한다.
2. 첫 실행의 신규 적재 건수와 두 번째 실행의 신규 적재 건수를 비교한다.
3. 두 번째 실행에서 신규 적재 건수가 0인지 확인한다.
4. 자연키 중복 조회 SQL의 결과가 0건인지 확인한다.
5. 서로 다른 항목·시각·관측소의 행은 정상적으로 각각 적재되는지 확인한다.

## 다음 단계

중복 방지 적용 후에는 마지막 성공 조회시각을 저장하는 checkpoint, MDC 관측항목 코드 매핑, 실제 센서 메타데이터 동기화를 순서대로 진행한다.
