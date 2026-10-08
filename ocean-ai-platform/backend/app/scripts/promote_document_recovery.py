"""Generate/validate a recovery promotion plan; writes require --apply and a real operator."""
import argparse
import json
import os
from pathlib import Path

from starlette.requests import Request

from app.rag.ingestion_recovery import canonical, guarded
from app.rag.recovery_promotion import build_promotion_plan, validate_plan, apply_plan, rollback_plan


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--recovery", type=Path)
    p.add_argument("--ledger", type=Path)
    p.add_argument("--contract", type=Path)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--rollback-receipt", type=Path)
    a = p.parse_args()
    plan_path = guarded(a.plan)
    if all((a.recovery, a.ledger, a.contract)):
        if plan_path.exists():
            raise ValueError("IMMUTABLE_PROMOTION_PLAN_ALREADY_EXISTS")
        plan = build_promotion_plan(a.recovery, a.ledger, a.contract)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_bytes(canonical(plan))
    else:
        plan = json.loads(plan_path.read_bytes())
    if a.apply or a.rollback_receipt:
        token = os.getenv("OCEAN_RAG_PROMOTION_TOKEN", "")
        request = Request({"type": "http", "headers": [(b"authorization", ("Bearer " + token).encode())]})
        if a.apply and a.rollback_receipt:raise ValueError('APPLY_AND_ROLLBACK_ARE_EXCLUSIVE')
        result = rollback_plan(plan,json.loads(guarded(a.rollback_receipt).read_bytes()),request) if a.rollback_receipt else apply_plan(plan, request)
    else:
        result = validate_plan(plan)
    print(json.dumps({k:v for k,v in result.items() if k != "documents"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
