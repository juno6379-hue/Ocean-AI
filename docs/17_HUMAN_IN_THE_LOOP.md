# Human-in-the-loop 승인 흐름

현행화: 2026-10-08 · 구현 기준: [승인 원천·모델 실행 릴리스](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)

## 승인자와 승인 근거

[security.py](../ocean-ai-platform/backend/app/core/security.py)는 서버의 `API_IDENTITIES`에 등록된 Bearer token으로 `Actor(user_id, role)`를 확인한다. 쓰기는 기본적으로 `operator`, `reviewer`, `admin` 역할이 필요하고, 승인·거부·검토 변경에는 `reviewer` 또는 `admin`이 필요하다. 요청 본문의 `user_id`로 검토자를 지정할 수 없다. 일반 승인 API는 이 값을 인증된 actor로 바꾼다. 인증 미설정은 503, token 누락·오류는 401, 역할 부족은 403이다.

원천 검토, Label 승인, Dataset 승인, 모델 독립 검토, 배포 승인은 각각 다른 대상을 검증한다. 기술 검사 통과나 파일에 적힌 `APPROVED`만으로 실제 담당자 승인을 대신하지 않는다. 원천 reviewer와 Dataset reviewer가 같아야 한다는 규칙도 없다. 각 단계는 자기 승인 이력과 해당 내용의 hash를 확인한다.

## 일반 승인 API의 대상과 환류

[routes_approvals.py](../ocean-ai-platform/backend/app/api/routes_approvals.py)는 대상 행을 잠그고 미검토 상태를 확인한다. 승인·거부·수정·의견은 `ApprovalHistory`에 남는다.

| 대상 | 승인 시 반영 | 승인만으로 수행하지 않는 일 |
|---|---|---|
| `QC_CHANGE` | 허용된 최종 QC flag와 reviewer·의견 기록 | 원천 QC 문자 재작성, AI Label 생성, 원천 의미 승인 |
| `AI_LABEL` | `review_status=APPROVED`, 검토자, `LabelReviewSnapshot`의 내용 hash 기록 | Dataset 자동 승인, 학습 시작 |
| `REPORT` | 보고서 승인·검토자 기록 | 외부 게시·발송 |
| `MODEL_DEPLOY` 호환 경로 | Registry 행을 `APPROVED`로 변경 | 실제 serving, Champion 승격, hash에 결합된 배포 승인 대체 |

거부는 대상의 `REJECTED` 또는 QC 검토 이력으로 남긴다. 이미 검토한 대상에 중복 승인·거부를 적용하지 않는다. `modify`는 QC의 2차 flag·의견, Label의 허용된 분류 필드, 보고서 제목·요약, 모델 지표 등 정해진 필드만 허용한다. 최종 QC·모델 상태를 수정 요청으로 임의 승격할 수 없다.

```text
GET  /api/approvals/pending
POST /api/approvals/approve
POST /api/approvals/reject
POST /api/approvals/modify
POST /api/approvals/comment
GET  /api/approvals/history
```

`pending`은 위 네 종류의 일반 업무 대기 목록이다. 원천 계약·Dataset·모델 프로토콜의 전체 승인 목록은 각 전용 API에서 조회한다.

## 원천·Dataset·모델의 전용 승인

| 단계 | API | 실제 승인에 결합되는 내용 |
|---|---|---|
| 원천 계약 | `POST /api/source-contracts/request`, `POST /api/source-contracts/{contract_id}/decision`, `GET /api/source-contracts/{contract_id}/receipt` | 불변 packet·decision과 실제 `SOURCE_CONTRACT` 이력, canonical receipt SHA |
| Dataset | `POST /api/datasets/{dataset_id}/approve` | v2 snapshot 전체 SHA, 참여 관측·Label·사건·Feature 및 동결된 의존성 |
| 분할·평가·수용 정책 | `POST /api/mlops/protocols/draft`, `POST /api/mlops/protocols/{sha256}/decision` | `MODEL_PROTOCOL` 이력과 정확한 JSON body SHA |
| 독립 모델 검토 | `POST /api/mlops/candidates/review` | 실제 worker의 committed 비교 영수증, 재현된 artifact·동일 test pair, `MODEL_INDEPENDENT_REVIEW` 이력 |
| 배포·rollback 판정 | `POST /api/mlops/models/{model_version}/decision` (`rollback=true`는 rollback) | report·artifact·실행 범위가 결합된 배포 identity SHA와 `MODEL_DEPLOY`/`MODEL_ROLLBACK` 이력 |

원천 영수증 검증은 원문·Parquet bytes, 행·열 locator, 단위·시간대·QC·센서 유효기간과 실제 최신 승인 이력을 다시 확인한다. 이후 거부·철회, 파일 변경, 코드 fingerprint 변경은 학습 또는 serving을 차단한다. 상세 절차는 [Dataset Registry](18_DATASET_REGISTRY.md)와 [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md)에 있다.

## Retraining Pool과 현재 상태

승인된 AI Label은 `RetrainingPool`의 `PENDING` 후보와 연결된다. 이 후보는 학습 입력 자체가 아니다. 승인 원천 binding, 사건·QC·Feature 근거, 고정 Dataset 참여 목록과 정책 승인을 갖춘 뒤 비교 작업을 요청해야 한다.

2026-10-08 13:09 KST 읽기 전용 운영 확인에서 `API_IDENTITIES`는 0이고 원천 packet·decision·binding, `ApprovalHistory`, Dataset·Model Registry는 모두 0이다. 따라서 실제 담당자 승인이나 운영 모델 선정이 완료된 상태가 아니다. 공개 복사본의 전체 시험 345개 통과·1개 skip은 격리된 구현 검증이다. 운영 진척은 [P0 상태](24_P0_END_TO_END_PROGRESS.md)에서 구분한다.
