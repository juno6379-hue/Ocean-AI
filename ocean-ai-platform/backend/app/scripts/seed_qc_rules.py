# 파일 역할: 초기 품질검사 규칙 정의를 등록합니다.
from app.core.database import SessionLocal
from app.models.domain import QCRuleDefinition

RULES = [
    ("TIDE_RANGE_V1", "조위 범위 검사", ["TIDE"], {"min": -500, "max": 2000}),
    ("WAVE_RANGE_V1", "파고 범위 검사", ["WAVE"], {"min": 0, "max": 30}),
]

def seed_qc_rules():
    db = SessionLocal()
    try:
        added = 0
        for rule_id, name, variables, threshold in RULES:
            if db.query(QCRuleDefinition).filter(QCRuleDefinition.qc_rule_id == rule_id, QCRuleDefinition.rule_version == "1.0").first():
                continue
            db.add(QCRuleDefinition(qc_rule_id=rule_id, qc_rule_name=name, qc_rule_group="RANGE", applicable_variable=variables, algorithm_description="value is outside configured range", threshold_definition=threshold, rule_version="1.0", active=True))
            added += 1
        db.commit(); print(f"QC rules added: {added}")
    finally: db.close()

if __name__ == "__main__": seed_qc_rules()
