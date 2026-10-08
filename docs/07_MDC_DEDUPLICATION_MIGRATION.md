# 07. 관측 멱등성과 중복 migration 검토

기준일: 2026-10-08. 현재 [DB 모델](../ocean-ai-platform/backend/app/models/domain.py)과 [수집 구현](../ocean-ai-platform/backend/app/scripts/sync_mdc_db.py)은 반복 조회가 관측 행을 늘리지 않도록 자연키와 PostgreSQL `ON CONFLICT DO NOTHING`을 사용한다. 기존 데이터의 중복 삭제와 새 행의 멱등 수집은 별도 작업이다.

## 고정 키와 보존 계보

| 계층 | 키 / 제약 | 의미 |
|---|---|---|
| Raw | `(station_id, sensor_id, variable_code, timestamp_utc)` unique; integer id PK | 같은 기술 채널·시각의 반복 적재를 억제한다. |
| Standard | 같은 자연키 unique; `observation_id` PK | 표준 관측의 중복 적재를 억제한다. source key의 digest를 사용한다. |
| Source binding | observation PK/FK, packet/approval FK, receipt SHA, `(parquet_sha256, source_row_locator)` unique | 승인된 실제 원천 행과 observation을 불변 payload로 연결한다. |
| Dataset membership | dataset/observation 및 snapshot hash 계보 | build 시 exact 참여 목록을 고정하고 승인 snapshot을 재검증한다. |

Binding의 key·SHA·locator는 [source binding 모델](../ocean-ai-platform/backend/app/models/source_observation_binding.py)과 [명시 DDL](../ocean-ai-platform/backend/migrations/20261007_source_observation_binding.sql)이 기준이다. 자연키 충돌만으로 원문이 동일하거나 물리 sensor·기간이 승인되었다고 볼 수 없다. 정정 원천, source 교체, episode 변경과 값 차이를 검토해야 한다.

## 기존 DB의 읽기 전용 점검

운영 DB에서 변경하기 전에 별도 읽기 전용 transaction으로 중복과 NULL, FK·참조 계보를 확인한다. 아래는 삭제 SQL이 아니다.

```sql
BEGIN TRANSACTION READ ONLY;
SELECT station_id, sensor_id, variable_code, timestamp_utc, COUNT(*) AS copies
FROM observation_raw
GROUP BY station_id, sensor_id, variable_code, timestamp_utc
HAVING COUNT(*) > 1;

SELECT station_id, sensor_id, variable_code, timestamp_utc, COUNT(*) AS copies
FROM observation_standard
GROUP BY station_id, sensor_id, variable_code, timestamp_utc
HAVING COUNT(*) > 1;

SELECT COUNT(*) AS incomplete_keys
FROM observation_raw
WHERE station_id IS NULL OR sensor_id IS NULL
   OR variable_code IS NULL OR timestamp_utc IS NULL;
ROLLBACK;
```

PostgreSQL 일반 unique 제약은 NULL을 같은 값으로 취급하지 않으므로 nullable key에 대한 완전성 점검이 필요하다. 원문 raw string/QC, 수신 시각, source SHA·locator, 표준화 결과, 라벨·Feature·사건·dataset 참조를 비교해 동일 행인지 먼저 판정한다. 최근 ingest 시각이나 큰 id만으로 보존해야 할 원천을 고르지 않는다.

## Legacy migration의 실제 영향

[migrate_process_schema.py](../ocean-ai-platform/backend/app/scripts/migrate_process_schema.py)는 Base metadata table 생성과 legacy 제약 추가뿐 아니라 **Raw의 큰 id와 Standard의 ctid 기준 중복 삭제**를 수행한다. 모든 기존 근거·FK·정정 우선순위를 검토하는 script가 아니므로 일반 설치 단계에서 실행하지 않는다. 원문에서 정정·서로 다른 source가 자연키를 공유하면 자동 삭제로 해결하면 안 된다.

적용이 필요한 경우 먼저 DB backup과 restore 검증, 삭제 후보별 exact row export/SHA 및 참조 영향 검토, survivor 기준과 담당자 승인, 격리 DB rehearsal을 준비한다. 사용자 source 원문과 이전 approval/snapshot은 별도로 보존한다. 참조 재연결·migration 후 count/unique/원문 hash·API 결과까지 검증해야 한다. 이 문서는 운영 중복 삭제 실행을 승인하거나 완료했다고 주장하지 않는다.

사건/문서 계보의 [additive migration](../ocean-ai-platform/backend/app/scripts/migrate_event_evidence.py)은 기존 unique 후보가 중복이면 수동 검토를 요구한다. 신규 [source contract migration](../ocean-ai-platform/backend/app/scripts/migrate_source_contracts.py)은 기본 dry-run이며 두 새 테이블만 대상으로 한다. 새 table 추가와 legacy 중복 삭제를 한 작업으로 묶지 않는다.

## 수집·승인 ingest의 멱등 검증

현재 Oracle sync는 batch insert에서 자연키 충돌을 무시하며, 같은 프로세스 scheduler는 중첩을 제한한다. DB unique 제약이 없다면 Python의 사전 존재 조회만으로 경쟁 insert를 막을 수 없다. 기존 DB에 실제 unique 제약이 적용되었는지 확인해야 한다.

승인된 [source ingest](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py)는 receipt의 현재 ledger/Actor/packet 및 실제 원천을 재검증한다. 같은 source binding의 동일 재실행은 추가 적재하지 않고, 바뀐 payload/receipt/source/identity를 멱등 성공으로 처리하지 않는다. Typed 자료는 승인 component binding을 유지하며 scalar ORM 값 하나로 임의 축약하지 않는다. [bridge 시험](../ocean-ai-platform/backend/tests/test_source_contract_snapshot.py)에서 재실행·변조·유효 구간·source/Feature 가용시각 차단을 확인한다.

멱등 insert는 수집 전체성을 보장하지 않는다. 현재 sync의 짧은 시간 창에는 durable checkpoint가 없고 Raw/Standard commit도 별도다. 지연 도착·중단 후 backfill, partial batch 복구, correction/version 정책은 [MDC 연계](05_MDC_DB_POSTGRESQL_MIGRATION.md)와 승인 원천 검토에서 별도 결정한다.

2026-10-08 운영 source binding/dataset/approval/model은 0이다. 이전 중복 정리 기록이나 격리 시험 통과를 현재 실제 승인 원천의 멱등 운영 완료로 해석하지 않는다.
