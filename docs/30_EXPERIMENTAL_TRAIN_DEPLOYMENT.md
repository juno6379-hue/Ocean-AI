# 30. 실제 원시 자료 학습과 개발용 시험 배포

기준일: **2026-10-08**. 사용자가 **이 PC의 개발용 시험 서버**를 선택했다. 실제 원천의 학습·비교와 별도 loopback 예측 서버를 연결한다. 운영 source 승인·Dataset·Model Registry와 별도의 개발 실행이다.

## 실제 학습 범위

2026-07 인천 `DT_0001`의 단일 `GR_OBS_ST` Parquet에서 AIR_PRES 44,625행, WATER_TEMP 44,626행, SALINITY 44,625행, 합계 **133,876행**을 사용한다. GD 월별 수집본과 합산하거나 GD 월말 부족을 운영 자료로 채우지 않는다. 8개 원문 literal 필드, 파일 전체 SHA와 row-group/row/column locator를 보존한다.

원문 날짜 기준으로 적합 전에 분할을 고정한다. 저장 시간대는 미확정이며 UTC로 변환하지 않는다.

| 분할 | 원문 날짜 범위 | 항목별 행 수 |
|---|---|---|
| TRAIN | 7/1 이상 ~ 7/19 미만 | 25,920 |
| VALIDATION | 7/19 이상 ~ 7/25 미만 | 8,640 |
| TEST | 7/25 이상 ~ 8/1 미만 | 10,065 / 10,066 / 10,065 |

최근 3개 원시 숫자로 다음 관측 행의 원시 숫자를 예측한다. 같은 분할의 인접 4행이 모두 수치·시각 조건을 통과한 경우만 평가한다. 보간하거나 분할 경계를 넘는 쌍을 만들지 않는다. 누락된 원문 시각 간격을 건널 수 있으므로 1분 예측이나 물리 시간 지평으로 표시하지 않는다.

PERSISTENCE와 Ridge 5개 alpha를 실제 비교했다. 평균·표준화·계수는 TRAIN만 사용하고 VALIDATION MAE로 선정한다. TEST는 선정 후 평가에만 사용하며 VALIDATION으로 다시 적합하지 않는다. 이번에는 세 항목 모두 **PERSISTENCE**가 선정됐다.

## 실행과 웹

- 학습: [CLI](../ocean-ai-platform/backend/app/scripts/train_raw_next_row.py), [학습 서비스](../ocean-ai-platform/backend/app/services/raw_next_row_training.py).
- 시험 배포: [CLI](../ocean-ai-platform/backend/app/scripts/raw_forecast_development_server.py), [모델·근거 검증 서비스](../ocean-ai-platform/backend/app/ml/raw_forecast_development_server.py).
- [MLOps 웹](http://127.0.0.1:5174/mlops)의 **개발용 학습 · 로컬 시험 배포**에서 고정 행 수·후보 오차·Release/모델/참여 SHA와 실제 예측을 확인한다.

시험 서버는 **127.0.0.1:8011**에만 바인딩한다. 기존 review8010, canonical8000/5173와 운영 worker를 바꾸지 않는다. Vite `/experimental-api`가 이 서버로 연결되며 운영 담당자 token을 전달하지 않는다.

| 경로 | 내용 |
|---|---|
| `GET /health` | 별도 개발 프로세스 응답 |
| `GET /readiness` | release 현재 검증 상태·모델 수 |
| `GET /release` | 항목·후보·고정 평가·원문 시각·학습/배포 근거 |
| `POST /predict` | 선택 release/artifact와 입력에 연결한 실제 예측 |

예측 요청은 `model_id`, `values`, `expected_release_id`, `expected_artifact_sha256`를 요구한다. 오래된 선택은 409로 차단하며 정확히 3개의 유한 숫자를 받는다. 모델은 숫자 JSON이며 pickle이나 사용자 query 경로를 로드하지 않는다.

backend 디렉터리에서 실행한다. 새 학습은 현재 원천 manifest 전체 SHA를 고정하고 새 출력 디렉터리를 사용한다.

```powershell
python -m app.scripts.train_raw_next_row `
  --source-manifest D:/AI_Observation/outputs/monthly-report-matching/202607/metric-enrichment/source-file-manifest.json `
  --source-manifest-sha256 e6968bfa4a162ffa1561383dcd4004323470e6002b9667da227040ff88875240 `
  --output D:/AI_Observation/outputs/train-deploy-20261008/training

python -m app.scripts.publish_raw_training_release `
  --training-root D:/AI_Observation/outputs/train-deploy-20261008/training `
  --release-root D:/AI_Observation/outputs/train-deploy-20261008/training/release-v1

python -m app.scripts.publish_raw_training_release `
  --parent-release-root D:/AI_Observation/outputs/train-deploy-20261008/training/release-v1 `
  --release-root D:/AI_Observation/outputs/train-deploy-20261008/training/release-v2

python -m app.scripts.raw_forecast_development_server `
  --register D:/AI_Observation/outputs/train-deploy-20261008/training/release-v2 `
  --validate-only

python -m app.scripts.raw_forecast_development_server
```

원천·참여 목록·학습/평가 receipt·모델 SHA가 맞는 release만 별도 `deployment/releases`에 보존하고 active pointer로 연결한다. 이전 release를 보존하고 재시작하면 고정 release를 다시 검증한다. 이후 파일이 바뀌면 예측을 차단한다. runtime 산출물은 `D:/AI_Observation/outputs/train-deploy-20261008`에만 보존하며 Git에 원문·행별 값·모델 계수를 게시하지 않는다.

## 완료의 범위와 검증

실제 보존 원천으로 개발용 학습·비교·서빙을 수행한다. 물리 단위·시간대·QC 판본·실물 센서 episode·온라인 가용성과 업무 수용 기준은 미확정이다. MAE/RMSE는 원시 숫자 오차이며 고장 탐지 정확도나 승인된 물리 성능이 아니다. 시험 release에 `experimental=true`, `nonoperational=true`, `approved=false`, `production_eligible=false`를 유지한다. 운영 원천·Dataset·Model Registry·승인 및 운영 모델 수는 변경하지 않는다.

최종 시험·실 HTTP·브라우저·독립 수치 검증은 [기계 판독 결과](30_EXPERIMENTAL_TRAIN_DEPLOYMENT.json)를 따른다. 이전 13단계 검증은 [29](29_DEVELOPMENT_STAGE_EXECUTION.md)에 보존한다.
