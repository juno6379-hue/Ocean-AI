# Fitted 이상탐지 개발 분석

기준일: 2026-10-08

## 실행 범위

[anomaly_analysis](../ocean-ai-platform/backend/app/services/anomaly_analysis.py)는 시계열의 과거 학습 구간과 별도 보정 구간에서 통계를 적합하고, 이후 시계열에 고정된 모델을 적용한다. 임의의 조위 50·800 같은 고정 수치를 실제 모델 성능으로 표시하지 않는다. 결과는 `ANALYSIS_ONLY`, `approved=false`, `production_eligible=false`다. 원천 QC·최종 QC·원인 라벨·Registry·승인 원장은 변경하지 않는다.

순수 개발 분석은 운영 승인 계정 설정 전에도 local loopback API로 실행할 수 있다. 요청은 4 MiB·최대 10,000행과 2,000,000개 window-row 연산 예산으로 제한하며 원천 파일이나 실행 가능한 모델을 업로드·역직렬화하지 않는다. 큰 window의 예산 초과도 구체적 미평가 사유로 반환한다. API는 숫자와 메타데이터를 가진 JSON artifact/report를 반환하고 파일·DB에 자동 적재하지 않는다.

개발 입력의 근거 권위는 `DECLARED_DEVELOPMENT_CONTRACT`다. caller가 제공한 근거 hash·locator와 사실 선언을 고정해 재현하지만 원문 행이나 실제 SOURCE_CONTRACT 승인 권위를 자동 검증한 것으로 간주하지 않는다. artifact의 SHA 역시 내용 무결성 값이며 인간 서명이나 운영 모델 승인 receipt가 아니다. 실제 생산 학습·모델 운영에는 [원천·Dataset 승인](18_DATASET_REGISTRY.md)과 [독립 모델 검토·배포 승인](19_MLOPS_VERSION_AND_EVALUATION.md)을 따로 통과해야 한다.

## 입력·고정 분할·가용 시각

시계열은 다음 계약을 명시한다.

- scope: station·physical sensor·sensor episode·variable·unit의 정확한 단일 범위. 각 행과 reference도 범위를 대조한다.
- facts: 의미·변수 family·단위·시계·QC 코드북·센서 구간의 근거 SHA/locator 및 시행기간. 현재 metadata 단위가 과거 모든 기간에도 적용된다고 추정하지 않는다.
- row: 고유 row ID, 원문 source SHA/행·열 locator, 명시 offset 시각, 수신/가용 시각, QC 가용 시각, 값, 사용 가능 QC 선언. NULL·미확정·비유한 값은 정상 판정으로 채우지 않는다.
- protocol: 버전·과업, 정확한 train/calibration 반개방 기간과 membership digest, 입력 간격, trailing window, 최소 유효 표본 수, 단위 해상도 floor·persistence epsilon, calibration quantile.
- reference/context: 아래 과업별 독립 기준 자료와 장비 기전 후보의 문서 근거.

학습과 보정 기간은 겹칠 수 없고 정렬되지 않은 시각·중복 관측·source cell 재사용을 거부한다. 적합 시 test 행을 입력하면 차단하며, 분석 구간은 calibration 종료와 모델 적합 가용 시각 뒤여야 한다. train·calibration·test 사이에 primary 또는 reference cell을 재사용할 수 없다.

특성은 현재와 과거만 포함한다. 정확한 간격에 결측·gap·episode 변경이 있으면 window를 이어 붙이거나 forward-fill하지 않는다. source/QC/reference 가용 시각이 분석 as-of보다 늦으면 미평가다. 결과 가용 시각에는 사용한 전체 window와 reference의 QC 가용 시각도 포함한다. 이 시각을 관측 시각으로 덮어써 과거 온라인 판단에 사용하지 않는다. 시간순 평가의 필요성은 [scikit-learn 시계열 평가 설명](https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split)을 참고한다.

## 실제 적합 방법

train에서 median·MAD 기반 residual scale, 변화량 scale, 정상 window range와 reference 대비 response ratio를 추정한다. 보정 데이터에는 이 train 통계를 그대로 적용하고, `numpy.quantile(..., method="higher")`로 각 모드의 경험적 임계값을 고정한다. 보정 데이터로 train 통계를 재적합하지 않으며 이후 평가 시 임계값을 바꾸지 않는다. quantile 연산은 [NumPy 공식 설명](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html)을 따른다.

| 모드 | 적합·분석 내용 | 근거 부족 시 |
|---|---|---|
| SPIKE | 연속 두 값의 변화량을 train robust scale로 나누고 보정 임계값과 비교 | 정확한 간격·사용 가능한 QC·원천 근거 없으면 NOT_EVALUATED |
| PERSISTENCE | train의 대표 window range 대비 현재 range, 명시 epsilon 이하의 flat window 확인 | train부터 평탄하거나 window가 불완전하면 미평가 |
| TIDE_RESIDUAL | 실제 조위와 동일시각 예측조위 residual의 train 중심·scale 대비 편차 | 단위·기준면·시행기간·예측 issued-at/학습 종료 근거가 없거나 hindcast가 미래에 발행되면 미평가 |
| DRIFT | TEMP/SAL의 독립 기준 센서에 대한 trailing residual median 편차 | 같은 station·variable·unit과 명시된 reference 센서/episode·QC 구간이 없으면 미평가 |
| SENSOR_DEGRADATION_CANDIDATE | 지속 residual bias·noise의 증가를 검토 신호로 제공 | 독립 reference와 해당 장비 기전 검토 문서가 없으면 미평가 |
| BIOFOULING_CANDIDATE | residual drift와 reference 대비 response damping을 검토 신호로 제공 | reference 변동이 부족하거나 장비 적용 근거가 없으면 미평가 |

