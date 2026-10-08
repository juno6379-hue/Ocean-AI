# Multi-Agent Workflow

작성일: 2026-09-16

## 구조

`routes_agents.py`는 단순 챗봇 API가 아니라 명시적 상태 머신을 호출한다. `multi_agent_workflow.py`의 각 단계가 상태를 입력받아 결과를 추가하고 다음 단계로 전달한다.

```text
Anomaly Detected
  → QC Analysis Agent
  → Root Cause Agent
  → RAG Evidence Agent
  → Recommendation
  → Human Approval
  → Report Draft Agent
  → MLOps Agent
```

구현된 Agent:

- QC Analysis Agent: Standard Observation 범위 이상 후보와 QC 지표 계산
- Root Cause Agent: AI Label·운영 로그 기반 원인 후보 추정
- RAG Evidence Agent: Hybrid Retrieval 근거 조회
- Report Draft Agent: 분석 초안 생성
- MLOps Agent: 재학습 우선순위 추천

Human Approval 단계는 `PENDING` 게이트로 멈추며, 승인 전 결과를 확정하지 않는다.

## API

- `POST /api/agents/workflow`
- `GET /api/agents/workflow/stages`

워크플로우 응답에는 각 단계 로그, QC 결과, 원인 후보, RAG 근거, 추천 조치, 승인 상태, 보고서 초안, MLOps 우선순위가 포함된다. 최상위 상태는 `ANALYSIS_ONLY`로 반환한다.

빈 관측 데이터에서도 전체 단계가 순서대로 실행되는 것을 확인했다. 실제 운영 적용 시 각 단계의 규칙·모델·승인 API를 교체해도 workflow 계약은 유지된다.
