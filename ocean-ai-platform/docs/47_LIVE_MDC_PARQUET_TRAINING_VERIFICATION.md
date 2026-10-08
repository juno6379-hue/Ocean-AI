# 실제 MDC·PostgreSQL·기존 Parquet 학습 검증

검증일: 2026-09-29. 최초 수온 검증을 조위·기압·풍속 및 기존 Data Lake로 확대했다. 합성자료 회귀 테스트와 아래 실제 관측자료 학습 결과를 구분한다. 상세 분할 기간·건수·해시는 `47_validation_summary.json`에 기록한다.

## 실제로 읽은 자료와 결과

모두 시간순 60% 학습 / 20% 검증 / 20% 테스트이며, 검증 구간에서 Ridge 정규화 강도를 선택한 뒤 학습+검증으로 재학습했다. 아래 MAE는 마지막 테스트 구간의 1시간 앞 **시간평균** 예측 오차다.

| 원천 / 항목 | 관측소 | 읽은 행 | 모델 MAE | 직전값 유지 MAE |
|---|---|---:|---:|---:|
| Oracle WEB_OBS_ST / 수온 | UN_0006 | 101,751 | 0.460 °C | 0.477 °C |
| Oracle TP_OBS_SO / 조위 | SO_1291 | 53,137 | 5.212* | 89.079* |
| Oracle WEB_OBS_ST / 기압 | UN_0002 | 103,573 | 0.233 hPa | 0.366 hPa |
| Oracle WEB_OBS_ST / 풍속 | UN_0002 | 103,576 | 0.424 m/s | 0.442 m/s |
| 기존 Parquet / OTT 조위 | DT_0001 | 10,648,794 | 7.166 cm** | 97.404 cm** |

* SO_1291의 단위는 기존 `TIDE_LEVEL→cm` 매핑에 따른 표기다. `WEB_OBS_ITEM_INFO`에서 해당 관측소의 단위 메타데이터를 찾지 못했으므로 수치 자체의 검증과 물리 단위 확인을 구분한다. 기준면·관측소 장비 명세 확인 전 운영 성능으로 확정하지 않는다.

** 역사 자료는 OTT 조위 파일을 cm·Asia/Seoul로 해석한 결과다. Parquet 자체에는 시간대가 없으므로 원본 운영 명세와 최종 대조해야 한다. 기압·풍속 단위는 MDC 항목 메타데이터의 hPa·m/s와 일치했다. 수온 메타데이터의 한글 단위는 Oracle 문자열 인코딩이 깨져 기존 C 매핑을 유지했다.

MDC 기간은 수온 2011-12~2013-10, 기압·풍속 2013년, 조위 2025-01~2026-01이다. 현재 시점의 실시간 관측이라는 뜻이 아니다. MDC에서 원본 QC 컬럼을 제공하지 않은 추출은 `UNREVIEWED`로 보존했다.

## Oracle → PostgreSQL 검증

- Oracle은 읽기 전용 트랜잭션, 바인드 변수, 행 상한, 연결·호출 시간 제한을 사용했다. 선택적 QC 컬럼이 없다는 ORA-00904일 때만 기본 컬럼 조회로 재시도한다. 접속 장애를 빈 자료로 처리하지 않는다.
- 실제 PostgreSQL 연결에서 임의 이름의 격리 스키마를 만들었다. Raw/Standard 건수와 관측값, 원본 KST에서 UTC로의 변환을 확인했고 최초 1,000행 재적재 시 추가 행은 0이었다.
- 센서 메타데이터를 배치 안에서 중복 생성하던 문제를 수정했다. 원천 항목 및 수심별 센서 구분을 유지한다.
- 학습 산출물을 저장하고 다시 읽어 예측값 일치를 확인했다. 예측 모델을 레지스트리에 `PENDING_APPROVAL`로 등록하는 경로도 검증했다.
- 각 검증의 외부 PostgreSQL 트랜잭션을 롤백하고 스키마 소멸을 확인했다. 운영 관측·승인·모델 레지스트리에는 검증 데이터를 남기지 않았다.
- 조위는 `TP_OBS_SO`, 기상·수질은 `WEB_OBS_ST`, 부이는 `WEB_OBS_VBU`로 수집 경로를 분리했다. 자동 수집은 계속 기본 비활성화다.

## Data Lake와 다변량 학습

