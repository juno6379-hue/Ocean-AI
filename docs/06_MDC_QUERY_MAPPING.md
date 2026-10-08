# 06. MDC query와 관측 매핑

기준일: 2026-10-08. 아래는 [현재 sync 구현](../ocean-ai-platform/backend/app/scripts/sync_mdc_db.py)의 실제 query/변환 규칙이다. 원천별 의미·단위·시간·센서 구간의 인간 승인은 [source contract](../ocean-ai-platform/backend/app/services/source_contract_authority.py)에서 별도로 검증한다. [설치·연계](05_MDC_DB_POSTGRESQL_MIGRATION.md)와 [관측소 분류](08_MDC_STATION_CODE_MAPPING.md)를 함께 사용한다.

## 관측소 기준정보

현재 `WEB_STATION` query는 `OBS_POST_ID, DATA_TYPE, OBS_POST_NAME, OBS_LAT, OBS_LON, DO_NM, ADDRESS, TOTAL_STATUS`를 읽는다.

| 원천 | 대상 / 처리 |
|---|---|
| `OBS_POST_ID` | metadata의 `station_id`: 앞뒤 공백 제거와 대문자화. StationMetadata의 integer `id`가 PK이고 station_id는 unique다. |
| `OBS_POST_NAME` | display용 이름 정리. 역사 표기·연도 prefix 제거가 물리 시설 동일성 승인인 것은 아니다. |
| `DATA_TYPE` | 명시된 7개 관측망 코드와 6개 RT 예외만 적용. 미등록 관측망은 임의 분류하지 않는다. |
| `OBS_LAT/OBS_LON` | 좌표. 유효성을 확인한 뒤 표시·해역 분류에 사용한다. |
| `DO_NM/ADDRESS` | 행정·주소 정보. DO_NM 자체를 해역으로 사용하지 않는다. |
| `TOTAL_STATUS` | 1→ACTIVE, 2→MAINTENANCE, 기타→ERROR. 실제 기간별 수집률과 별도다. |

`map_sea_area`의 현재 좌표 규칙은 위도≤34 및 경도≥125이면 제주권, 그 외 경도≥128이면 동해, 경도≤126.5이면 서해, 나머지는 남해다. 유효하지 않은 좌표는 미상이다. 이 표시 규칙을 source owner의 시설·구역 승인으로 해석하지 않는다.

## 관측 query의 공통 구조

```sql
SELECT OBS_POST_ID, OBS_ITEM_CODE, OBS_TIME, OBS_VALUE,
       QC_FLAG, MQC_FLAG, RECEIVE_TIME
FROM WEB_OBS_ST
WHERE OBS_TIME > :start_time AND OBS_TIME <= :end_time
```

`WEB_OBS_VBU`는 여기에 `WATER_STEP, FR_DEPTH, TO_DEPTH`를 포함한다. `TP_OBS_SO`도 공통 항목·시각 구조를 사용한다. 실제 SQL 조립은 sync script를 기준으로 하며, optional QC/receive 열이 없을 때 ORA-00904 fallback이 적용될 수 있다. 현재 query는 source unit과 N1_AQC_FLAG를 모두 읽는 일반 원천 adapter가 아니다.

| 원천 값 | Raw/Standard 처리와 한계 |
|---|---|
| 관측소/항목 | 관측 행의 station은 strip, item은 strip+uppercase. Metadata의 station uppercase 규칙과도 대조해야 한다. source item/system은 별도로 보존한다. |
| `OBS_TIME` | 원천 local 시각을 기존 수집 정책의 KST로 해석하고 UTC로 변환. 시간 자체를 현재로 이동하지 않는다. 개별 원천의 timezone 승인으로 간주하지 않는다. |
| `OBS_VALUE` | 수치 변환 후 Raw와 Standard. 원문 문자열·정밀도·missing 구분과 locator를 보존해야 승인 계약으로 연결할 수 있다. |
| QC/MQC | raw 값 보존. 기존 value_status 판정은 선택 code를 대문자화하고 `1/G`→OK, `4/B`→ANOMALY, 기타→UNREVIEWED로 처리한다. 모든 codebook의 승인 의미가 아니다. |
| receive | 조회 가능한 경우 수신시각 보존. 학습에는 exact receive literal·clock policy·UTC·최종 available_at을 검증해야 한다. |
| depth | `WATER_STEP/FR_DEPTH/TO_DEPTH`를 변환하며 non-null depth가 있으면 채널 ID에 depth digest suffix를 붙인다. 물리 센서 episode를 새로 만든 것이 아니다. |

