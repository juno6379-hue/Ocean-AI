"""Small review-state backup and fresh disposable restoration check."""
import argparse
import json
from pathlib import Path

from app.services.operational_backup_review import create_backup, restore_check


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--backup", type=Path, required=True)
    p.add_argument("--restore", type=Path, required=True)
    p.add_argument("--source", nargs=2, action="append", metavar=("ROLE", "PATH"), required=True)
    p.add_argument("--max-bytes", type=int, default=64*1024*1024)
    a = p.parse_args()
    manifest = create_backup(a.backup, [{"role": role, "path": path} for role, path in a.source], max_total_bytes=a.max_bytes)
    receipt = restore_check(a.backup, a.restore)
    print(json.dumps({"status": receipt["status"], "files": len(manifest["entries"]), "bytes": manifest["total_bytes"],
                      "production_paths_changed": False, "full_database_restore": False}))


if __name__ == "__main__":
    main()
