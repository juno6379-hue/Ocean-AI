# 파일 역할: 초기 품질검사 규칙 정의를 등록합니다.
from app.core.database import SessionLocal
from app.models.domain import QCRuleDefinition
from app.services.qc_rule_engine import catalog, ENGINE_VERSION, GUIDE_SHA256
import argparse
import json

RULES = [
    ("TIDE_RANGE_V1", "조위 범위 검사", ["TIDE"], {"min": -500, "max": 2000}),
    ("WAVE_RANGE_V1", "파고 범위 검사", ["WAVE"], {"min": 0, "max": 30}),
]

def guide_rule_templates():
    """Inactive references; no station unit, clock, baseline or approval invented."""
    reference = catalog()
    return [{"qc_rule_id": "GUIDE2023_" + r["kind"], "qc_rule_name": r["name_ko"],
        "qc_rule_group": r["strength"], "applicable_variable": [v for v, item in reference["items"].items() if r["kind"] in item["applicable_rules"] or r["kind"] in {"LO", "DE", "PO"}],
        "algorithm_description": "2023.12 guide reference; explicit source-specific configuration required; not operating approval",
        "threshold_definition": {"kind": r["kind"], "parameters": {}, "provenance": {"guide_sha256": GUIDE_SHA256, "pdf_pages": r["pdf_pages"], "profile_id": None, "configuration_reference": None}},
        "rule_version": ENGINE_VERSION, "active": False} for r in reference["rules"]]


def seed_qc_rules(db=None):
    owned = db is None
    if owned:
        db = SessionLocal()
    try:
        added = 0
        for rule_id, name, variables, threshold in RULES:
            if db.query(QCRuleDefinition).filter(QCRuleDefinition.qc_rule_id == rule_id, QCRuleDefinition.rule_version == "1.0").first():
                continue
            db.add(QCRuleDefinition(qc_rule_id=rule_id, qc_rule_name=name, qc_rule_group="RANGE", applicable_variable=variables, algorithm_description="value is outside configured range", threshold_definition=threshold, rule_version="1.0", active=True))
            added += 1
        for template in guide_rule_templates():
            if not db.query(QCRuleDefinition).filter_by(qc_rule_id=template["qc_rule_id"], rule_version=template["rule_version"]).first():
                db.add(QCRuleDefinition(**template)); added += 1
        db.commit()
        return added
    finally:
        if owned: db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview inactive guide QC references; --apply explicitly writes the configured DB")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        print(f"QC rules added: {seed_qc_rules()}")
    else:
        print(json.dumps({"mode": "DRY_RUN", "guide_templates": guide_rule_templates(), "legacy_rules": RULES}, ensure_ascii=False, indent=2))
