# 파일 역할: 메타데이터와 관계형 조건을 적용해 벡터·키워드 근거를 통합 검색합니다.
"""Metadata → SQL → Vector → Keyword → Rerank → Context Assembly 검색."""
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import or_

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.domain import DocumentIndex


def _where(filters: Dict[str, Any]) -> Dict[str, Any]:
    mapping = {"station_id": "related_station_id", "sensor_id": "related_sensor_id",
               "variable_code": "related_variable_code", "report_type": "document_type",
               "event_type": "event_type", "error_type": "error_type"}
    clauses = [{dest: {"$eq": filters[key]}} for key, dest in mapping.items() if filters.get(key)]
    from datetime import timezone
    for key, op in [("date_start", "$gte"), ("date_end", "$lte")]:
        value = filters.get(key)
        if value:
            value = datetime.fromisoformat(value) if isinstance(value, str) else value
            if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
            clauses.append({"document_date_epoch": {op: value.timestamp()}})
    return {"$and": clauses} if len(clauses) > 1 else (clauses[0] if clauses else {})


def _metadata_filter(query, filters: Dict[str, Any]):
    """관계형 메타데이터와 기간 필터를 먼저 적용한다."""
    mapping = {
        "station_id": DocumentIndex.related_station_id,
        "sensor_id": DocumentIndex.related_sensor_id,
        "variable_code": DocumentIndex.related_variable_code,
        "report_type": DocumentIndex.document_type,
        "event_type": DocumentIndex.event_type,
        "error_type": DocumentIndex.error_type,
    }
    for key, column in mapping.items():
        if filters.get(key):
            query = query.filter(column == filters[key])
    if filters.get("date_start"):
        query = query.filter(DocumentIndex.document_date >= filters["date_start"])
    if filters.get("date_end"):
        query = query.filter(DocumentIndex.document_date <= filters["date_end"])
    return query


def _keyword_terms(query_text: str) -> List[str]:
    return [term for term in re.findall(r"[\w가-힣_-]+", query_text.lower()) if len(term) >= 2]


def hybrid_search(query_text: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 5) -> Dict[str, Any]:
    from app.rag.document_contract import load_contract, get_collection, embed
    filters = filters or {}
    top_k = max(1, min(top_k, 50))
    candidates = {}
    vector_status = "DISABLED"
    vector_error = None
    contract = None
    try:
        contract = load_contract()
    except RuntimeError as exc:
        vector_error = str(exc)
    with SessionLocal() as db:
        base = _metadata_filter(db.query(DocumentIndex), filters)
        if contract:
            # 미임베딩 관계형 근거는 키워드 검색에 허용하고, 이전 임베딩 버전은 제외한다.
            base = base.filter(or_(DocumentIndex.embedding_version == contract["embedding_version"],
                                  DocumentIndex.embedding_version.is_(None)))
        else:
            # 계약이 없으면 SQL 원문 근거만 조회하고 임의의 벡터 컬렉션으로 대체하지 않는다.
            base = base.filter(DocumentIndex.embedding_version.is_(None))
        eligible_count = base.count()
        if settings.VECTOR_SEARCH_ENABLED and contract and eligible_count:
            try:
                collection = get_collection(contract)
                n = min(collection.count(), top_k * 20)
                if n:
                    result = collection.query(query_embeddings=embed([query_text], contract, query=True),
                        n_results=n, where=_where(filters) or None, include=["distances"])
                    scores = dict(zip(result["ids"][0], result["distances"][0]))
                    for row in base.filter(DocumentIndex.chunk_id.in_(list(scores))).all():
                        candidates[row.chunk_id] = {"row": row, "vector_similarity":
                            max(-1.0, min(1.0, 1.0-float(scores[row.chunk_id]))), "keyword_score": 0.0}
                vector_status = "AVAILABLE"
            except Exception as exc:
                import logging
                logging.getLogger(__name__).exception("document_vector_search_failed")
                vector_status = "UNAVAILABLE"
                vector_error = type(exc).__name__ + ": " + str(exc)[:300]
        elif settings.VECTOR_SEARCH_ENABLED:
            vector_status = "EMPTY" if contract else "UNAVAILABLE"
        terms = _keyword_terms(query_text)
        if terms:
            keyword_query = base.filter(or_(*(DocumentIndex.chunk_text.contains(term, autoescape=True) for term in terms)))
            for row in keyword_query.order_by(DocumentIndex.chunk_id).limit(top_k * 20).all():
                item = candidates.setdefault(row.chunk_id, {"row": row, "vector_similarity": None, "keyword_score": 0.0})
                item["keyword_score"] = sum(t in (row.chunk_text or "").lower() for t in terms) / len(terms)
        ranked = []
        for item in candidates.values():
            row = item["row"]
            vector = item["vector_similarity"]
            score = .7 * max(0.0, vector or 0.0) + .3 * item["keyword_score"]
            if score <= 0: continue
            ranked.append({"document_name": row.document_title,
                "report_date": row.document_date.isoformat() if row.document_date else None,
                "section": row.section_name, "page": row.page_no, "chunk": row.chunk_text,
                "similarity": round(vector, 6) if vector is not None else None,
                # Keyword-only matches have no cosine score. Never fabricate one
                # or interpret rerank_score as embedding similarity/confidence.
                "retrieval_method": ("HYBRID" if item["keyword_score"] else "VECTOR") if vector is not None else "KEYWORD",
                "rerank_score": round(score, 6), "keyword_score": item["keyword_score"],
                "chunk_id": row.chunk_id, "document_id": row.document_id,
                "embedding_model": row.embedding_model, "embedding_version": row.embedding_version,
                "metadata": row.metadata_json or {}})
        ranked.sort(key=lambda item: (-item["rerank_score"], item["chunk_id"]))
        evidence = ranked[:top_k]
        context = "\n\n".join(
            f"[{r['document_name']} | {r['report_date']} | {r['section']} | p.{r['page']} | chunk:{r['chunk_id']}]\n{r['chunk']}"
            for r in evidence)
        return {"query": query_text, "filters": filters, "results": evidence, "context": context,
                "vector_status": vector_status, "vector_error": vector_error,
                "collection": contract['collection'] if contract else None,
                "eligible_chunks": eligible_count,
                "evidence_status": "FOUND" if evidence else "NO_RELEVANT_EVIDENCE"}
