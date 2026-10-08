# `spool(2001_2021)` 분석 및 관측항목별 AI 반영 판단

분석 대상은 `E:\백업\data\old\spool(2001_2021)`이며 원본 파일은 수정하지 않았다. 폴더에는 `00_info`(KOOFS 관측소·센서 메타데이터), `00_sql`(Oracle 추출 SQL), `00_prd`(관측소별 PRD), `01_raw`(월 단위 원시 TXT), `02_cov`(수집률), `03_edt`(편집 결과), `04_fnl`(최종 CSV), `월별자료`(DAT)가 있다. `DT.sql`은 2021년 자료 추출 시 다음 항목을 명시한다.

`TIDE_LEVEL_VEGA`, `TIDE_LEVEL_VEGA_2`, `TIDE_LEVEL_MIROS`, `TIDE_LEVEL_LASER`, `TIDE_LEVEL_LASER_1`, `TIDE_LEVEL_OTT`, `TIDE_LEVEL_WLS`, `WATER_TEMP`, `SALINITY`, `ELECT_CONDUCT`, `WIND_SPEED`, `WIND_DIRECT`, `WIND_GUST`, `AIR_PRES`, `AIR_TEMP`, `MAX_WAVE_HEIGHT`, `MAX_WAVE_PERIOD`, `SIGNIFI_WAVE_HEIGHT`, `SIGNIFI_WAVE_PERIOD`.

## 현재 코드와의 차이

현재 MDC 동기화 코드는 `TIDE`와 `WAVE`만 `ObservationRaw`/`ObservationStandard`로 적재한다. 따라서 아래 판단에서 “즉시 반영”은 현행 파이프라인과 바로 연결되는 항목, “확장 반영”은 원본 컬럼 매핑·단위·QC 규칙·학습 데이터셋을 추가한 뒤 연결할 항목을 의미한다.

| 관측항목 | AI 모델 반영 | 권장 모델/용도 | 반영 방법 및 주의점 |
|---|---|---|---|
| TIDE_LEVEL_* 7종 | 즉시 반영 | 조위 이상탐지, 예측 잔차, 결측·센서 드리프트 | 센서별 원시값을 보존하고 기준 센서(VEGA 등)와 보조 센서의 교차검증 Feature를 생성한다. 최종 QC는 승인 전 분석 상태로 유지한다. |
| MAX_WAVE_HEIGHT | 즉시 반영(확장) | 파고 이상탐지·단기 예측 | `WAVE` 표준 코드로 매핑하되 원본 항목 코드를 `metadata_json`에 남긴다. 단위 m, 물리 범위와 급변률 QC를 적용한다. |
| SIGNIFI_WAVE_HEIGHT | 확장 반영 | 유의파고 예측·이상탐지 | 최대파고와 분리된 변수로 저장한다. 파고 계열 간 물리적 일관성 Feature를 사용한다. |
| MAX_WAVE_PERIOD | 확장 반영 | 파주기 이상탐지 | 초 단위 표준화, 파고와의 결합 Feature를 생성한다. |
| SIGNIFI_WAVE_PERIOD | 확장 반영 | 유의파주기 이상탐지 | 초 단위 표준화 및 결측 구간 분리. |
| WATER_TEMP | 확장 반영 | 계절·추세 기반 이상탐지, 센서 열화 후보 | `WATER_TEMP`와 ℃ 단위 매핑, 계절성·수심·인접 관측소 Feature가 필요하다. |
| SALINITY | 확장 반영 | 염분 이상탐지·수괴 변화 분석 | PSU 단위를 보존하고 수온·전기전도도와 교차변수 QC를 적용한다. |
| ELECT_CONDUCT | 확장 반영 | 센서 상태 및 염분 보조 Feature | ms/cm 단위 확인 후 염분과 일관성 검사에 사용한다. 단독 예측 타깃보다는 보조 Feature가 적합하다. |
| WIND_SPEED | 확장 반영 | 풍속 이상탐지·단기 예측 | m/s 표준화, 풍향과 벡터 Feature로 결합한다. |
| WIND_DIRECT | 확장 반영 | 풍향 이상탐지 | 각도형 변수이므로 일반 평균 대신 sin/cos 변환을 사용한다. |
| WIND_GUST | 확장 반영 | 극값·돌풍 이벤트 탐지 | 풍속 대비 돌풍 비율과 임계 초과 이벤트를 생성한다. |
| AIR_PRES | 확장 반영 | 기압 급변·폭풍 전조 탐지 | hPa 표준화, 조위·풍속과 시간 지연 Feature를 사용한다. |
| AIR_TEMP | 확장 반영 | 기온 추세·센서 이상탐지 | ℃ 표준화, 계절성과 결측 패턴을 분리한다. |
| RECEIVE_TIME | Feature/운영 품질 전용 | 통신 지연·수집률 예측 | 관측값 타깃으로 학습하지 않고 `latency`, 지연 구간, 통신 장애 이벤트 Feature로만 사용한다. |
| QC_FLAG/MQC_FLAG | Label 후보·검증 기준 | 지도학습 Label 및 평가 | AI Label과 동일시하지 않는다. 기존 플래그는 weak label로 저장하고 Human Approval 후 확정 Label로 승격한다. |

## 반영 우선순위

1. **P0**: 조위 7종과 파고 4종의 원본 항목 코드를 표준 `variable_code`로 확장하고 `ObservationStandard`에 단위·변환 규칙을 기록한다.
2. **P1**: 수온·염분·전기전도도·기상 6종을 추가하고 교차변수/계절성 Feature 및 항목별 QC Rule을 등록한다.
3. **P1 운영**: `RECEIVE_TIME`, `02_cov`, `03_edt`, `04_fnl`은 관측값 학습셋에 직접 섞지 않고 수집률·통신·수동편집 이력으로 연결한다.
4. **P2**: 2001~2021 장기자료로 항목별 Dataset Version을 만들되, 시간 기준 분할과 관측소 기준 분할을 동시에 검증한다. 2021년 이후 자료는 현재 MDC 동기화 자료와 별도 버전으로 관리한다.

## 적재·학습 전 필수 검증

- `DT_` 관측소 코드와 현재 `StationMetadata.station_id` 매칭률 및 폐쇄·이전 이력을 확인한다.
- PRD/TXT/DAT의 시간대와 현재 동기화의 8년 시프트 규칙을 분리 기록한다. 원본 시각과 표시 시각을 덮어쓰지 않는다.
- 항목별 단위, 샘플 주기, 결측 코드, 중복 키를 프로파일링한 후 적재한다.
- `QCFlagHistory`는 원본 QC 이력으로 보존하고, `QCRuleResult`는 실행된 규칙별 결과로 저장한다.
- AI 학습에는 승인된 `AILabel`만 사용하며, 원본 QC 플래그나 모델 추천값을 자동 정답으로 사용하지 않는다.
- 문서·보고서는 구조화 관측값과 분리해 DocumentIndex/Embedding에 넣고, 관측 레코드에는 근거 문서 ID만 연결한다.

현재 단계의 결론은 조위·파고 계열을 우선 AI 모델에 연결하고, 나머지 항목은 데이터 프로파일링과 표준화 완료 후 확장 모델에 포함하는 것이다. 이 판단은 원본 보유 여부가 아니라 현재 코드의 실제 적재 범위와 항목별 물리적·운영적 활용성을 기준으로 했다.
