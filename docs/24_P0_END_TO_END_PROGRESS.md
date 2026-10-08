# P0 엔드투엔드 진행 현황과 다음 단계

현행화: 2026-10-08 · 요구사항: [process.md](../process.md)

## 현재 판정

승인 원천 → Dataset snapshot v2 → 고정 비교 → 독립 검토 → Registry → local serving의 코드 경로와 격리 시험은 준비되어 있다. 실제 승인 원천·Dataset·학습 이력·등록 모델·운영 모델은 0이므로 P0 전체 운영 완료로 판정하지 않는다. worker가 실행 중인 것과 학습 입력이 승인되어 모델 비교가 완료된 것은 별개다.

## 오늘의 읽기 전용 확인

운영 DB 확인 시각은 **2026-10-08 04:09:54 UTC / 13:09:54 KST**다. canonical PostgreSQL에서 `transaction_read_only=on`으로 조회했다.

| 실제 DB/설정 항목 | 확인 결과 |
|---|---|
| source 계약 packet·decision·관측 binding | 각각 0건 |
| ApprovalHistory | 0건 |
| DatasetRegistry | 0건 |
| ModelRegistry·RetrainingHistory | 각각 0건 |
| EventRegistry·EventEvidence·SensorAlias | 각각 0건 |
| API identities | 0개: 승인·등록 등의 보호된 작업을 수행할 담당 인증이 미설정 |
| runtime 설정 | DATA_MODE=live, MDC_SYNC_ENABLED=false, AUTO_CREATE_TABLES=false |
| MDC sensor catalog | `mdc_sensor_catalog` 테이블 없음: 운영 migration·수집 완료 아님 |
| backend / frontend | localhost backend health HTTP 200, frontend HTTP 200 |

runtime GET 확인 시각은 **2026-10-08 04:10:55.581022 UTC / 13:10:55 KST**다.

| runtime 확인 | 결과 |
|---|---|
| `/api/mlops/readiness` | HTTP 200, `status=BLOCKED`, `operational_model_count=0` |
| worker | configured=true, running=true, status=RUNNING, heartbeat 약 4초 전 |
| `/api/mlops/training/jobs` | queue_initialized=true, jobs=[] |
| 승인 입력 / 수용 기준 | approved_input_ready=false / acceptance_criteria_status=NOT_DEFINED |
| serving 설정 / 실제 모델 | configured=true / live_local_model_count=0 |
| `/api/mlops/serving/health` | HTTP 409, `NO_ACTIVE_LOCAL_MODEL` |
| `/api/mlops/adapters` | 72 keys, 6 representation implementations, 3 task algorithms, operational_completion=false |

이 프로세스는 기존 canonical 작업본의 worker이며 공개 Git tree를 이미 기동했다는 뜻이 아니다. 코드 fingerprint는 `bb62170c7d6ac03d102838f718f83b5ddb6f0e0e6f288534cf093a0aa4a90157`이었다. 비어 있는 큐에서 승인 작업을 기다리고 있으며 실제 학습은 실행되지 않았다. 프로세스 상태는 위 확인 시점의 결과이므로 이후 운영 점검에서 heartbeat와 identity를 다시 조회해야 한다.

## 구현·시험·실원천·운영 승인의 분리

| 단계 | 코드·격리 시험으로 확인한 내용 | 실제 운영의 남은 조건 |
|---|---|---|
| 원천 계약 | 실제 파일/행·식별자 literal·단위 변환·시각·QC·센서 구간·typed component 근거와 최신 승인 SHA 재검증 | 의미·단위·QC 코드북·기간·가용 시각을 담당자가 확정하고 실제 actor로 승인해야 한다. |
| 원천 ingest / Dataset | 승인 원천 binding, v2 의존성 동결, 정확한 membership, 분할·Feature as-of 검증 | 실제 승인 source ingest와 사건·라벨·Feature 연결, 고정 Dataset/정책 승인이 필요하다. |
| 고정 비교 | 동일 holdout의 자료형별 기준선·후보와 train-only 전처리, 평가·수용 계약 | 승인 원천에서 실제 업무별 비교를 실행하고 정책 초안을 승인해야 한다. |
| worker / Registry | 멱등 큐·fenced lease·heartbeat·quarantine, 독립 재현 검토, 후보 provenance | worker 프로세스는 실행 중이나 승인 job·학습·모델 등록은 0이다. |
| 배포 / rollback | 실제 수치 JSON 예측·identity 검사, 철회/변조 차단·commit 실패 복원·승인 rollback | 실제 배포 승인과 모델이 없으며 전체 API 지연·throughput·비용의 운영 검증도 남아 있다. |
| UI / agent | lake 검토 화면, 구현/프로세스/승인/모델 상태 분리, 개별 검토 bundle | 기존 다중 agent workflow는 데모 분석 경로다. PENDING marker 후 실행이 계속되며 live에서는 차단된다. |

