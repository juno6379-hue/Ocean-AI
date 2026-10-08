# Hybrid Retrieval

작성일: 2026-09-16

## 검색 순서

`backend/app/rag/hybrid_retriever.py`에 다음 단계를 고정된 순서로 구현했다.

1. Metadata Filter
2. SQL/Relational Query
3. Vector Similarity Search
4. Keyword Search
5. Reranking
6. Context Assembly

필터는 `station_id`, `sensor_id`, `variable_code`, `date_start/date_end`, `report_type`, `event_type`, `error_type`를 지원한다. 기간과 관계형 필터는 PostgreSQL `DocumentIndex`에서 먼저 적용하고, Chroma 벡터 결과도 동일 chunk의 메타데이터로 다시 검증한다.

재정렬 점수는 벡터 유사도 70%와 키워드 일치도 30%를 결합한다. Chroma 또는 임베딩 모델이 준비되지 않은 경우에도 SQL·키워드 결과를 반환한다.

## 근거 결과 형식

각 결과에는 반드시 다음 필드가 포함된다.

`document_name`, `report_date`, `section`, `page`, `chunk`, `similarity`, `chunk_id`, `document_id`, `metadata`

`context` 필드는 위 근거 정보를 표시한 조립 문맥이다.

## API

```text
POST /api/rag/hybrid-search
```

예시 요청:

```json
{
  "query": "조위 급변 원인과 처리 결과",
  "station_id": "DT_0001",
  "variable_code": "TIDE",
  "date_start": "2026-01-01T00:00:00",
  "date_end": "2026-01-31T23:59:59",
  "report_type": "QUALITY_PROCESSING_REPORT",
  "top_k": 5
}
```

임베딩 실행 전에는 벡터 후보가 없을 수 있으며, 문서 Ingestion이 완료되면 동일 `chunk_id` 기준으로 Vector와 DocumentIndex가 결합된다.