단위는 자동 변환하지 않는다. TEMP는 명시한 섭씨·Kelvin·화씨 표현, SAL은 명시한 salinity 표현, TIDE는 명시한 길이 단위를 제한적으로 지원하며 서로 다른 단위의 paired reference는 거부한다. 이는 해당 원천 단위의 역사적 적용을 승인한 목록이 아니다.

spike/flat-line 같은 QC 검사와 학습한 통계 점수는 구분한다. [IOOS QARTOD 온·염분 QC 자료](https://ioos.noaa.gov/ioos-in-action/temperature-salinity/)는 QC 검토 배경이며 이 개발 모델의 threshold·장비 원인·운영 수용 기준을 승인한 근거가 아니다. 환경 변화도 유사한 신호를 만들 수 있으므로 biofouling·degradation은 후보이고 `cause_attribution=NOT_ESTABLISHED`를 유지한다.

## 점수·artifact·API

`score`는 위 모드의 통계량이고 `calibration_rank`는 보정 통계량 분포에서의 경험적 순위다. `support_strength`는 ANOMALY에 rank, NORMAL에 1-rank를 사용하며 UNKNOWN에는 null이다. 어떤 값도 장비 고장 확률·분류 확률 또는 규제상 confidence가 아니다. 작은 표본·연속 상관·환경 변화에서 운영 false-positive 보장을 제공하지 않는다.

[numeric artifact](../ocean-ai-platform/backend/app/ml/anomaly_artifact.py)는 protocol/contract/data SHA, 분할별 SHA, exact source cell, 적합 통계·보정 점수·임계값·제외 사유와 코드/Python/NumPy fingerprint를 보존한다. hash 변조·코드 변경·보정 점수와 임계값 불일치·scope 변경은 차단한다. H5/pickle/joblib 실행 모델을 읽지 않는다.

```text
POST /api/anomaly-analysis/fit
  {series: ocean-anomaly-series-1, protocol: ocean-anomaly-protocol-1}
POST /api/anomaly-analysis/analyze
  {series: 이후 시계열, artifact: fit 응답의 artifact envelope}
```

순수 함수는 `fit_analysis(series, protocol)`, `analyze_series(series, artifact)`다. 분할을 아직 정할 수 없는 실제 자료는 `source_requirements(series)`로 필요한 사실·시계 조건을 점검할 수 있다. 이 함수는 실제 자료를 train/test로 임의 배정하거나 fitting하지 않는다. 결과의 event/available 시각, exact scope, 원문/reference locator, report·artifact SHA는 [evidence fusion](../ocean-ai-platform/backend/app/services/evidence_fusion.py)의 검토 근거로 전달한다. Fusion 점수 역시 최종 QC나 원인 승인과 별개다.

## 검증과 실제 원천 상태

2026-10-09 QC 상세 Drawer는 정확히 연결된 **저장 AI 결과**만 읽는다. 예상값·Residual·score를 원문 실측과 분리하고 같은 source/row/physical sensor/기간·가용 판본과 SHA가 맞지 않으면 표시하지 않는다. 실제 모델이 없으면 미실행/모델 없음이며 가짜 예측선을 만들지 않는다. 화면 클릭의 새 추론·학습·배포는 이 후속 개발에 포함하지 않았다. [36의 구현·검증](36_QC_OPERATIONAL_DASHBOARD_EXECUTION.md), [34의 목적별 학습·평가 준비도](34_PURPOSE_DATASET_MODEL_READINESS_REVIEW.md)를 구분한다.

[격리 시험](../ocean-ai-platform/backend/tests/test_anomaly_analysis.py)은 합성 정상 자료와 별도 heldout 결함을 사용한다. 고정 합성 시나리오에서 healthy SPIKE는 159개 평가 중 5개 false positive(약 3.14%), 주입한 spike edge 6개는 TP 6/FN 0이었다. TEMP/SAL drift의 충분히 진행된 마지막 40개는 각각 40개 탐지했고 flatline 마지막 50개는 50개 탐지했다. 이는 합성 검증 값이며 실제 해양관측 성능이나 원인 정답률이 아니다.

2026-10-08 읽기 전용 smoke에서 보존 `GR_OBS_ST_202609` Parquet의 전체 bytes SHA가 manifest와 일치했고 DT_0001 WATER_TEMP 500행의 유한 값을 읽었다. 원문 시각은 offset 없는 문자열이며 과거 기간 단위·QC 코드북·물리 센서 구간이 미확정이다. 요구조건 점검은 NOT_EVALUATED였고 실제 원천 fitting·Registry 등록·운영 배포는 수행하지 않았다. 삭제된 원본 CSV를 현재 보존 원본으로 표시하지 않는다.

운영 전에는 실제 source/reference 근거, 장비 점검·세척·교체 사건, 고정 검증 모집단과 수용 정책을 확정해야 한다. [72업무](19_MLOPS_VERSION_AND_EVALUATION.md)의 기존 representation baseline partial 상태를 이 개발 엔진만으로 운영 완료로 바꾸지 않는다.
## 10/8 단계별 보완 결과

이전9월 WATER_TEMP requirements-only smoke와 별도로, 2023-01 DT_0001 native3항목에서 raw schema로300/100/100고정 fit/calibration/test를 실행했다. 600예측 중552평가/48warm-up, 후보0/14/0이다. 원문 시각을 명시적 NATIVE_CLOCK_ASCENDING으로 정렬하되 물리 단위/UTC/센서/QC/availability를 확정하지 않는다. exact row/manifest SHA와 독립 재산정 및 raw Fusion3건을 보존했다. production 물리 fit0, cause/accuracy미산정. [29](29_DEVELOPMENT_STAGE_EXECUTION.md).
