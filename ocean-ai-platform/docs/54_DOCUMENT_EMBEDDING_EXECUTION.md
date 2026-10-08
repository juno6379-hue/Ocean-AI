# 문서 임베딩 연결·실행·검증 기록

작성일: 2026-10-02. 전체 임베딩 배치는 진행 중이며, 아래 구현·검증 통과를 전체 파일 처리 완료로 해석하지 않는다.

## 적용한 네 가지 작업

1. 모델·컬렉션·차원 통일: `document_contract.py`에서 Ollama 모델 이름, 실제 모델 digest, 1,024차원, cosine 거리, 파서·청킹 버전을 고정한다. 임베딩과 Hybrid Retrieval, 챗봇은 동일 계약을 사용한다. 모델 digest나 차원이 바뀌면 무조건 검색을 진행하지 않고 불일치를 반환한다.
2. 파일 처리 이력: SQLite WAL 원장에 원본 경로·크기·수정시간·체크섬·자료군·상태·사유·재시도 횟수·대표본·청크 수·버전을 기록한다. 원본 파일은 변경하지 않는다. 동일 내용 사본과 재실행으로 생기는 중복 벡터를 방지한다.
3. 의미 기반 처리: PDF/TXT/HWP/HWPX/XLSX/XLS/DOCX 파서와 제목·절·관측소 이슈·표 행 경계 청킹을 구현했다. 긴 단위는 문장·줄·표 셀 경계를 사용한다. 임베딩 서버의 자동 절단을 끄고 문맥 초과는 오류로 기록한다.
4. 실제 검색 검증: 문서별 벡터와 DocumentIndex를 동일 chunk_id로 저장하고, HTTP 검색 라우터를 실제 PostgreSQL·Chroma·Ollama에 연결해 검증한다. 문서명·날짜·section·page·chunk·similarity 필드를 제공한다. similarity는 cosine 유사도이고 재정렬 점수는 별도 rerank_score로 구분한다.

기존 ocean_reports 1,786개 청크는 보존한다. 모델 생성 이력이 불명확한 기존 벡터에 새 모델 이름을 덮어쓰지 않고 원문에서 새 버전으로 재임베딩한다. 테스트용 langchain 컬렉션을 운영 검색에 사용하지 않는다.

## 범위 및 완료율

- 로컬 전체 목록: 71,957개.
- 지원 형식이며 요청한 자료군인 대상: 4,955개. 최초 집계 4,973개에서 Office 임시 잠금 파일 18개를 제외했다.
- 대상 외·미지원 자산·임시 파일: 67,002개. 각 파일의 제외 사유를 기록한다.
- 대상은 가이드북·일일상황/현황·일일점검·품질처리/수집률·주간조위편차·대조기 자료다.
- 성공률 분모는 4,955개다. 대상 외 제외율을 임베딩 성공률로 표시하지 않는다.
- Google Drive 파일 전수 수집 및 Drive/로컬 동기화는 이번 실행 범위가 아니다.

## 검증

- 문서 파이프라인·품질관리/승인 기존 회귀 테스트: 23개 통과.
- 커밋 대상으로 선별한 소스만 별도 디렉터리에 추출한 독립 검증: 문서 파이프라인 테스트 8개 통과. 기존 미커밋 기능 변경에 의존하지 않음을 확인했다.
- 프런트엔드: `npm run build` 성공. 기존 번들 크기 경고는 남아 있다.
- 1차 실제 검증: 활성 버전 DocumentIndex 1,166청크와 Vector DB의 동일 ID 1,166개를 대조해 누락 0개 확인.
- 1차 실제 검색: 일일상황·일일점검·가이드북·수집률·대조기 5개 유형에서 근거 필드·원문·유사도·유형 일치 통과. 존재하지 않는 관측소 필터는 결과 0건 확인.
- 2차 실제 검증: Chroma 단일 서버와 임베딩 배치를 동시에 실행하면서 활성 버전 색인 2,512개와 벡터 ID 2,512개를 대조했다. 누락 0개이며, 요청한 7개 보고서 유형 모두 실제 검색 검증을 통과했다. 관측소 부정 조건 검증도 통과했다.
- 파일별 처리와 검색 검증은 배치가 진행된 뒤 갱신된다. 최신 수치는 `54_DOCUMENT_PIPELINE_VERIFICATION.json`에 별도 저장한다.
- 실제 검색 검증은 FastAPI TestClient로 현재 라우터를 실행했다. 실행 중인 별도 백엔드 서버의 재시작·배포까지 확인했다는 의미는 아니다.
- 검색 관련성에 대한 전문가 평가, 전 자료군 완료 및 문서-사건-관측 연결은 별도 검증 대상이다.

