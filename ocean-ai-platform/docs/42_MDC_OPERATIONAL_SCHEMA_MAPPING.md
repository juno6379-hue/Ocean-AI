# MDC 운영 테이블 매핑

실제 Oracle MDC 운영 스키마는 `inspect_mdc_schema.py`로 `ALL_TAB_COLUMNS`를 조회해 inventory를 생성한다. 대상은 `WEB_STATION`(관측소 메타데이터), `WEB_OBS_ST`(조위 관측), `WEB_OBS_VBU`(부이 관측)다.

동기화 시 `OBS_ITEM_CODE`를 원본 코드로 보존하고 `MDCItemMapping`을 통해 표준 코드·단위·센서 유형으로 변환한다. 부이의 `WATER_STEP`, `FR_DEPTH`, `TO_DEPTH`, 수신시각과 `QC_FLAG`, `MQC_FLAG`는 ObservationRaw/ObservationStandard에 별도 저장한다. 센서 메타데이터는 관측 레코드의 MDC 코드에서 upsert한다.

컬럼이 운영 DB 버전에 없을 경우 확장 조회가 실패하면 기본 컬럼 쿼리로 fallback하고 해당 QC/MQC 값은 NULL로 남긴다. 스키마 inventory 결과와 샘플 건수는 배포 전 검증 증거로 보관한다.

2026-09-18 개발 환경 조회 결과는 Oracle `DPY-3010`(Thick Client 미초기화/서버 버전 호환 문제)로 0건이었다. 운영 서버의 `C:\Oracle\instantclient_23_0` 경로와 Oracle Client 권한을 확인한 뒤 동일 스크립트를 재실행해야 한다. PostgreSQL 코드·컬럼 매핑은 이 조회 실패와 분리되어 기본 컬럼 fallback을 유지한다.
