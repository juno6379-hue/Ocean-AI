# P0 현재 단계와 다음 작업

현행화: 2026-10-08. 요구사항: [process.md](../process.md).

## 현재 단계

이번 개발의 12종 Rule QC, fitted 통계 이상탐지 6모드, 5종 Evidence Fusion, PostgreSQL stop/resume 승인 gate와 QC 화면 연결을 구현했다. 코드·격리 시험을 검증했으며 최신 웹과 GitHub 문서를 함께 갱신한다. 실제 원천 승인·dataset·학습·registry·운영 모델은 0이다. 전체 운영 완료로 판정하지 않는다.

| 사용자 요청 | 현재 상태 | 남은 조건 |
|---|---|---|
| 미확정 원천 사실 확정 | 가이드 원문/판본·현재 metadata literal·captured SQL·실제 표본 hash를 재확인 | historical 배율/기준면/시계/QC 판본·시행기간/물리 센서 episode를 확정할 근거 부족. 현재 metadata를 과거 전체에 소급하지 않는다. |
| 12종 Rule QC | WT/LO/ER/GR/GD/RL/SP/RR/SR/ST/DE/PO 엔진·catalog·API·결과 계보 구현 | 실제 조건/보조자료가 빠지면 NOT_EVALUATED. 실제500행×12=6,000건도 미평가로 유지한다. |
| 실제 이상탐지 AI | fixed TRAIN/CALIBRATION, causal spike/persistence/tide residual/TEMP-SAL drift/biofouling/degradation 후보 구현 | 합성 held-out 검증은 완료. 실제 WATER_TEMP 원천 조건 미확정으로 source fit 0이며 운영 성능 수용도 남는다. |
| Evidence Fusion | Rule+AI+Metadata+Operation+RAG의 단일 recommendation_score·coverage·충돌·누락 구현 | 개발 가중 recipe. 실제 업무 수용 기준이나 고장 확률이 아니다. |
| Human Approval | PostgreSQL 영속 PENDING 중단, reviewer 결정 후 explicit resume·hash/revision/membership 검증 | 실제 계정 설정은 DEFERRED_BY_USER. 승인 후에도 보고서 초안/MLOps 추천이며 학습/registry/배포를 수행하지 않는다. |
| source→snapshot→모델 | 승인 binding, v2 freeze·고정 비교·worker·독립 등록·serving 코드 유지 | legacy v1 자동 변환 미구현. 실제 source/사건/기간/고정 split·수용 정책 승인과 업무별 모델 비교가 필요하다. |

## 실제 자료 확인과 운영 수치

[원천 사실 재확인](26_SOURCE_FACT_RESOLUTION.md)에 근거 SHA·locator와 확인 가능한 범위를 기록한다. 기존 검토 분모는 66,190 channel-month grain, 미확정18,502개 항목, 미연결 사건 후보40개, 기간 충돌1건/152 scope다. 담당 승인 기록은 없다. 삭제된 D:\share의 원본을 현재 보존 원본으로 표시하지 않는다.

10/8 확인의 source packet/decision/binding·ApprovalHistory·DatasetRegistry·ModelRegistry·RetrainingHistory는 각각0이다. 기존 canonical worker는 빈 큐에서 대기하며 operational model0, readiness BLOCKED, serving NO_ACTIVE_LOCAL_MODEL이다. 72개 key는 REPRESENTATION_BASELINE_SCOPE_PARTIAL이며 6종 표현/3종 업무 기준선의 연결을 72개 실제 운영 모델 완료로 해석하지 않는다.

최신 코드 웹은 공개 작업본에서 별도 loopback backend8010/frontend5174로 실행한다. 기존 canonical8000/5173·문서 Chroma8001·worker는 유지한다. 최신 웹의 health/readiness와 readonly API 확인은 [기계 판독 상태](current_status.json)에 기록한다. 계정은 미설정이며 protected session/승인은503으로 차단되는 것이 현재 의도된 상태다.

## 검증과 스키마

[10/8 감사](10_IMPLEMENTATION_AUDIT.md)와 [current_status.json](current_status.json)에 최종 전체 backend 회귀, frontend clean install/build, PostgreSQL session 재개·변조/중복 차단 확인을 기록한다. SQLite는 격리 시험·기존 로컬 큐에만 사용하며 업무 원장과 새 workflow는 PostgreSQL이다. 실제 업무 schema에는 검증된 nullable QC evidence3열과 빈 workflow2테이블만 additive 적용한다. 계정·source 승인·dataset·모델 적재는 수행하지 않는다.

## 남은 실행 순서

1. 실제 보존 문서·원천에서 historical 의미/단위/배율/기준면·clock·QC codebook/기간·sensor episode를 보완하고 사건40후보/기간1충돌의 기술 판정을 정리한다.
2. 실제 업무 수행 시 operator/reviewer 계정을 설정하고 exact source packet을 승인한다. 현재 계정 부재는 기술 분석을 중단하는 이유가 아니다.
3. 승인 ingest/binding과 사건·라벨·Feature 계보를 검토하고 source 의존성을 v2 snapshot에 동결한다. 고정 train/validation/test·평가·운영 수용 기준을 승인한다.
4. 실제 업무별 비교 adapter와 worker를 실행해 독립 검토 후 registry·배포·serving·rollback을 검증한다. 임의 가중치 등록 또는 synthetic 성능으로 registry0을 해소하지 않는다.

[설치](02_SETUP_AND_INSTALLATION.md), [API](04_API_SPECIFICATION.md), [QC](12_QC_RULE_RESULT_LAYER.md), [AI](25_ANOMALY_AI.md), [승인](17_HUMAN_IN_THE_LOOP.md), [Dataset](18_DATASET_REGISTRY.md), [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md)를 따른다.

최종 검증: 2026-10-08 backend **512 passed / 1 skipped**(46.36초), frontend TypeScript/Vite build PASS. 실제 PostgreSQL 임시 schema의 migration·session 재개·입력 변경 차단 PASS와 최신 backend8010의 QC/AI→Fusion 읽기 전용 HTTP 연결을 확인했다. 실제 source fit·model registry·배포는0이다.
