"""Small immutable review-state backup and disposable restoration verification.

This is not a PostgreSQL disaster-recovery backup or a source/vector copy. It
preserves selected non-secret review artifacts and consistent small SQLite
queues. Full DB dumps, large source copies and operational cutover are separate.
"""
import json
import shutil
import sqlite3
from pathlib import Path

from app.rag.ingestion_recovery import canonical, guarded, now, readonly_ledger, sha_file
import hashlib

ROLES = {"MANIFEST", "POLICY", "RECEIPT", "POINTER", "SCHEMA", "QUEUE_DB"}
SECRET_KEYS = {"token", "password", "api_key", "api_identities", "database_url", "mdc_pwd"}


def secret_keys(value):
    if isinstance(value, dict):
        return any(str(k).lower() in SECRET_KEYS or secret_keys(v) for k, v in value.items())
    if isinstance(value, list):
        return any(secret_keys(v) for v in value)
    return False


def sqlite_readonly_export(path, destination):
    """Schema and counts only; no operational credentials or observation payloads."""
    with readonly_ledger(path) as c:
        schemas = [{"name": r["name"], "sql": r["sql"]} for r in c.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        counts = {r["name"]: c.execute('SELECT COUNT(*) FROM "' + r["name"].replace('"', '""') + '"').fetchone()[0] for r in schemas}
    body = {"checked_at": now(), "source_path": str(guarded(path)), "schemas": schemas,
            "counts": counts, "data_included": False, "scope": "SCHEMA_AND_COUNTS_NOT_FULL_RESTORE"}
    guarded(destination).write_bytes(canonical(body))
    return body


def create_backup(destination, inputs, *, max_total_bytes=64 * 1024 * 1024):
    root = guarded(destination)
    if root.exists() and any(root.iterdir()):
        raise ValueError("BACKUP_DESTINATION_NOT_EMPTY")
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    total = 0
    for index, spec in enumerate(inputs):
        role = spec.get("role")
        if role not in ROLES:
            raise ValueError("BACKUP_ROLE_NOT_ALLOWED")
        source = guarded(spec["path"])
        if source.name.lower().startswith(".env"):
            raise ValueError("SECRET_CONFIGURATION_BACKUP_FORBIDDEN")
        if source.stat().st_size + total > max_total_bytes:
            raise ValueError("SMALL_BACKUP_BUDGET_EXCEEDED")
        if source.suffix == ".json" and secret_keys(json.loads(source.read_bytes())):
            raise ValueError("SECRET_KEYS_BACKUP_FORBIDDEN")
        target = guarded(root / f"{index:03d}-{source.name}", root)
        if role == "QUEUE_DB":
            with readonly_ledger(source) as original, sqlite3.connect(target) as restored:
                original.backup(restored)
                if restored.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("QUEUE_BACKUP_INTEGRITY_FAILED")
            # SQLite backup is a transaction snapshot; its file bytes need not
            # equal the live DB file when that DB has WAL/concurrent commits.
            source_sha = None
        else:
            source_sha = sha_file(source)
            shutil.copyfile(source, target)
            if sha_file(source) != source_sha or sha_file(target) != source_sha:
                raise ValueError("BACKUP_SOURCE_CHANGED_OR_HASH_MISMATCH")
        total += target.stat().st_size
        if total > max_total_bytes:
            raise ValueError('SMALL_BACKUP_BUDGET_EXCEEDED_DURING_SNAPSHOT')
        entries.append({"role": role, "original_path": str(source), "relative_path": target.name,
                        "source_sha256": source_sha, "sha256": sha_file(target), "bytes": target.stat().st_size})
    manifest = {"schema_version": "small-review-state-backup-v1", "created_at": now(), "entries": entries,
                "total_bytes": total, "full_database_restore": False, "source_vectors_backed_up": False,
                "production_cutover": False}
    (root / "manifest.json").write_bytes(canonical(manifest))
    return manifest


def restore_check(backup, destination):
    source = guarded(backup)
    target_root = guarded(destination)
    if source == target_root or target_root.exists():
        raise ValueError("DISPOSABLE_RESTORE_DESTINATION_MUST_BE_NEW")
    manifest_path = guarded(source / 'manifest.json',source)
    if manifest_path.stat().st_size>1024*1024:raise ValueError('BACKUP_MANIFEST_TOO_LARGE')
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("schema_version") != "small-review-state-backup-v1":
        raise ValueError("BACKUP_MANIFEST_SCHEMA_INVALID")
    checked = []
    # Validate every source and destination before writing any restored file.
    pairs = []
    for row in manifest.get("entries", []):
        if not isinstance(row, dict) or row.get("role") not in ROLES:
            raise ValueError("BACKUP_ENTRY_INVALID")
        path = guarded(source / row["relative_path"], source)
        dest = guarded(target_root / row["relative_path"], target_root)
        if path.stat().st_size != row["bytes"] or sha_file(path) != row["sha256"]:
            raise ValueError("BACKUP_HASH_MISMATCH")
        pairs.append((row, path, dest))
    target_root.mkdir(parents=True)
    for row, path, dest in pairs:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        if sha_file(dest) != row["sha256"]:
            raise ValueError("RESTORE_HASH_MISMATCH")
        sqlite_status = None
        if row["role"] == "QUEUE_DB":
            with readonly_ledger(dest) as c:
                sqlite_status = c.execute("PRAGMA integrity_check").fetchone()[0]
            if sqlite_status != "ok":
                raise ValueError("RESTORE_SQLITE_INTEGRITY_FAILED")
            if sqlite_logical_digest(path) != sqlite_logical_digest(dest):
                raise ValueError("RESTORE_SQLITE_LOGICAL_STATE_MISMATCH")
        checked.append({"relative_path": row["relative_path"], "sha256": row["sha256"], "hash_match": True,
                        "sqlite_integrity": sqlite_status})
    receipt = {"schema_version": "small-review-state-restore-v1", "checked_at": now(), "status": "PASS",
               "backup_manifest_sha256": sha_file(source / "manifest.json"), "restored_entries": checked,
               "production_paths_changed": False, "full_database_restore": False,
               "next_required": ["Perform a separately reviewed PostgreSQL dump/restore rehearsal before production recovery",
                                 "Verify source/vector manifests and exact path pointers before any service restart"]}
    (target_root / "restore-receipt.json").write_bytes(canonical(receipt))
    return receipt


def sqlite_logical_digest(path, *, max_rows=10000):
    """Logical schema/row digest without exposing queue row payloads."""
    tables = {}
    with readonly_ledger(path) as c:
        for row in c.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            table = row['name']
            values = c.execute('SELECT * FROM "' + table.replace('"', '""') + '" LIMIT ?', (max_rows + 1,)).fetchall()
            if len(values) > max_rows:
                raise ValueError('SMALL_QUEUE_LOGICAL_REVIEW_LIMIT_EXCEEDED')
            canonical_rows = []
            for value in values:
                canonical_rows.append(canonical([{'type': type(v).__name__, 'value': v.hex() if isinstance(v, bytes) else v} for v in value]))
            tables[table] = {'schema_sha256': hashlib.sha256(row['sql'].encode()).hexdigest(),
                'rows': len(values), 'row_digest': hashlib.sha256(b'\n'.join(sorted(canonical_rows))).hexdigest()}
    return tables
