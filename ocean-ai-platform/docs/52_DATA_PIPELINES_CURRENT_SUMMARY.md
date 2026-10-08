# 정형·비정형 자료 처리 현황 요약

작성일: 2026-10-02. 기준: 로컬 파일 목록, 활성 PostgreSQL 실측, Chroma 저장소와 실행 중인 문서 배치. 수치는 확인 시점의 스냅샷이며 배치 진행에 따라 달라진다.

## 1. 현재 결론

- 정형자료는 원시·표준화 관측 일부를 PostgreSQL에 저장했고, 과거 자료의 Parquet 산출물이 있다. 전체 관측항목에 대한 변환 정확성·결측 판정·중복 검증 및 후속 학습 계보 연결은 미완료다.
- 비정형자료는 전체 로컬 파일 목록을 등록하고, 요청한 보고서 유형의 의미 기반 재청킹·임베딩을 실행 중이다. 기존 178개 PDF의 1,786개 임베딩은 보존하고 새 버전 컬렉션에 원문을 재처리한다.
- 두 자료군의 `station_id + sensor_id + time + event_id` 연결은 목표 구조다. 실제 사건·QC·승인 라벨·Feature·Dataset까지 연결한 운영 완료 상태는 아니다.

## 2. 자료 범위

| 로컬 대분류 | 파일 수 | 용도 |
|---|---:|---|
| 정형데이터 | 581 | 월별 관측 CSV, 기준정보, DB 정의 등 |
| 비정형데이터 | 25,498 | 업무 보고서, 간행물, 표·그림, 혼합 형식 자료 |
| 소스코드 | 2,326 | 수집된 기존 시스템 소스·실행물; 보존 대상 |
| 요청자료 | 43,551 | 납품·요청 차수별 혼합 원본 |
| 보관 | 1 | 구버전 자료 |
| 합계 | 71,957 | `C:\AI_Observation\ocean-ai-platform\분류` 실측 |

Google Drive의 `05.자료 수집`은 정형·비정형·소스 구조를 확인했다. Drive 전체 파일과 로컬의 누락·중복 대조 및 Drive 전용 수집 배치는 이번 로컬 임베딩 실행에 포함하지 않았다. 따라서 로컬 완료율을 Drive 완료율로 표시하지 않는다.

## 3. 정형자료

목표 흐름:

```text
Raw CSV → Schema Profiling → Standardized Observation → QC Rule Result
        → Operation/Event Link → 검토·승인 AI Label → Feature Store → Dataset Registry
```

| 단계 | 실제 저장 상태 | 현재 판단 |
|---|---:|---|
| ObservationRaw | 13,621행 | 일부 실자료 적재 |
| ObservationStandard | 4,074행 | MDC 동기화의 항목·단위 표준화 일부 적용 |
| QCRuleDefinition | 2행 | 규칙 정의 존재 |
| QCRuleResult | 0행 | 개별 검사 API는 있으나 실제 검사 결과 없음 |
| OperationLog / EventRegistry | 각각 0행 | 운영 사건 연결 미완료 |
| AILabel | 0행 | QC Flag와 모델은 분리됐으나 실제 승인 라벨 없음 |
| FeatureDefinition / FeatureValue | 9행 / 0행 | 정의 및 계산 코드 일부 존재, Feature 값 적재 미완료 |
| DatasetRegistry | 0행 | 등록 API 존재, 실제 데이터셋 등록·계보 연결 미완료 |
| DataLakeStat | 1행 | 기존 TIDE manifest 집계 적재; 전체 품질 검증 통계는 아님 |

### 과거 Parquet

별도 원본 `E:\백업\data\old\spool(2001_2021)`의 기존 점검 기록:

