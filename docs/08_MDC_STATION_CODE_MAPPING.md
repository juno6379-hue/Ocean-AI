# 08. MDC 관측소 코드와 표시 분류

기준일: 2026-10-08. [sync mapping](../ocean-ai-platform/backend/app/scripts/sync_mdc_db.py), [분류 서비스](../ocean-ai-platform/backend/app/services/station_classification.py), [station API](../ocean-ai-platform/backend/app/api/routes_stations.py)가 현재 기준이다. 관측망 display 분류는 물리 시설·센서 identity와 기간의 승인을 대신하지 않는다.

## 허용된 관측망과 예외

| MDC DATA_TYPE | StationMetadata.network_type | 역할 |
|---|---|---|
| DT | 조위관측소 | 현재 조위 관측망 |
| TW | 해양관측부이 | 부이 display 분류 |
| IE | 해양과학기지 | 과학기지 |
| RT | 해양관측소 | 일반 해양관측소 |
| HF | HF-Radar | HF-Radar |
| SO | 조위관측소 | 구자료 호환 |
| KG | 해양관측부이 | 구자료 호환 display 분류 |

`DT_0046, DT_0047, DT_0048, DT_0039, DT_0041, DT_0042`는 기존 webMIMS의 RT 분류 예외를 명시 적용한다. Metadata station ID는 `OBS_POST_ID`의 공백 제거·대문자화이며 임의 `ST_` 접두어를 붙이지 않는다. 미등록 DATA_TYPE은 mapping 함수에서 제외되고 검토 대상으로 남긴다. 이름 정리 규칙이 역사 코드의 동일성, 재개소·후속 시설 연결을 승인한 것이 아니다.

원천 workbook의 IE 예시는 `IE_0060` 이어도, `IE_0061` 신안가거초, `IE_0062` 옹진소청초다. KG 계열 `GD_OBS_VBU`와 TW 계열 `GD_OBS_BU`는 원천군이 다르다. 같은 display 부이 분류여도 파일·시트·채널·깊이를 합치지 않는다. 독립된 station 목록과 item 목록을 같은 Excel 행 번호로 join하지 않는다.

## API와 화면의 분모

`/api/stations/catalog/classifications`는 DB에 등록된 관측망/해역과 등록 관측소 분모를 제공한다. 등록이 없는 코드는 `__UNREGISTERED__`, 등록 station의 분류 필드가 비어 있으면 `__UNASSIGNED__`로 구별한다. 해당 범위의 station 필터를 먼저 적용하므로 미분류 선택이 전체 관측 조회로 확대되지 않는다. [분류 scope 시험](../ocean-ai-platform/backend/tests/test_station_classification_scope.py)을 참조한다.

`as_of_month=2026-07`은 공식7월 보고서와 코드·명칭·유형·공개좌표가 유일하게 대응한70개를 읽기 전용으로 참조한다. 물리센서 승인이나 PostgreSQL수정이 아니다. 해역은 직접 근거52개만 반영하고 미명시는 기존 값을 유지한다. 다른 기간과 검증 당시 등록값이 달라진 레코드에는 적용하지 않는다. [7월 대응 검토](27_JULY_REPORT_PARQUET_MATCH.md)를 참조한다.

기존 `/api/observations/summary`는 등록 StationMetadata로 table/typeStatus/mapMarkers를 구성한다. ACTIVE는 정상, MAINTENANCE/DELAY/DEGRADED는 지연, ERROR/INACTIVE/OFFLINE/STOPPED는 중단으로 표시한다. 현재 legacy fallback에서는 그 외 상태도 정상으로 묶일 수 있으므로 미확인 상태가 검증된 정상이라는 뜻은 아니다.

