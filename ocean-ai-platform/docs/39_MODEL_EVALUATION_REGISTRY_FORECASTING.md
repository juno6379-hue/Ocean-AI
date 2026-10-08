# 모델 평가·Registry·AI Insights·Forecasting 연결

## API

- `POST /api/forecasting/baseline`: 실제 PostgreSQL 최신 조위에서 기준선 예측 생성
- `GET /api/forecasting/models`: 조위 모델 Registry 조회
- `GET /api/ai-insights/long-term`: 관측소별 장기 조위 추세 분석

예측은 `CANDIDATE`, `approval_required=true`로 반환되며 자동 배포하지 않는다. 모델 Registry에는 dataset/feature/label/preprocessing 버전과 평가 지표(Precision, Recall, F1, AUROC, FPR, FNR, latency)를 등록한다. AI Insights는 `ANALYSIS_ONLY`이며 상승률이나 이상 후보를 최종 판정으로 사용하지 않는다.

## 평가 순서

시간 순서 TEST에서 horizon별 MAE/RMSE를 계산하고 이상탐지 평가에는 Precision/Recall/F1/AUROC/FPR/FNR을 사용한다. latency를 함께 기록한 뒤 ModelRegistry에 후보를 저장하고 Human Approval 후 Champion으로 승격한다.
