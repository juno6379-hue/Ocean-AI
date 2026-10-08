"""Exhaustive read-only backlog review; bounded isolated local embedding/retrieval."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from app.rag.ingestion_recovery import (RecoveryStore, backlog_snapshot, canonical,
    failure_category, guarded, local_embedder, now, parser_review, resolve_preserved, sha_file)
from app.rag.report_parser import parse, semantic_blocks


def write_json(path, body):
    path = guarded(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical(body))
    temporary.replace(path)


def run(ledger, contract_path, output, aliases, *, embed_documents=24, embed_chunks=10000):
    output = guarded(output)
    output.mkdir(parents=True, exist_ok=True)
    contract = json.loads(guarded(contract_path).read_bytes())
    snapshot = backlog_snapshot(ledger)
    write_json(output / "backlog-before.json", snapshot)
    # The audit visits every path; duplicate bytes reuse the exact parser result.
    # PDF passwords are never guessed and damaged originals are never rewritten.
    audit = []
    parser_cache = {}
    successful = set(snapshot["successful_checksums"])
    for index, row in enumerate(snapshot["backlog"]):
        reviewed = {"backlog_ordinal": index, "original_status": row["status"],
                    "original_reason": row.get("reason"), "document_type": row["document_type"],
                    "original_path": row["path"], "approved": False}
        try:
            proof = resolve_preserved(row, aliases)
            reviewed["preservation"] = proof
            reviewed["already_indexed_exact_content"] = proof["sha256"] in successful
            if proof["sha256"] not in parser_cache:
                try:
                    blocks, parser_result = parser_review(proof["path"], row["document_type"])
                    if sha_file(proof["path"]) != proof["sha256"]:
                        raise ValueError("SOURCE_CHECKSUM_CHANGED_DURING_PARSE")
                    parser_cache[proof["sha256"]] = parser_result
                except Exception as error:
                    parser_cache[proof["sha256"]] = {"parser_status": "BLOCKED", "category": failure_category(error),
                                                      "error": str(error)[:1500]}
            reviewed.update(parser_cache[proof["sha256"]])
        except Exception as error:
            reviewed.update({"parser_status": "NOT_EVALUATED", "category": failure_category(error), "error": str(error)[:1500]})
        audit.append(reviewed)
        # Durable append-only review journal; compact progress remains readable.
        with (output / "backlog-review.jsonl").open("ab") as f:
            f.write(canonical(reviewed) + b"\n")
        if index % 20 == 0 or index + 1 == len(snapshot["backlog"]):
            write_json(output / "progress.json", {"checked_at": now(), "phase": "EXHAUSTIVE_PRESERVATION_AND_PARSE",
                "reviewed_paths": index + 1, "total_paths": len(snapshot["backlog"]),
                "counts": dict(Counter(r["parser_status"] for r in audit))})
    # The final authoritative JSONL is exactly this run, not accumulated attempts.
    (output / "backlog-review.jsonl").write_bytes(b"".join(canonical(r) + b"\n" for r in audit))
    embedding_results = []
    store = RecoveryStore(output / "recovery.sqlite3", contract, source_ledger=ledger)
    try:
        embed = local_embedder(contract)
        chosen = {}
        for r in audit:
            if r["parser_status"] == "PARSEABLE":
                chosen.setdefault(r["preservation"]["sha256"], r)
        budget = embed_chunks
        # Complete small unique documents first, then preserve restartable partials.
        for r in sorted(chosen.values(), key=lambda r: (r["chunks"], r["preservation"]["sha256"]))[:embed_documents]:
            if budget <= 0:
                break
            before = store.summary()["chunks"]
            result = store.ingest(r["preservation"], r["document_type"], embed, chunk_budget=budget)
            embedding_results.append(result)
            budget -= store.summary()["chunks"] - before
            write_json(output / "progress.json", {"checked_at": now(), "phase": "ISOLATED_LOCAL_EMBEDDING",
                "reviewed_paths": len(audit), "total_paths": len(audit), "embedding_results": embedding_results,
                "collection": store.summary()})
        # Exact-citation retrieval tests: self query, PDF page/document filters,
        # nonexistent document filter and source-hash integrity.
        samples = []
        for row in store.c.execute("SELECT c.* FROM chunks c JOIN documents d ON c.document_sha=d.sha256 WHERE d.status='SUCCEEDED' GROUP BY c.document_sha ORDER BY c.document_sha LIMIT 7"):
            citation = json.loads(row["citation"])
            hits = store.search(row["text"][:400], embed, top_k=3, document_sha=row["document_sha"], page=citation["page"])
            samples.append({"query_sha256": hashlib.sha256(row["text"][:400].encode()).hexdigest(),
                "document_sha256": row["document_sha"], "expected_chunk_id": row["id"], "results": hits,
                "pass": bool(hits) and hits[0]["chunk_id"] == row["id"]})
        negatives = store.search("관측소 센서 점검", embed, document_sha="0" * 64)
        retrieval = {"checked_at": now(), "samples": samples, "negative_exact_document_filter_pass": negatives == [],
                     "status": "PASS" if samples and all(s["pass"] for s in samples) and negatives == [] else "REVIEW_REQUIRED",
                     "scope": "ISOLATED_ACTIVE_MODEL_CONTRACT_CITATION_AND_FILTER_SMOKE_NOT_DOMAIN_QA"}
        write_json(output / "retrieval-verification.json", retrieval)
    except Exception as error:
        write_json(output / "embedding-runtime-blocker.json", {"checked_at": now(), "category": failure_category(error), "error": str(error)})
    finally:
        collection = store.summary()
        store.close()
    after = backlog_snapshot(ledger)
    write_json(output / "backlog-after.json", after)
    summary = {"schema_version": "document-backlog-review-v1", "checked_at": now(), "approved": False,
        "production_ledger_changed": snapshot["snapshot_sha256"] != after["snapshot_sha256"],
        "source_ledger_counts": snapshot["counts"], "backlog_paths": len(audit),
        "preservation_hash_match_paths": sum(r.get("preservation", {}).get("status") == "HASH_MATCH" for r in audit),
        "parser_status_counts": dict(Counter(r["parser_status"] for r in audit)),
        "unique_content_status_counts": dict(Counter(r["parser_status"] for r in parser_cache.values())),
        "blocked_categories": dict(Counter(r.get("category") for r in audit if r["parser_status"] != "PARSEABLE")),
        "already_indexed_exact_content_paths": sum(r.get("already_indexed_exact_content", False) for r in audit),
        "isolated_collection": collection, "isolated_completed_content": collection["counts"].get("SUCCEEDED", 0),
        "embedding_results": embedding_results, "production_backlog_resolved": 0,
        "remaining_next": ["Promote independently verified recovery outputs through the normal authenticated production ingestion path",
            "Obtain original owner password/unprotected export for encrypted files", "Obtain intact export for damaged source",
            "Continue isolated run with the same contract and SQLite; PARTIAL checkpoints resume without duplicate vectors"],
        "evidence": [{"path": str(output / name), "sha256": sha_file(output / name)} for name in
                     ["backlog-review.jsonl", "backlog-before.json", "backlog-after.json"]]}
    write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alias", action="append", nargs=2, metavar=("SOURCE_ROOT", "PRESERVED_ROOT"), required=True)
    parser.add_argument("--embed-documents", type=int, default=24)
    parser.add_argument("--embed-chunks", type=int, default=10000)
    args = parser.parse_args()
    summary = run(args.ledger, args.contract, args.output, args.alias,
                  embed_documents=args.embed_documents, embed_chunks=args.embed_chunks)
    print(json.dumps({k: summary[k] for k in ("backlog_paths", "parser_status_counts", "isolated_completed_content", "production_ledger_changed")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
