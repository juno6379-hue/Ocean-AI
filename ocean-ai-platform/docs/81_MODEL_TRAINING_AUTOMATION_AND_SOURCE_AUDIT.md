> 이 문서는 구현 완료 전 점검을 포함하는 과거 기록입니다. worker/typed bridge의 최종 구현 및 현재 범위는 [82번 릴리스 문서](82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)를 확인하세요.

# 모델 소스 감사·관측항목 확장·재학습 자동화 계약

점검일: 2026-10-07. 상태: **DESIGN_ONLY / UPLOAD_IN_PROGRESS_PARTIAL_AUDIT / NO_FINAL_SELECTION**.
새 학습·모델 실행·운영 승인·배포는 수행하지 않았다. 현재 `/api/mlops/retrain`은 501이며
학습 job을 생성하지 않는다. 다음 실행 작업은 승인된 계약에 따른 training worker 구현이다.

## 확인한 범위와 원문

읽은 범위는 기존 모델 계획·데이터셋/평가 계약, 2025 결과보고 제3장 관련 본문과
PDF p58/59/60/66/67 렌더, QC 담당이 작성한 전체 항목 매트릭스, canonical `backend/app/ml`
및 관련 실행 스크립트, 업로드 중 안정 파일이다. 모든 문서/업로드 전체를 숙지했다고 주장하지 않는다.

2025 결과보고 제3장 p58–60은 기존 2024 조위 LSTM Autoencoder에서 과거 4분 OBS+PRD로
현재 조위를 예측하는 2025 LSTM 방식으로 변경했다고 설명한다. 안정 업로드의 세 해역
`AI_QC_*_sea_no_update.py`가 이 입력/추론 구조에 부합한다. 과거 조위 모델 파일명 미발견
결론은 **업로드 이전 검색 범위에 한정**하며 새 발견으로 보완한다.

- 업로드 원본: `D:/share/AI_anomaly_detection`.
- 실제 자산 예: `model_output_forecast/DT_0001/TIDE_LEVEL_LASER_1/residual_lstm_forecast.h5`.
- 스냅샷 3/4에서 경로·크기·mtime가 일치하고 읽기 전후 stat도 일치한 자산을 해시했다.
- 안정 `residual_lstm_forecast.h5` 94개/관측소 디렉터리 55개, scaler 94개, DEV 94개.
  `best_model.h5` 80개를 포함한 H5 174개를 174개 운영모델로 해석하지 않는다.
- H5 signature 및 raw bytes의 완결 JSON만 제한적으로 판독한 보조적 메타데이터는
  Input `(None,4,2)` → LSTM64 → Dense1, tanh 80개/relu 14개다.
  **정식 HDF5 attribute/tensor 검증 또는 TensorFlow load 결과가 아니다.**
- 코드 import/실행, 패키지 설치, H5 실행, scaler/state pickle·joblib 역직렬화는 하지 않았다.
- 안정 업로드 범위에서 학습 스크립트/노트북·학습 membership·scaler fit 기간·분할·epoch·
  optimizer·seed·환경 lock을 아직 확인하지 못했다. 업로드 완료나 학습 재현을 선언하지 않는다.

상세 근거와 hash:

- [업로드 소스 감사](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/uploaded-source-findings.txt)
- [자산 메타데이터·SHA256](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/uploaded-asset-audit.json)
- [소스 AST 감사](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/upload-source-audit.json)
- [초기 파일 검색 범위·오류 기록](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/file-audit.json)

## 성능 근거와 우선 해결할 불일치

### 기존 LSTM의 학습 데이터셋 확보 여부

**가중치를 만든 정확한 2020–2022 정상 학습 데이터셋은 아직 미확인**이다.
안정 snapshot3/4에 CSV14,280개가 있지만 파일 존재와 학습 membership 증명은 다르다.
큰 파일 전체 순회 없이 세 그룹에서 각5개, 총15개 CSV의 처음/끝 최대8KiB를 읽었다.

