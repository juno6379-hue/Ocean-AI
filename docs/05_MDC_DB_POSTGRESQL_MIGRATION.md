# 05. MDC Oracle와 PostgreSQL 연계

기준일: 2026-10-08. 현재 [sync_mdc_db.py](../ocean-ai-platform/backend/app/scripts/sync_mdc_db.py)는 Oracle에서 기준정보·관측 행을 읽어 PostgreSQL 조회 모델에 적재하는 기존 연계다. 승인 source contract 기반 운영 학습 ingest는 [별도 bridge](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py)다. Oracle 수집에 성공한 사실만으로 물리 센서·clock·단위·QC·기간이 승인되지 않는다.

## 접속과 기동 조건

Backend `.env`의 `MDC_DSN`, `MDC_USER`, `MDC_PWD`는 실제 허가된 읽기 전용 연결 정보로 설정한다. 소스에 접속 주소·비밀번호를 넣지 않는다. `oracledb`는 [requirements](../ocean-ai-platform/backend/requirements.txt)에 포함된다. `ORACLE_CLIENT_LIB_DIR`를 지정하면 thick 모드 client library를 초기화하고, 비어 있으면 thin 모드를 사용한다. Instant Client가 모든 환경의 필수 조건인 것은 아니다.

Oracle 조회는 읽기 전용 transaction과 connect/call timeout을 사용한다. 원격 연결·권한·table/column 오류를 시험 데이터로 대체하지 않는다. 선택 열이 없는 Oracle ORA-00904일 때만 해당 조회의 선택 열 없는 fallback을 사용한다. 이 경우 missing QC/receive를 승인된 값으로 채우지 않는다.

[main.py](../ocean-ai-platform/backend/app/main.py)의 scheduler는 `MDC_SYNC_ENABLED=true`일 때만 시작하며 `DATA_MODE=live`를 요구한다. 기본값은 false다. 활성화 시 시작 시점에 metadata와 당일 관측을 수집하고, 이후 **10초마다** `sync_job()`을 호출한다. `max_instances=1`, `coalesce=true`로 같은 scheduler의 작업 중첩을 제한한다. API worker를 여러 개 띄우면 각 프로세스의 scheduler가 별도로 시작할 수 있으므로 수집 소유 프로세스를 하나로 정해야 한다.

## 조회 범위와 적재

| 작업 | Oracle 자료 | 현재 범위 | PostgreSQL 반영 |
|---|---|---|---|
| `sync_metadata` | `WEB_STATION` | 관측소 기준정보 | 허용된 관측망·유효 코드와 이름만 StationMetadata에 upsert |
| `sync_station_data` | `WEB_OBS_ST` | `(window_start, window_end]` | Raw 자연키 충돌 무시 후 Standard 변환 |
| `sync_buoy_data` | `WEB_OBS_VBU` | 같은 시간 창, 수심 열 포함 | 깊이별 기술 채널 ID로 Raw/Standard |
| `sync_tide_data` | `TP_OBS_SO` | 같은 시간 창 | 조위 항목 Raw/Standard |
| `sync_today_bulk` | 위 세 관측 table | 현재 KST 날짜 00:00부터 실행 시각 | 시작 시 당일 범위 적재 |

기본 증분 창은 현재 시각 기준 약 10초다. 과거 문서의 5분 scheduler·1시간 조회·8년 timestamp 이동은 현재 동작이 아니다. `shift_time_to_present()`는 timestamp를 변경하지 않는다. 이름이 남아 있는 `get_simulated_time_range()`도 현재 시각 기반 조회 창을 만든다. 기존 `SIMULATED` DB 행은 이 변경으로 자동 정정되거나 실제 source 행으로 승격되지 않는다.

현재 수집기는 durable watermark/replay checkpoint가 없다. 수집 중단 기간과 이전 OBS_TIME을 가진 지연 도착 행은 짧은 다음 창에서 빠질 수 있다. backfill 범위·원문 중복/변경·late arrival·재처리 정책을 검토해야 한다. 1,000행 배치의 Raw와 Standard commit은 별도이므로 전체 수집이 하나의 원자적 transaction인 것으로 가정하지 않는다. [멱등·중복 검토](07_MDC_DEDUPLICATION_MIGRATION.md)를 참조한다.

## 기준정보와 변환의 한계

`station_metadata.id`가 PK이고 `station_id`는 원천 코드 기반 unique key다. `sensor_metadata.sensor_id`는 기술 채널 ID다. 현재 `map_mdc_item()`과 KST→UTC 변환은 기존 수집 정책이며 원문별 업무 승인의 대용이 아니다. 특히 WAVE 계열을 묶는 coarse mapping과 UNKNOWN 단위가 있다. [실제 query/단위 매핑](06_MDC_QUERY_MAPPING.md), [분류와 표시](08_MDC_STATION_CODE_MAPPING.md)를 확인한다.

원천 QC/MQC, source item/system, depth, receive time을 보존하지만 선택 query가 모든 원천 QC 열·단위를 수집하는 것은 아니다. 고정 split 학습에는 원문 locator와 source receipt가 연결된 `SourceObservationBinding`이 추가로 필요하다. Raw/Standard 자연키에 들어갔다고 Dataset approval에 바로 사용할 수 없다.

## 변경과 적용 절차

1. Oracle schema·원문 sample·query 범위와 source clock/단위를 읽기 전용으로 확인한다. 접속 정보는 로그와 문서에 노출하지 않는다.
2. 대상 PostgreSQL의 기존 schema·row count·자연키 중복·FK와 데이터 보존 계획을 검토한다. 자동 DDL과 demo seed는 끈다.
3. 신규 source review/binding과 사건 계보는 개별 additive migration을 검토한다. [source contract DDL](../ocean-ai-platform/backend/app/scripts/migrate_source_contracts.py)은 dry-run이 기본이고 [source binding SQL](../ocean-ai-platform/backend/migrations/20261007_source_observation_binding.sql)은 참조 table을 먼저 요구한다.
4. 승인된 수집 범위에서만 명시 실행한다. Backend의 `python -m app.scripts.sync_mdc_db`는 Oracle 조회와 PostgreSQL 쓰기를 수행하는 명령이며 일반 설치 검증이 아니다.
5. 원문 기준 count/자연키·source literal·time/depth/단위/QC를 대조하고 실제 source contract 검토로 연결한다. 등록 metadata count와 예상 관측수 대비 수집률을 구분한다.

2026-10-08 13:09 KST 운영 설정은 live/sync false/자동 DDL false다. Source contract·binding·승인 dataset·운영 model은 0이다. `mdc_sensor_catalog`는 코드 정의가 있으나 운영 table은 없다. 이 문서가 Oracle 재수집·DDL·운영 승인 수행 완료를 뜻하지 않는다.
