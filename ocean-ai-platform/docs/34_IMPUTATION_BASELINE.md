# 결측치 보간 기준선

`POST /api/imputation/run`은 조위(`TIDE`)를 우선 대상으로 두 관측값 사이의 짧은 결측 구간을 선형 보간한다. 기본 허용 간격은 3주기이며, 보간값은 `ObservationImputation`에 원본 관측 ID·간격 길이·신뢰도·모델 버전과 함께 저장한다.

보간값은 원본 `ObservationStandard`를 덮어쓰지 않고 `PENDING` 승인 상태로 반환한다. 긴 결측은 자동 생성하지 않고 `long_gaps_deferred=true`로 남겨 GRU-D/BRITS/SAITS 등 모델 기반 보간 단계에서 처리한다. 승인 전에는 최종 QC 플래그를 변경하지 않는다.