기존 `data_lake/tide_obs/DT_0001.parquet`의 `Time`, `OTT`, `QC2`를 20만 행씩 읽었다. KST 기준 2001-01-01~2021-03-31의 10,648,794행 중 QC가 G인 9,847,505행을 사용하고 B/결측 801,289행을 제외했다. 시간당 유효 관측 30개 이상인 164,393시간을 남겼다. 원본을 다시 변환하거나 결측을 보간하지 않았다. 테스트 표본은 31,072개다.

`spool_2001_2021`의 다른 Parquet 파티션에는 변수·처리단계 분류가 의심스러운 파일이 있어 전체 파일을 일괄 결합하지 않았다. 이번 검증은 모든 관측소·모든 변수를 검증했다는 뜻이 아니다. 원천 컬럼, 단위, QC, 관측소, 시간대, 처리단계별 목록을 먼저 확정해야 한다.

같은 `UN_0002`의 풍속에 기압의 1·6·24시간 전 값을 추가한 다변량 학습도 실행했다. MAE 0.425 m/s, RMSE 0.593 m/s로, 풍속 단독 MAE 0.424보다 개선되지 않았다. 따라서 기압 추가가 성능을 개선했다고 주장하지 않는다. 입력 파일의 검증 보고서와 SHA-256, 관측소 일치를 확인한다. `UN_0002`, `UN_0006`, `SO_1291`, `DT_0001`을 임의로 동일 관측소로 결합하지 않았다.

특징은 과거 지연값과 과거 6시간 평균·표준편차 및 시각 주기다. 각 예측 시점까지 관측된 테스트 구간의 과거값을 사용하는 rolling 평가이며, 24시간 이상의 연속 미래 예측이나 미관측 관측소 일반화 평가는 아니다. 조위의 직전값 유지 기준선은 단순 기준이며 조석 조화분해 모델과의 비교는 아직 수행하지 않았다.

## 재현 명령

`backend` 디렉터리에서 `.env`에 실제 DB 설정을 넣고 실행한다. 비밀번호·접속 문자열·관측 원자료·joblib 파일은 Git에 포함하지 않는다. 출력 경로는 매번 새로 지정한다.

```powershell
$env:PYTHONPATH='.'
python -m app.scripts.validate_live_pipeline --table TP_OBS_SO --station-id SO_1291 --item TIDE_LEVEL --start 2025-01-01 --end 2026-01-06 --output validation_runs/tide-new
python -m app.scripts.validate_live_pipeline --station-id UN_0002 --item AIR_PRES --start 2013-01-01 --end 2014-01-01 --output validation_runs/pressure-new
python -m app.scripts.validate_live_pipeline --station-id UN_0002 --item WIND_SPEED --start 2013-01-01 --end 2014-01-01 --output validation_runs/wind-new
python -m app.scripts.validate_live_pipeline --station-id UN_0006 --item WATER_TEMP --start 2011-12-01 --end 2013-11-01 --output validation_runs/water-temp-new
python -m app.scripts.train_parquet_history --source ../data_lake/tide_obs/DT_0001.parquet --station-id DT_0001 --output validation_runs/history-new
python -m app.scripts.train_mdc_multivariate --target-run validation_runs/wind-new --covariate-run validation_runs/pressure-new --output validation_runs/multivariate-new/candidate
```

로컬 검증 결과는 `backend/validation_runs/20260929-*`에 보존했다. 저장소에는 집계·분할 기간·해시를 담은 요약 JSON만 포함한다. Python/패키지 버전은 각 산출물의 metrics에 기록한다.

## 완료 범위와 남은 연결

실제 DB 연계, 기존 Parquet 읽기, 시간순 학습·평가·모델 저장·재로딩, 승인 대기 등록 경로까지 확인했다. 온라인 재학습 worker 및 학습 모델의 예측 API 서빙 연결은 아직 구현하지 않았다. 기존 예측 API는 직전값 유지 기준선이며 이번 후보 모델로 자동 교체하지 않았다. 부이의 모든 항목·수심에 대한 실제 대량 검증, 동시 승인 잠금, 기존 8년 이동 데이터 복원도 별도 작업이다.

단위 및 변수 분류가 불명확한 항목은 원천 메타데이터를 확인해야 한다. 특히 기존 광범위 WAVE 매핑·레이크 변수 분류는 이번 네 항목 검증으로 보증하지 않는다. 기존 소스 이력에 포함됐던 접속 자격증명은 별도로 교체해야 한다.
