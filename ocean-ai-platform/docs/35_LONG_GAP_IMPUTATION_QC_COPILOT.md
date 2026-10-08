# 긴 결측 보간 모델 확장 및 QC Copilot 연결

`/api/qc/copilot/analyze` 응답에 `imputation_candidates`를 추가해 관측소의 기존 보간 후보를 함께 표시한다. 후보는 `ObservationImputation`에서 조회하며 원본 관측값과 분리된 승인 대기 데이터다.

`POST /api/imputation/long-gap/plan`은 긴 결측 학습 계획을 생성한다. 후보 모델은 GRU-D(불규칙 샘플·결측 마스크), BRITS(양방향 결측 추정), SAITS(다변량 attention)이며 현재 상태는 `QUEUED/CANDIDATE`다. 학습 전에는 실제 결측을 가린 masking 검증, 시간·관측소 누수 검사, Dataset/Feature/Preprocessing 버전 등록을 수행한다.

딥러닝 결과도 원본을 덮어쓰지 않고 보간값·신뢰도·모델 버전·입력 구간을 별도 저장한다. QC Copilot은 근거와 함께 승인 요청만 생성하며 사람 승인 전 최종 QC를 변경하지 않는다.
