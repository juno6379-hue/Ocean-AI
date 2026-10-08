# DocumentIndex 및 Embedding 구조

현행화: 2026-10-08

## 현행 구성

[semantic_ingestion](../ocean-ai-platform/backend/app/rag/semantic_ingestion.py)은 [document_pipeline](../ocean-ai-platform/backend/app/rag/document_pipeline.py)의 compatibility 진입점이다. 실제 수집기는 파일별 SQLite 실행 원장, PostgreSQL `DocumentIndex`, 전용 Chroma HTTP 서버 및 Ollama embedding 계약을 함께 사용한다. 이전 HuggingFace 고정 모델·embedding version `1.0` 설명을 현행 경로에 적용하지 않는다. `ingest_text()`는 원본 파일의 감사 근거가 없는 text-only 수집을 거부한다.

[DocumentIndex 모델](../ocean-ai-platform/backend/app/models/domain.py)은 문서·chunk ID, 유형/제목/날짜, section/page/text, station/sensor/variable 및 event 후보, embedding model/version, parser version, metadata JSON을 저장한다. 내부 surrogate ID와 문서/chunk ID는 역할이 다르며 `embedding_id=chunk_id`로 벡터와 관계형 행을 연결한다.

## 유형·파싱·메타데이터

[report_parser](../ocean-ai-platform/backend/app/rag/report_parser.py)가 인식하는 유형은 QUALITY_GUIDEBOOK, DAILY_SITUATION_REPORT, DAILY_INSPECTION_REPORT, QUALITY_PROCESSING_REPORT, QUALITY_COLLECTION_REPORT, WEEKLY_TIDE_RESIDUAL_REPORT, SPRING_TIDE_MONITORING_REPORT다. 지원 확장자는 PDF/TXT/HWP/HWPX/XLSX/XLS/DOCX이며, 유형 범위 밖이나 지원하지 않는 파일은 EXCLUDED 사유를 기록한다. 기존 원장의 다른 문서 유형이 현재 자동 classifier에 모두 포함되는 것은 아니다.

본문은 절·이슈·관측소·표 행과 문맥으로 나눈다. 실제 PDF 페이지와 비PDF locator를 보존하며 임의 page나 수집일을 보고일로 만들지 않는다. 보고일은 파일/상위 경로와 보고서 헤더에서 찾고 없으면 unresolved/null이다. 표 헤더와 병합 셀의 관측소 문맥, HWPX 중첩 문단 중복, PDF 제어문자 처리를 시험한다.

문서의 관측소 코드·이름·변수 단어는 **후보 추출**이다. 관측소나 변수 후보가 여러 개면 단일 관계 필드를 비워 둔다. `event_id`, period start/end는 자동 확정하지 않으며 `mapping_status`와 후보 목록을 남긴다. 검색 metadata가 실제 physical sensor·원천 기간·사건의 인간 승인을 대신하지 않는다.

## 불변 ID와 embedding 계약

| 식별자·계약 | 현재 규칙 |
|---|---|
| document ID | 문서 유형과 전체 파일 SHA-256의 hash |
| chunk ID | document ID + embedding version + chunk 순서 + text의 hash |
| embedding 계약 | provider, model/digest, dimension, cosine metric, parser/chunk version, query prefix |
| collection | 계약 hash로 만든 `embedding_version`과 `ocean_semantic_<version>` |

[document_contract](../ocean-ai-platform/backend/app/rag/document_contract.py)의 현재 parser는 `report-parser-2.2`, chunk는 `section-issue-table-2.1`이다. 모델은 `OLLAMA_EMBED_MODEL`을 사용하며 기본 `mxbai-embed-large:latest`다. 실제 `/api/tags` digest와 `/api/embed` 출력 차원을 확인하여 계약을 만든다. query에는 계약의 prefix를 사용하고 모델 digest·응답 개수/차원·Chroma collection의 embedding version/dimension이 맞지 않으면 실패한다. tag 이름만 같다고 같은 embedding으로 취급하지 않는다.

`OCEAN_APP_DATA_DIR`는 앱 자료 루트, `DOCUMENT_PIPELINE_DIR`는 계약·파일 원장 루트를 지정한다. `DOCUMENT_CHROMA_HOST/PORT/SSL`은 전용 서버 연결이며 API와 배치가 임의의 서로 다른 로컬 vector store를 열지 않는다. 실제 contract·DB·Chroma·원문은 Git에 포함되지 않는다.

## 재개·중복·공개 시점

