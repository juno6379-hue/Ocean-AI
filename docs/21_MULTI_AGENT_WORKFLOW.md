# Multi-Agent Workflow와 Evidence Fusion

현행화: 2026-10-08 · 상세 계약: [Evidence Fusion·승인 중단/재개](../ocean-ai-platform/docs/84_EVIDENCE_FUSION_WORKFLOW.md)

## 분석 범위와 추천

[workflow](../ocean-ai-platform/backend/app/agents/multi_agent_workflow.py)는 관측소·센서·항목·단위와 명시적 UTC offset을 가진 관측 기간·`as_of`를 입력받는다. 조회는 이 정확한 범위의 표준 관측과 Rule, Label, 센서 metadata, 운영 로그로 제한한다. 주요 DB 조회는 각각 최대 500개이며 501번째 행으로 잘림 여부를 표시한다. `BOUNDED_DB_ANALYSIS_NOT_CENSUS`는 전수 검토 완료가 아니다.

[Evidence Fusion](../ocean-ai-platform/backend/app/services/evidence_fusion.py)은 다섯 근거를 하나의 `recommendation_score`로 합친다. 점수는 가중 이상 지지도이고 확률이나 최종 QC가 아니다. Rule 0.30, AI 0.25, Metadata·Operation·RAG 각각 0.15의 고정 가중치를 사용하며, 각 종류 안에서는 가장 높은 유효 지지도를 사용한다. 근거가 없는 종류를 빼고 가중치를 다시 정규화하지 않는다. 평가 가능한 정상·이상 근거가 전혀 없으면 점수는 `null`이다.

| 근거 | 현재 연결 | 유효성 경계 |
|---|---|---|
| Rule | 저장된 `QCRuleResult` 및 [12종 guide Rule](../ocean-ai-platform/backend/app/services/qc_rule_engine.py) 분석 결과 | 평가 상태·원천 의미·물리 센서/구간·정확한 단위·명시적 event/실행 가용시각이 필요하다. Rule report 전체 SHA를 확인하고 기존 naive 시각만 가진 결과는 미평가로 보존한다. |
| AI | [시계열 분석](../ocean-ai-platform/backend/app/services/anomaly_analysis.py)의 frozen artifact 결과와 기존 Label | AI report 전체 SHA를 다시 확인한다. 경험적 calibration 지지도는 확률이 아니다. 단위·가용시각이 없는 기존 Label은 점수에 넣지 않는다. |
| Metadata | 정확한 센서 metadata, 명시적 개발 검토 입력 | 현재 장비 정보만으로 역사적 단위·유효기간·가용시각을 확정하지 않는다. |
| Operation | 센서별 운영 로그의 명시적 scope·event/available 시각 | 구조화되지 않은 사건 문구나 naive 시각으로 실제 사건 시간을 추정하지 않는다. |
| RAG | 관측소·센서·항목·기간 조건의 hybrid retrieval | 문서 발행일·색인일·cosine relevance를 가용시각이나 이상 확률로 사용하지 않는다. 검색 오류와 성공한 빈 검색을 구분한다. |

근거의 source 종류, 전체 SHA와 typed locator를 보존하며 같은 원문 근거를 반복 입력해도 중복 가산하지 않는다. 같은 출처가 상반된 주장으로 제출되면 충돌로 격리한다. 같은 시각·scope의 정상/이상 주장은 `REVIEW_CONFLICT`로 남긴다. 다른 시각의 정상과 이상 결과가 함께 있는 것은 그 자체로 충돌이 아니다. 미래 관측·미래 가용 근거, 다른 단위/센서/항목, 미평가 결과는 점수에서 제외하고 이유를 반환한다. Context 근거는 설명에 남고 정상·이상 점수를 만들지 않는다.

무승인 기준 분석은 `POST /api/agents/evidence/analyze`에서 실행할 수 있다. 결과에는 점수 외에도 normal support, 종류별 coverage, missing, conflict, accepted/excluded provenance가 포함된다. 호출자 선언은 `DECLARED_REVIEW_INPUT`으로 표시하고 `approved=false`를 유지한다. 운영 계정 설정 전에도 이 분석 조회는 가능하다.

## 실제 승인에서 멈추는 영속 workflow

```text
Evidence Collection
→ Rule/AI/Metadata/Operation/RAG Fusion
→ Recommendation
→ Human Approval: PENDING에서 중단, result=null
→ reviewer 판정 APPROVED
→ operator의 별도 resume
→ Report Draft Agent
→ MLOps Recommendation
```

