# Multi-Agent Workflow의 현재 실행 범위

현행화: 2026-10-08

## 기존 workflow API는 데모 분석 경로

[routes_agents.py](../ocean-ai-platform/backend/app/api/routes_agents.py)는 [multi_agent_workflow.py](../ocean-ai-platform/backend/app/agents/multi_agent_workflow.py)의 단계 함수를 순서대로 호출한다. 이 경로는 현재 원천 승인·고정 dataset·모델 worker를 연결하는 운영 상태 머신이 아니다. [서버 권한 검사](../ocean-ai-platform/backend/app/core/security.py)는 `POST /api/agents/workflow`를 `DATA_MODE=demo`에서만 허용하며 live 모드에서는 409로 차단한다.

```text
Anomaly Detected
  → QC Analysis Agent
  → Root Cause Agent
  → RAG Evidence Agent
  → Recommendation
  → Human Approval (PENDING 표시)
  → Report Draft Agent
  → MLOps Agent
```

Human Approval 함수는 `PENDING` 정보를 state에 추가한다. 실행 loop는 그 뒤의 보고서와 MLOps 단계도 계속 호출한다. 실제 승인 응답을 기다리거나 승인 후 재개하는 기능은 없다. 최상위 `ANALYSIS_ONLY`와 승인 대기 문구가 결과 확정을 구분하지만, 이 marker를 실제 승인 게이트로 설명해서는 안 된다.

| 단계 | 구현된 동작 | 운영 적용 경계 |
|---|---|---|
| QC Analysis | 값 5 미만·30 초과를 후보로 세는 `range_rule(v1)` | 항목·단위·시행기간에 맞춘 승인 QC 코드북이나 실제 AI 모델이 아니다. |
| Root Cause | 최근 관측소 라벨 또는 통신 로그에서 원인 후보를 선택 | 승인 라벨만 선택하지 않으며 실제 사건·센서 유효기간에 결합되지 않는다. |
| RAG Evidence | 관측소 조건으로 hybrid retrieval을 요청 | 검색 오류도 빈 근거로 반환하므로 빈 목록이 충분한 근거를 뜻하지 않는다. |
| Recommendation | 후보 원인에 따라 점검 문구를 구성 | 운영 조치 수행이나 장애 확정이 아니다. |
| Human Approval | `PENDING`, `required=True` 표시 | 실제 actor·승인 이력·내용 hash 검증 및 중단·재개가 없다. |
| Report Draft | state를 텍스트 초안으로 구성 | 승인된 Report Registry 등록·발행이 아니다. |
| MLOps | 후보 10건 이상이면 HIGH, 그 외 NORMAL 추천 | 승인 입력이나 durable training queue에 연결되지 않는다. |

입력 조회는 관측소의 최신 `ObservationStandard` 최대 500행이다. `sensor_id`를 요청받아 state에 저장하지만 조회 조건에 적용하지 않고 항목·단위도 분리하지 않는다. 이 범위에서 계산한 혼합 값의 QC 후보를 실제 센서·업무 평가로 사용할 수 없다.

```text
POST /api/agents/workflow
GET /api/agents/workflow/stages
```

응답에는 단계 로그, QC 집계, 원인 후보, RAG 근거, 추천, 승인 대기 marker, 보고서 초안, 재학습 우선순위가 포함된다. stages 조회는 단계 목록을 설명하며 live 운영 완료를 입증하지 않는다.

## 개별 검토 agent와 운영 실행 체계

[QC Copilot agent](../ocean-ai-platform/backend/app/agents/qc_copilot_agent.py)와 [원인 진단 agent](../ocean-ai-platform/backend/app/agents/cause_diagnosis_agent.py)의 검토 bundle은 재검사·원천 flag·AI 점수·담당 QC와 문서 근거를 구분한다. 미실행 결과는 `NOT_EVALUATED`로 보존하고 근거 없는 정상 판정이나 확정 원인을 만들지 않는다. 이 개별 adapter의 개선이 위 데모 workflow 전체를 원천 승인 기반 workflow로 바꾸지는 않는다.

현재 엄격한 실행 경로는 다음처럼 별도 API·service로 구현되어 있다.

```text
실제 원천 계약 판정·내용 hash 승인
→ approved source ingest와 원문 관측 binding
→ 사건·라벨·Feature 근거 검토
→ 고정 protocol과 dataset snapshot v2 승인
→ preflight와 fenced worker
→ 독립 재현 검토·candidate Registry
→ 실제 배포 identity 승인·local serving
```

각 단계의 권한과 불변 근거는 [17](17_HUMAN_IN_THE_LOOP.md), [18](18_DATASET_REGISTRY.md), [19](19_MLOPS_VERSION_AND_EVALUATION.md)를 따른다. agent가 `APPROVED` 문자열을 출력하는 것으로 이 gate를 통과할 수 없다. 개발 작업을 여러 agent가 나누고 상호 검토한 결과도 원천 담당자의 운영 승인과 구분한다. 개발상의 분담은 [협업 지침](../ocean-ai-platform/docs/77_AGENT_COLLABORATION_EXECUTION.md)을 참고한다.

## 검증과 남은 작업

2026-10-08 공개 코드의 backend 345개 시험 통과·1개 skip과 frontend build는 구현 검증이다. 13:09 KST 실제 DB에는 승인·데이터셋·학습·모델·사건 기록이 모두 0이었다. 72업무 mapping은 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이며 운영 모델 선정 완료가 아니다.

운영 agent orchestration에는 항목·단위·센서·기간별 입력, 실제 승인 대기·재개 상태, 검색 오류 구분, 승인 근거와 작업 큐의 연결 검증이 남아 있다. 현재 live에서 차단된 데모 workflow를 이 작업의 완료 증거로 사용하지 않는다. 최신 실행 확인은 [P0 진행 현황](24_P0_END_TO_END_PROGRESS.md)에 기록한다.
