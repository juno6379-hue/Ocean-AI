# 03. Agent 업무와 승인 흐름

기준일: 2026-10-08. Agent는 원천·문서·QC 근거를 모아 검토 후보를 만들고, 실행 가능 조건을 검증한다. 인간의 source/QC/센서 구간 승인과 운영 모델 배포 결정을 대신 기록하지 않는다. [전체 구성](01_SYSTEM_ARCHITECTURE.md), [승인 설계](17_HUMAN_IN_THE_LOOP.md), [상세 구현 82](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)를 참조한다.

## 현재 Agent 구현

| 역할 | 실제 동작 | 산출물의 상태 |
|---|---|---|
| QC Copilot | 정확한 station/sensor/item/기간 scope의 원천 QC 문자, 규칙 결과, 문서 근거를 묶는다. 공백·NULL을 보존한다. | 분석/검토 후보. 원문 QC의 의미와 최종 운영 QC는 별도 승인이다. |
| 원인 진단 | 기존 근거와 문서에 나타난 사건 후보를 정리한다. 자료에 없는 고장 원인·확률을 생성하지 않는다. | 원인 미확정 또는 문서 연결 후보. 검색 유사도를 인과 확신도로 바꾸지 않는다. |
| 라벨 검토 | 저장된 observation/event/document/operation 식별자와 검토 입력을 대조한다. | 라벨 검토 packet. 누락된 사건·센서 identity를 발명하지 않는다. |
| 보고서 | 검토 상태를 포함한 초안을 생성한다. | DRAFT와 생성 기록. 검토·승인·발행은 별도 API 상태 전이다. |
| MLOps | 승인 dataset과 protocol, artifact 계보를 검증하고 실행 요청 또는 우선순위 추천을 만든다. | 추천, BLOCKED, 실행 후보. 추천을 등록·배포 성공으로 표기하지 않는다. |

근거: [QC Agent](../ocean-ai-platform/backend/app/agents/qc_copilot_agent.py), [원인 진단](../ocean-ai-platform/backend/app/agents/cause_diagnosis_agent.py), [라벨 검토](../ocean-ai-platform/backend/app/services/label_review_agent.py), [보고서 Agent](../ocean-ai-platform/backend/app/agents/report_agent.py), [QC 검토 서비스](../ocean-ai-platform/backend/app/services/qc_review_agent.py).

## 분석 graph와 demo prototype

[LangGraph orchestrator](../ocean-ai-platform/backend/app/agents/orchestrator.py)는 `fetch_data → detect_anomalies → diagnose_cause → generate_report` 순서로 수행한다. Station과 target date를 명시하며 선택 sensor/item과 제한된 관측 행을 읽는다. Graph 내부 노드 호출은 source approval, dataset approval, model deployment를 자동으로 수행하는 작업이 아니다.

별도의 [multi_agent_workflow.py](../ocean-ai-platform/backend/app/agents/multi_agent_workflow.py)는 QC→근거 확인→검색→추천→PENDING 검토 객체→초안→MLOps 추천의 prototype다. 여러 역할 이름이 있으나 코드에서는 순차 처리하며 일반 범위 규칙과 최근 Standard 행을 사용한다. 결과는 `ANALYSIS_ONLY`다. 실제 인간 승인이나 훈련을 수행하지 않는다. `/api/agents/workflow`와 `/api/test-auto/run`은 `DATA_MODE=demo`에서만 열리고 live에서는 409다. `/api/agents/workflow/stages`는 단계 설명 조회다.

Live의 `/api/qc/copilot/analyze`는 분석 POST로 사용할 수 있다. 예를 들어 station/sensor/variable scope를 정해 원천 QC와 문서를 조회할 수 있지만, 결과가 나와도 승인된 source contract나 AI label이 생성된 것으로 해석하지 않는다. 실행 payload와 인증은 [API 명세](04_API_SPECIFICATION.md)를 참조한다.

## 실제 운영 승인으로 이어지는 순서

1. **Source owner 검토:** 원문 file/SHA/locator, 원천 문자열, 물리 센서·episode·기간, 단위와 변환, clock, 관측·수신·QC 가용시각, raw QC codebook을 검토한다. Agent가 기술적으로 확인한 부분과 담당자 미확정 부분을 같은 packet에서 구분한다.
2. **Source contract 결정:** `/api/source-contracts/request`로 PENDING packet을 만들고, reviewer가 예상 packet SHA를 확인하여 decision을 기록한다. 승인 receipt는 실제 ledger와 현재 상태에 묶인다. Receipt와 DB의 requester/reviewer/hash 불일치, 현재 승인 철회·변조는 차단된다. Ingest operator가 원요청자와 동일해야 한다는 뜻은 아니다.
3. **승인 원천 ingest:** receipt와 원문을 다시 검증하고 Raw/Standard와 source binding을 저장한다. 사건·라벨·Feature는 각각의 근거·검토가 이어져야 한다. 보고일, 실제 고장 구간, 조치일, 관측일을 구분한다.
4. **Dataset 고정:** 승인된 source 의존성과 split/evaluation/acceptance 프로토콜, 실제 membership을 snapshot v2에 동결한다. Feature 입력 원천의 as-of까지 검증한다. 승인 없는 파일 후보는 draft 경로에 남는다.
5. **학습·독립 검토:** 고정 분할 manifest를 preflight 후 worker 큐에 넣는다. 후보 metric·artifact를 독립 replay하고 registry에 등록한다. 운영 배포·rollback 결정은 별도 reviewer와 무결성 검증을 요구한다.

Agent 간 최적화는 이 공통 grain, raw literal, 파일 hash, 기간·가용시각, receipt 인터페이스를 맞추고 상대 산출물을 재검토하는 것이다. 채널 수·문서 추출 수·모듈 시험 통과 수를 의미 승인 수로 바꾸지 않는다. [source authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py), [dataset bridge](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py), [model runner](../ocean-ai-platform/backend/app/ml/comparison_runner.py)가 실행 경계를 강제한다.

## 현재 남은 검토

2026-10-08 13:09 KST 운영 DB의 source 계약·결정·binding, 승인, dataset, model, retraining, 사건·근거·alias는 모두 0이며 인증 Actor도 아직 미설정이다. 2026-10-07 전수 검토 파일의 66,190 월 grain, 152 기간 충돌, 40 미연결 보고서 행은 기술 검토 분모와 후보 상태다. 인간의 전수 승인이나 운영 DB 등록 수가 아니다.

AIR_PRES 500행의 원문·Parquet 일치는 확인했으나 18,502 미확정 오류로 승인 준비도가 차단된다. Source/물리 sensor/기간/clock/단위/QC 담당자의 실제 결정, 사건·라벨·Feature 검토, 고정 split 승인 이후에 모델 비교가 가능하다. 72개 업무의 표현별 baseline 구현 상태는 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이며 업무별 승인 운영 모델 완수 상태가 아니다.
