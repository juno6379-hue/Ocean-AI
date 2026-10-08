# Human-in-the-loop 승인 흐름

작성일: 2026-09-16

## 승인 대상과 환류

`routes_approvals.py`를 실제 FastAPI 라우터로 구현하고 `main.py`에 등록했다.

| 대상 | 승인 시 반영 |
|---|---|
| `QC_CHANGE` | `QCFlagHistory.qc_flag_final`, `reviewer_id`, `review_comment` 반영 |
| `AI_LABEL` | `AILabel.review_status=APPROVED`, 검토자 기록, `RetrainingPool`에 학습 후보 등록 |
| `REPORT` | `ReportRegistry.status=APPROVED`, 승인자 기록 |
| `MODEL_DEPLOY` | `ModelRegistry.status=PRODUCTION` |

거부 시 대상별 `REJECTED` 또는 `ARCHIVED` 상태를 적용하고 승인 이력을 남긴다. QC·AI Label·보고서·모델은 서로 다른 상태 필드를 사용해 QC Flag와 AI Label의 의미를 섞지 않는다.

## API

- `GET /api/approvals/pending`
- `POST /api/approvals/approve`
- `POST /api/approvals/reject`
- `POST /api/approvals/modify`
- `POST /api/approvals/comment`
- `GET /api/approvals/history`

모든 변경·승인·거부·댓글은 `ApprovalHistory`에 `approval_type`, `target_id`, 사용자, 상태, 의견으로 기록한다. `modify`는 대상별 허용 필드만 변경한다.

## Retraining Pool

승인된 AI Label은 `RetrainingPool`에 `PENDING`으로 등록된다. 이 테이블은 학습 데이터 후보와 원본 Label을 연결하며, 실제 Dataset Version 생성·학습 실행은 후속 파이프라인이 pool 상태를 소비한다.

기존 데이터에 임의 승인 기록은 생성하지 않았으며, `retraining_pool` 테이블 생성과 라우터 컴파일을 확인했다.
