import json

import pytest

from app.services.development_stage_review import get_development_stage_review
from app.rag.ingestion_recovery import sha_file


def index(tmp_path, evidence, **extra):
    (tmp_path / "stage-index.json").write_text(json.dumps({"stages": [{"stage_id": 4, "verification": "VERIFIED", "evidence": evidence, **extra}]}))


def test_missing_stages_are_unknown_and_never_complete(tmp_path):
    r = get_development_stage_review(tmp_path, ledger_path=tmp_path / "missing.db")
    assert len(r["stages"]) == 13
    assert all(s["verification"] == "UNKNOWN" for s in r["stages"])
    assert r["approved"] is False


def test_exact_pass_receipt_and_claims_do_not_grant_human_approval(tmp_path):
    p = tmp_path / "receipt.json";p.write_text('{"status":"PASS","passed":3,"failed":0}')
    index(tmp_path, [{"path": p.name, "sha256": sha_file(p)}], approval="APPROVED", operational_status="OPERATING")
    r = get_development_stage_review(tmp_path, ledger_path=tmp_path / "none.db")["stages"][3]
    assert r["verification"] == "VERIFIED"
    assert r["approval"] == r["operational_status"] == "UNKNOWN"
    p.write_text('{"status":"PASS","passed":4,"failed":0}')
    assert get_development_stage_review(tmp_path, ledger_path=tmp_path / "none.db")["stages"][3]["verification"] == "FAILED"


@pytest.mark.parametrize("evidence", ["wrong", ["wrong"], None, [{}]])
def test_malformed_evidence_does_not_crash(evidence, tmp_path):
    index(tmp_path, evidence)
    assert get_development_stage_review(tmp_path, ledger_path=tmp_path / "none.db")["stages"][3]["verification"] == "FAILED"


def test_bare_pass_without_test_denominator_is_partial(tmp_path):
    p = tmp_path / "r.json"; p.write_text('{"status":"PASS"}')
    index(tmp_path, [{"path": p.name, "sha256": sha_file(p)}])
    assert get_development_stage_review(tmp_path, ledger_path=tmp_path / "none.db")["stages"][3]["verification"] == "PARTIAL"


def test_duplicate_stage_cannot_silently_override(tmp_path):
    (tmp_path / "stage-index.json").write_text('{"stages":[{"stage_id":4,"evidence":[]},{"stage_id":4,"evidence":[]}]}')
    assert get_development_stage_review(tmp_path, ledger_path=tmp_path / "none.db")["stages"][3]["verification"] == "FAILED"


@pytest.mark.parametrize('value',[[],{},None,True])
def test_malformed_status_axis_stays_unknown(value,tmp_path):
    p=tmp_path/'receipt.json';p.write_text('{"status":"PASS","passed":1,"failed":0}')
    index(tmp_path,[{'path':p.name,'sha256':sha_file(p)}],implementation=value)
    assert get_development_stage_review(tmp_path,ledger_path=tmp_path/'none.db')['stages'][3]['implementation']=='UNKNOWN'
