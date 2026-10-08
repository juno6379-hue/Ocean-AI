# 파일 역할: 문서 근거 검색 관련 요청을 검증하고 API 응답을 제공합니다.
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import datetime
from app.rag.hybrid_retriever import hybrid_search
from app.core.database import get_db
from app.models.domain import DocumentIndex
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/rag",
    tags=["Knowledge Agent"]
)

class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


class HybridSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    station_id: Optional[str] = None
    sensor_id: Optional[str] = None
    variable_code: Optional[str] = None
    date_start: Optional[datetime.datetime] = None
    date_end: Optional[datetime.datetime] = None
    report_type: Optional[str] = None
    event_type: Optional[str] = None
    error_type: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)

class IngestRequest(BaseModel):
    directory: str
    max_files: Optional[int] = None

@router.post("/ingest")
def ingest_documents(req: IngestRequest):
    from app.rag.semantic_ingestion import ingest_directory
    if req.max_files is not None and req.max_files < 1:
        raise HTTPException(422, "max_files must be positive")
    return ingest_directory(req.directory, req.max_files)

@router.post("/reindex")
def reindex_documents(req: IngestRequest):
    from app.rag.semantic_ingestion import ingest_directory
    return ingest_directory(req.directory, req.max_files)

@router.get("/documents")
def list_indexed_documents(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.query(DocumentIndex.document_id, DocumentIndex.document_title, DocumentIndex.document_type).distinct().limit(min(limit, 1000)).all()
    return {"documents": [{"document_id": x[0], "document_title": x[1], "document_type": x[2]} for x in rows]}

@router.get("/chunks/{document_id}")
def list_document_chunks(document_id: str, db: Session = Depends(get_db)):
    rows = db.query(DocumentIndex).filter(DocumentIndex.document_id == document_id).order_by(DocumentIndex.page_no, DocumentIndex.chunk_id).all()
    return {"document_id": document_id, "chunks": rows}

@router.delete("/documents/{document_id}")
def delete_indexed_document(document_id: str, db: Session = Depends(get_db)):
    deleted = db.query(DocumentIndex).filter(DocumentIndex.document_id == document_id).delete(synchronize_session=False)
    db.commit()
    return {"document_id": document_id, "deleted_chunks": deleted}


@router.post("/hybrid-search")
def hybrid_search_api(req: HybridSearchRequest):
    filters = (req.model_dump() if hasattr(req, "model_dump") else req.dict())
    filters.pop("query", None)
    top_k = filters.pop("top_k", 5)
    return {"success": True, **hybrid_search(req.query, filters, top_k)}

@router.post("/chat")
async def chat_with_knowledge_base(req: ChatRequest):
    """
    RAG 지식 검색 및 SQL 데이터 조회 통합 챗봇 API 엔드포인트
    """
    try:
        if not req.query:
            raise HTTPException(status_code=400, detail="질문이 비어있습니다.")
            
        # 1. 의도 분류 (RAG vs SQL)
        try:
            from app.agents.sql_agent import classify_intent, ask_sql_agent
            intent = classify_intent(req.query)
        except ImportError:
            intent = "RAG"
            ask_sql_agent = None
        
        # 2. 에이전트 라우팅
        if intent == "DATA" and ask_sql_agent:
            result = ask_sql_agent(req.query)
        else:
            try:
                from app.agents.rag_knowledge_agent import ask_knowledge_base
                result = ask_knowledge_base(req.query)
            except ImportError:
                result = hybrid_search(req.query, {}, 5)
                result["fallback"] = "HYBRID_RETRIEVAL"
        
        if isinstance(result, dict) and "answer" not in result:
            result = {"answer": result.get("context", "근거 문서가 없습니다."), "source": "HYBRID_RETRIEVAL", **result}
        return {
            "success": True,
            "answer": result["answer"],
            "source": result["source"],
            "evidence": result.get("results", []),
            "vector_status": result.get("vector_status")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingestion/status")
def ingestion_status():
    from app.rag.document_pipeline import status
    return status()


@router.get("/ingestion/files")
def ingestion_files(status: Optional[str] = None, limit: int = 100):
    from app.rag.document_pipeline import file_records
    return {"files": file_records(status, limit), "is_demo": False}