72업무의 상태는 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이다. 6종 자료형 adapter와 3개 과업 알고리즘을 각 key에 연결했으나 72개 승인 운영 모델을 학습·선정한 것이 아니다. HF total은 명시 grid-cell UV, profile은 승인 단일 target/unit·고정 bin, trajectory는 명시 position endpoint의 기준선 범위다. 전체 공간장·혼합 항목·업무 고유 예측 대상과 성능은 추가 계약·실평가가 필요하다.

## 2026-10-07 원천 검토에서 남은 근거

- AIR_PRES 실제 500행은 literal·Parquet hash·행 값 일치를 확인했다. 의미·단위·QC·수신 시각 정책·기간 등 readiness 검증 **18,502개 항목**이 미확정이며 승인된 학습 자료가 아니다.
- 공통 의미 식별자·기간·사건 검토의 **66,190 channel-month scope** 정산은 기술적 검토 원장 범위다. 전수 운영 승인을 뜻하지 않는다.
- **미연결 보고서 사건 후보 40행**, **시설 기간 충돌 1건에 연결된 152 scope**는 검토 자료의 현황이며 해결 승인이 없다. 40행을 DB EventRegistry 적재 수로 표시하지 않는다.
- 과거 DB의 MDC_SIMULATED 관측은 실제 원천으로 승격하지 않았다. 실제 승인 원천과 혼합해 학습 완료 수를 만들지 않는다.
- 삭제된 원본 CSV는 현재 보존 원본으로 표시할 수 없다. 기존 변환 manifest와 실제 Parquet 해시를 근거로 사용할 때도 원본 소실과 변환 자료만 사용하는 정책을 명시해 담당 검토를 받아야 한다.

## 실제로 진행해야 할 순서

1. 운영 담당자가 실제 operator/reviewer identity와 권한을 설정한다. agent가 HUMAN 승인 이력이나 담당 인증을 임의 생성하지 않는다.
2. 원문·Parquet·문서 근거를 검토하여 식별자·단위/기준면·시간대/수신 시각·QC 시행기간·물리 센서와 사건 연결을 확정하고 원천 계약을 승인한다.
3. approved source를 ingest하고 사건·라벨·Feature의 내용과 가용 시각을 검토한다. 원천 QC 존재와 규칙 재검사·AI 점수·최종 담당 QC를 구분한다.
4. 평가 목표에 맞는 고정 train/validation/test와 평가·수용 정책을 검토한다. exact membership·기간·hash와 의존성이 동결된 v2 Dataset을 승인한다.
5. 실제 입력 preflight가 통과한 job을 enqueue하여 기준선·후보를 동일 holdout에서 비교한다. 최종 test tuning이나 임의 split은 허용하지 않는다.
6. 정확한 report/artifact를 독립 재현·검토한 뒤 후보를 등록한다. 실제 모델 선정 기준과 미지원 업무 범위를 확인한다.
7. 배포 identity를 승인하고 loopback에서 실제 health·prediction을 확인한다. 전체 운영 지연·비용·오류와 승인 rollback을 검증한 후 확장한다.

원천 승인·고정 Dataset·수용 기준이 없는 현재 단계에서는 preflight와 review packet의 blocker를 해소하는 일이 선행된다. Registry 0을 줄이기 위한 임의 가중치 등록이나 합성 성능을 실제 비교 결과로 사용하지 않는다.

## 검증 기록과 재현 범위

2026-10-08 공개 작업본 검증은 **backend 전체 345 passed / 1 skipped**, 깨끗한 `npm ci --ignore-scripts`와 TypeScript/Vite production build 통과다. 2026-10-07 canonical 작업본의 통합 176개 시험 및 6종 독립 수치 계산 통과와 구분한다. fixture 시험은 실제 원천 학습·운영 승인 증거가 아니다.

backend에서 별도 임시 MLOps·문서 루트를 지정하고 `python -B -m pytest tests -q -p no:cacheprovider`로 재현한다. [conftest](../ocean-ai-platform/backend/tests/conftest.py)는 SQLite와 자동 MDC 동기화·DDL 비활성화를 사용한다. 테스트를 운영 PostgreSQL에 연결하지 않는다. frontend는 lock을 사용해 설치한 뒤 `npm run build`한다. 설치와 로컬 자료 연결은 [02](02_SETUP_AND_INSTALLATION.md)를 따른다.

공개 정리에 따른 provenance·줄바꿈·기본 설정 차이로 canonical과 공개 코드 fingerprint는 다를 수 있다. 기존 영수증을 새 코드에 재사용하지 말고 새 fingerprint와 실제 승인 입력으로 다시 비교·검토한다. 이 문서 현행화에서는 운영 DB·설정·source packet을 변경하지 않았다.

세부 경로: [승인](17_HUMAN_IN_THE_LOOP.md), [Dataset](18_DATASET_REGISTRY.md), [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md), [AI Insights](20_AI_INSIGHTS.md), [agent 범위](21_MULTI_AGENT_WORKFLOW.md), [프런트엔드](22_FRONTEND_OPERATIONS_AUDIT.md), [요구사항 대응](23_PROCESS_ALIGNMENT.md), [상세 릴리스](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md).