| 자료 | 안정 파일수 | 확인한 내용 | 현재 분류 |
|---|---:|---|---|
| local_selene_data/qc_results | 13,228 | OBS_TIME, OBS, MQC_FLAG, PRD, NEAR_FLAG; 샘플2025-11~2026-03 | QC 처리 결과 |
| model_output_forecast/**/forecast_result.csv | 94 | timestamp, y_val, y_pred; 일부2020~2022 | 검증/예측 결과 형식, 정확 split 미검증 |
| debug_logs | 946 | real_obs, predicted_obs, tide_pre_val, threshold, flags 등 | 추론 로그 |

`DT_0001/TIDE_LEVEL_LASER_1/forecast_result.csv`의 양끝 행은2022-06-13 05:35~
2022-12-31 23:59, `TIDE_LEVEL_OTT`는2020-12-22 11:03~2021-03-24 10:03이다.
이는 전체 파일의 min/max를 계산한 결과가 아니며 연도가 겹쳐도 학습 원본으로 확정하지 않는다.
입력 OBS/PRD window·정상선별 membership·scaler fit 기간·분할/학습 코드가 필요하다.
안정 snapshot의 train/split/membership/manifest 명명 파일 및 Parquet는0개였으나,
이름검색은 모든 가능한 학습자료의 부재를 증명하지 않고 업로드도 아직 진행 중이다.
일부 debug 파일명 날짜와 내부 관측시각이 달라 파일명으로 원천기간을 확정하지 않는다.

[데이터셋 가용성의 bounded 감사](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/dataset-availability-audit.json)에
샘플 경로·헤더·양끝시각·부분 hash를 보존했다. 부분 hash를 전체 파일 SHA로 표시하지 않았다.

### 문서 평가값과 코드 불일치

보고서 p67 표3-37의 AI QC 결과는 Accuracy 98.97%, Precision 39.44%, Recall 92.21%,
F1 55.25%이다. 그림의 TN 2,625,410 / FP 25,939 / FN 1,426 / TP 16,890과 함께 보아야 한다.
높은 전체 accuracy만으로 운영 적합성을 판단할 수 없으며 오경보와 사건별 지연·검토 부담을
후보 비교에 포함한다. p66의 92.2%는 BAD 중 탐지 비율이다. p67 본문 F1 5.53%와 표55.25%
불일치는 원문 그대로 기록한다. 2025 시설 운영평가점수와 AI 정확도는 별개다.

이 수치는 보고서의 평가 결과이며 현재 업로드 코드로 재현한 값이 아니다. 동일 날짜/센서/
정답판본/임계값 조건을 검증하기 전 새 코드의 검증 성능으로 등록하지 않는다.
보고서 p64 최종안전값 동해123/서해208/남해154cm와 소스 세 해역100cm가 다르다.
DEV 누락 시10cm fallback, NaN→0, 잘못된 입력길이→zero tensor, MQC 누락→G,
현재 DB QC를 사용하는 과거 replay의 as-of 가용시각은 별도 검증 대상이다.
`no_update`라는 이름이어도 NEAR_TIME v2/v3에 DB UPDATE 실제 호출이 있으므로 실행하지 않았다.

## 전체 관측항목의 후보 설계

QC 매트릭스의 15개 기본항목 × 3개 과업, HF R/T × 3개 과업, 기타 7개 관측자료형 ×
3개 과업에 대응하는 **72개 (domain,item,task)** 키가 정확히 일치하는지 검증했다.
검증 PASS는 매트릭스의 범위 정합성만 뜻하며 모델 성능/학습/승인을 뜻하지 않는다.
모든 행은 DESIGN_ONLY_NO_WINNER이고 미정 선정 기준은 NOT_DEFINED다.

