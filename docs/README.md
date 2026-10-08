# Ocean-AI 현행 문서 안내

기준일: **2026-10-08**. 이 폴더의 01~29 문서는 10/8 QC·AI·Fusion·승인 gate 확장과 7월 현황·월간보고서 대조를 반영한다. 구현 검증과 실제 운영 승인을 구분한다. 기계 판독용 확인 결과는 [current_status.json](current_status.json)이다.

## 현재 확인 결과

2026-10-08 운영 PostgreSQL을 읽기 전용으로 확인했고, 백엔드 health/readiness와 프런트엔드 HTTP 응답은 정상이다. 기존 canonical 작업본의 학습 worker는 실행 중이며 큐는 비어 있다. **원천 계약·판정·관측 binding·승인 기록·dataset·학습 이력·model registry는 모두 0건**이고, 실제 운영 모델도 0개다. 실제 계정은 사용자 지시로 업무 수행 시점에 설정한다(DEFERRED_BY_USER). 현재 readonly 기술 분석은 가능하고 실제 승인 쓰기는 차단한다. 운영 `mdc_sensor_catalog` 테이블은 아직 적용되지 않았다.

`/api/mlops/readiness`는 `BLOCKED`, 수용 기준 상태는 `NOT_DEFINED`, `/api/mlops/serving/health`는 `409 NO_ACTIVE_LOCAL_MODEL`이다. 프로세스 실행과 자료형 기준선 구현을 업무별 모델의 운영 완료로 해석하지 않는다. 72개 업무 키는 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이며, 구현 범위는 6종 자료형과 3종 업무 알고리즘의 기준선이다.

문서 수집 상태는 2026-10-08 조회에서 eligible 4,958개 중 성공 1,603개·중복 1,513개·대기 1,697개·실패 145개이고 최근 실행은 `PARTIAL`이다. 원문 수집 전체 완료나 모든 chunk의 vector 검색 품질 검증을 뜻하지 않는다. 분모와 상태별 해석은 [15](15_DOCUMENT_INDEX_INGESTION.md)를 확인한다.

최신 전체 backend 회귀·frontend build·PostgreSQL gate 검증 결과는 [10/8 감사](10_IMPLEMENTATION_AUDIT.md)와 [current_status.json](current_status.json)을 따른다. 이는 구현에 대한 검증이며 실원천 승인이나 운영 성능 수용 결과가 아니다. 현재 실행 중인 canonical 작업본과 공개 복사본은 설정·provenance·줄바꿈 정리 때문에 fingerprint가 다를 수 있다.

## 문서 목록

| 번호 | 문서 | 확인할 내용 |
|---|---|---|
| 01 | [시스템 아키텍처](01_SYSTEM_ARCHITECTURE.md) | 원천 계약부터 dataset·모델·serving까지의 실제 경계 |
| 02 | [설치 및 실행](02_SETUP_AND_INSTALLATION.md) | 환경변수, PostgreSQL, 문서 contract, 실행·검증 명령 |
| 03 | [에이전트 워크플로우](03_AGENT_WORKFLOW.md) | 초안·분석 agent와 승인 모델 실행의 구분 |
| 04 | [API 명세](04_API_SPECIFICATION.md) | 실제 경로, payload, 인증·차단 응답 |
| 05 | [MDC → PostgreSQL 이관](05_MDC_DB_POSTGRESQL_MIGRATION.md) | 명시적 스키마·원천 적재와 자동 동기화 조건 |
| 06 | [MDC 조회 매핑](06_MDC_QUERY_MAPPING.md) | 원천 항목·변수·의미 대응 |
| 07 | [중복 제거](07_MDC_DEDUPLICATION_MIGRATION.md) | unique key, 멱등성, 원천 해시 보존 |
| 08 | [관측소 코드 매핑](08_MDC_STATION_CODE_MAPPING.md) | 별칭과 물리 센서 유효기간의 차이 |
| 09 | [해역 매핑](09_MDC_SEA_AREA_MAPPING.md) | 분류용 해역과 승인 원천 scope |
| 10 | [구현 감사](10_IMPLEMENTATION_AUDIT.md) | 구현·시험·운영 상태별 검증 근거 |
| 11 | [표준 관측 계층](11_OBSERVATION_STANDARD_LAYER.md) | 원천 lineage, 단위·시간·QC·센서 계약 |
| 12 | [QC 규칙·결과](12_QC_RULE_RESULT_LAYER.md) | 원문 QC와 판본·시행기간별 계산 결과 |
| 13 | [AI 라벨 분리](13_AI_LABEL_SEPARATION.md) | 후보 라벨과 검토 승인 snapshot |
| 14 | [Feature 계층](14_FEATURE_STORE.md) | 원천 가용 시각과 as-of 누출 차단 |
| 15 | [문서 수집·색인](15_DOCUMENT_INDEX_INGESTION.md) | 문서 contract, 파싱·vector 성공·실패 상태 |
| 16 | [하이브리드 검색](16_HYBRID_RETRIEVAL.md) | 키워드·vector 결과 및 근거 점수의 의미 |
| 17 | [사람의 검토·승인](17_HUMAN_IN_THE_LOOP.md) | actor 권한, 판정 원장과 불변 영수증 |
| 18 | [Dataset registry](18_DATASET_REGISTRY.md) | v2 원천 의존성 동결과 고정 분할 |
| 19 | [모델 버전·평가](19_MLOPS_VERSION_AND_EVALUATION.md) | worker, 독립 재현, 선정·등록·배포·rollback |
| 20 | [AI Insights](20_AI_INSIGHTS.md) | 휴리스틱 분석의 구현 범위와 운영 모델의 차이 |
| 21 | [Multi-agent 실행](21_MULTI_AGENT_WORKFLOW.md) | Evidence Fusion·영속 stop/resume gate와 실행 경계 |
| 22 | [프런트엔드 운영 감사](22_FRONTEND_OPERATIONS_AUDIT.md) | 실 API, 인증, 미확정·오류·빈 상태 표시 |
| 23 | [업무 절차 대응](23_PROCESS_ALIGNMENT.md) | 원천 담당·사건 담당·업무 담당의 결정과 실행 순서 |
| 24 | [현재 단계와 다음 작업](24_P0_END_TO_END_PROGRESS.md) | 미확정 원천·승인·업무별 모델 운영의 완료 조건 |
| 25 | [이상탐지 AI](25_ANOMALY_AI.md) | fixed fit/calibration·6모드·actual source 미평가 |
| 26 | [원천 사실 재확인](26_SOURCE_FACT_RESOLUTION.md) | 확인된 근거와 historical 미확정 항목 |
| 27 | [7월 월간보고서·Parquet 대조](27_JULY_REPORT_PARQUET_MATCH.md) | 7월 기본 화면,146개 파일 검증,시설·항목 대응과 통계 차이 |
| 28 | [미산정 지표 보완](28_METRIC_COMPLETION.md) | 전수 시간격자·결측 표현·QC 코드·보고서 참조값·실제 요청 오류율과 산정 근거 |
| 29 | [단계별 실행·최종 검증](29_DEVELOPMENT_STAGE_EXECUTION.md) | 13단계·세 에이전트·부모 검증·실원천 실험과 미완료 조건 |
| 85 | [운영·문서 복구](85_OPERATIONS_RECOVERY_REVIEW.md) | backup·resume·dry-run 승격·보호된 rollback |