## 오류와 수정 기록

| 발견 사항 | 처리 |
|---|---|
| 기존 임베딩 컬렉션과 Hybrid Retriever의 컬렉션 불일치 | 공통 계약으로 검색 경로 통일 |
| PDF 숫자 표가 붙어 추출되어 문맥 길이 초과 | 레이아웃 추출 우선, 의미 경계 분할 적용 |
| 일부 PDF 폰트를 레이아웃 모드가 해석하지 못함 | 표준 텍스트 추출로 대체; 둘 다 비면 실패 처리 |
| 가이드북의 빈 페이지를 OCR 대상으로 오판 | PDF 실제 그리기 연산자를 확인해 빈 페이지와 스캔 구분 |
| PDF 제어문자 NUL 때문에 PostgreSQL 저장 실패 | 벡터·SQL 저장 전에 동일하게 제어문자 정규화; 회귀 테스트 추가 |
| HWPX의 중첩 문단에서 본문 중복 추출 | 자식 문단은 독립 방문하도록 수정 |
| SQL에만 등록된 미임베딩 근거가 검색에서 제외됨 | 관계형 원문은 키워드 검색 허용, cosine 유사도는 null로 명시 |
| Windows pytest 임시 폴더 접근 제한 | 승인받은 격리 테스트 환경에서 재실행해 통과 |
| 암호가 필요한 PDF | `ENCRYPTED_PDF` 실패 기록; 암호를 추정하거나 완료로 처리하지 않음 |
| 매우 큰 문서가 전체 유형 검증을 지연 | 유형별 순환 및 작은 파일 우선 처리, 청크 단위 진행량·중단·재개 지원 |
| 독립 프로세스가 PersistentClient로 동시 읽기·쓰기를 할 때 `Error finding id` 발생 | 파일 저장소를 여는 Chroma 서버를 하나로 통일하고 배치·검색은 HTTP 클라이언트를 사용. 실제 동시 실행 중 7개 유형 재검증 통과 |

전체 오류 이력은 `backend/app/data/document_pipeline/ingestion.sqlite3`의 errors 테이블에 보존한다. 오류를 수정하고 재처리한 이력도 삭제하지 않는다.

## 실행 및 조회

프로젝트 루트에서:

```powershell
$env:PYTHONPATH = 'backend'
$env:PYTHONIOENCODING = 'utf-8'
python -m app.scripts.serve_document_vectors
```

벡터 서버를 유지한 상태에서 별도 터미널에서 배치를 실행한다. 기본 서버 주소는 로컬 전용 `127.0.0.1:8001`이며 `.env`의 `DOCUMENT_CHROMA_HOST`, `DOCUMENT_CHROMA_PORT`, `DOCUMENT_CHROMA_SSL`로 클라이언트 설정을 관리한다. 운영 상시 실행에는 별도 서비스 등록이 필요하며 이번 실행은 숨김 백그라운드 프로세스다.

```powershell
$env:PYTHONPATH = 'backend'
$env:PYTHONIOENCODING = 'utf-8'
python -m app.scripts.ingest_document_library --source 'C:\AI_Observation\ocean-ai-platform\분류'
```

성공한 파일은 건너뛰고 미처리 파일을 이어서 실행한다. 실패 파일까지 다시 실행하려면 `--retry-failed`를 추가한다. OS 파일 잠금으로 동시에 두 배치가 쓰지 못하게 한다. 정상 중단은 `backend/app/data/document_pipeline/stop.request` 파일을 생성하고, 재개 전에 해당 요청 파일을 제거한다.

실제 검색 검증:

```powershell
python -m app.scripts.verify_document_retrieval --output backend/app/data/document_pipeline/retrieval_verification.json
```

조회 API:

- `GET /api/rag/ingestion/status`
- `GET /api/rag/ingestion/files?status=FAILED`
- `POST /api/rag/hybrid-search`

물리 페이지가 없는 엑셀·HWP 문서는 page=null이며 source_locator에 시트·행·문단 위치를 기록한다. 원문에서 보고일을 확정하지 못하면 null과 date_source=unresolved를 반환한다. 보고일을 실행시각으로 대체하지 않는다.
