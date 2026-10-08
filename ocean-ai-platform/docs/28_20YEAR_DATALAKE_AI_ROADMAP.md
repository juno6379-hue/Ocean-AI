# 20년 관측자료 Data Lake 및 AI 계획

2001~2021 원천 PRD/TXT/DAT 전체를 운영 PostgreSQL에 일괄 적재하지 않는다. 원본은 보존 영역에 두고 체크섬·파서 버전을 기록하며, 정제 결과는 `year/month/station_id/variable_code` 파티션 Parquet으로 저장한다. PostgreSQL에는 최근 운영자료, 집계 통계, QC 결과, 승인 Label, Dataset/Model Registry와 Data Lake 위치만 적재한다.

결측 보간·QC Copilot은 보간값·신뢰도·모델 버전을 원시값과 분리하고 승인 요청을 반환한다. AI Insights는 월·연도 집계로 해수면 상승률·변화점 후보를 분석 결과로 제공한다. Forecasting은 시간 순서·관측소 누수 방지 Dataset으로 수일 예측 모델을 학습하고 Precision/Recall/F1/AUROC, FPR/FNR, latency를 기록한다.

기존 `QCCopilot`, `AIInsights`, `MLOps` 메뉴는 각 기능 화면으로 유지하고, 저장 정책과 전체 파이프라인 상태를 보여주는 `Data Lake & AI 계획` 메뉴를 추가한다. 실행 순서는 `원본 inventory → Parquet 변환/검증 → 통계 적재 → 보간 학습 → 장기 추세 → Forecasting → UI 연결`이다.