운영 workflow는 [PostgreSQL 모델](../ocean-ai-platform/backend/app/models/agent_workflow.py)의 `agent_workflow_run`과 `agent_workflow_transition`에 저장한다. 상태와 actor, 입력·추천·전이 record의 SHA, idempotency key, revision 및 `ApprovalHistory`가 세션 재시작 후에도 남는다. [명시적 migration](../ocean-ai-platform/backend/migrations/20261008_agent_workflow.sql)이 필요하며 API 조회로 테이블이나 계정을 자동 생성하지 않는다.

| API | 역할과 결과 |
|---|---|
| `POST /api/agents/evidence/analyze` | 읽기 전용 분석, Fusion 직접 응답, 승인·후속 실행 없음 |
| `POST /api/agents/workflows` | operator/reviewer/admin의 업무 생성, `PENDING`, `result=null` |
| `GET /api/agents/workflows` 및 `/{workflow_id}` | 저장 상태 조회, 목록은 station/sensor/variable/unit 조건을 적용한 후 최대 200개 |
| `POST /api/agents/workflows/{workflow_id}/decision` | reviewer/admin만 `APPROVED` 또는 `REJECTED` 판정 |
| `POST /api/agents/workflows/{workflow_id}/resume` | operator/reviewer/admin, 현재 실제 승인과 동일 입력을 검증한 후 초안 생성 |
| `POST /api/agents/workflows/{workflow_id}/cancel` | 요청자 또는 reviewer/admin의 중단 |
| `GET /api/agents/workflow/stages` | 단계와 중단 경계 설명 |

판정·재개·취소는 현재 `recommendation_sha256`와 `revision`을 함께 제출해야 한다. 승인·재개에는 frozen 입력과 추천, 현재 DB 행·참여 목록·파일 SHA·계산 recipe의 일치가 필요하다. 최신 실제 승인과 actor 전이 이력도 재개 시 대조한다. 동시 요청은 row lock과 revision CAS로 한 번만 후속 단계를 실행한다. 같은 key·actor·내용의 replay는 저장 결과를 반환한다. stale 승인과 다른 내용의 replay, 취소·거부 후 재개는 차단한다. 외부 근거 변경 후에는 해당 입력을 승인/재개할 수 없지만 저장 snapshot을 변경하지 않고 취소할 수 있다.

인증은 [서버 Actor](../ocean-ai-platform/backend/app/core/security.py)를 사용한다. body에 `user_id`, `approved_by`를 넣어 권한을 만들 수 없으며 알 수 없는 request 필드는 거부한다. 실제 계정 설정은 별도 작업이다. demo 전용 `POST /api/agents/workflow`도 이제 `PENDING`에서 멈추고 후속 결과를 만들지 않는다. 이 demo는 영속 승인 업무를 만들지 않으며 live에서는 기존 정책대로 차단한다.

## 초안 완료와 운영 승인 구분

`COMPLETED`의 `result`는 `{report_draft, mlops, workflow_approval_history_id, recommendation_sha256, source_qc_dataset_model_approval_granted:false}`이다. 보고서는 `DRAFT`, MLOps는 `RECOMMENDATION`이고 학습 queue·모델 등록·배포를 실행하지 않는다. Recommendation 승인과 원천/QC/Label/Dataset/보고서/모델 승인은 다른 업무다. 최종 QC·학습·배포는 [승인](17_HUMAN_IN_THE_LOOP.md), [Dataset](18_DATASET_REGISTRY.md), [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md)의 실제 승인 경로를 계속 따른다.

개발 시험은 SQLite/temp 원문을 사용한 격리 승인·ingest·Rule·AI 연결, 실제 동시 resume, stale/replay/tamper/cancel를 검증한다. 별도 PostgreSQL 임시 schema에서는 migration, 세션 재시작, 실제 ledger와 승인 전/후 재개 경계를 검증했다. 이 결과가 운영 데이터나 담당자 승인을 만들어 주지는 않는다. 2026-10-08 13:09 KST 운영 확인은 원천·승인·Dataset·Model Registry 0, `API_IDENTITIES` 0이며 72 업무는 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이다. 이후 운영과 웹 상태는 [P0 진행 현황](24_P0_END_TO_END_PROGRESS.md)에 기록한다.
## 10/8 단계별 보완 결과

단계별 세 에이전트가 코드·원천·격리 실행을 맡고 서로 malformed shape/API500, receipt locator, 문서 rollback postimage 문제를 재현·수정했다. 부모가 최종 전체 회귀·PostgreSQL8gate·원문/수치·실API/브라우저를 검증했다. root stage-index는 human authority가 아니며 Recommendation 승인은 source/QC/Dataset/Model 승인을 부여하지 않는다. [29](29_DEVELOPMENT_STAGE_EXECUTION.md).
