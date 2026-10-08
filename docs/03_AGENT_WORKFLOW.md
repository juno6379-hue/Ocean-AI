# 03. Agent 업무와 실행 경계

기준일: 2026-10-08. Agent 간 역할을 공통 scope·원문 hash·sensor episode·as-of·원본 보고서 checksum으로 연결한다. 담당 계정 설정은 실제 운영 시점으로 미루며 기술 분석은 계속할 수 있다.

## 이번 구현의 실행 순서

1. 원천·센서·단위·시계·QC·기간 사실과 보조입력을 확인한다. [12종 QC](12_QC_RULE_RESULT_LAYER.md)는 누락 조건을 NOT_EVALUATED로 남긴다.
2. [통계 이상탐지](25_ANOMALY_AI.md)는 독립 고정 TRAIN/CALIBRATION과 causal window로 fit/analyze한다. 호출자가 선언한 개발 contract는 실제 source 승인 권위가 아니다.
3. [Evidence Fusion](21_MULTI_AGENT_WORKFLOW.md)은 Rule+AI+Metadata+Operation+RAG를 하나의 Recommendation score로 결합하고 coverage·충돌·미확정 사유를 함께 반환한다.
4. operator가 workflow를 만들면 PostgreSQL PENDING에서 멈춘다. reviewer 결정 이후 별도 resume 요청에서 내용 SHA·revision·원천 membership·파일 의존성을 다시 확인한다.
5. resume은 검토된 보고서 DRAFT와 MLOps 추천을 반환한다. 훈련 enqueue·registry·배포의 승인과 실행은 별도 기존 경로다.

새 readonly `/api/agents/evidence/analyze`, `/api/qc/rules/evaluate`, loopback `/api/anomaly-analysis/fit`·`analyze`는 실제 승인 계정 없이 개발 검토에 쓸 수 있다. 개발 사실 선언은 원천 적재 또는 운영 승인으로 저장되지 않는다. 실제 workflow 생성·결정·재개는 서버 Actor/role을 요구한다. [API](04_API_SPECIFICATION.md), [Human Approval](17_HUMAN_IN_THE_LOOP.md)을 참조한다.

## 기존 agent와의 관계

QC Copilot은 관측·QC·문서 근거를 설명하고, label reviewer는 사건·관측·문서 snapshot을 검토한다. 기존 LangGraph orchestrator의 fetch/detect/diagnose/report 흐름은 분석용이며 source/dataset/model 승인을 수행하지 않는다. AI Insights의 heuristic 점수도 새 fitted anomaly artifact와 별도다.

호환 `/api/agents/workflow`는 demo 전용이다. 이 경로도 PENDING에서 중단하지만 실제 영속 승인 절차는 `/api/agents/workflows`를 사용한다. 단계 이름이 여러 개라는 이유로 병렬 운영 agent나 모델 배포가 완료됐다고 표시하지 않는다.

## 운영 모델까지 이어지는 별도 사슬

원문/Parquet 재검증과 인증 source 결정 → 승인 observation binding → 사건·라벨·Feature 가용시각 검토 → v2 snapshot source/protocol 의존성 동결 → 고정 train/validation/test 비교 → worker 후보 → 독립 재현·등록 → 별도 배포 identity 승인 → serving·rollback 검증이 필요하다. legacy v1을 승인 v2로 자동 승격하지 않는다.

이번 개발 검증은 인간 전수 승인이 아니다. 실제 historical 원천 사실과 사건/기간 판정이 부족하며 source 승인·dataset·model registry·운영 모델은 0이다. 72업무는 REPRESENTATION_BASELINE_SCOPE_PARTIAL이다. [원천 사실](26_SOURCE_FACT_RESOLUTION.md), [현재 단계](24_P0_END_TO_END_PROGRESS.md), [상세 source/model 연결](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)을 참조한다.