유형과 내용 hash가 같은 사본은 active version의 성공한 문서 색인을 공유하고 DUPLICATE로 기록한다. embedding cache는 모델 digest와 text hash를 사용한다. 벡터는 chunk batch로 upsert하지만 문서 전체 벡터 처리 후 PostgreSQL 색인을 commit한다. 검색기는 PostgreSQL의 eligible chunk와 다시 교집합을 확인하여 진행 중 벡터를 임의 공개하지 않는다.

벡터·SQL·파일 원장은 서로 다른 저장소이며 분산 원자 트랜잭션은 아니다. 오류 시 벡터에 일부 chunk가 남을 수 있다. idempotent upsert·관계형 공개 순서·파일 원장/재시도로 정산한다. `DELETE /api/rag/documents/{id}`는 현재 SQL DocumentIndex만 지우며 Chroma·원문·원장 전체 삭제를 제공하지 않는다.

## 실행과 상태 확인

장시간 실행의 진입점은 [ingest_document_library](../ocean-ai-platform/backend/app/scripts/ingest_document_library.py)다. 아래는 로컬 자료·DB·Ollama/Chroma를 연결한 운영자가 실행할 명령 형식이며 문서 갱신 중 실행하지 않았다.

```powershell
# backend 디렉터리에서 실제 보존 문서 경로를 입력한다.
$DocumentRoot = Read-Host '보존 문서 폴더의 절대경로'
python -m app.scripts.ingest_document_library --source "$DocumentRoot" --inventory-only
python -m app.scripts.ingest_document_library --source "$DocumentRoot" --limit 10
python -m app.scripts.ingest_document_library --source "$DocumentRoot" --retry-failed
```

`--inventory-only`도 파일 원장을 작성한다. 상태 조회는 `GET /api/rag/ingestion/status`, 파일별 사유는 `GET /api/rag/ingestion/files?status=FAILED`를 사용한다. `POST /api/rag/ingest`와 `/reindex`는 [인증된 쓰기 API](../ocean-ai-platform/backend/app/api/routes_rag.py)이며 실제 대기/부분/오류를 원장 기준으로 반환한다.

파일은 PENDING/RUNNING/SUCCEEDED/DUPLICATE/EXCLUDED/FAILED, 실행은 PARTIAL/COMPLETED_WITH_ERRORS/COMPLETED/INTERRUPTED를 구분한다. `accounted_percent`에는 FAILED·EXCLUDED도 포함되므로 100% 정산이 임베딩 성공률 100%를 뜻하지 않는다. indexed chunk 수와 Chroma 전체 수에는 진행 중 자료 때문에 차이가 있을 수 있다.

## 2026-10-08 읽기 전용 실측

**04:14:30Z (13:14 KST)**의 `/api/rag/ingestion/status` GET은 HTTP 200이었다.

| 분모·상태 | 파일 수 |
|---|---:|
| 전체 목록 | 71,960 |
| 수집 대상 eligible | 4,958 |
| SUCCEEDED / DUPLICATE | 1,603 / 1,513 |
| PENDING / FAILED | 1,697 / 145 |
| EXCLUDED | 67,002 |

고유 성공 문서는 1,603개, 원장상 indexed chunk는 244,680개였다. 대상 성공률은 62.85%, 전체 정산율은 97.64%, 대상 처리율은 65.77%이며 최근 실행 `20261006T134703`은 PARTIAL이었다. 이 GET은 현재 vector 검색·cosine 실측이나 문서 전수 내용 검토를 수행하지 않았다. 1,603개 색인 성공 문서와 별도 원천 승인 검토 문서 범위를 합쳐 승인 분모를 만들지 않는다.

[document pipeline 시험](../ocean-ai-platform/backend/tests/test_document_pipeline.py)은 문맥/날짜/표 파싱, 중복, idempotency, 벡터 실패 시 SQL 미공개, 검색 score 경계를 확인한다. 남은 대기·실패와 유형별 사유를 정산하고 실제 active contract·SQL/vector ID 대응을 별도 확인해야 한다. 검색 계약은 [Hybrid Retrieval](16_HYBRID_RETRIEVAL.md)을 따른다.
## 10/8 단계별 보완 결과

전수1,842경로의 원본·별도 보존 SHA가 모두 일치했다. parser는1,584 parseable/113font partial/144encrypted/1damaged다. unique951 중 parseable786이며 별도 local collection에 81개 내용/8,761chunks를 완료했다. exact ordinal 재개와 operator 승격 검토를 구현했다. canonical pending1,697/failed145와 실제 published0을 유지한다. 전량 약358만 semantic blocks의 embedding 완료가 아니다. [29](29_DEVELOPMENT_STAGE_EXECUTION.md), [85](85_OPERATIONS_RECOVERY_REVIEW.md).
