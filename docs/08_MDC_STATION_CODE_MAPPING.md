# 08. MDC 관측소 코드 및 관측 현황 표시 매핑

작성일: 2026-09-16

## 문제 원인

기존 동기화 코드는 `SO`, `TW`, `KG`, `HF`만 허용했다. 실제 webMIMS 소스와 MDC 운영자료에서 사용하는 주요 `DATA_TYPE`은 `DT`, `TW`, `IE`, `RT`, `HF`다. 그 결과 조위관측소(`DT`)와 해양과학기지(`IE`)가 PostgreSQL에 들어오지 않거나 유형별 화면 집계에서 누락될 수 있었다.

## 적용한 매핑

| MDC `DATA_TYPE` | PostgreSQL `StationMetadata.network_type` | 화면 의미 |
|---|---|---|
| `DT` | `조위관측소` | 조위관측소 |
| `TW` | `해양관측부이` | 해양관측부이 |
| `IE` | `해양과학기지` | 해양과학기지 |
| `RT` | `해양관측소` | 일반 해양관측소 |
| `HF` | `HF-Radar` | HF-Radar |
| `SO` | `조위관측소` | 구자료 호환 |
| `KG` | `해양관측부이` | 구자료 호환 |

webMIMS 기존 SQL에서 `DT_0046`, `DT_0047`, `DT_0048`, `DT_0039`, `DT_0041`, `DT_0042`를 `RT`로 표시하던 예외도 반영했다. 관측소 ID는 MDC의 `OBS_POST_ID`를 공백 제거·대문자화한 값을 그대로 PostgreSQL `station_id`로 사용한다. 임의의 `ST_` 접두어는 붙이지 않는다.

## 관측 현황 UI 수정

`/api/observations/summary`는 `ACTIVE`, `MAINTENANCE`, `ERROR`를 각각 정상·지연·중단으로 변환한다. 기존에는 한국어 상태만 검사해 MDC 상태값이 화면에서 정상으로 오인될 수 있었다.

유형별 현황은 `SensorMetadata`가 아직 비어 있어도 `StationMetadata.network_type` 기준으로 계산한다. 따라서 해양관측부이와 해양과학기지의 관측소 수와 상태가 센서 메타데이터 동기화 여부에 따라 사라지지 않는다.

통합 대시보드 지도는 고정 좌표를 제거하고 `/api/dashboard/summary`의 `station_id`, 위도·경도, `network_type`을 사용한다. 지도 팝업에서 MDC 관측소 코드와 매핑된 관측망을 함께 표시한다. 장비 관리 화면의 관측망별 운영률도 하드코딩된 장비명 대신 `StationMetadata.network_type`별 정상 관측소 비율로 계산한다.

## 재동기화 및 검증

1. PostgreSQL에서 기존 `station_metadata`의 `station_id`, `network_type`을 백업한다.
2. `sync_metadata()`를 실행해 MDC `WEB_STATION`을 다시 동기화한다.
3. 유형별 건수를 확인한다.

```sql
SELECT network_type, COUNT(*)
FROM station_metadata
GROUP BY network_type
ORDER BY network_type;
```

4. MDC 원본의 `DATA_TYPE`별 건수와 PostgreSQL 매핑 후 건수를 비교한다.
5. `/api/observations/summary`의 `mapMarkers`, `tableData`, `typeStatus`에서 `해양관측부이`, `해양과학기지`가 반환되는지 확인한다.

## 2026-09-16 실제 동기화 결과

`sync_metadata()`를 실행해 MDC `WEB_STATION` 323건을 처리했다. PostgreSQL 반영 결과는 신규 101건, 기존 관측소 업데이트 222건이다. 유형별 건수는 조위관측소 201개소, 해양관측소 27개소, 해양과학기지 3개소, 해양관측부이 69개소, HF-Radar 23개소로 확인됐다. `IE` 관측소는 `IE_0060`(이어도), `IE_0061`(신안가거초), `IE_0062`(옹진소청초)로 저장됐다.

실제 MDC 접속 후 `WEB_STATION.DATA_TYPE`의 전체 고유값과 `OBS_POST_ID` 예외 목록을 추출해 이 매핑표와 대조한다. 미등록 코드는 임의로 분류하지 않고 매핑표와 테스트를 먼저 갱신한다.

## 기준자료 대조 결과

`분류/정형데이터/01.정형데이터/관측소_OBS ID POST_OCEANDB_v5.xlsx`의 시트와 샘플 코드를 대조한 결과, 해양과학기지 시트에는 `IE_0061`, `IE_0062`, `IE_0060`이 기록되어 있다. 따라서 해양과학기지의 현재 MDC 코드 매핑은 `IE`가 맞다. 같은 파일에서 `KG_*`는 대형부이(`GD_OBS_VBU`), `TW_*`는 해양관측부이(`GD_OBS_BU`)로 구분되어 있으므로 두 코드를 하나의 화면 표시명으로 묶을지는 업무 표시정책으로 결정해야 한다. 화면과 API에는 관측소 코드 접두부도 함께 반환하도록 했다.
