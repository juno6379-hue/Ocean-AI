"""Read-only-DB manual comparison CLI; blocked inputs start no training."""
import argparse
import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import SessionLocal
from app.ml.comparison_runner import DatabaseAuthority, run_manual, _atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Train only if all approval and fixed-input gates pass")
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            if db.bind.dialect.name == "postgresql":
                db.execute(text("SET TRANSACTION READ ONLY"))
            with db.no_autoflush:
                result = run_manual(args.manifest, DatabaseAuthority(db, settings.DATASET_SNAPSHOT_DIR),
                                    args.job_root, execute=args.execute)
            db.rollback()
    except SQLAlchemyError as exc:
        # Avoid exposing connection strings or credentials in a diagnostic file.
        result = {"status": "BLOCKED", "training_started": False, "blockers": [
            {"code": "APPROVAL_AUTHORITY_UNAVAILABLE", "detail": type(exc).__name__}],
            "registered_models": 0, "deployed_models": 0}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(args.report, result)
    print(json.dumps({k: result.get(k) for k in ("status", "training_started", "job_id", "blockers")},
                     ensure_ascii=False, allow_nan=False))
    return 0 if result["status"] in {"PREFLIGHT_VERIFIED_CANDIDATE_INPUT_ONLY", "COMPARISON_COMPLETE_CANDIDATE_ONLY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
