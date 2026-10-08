# AI 시계열 분석 모델 계획 및 단계별 구체화

> 2026-10-07 범위 갱신: 사용자는 품질관리 가이드북의 전체 관측항목(수온·염분·HF-radar 포함)을 품질검사·이상 탐지·예측 대상으로 대응시키도록 지시했다. LSTM Autoencoder보다 나은 후보도 비교한다. 아래 모델명은 계획이며 구현·선정·배포 완료가 아니다. 최신 업무·자료형·메뉴 역할 계약은 `79_MODEL_AND_BUSINESS_UI_SCOPE.md`, 실제 학습 파일과 운영 준비도는 `76_MLOPS_AGENT_CONTRACT.md`를 따른다.

## 1. 최종 목표

2001~2021 장기 관측자료를 원본·Parquet Data Lake·PostgreSQL 요약 계층으로 분리하고, 다음 기능을 승인 가능한 분석 결과로 제공한다.

- 결측 구간의 복원 후보와 신뢰도
- 규칙 QC와 AI 이상탐지의 결합 근거
- 장기 해수면 상승·기후 변화 추세와 변화점
- 수일 뒤 조위 예측 및 운영 경보

AI가 원본값이나 최종 QC 플래그를 자동으로 덮어쓰지 않는다. 모든 예측은 모델 버전·Dataset 버전·Feature 버전·입력 기간·근거를 남기고 Human Approval을 거친다.

## 2. 모델 선택 원칙

항목별로 단일 모델을 고정하지 않고 기준 모델과 후보 모델을 함께 평가한다. 결측률, 관측주기, 계절성, 관측소 수, 데이터 누수 여부를 먼저 확인하고 성능과 지연시간을 비교해 Champion을 선정한다.

### 2.1 결측치 보간

| 단계 | 모델 | 적용 조건 | 출력 |
|---|---|---|---|
| 기준선 | 선형·시간 보간, 이동 중앙값 | 짧은 결측(예: 1~3주기), 정상 구간 | 보간값, 방법, 구간 길이 |
| 통계 | Kalman Smoother, SARIMA | 단일 관측소의 추세·주기성이 안정적일 때 | 보간값, 예측구간 |
| 딥러닝 후보 | GRU-D 또는 BRITS | 결측 마스크와 시간 간격을 함께 학습할 때 | 보간값, 신뢰도 |
| 다변량 후보 | SAITS 또는 시간 Transformer | 조위·기압·풍속 등 동시 관측과 긴 결측 | 보간값, 변수별 기여도 |

짧은 결측은 기준선보다 복잡한 모델을 사용하지 않는다. 긴 결측은 관측소·변수별로 검증하고, 실제 결측을 인위적으로 가린 마스킹 평가로 MAE/RMSE를 산출한다.

### 2.2 QC 자동화 및 이상탐지

| 모델 | 용도 | 주의점 |
|---|---|---|
| 물리 범위·급변·지속성 Rule | 설명 가능한 1차 QC | `QCRuleResult`로 규칙별 결과 저장 |
| Isolation Forest | 라벨이 적은 초기 이상탐지 | 이상 점수를 확정 플래그로 사용하지 않음 |
| Robust Z-score/季節 기준 | 항목별 계절성 이상 | 평균 대신 중앙값·MAD 사용 |
| LSTM/TCN Autoencoder | 정상 패턴 재구성 오차 탐지 | 정상 학습셋 오염 여부 점검 |
| TFT 또는 Transformer | 다변량·시간 지연 이상탐지 | 데이터가 충분할 때만 후보로 승격 |

규칙 결과, AI 점수, 원인 후보를 결합해 `QCCopilot` 분석 결과를 만들고, 최종 QC 변경은 승인 API에서만 수행한다. 평가는 Precision, Recall, F1, AUROC, False Positive Rate, False Negative Rate와 처리 latency를 사용한다.

### 2.3 장기 해수면·기후 분석

예측 모델과 분리된 분석 파이프라인으로 운영한다.

1. 월·연도별 중앙값과 분위수 집계
2. 조석 성분·계절성 제거
3. Theil–Sen robust slope와 Mann–Kendall 추세 검정
4. STL decomposition으로 추세·계절·잔차 분리
5. PELT 또는 Bayesian Change Point로 변화점 후보 탐지
6. 관측소별 상승률·신뢰구간·자료충족률 산출

결과는 `AI Insights`에서 분석·추천으로 표시하며 자동 경보나 최종 판정으로 표현하지 않는다. 관측소 이전·센서 교체·기준면 변경은 OperationLog와 함께 보정하거나 분석 구간을 분리한다.

### 2.4 조위 Forecasting

