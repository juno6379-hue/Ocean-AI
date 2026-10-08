# MLOps 검증·평가·배포 계약

점검일: 2026-10-07 KST. 작업 기준 소스: `D:/AI_Observation/source/ocean-ai-platform`.
이 문서는 실제 읽은 문서·코드·읽기 전용 DB 결과와 구현 범위를 구분한다.

## 1. 검토한 근거와 해석

| 읽은 근거 | 적용한 계약 |
|---|---|
| 30_AI_TIME_SERIES_MODEL_PLAN.md | 시간순 분할, 사건·관측소 holdout, TRAIN-only fit, QC/보간/예측 별도 평가, Human Approval |
| 39_MODEL_EVALUATION_REGISTRY_FORECASTING.md | 후보와 운영 구분, 지평별 오차·lineage·latency 기록 |
| 47_LIVE_MDC_PARQUET_TRAINING_VERIFICATION.md 및 47_validation_summary.json | 실제 Ridge 파일럿은 1시간 평균 rolling 예측. 단위·시간대·QC 한계와 운영 DB rollback 명시 |
| 66_EVIDENCE_TEMPORAL_EVALUATION.md | 네 업무별 프로토콜, 승인 멤버 0, 미래 보고서·사건 누수 방지, 미측정 비용 NULL |
| 69_EXPLAINABLE_AI_FOUNDATION_STATUS_AND_ROADMAP.md | 지표명 보유와 평가 완료 구분. 허용 기준은 담당자가 승인하며 임의 합격선 금지 |
| 70_UI_UX_AND_BACKGROUND_EXECUTION.md | 실제 0·조회 실패·미연결 구분. 모델/성능/알림 예시를 운영값으로 표시 금지 |
| evidence_evaluation/benchmark.py, evaluate.py, README.md | 동일 test membership·모델 digest·hardware·protocol hash·측정시간/비용; 승인 원장 export를 전제로 한 offline 채점기 |
| routes_datasets.py, dataset_lineage.py 및 관련 모델 스키마 | 데이터셋 버전은 이름 내 유일; 승인 스냅샷·hash·검토자 기록은 필요조건이며 모델 실행을 증명하지 않음 |

2025 시설 운영평가 보고서의 점수·수집률은 시설 운영에 관한 지표다. AI 모델 정확도,
재현율, 보고서 생성의 인용 정확도 또는 배포 합격선으로 전용하지 않는다. 해당 원문을
이번 MLOps 담당이 전수 검수했다는 주장은 하지 않는다. Label 담당이 읽은 보고서의
`감도 저하 추정` 등의 원인 후보도 검토 전 정답 label로 승격하지 않는다.

## 2. 업무별 평가 계약

| 업무 | 고정할 평가 범위와 누수 차단 | 품질·근거 평가 | 실행시간·비용 | 운영 합격 기준 |
|---|---|---|---|---|
| 예측 | 시간순 TRAIN/VALIDATION/TEST, horizon embargo, 관측소 holdout 별도; 미래 보고서/Feature 제외; scaler TRAIN-only fit | 항목·단위·horizon별 MAE/RMSE, persistence/seasonal 대비 skill; 센서·결측 구간별 성능 | 사례별 latency와 p50/p95, 장비·모델 digest, 실청구액 또는 실측전력 | NOT_DEFINED |
| 이상 탐지/QC | 시간순+사건 그룹 분할, 임계값은 validation에서 고정, 정상 음성 구간 담당 검토 | Precision/Recall/F1/FPR/FNR/AUROC, 사건 recall·탐지지연·일당 오경보; 규칙 버전/원인후보와 정답 구분 | 동일 평가 사례·실행 장비의 p50/p95 및 측정비용 | NOT_DEFINED |
| 검색 | 문서군·개정판·질의 template holdout, corpus hash/qrels/필터/k 고정 | Recall@k/MRR@k/nDCG@k, 답 없음 처리, 관측소·기간 필터 준수 | query별 실측 latency·실청구액/전력, 인덱스·임베딩 digest | NOT_DEFINED |
| 보고서/설명 | 관측소·기간·문서 holdout, 동일 evidence packet, blind human review | 주장 근거율·인용 정확도·필수 사실 포함률·허위 주장 수, 수치/날짜 재검산·불명 보존 | 생성 p50/p95, 수정량·검토시간, 측정비용; LLM 자기평가를 정답으로 사용 금지 | NOT_DEFINED |

