# 실행 복구 및 승인·데이터 신뢰성 보강

2026-09-29 현재 체크아웃에 적용했다. 기존 RAG/SQL Agent 미커밋 작업은 유지했다. 운영 DB, Oracle, 기존 관측자료를 수정하거나 서버를 재시작하지 않았다.

## 변경 사항

1. Layout의 손상된 문자열·JSX를 복구하고 Forecasting 화면을 라우트와 메뉴에 연결했다.
2. 프런트 API 주소를 `VITE_API_BASE_URL`로 통일했다. 기본 `/api`는 Vite 개발 프록시를 통해 `127.0.0.1:8000`으로 연결된다. 기존 8080 서버를 쓰려면 `frontend/.env.local`에 `API_PROXY_TARGET=http://127.0.0.1:8080`을 설정한다. 운영 정적 배포는 웹 서버에서 `/api`를 백엔드로 프록시하거나 빌드 전에 API URL을 지정한다.
3. 변경 요청에 서버 관리 담당자 토큰을 요구한다. 승인·반려·모델 승격·롤백·데이터셋 승인에는 reviewer/admin 역할이 필요하다. 요청 본문의 user_id는 승인자의 신원으로 신뢰하지 않는다. 토큰은 UI 메모리에만 보관하며 새로고침하면 다시 연결한다.
4. QC 반려는 기존 최종 플래그를 보존한다. 검토 완료 대상의 재승인·수정은 409로 거절하고 AI 라벨 중복 승인으로 재학습 풀에 중복 추가되는 것을 방지한다. 최종 플래그·배포 상태를 일반 수정 API로 변경할 수 없다.
5. 모델 승인 상태는 APPROVED이며 배포 상태 승격은 별도 요청이다. 미승인 모델의 승격을 차단했다. 모델 승격은 레지스트리 변경이며 실제 서빙 배포는 아직 연결되지 않았다. 재학습 worker 미구현 상태에서 QUEUED/COMPLETED를 허위로 반환하지 않는다.
6. MDC 수집에서 과거 관측시각의 8년 이동을 제거했다. 자동 수집은 기본 비활성화이며 원본 KST 시각과 UTC 변환만 보존한다. 하드코딩된 MDC 접속 정보를 서버 환경 설정으로 옮겼다. 기존에 이동 저장된 데이터는 자동 복원하지 않았다.
7. 무작위 QC Agent, 임의 AI 차트, 테스트 자동화, 고정 임계값 Multi-Agent 경로는 demo 모드에서만 허용한다. 장비 상태 API는 live 모드에서 임의 건강점수·가짜 티켓을 반환하지 않는다. 대시보드 성능·보고서 통계는 레지스트리 집계를 사용한다. 산정 근거가 없는 수집률은 null/미산정으로 표시한다. UI의 남은 정적 예시는 상단 검증용 안내로 구분한다.
8. `/api/qc/review-candidates`를 추가하여 실제 규칙 실행 결과를 승인 대기 항목으로 저장한다. 최종 플래그는 승인 전까지 null이다. 같은 관측의 중복 후보 생성을 방지한다.
9. 미검토 관측을 정상으로 집계하지 않는다. 데이터셋 해시는 관측값·검토된 QC·변환/전처리/특징/라벨 버전을 포함한다. 빌드 시 해시명 JSON 스냅샷을 보존하고 검증 이후 원천 변경 시 승인을 차단한다. 승인된 레지스트리의 재빌드는 거절한다. 스냅샷의 저장 위치는 `DATASET_SNAPSHOT_DIR`이다.
10. Parquet 변환은 기본 원본 시간대 Asia/Seoul을 UTC로 변환하며 원본 상대경로 해시를 파일명에 포함한다. 다른 폴더의 동일 파일명 충돌을 방지한다. 기존 레이크와 섞이지 않게 새 출력 폴더로 변환·검증해야 한다.
11. 벡터 검색은 `VECTOR_SEARCH_ENABLED=false`가 기본이며 SQL/키워드 근거 검색을 제공한다. 벡터 검색 상태를 응답에 포함하고 관련도 0 문서를 근거로 반환하지 않는다. 기존 임베딩 경로 통합과 재색인은 별도 작업이다.

## 로컬 실행 설정

`backend/.env`의 기존 DB 설정을 보존하고 다음 항목을 추가한다.

```dotenv
DATA_MODE=live
MDC_SYNC_ENABLED=false
AUTO_CREATE_TABLES=false
VECTOR_SEARCH_ENABLED=false
DATASET_SNAPSHOT_DIR=data/dataset_snapshots
API_IDENTITIES={}
```

`API_IDENTITIES`는 담당자 ID를 키로, `token`과 `role`을 값으로 갖는 JSON이다. 예시 구조:

