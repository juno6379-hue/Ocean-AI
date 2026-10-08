# 장기 추세·조위 예측 기준선

`analyze_long_term.py`는 Parquet의 조위 시계열을 관측소별로 집계해 연간 선형 추세와 월별 중앙값을 산출한다. 결과는 `ANALYSIS_ONLY`이며 관측소별 기간·표본 수를 함께 기록한다.

`forecast_tide_baseline.py`는 MLOps 후보 등록 전 기준선인 persistence 예측을 생성한다. 1·6·24·72시간 horizon을 지원하고, 실제 모델 비교 시 Precision/Recall/F1/AUROC/FPR/FNR/latency 지표를 채운다. 기준선 결과는 `CANDIDATE` 상태로만 저장하며 배포 전 승인이 필요하다.

실행 순서는 `Parquet 변환 → 장기 추세 JSON → 기준선 예측 JSON → Dataset/Model Registry 등록 → 후보 모델 학습·비교 → UI 표시`다.
