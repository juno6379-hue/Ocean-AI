# MDC 실제 운영 스키마 inventory (2026-09-18)

Oracle Thick Client로 실제 MDC에 연결해 `ALL_TAB_COLUMNS`를 조회했다.

## 확인 결과

- `WEB_STATION`: 24개 컬럼
- `WEB_OBS_ST`: 4개 컬럼
- `WEB_OBS_VBU`: 7개 컬럼
- `GD_OBS_ST`, `GD_OBS_VBU`: 현재 계정에서 조회 가능한 컬럼 0개

`WEB_OBS_ST`에는 `OBS_POST_ID`, `OBS_ITEM_CODE`, `OBS_TIME`, `OBS_VALUE`만 존재한다. `QC_FLAG`, `MQC_FLAG`, `RECEIVE_TIME`은 이 운영 테이블에 없으므로 확장 조회는 실패하며 기본 컬럼으로 fallback한다.

`WEB_OBS_VBU`에는 `OBS_POST_ID`, `OBS_ITEM_CODE`, `OBS_TIME`, `WATER_STEP(VARCHAR2)`, `FR_DEPTH`, `TO_DEPTH`, `OBS_VALUE`가 존재한다. 수심·수위 구간은 PostgreSQL `ObservationRaw`/`ObservationStandard`에 저장한다.

## 동기화 샘플 검증

동기화 실행 결과:

```text
StationMetadata: 323
ObservationRaw: 13,615
ObservationStandard: 4,074
```

기존 중복 자연키를 제거한 후 unique index를 생성했고, 부이 `SALINITY2`가 표준 `SALINITY`로 매핑되는 것을 확인했다. `QC_FLAG`·`MQC_FLAG`는 실제 테이블에 컬럼이 없으므로 NULL이며, 별도 운영 QC 테이블이 제공되면 추가 매핑한다.
