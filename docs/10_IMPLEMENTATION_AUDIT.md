# 10/8 Current Implementation Audit

현행화: 2026-10-08. 9/16 최초 감사 이후의 코드와 이번 QC·AI·Fusion·승인 gate를 실제 구현에 대조한다. 구현 시험, 원천 사실 확인, 실제 담당 승인, 운영 모델은 각각 별도 판정이다.

## 현재 구현

| 항목 | 검증된 실행 경로 | 현재 적용 범위 |
|---|---|---|
| Rule QC | [12종 엔진](../ocean-ai-platform/backend/app/services/qc_rule_engine.py), 버전 catalog, 평가·저장 API | 가이드북 2023.12 p23/table2-7의 WT/LO/ER/GR/GD/RL/SP/RR/SR/ST/DE/PO. 단위·센서 episode·clock·QC 판본/기간·가용 시각·규칙별 보조입력이 없으면 NOT_EVALUATED. |
| 이상탐지 AI | [fitted anomaly analysis](../ocean-ai-platform/backend/app/services/anomaly_analysis.py), JSON artifact와 loopback 분석 API | 별도 고정 TRAIN/CALIBRATION으로 fit하는 인과 통계 모델. 조위 residual, TEMP/SAL drift, spike, persistence, biofouling candidate, sensor degradation candidate. 원인 확정이나 운영 성능 검증이 아니다. |
| Evidence Fusion | [fusion](../ocean-ai-platform/backend/app/services/evidence_fusion.py) | Rule/AI/Metadata/Operation/RAG를 Recommendation score로 결합한다. exact scope·기간·availability·원본 checksum을 확인하고 중복/충돌/누락을 표시한다. 개발 recipe이며 고장 확률·승인 운영 기준이 아니다. |
| Human Approval | [영속 workflow](../ocean-ai-platform/backend/app/agents/multi_agent_workflow.py), [API](../ocean-ai-platform/backend/app/api/routes_agents.py) | PENDING에서 중단한다. reviewer 결정 이후 별도 resume, hash/revision 재확인과 입력 변경·재요청·경합 차단. PostgreSQL에 상태·전이·승인 연결을 보존한다. |
| 화면 | [WorkflowReviewPanel](../ocean-ai-platform/frontend/src/components/WorkflowReviewPanel.tsx) | QC Copilot에서 scope 분석·상태 조회·승인/반려·재개. 실제 계정 미설정이면 조회/분석만 가능하다. |
| 원천 계약·production bridge | [authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py), [snapshot](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py) | 승인 원천 재검증·ingest binding·v2 source dependency freeze 구현. legacy v1 자동 전환은 미지원이다. |
| 고정 비교·worker·registry·serving | [model runner](../ocean-ai-platform/backend/app/ml/comparison_runner.py), [실행 API](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | 승인 source/dataset/protocol과 독립 검토를 요구한다. 자료형 기준선 부분 구현이며 72업무의 실제 선정/배포 완료가 아니다. |
| 문서 검색·Feature·사건 | [문서](15_DOCUMENT_INDEX_INGESTION.md), [feature](14_FEATURE_STORE.md), [라벨](13_AI_LABEL_SEPARATION.md) | 기존 계보·contract·as-of 검증을 유지한다. 문서 검색 결과는 물리 고장 또는 원천 의미 승인 증거로 자동 승격하지 않는다. |

호환 `/api/agents/workflow`는 demo 전용이며 이제 PENDING에서 멈춘다. live 운영 검토는 `/api/agents/evidence/analyze`와 `/api/agents/workflows`를 사용한다. 기존 일반 orchestrator나 AI Insights 휴리스틱을 새 fitted 모델 실행과 혼동하지 않는다. Workflow 승인 후 생성되는 것은 보고서 초안과 MLOps 추천이다. 학습 enqueue·모델 등록·배포는 수행하지 않는다.

## 검증 기록

최종 전체 회귀와 frontend build 결과는 [current_status.json](current_status.json)에 기록한다. 이전 공개 tree의 345 passed/1 skipped는 이번 추가 코드의 시험 결과로 재사용하지 않는다.

부모 검증은 별도 PostgreSQL schema에 기존 ORM 구조를 만든 뒤 실제 두 additive migration을 두 번 적용했다. 새 session에서 PENDING 유지·승인 전 resume 차단·승인 후 resume·멱등 재요청·입력 membership 변경 차단을 확인하고 schema를 제거했다. 실제 승인·source·dataset·model 원장 값은 바꾸지 않았다. 이 검증은 실제 계정 승인 또는 실제 원천 학습이 아니다.

가이드북 catalog는 실제 PDF 180개 matrix cell과 대조했다. 보존된 실제 AIR_PRES 500행의 hash/literal 일치와 12×500=6,000 QC 미평가를 확인했다. 원천 조건 누락을 정상으로 계산하지 않았다. 실제 WATER_TEMP 500행도 naive 시각·QC 판본·historical 단위/episode 근거 부족으로 fit하지 않았다. 합성 held-out anomaly 결과는 코드 동작 시험이며 실제 해양 자료의 성능 수용 결과가 아니다.

## 실제 운영 상태와 남은 일

업무 DB는 PostgreSQL이다. SQLite는 격리 단위시험과 기존 로컬 worker/file queue에만 남는다. 실제 계정 설정은 사용자 지시로 DEFERRED_BY_USER이며 새 계정·token·인간 승인 기록을 발명하지 않았다. source packet/decision/binding, ApprovalHistory, DatasetRegistry, ModelRegistry, RetrainingHistory는 확인 시각에 모두 0이다.

[원천 사실 재확인](26_SOURCE_FACT_RESOLUTION.md)에서 가이드 판본·현재 항목 literal/단위·캡처 SQL은 확인했다. 과거 행의 배율/기준면·시계·QC 코드북 시행기간·물리 센서 유효기간을 확정할 증거는 부족하다. 기존 미확정 18,502개 항목, 미연결 사건 후보 40개, 기간 충돌 1건/152 scope의 담당 판정도 남아 있다. 실제 source fit·registry·운영 모델은 0이며 P0 전체 운영 완료로 판정하지 않는다.

다음 순서는 근거 보완 → 원천/기간/사건 기술 판정 → 실제 업무 수행 시 계정 설정과 source 승인 → 승인 ingest/v2 snapshot·고정 분할/수용 정책 승인 → 업무별 실제 비교·독립 검토·registry·배포 검증이다. [현재 단계](24_P0_END_TO_END_PROGRESS.md), [QC](12_QC_RULE_RESULT_LAYER.md), [AI](25_ANOMALY_AI.md), [승인](17_HUMAN_IN_THE_LOOP.md)을 따른다.

최종 검증: 2026-10-08 backend **512 passed / 1 skipped**(46.36초), frontend TypeScript/Vite build PASS. 실제 PostgreSQL 임시 schema의 migration·session 재개·입력 변경 차단 PASS와 최신 backend8010의 QC/AI→Fusion 읽기 전용 HTTP 연결을 확인했다. 실제 source fit·model registry·배포는0이다.