조위 cm·천문예측·4분 window·센서별 scaler에 묶인 가중치를 수온·염분에 직접 적용하지 않는다.
항목별 단변량, 가용시각이 검증된 동시 다변량, HF signed radial/합성 vector·격자·APM,
CTD cast/profile, ADCP depth/bin/beam, 이동궤적을 각각 입력 계약으로 구분한다.
HF 접근(+)·후퇴(-) 방사속도에 일반 유속의 비음수 범위를 적용하지 않으며 수집률<50%는
QC 검사제외로 남긴다. 원천단위·주기·품질플래그·센서교체·보고서 시간누수를 먼저 고정한다.

후보는 소수로 시작하며 같은 항목/단위/holdout/센서전환/자료부족 조건으로 비교한다.
이상탐지는 기존 AE/forecast-LSTM과 TCN/TranAD, 예측은 persistence/계절기준선·Ridge와
LightGBM/PatchTST를 비교 대상으로 설계했다. 복잡한 모델이 우수하다고 미리 결론내리지 않는다.
PatchTST 기본 channel-independent 구조를 HF 공간 상호작용 모델로 간주하지 않는다.
TranAD 참고 구현의 정답을 이용한 point adjustment/backfill을 실시간 예측 성능에 섞지 않는다.

- [72행 후보 매트릭스](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/model-candidate-matrix.json)
- [키 정합성 검증](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/matrix-verification.json)
- [문서·후보 종합 분석](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/model-assessment.txt)
- [QC 자료형·과업 원본 매트릭스](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/qc-scope/model-task-matrix.json)