- 산출 경로: `C:\AI_Observation\data_lake\spool_2001_2021`
- manifest 입력 360,133개, Parquet 파일 93,649개, 약 37.94GB.
- manifest 행 수 합계 3,595,161,514건, 연도 파티션 2000~2022, 변수 집계 TIDE.
- 이 수치는 기존 변환 로그와 파일 집계다. 고유하고 유효한 관측 건수나 모든 관측항목의 처리 완료를 보증하지 않는다.
- `-999`가 최솟값에 포함되지만 결측 집계는 0이었던 문제, 고정폭 파서의 TIDE 고정 분류, 0행 파일도 CONVERTED로 기록하는 문제를 재검증해야 한다.
- Parquet 정규화 출력에 sensor_id가 보존되지 않는 경로가 있어 장비·사건 연결을 보강해야 한다.

전체 학습에 앞서 원본 형식·항목 inventory → 전용 파서 검증 → 결측·중복·코드 검사 → 재현 가능한 표준 관측과 품질 통계 순으로 확정한다.

## 4. 비정형자료

목표 흐름:

```text
Report → Parser → Metadata Extraction → Semantic Chunk → Embedding → Vector DB
                                                               ↘ DocumentIndex
```

### 이번 적용 내용

| 단계 | 구현·실행 내용 |
|---|---|
| 목록과 범위 | 71,957개 파일 목록 등록. 요청 자료군이며 지원 형식인 파일 4,955개를 처리 대상으로 집계 |
| 대상 자료군 | 품질관리 가이드북, 일일상황·현황보고, 일일점검, 품질처리·수집률, 주간조위편차, 대조기 모니터링 |
| Parser | PDF, TXT, HWP, HWPX, XLSX, XLS, DOCX 지원. 페이지·시트·행 위치 보존 |
| Metadata | 원문/파일명의 날짜, 문서 유형, 관측소 후보, 변수 후보와 확인 가능한 센서를 기록. 불명확한 항목은 미확정으로 보존 |
| Semantic Chunk | 절·제목·관측소 이슈·표 행 경계 사용. 긴 블록은 문장·줄·표 셀 경계로 나누며 고정 토큰 슬라이딩 윈도우는 사용하지 않음 |
| Embedding | 로컬 Ollama `mxbai-embed-large:latest`, 1,024차원. 모델 digest·파서·청킹 버전으로 컬렉션을 구분 |
| Vector DB / SQL | 동일 chunk_id를 벡터 ID와 DocumentIndex.embedding_id에 기록. 문서의 벡터 저장이 끝난 후 관계형 색인 공개 |
| 중복·재개 | 같은 내용·유형의 사본은 대표 색인에 연결. 체크섬과 처리 상태를 기록하며 중단 후 재실행 가능 |
| 검색 | Hybrid Retrieval과 챗봇이 같은 컬렉션·모델 계약을 사용. 문서명·보고일·절·페이지·청크·유사도 제공 |
| 오류 | 암호 PDF, OCR 필요, 파싱·임베딩·DB 실패를 파일별로 기록. 실패를 완료 건수에 포함하지 않음 |

### 완료율 해석

- `success_percent = (성공 파일 + 내용 동일 사본) / 지원 형식의 대상 파일`.
- `eligible_processed_percent`는 대상 중 성공·중복·실패로 판정된 비율이다. 실패를 포함하므로 성공률과 다르다.
- `accounted_percent`는 전체 파일 중 대상 외 제외까지 판정한 비율이다. 임베딩 성공률이 아니다.
- 제외 67,002개 중 대부분은 이번 요청 자료군에 속하지 않는 파일이고, 나머지는 Office 임시 잠금 파일 18개와 ZIP·이미지 등 현재 문서 배치가 직접 처리하지 않는 형식이다. 제외 사유는 개별 목록에 보존한다.
- PDF가 아닌 자료에는 물리 페이지가 없을 수 있어 page는 null이며 시트·행·문단 위치를 별도 제공한다. 원문에서 날짜를 확정할 수 없으면 현재 날짜로 대체하지 않는다.

현재 진행 수치는 `GET /api/rag/ingestion/status`, 파일별 결과는 `GET /api/rag/ingestion/files?status=FAILED`에서 확인한다. 배치 실행 중이므로 문서 전체 임베딩 완료로 보고하지 않는다.