`station_operating_rate`는 등록 관측소 중 표시상 정상 비율이다. 예상 관측수·관측 주기·전체 원천 coverage가 없으면 `collection_rate`는 NULL이다. 일별 Raw count는 UTC 날짜 기준 SQL 행 수이며 기존 SIMULATED 행이 포함될 수 있다. 빈 `chart_data`를 가짜 추이로 채우지 않는다. 지도에서 좌표 없는 station을 빼더라도 표의 등록 count와 이유를 구분한다. 실제 lake 조회는 별도 `/api/lake/*` 경로를 사용한다. [observations API](../ocean-ai-platform/backend/app/api/routes_observations.py), [lake API](../ocean-ai-platform/backend/app/api/routes_lake_browser.py)를 참조한다.

## 물리 sensor와 기간 검토

`/api/events/reference-catalog`는 저장된 station/sensor/alias를 조회한다. 생성된 `S_...` ID나 관측망 코드가 실제 장비 serial·sensor episode 증거는 아니다. 원천군·정확 station/item·typed depth·기간을 먼저 고정하고 실제 설치/교체/제거·장애/정비 문서와 연결해야 한다. 동명이인 시설과 역사 code, source 전환, 기간 충돌은 명시 근거 없이 자동 승인하지 않는다.

[mdc_sensor_catalog 모델](../ocean-ai-platform/backend/app/models/evidence.py)과 `/api/events/mdc-sensor-catalog` 조회 구현은 존재하지만 2026-10-08 13:09 KST 운영 table은 **미생성**이다. API 존재와 catalog 운영 적재 완료를 구분한다. [reconcile_mdc_sensors.py](../ocean-ai-platform/backend/app/scripts/reconcile_mdc_sensors.py)는 `WEB_EQUIP_INFO`, `WEB_OBS_ITEM_INFO`, `WEB_STATION`의 장비/항목/유효기간을 읽어 versioned source channel과 unresolved audit를 만든다.

Backend에서 `python -m app.scripts.reconcile_mdc_sensors --output <검토파일>`은 기본 preview다. `--source-json <보존원문JSON>`이면 저장된 원천으로 대조한다. Source JSON이 없으면 실제 Oracle에 읽기 전용으로 접속한다. `--apply`는 신규 catalog table과 records를 쓰므로 schema/관측소 FK/연결 권한·검토 결과 확인 후 별도 적용한다. 적용 자체도 source identity/period 승인이나 legacy SIMULATED 행의 승격을 뜻하지 않는다.

## 검증 절차와 과거 기록

1. 읽기 전용으로 MDC DATA_TYPE 고유값·예외 station과 DB 등록 유형/좌표·상태를 대조한다.
2. 코드 누락·NULL·불명 관측망과 같은 display 이름의 source 차이를 unresolved로 남긴다.
3. API 필터의 station scope, 미등록/미분류와 등록 count를 확인한다. 실제 관측 범위와 수집률은 별도 manifest/관측 주기 증거로 검증한다.
4. 물리 sensor/episode·effective period·clock·unit/QC 증거를 source contract review packet으로 연결하고 reviewer 결정을 기다린다.

```sql
BEGIN TRANSACTION READ ONLY;
SELECT network_type, COUNT(*) AS registered_stations
FROM station_metadata
GROUP BY network_type ORDER BY network_type;
ROLLBACK;
```

기존 문서는 2026-09-16 동기화 기록으로 323 station(조위 201, RT 27, 과학기지 3, 부이 69, HF 23), 신규 101/갱신 222를 기재했다. 이는 과거 문서의 실행 기록이며 현재 원문·DB snapshot으로 재검증한 최신 현황 수치가 아니다. 현재 운영 승인·source binding·사건/alias·dataset·model은 2026-10-08 확인에서 0이다. 66,190 월 grain, 152 기간 충돌과 40 미연결 보고서 행은 2026-10-07 파일 검토 후보 상태이고 catalog/의미 전수 승인 수가 아니다. [현재 현황](README.md), [정확 매핑 계약](06_MDC_QUERY_MAPPING.md), [source release 기록](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)을 참조한다.
