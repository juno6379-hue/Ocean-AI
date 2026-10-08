import json
import sqlite3

import pytest

from app.services.operational_backup_review import create_backup, restore_check, sqlite_readonly_export
from app.rag.ingestion_recovery import sha_file


def test_small_backup_restores_hash_and_queue_integrity_without_operational_mutation(tmp_path):
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"approved":false,"status":"PENDING"}')
    queue = tmp_path / "queue.sqlite3"
    c = sqlite3.connect(queue)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE jobs(id PRIMARY KEY,status)")
    c.execute("INSERT INTO jobs VALUES(1,'PENDING')"); c.commit()
    manifest = create_backup(tmp_path / "backup", [{"role": "RECEIPT", "path": receipt}, {"role": "QUEUE_DB", "path": queue}])
    c.execute("INSERT INTO jobs VALUES(2,'RUNNING')"); c.commit()
    result = restore_check(tmp_path / "backup", tmp_path / "disposable")
    assert result["status"] == "PASS"
    assert result["production_paths_changed"] is False
    restored = sqlite3.connect(tmp_path / "disposable" / manifest["entries"][1]["relative_path"])
    assert restored.execute("SELECT * FROM jobs").fetchall() == [(1, "PENDING")]
    assert c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2
    c.close(); restored.close()


def test_backup_tamper_or_existing_restore_destination_rejected(tmp_path):
    p = tmp_path / "receipt.json"; p.write_text("{}")
    m = create_backup(tmp_path / "backup", [{"role": "RECEIPT", "path": p}])
    restored = tmp_path / "restore"; restored.mkdir()
    with pytest.raises(ValueError, match="MUST_BE_NEW"):
        restore_check(tmp_path / "backup", restored)
    (tmp_path / "backup" / m["entries"][0]["relative_path"]).write_text("evil")
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        restore_check(tmp_path / "backup", tmp_path / "fresh")
    assert not (tmp_path / "fresh").exists()


def test_secrets_and_large_source_copies_are_not_small_review_backup(tmp_path):
    p = tmp_path / ".env"; p.write_text("TOKEN=private")
    with pytest.raises(ValueError, match="SECRET_CONFIGURATION"):
        create_backup(tmp_path / "one", [{"role": "POLICY", "path": p}])
    p = tmp_path / "config.json"; p.write_text('{"nested":{"token":"private"}}')
    with pytest.raises(ValueError, match="SECRET_KEYS"):
        create_backup(tmp_path / "two", [{"role": "POLICY", "path": p}])
    p.write_text("{}")
    with pytest.raises(ValueError, match="BUDGET"):
        create_backup(tmp_path / "three", [{"role": "POLICY", "path": p}], max_total_bytes=1)


def test_schema_export_contains_counts_without_payload(tmp_path):
    p = tmp_path / "queue.sqlite3"; c = sqlite3.connect(p)
    c.execute("CREATE TABLE sensitive(value)"); c.execute("INSERT INTO sensitive VALUES('private')");c.commit();c.close()
    r = sqlite_readonly_export(p, tmp_path / "schema.json")
    assert r["counts"] == {"sensitive": 1}
    assert "private" not in (tmp_path / "schema.json").read_text()
