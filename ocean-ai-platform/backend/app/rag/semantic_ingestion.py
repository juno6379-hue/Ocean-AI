# 파일 역할: 문서 수집 요청을 이력 관리가 가능한 의미 기반 파이프라인으로 전달합니다.
"""Public ingestion entry point; all writes use the versioned audit pipeline."""
from app.rag.report_parser import classify as classify_document_type, semantic_blocks, Unit


def semantic_chunks(text, document_type):
    units = [Unit(value, page=i+1) for i, value in enumerate(text.split("---PAGE---"))]
    return [(u.text, u.section, u.page) for u in semantic_blocks(units, document_type)]


def ingest_directory(directory, max_files=None):
    # A long job runs via CLI; API returns actual partial/failure status, never a constant COMPLETED.
    from app.rag.document_pipeline import run
    return run(directory, max_files)


def ingest_text(text, title, source_path, persist_embeddings=True):
    raise ValueError("Text-only ingestion has no reliable source audit. Use ingest_directory or ingest_document_library with the original report path.")
