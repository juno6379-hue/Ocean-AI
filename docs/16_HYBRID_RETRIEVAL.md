# Hybrid Retrieval

현행화: 2026-10-08

## 실제 검색 경로

[hybrid_retriever](../ocean-ai-platform/backend/app/rag/hybrid_retriever.py)의 `hybrid_search()`는 다음 순서로 검색한다.

1. station/sensor/variable/report type/event type/error type 및 **문서 날짜** 조건으로 PostgreSQL `DocumentIndex`를 제한한다.
2. [document embedding contract](../ocean-ai-platform/backend/app/rag/document_contract.py)를 읽어 active embedding version 또는 미임베딩 관계형 행만 대상으로 삼는다. 계약이 없으면 version이 null인 SQL 근거만 허용한다.
3. VECTOR_SEARCH_ENABLED이고 계약·eligible 행이 있으면 모델 digest·dimension·collection을 검사한 후 Chroma cosine 검색을 실행한다.
4. Chroma 결과의 chunk ID를 관계형 필터 결과와 다시 대조한다. 필터 밖/미공개/이전 version 벡터는 문맥으로 사용하지 않는다.
5. 같은 관계형 범위에서 query token의 text contains 검색을 수행한다. token은 2자 이상이며 keyword 후보를 최대 `top_k × 20`개 조회한다.
6. chunk ID로 후보를 합쳐 가중 재정렬하고 `top_k`개 근거의 문서명·날짜·section·page·chunk ID와 본문으로 context를 조립한다.

이는 문서의 관계형 metadata와 벡터/키워드 근거 결합이다. SQL agent가 관측 DB를 질의하는 경로와 자동 multi-source rank fusion하는 구현은 아니다. `/api/rag/chat`의 SQL/RAG intent 분기는 별도의 라우팅이다.

## 점수의 의미

```text
vector similarity = clamp(1 - cosine distance, -1, 1)
keyword score     = 포함된 query token 수 / query token 수
rerank score      = 0.7 × max(vector similarity, 0) + 0.3 × keyword score
```

| retrieval_method | similarity | 의미 |
|---|---|---|
| VECTOR | 실제 vector cosine 값 | keyword 일치가 없는 vector 근거 |
| HYBRID | 실제 vector cosine 값 | vector·keyword가 함께 있는 근거 |
| KEYWORD | `null` | embedding similarity를 측정하지 않은 text 근거 |

rerank score는 정렬용 값이며 cosine·원인 신뢰도·QC 정확도가 아니다. keyword-only 결과에 0이나 가중 score를 실제 cosine으로 채우지 않는다. 현재 재정렬은 위의 고정 가중식이며 학습된 cross-encoder reranker를 사용하지 않는다.

## 반환 계약과 상태

결과에는 document name/date, section/page/chunk, similarity, retrieval method, rerank/keyword score, chunk/document ID, embedding model/version, metadata가 포함된다. 보고일·실제 페이지 근거가 없으면 null일 수 있다. 상위 응답에는 filters, context, eligible_chunks, collection, vector_status/vector_error, evidence_status가 있다.

- `DISABLED`: vector 검색 설정이 꺼져 있다.
- `UNAVAILABLE`: 계약 또는 vector 실행에 오류가 있다. SQL keyword 근거가 있다면 별도로 반환할 수 있다.
- `EMPTY`: 계약은 있지만 vector 검색 조건에 eligible 자료가 없다.
- `AVAILABLE`: vector 검색 경로를 사용할 수 있었다. 결과에 keyword-only 근거가 섞일 수 있으며 이 상태만으로 모든 결과의 cosine이 측정됐다는 의미는 아니다.
- `FOUND` / `NO_RELEVANT_EVIDENCE`: 현재 조건에 반환 가능한 근거가 있는지 구분한다. HTTP 성공이나 vector 상태가 원인 확정을 의미하지 않는다.

모델·Chroma 오류를 다른 collection이나 임의 embedding으로 대체하지 않는다. 실제 model digest가 바뀌면 새 계약·collection/재수집이 필요하다.

## API 사용 예시

[RAG API](../ocean-ai-platform/backend/app/api/routes_rag.py)의 `POST /api/rag/hybrid-search`는 분석 조회다. query는 1~4,000자, top_k는 1~50 범위다.

```json
{
  "query": "조위 급변 처리 결과",
  "station_id": "DT_0001",
  "variable_code": "TIDE",
  "date_start": "2026-01-01T00:00:00Z",
  "date_end": "2026-01-31T23:59:59Z",
  "report_type": "QUALITY_PROCESSING_REPORT",
  "top_k": 5
}
```

예시 필터의 날짜는 **보고서 document_date**다. 사건 유효기간·관측시각·자료 가용 시각 필터 또는 해당 시점의 승인 증거를 대신하지 않는다. 표준 API는 event_id 필터를 제공하지 않는다. 반환된 문서의 사건 동일성·physical sensor·단위·QC 시행기간은 [원천 계약](11_OBSERVATION_STANDARD_LAYER.md)과 [사건/Label 검토](13_AI_LABEL_SEPARATION.md)에서 별도로 확인한다. 예측 입력의 문서 available_at은 [Feature as-of](14_FEATURE_STORE.md)와 downstream 계약에서 검증해야 한다.

## 검증과 현재 실행 확인

[test_document_pipeline](../ocean-ai-platform/backend/tests/test_document_pipeline.py)은 station/sensor/type 필터, 실 cosine과 rerank score 분리, keyword-only의 `similarity=None`을 시험한다. [verify_document_retrieval](../ocean-ai-platform/backend/app/scripts/verify_document_retrieval.py)은 로컬 연결에서 active-version 색인·embedding ID·원문 존재, 보고서 유형별 HTTP 검색과 잘못된 station의 빈 결과를 점검한다. 그 실행 결과도 시각·계약·corpus 범위가 있는 근거다.

이번 문서 갱신은 코드·기존 시험 근거와 수집 상태 GET을 확인했으며 새 embedding·vector 검색 배치를 실행하지 않았다. 실제 corpus/contract·Chroma 원장이 Git에 없으므로 clone의 시험 통과로 현재 vector 검색이나 전 문서 근거 승인이 완료됐다고 표시하지 않는다. 수집·정산의 현재 분모는 [DocumentIndex와 수집](15_DOCUMENT_INDEX_INGESTION.md)의 2026-10-08 13:14 KST 기록을 참고한다.
## 10/8 단계별 보완 결과

별도 복구 SQLite에서 현재 loopback Ollama 모델 digest/차원 계약에 맞는 vector와 citation·source/page/document filter를 시험했다. 완성 문서만 조회하고 PARTIAL은 제외한다. self-query7건 성공은 전체 도메인 QA 정확도가 아니다. 이후 수정된 SQL postimage는 재실행/rollback이 거부한다. [29](29_DEVELOPMENT_STAGE_EXECUTION.md).
