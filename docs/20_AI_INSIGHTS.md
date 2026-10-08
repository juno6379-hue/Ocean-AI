# AI Insights 분석 API

작성일: 2026-09-16

## 원칙

AI Insights는 자동 확정 기능이 아니다. 응답 최상위 `status`는 항상 `ANALYSIS_ONLY`이며, 후보와 추천에는 `status=ANALYSIS`, `CANDIDATE`, `RECOMMENDATION`을 표시한다. QC Flag·AI Label·모델 상태를 이 API가 자동 변경하지 않는다.

## 제공 분석

`GET /api/ai-insights/summary`에서 다음 결과를 제공한다.

- 관측소별 `station_quality_risk`
- 변수별 `variable_quality_score`
- 시간대 반복 이상 `recurring_anomaly_pattern`
- `sensor_degradation_candidate`
- `repeated_communication_failure`
- `repeated_qc_false_positive`
- 일자별 `quality_trend`
- 근거를 포함한 `retraining_priority`

계산에는 `QCFlagHistory`, `QCRuleResult`, `AIPredictionResult`, `AILabel`, `OperationLog`, `StationMetadata`를 사용한다. QC Flag 3/4, AI 이상 추천, 원인 라벨, 통신 이벤트 반복을 집계해 위험·우선순위를 계산하며, 데이터가 없으면 0점/빈 후보를 반환한다.

선택적으로 `station_id`를 전달해 한 관측소만 분석할 수 있다.

```text
GET /api/ai-insights/summary?station_id=DT_0001
```

라우터를 `main.py`에 등록하고 빈 데이터베이스에서 분석 API가 오류 없이 응답하는 것을 확인했다.
