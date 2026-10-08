# DocumentIndex 및 Embedding 구조

작성일: 2026-09-16

## 확장 필드

`DocumentIndex`에 다음 필드를 추가했다.

`document_id`, `report_id`, `chunk_id`, `document_type`, `document_title`, `document_date`, `period_start`, `period_end`, `related_station_id`, `related_sensor_id`, `related_variable_code`, `event_id`, `event_type`, `error_type`, `error_cause`, `section_name`, `page_no`, `chunk_text`, `embedding_id`, `embedding_model`, `embedding_version`, `metadata_json`

기존 내부 surrogate `id`는 호환성을 위해 유지하고, 문서 식별자는 `document_id`, chunk 식별자는 `chunk_id`로 사용한다. 동일 문서의 여러 chunk가 같은 `document_id`를 가질 수 있으며 `chunk_id`는 유일하다.

## Ingestion Pipeline

`backend/app/rag/semantic_ingestion.py`에 유형별 수집 파이프라인을 구현했다.

- 품질관리 가이드북: 절·장·표·검사규칙 제목 경계
- 일일상황보고: 관측소·이슈 블록 경계
- 일일점검보고서: 관측소 블록 경계(장비·문제·조치 문맥 보존)
- 품질처리보고서 및 수집률: 품질 처리/수집률 섹션과 관측소 경계
- 주간조위편차경향보고서: 조위·기간 섹션 경계
- 대조기 모니터링 보고서: 대조기/위험 사건 섹션 경계

PDF는 페이지 경계를 보존하고 TXT는 줄·제목·관측소 사건 경계를 사용한다. 고정 token 크기나 overlap을 기준으로 자르지 않는다. 각 chunk의 MDC 관측소 코드, 변수 코드, 사건·오류 메타데이터를 추출해 `metadata_json`에 저장한다.

임베딩은 `embedding_id = chunk_id`, 모델은 `EMBEDDING_MODEL` 환경변수(기본 `jhgan/ko-sroberta-multitask`), 버전은 `1.0`으로 기록한다. Chroma 저장과 PostgreSQL DocumentIndex 저장을 동일 chunk ID로 연결한다.

일괄 실행은 다음 함수로 수행한다.

```python
from app.rag.semantic_ingestion import ingest_directory
ingest_directory(r"C:\AI_Observation\ocean-ai-platform\분류\비정형데이터")
```

현재 구조·마이그레이션·컴파일 검증을 완료했다. 실제 대용량 임베딩 실행은 모델 다운로드와 처리 시간이 필요하므로 별도 배치로 실행한다.