현황의 기본 관측기간은 **2026년7월 단일 월**이다. 보고서 국가망140개(공개120·제한20),선택 원천 보유코드,과거 누적 보유를 구분한다. 7월Parquet146개 전체hash·행정산은 통과했으나 월말 원천 부족,HF자료 미확인,2차QC통계 차이가 남았다. 판정은 [27](27_JULY_REPORT_PARQUET_MATCH.md)을 따른다.

## 10/8 확장과 실행 웹

12종 Rule QC, fitted 통계 이상탐지6모드,5종 Evidence Fusion과 PostgreSQL PENDING stop/resume을 구현했다. 실제 조건이 없으면 NOT_EVALUATED이며 score는 운영 확률이 아니다. 최신 개발 웹은 `http://127.0.0.1:5174`, backend는8010이다. 기존 canonical5173/8000과 worker는 유지한다. 현재 분석/조회는 가능하고 실제 계정 승인·물리 source fit·등록/운영 모델은0이다. 별도 원시 숫자 적합3개는 [29](29_DEVELOPMENT_STAGE_EXECUTION.md)에 기록했다.

## 운영 완료까지 필요한 순서

1. 원천 담당이 의미 식별자, 단위/배율/기준면, 시간대, QC 판본·시행기간, 물리 센서 설치/교체/철거 기간을 근거와 함께 확정한다.
2. 사건 담당이 미연결 사건과 기간 충돌, GR/시트/원천 코드의 적용 범위를 판정하고 실제 승인 기록을 남긴다.
3. 실제 reviewer/operator 인증을 설정하고 원천 계약을 판정한다. 승인된 원천 ingest·관측 binding을 만든 뒤 source 의존성을 v2 snapshot에 동결하고 고정 분할·평가·수용 계약을 승인한다.
4. 승인된 snapshot으로 업무별 비교·학습을 실행하고 독립 재현·검토 후 등록한다. 배포 identity 승인과 loopback pilot를 검증한다. 업무 고유 adapter와 전체 공간장/profile/trajectory의 실평가는 별도로 완료한다.

2026-10-07 검토 자료에는 66,190개 원천 단위, 직접 대조한 AIR_PRES 500행, 미확정 18,502개 항목, 미연결 사건 후보 40건, 152개 단위에 영향을 주는 기간 충돌 1건이 기록되어 있다. 이는 검토 준비 결과이며 담당 승인이 아니다. 실제 원문·Parquet·검토 패킷·영수증·DB·모델 산출물과 token은 로컬 보존 대상이다.

## 상세 구현 및 과거 기록

[승인 원천 계약과 모델 실행 연결](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)은 구현 세부 사항을 설명한다. [플랫폼 문서 폴더](../ocean-ai-platform/docs/)에는 날짜별 실행 기록과 과거 설계가 함께 보존되어 있다. 그 기록의 과거 완료율·건수·PID·경로를 현재 상태로 재사용하지 않는다. 현재 설치 절차는 이 폴더의 [02](02_SETUP_AND_INSTALLATION.md), API는 [04](04_API_SPECIFICATION.md), 운영 판정은 [24](24_P0_END_TO_END_PROGRESS.md)를 기준으로 확인한다.
