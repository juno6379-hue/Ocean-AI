# QC Flag와 AI Label 분리

현행화: 2026-10-08

## 의미와 책임

QC는 관측 품질 규칙·검토 결과다. AI Label은 사건 기간의 품질 정답과 오류 원인을 표현한다. 규칙 결과에서 label 후보를 추천할 수 있지만, 추천은 인간 승인과 원인 확정까지 생성하지 않는다. 원천 QC flag, 모델 anomaly score, 검색 similarity를 그대로 승인 Label로 복사하지 않는다.

[AILabel 모델](../ocean-ai-platform/backend/app/models/domain.py)은 label ID, 관측소·센서·변수, 사건 시작/종료, quality label, error type/cause, source/confidence, review status/reviewer, label version을 저장한다. 사건과 근거는 [EventEvidence·LabelReviewSnapshot](../ocean-ai-platform/backend/app/models/evidence.py)에 연결한다.

## 후보 등록

- `GET/POST /api/qc/ai-labels`: [QC API](../ocean-ai-platform/backend/app/api/routes_qc.py)의 직접 후보 등록이다. 새 label은 `PENDING`만 허용하며 reviewer를 직접 지정할 수 없다. 이 경로에 등록했다는 사실만으로 사건 근거가 완성되지는 않는다.
- [event_evidence](../ocean-ai-platform/backend/app/services/event_evidence.py)의 `create_label_candidate()`는 닫힌 사건 구간과 DOCUMENT·OBSERVATION·QC_RESULT·OPERATION_LOG 근거를 요구한다. 규칙에서 품질 후보를 정하지만 `error_cause='unknown'`, `PENDING`으로 남긴다.
- [label_review_agent](../ocean-ai-platform/backend/app/services/label_review_agent.py)는 관측·채널·dataset·문서의 검토 후보를 제안한다. agent 출력은 실제 reviewer 결정이 아니다.

운영 검토에서 사용하는 품질 값은 `NORMAL`, `SUSPECT`, `BAD`, `MISSING`이다. 원인 후보는 다음과 같다.

```text
facility_damage, equipment_fault, sensor_degradation, biofouling,
power_fault, communication_fault, qc_algorithm_error,
cross_variable_inconsistency, statistical_outlier, db_error,
service_publication_error, natural_event, unknown
```

`error_cause`는 DB CHECK와 API에서 제한한다. 승인 시 `validate_label()`은 품질·원인, 유한한 0~1 confidence, 사건 종료가 시작보다 뒤인지 검사한다. confidence는 실제 측정 근거 없이는 임의 부여하지 않는다.

## 실제 승인과 불변 근거

[승인 API](../ocean-ai-platform/backend/app/api/routes_approvals.py)의 `AI_LABEL` 대상에서 reviewer/admin의 인증 actor로 결정한다. 변경은 먼저 modify 경로에서 검토하고 approve 요청에 변경사항을 함께 넣어 우회할 수 없다.

승인은 `ApprovalHistory`와 라벨·사건·문서·관측·QC·운영 근거를 고정한 `LabelReviewSnapshot.payload_hash`를 함께 기록한다. `approved_label_proof()`는 현재 Label 상태/검토자, 실제 원장 및 저장 snapshot과 현재 근거 hash가 맞는지 확인한다. 근거가 바뀌거나 SIMULATED/DEMO 원천으로 변경되면 승인 증거로 재사용하지 않는다.

승인된 label은 `RetrainingPool`의 **PENDING 후보**로 들어갈 수 있다. 이는 Dataset 승인, 학습 실행, 모델 배포의 자동 실행을 의미하지 않는다. [Dataset](18_DATASET_REGISTRY.md)은 관측마다 정확히 하나의 승인 label proof와 동일 scope·기간의 사건 연결, 원천/QC/feature 근거를 별도로 확인한다.

## 사건 기간·공통 식별자의 경계

문서명·관측소 이름·item 단어·월이 맞는 후보 연결을 정확한 물리 센서 사건 동일성으로 승격하지 않는다. [원천 계약](11_OBSERVATION_STANDARD_LAYER.md)의 exact grain/physical episode/timezone과 사건 구간의 근거가 함께 필요하다. 문서 검색이나 dictionary 대조가 성공해도 label은 승인되지 않는다.

2026-10-07 검토 파일의 미연결 사건 후보 40개와 기간 충돌 1건/152 grain은 해결 승인 미확보 상태였다. 이 수치를 DB 사건 40건으로 해석하지 않는다. 부모의 2026-10-08 읽기 전용 확인에서 `event_registry`, `event_evidence`, `approval_history`는 모두 0이었다.

## 검증·남은 작업

[event evidence 시험](../ocean-ai-platform/backend/tests/test_event_evidence.py), [label agent 시험](../ocean-ai-platform/backend/tests/test_label_review_agent.py), [안전 workflow 시험](../ocean-ai-platform/backend/tests/test_safety_workflow.py)은 후보·승인·내용 변경·모의 원천 차단 경계를 검증한다. 실제 담당자가 원천·사건·품질·원인 근거를 확인하고 인증된 승인 기록을 남기는 단계는 별도로 필요하다. 승인 책임은 [Human-in-the-loop](17_HUMAN_IN_THE_LOOP.md)를 따른다.
