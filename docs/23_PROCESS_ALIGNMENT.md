# process.md 요구사항과 현행 구현의 대응

현행화: 2026-10-08

[process.md](../process.md)의 P0/P1 요구사항을 현재 코드와 실제 운영 상태에 대조한 문서다. 요구사항의 목표, 구현된 실행 경로, 승인된 운영 결과를 구분한다. 기존 데이터와 설명은 단계적으로 보강하며 기술 검증으로 담당자의 승인을 대신하지 않는다.

## 구조와 실행 경로

| 요구사항 | 현행 구현 | 실제 운영을 위해 필요한 근거 |
|---|---|---|
| Observation → Standardization | 실제 원문/Parquet 행·단위 변환·시각·물리 센서·기간을 검증하는 Source Contract, 승인 ingest와 `SourceObservationBinding` | 원천 담당자의 exact packet/receipt 승인. SIMULATED DB 관측은 실제 원천으로 승격하지 않는다. |
| Rule QC → QC Copilot | `QCRuleDefinition`, `QCRuleResult`, 명시적 규칙 실행 API, 원천 flag·재검사·AI 점수·담당 QC를 분리하는 검토 bundle | 일반 min/max 실행은 원천 QC 코드북·시행기간 전체 구현이 아니다. 미실행은 NOT_EVALUATED로 보존한다. |
| 사건·라벨·문서 근거 | `EventRegistry`, `EventEvidence`, 기간·센서 식별자 검토, AI Label 승인 snapshot과 검토 이력 | 동일 관측소·날짜만으로 사건을 병합하지 않는다. 실제 이벤트·라벨 연결과 승인 기록이 필요하다. |
| Feature·Dataset lineage | Feature 원천 가용/QC 가용 시각 검증, 고정 membership, snapshot v2의 원천·3종 protocol 의존성 동결 | 원천·Feature as-of·고정 분할·Dataset 내용 SHA와 실제 승인 일치. legacy v1 자동 승인은 차단한다. |
| 문서 embedding/RAG | Ingest·parser·chunk·index 버전·검색 traceability 경로 | 로컬 원문과 문서 contract·검색 성능을 검증한다. 원시 관측 수치와 문서 embedding 대상을 구분한다. |
| 학습·평가·Registry | 자료형 6종의 제한된 기준선, 고정 split/evaluation/acceptance 정책, fenced 큐·worker, 독립 재현 검토와 후보 등록 | 72개 mapping은 REPRESENTATION_BASELINE_SCOPE_PARTIAL. 실제 승인 원천의 비교·선정과 업무별 추가 적합성 검증이 필요하다. |
| 배포·rollback | 정확한 candidate/report/artifact identity 승인, 수치 JSON loopback serving과 승인 rollback·실패 복원 | 실제 MODEL_DEPLOY/MODEL_ROLLBACK 이력과 runtime identity·성능·비용 검증. 상태 문자열만으로 serving하지 않는다. |
| 인증·감사·화면 | 서버 actor/reviewer 검사, HTTP 구조화 로그, ApprovalHistory·불변 receipt, 실제 상태를 나누는 화면 | 운영 담당 identity와 권한 설정, 일반 요청의 영속 AuditLog/보존 정책, 승인 실패·반려 동작 검증이 필요하다. |

관련 구현은 [원천 authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py), [snapshot bridge](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py), [Dataset lineage](../ocean-ai-platform/backend/app/services/dataset_lineage.py), [QC API](../ocean-ai-platform/backend/app/api/routes_qc.py), [model preflight](../ocean-ai-platform/backend/app/ml/comparison_runner.py), [worker 큐](../ocean-ai-platform/backend/app/ml/job_queue.py), [security](../ocean-ai-platform/backend/app/core/security.py)를 기준으로 한다.

## 스키마와 실제 적용의 구분

모델 정의·migration 파일이 존재하는 것과 운영 DB에 적용되어 데이터가 적재된 것은 다르다. `AUTO_CREATE_TABLES`는 기본 false이며 운영 전체 스키마를 앱 기동만으로 생성하지 않는다. 원천 계약의 [명시적 migration](../ocean-ai-platform/backend/app/scripts/migrate_source_contracts.py)은 기본 dry-run이고 `--apply`를 선택하면 신규 packet·decision 두 테이블만 만든다. 관측 binding은 [별도 migration](../ocean-ai-platform/backend/migrations/20261007_source_observation_binding.sql)이며 필요한 기존 테이블과 제약을 함께 확인해야 한다.

2026-10-08 13:09 KST 읽기 전용 DB 확인에서 source packet/decision/binding, ApprovalHistory, DatasetRegistry, ModelRegistry, RetrainingHistory, EventRegistry/EventEvidence, SensorAlias는 모두 0이었다. `mdc_sensor_catalog`는 운영 DB에 없었다. 과거 문서의 migration 성공·기본 QC 2건 적재 주장을 이번 실제 운영 상태로 이어 쓰지 않는다. 이 현행화 작업은 migration이나 운영 DB 적재를 수행하지 않았다.

## 완료 판단

공개 작업본의 backend 345개 시험 통과·1개 skip과 깨끗한 frontend 설치/build는 코드 검증이다. 실제 canonical worker 프로세스 실행과 빈 큐는 확인됐지만 승인 학습 입력과 운영 모델이 없다. 따라서 P0/P1 전체 운영 완료로 판정하지 않는다.

원천·기간·사건 승인, 고정 학습 입력과 수용 기준, 업무별 실제 비교, 독립 검토·모델 등록, 배포 identity와 운영 비용 검증을 순서대로 완료해야 한다. 기존 다중 agent 데모의 PENDING marker도 이 승인 흐름을 대체하지 않는다.

세부 계약은 [승인](17_HUMAN_IN_THE_LOOP.md), [Dataset](18_DATASET_REGISTRY.md), [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md), [agent 경계](21_MULTI_AGENT_WORKFLOW.md), [상세 릴리스](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md), 실제 확인 시점은 [P0 진행 현황](24_P0_END_TO_END_PROGRESS.md)에 정리한다.