실제 검색 검증에서는 활성 버전 DocumentIndex 2,512개와 같은 ID의 벡터 2,512개를 대조해 누락 0개를 확인했다. 7개 보고서 유형의 문서명·날짜·절·페이지·청크·유사도와 원문 연결 검증을 통과했다. 이는 처리된 자료의 검색 연결 검증이며, 대상 4,955개 전체 처리 완료나 전문가의 검색 관련성 평가를 뜻하지 않는다. 상세 시점별 집계는 `54_DOCUMENT_PIPELINE_VERIFICATION.json`에 기록한다.

검증 후 진행 스냅샷: 성공 31개, 내용 동일 사본 9개, 실패 5개, 처리 중 1개, 대기 4,909개다. 대상 대비 성공률은 0.81%이고 공개된 청크는 3,600개다. 서버와 변환 배치는 백그라운드에서 실행 중이며, 이후 집계는 API·원장을 기준으로 확인한다.

## 5. 두 자료군 연결의 남은 작업

1. 관측소·센서·변수 기준정보를 공유하고 문서의 장비 표현과 실제 센서 코드를 매칭한다.
2. 보고일과 사건 발생기간을 분리하며, 관측 UTC 시각과 사건 기간의 겹침 규칙을 정의한다.
3. EventRegistry를 중심으로 문서 청크·Observation·QC 결과·OperationLog의 다대다 근거 관계를 저장한다.
4. QC 결과와 문서·운영 근거로 AILabel 검토 후보를 만들고 승인 이력을 남긴다. QC Flag를 자동 확정 학습 라벨로 사용하지 않는다.
5. 승인 라벨과 버전별 Feature 값을 실제 Dataset snapshot에 포함해 원문까지 추적하고 시간·관측소 누수를 검증한다.
6. 실사건 한 건을 문서 → 사건 → 관측 → QC → 승인 라벨 → Feature → Dataset으로 양방향 검증한 후 확대한다.

## 6. 한글 주석 적용

2026-10-02 후속 반영: 위 연결 과제 1~5의 저장 구조·API·검증 로직을 추가했고, 6번 전체 흐름은 격리 E2E에서 통과했다. 실사건은 센서 기준정보·사건기간·관측 근거·승인 담당자 설정이 부족해 아직 완료되지 않았다. 상세 구현·오류·실측 결과는 `55_EVENT_EVIDENCE_IMPLEMENTATION.md`와 `55_EVENT_EVIDENCE_LIVE_CHECK.json`을 참조한다.

개발 대상인 `backend/app`, `backend/scripts`, `backend/tests`, `frontend/src` 및 프로젝트 진입·설정 스크립트에 파일 역할 한글 주석을 적용했다. 적용 경로와 누락 여부는 `53_KOREAN_SOURCE_COMMENT_COVERAGE.json`에 기록한다.

이번 점검 대상은 134개 소스 파일이며 파일 역할 한글 주석 누락은 0개다. 파일 설명과 핵심 처리 주석을 보강한 것으로, 기존 모든 영문 주석을 번역하거나 코드의 모든 줄에 주석을 붙였다는 의미는 아니다. 회귀 테스트 23개와 프런트엔드 빌드를 통과했다.

수집 원본인 `분류/소스코드`, 외부 라이브러리, 빌드 산출물, 관측·문서 원본은 수정하지 않는다. 파일 설명 주석의 존재가 각 기능의 구현 완료를 뜻하지 않으며, 빈 구현은 확장용 소스로 표시한다.

## 근거 문서

- 49_LOCAL_DRIVE_CLASSIFICATION_AUDIT_20261001.md: 로컬·Drive 분류 범위.
- 50_EMBEDDING_STATUS_AUDIT_20261002.md: 변경 전 임베딩 저장 상태.
- 51_DUAL_PIPELINE_LINKAGE_AUDIT_20261002.md: 두 파이프라인 연결의 미완료 지점.
- 54_DOCUMENT_EMBEDDING_EXECUTION.md: 이번 변경의 실행·검증 결과와 오류 기록.
