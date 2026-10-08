# Forecasting UI 연결

`Forecasting.tsx`는 실제 `POST /api/forecasting/baseline`을 호출해 조위 기준선 예측과 후보 상태를 표시한다. 예측은 승인 전 결과로만 표시한다. 기존 `App.tsx`의 레거시 인코딩 정비 후 라우트를 등록한다.