현재 실제 PG의 네 protocol payload에는 수치 min/max requirements가 없다.
시험 전에 품질·지연·비용 한계와 적용범위/단위를 승인·고정해야 한다. 95% 등 임의
합격선, 서로 다른 단위 MAE 합산, 미측정 비용 0원, UI 테스트 통과를 모델 정확도로
해석하지 않는다. 평가 코드가 존재하는 것과 후보 실행·선정·운영 승인은 별개다.

## 3. 실제 상태: 읽기 전용 점검

운영 PostgreSQL 연결에서 `SET TRANSACTION READ ONLY` 후 조회하고 rollback했다.

| 대상 | 실제 결과 |
|---|---:|
| public.model_registry | 0 |
| public.dataset_registry | 0 |
| public.approval_history | 0 |
| public.retraining_history | 0 |
| evidence_eval.benchmark_protocol | 4 |
| evidence_eval.v_dataset_readiness | 4개 모두 BLOCKED, eligible_members 각각 0 |

시설·관측·문서 보유와 승인된 학습 데이터셋 보유는 별개다. 현재 운영 모델 선정,
승인 데이터셋 준비, 모델 서빙·재학습 worker 및 runtime rollback은 미완료다.

## 4. 기존 학습 코드와 파일 보유

`app/ml/trainer.py`와 실제 Parquet/MDC 학습 스크립트가 존재한다. 과거 문서에 기록된
Ridge의 시간순 60/20/20 학습·검증·시험 및 저장/재로딩 시험은 실제 실행 이력이다.
다만 과거 학습 script의 Asia/Seoul, TIDE/cm, G/1/GOOD 등 기본 해석을 미확정 새 원천에
그대로 적용해서는 안 된다. 단위·시간대·원천 QC 의미와 최신 승인 계약을 먼저 검증한다.
이 작업에서는 학습 script를 변경하거나 새 학습을 실행하지 않았다.

현재 D: canonical source 아래에는 `backend/validation_runs`가 없다. 기존 산출물은
`C:/AI_Observation/ocean-ai-platform/backend/validation_runs/<run>/candidate/`에 남아 있다.
아래 6개 `model.joblib`의 SHA-256을 실제 bytes로 계산하여 같은 폴더의 `metrics.json`
값과 대조했고 모두 일치했다. 역직렬화/예측 실행은 하지 않았다. metadata에 있는
`artifact_reload_verified=true`는 과거 기록이며 현재 runtime 검증을 뜻하지 않는다.

| run | label_version | 기록된 시험 MAE | 시험 표본 | 현재 파일 hash |
|---|---|---:|---:|---|
| 20260929-mdc-pressure | OBSERVED_VALUE_UNREVIEWED | 0.233463 | 1690 | 일치 |
| 20260929-mdc-tide | OBSERVED_VALUE_UNREVIEWED | 5.211766 | 1762 | 일치 |
| 20260929-mdc-wind | OBSERVED_VALUE_UNREVIEWED | 0.424487 | 1691 | 일치 |
| 20260929-mdc-wind-pressure | OBSERVED_VALUE_UNREVIEWED | 0.425313 | 1691 | 일치 |
| 20260929-parquet-tide | SOURCE_QC_GOOD | 7.165944 | 31072 | 일치 |
| 20260929-water-temp | OBSERVED_VALUE_UNREVIEWED | 0.459728 | 1492 | 일치 |

전부 `RIDGE_HOURLY_FORECAST`, `CANDIDATE`, `approval_required=true`다. 단위/시간대의
해석 한계는 47번 문서를 따른다. 표의 점수를 현재 운영 정확도로 사용하지 않는다.
원본 파일을 이동·삭제하거나 운영 Registry에 자동 등록하지 않았다.