```json
{"reviewer-id":{"token":"여기에-담당자별-고유한-랜덤-토큰","role":"reviewer"},"operator-id":{"token":"별도의-고유한-랜덤-토큰","role":"operator"}}
```

실제 토큰은 예시 문자열을 사용하지 않고 비밀 관리 절차로 생성·전달한다. 브라우저 빌드 환경변수에 토큰을 넣지 않는다. 서버를 재시작한 뒤 화면 상단의 담당자 연결에서 입력한다. 설정이 비어 있으면 변경 기능은 503, 잘못된 토큰은 401, 부족한 권한은 403으로 차단된다. 이는 내부 실증용 인증이며 조직 SSO·토큰 만료·발급/폐기 관리 UI는 아직 구현하지 않았다. 원격 배포에는 HTTPS가 필요하다.

MDC 연결이 필요할 때만 `MDC_DSN`, `MDC_USER`, `MDC_PWD`, 선택적 `ORACLE_CLIENT_LIB_DIR`를 설정하고 `MDC_SYNC_ENABLED=true`로 바꾼다. 현재 스케줄러는 API 프로세스 내부에 있으므로 수집 활성화 시 worker는 하나로 실행한다. 별도 수집 worker 분리는 후속 작업이다. 기존 코드에 있던 접속 자격증명은 저장소 이력에도 남을 수 있으므로 담당자가 교체해야 한다.

새 DB에 한해 `AUTO_CREATE_TABLES=true`로 초기 테이블을 만들 수 있다. 기존 DB 마이그레이션 대체 수단은 아니다. 이번 변경은 DB 컬럼 추가 없이 기존 모델을 사용한다. 기존 검증 데이터셋은 새 해시 기준으로 재빌드해야 한다. 기존 승인 데이터셋을 바꾸려면 새 버전을 등록한다.

## 검증

실행 결과: 프런트 TypeScript 및 Vite 프로덕션 빌드 통과, 회귀 테스트 22개 통과, backend/app Python 파일 문법 검사 통과. 기존 Pydantic/UTC 사용 경고와 Vite 큰 청크 경고는 남아 있다.

저장소 루트에서:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/tests/test_safety_workflow.py -q -p no:cacheprovider
```

`frontend`에서:

```powershell
npm run build
```

회귀 테스트는 SQLite 메모리 DB, 합성 관측자료, 임시 문서를 사용한다. Oracle·운영 PostgreSQL·Ollama에 접속하지 않는다. 테스트 산출물은 `backend/tests/.work` 또는 `OCEAN_TEST_WORKDIR`에 생성한다.

검증 범위: 무인증/권한 부족 차단, 반려값 보존, 중복 승인, 배포 승인 우회, 보고서 호환 승인 경로, 원본 시각 보존, demo 경로 차단, Raw→Standard→Rule QC→문서 근거→승인 후보→담당자 승인→AI Label→Retraining Pool→Dataset build/validate/approve, 스냅샷 해시와 변경 감지, 빈 DB 조회 8개, Parquet 시간대 및 파일 충돌.

## 남은 작업

- 운영 PostgreSQL의 동시 승인·잠금 검증, 기존 8년 이동 자료의 식별·복구 계획. 실제 네 항목의 DB 연계·학습 검증은 문서 47에 기록했다.
- RAG 임베더/컬렉션/DocumentIndex 통합과 실제 문서 재색인. 현재 벡터 기능은 기본 비활성화다.
- SQL 챗봇의 조건 추출·조회 상한·다운로드 제공 개선. 기존 사용자 작업을 이번 변경에서 수정하지 않았다.
- UI에 남은 정적 예시의 제거와 모든 오류/자료 없음 상태 정비. 브라우저 시각 검증은 수행하지 않았다.
- 인증을 조직 계정 체계로 통합하고 역할별 API 범위를 더 세분화한다. 현재 일반 변경은 operator 이상, 최종 검토는 reviewer 이상이다.
- 온라인 학습 worker 및 후보 모델 서빙 연결. 실제 모델 산출물·시간순 평가·기준선 비교는 문서 47에서 확인했다. 예측 API는 아직 마지막 관측값 유지 기준선이다.
- Vite 큰 청크 경고, 기존 Pydantic/UTC 사용 경고, 의존성 고정과 별도 수집 worker.

## 실제 자료 검증 후속 결과

Oracle 조위·기압·풍속·수온, PostgreSQL 격리 적재, 기존 1,064만 행 Parquet 및 다변량 학습은 [실제 검증 보고서](47_LIVE_MDC_PARQUET_TRAINING_VERIFICATION.md)를 참조한다. 합성자료 단위 테스트와 실제 자료 실험 결과는 구분한다.