Raw QC에서 `'G '`와 `'G'`, 빈 문자열과 NULL을 같은 원문으로 바꾸지 않는다. SQLPLUS padding 제거도 승인된 명시 transform을 적용하고 원문 literal을 따로 보존한다. 문서 발행일, 관측일, 장비 설치/교체일, 보고된 장애 구간, 실제 가용시각은 각각의 date role로 검토한다.

## 현재 항목 mapping

| 원천 항목 조건 | 현재 variable / 기본 unit / sensor type |
|---|---|
| `TIDE_LEVEL*` | TIDE / cm / TIDE_GAUGE |
| 코드에 `WAVE` 또는 SEA_LEVEL/WAVE_HEIGHT/WAVE_PERIOD | WAVE / m / WAVE_SENSOR |
| WATER_TEMP 또는 TEMP | WATER_TEMP / C / WATER_QUALITY |
| SALINITY 또는 SALINITY2 | SALINITY / PSU / WATER_QUALITY |
| ELECT_CONDUCT | ELECT_CONDUCT / MS/CM / WATER_QUALITY |
| WIND_SPEED 또는 WIND_GUST | 원천 WIND_SPEED 또는 WIND_GUST 그대로 / M/S / METEOROLOGY |
| WIND_DIRECT | WIND_DIRECT / DEG / METEOROLOGY |
| AIR_PRES | AIR_PRES / HPA / METEOROLOGY |
| AIR_TEMP | AIR_TEMP / C / METEOROLOGY |
| 그 외 | 원천 코드 / UNKNOWN / MDC |

이 표는 coarse legacy mapper의 동작 설명이다. `WAVE_PERIOD`에도 M 기본 단위가 적용되는 현행 규칙은 파주기 의미·단위를 확정한 계약이 아니며, 업무별 정밀 mapping 전에 담당자 검토가 필요하다. 원천 단위가 UNKNOWN일 때 기본 단위를 채우는 동작도 원문 단위 확인으로 해석하면 안 된다.

Standard 변환은 TIDE의 M→CM에 ×100, CM에는 identity를 적용한다. WAVE M은 M으로 유지하고 그 외에는 source unit과 `IDENTITY_UNMAPPED_UNIT` 계열 규칙이 남을 수 있다. 생성된 `S_{item}_{station}{depth_suffix}`는 source channel 식별자다. 실제 장비 serial, 교체·철거 경계와 유효기간을 추정하여 덧붙이지 않는다.

## 승인 원천 계약의 추가 조건

[source snapshot bridge](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py)는 actual source file/SHA, manifest SHA, `parquet_row_group=<n>;row_index=<n>`, 원문 station/item/time/value/QC literal과 타입을 확인한다. `FR_DEPTH`/`FROM_DEPTH`는 명시 `source_column_map`과 근거로 선택하고 두 열이 충돌하면 차단한다. NULL·수치·문자 깊이는 exact scope에서 구분한다.

물리 sensor/episode/event, effective `[start,end)`, unit/quantity transform, source timezone와 명시 offset UTC, 수신시각 정책, QC codebook/rule/가용시각, training 상태가 검토되어야 한다. 벡터·profile·trajectory의 각 component에도 원천 행·clock·QC·episode·가용시각 근거가 필요하며 aggregate 가용시각보다 늦은 component를 숨길 수 없다. 이름이나 같은 workbook 행만으로 station-sensor를 결합하지 않는다.

현재 API `/api/events/reference-catalog`와 기준정보는 검토용 source channel catalog다. 운영 `mdc_sensor_catalog` table은 2026-10-08 확인 시 없었다. 실제 승인된 source binding은 0이며 기존 SQL 행을 학습 입력으로 자동 승격하지 않는다. [학습 입력 계약](18_DATASET_REGISTRY.md)과 [구현 기록 82](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)를 참조한다.
