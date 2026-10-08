"""Read-only migration accounting and native July extent reconciliation."""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq

from app.rag.ingestion_recovery import canonical, guarded, now, readonly_ledger, sha_file


def review_migration(journal, receipts_root):
    with readonly_ledger(journal) as c:
        scopes = [dict(r) for r in c.execute("SELECT name,source,target,state FROM scopes ORDER BY name")]
        accounting = [dict(r) for r in c.execute("SELECT scope,status,COUNT(*) AS files,SUM(bytes) AS bytes FROM files GROUP BY scope,status")]
        invalid = c.execute("SELECT COUNT(*) FROM files WHERE status!='VERIFIED' OR sha256 IS NULL OR length(sha256)!=64").fetchone()[0]
    receipts = []
    for scope in scopes:
        receipt_path = guarded(Path(receipts_root) / ("verification-" + scope["name"] + ".json"), receipts_root)
        receipt = json.loads(receipt_path.read_bytes())
        expected = sum(r["files"] for r in accounting if r["scope"] == scope["name"])
        derived = []
        errors = receipt.get("errors", [])
        # The target also contains newly generated review snapshots. These
        # cannot be classified as missing copies or silently deleted.
        additive_valid = bool(errors) and scope["name"] == "integrated_lake"
        for error in errors:
            try:
                path = guarded(error["path"], scope["target"])
                allowed = guarded(Path(scope["target"]) / "metadata" / "facility_registry", scope["target"])
                if error.get("kind") != "target" or error.get("error") != "UNINVENTORIED_FILE" or not path.is_relative_to(allowed):
                    raise ValueError("UNEXPECTED_COPY_ERROR")
                manifest_path = path.parent / "manifest.json"
                manifest = json.loads(manifest_path.read_bytes())
                if manifest.get("status") != "PUBLISHED_REVIEW_ONLY" or manifest.get("operating_facility_count") is not None:
                    raise ValueError("UNRECOGNIZED_ADDITIVE_METADATA")
                current_sha = sha_file(path)
                valid_file = path.name == "manifest.json"
                if not valid_file:
                    specs = [v for v in manifest["files"].values() if Path(v["path"]) == path]
                    valid_file = len(specs) == 1 and specs[0]["sha256"] == current_sha and specs[0]["rows"] == pq.ParquetFile(path).metadata.num_rows
                if not valid_file:
                    raise ValueError("DERIVED_METADATA_HASH_OR_FOOTER_CHANGED")
                derived.append({"path": str(path), "sha256": current_sha, "manifest_sha256": sha_file(manifest_path),
                                "status": "ADDITIVE_PUBLISHED_REVIEW_METADATA_REVERIFIED", "checked_at": now()})
            except (ValueError, KeyError, TypeError, OSError):
                additive_valid = False
        valid = scope["state"] == "COPY_VERIFIED" and ((receipt.get("status") == "VERIFIED_NOT_CUTOVER" and errors == []) or additive_valid)
        valid = valid and receipt.get("file_counts", {}).get("source", {}).get("files") == expected and receipt.get("file_counts", {}).get("target", {}).get("files") == expected + len(derived)
        receipts.append({"scope": scope["name"], "path": str(receipt_path), "sha256": sha_file(receipt_path),
                         "checked_at": receipt.get("checked_at"), "expected_files": expected,
                         "passed": valid, "original_receipt_status": receipt.get("status"), "additive_derived_files": derived,
                         "verification_basis": receipt.get("hash_basis"),
                         "technical_resolution": "COPY_CORPUS_PRIOR_RESCAN_PLUS_FRESH_ADDITIVE_METADATA" if additive_valid else "PRIOR_COPY_INVENTORY_RESCAN"})
    return {"schema_version": "migration-preservation-readonly-review-v1", "checked_at": now(),
            "scopes": scopes, "scope_count": len(scopes), "ledger_accounting": accounting,
            "files": sum(r["files"] for r in accounting), "bytes": sum(r["bytes"] or 0 for r in accounting),
            "invalid_hash_or_unverified_ledger_rows": invalid, "rescan_receipts": receipts,
            "status": "PASS" if invalid == 0 and all(r["passed"] for r in receipts) else "FAILED",
            "passed": sum(r["passed"] for r in receipts), "failed": invalid + sum(not r["passed"] for r in receipts),
            "hash_scope": "COPY_AND_DESTINATION_HASH_LEDGER_PLUS_PRIOR_INVENTORY_RESCAN; NOT_A_NEW_1_89TB_REHASH",
            "source_deleted": False, "cutover_performed": False}