| 순서 | 모델 | 역할 |
|---|---|---|
| 1 | Persistence/조화분석(Harmonic) | 운영 기준선과 설명 가능한 예측 |
| 2 | SARIMAX/Prophet | 단일 관측소 계절·추세 비교 |
| 3 | LightGBM/XGBoost lag model | 지연값·기상·조석 Feature 기반 강한 기준 모델 |
| 4 | TCN 또는 LSTM/GRU | 장기 시계열의 비선형 패턴 |
| 5 | TFT/Transformer | 다변량·다중 관측소·수일 다중 스텝 예측 후보 |

처음에는 조화분석과 LightGBM을 기준으로 시작하고, 데이터량과 latency가 허용될 때 TCN/LSTM, TFT 순서로 확장한다. 예측 수평은 1시간·6시간·24시간·72시간으로 분리하고 horizon별 MAE/RMSE/MAE와 운영 latency를 기록한다.

## 3. 데이터·Feature 설계

- 원본: 변경 불가 보존, checksum 기록
- Data Lake: Parquet `year/month/station_id/variable_code` 파티션
- 운영 DB: 최근 관측, 집계 통계, QC 결과, 승인 Label, Registry
- 시간 Feature: lag, rolling mean/std, rate of change, persistence duration
- 조위 Feature: 조화 성분, 예측 잔차, 조석 주기
- 교차변수 Feature: 기압·풍속·수온·염분·전기전도도 관계
- 운영 Feature: 수신 지연, 점검·교체·보정 이력, 최근 장애

보간값은 `value_imputed` 계층으로 분리하고 학습 시 원본/보간 여부를 mask로 전달한다. 미래값을 사용한 rolling·정규화는 금지한다.

## 4. 데이터셋 분리와 누수 방지

- 시간 순서: TRAIN → VALIDATION → TEST → BLIND_TEST
- 관측소 일반화 평가: 일부 관측소를 통째로 hold-out
- RETRAINING_POOL: Human Approval을 받은 Label만 포함
- 동일 이벤트·동일 시간창이 분할 경계를 넘지 않도록 그룹 분할
- 전처리·스케일러·Feature 계산은 TRAIN 구간으로만 fit

모든 Dataset은 기간, 관측소·센서·변수 범위, 결측/정상/의심/불량 수, feature/label/preprocessing 버전과 data hash를 `DatasetRegistry`에 기록한다.

## 5. 단계별 실행 순서와 완료 기준

### 단계 A — 포맷·품질 프로파일

파일별 인코딩·구분자·시간대·샘플주기·관측항목·결측코드·QC/MQC 분포를 조사한다. 완료 기준은 전체 파일 inventory와 파싱 성공/실패 manifest다.

### 단계 B — Parquet 변환

청크 변환, 파티션 저장, checksum, 변수별 통계를 생성한다. 완료 기준은 샘플 파일 재현 변환과 행 수·최소/최대·결측률 검증이다.

### 단계 C — PostgreSQL 요약 적재

관측소·변수·월별 집계와 QC 통계만 적재한다. 원천 전체 적재를 금지하고 적재 건수·hash를 검증한다.

### 단계 D — 결측 보간·QC Copilot

기준선 → 통계 → 딥러닝 순으로 비교하고, `QCRuleResult`·AI 점수·문서 근거·승인 요청을 반환한다. 완료 기준은 인위적 masking 평가와 승인 이력이다.

### 단계 E — 장기 Insights

추세·변화점·관측소 비교를 생성하고 불확실성·자료충족률을 함께 표시한다. 완료 기준은 기준면·센서 변경 이력 반영과 결과 재현성이다.

### 단계 F — Forecasting MLOps

기준 모델부터 후보 모델을 학습해 Registry에 등록하고 Champion/Challenger를 비교한다. 완료 기준은 horizon별 평가 지표, latency, dataset/feature lineage, rollback 정보다.

### 단계 G — UI·운영 연결

Data Lake 메뉴에는 변환·통계·모델 상태를, QCCopilot에는 보간 후보·근거·승인을, AIInsights에는 장기 추세를, MLOps에는 예측 모델과 평가를 표시한다. 모든 데모 응답은 `is_demo=true`로 구분한다.

## 6. 1차 구현 범위

초기 계획의 `TIDE`·`WAVE` 한정은 최신 전체 항목 요구를 대체하지 않는다. 가이드 원문에서 대상 목록을 확정하고 항목별 규칙 QC·이상 탐지·예측 적용표와 미연결 사유를 먼저 만든다. 확인된 학습 산출물은 Ridge 후보이며, 이 문서의 다른 후보가 구현·운영되었다는 뜻은 아니다. 같은 평가자료로 단순 기준선과 심층학습 후보를 비교하고, HF-radar의 공간·벡터 자료를 단일 조위 시계열과 구분한다. 제한 범위 파일럿과 전체 대상 검토 진행률은 별도로 보고한다.