## 5. 구현한 API 계약

서비스: `app.services.mlops_readiness.get_mlops_readiness(db)` 및
`model_readiness(db, model, datasets=None)`. 조회만 수행한다.

- `GET /api/mlops/readiness`: status, counts, operational_model_count, blockers, models.
- `GET /api/mlops/summary`: 기존 registry counts를 보존하고 readiness를 함께 제공.
- model readiness: `ready_for_deployment=false`, `operational_verified=false`,
  checks(dataset/artifact/evaluation/acceptance_criteria/approval/runtime), blockers.
- dataset: 버전이 여러 family에 중복되면 모호성 차단. 최신 승인, 승인자 일치,
  hash-bound 승인 comment, 파일 hash, 모델의 Feature/Label/전처리·항목 대응을 검사.
  `SNAPSHOT_HASH_MATCH`는 그 제한된 검사만 뜻한다. 승인 label·실제 멤버십·사건 분할을
  전체 재검증한 것이 아니므로 `evidence_lineage_verified=false`와 별도 blocker 유지.
- artifact: 파일 존재·비어있지 않음을 확인할 뿐 로드하지 않는다. Registry schema에
  모델 hash/검증 실행 receipt가 없으므로 `PRESENT_UNVERIFIED` 또는 `MISSING`.
- evaluation: task별 지표의 필수값·유한성·범위를 검사. 유효 수치도 독립 평가 실행과
  연결되지 않으면 `DECLARED_UNVERIFIED`. 합격 기준은 `NOT_DEFINED`, 값은 null.
- runtime: 현재 실제 실행기/서빙 probe가 없어 항상 `NOT_CONFIGURED`. DB의 PRODUCTION
  값만으로 운영 모델 수를 올리지 않는다. `operational_model_count=0`.

배포는 reviewer 권한 및 APPROVED 전제 검사 뒤 무변경 409 `DEPLOYMENT_BLOCKED`.
롤백은 현 champion/PRODUCTION 전제 검사 뒤 무변경 409 `ROLLBACK_RUNTIME_NOT_CONFIGURED`.
`mutation_performed=false`로 응답하고 어떤 champion도 archive/복원하지 않는다.
재학습은 기존 501이며 job이 생성되었다고 응답하지 않는다.

실제 배포를 활성화하려면 승인된 데이터셋/분할·모델 hash·평가/requirements를 고정하고,
reviewer 승인 및 runtime load/health/inference probe, 실행 receipt·실패 처리·감시를
연결해야 한다. rollback도 이전 모델 hash/환경/승인, 실제 트래픽 전환 및 검증 receipt가
필요하다. 이 계약은 아직 구현되지 않았으며 API 입력 boolean으로 우회할 수 없다.

## 6. UI와 검증

MLOps 화면은 summary readiness의 실제 건수·차단 사유를 표시한다. DB PRODUCTION은
`운영 기록 · 실행 미검증`으로 표시하며 운영 검증 모델과 구분한다. 고정 알림 12건,
과거 고정 기간, 허위 재학습 시작 표시를 제거했고 학습 버튼은 미연결 상태로 비활성화한다.
0건과 조회 오류를 구분하고 파일/평가/승인 누락을 모델별로 열어볼 수 있다.

- 초기 회귀: 신규 readiness 6개 + 기존 safety 15개 = 21 passed.
- Label 담당 교차리뷰 후 승인자 일치·스냅샷 의미 제한, caller pending-row autoflush 방지 추가: readiness 8개 재검증 PASS.
- frontend TypeScript + Vite build PASS. 기존 큰 bundle 경고는 남음.
- 합성 fixture 시험은 운영 모델 학습/평가가 아니다. 실제 브라우저 픽셀·클릭 및 서버
  재시작 후 HTTP 검증은 coordinator/UI 담당의 후속 단계이며 여기서 완료 주장하지 않는다.

전문가 승인, 실제 모델 선정·배포, 신규 학습, 운영 DB 상태 변경은 수행하지 않았다.
