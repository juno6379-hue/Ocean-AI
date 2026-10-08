# AI Insights 분석과 원천 검토 화면

현행화: 2026-10-08

## 분석 결과와 승인 결과

분석 API의 최상위 상태는 `ANALYSIS_ONLY`다. 개별 결과의 `ANALYSIS`, `CANDIDATE`, `RECOMMENDATION`은 검토 자료이며 QC 최종값·원인 라벨·재학습 작업·운영 모델을 확정하지 않는다. 승인과 모델 실행은 [Human-in-the-loop](17_HUMAN_IN_THE_LOOP.md), [Dataset Registry](18_DATASET_REGISTRY.md), [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md)의 별도 경로를 따른다.

## 현재 화면의 데이터 경로

현재 [AIInsights 화면](../ocean-ai-platform/frontend/src/pages/AIInsights.tsx)은 [AnalysisWorkspace](../ocean-ai-platform/frontend/src/components/AnalysisWorkspace.tsx)를 사용한다. `/api/lake/monitoring`과 `/api/lake/summary`에서 원천·기간·관측망·해역·관측소·항목별 보유 자료와 검토 근거를 조회한다. QC Copilot도 같은 component를 사용하며 Insights 표시 모드만 다르다.

두 조회의 snapshot과 선택 범위가 일치하는지 확인하고, 없는 월의 지표는 `null`로 보존한다. 원천 QC 값이 있는 비율은 QC 판정의 의미나 정상률을 입증하지 않는다. 보유 행 수 역시 예상 수집 대상에 대한 수집률을 뜻하지 않는다. 의미·단위·QC 코드북·센서 유효기간이 승인되지 않은 자료를 정상 관측이나 운영 모델 성과로 표시해서는 안 된다.

## 별도로 유지되는 분석 API

[기존 AI Insights API](../ocean-ai-platform/backend/app/api/routes_ai_insights.py)는 아래 집계를 제공한다. 현재 화면이 이 API를 호출하는 것은 아니다.

| 응답 | 현재 계산과 해석 범위 |
|---|---|
| `station_quality_risk` | 저장된 최종 QC 4에 가중치 1, QC 3에 0.5를 적용하고 AI 추천 BAD/SUSPECT 건수 보너스를 더한다. 40·70 구간과 가중치는 코드의 휴리스틱이며 승인된 위험 정책이 아니다. |
| `variable_quality_score` | 위 위험 점수의 보수로 계산한다. QC가 없을 때 라벨 수가 분모로 사용될 수 있어 공인 품질 정확도가 아니다. |
| `recurring_anomaly_pattern` | AI 추천의 관측소·항목·UTC 시간대 반복을 집계한다. 사건 원인이나 주기성 검정 결과가 아니다. |
| `sensor_degradation_candidate` | 저장된 `sensor_degradation` 라벨의 근거와 confidence를 반환한다. 이 조회는 승인된 라벨만 선택하는 필터가 없다. |
| `repeated_communication_failure` | 운영 로그의 통신 관련 문자열이 2회 이상인 관측소·센서를 반환한다. 실제 장애 사건 연결과 유효기간 검토는 별도다. |
| `repeated_qc_false_positive` | `qc_algorithm_error` 라벨이 2회 이상인 관측소를 반환한다. 실제 false-positive rate 평가가 아니다. |
| `quality_trend` | 저장된 QC 3/4의 일자별 건수다. 모수·단위·장비 변화가 보정된 추세는 아니다. |
| `retraining_priority` | 위험 점수와 위 후보의 존재를 근거로 검토 순위를 만든다. 학습 큐에 작업을 등록하지 않는다. |

이 경로는 `QCFlagHistory`, `AILabel`, `AIPredictionResult`, `OperationLog`, `StationMetadata` 등을 읽는다. 미승인 라벨이나 과거 모의 관측이 들어 있는 DB의 집계를 실제 승인 원천 평가로 사용하지 않는다. 자료가 없을 때의 0점·빈 목록은 정상 판정이 아니다.

```text
GET /api/ai-insights/summary?station_id=<station_id>
GET /api/ai-insights/long-term?station_id=<station_id>&variable_code=<variable_code>
```

`long-term`의 `annual_slope`는 첫 값과 마지막 값의 차이를 경과 시간으로 나눠 연율화한다. 회귀 추정·유의성 검정·계절 보정·승인 단위 검증을 수행하지 않으며, 표본이 부족하면 0을 반환한다. 이를 장기 해양 변화의 확정 결과로 해석하지 않는다.

## 검증과 남은 작업

최신 전체 backend 회귀와 frontend build 결과는 [10/8 감사](10_IMPLEMENTATION_AUDIT.md)에 기록한다. 이는 분석 경로와 코드의 검증이며 실제 위험 점수의 현장 성능 검증은 아니다. 같은 날 13:09 KST 읽기 전용 DB 확인에서는 승인 이력·데이터셋·모델·사건 연결 기록이 모두 0이었다.

실제 활용에는 승인 원천과 라벨, 기간·사건 연결, 업무별 평가 모집단, 위험 정책의 보정 및 담당자 검토가 필요하다. 현재 실행 상태와 근거 시점은 [P0 진행 현황](24_P0_END_TO_END_PROGRESS.md), 화면 연결은 [프런트엔드 문서](22_FRONTEND_OPERATIONS_AUDIT.md)를 확인한다.

## 10/8 추가 fitted 모델과의 구분

[25: 이상탐지 AI](25_ANOMALY_AI.md)는 fixed TRAIN/CALIBRATION과 numeric artifact를 사용하는 통계 fit/analyze다. 이 문서의 legacy Insights 휴리스틱과 별도다. 실제 원천 조건이 미확정인 입력은 NOT_EVALUATED이고 실제 source fit/운영 registry는0이다. 새 [Fusion](21_MULTI_AGENT_WORKFLOW.md)의 Recommendation score 역시 개발 recipe이며 고장 확률이 아니다.
