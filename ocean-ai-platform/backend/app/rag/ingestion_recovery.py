"""Read-only production backlog audit and restartable, isolated local ingestion.

This module never imports application DB sessions or connects to active Chroma.
An exact active embedding contract can be reused with a loopback Ollama endpoint;
vectors and parser citations are stored only in the explicitly selected SQLite.
Its completion is a development verification, not publication to DocumentIndex.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sqlite3
import stat
import urllib.parse
import urllib.request
import warnings
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.rag.report_parser import parse, semantic_blocks
from app.rag.document_contract import CHUNK_VERSION, PARSER_VERSION


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def guarded(path, root=None):
    """Check every existing ancestor before reading/writing; no junction traversal."""
    p = Path(path).absolute()
    for part in (p, *p.parents):
        if part.exists() or part.is_symlink():
            s = part.lstat()
            if part.is_symlink() or getattr(s, "st_file_attributes", 0) & 0x400:
                raise ValueError("REPARSE_POINT_FORBIDDEN")
    p = p.resolve()
    if root is not None:
        r = guarded(root)
        if not p.is_relative_to(r):
            raise ValueError("PATH_OUTSIDE_ROOT")
    return p


@contextmanager
def readonly_ledger(path):
    p = guarded(path)
    c = sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON")
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


def backlog_snapshot(path):
    with readonly_ledger(path) as c:
        columns = {r[1] for r in c.execute("PRAGMA table_info(files)")}
        needed = {"path", "root", "status", "document_type", "checksum", "size"}
        if not needed <= columns:
            raise ValueError("UNSUPPORTED_LEDGER_SCHEMA")
        counts = dict(c.execute("SELECT status,COUNT(*) FROM files GROUP BY status"))
        rows = [dict(r) for r in c.execute(
            "SELECT path,root,size,document_type,status,reason,checksum FROM files "
            "WHERE status IN ('PENDING','FAILED') ORDER BY size,path")]
        known = {r[0] for r in c.execute(
            "SELECT checksum FROM files WHERE status='SUCCEEDED' AND checksum IS NOT NULL")}
    return {"checked_at": now(), "ledger_path": str(Path(path).absolute()),
            "counts": counts, "backlog": rows, "successful_checksums": sorted(known),
            "snapshot_sha256": hashlib.sha256(canonical({"counts": counts, "backlog": rows})).hexdigest()}


def failure_category(error):
    text = str(error)
    for marker, category in (
        ("ENCRYPTED_PDF", "OWNER_PASSWORD_REQUIRED"),
        ("PROTECTED_HWP", "OWNER_UNPROTECTED_EXPORT_REQUIRED"),
        ("PDF_FONT_MAPPING", "PDF_FONT_MAPPING_REVIEW_REQUIRED"),
        ("OCR_REQUIRED", "LOCAL_OCR_REVIEW_REQUIRED"),
        ("Stream has ended", "DAMAGED_SOURCE_REEXPORT_REQUIRED"),
        ("Invalid cross-reference", "DAMAGED_SOURCE_REEXPORT_REQUIRED"),
        ("ENCODING_UNRESOLVED", "SOURCE_ENCODING_REQUIRED"),
        ("REPARSE", "PATH_POLICY_REJECTED"),
        ("CHECKSUM", "SOURCE_CHANGED"),
        ("DIMENSION", "EMBEDDING_CONTRACT_MISMATCH"),
        ("MODEL_DIGEST", "EMBEDDING_CONTRACT_MISMATCH"),
        ("CONTEXT", "SEMANTIC_UNIT_TOO_LARGE"),
        ("EMPTY", "NO_EXTRACTABLE_CONTENT"),
    ):
        if marker in text:
            return category
    if isinstance(error, FileNotFoundError):
        return "SOURCE_NOT_AVAILABLE"
    if isinstance(error, (TimeoutError, ConnectionError)) or "timed out" in text:
        return "LOCAL_EMBEDDING_TEMPORARILY_UNAVAILABLE"
    return "PARSER_OR_LOCAL_RUNTIME_REVIEW_REQUIRED"


def resolve_preserved(row, aliases):
    """Only exact root-relative aliases; names/substring/suffix guesses are forbidden."""
    original = guarded(row["path"])
    candidates = []
    for source_root, target_root in aliases:
        sr = guarded(source_root)
        if original.is_relative_to(sr):
            candidates.append(guarded(Path(target_root) / original.relative_to(sr), target_root))
    if len(candidates) != 1:
        raise ValueError("PRESERVATION_ALIAS_NOT_UNIQUE")
    preserved = candidates[0]
    if not original.is_file() or not preserved.is_file():
        raise FileNotFoundError("Original or preserved exact alias is absent")
    first = sha_file(original)
    second = sha_file(preserved)
    if first != second or (row.get("checksum") and row["checksum"] != first):
        raise ValueError("PRESERVED_CHECKSUM_MISMATCH")
    if original.stat().st_size != row["size"] or preserved.stat().st_size != row["size"]:
        raise ValueError("LEDGER_SIZE_CHANGED")
    return {"original_path": str(original), "path": str(preserved), "sha256": first,
            "bytes": row["size"], "verified_at": now(), "status": "HASH_MATCH"}


def local_embedder(contract, base_url="http://127.0.0.1:11434"):
    host = urllib.parse.urlparse(base_url)
    if host.scheme != "http" or host.hostname not in {"127.0.0.1", "localhost", "::1"} or host.username:
        raise ValueError("LOCAL_EMBEDDING_ENDPOINT_REQUIRED")
    if contract.get("provider") != "ollama" or contract.get("metric") != "cosine":
        raise ValueError("UNSUPPORTED_EMBEDDING_CONTRACT")
    if contract.get("parser_version") != PARSER_VERSION or contract.get("chunk_version") != CHUNK_VERSION:
        raise ValueError("PARSER_CONTRACT_MISMATCH")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def check_model():
        body = json.load(opener.open(base_url + "/api/tags", timeout=15))
        if not any(m["name"] == contract["model"] and m.get("digest") == contract["model_digest"]
                   for m in body.get("models", [])):
            raise ValueError("MODEL_DIGEST_MISMATCH")
    check_model()
    def embed(texts, query=False):
        check_model()  # A model replacement cannot silently mix the index.
        inputs = [contract.get("query_prefix", "") + t for t in texts] if query else texts
        req = urllib.request.Request(base_url + "/api/embed", data=canonical({
            "model": contract["model"], "input": inputs, "truncate": False}),
            headers={"Content-Type": "application/json"}, method="POST")
        body = json.load(opener.open(req, timeout=180))
        vectors = body.get("embeddings", [])
        if len(vectors) != len(texts):
            raise ValueError("EMBEDDING_COUNT_MISMATCH")
        for v in vectors:
            if len(v) != contract["dimension"] or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in v):
                raise ValueError("EMBEDDING_DIMENSION_OR_VALUE_MISMATCH")
        return vectors
    return embed


class RecoveryStore:
    def __init__(self, path, contract, source_ledger=None):
        self.path = guarded(path)
        if source_ledger and self.path == guarded(source_ledger):
            raise ValueError("ACTIVE_LEDGER_WRITE_FORBIDDEN")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(self.path)
        self.c.row_factory = sqlite3.Row
        self.c.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS documents(sha256 TEXT PRIMARY KEY,path TEXT NOT NULL,
          kind TEXT NOT NULL,status TEXT NOT NULL,total_chunks INTEGER NOT NULL DEFAULT 0,
          completed_chunks INTEGER NOT NULL DEFAULT 0,error TEXT,category TEXT,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,document_sha TEXT NOT NULL,
          ordinal INTEGER NOT NULL,text TEXT NOT NULL,citation TEXT NOT NULL,vector TEXT NOT NULL,
          UNIQUE(document_sha,ordinal));
        """)
        exact = hashlib.sha256(canonical(contract)).hexdigest()
        prev = self.c.execute("SELECT value FROM meta WHERE key='contract_sha256'").fetchone()
        if prev and prev[0] != exact:
            self.c.close()
            raise ValueError("IMMUTABLE_CONTRACT_MISMATCH")
        self.c.execute("INSERT OR IGNORE INTO meta VALUES('contract_sha256',?)", (exact,))
        self.c.execute("INSERT OR IGNORE INTO meta VALUES('contract',?)", (canonical(contract).decode(),))
        self.c.commit()
        self.contract = contract

    def ingest(self, proof, kind, embed, *, chunk_budget=2000, batch_size=12):
        path = guarded(proof["path"])
        expected = proof["sha256"]
        if sha_file(path) != expected:
            raise ValueError("SOURCE_CHECKSUM_CHANGED")
        previous = self.c.execute("SELECT * FROM documents WHERE sha256=?", (expected,)).fetchone()
        if previous and previous["kind"] != kind:
            raise ValueError("SAME_BYTES_DIFFERENT_DOCUMENT_TYPE_REVIEW_REQUIRED")
        if previous and previous["status"] == "SUCCEEDED":
            return {"status": "DUPLICATE", "sha256": expected, "chunks": previous["total_chunks"]}
        self.c.execute("INSERT OR IGNORE INTO documents(sha256,path,kind,status,updated_at) VALUES(?,?,?,'PENDING',?)",
                       (expected, str(path), kind, now()))
        self.c.commit()
        try:
            blocks, reviewed = parser_review(path, kind)
            if reviewed['parser_status'] != 'PARSEABLE':
                raise ValueError('PDF_FONT_MAPPING_REVIEW_REQUIRED')
            if not blocks:
                raise ValueError("EMPTY_CHUNKS")
            # Parse bytes cannot change between verification and citation publication.
            if sha_file(path) != expected:
                raise ValueError("SOURCE_CHECKSUM_CHANGED_DURING_PARSE")
            existing = {r[0] for r in self.c.execute("SELECT ordinal FROM chunks WHERE document_sha=?", (expected,))}
            needed = [(i, b) for i, b in enumerate(blocks) if i not in existing]
            self.c.execute("UPDATE documents SET total_chunks=?,status='PARTIAL',error=NULL,category=NULL WHERE sha256=?",
                           (len(blocks), expected))
            self.c.commit()
            for offset in range(0, min(len(needed), chunk_budget), batch_size):
                batch = needed[offset:min(offset + batch_size, chunk_budget)]
                vectors = embed([b.text for _, b in batch])
                if len(vectors) != len(batch):
                    raise ValueError("EMBEDDING_COUNT_MISMATCH")
                for (i, b), vector in zip(batch, vectors):
                    if len(vector) != self.contract["dimension"] or not all(math.isfinite(x) for x in vector):
                        raise ValueError("EMBEDDING_DIMENSION_OR_VALUE_MISMATCH")
                    cid = hashlib.sha256(canonical([expected, self.contract, i, b.text])).hexdigest()
                    citation = {"source_sha256": expected, "source_path": str(path),
                                "original_path": proof.get("original_path"), "page": b.page,
                                "locator": b.locator, "section": b.section,
                                "embedding_version": self.contract["embedding_version"],
                                "document_type": kind, "available_at": None,
                                "authority": "DEVELOPMENT_REPROCESSING_NO_SOURCE_APPROVAL"}
                    self.c.execute("INSERT OR IGNORE INTO chunks VALUES(?,?,?,?,?,?)",
                                   (cid, expected, i, b.text, canonical(citation).decode(), canonical(vector).decode()))
                self.c.execute("UPDATE documents SET completed_chunks=(SELECT COUNT(*) FROM chunks WHERE document_sha=?),updated_at=? WHERE sha256=?",
                               (expected, now(), expected))
                self.c.commit()
            count = self.c.execute("SELECT COUNT(*) FROM chunks WHERE document_sha=?", (expected,)).fetchone()[0]
            status = "SUCCEEDED" if count == len(blocks) else "PARTIAL"
            self.c.execute("UPDATE documents SET status=?,updated_at=? WHERE sha256=?", (status, now(), expected))
            self.c.commit()
            return {"status": status, "sha256": expected, "chunks": count, "expected_chunks": len(blocks)}
        except Exception as error:
            self.c.execute("UPDATE documents SET status='FAILED',error=?,category=?,updated_at=? WHERE sha256=?",
                           (str(error)[:2000], failure_category(error), now(), expected))
            self.c.commit()
            return {"status": "FAILED", "sha256": expected, "category": failure_category(error), "error": str(error)[:2000]}

    def search(self, query, embed, *, top_k=5, document_sha=None, page=None):
        q = embed([query], query=True)[0]
        conditions = ["d.status='SUCCEEDED'"]
        args = []
        if document_sha:
            conditions.append("c.document_sha=?")
            args.append(document_sha)
        results = []
        verified_sources = {}
        for row in self.c.execute("SELECT c.* FROM chunks c JOIN documents d ON c.document_sha=d.sha256 WHERE " + " AND ".join(conditions), args):
            citation = json.loads(row["citation"])
            if page is not None and citation["page"] != page:
                continue
            path = guarded(citation["source_path"])
            if path not in verified_sources:
                verified_sources[path] = sha_file(path)
            if verified_sources[path] != citation["source_sha256"]:
                continue  # Changed input is not usable evidence.
            v = json.loads(row["vector"])
            norms = math.sqrt(sum(x*x for x in q)) * math.sqrt(sum(x*x for x in v))
            similarity = sum(x*y for x, y in zip(q, v)) / norms if norms else 0.0
            results.append({"chunk_id": row["id"], "text": row["text"], "cosine_similarity": similarity,
                            "score_kind": "COSINE_RELEVANCE_NOT_QC_PROBABILITY", "citation": citation})
        return sorted(results, key=lambda r: (-r["cosine_similarity"], r["chunk_id"]))[:top_k]

    def summary(self):
        return {"collection": "isolated-sqlite:" + str(self.path),
                "counts": dict(self.c.execute("SELECT status,COUNT(*) FROM documents GROUP BY status")),
                "chunks": self.c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
                "failure_categories": dict(self.c.execute("SELECT category,COUNT(*) FROM documents WHERE status='FAILED' GROUP BY category")),
                "approved": False, "production_publication": False}

    def close(self):
        self.c.close()


def parser_review(path, kind):
    """Capture completeness warnings rather than treating partial PDF text as complete."""
    messages = []
    class Capture(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())
    handler = Capture()
    log = logging.getLogger("pypdf")
    log.addHandler(handler)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            units = parse(Path(path))
            blocks = semantic_blocks(units, kind)
            messages.extend(str(w.message) for w in caught)
        if not blocks:
            raise ValueError("EMPTY_CHUNKS")
        incomplete = any("uninterpretable font" in m or "incomplete" in m.lower() for m in messages)
        return blocks, {"parser_status": "PARTIAL_EXTRACTION_REVIEW_REQUIRED" if incomplete else "PARSEABLE",
            "units": len(units), "chunks": len(blocks), "parser_warnings": sorted(set(messages)),
            "category": "PDF_FONT_MAPPING_REVIEW_REQUIRED" if incomplete else None,
            "extracted_text_sha256": hashlib.sha256(canonical([
                {"text": b.text, "page": b.page, "locator": b.locator, "section": b.section} for b in blocks])).hexdigest()}
    finally:
        log.removeHandler(handler)
