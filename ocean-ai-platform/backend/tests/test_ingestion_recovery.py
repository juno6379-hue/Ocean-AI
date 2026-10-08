import json
import logging
import sqlite3

import pytest

from app.rag import ingestion_recovery as m
from app.rag.document_contract import PARSER_VERSION, CHUNK_VERSION


@pytest.fixture
def contract():
    return {"provider": "ollama", "model": "local", "model_digest": "abc", "dimension": 2,
            "metric": "cosine", "embedding_version": "test", "parser_version": PARSER_VERSION,
            "chunk_version": CHUNK_VERSION, "query_prefix": ""}


def proof(path):
    return {"path": str(path), "sha256": m.sha_file(path), "original_path": str(path), "bytes": path.stat().st_size}


def embed(texts, query=False):
    return [[float("센서" in t), float("기압" in t)] for t in texts]


def test_resume_publishes_only_complete_documents_and_is_idempotent(tmp_path, contract):
    src = tmp_path / "raw.txt"
    src.write_text("센서\n\n기압\n\n센서 기압", encoding="utf8")
    store = m.RecoveryStore(tmp_path / "index.sqlite3", contract)
    first = store.ingest(proof(src), "DAILY_INSPECTION_REPORT", embed, chunk_budget=1)
    assert first["status"] == "PARTIAL"
    assert store.search("센서", embed) == []
    assert store.ingest(proof(src), "DAILY_INSPECTION_REPORT", embed)["status"] == "SUCCEEDED"
    count = store.summary()["chunks"]
    assert store.ingest(proof(src), "DAILY_INSPECTION_REPORT", embed)["status"] == "DUPLICATE"
    assert store.summary()["chunks"] == count == 3
    assert store.search("기압", embed)[0]["citation"]["source_sha256"] == proof(src)["sha256"]
    assert store.search("센서", embed, document_sha="0" * 64) == []
    assert store.search("센서", embed, page=99) == []
    store.close()


def test_changed_source_is_not_retrieval_evidence(tmp_path, contract):
    src = tmp_path / "raw.txt"
    src.write_text("센서", encoding="utf8")
    old = proof(src)
    store = m.RecoveryStore(tmp_path / "index.sqlite3", contract)
    store.ingest(old, "DAILY_INSPECTION_REPORT", embed)
    src.write_text("센서 수정", encoding="utf8")
    assert store.search("센서", embed) == []
    with pytest.raises(ValueError, match="SOURCE_CHECKSUM_CHANGED"):
        store.ingest(old, "DAILY_INSPECTION_REPORT", embed)


def test_embedding_dimension_failure_cannot_publish(tmp_path, contract):
    src = tmp_path / "raw.txt"
    src.write_text("센서", encoding="utf8")
    store = m.RecoveryStore(tmp_path / "index.sqlite3", contract)
    r = store.ingest(proof(src), "DAILY_INSPECTION_REPORT", lambda t: [[1]])
    assert r["status"] == "FAILED"
    assert r["category"] == "EMBEDDING_CONTRACT_MISMATCH"
    assert store.summary()["chunks"] == 0


def test_contract_cannot_be_replaced_on_resume(tmp_path, contract):
    path = tmp_path / "index.sqlite3"
    m.RecoveryStore(path, contract).close()
    with pytest.raises(ValueError, match="IMMUTABLE_CONTRACT"):
        m.RecoveryStore(path, {**contract, "model_digest": "changed"})
    with pytest.raises(ValueError, match="ACTIVE_LEDGER_WRITE_FORBIDDEN"):
        m.RecoveryStore(path, contract, source_ledger=path)


def test_exact_preserved_alias_hash_and_ledger_checksum_required(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    (a / "x.txt").write_text("same")
    (b / "x.txt").write_text("same")
    row = {"path": str(a / "x.txt"), "size": 4, "checksum": m.sha_file(a / "x.txt")}
    assert m.resolve_preserved(row, [(a, b)])["status"] == "HASH_MATCH"
    (b / "x.txt").write_text("evil")
    with pytest.raises(ValueError, match="CHECKSUM"):
        m.resolve_preserved(row, [(a, b)])
    with pytest.raises(ValueError, match="NOT_UNIQUE"):
        m.resolve_preserved(row, [(a, b), (a, b)])


def test_production_ledger_reader_cannot_mutate(tmp_path):
    p = tmp_path / "ledger.sqlite3"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE files(path,root,status,document_type,checksum,size,reason)")
    c.execute("INSERT INTO files VALUES('p','r','FAILED','PDF',NULL,1,'encrypted')")
    c.commit(); c.close()
    before = m.sha_file(p)
    assert m.backlog_snapshot(p)["counts"] == {"FAILED": 1}
    with m.readonly_ledger(p) as ro:
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("DELETE FROM files")
    assert m.sha_file(p) == before


def test_pdf_font_warning_prevents_complete_extraction_claim(monkeypatch, tmp_path):
    from app.rag.report_parser import Unit
    def partial(path):
        logging.getLogger("pypdf._page").warning("PDF contains an uninterpretable font. Output will be incomplete.")
        return [Unit("partial")]
    monkeypatch.setattr(m, "parse", partial)
    _, r = m.parser_review(tmp_path / "source.pdf", "PDF")
    assert r["parser_status"] == "PARTIAL_EXTRACTION_REVIEW_REQUIRED"
    assert r["category"] == "PDF_FONT_MAPPING_REVIEW_REQUIRED"


@pytest.mark.parametrize("error,category", [
    ("ENCRYPTED_PDF: password required", "OWNER_PASSWORD_REQUIRED"),
    ("PROTECTED_HWP: encrypted", "OWNER_UNPROTECTED_EXPORT_REQUIRED"),
    ("OCR_REQUIRED", "LOCAL_OCR_REVIEW_REQUIRED"),
    ("Stream has ended unexpectedly", "DAMAGED_SOURCE_REEXPORT_REQUIRED"),
])
def test_failure_is_actionable_without_invented_decrypt(error, category):
    assert m.failure_category(error) == category


def test_external_embedding_endpoint_forbidden(contract):
    with pytest.raises(ValueError, match="LOCAL_EMBEDDING"):
        m.local_embedder(contract, "https://example.com")