후보의 1차 근거: [TCN 공식 구현](https://github.com/locuslab/TCN),
[TranAD 공식 구현](https://github.com/imperial-qore/TranAD),
[LightGBM 공식 구현](https://github.com/lightgbm-org/LightGBM),
[PatchTST 공식 구현](https://github.com/yuqinie98/PatchTST).
이들을 설치/학습/선정한 상태는 아니다.

## 재학습·평가 자동화의 담당과 다음 구현

모델·MLOps가 job/학습/평가/기존모델 비교를 주관한다. 데이터 통합은 표준 Parquet와 정산,
QC/Label은 학습근거·정답·승인 데이터셋, 독립검증은 누수/동일조건/재현/운영 receipt,
UI는 비교 결과와 이력을 담당한다.

현재 존재하는 연결점은 `ml/trainer.py::train_from_hourly`의 Ridge,
`ml/evaluator.py::regression_metrics`의 MAE/RMSE/bias,
`ml/model_registry.py::save_candidate`의 후보 파일 저장이다. trainer의 시간순60/20/20은
매번 데이터 길이에 따라 변경되어 고정 holdout 비교가 아니다. `champion-challenger` API는
저장된 metrics 두 개를 반환할 뿐 paired 재평가를 하지 않는다. main.py APScheduler는 MDC
동기화이며 학습 worker가 아니다. `train_parquet_history.py`의 TIDE·cm·G/1/GOOD·KST
가정과 `train_mdc_multivariate.py`의 QC 미검증 snapshot은 전체 항목 자동학습 입력 계약을
대체하지 못한다.

다음 구현은 아래 순서로 진행하며 자동 학습을 이번 감사의 부수효과로 시작하지 않는다.

1. 원천/단위/QC/as-of·센서구간 계약과 승인 dataset/split_manifest를 runner 입력으로 고정.
2. schedule/신규 승인자료/검증 drift/manual trigger와 durable job, 중복 lock·멱등jobid·lease.
3. train에서만 전처리 fit, validation tuning, 명시된 최종 재fit과 challenger artifact 생성.
4. 고정 holdout의 동일 origin에서 기존모델/후보/기준선 비교; 지평별 MAE/RMSE,
   anomaly precision/recall/F1/FPR·오경보/일·탐지지연, 비용·학습시간·서비스 latency/자원 기록.
5. 독립검증 및 승인 gate, 실제 serving identity/health receipt, 이전 artifact 복구 receipt.
6. 실패 분류·한정 재시도·quarantine, crash recovery와 기존 champion 보존 검증.

주기·최소 신규자료·drift 임계값·최소개선·최대회귀·비용/지연 예산·재시도 정책은
**NOT_DEFINED**로 남긴다. 모델이 없으면 NO_CHAMPION으로 기준선과 비교한다.
현재 deploy/rollback은 runtime 미구성으로 DB를 바꾸지 않는 409 계약을 유지한다.

구체적 함수별 재사용/누락 목록·상태전이·평가지표·테스트 명세는
[재학습 실행 계약](<local-evidence-root>/2026-09-29/new-chat/outputs/model-scope-20261007/mlops/retraining-execution-contract.txt)에 있다.
업로드 후속 확인과 training worker 구현은 다음 작업이며, 이번 bounded 감사의 완료가
업로드 전체 완료·학습 재현·성능 승인·운영 배포 완료를 뜻하지 않는다.

## 2026-10-07 엄격한 수동 비교 어댑터 구현과 독립 검증

`app/ml/comparison_runner.py`와 `app/scripts/run_model_comparison.py`에
단변량 FORECAST Ridge/persistence 비교 어댑터를 구현했다. source 의미/단위/QC/시간대,
실물 센서 유효기간, 원천 파일 SHA, 코드표, as-of, 고정 train/validation/test 명세를
명시적으로 요구한다. train만 scaler fit, validation tuning, 동일 잠긴 test pair의
MAE/RMSE를 사용한다. durable SQLite job/멱등성/lease/quarantine 경계가 있으며
crash recovery는 수동이다. 외부 H5/pickle을 읽거나 자동 학습을 시작하지 않았다.

모델 담당 19개 시험과 다른 담당의 입력 거부 교차 검토를 통과했다.
주 에이전트의 별도 NumPy closed-form 해법은 합성 데이터의 전처리/계수/예측/지표를 대조했다.
test 정답 변경이 tuning/scaler/계수에 영향을 주지 않는 것과 재실행 멱등성을 확인했다.
합성 증명만이며 실제 원천 학습·운영 모델 선정·model_registry 적재는 모두 0이다.
현재 live DB authority 검사 결과 `APPROVED_DATASET_NOT_FOUND`로 job 생성 전에 차단된다.

아직 구현되지 않은 production 연결은 승인 source 계약의 파일/판본/기간 의존성을
DatasetRegistry snapshot에 동결하는 bridge, 실제 승인 dataset/고정 split,
다른 업무 어댑터, training worker/scheduler, 운영 수용 기준,
기존 운영 모델과의 재평가/선정/등록/serving/배포 실행기다.
legacy `event-evidence-dataset-1`은 source 계약 의존성을 동결하지 않는다.
따라서 이 수동 어댑터 구현을 72개 업무 전체 운영 모델 완료로 해석하지 않는다.

검증 게시본의 `model-comparison/input-contract-and-remaining-work.txt`에
함수별 연결점과 잔여 필드가 있다. 부모 수치 검증은 `parent/model-verification.json`,
live authority 차단은 `parent/live-database-authority-preflight.json`이다.

## 모델 인계 파일 별도 보존 완료 (2026-10-07 16:02 KST)

`D:\share\AI_anomaly_detection`의 16,239개 파일/3,171,520,129 bytes를
`D:\AI_Observation\source\model_handoff\AI_anomaly_detection`에 보존했다.
복사 시 해시 검사 후 주 에이전트가 원본/보존본 전 파일을 별도로 SHA-256 재검사했고
전후 경로/크기/mtime inventory가 일치했다. 이전 감사 373개 asset SHA도 모두 일치한다.
H5 구성은 residual LSTM 94개와 best_model 80개, 합계 174개다.
단순 폴더별 수를 모델 종류별 수로 오인한 부모 검증기 조건을 수정하고 최종 재검사를 통과했다.

모델 역직렬화/학습/실행/운영 승인/registry 적재나 원본 삭제는 하지 않았다.
동일 D 드라이브 안의 독립 경로 보존이므로 별도 물리 디스크 백업은 아니다.
증거는 최종 통합 폴더 `preservation/parent-verification.json`, `manifest.jsonl`, `status.json`과
`evidence/verify_model_handoff_preservation.py`에 있다.
