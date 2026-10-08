# 기능 구현 실태 점검

현행화: 2026-10-08

대상은 이 저장소의 `ocean-ai-platform/backend`와 `frontend`다. 구현된 실행 경로, 시험 통과, 실제 자료 승인, 운영 실행을 각각 구분한다. 2026-09-16의 최초 점검에서 미구현으로 분류했던 기능도 이후 코드가 추가되어 아래 판정을 적용한다.

## 현행 구현과 실제 적용 조건

| 항목 | 현재 코드 경로 | 운영에 필요한 조건·한계 |
|---|---|---|
| 원천 의미·단위·시간·센서 계약 | [source_contract_authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py), [요청·판정 API](../ocean-ai-platform/backend/app/api/routes_source_contracts.py) | 실제 actor, packet/receipt SHA, 최신 승인 원장, 원문·Parquet 행 재검증이 필요하다. 기술 검토를 인간 승인으로 승격하지 않는다. |
| Raw/Standard와 원천 binding | [source_contract_snapshot](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py)의 `ingest_approved_source()` | 승인 원천에 한해 멱등 적재한다. literal·해시·locator·물리 센서·기간을 binding에 보존한다. 기존 MDC 매핑은 이 승인 계약을 대체하지 않는다. |
| QC 실행·최종 검토 | [QC API](../ocean-ai-platform/backend/app/api/routes_qc.py), [승인 API](../ocean-ai-platform/backend/app/api/routes_approvals.py) | min/max 규칙 실행과 검토 후보 저장은 구현됐다. 원천 QC 코드북과 시행기간 승인, 업무별 규칙 적합성 검토가 별도로 필요하다. |
| AI Label·사건 근거 | [event_evidence](../ocean-ai-platform/backend/app/services/event_evidence.py), [label_review_agent](../ocean-ai-platform/backend/app/services/label_review_agent.py) | 사건·관측·문서·QC·운영 근거와 라벨 검토 snapshot을 연결한다. `PENDING` 후보는 학습 정답이 아니다. |
| Feature 계산·계보 | [evidence_features](../ocean-ai-platform/backend/app/services/evidence_features.py), [feature_generator](../ocean-ai-platform/backend/app/ml/feature_generator.py) | 사건 기반 과거·현재 feature와 시간별 lag 실험이 구현됐다. 원천/QC 실제 가용 시각과 feature 선언 시각을 snapshot에서 재검증한다. |
| 문서 수집·Embedding | [document_pipeline](../ocean-ai-platform/backend/app/rag/document_pipeline.py), [document_contract](../ocean-ai-platform/backend/app/rag/document_contract.py) | 파일 원장·내용 중복·재개·Ollama 모델 digest·Chroma 계약을 사용한다. Git clone만으로 원문·색인·실행 완료가 생성되지는 않는다. |
| Hybrid Retrieval | [hybrid_retriever](../ocean-ai-platform/backend/app/rag/hybrid_retriever.py) | 관계형 필터→벡터→키워드→가중 재정렬이 구현됐다. keyword-only 결과의 cosine은 `null`이다. 검색 성공은 원천 또는 사건 승인과 별개다. |
| 근거 설명 | [qc_copilot_agent](../ocean-ai-platform/backend/app/agents/qc_copilot_agent.py), 사건·문서 근거와 검토 응답 | 근거·미확정 사유를 전달한다. 설명 문구의 존재가 SHAP 기여도, 모델 confidence 또는 업무별 설명 충실도 평가 완료를 뜻하지 않는다. |
| Dataset Version | [dataset_lineage](../ocean-ai-platform/backend/app/services/dataset_lineage.py), source dependency freeze | v2 snapshot에 source와 split/evaluation/acceptance 의존성을 동결한다. 기존 v1의 자동 승인·자동 운영 전환은 지원하지 않는다. |
| 모델 비교·작업·Registry·서빙 | [comparison_runner](../ocean-ai-platform/backend/app/ml/comparison_runner.py), [MLOps 실행 API](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | 고정 분할, 실제 승인, worker, 독립 검토, candidate 등록·배포·loopback 서빙의 코드가 있다. 승인 입력 없이 모델을 만들거나 배포 완료로 표시하지 않는다. |
| 인증·Human Approval | [security](../ocean-ai-platform/backend/app/core/security.py) 및 각 승인 서비스 | 서버 identities의 actor/role을 사용한다. 요청 본문의 사용자·상태 문자열은 승인 권위가 아니다. 인증 미설정은 차단한다. |
| 화면·API 등록 | [main.py](../ocean-ai-platform/backend/app/main.py), [API client](../ocean-ai-platform/frontend/src/api/client.ts) | source/technical-review/dataset/approval 등 라우터와 환경별 API wrapper를 연결한다. loading/error/실제 0을 분리한다. |

## Copilot·에이전트의 경계

`/api/qc/copilot/analyze`는 저장된 관측·규칙·AI 결과와 문서 검색을 근거로 분석 응답을 반환한다. 최종 QC를 자동 저장하거나 인간 승인으로 처리하지 않는다. [qc_review_agent](../ocean-ai-platform/backend/app/services/qc_review_agent.py)는 코드북·물리 센서·시행기간 등 근거가 없으면 미평가/차단 사유를 반환한다.

호환 경로인 [multi_agent_workflow](../ocean-ai-platform/backend/app/agents/multi_agent_workflow.py)는 휴리스틱 규칙과 `PENDING` 표시를 포함하는 분석 프로토타입이다. 그 `HumanApproval` 단계는 실제 reviewer 결정에 결합된 운영 승인 gate가 아니다. 상세는 [멀티 에이전트 workflow](21_MULTI_AGENT_WORKFLOW.md)를 참고한다. 모든 agent 경로가 엄격한 원천→모델 승인 사슬로 통합됐다고 해석하지 않는다.

## 날짜가 있는 검증 기록

- 2026-10-08 공개 작업본: backend 전체 시험 **345 passed / 1 skipped**, 깨끗한 `npm ci --ignore-scripts` 및 TypeScript/Vite production build 통과. 이는 코드·재현 설치 검증이다.
- 부모 에이전트의 2026-10-08 **04:09:54Z** PostgreSQL 읽기 전용 확인: `source_contract_packets`, `source_contract_decisions`, `source_observation_binding`, `approval_history`, `dataset_registry`, `model_registry`, `retraining_history`, `event_registry`, `event_evidence`, `sensor_alias`는 모두 **0**이었다. `API_IDENTITIES`도 0이며 `DATA_MODE=live`, MDC 자동 수집·전체 자동 DDL은 비활성화였다. `mdc_sensor_catalog`는 운영 DB에 아직 없었다. 모델 선언과 실제 마이그레이션·적재를 구분한다.
- 위 실측의 로컬 근거는 `docs-operational-readonly-20261008.json`이다. 운영 DB와 실측 원장은 Git에 포함하지 않으며, 수치는 해당 확인 시각에 한한다.
- 같은 날 runtime GET의 MLOps readiness는 `BLOCKED`였다. 기존 canonical worker는 설정·실행 확인됐지만 queue jobs는 비어 있었고 `approved_input_ready=false`, 실제 운영 모델은 0이었다. serving health는 `409 NO_ACTIVE_LOCAL_MODEL`이었다. 프로세스 실행과 실제 학습·운영 완료를 구분한다.
- 2026-10-07 원천 검토 기록: AIR_PRES 500행의 원문·Parquet 일치는 확인했으나 **18,502개 검증 항목이 미확정**이었다. 검토 파일의 사건 후보 40개 미연결 및 기간 충돌 1건/152 grain의 해결 승인은 확보되지 않았다. 이 40개는 DB 사건 건수가 아니다.

## 남은 단계

실제 원천 의미·단위/배율/기준면·시계·QC 판본/기간·물리 센서/기간의 근거를 확정하고 인증된 담당자가 판정해야 한다. 이어 실제 source ingest, 사건·라벨·feature 계보, v2 snapshot과 고정 프로토콜 승인, 비교 학습·독립 검토·Registry·배포를 진행한다. 단계와 책임은 [Human-in-the-loop](17_HUMAN_IN_THE_LOOP.md), [Dataset](18_DATASET_REGISTRY.md), [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md)에 연결한다.

72개 업무 키의 상태는 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이다. 자료형 기준선 지원이 72개 운영 모델 선정·완료를 뜻하지 않는다. 전체 구현 및 자료형별 제한은 [게시 구현 기준](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)을 따른다.