def native_extent(channel):
    grain = channel["grain"]
    count = channel["raw_rows"]
    result = {"grain": grain, "raw_rows": count,
              "first_native_clock": channel.get("first_valid_native_clock"),
              "last_native_clock": channel.get("last_valid_native_clock"),
              "source_clock_approved": False, "operational_gap_cause": None,
              "source_QC_interpreted": False, "approved": False}
    if count == 0:
        return {**result, "status": "NO_CURRENT_HELD_ROWS", "trailing_gap_native_seconds": None}
    grid = channel.get("interval_and_grid_diagnostic", {})
    interval = grid.get("representative_interval_microseconds")
    last = channel.get("last_valid_native_clock")
    if not interval or not last:
        return {**result, "status": "CADENCE_OR_EXTENT_UNRESOLVED", "trailing_gap_native_seconds": None}
    month = datetime.strptime(grain["month"], "%Y-%m")
    end = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_native = datetime.fromisoformat(last)
    next_slot = last_native + timedelta(microseconds=interval)
    gap = max(0.0, (end - next_slot).total_seconds())
    return {**result, "status": "TRAILING_NATIVE_EXTENT_GAP_CANDIDATE" if gap else "END_EXTENT_REACHES_NATIVE_MONTH_BOUNDARY",
            "representative_interval_microseconds_unapproved": interval,
            "next_native_slot_candidate": next_slot.isoformat(), "native_month_end_exclusive": end.isoformat(),
            "trailing_gap_native_seconds": gap,
            "gap_interpretation": "HELD_FILE_EXTENT_ONLY_NOT_CONFIRMED_SENSOR_OUTAGE_OR_SCHEDULE"}


def review_july(manifest_path, metrics_path, *, full_hash=True):
    manifest = json.loads(guarded(manifest_path).read_bytes())
    metrics = json.loads(guarded(metrics_path).read_bytes())
    manifest_sha = sha_file(manifest_path)
    if metrics.get("source_files_manifest_sha256") != manifest_sha:
        raise ValueError("SOURCE_METRICS_MANIFEST_HASH_MISMATCH")
    checks = []
    for entry in manifest["files"]:
        path = guarded(entry["path"])
        current_sha = sha_file(path) if full_hash else None
        st = path.stat()
        footer = pq.ParquetFile(path).metadata
        passed = st.st_size == entry["bytes"] and st.st_mtime_ns == entry["mtime_ns"] and footer.num_rows == entry["footer_rows"]
        if full_hash:
            passed = passed and current_sha == entry["sha256"]
        checks.append({"path": str(path), "source_group": entry["source_group"], "current_sha256": current_sha,
                       "expected_sha256": entry["sha256"], "footer_rows": footer.num_rows, "passed": passed})
    extents = [native_extent(r) for r in metrics["channels"]]
    sources = []
    for group in sorted({r["grain"]["source_group"] for r in extents}):
        rows = [r for r in extents if r["grain"]["source_group"] == group]
        sources.append({"source_group": group, "catalog_grains": len(rows), "held_grains": sum(r["raw_rows"] > 0 for r in rows),
            "raw_rows": sum(r["raw_rows"] for r in rows), "last_native_clock_distribution": dict(Counter(r["last_native_clock"] for r in rows if r["raw_rows"])),
            "status_counts": dict(Counter(r["status"] for r in rows))})
    families = defaultdict(list)
    for r in extents:
        g = r["grain"]
        key = canonical({k: v for k, v in g.items() if k != "source_group"})
        families[key].append(r)
    cross_source = [{"same_literal_grain_reference": json.loads(key), "sources": [
        {"source_group": r["grain"]["source_group"], "raw_rows": r["raw_rows"], "last_native_clock": r["last_native_clock"]} for r in rows],
        "identity_status": "CROSS_SOURCE_PHYSICAL_IDENTITY_NOT_APPROVED", "merge_performed": False}
        for key, rows in families.items() if len(rows) > 1 and len({r["last_native_clock"] for r in rows}) > 1]
    return {"schema_version": "July-preservation-extent-review-v1", "checked_at": now(),
            "source_manifest_sha256": manifest_sha, "metrics_sha256": sha_file(metrics_path), "source_file_checks": checks,
            "catalog_grains": len(extents), "held_grains": sum(r["raw_rows"] > 0 for r in extents),
            "no_held_grains": sum(r["raw_rows"] == 0 for r in extents), "source_summaries": sources,
            "extent_decisions": extents, "cross_source_extent_references": cross_source,
            "passed": sum(r["passed"] for r in checks), "failed": sum(not r["passed"] for r in checks),
            "status": "PASS" if all(r["passed"] for r in checks) else "FAILED",
            "approved": False, "completed_source_backfill": False,
            "next_required": ["Obtain the original July GD_OBS_ST extraction/export log and the post-cutoff source records",
                              "Approve the source clock, intended schedule and operational intervals before assigning outage or collection-rate semantics",
                              "Keep GR_OBS_ST holdings separate; later GR rows do not fill the GD source gap"]}
