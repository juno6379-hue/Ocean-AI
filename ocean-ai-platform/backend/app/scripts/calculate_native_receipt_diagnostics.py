"""Freeze source-native receipt clock diagnostics without changing an application DB.

Run from backend: python -B -m app.scripts.calculate_native_receipt_diagnostics
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.services.native_receipt_diagnostics import (
    DATA_ROOT, DEFAULT_ROOT, SOURCES, calculate_field_absence_coverage, calculate_source, canonical_bytes,
    guarded_path, publish_packets, read_json, sha_file, typed_grain,
)

JULY_MANIFEST = Path("D:/AI_Observation/outputs/monthly-report-matching/202607/metric-enrichment/source-file-manifest.json")
HISTORY_MANIFEST = Path("D:/AI_Observation/data_lake/spool_2001_2026/metadata/raw/manifest.json")


def native_receipt_coverage(args):
    """Sequential, resumable, one-month-at-a-time real BU/GR source processing."""
    import duckdb
    import pyarrow.parquet as pq
    view = args.snapshot_path
    catalog_path = view / "station-item-month-validation.parquet"
    assets_path = view / "file-only-timeseries.duckdb"
    catalog_sha, asset_sha = sha_file(catalog_path), sha_file(assets_path)
    catalog = pq.read_table(catalog_path).to_pylist()
    db = duckdb.connect(str(assets_path), read_only=True, config={"threads": 1, "memory_limit": "256MB"})
    try:
        cursor = db.execute("SELECT * FROM source_assets")
        columns = [column[0] for column in cursor.description]
        assets = [dict(zip(columns, values)) for values in cursor.fetchall()]
    finally:
        db.close()
    records, preserved = [], []
    for source in args.sources:
        if source not in {"GD_OBS_BU", "GR_OBS_ST"}:
            raise ValueError("NATIVE_RECEIPT_COVERAGE_SOURCE_UNSUPPORTED")
        by_month = {}
        for asset in assets:
            if asset["source_group"] != source:
                continue
            matches = re.findall(r"(?<!\d)(20\d{2}(?:0[1-9]|1[0-2]))(?!\d)", str(asset["source_path"]).replace("\\", "/").rsplit("/", 1)[-1])
            if len(matches) != 1:
                raise ValueError("SOURCE_ASSET_MONTH_AMBIGUOUS")
            month = matches[0][:4] + "-" + matches[0][4:]
            by_month.setdefault(month, []).append({"path": asset["parquet_path"], "sha256": asset["parquet_sha256"]})
        for month, entries in sorted(by_month.items()):
            pointer = args.output_root / args.snapshot / source / month / "published.json"
            if pointer.exists():
                # Preserve completed packets, and revalidate them rather than trusting existence.
                from app.services.native_receipt_diagnostics import receipt_diagnostics
                existing = receipt_diagnostics(source, month, month, snapshot=args.snapshot,
                                               root=args.output_root, source_root=args.source_root)
                if existing["state"] in {"INVALID_PACKET", "UNAVAILABLE", "UNAVAILABLE_PERIOD", "EMPTY_SCOPE"}:
                    raise ValueError("EXISTING_RECEIPT_PACKET_INVALID")
                preserved.append({"source": source, "month": month, "packet_receipts": existing["packet_receipts"]})
                continue
            print(json.dumps({"stage": "NATIVE_RECEIPT_MONTH_STARTED", "source": source, "month": month, "files": len(entries)}, ensure_ascii=False), flush=True)
            packets = calculate_source(entries, source, args.snapshot, args.source_root, {month})
            if len(packets) != 1 or packets[0]["month"] != month:
                raise ValueError("SOURCE_NATIVE_MONTH_HAS_NO_ROWS")
            packet = packets[0]
            expected = {typed_grain(row): row["held_rows"] for row in catalog if row["source_group"] == source and str(row["month"])[:7] == month and row["held_rows"] > 0}
            actual = {typed_grain(row): row["raw_rows"] for row in packet["channels"]}
            if expected != actual:
                raise ValueError("ACTUAL_RECEIPT_ROW_COUNTS_NOT_BOUND_TO_CATALOG")
            if sha_file(catalog_path) != catalog_sha or sha_file(assets_path) != asset_sha:
                raise ValueError("CATALOG_CHANGED_DURING_RECEIPT_SCAN")
            packet["count_validation"] = {"status": "EXACT_TYPED_GRAIN_CATALOG_COUNTS_MATCH", "catalog_path": str(catalog_path),
                                          "catalog_sha256": catalog_sha, "source_assets_path": str(assets_path), "source_assets_sha256": asset_sha}
            receipts = publish_packets(packets, args.output_root)
            records.extend(receipts)
            print(json.dumps({"stage": "NATIVE_RECEIPT_MONTH_FROZEN", "source": source, "month": month,
                              "channel_months": len(packet["channels"]), "raw_rows": packet["raw"]["raw_rows"],
                              "native_difference_mean_seconds": (packet["raw"]["difference_seconds"] or {}).get("mean")}, ensure_ascii=False), flush=True)
    return {"schema_version": "native-receipt-all-months-execution-1", "status": "CALCULATED_NATIVE_CLOCK_DIFFERENCE",
            "snapshot": args.snapshot, "approved": False, "operational_delay": False,
            "application_db_mutations": 0, "sources": args.sources, "preserved_packets": preserved,
            "new_packets": records, "new_packet_count": len(records), "finished_at": datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--source-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--july-manifest", type=Path, default=JULY_MANIFEST)
    parser.add_argument("--history-manifest", type=Path, default=HISTORY_MANIFEST)
    parser.add_argument("--snapshot", default=None)
    parser.add_argument("--sources", nargs="+", choices=sorted(SOURCES), default=sorted(SOURCES))
    parser.add_argument("--field-absence-coverage", action="store_true", help="GDST/VBU all asset months: schema/SHA/footer and frozen catalogue counts, no raw clock scan")
    parser.add_argument("--native-receipt-coverage", action="store_true", help="All actual BU/GR asset months sequentially; requires --sources GD_OBS_BU GR_OBS_ST")
    parser.add_argument("--snapshot-path", type=Path, default=None)
    args = parser.parse_args()
    if args.snapshot is None:
        from app.services.lake_browser import context
        args.snapshot = context()[0].name
    output_root = guarded_path(args.output_root, args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    start = datetime.now(timezone.utc).isoformat()
    if args.native_receipt_coverage:
        if args.snapshot_path is None:
            from app.services.lake_browser import context
            args.snapshot_path = context()[0]
        if args.snapshot_path.name != args.snapshot:
            raise ValueError("SNAPSHOT_PATH_MISMATCH")
        body = native_receipt_coverage(args)
        body["started_at"] = start
        data = canonical_bytes(body); digest = hashlib.sha256(data).hexdigest()
        path = output_root / f"native-coverage-execution-{digest}.json"
        with path.open("xb") as handle:
            handle.write(data)
        print(json.dumps({"stage": "COMPLETE_NATIVE_RECEIPT_COVERAGE", "path": str(path), "sha256": digest,
                          "new_packets": body["new_packet_count"]}, ensure_ascii=False), flush=True)
        return
    if args.field_absence_coverage:
        if args.snapshot_path is None:
            from app.services.lake_browser import context
            args.snapshot_path = context()[0]
        if args.snapshot_path.name != args.snapshot:
            raise ValueError("SNAPSHOT_PATH_MISMATCH")
        packets = calculate_field_absence_coverage(args.snapshot_path, args.source_root,
                  emit=lambda status: print(json.dumps(status, ensure_ascii=False), flush=True))
        # A copied full-row July packet is stronger evidence and remains immutable.
        packets = [packet for packet in packets if not (output_root / packet["snapshot"] / packet["source"] / packet["month"] / "published.json").exists()]
        receipts = publish_packets(packets, output_root)
        body = {"schema_version": "native-receipt-schema-absence-execution-1", "started_at": start,
                "finished_at": datetime.now(timezone.utc).isoformat(), "snapshot": args.snapshot,
                "status": "FIELD_ABSENT", "approved": False, "operational_delay": False,
                "computation_level": "SCHEMA_ONLY_RECEIPT_ABSENCE_WITH_FROZEN_CATALOG_COUNTS",
                "new_raw_clock_rows_scanned": 0, "packet_count": len(receipts), "receipts": receipts}
        data = canonical_bytes(body); digest = hashlib.sha256(data).hexdigest()
        path = output_root / f"absence-execution-{digest}.json"
        with path.open("xb") as handle:
            handle.write(data)
        print(json.dumps({"stage": "COMPLETE_FIELD_ABSENCE", "path": str(path), "sha256": digest, "new_packets": len(receipts)}, ensure_ascii=False), flush=True)
        return
    july, july_sha = read_json(args.july_manifest, args.july_manifest.parent)
    if july.get("month") != "2026-07" or not isinstance(july.get("files"), list):
        raise ValueError("JULY_SOURCE_MANIFEST_INVALID")
    histories, history_sha = read_json(args.history_manifest, args.source_root)
    records, input_manifests = [], [{"path": str(args.july_manifest), "sha256": july_sha},
                                    {"path": str(args.history_manifest), "sha256": history_sha}]
    for source in args.sources:
        if source == "HISTORICAL_RECONCILED":
            entries = [{**spec, "path": str(args.source_root / "spool_2001_2026" / spec["path"])}
                       for spec in histories["files"] if spec["path"].startswith("raw/reconciled_v1/")]
            months = None
        else:
            entries = [spec for spec in july["files"] if spec["source_group"] == source]
            months = {"2026-07"}
        print(json.dumps({"stage": "SOURCE_SCAN_STARTED", "source": source, "files": len(entries)}, ensure_ascii=False), flush=True)
        packets = calculate_source(entries, source, args.snapshot, args.source_root, months)
        for packet in packets:
            packet["input_manifests"] = input_manifests
        receipts = publish_packets(packets, output_root)
        records.extend(receipts)
        print(json.dumps({"stage": "SOURCE_FROZEN", "source": source, "months": len(receipts),
                          "channel_months": sum(record["channel_months"] for record in receipts),
                          "raw_rows": sum(record["raw_rows"] for record in receipts)}, ensure_ascii=False), flush=True)
    summary = {"schema_version": "native-receipt-diagnostics-execution-1", "snapshot": args.snapshot,
               "started_at": start, "finished_at": datetime.now(timezone.utc).isoformat(),
               "status": "CALCULATED_NATIVE_CLOCK_DIFFERENCE", "approved": False, "operational_delay": False,
               "verification_level": "FRESH_WHOLE_PRESERVED_PARQUET_SHA_FOOTER_BEFORE_AND_AFTER_SCAN",
               "original_deleted_csv_rechecked": False, "application_db_mutations": 0,
               "input_manifests": input_manifests, "packet_count": len(records),
               "channel_months": sum(record["channel_months"] for record in records),
               "raw_rows": sum(record["raw_rows"] for record in records), "receipts": records}
    data = canonical_bytes(summary)
    digest = hashlib.sha256(data).hexdigest()
    path = guarded_path(output_root / f"execution-{digest}.json", output_root)
    with path.open("xb") as handle:
        handle.write(data)
    print(json.dumps({"stage": "COMPLETE", "path": str(path), "sha256": digest,
                      "packets": len(records), "channel_months": summary["channel_months"],
                      "raw_rows": summary["raw_rows"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
