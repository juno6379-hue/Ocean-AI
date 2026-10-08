# 승인 원천 계약과 모델 실행 연결 — 2026-10-08 게시

현행 설치·API·운영 상태는 [루트 문서 안내](../../docs/README.md)를 기준으로 확인한다.
2026-10-08 읽기 전용 확인에서 기존 canonical worker는 실행 중이고 큐는 비어 있으며,
실제 원천 계약·승인·dataset·학습 이력·registry·운영 모델은 모두 0이다.
API identities도 0이고 운영 수용 기준은 `NOT_DEFINED`, serving은 `409 NO_ACTIVE_LOCAL_MODEL`이다.

이 변경은 검증된 원천 계약을 dataset snapshot과 모델 비교·배포 근거로 이어 준다.
원천의 의미·단위·시간대·QC·센서 유효기간이나 실제 운영 승인을 만들어 내지는 않는다.

## 구현

- 실제 actor와 reviewer 역할을 확인하는 원천 계약 요청·판정·불변 영수증 API.
- 원문/Parquet 해시, 행·열 locator, 단위/배율/기준면, 시간대/DST, 물리 센서·QC 시행기간 재검증.
- 벡터·방향·profile·trajectory 구성 성분마다 원문 QC·수신 시각·센서 구간·깊이 대응 검증.
- 승인 계약에서 멱등 ingest 및 관측 binding을 만들고 v2 snapshot에 source/split/evaluation/acceptance 의존성 동결.
- feature의 실제 원천 가용 시각과 QC 가용 시각을 선언 시각 및 origin과 비교하는 누출 차단.
- 기존 v1 snapshot은 원천 의존성 동결 없이 승인할 수 없다. 실제 legacy 자동 전환은 수행하지 않았다.
- 고정 train/validation/test와 hash에 결합된 평가·수용 계약, fenced SQLite 큐·worker·재시도·격리.
- 독립 재현 검토 후 candidate 등록, 실제 수치 JSON loopback serving, 승인 취소·코드 변경 차단, 실패 복원·승인 rollback.
- 화면에서 코드 구현·프로세스 실행·승인 입력·실제 운영 모델 수를 구분한다.

## 검증과 운영 범위

2026-10-07의 canonical D 작업본에서 통합 시험 176개, 프런트엔드 빌드,
6종 자료형의 독립 수치 계산 및 실제 HTTP/process heartbeat/creation-token 검증이 통과했다.
검증 당시 worker는 IDLE이고 실제 승인·학습·모델 등록·운영 모델·배포는 모두 0이다.
실제 원천 500행은 원문/Parquet 일치가 확인됐지만 의미·단위·QC·기간 등 18,502개 검증 항목이 미확정이다.
운영 DB에 있던 SIMULATED 자료는 실제 원천으로 승격하지 않았다.

72개 업무 키는 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이다. 자료형 6종과 업무 알고리즘 3종을 연결했으며,
이는 72개 승인 운영 모델 또는 전체 공간장·profile·trajectory의 업무 적합성 완료가 아니다.
HF total은 명시된 grid cell의 vector 기준선, profile은 승인된 단일 target/unit·고정 bin,
trajectory는 명시된 position endpoint 기준선이다. 업무 고유 adapter와 실제 원천의 실평가가 남아 있다.
수치 호출의 p95와 실제 전체 API p95는 별개이고 후자는 운영 평가가 필요하다.

이번 공개 복사본은 고정 credential을 예제값으로 바꾸고 로컬 개인 경로를 추상화했다.
2026-10-08 공개 복사본 검증은 전체 backend 시험 345개 통과·1개 skip,
깨끗한 `npm ci --ignore-scripts`와 TypeScript/Vite production build 통과다.
재현 가능한 설치를 위해 누락된 frontend transitive dependency lock 항목도 정리했다.
scope matrix의 72개 업무 행은 그대로이며 provenance 경로만 정리했다.
줄바꿈·provenance·설정 기본값의 공개 정리로 execution fingerprint는 canonical 검증본과 달라질 수 있다.
기존 학습 영수증을 새 코드의 승인 근거로 재사용하지 말고 새 fingerprint로 다시 비교·검토해야 한다.
공개 복사본 자체의 시험 결과는 커밋 설명의 검증 기록과 [현행 상태 요약](../../docs/current_status.json)을 확인한다.

## 로컬 자료와 설정

Git에는 `.env`, 실제 담당자 token, 원문/Parquet, DB·Chroma, 실제 source packet·승인 영수증,
dataset snapshot·model artifact, 검토 묶음·로그를 포함하지 않는다. clone만으로 운영 자료가 생성되지 않는다.
환경변수와 보존된 로컬 자료를 연결하고 해당 원천의 실제 담당 승인을 확보해야 한다.

`backend/.env.example`에서 Compose용 `POSTGRES_PASSWORD` 항목을 제외한 서버 설정만 별도 backend `.env`로 준비한다.
현재 `Settings`에는 `POSTGRES_PASSWORD` 필드가 없어 예제 전체를 복사하면 `extra_forbidden` 오류가 발생한다.
DATABASE_URL 및 실제 reviewer/operator identities를 설정하는 명령은 [현행 설치 문서](../../docs/02_SETUP_AND_INSTALLATION.md)를 따른다.
예제 `change-me`는 실제 비밀번호가 아니다. Docker의 POSTGRES_PASSWORD는 shell 또는 Compose용 별도 환경에 지정한다.
MDC_DSN/MDC_USER/MDC_PWD는 비어 있고 자동 수집과 자동 전체 DDL은 기본 꺼져 있다.
토큰과 인증 정보는 Git이나 frontend env에 넣지 않는다.

현재 workstation 기본 경로는 `D:/AI_Observation` 원천/검토 루트이고 문서 실행기는 기존 C 문서 데이터의
contract를 요구한다. source authority·technical-review의 지정 루트와 기존 문서 contract가 필요하다.
문서 데이터는 `OCEAN_APP_DATA_DIR`/`DOCUMENT_PIPELINE_DIR` 또는 launcher의 DocumentDataRoot로 지정한다.
레이크는 INTEGRATED_LAKE_ROOT/SHARE_MONTHLY_LAKE_ROOT, snapshot은 DATASET_SNAPSHOT_DIR,
MLOps 상태는 OCEAN_MLOPS_ROOT로 지정한다. 지정 경로에 임의의 승인 영수증을 만들어 대체하지 않는다.
기존 자료의 원본 삭제나 경로 cutover는 이 커밋의 작업이 아니다.

## 검증과 실제 실행 순서

백엔드 의존성은 `backend/requirements.txt`, 프런트엔드는 package lock을 사용한다.
backend에서 `python -B -m pytest tests -q -p no:cacheprovider`를 실행한다.
conftest는 SQLite와 자동 동기화/DDL 비활성화를 사용한다. 별도 임시 MLOps·문서 루트를 지정한다.
frontend에서 `npm ci --ignore-scripts` 후 `npm run build`로 확인한다.

실제 실행은 인증된 source 판정 → approved source ingest → 고정 프로토콜과 snapshot 승인 →
training enqueue → worker 실행 → 독립 재현·검토 → registry → 배포 identity 승인 → loopback pilot 순서다.
승인 값이 없는 source packet이나 검토 초안을 바로 학습 또는 배포에 사용하지 않는다.
원천/QC/센서 기간 또는 feature as-of가 바뀌면 snapshot과 모델 근거를 다시 검증한다.
