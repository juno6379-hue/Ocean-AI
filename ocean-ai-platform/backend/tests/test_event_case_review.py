import pytest

from app.services import event_case_review as m
from app.rag.ingestion_recovery import sha_file
from app.rag.report_parser import Unit


def test_station_qualified_serial_and_day_headers_do_not_become_utc_episode(tmp_path, monkeypatch):
    p = tmp_path / "history.hwp"; p.write_bytes(b"immutable native source")
    units = [Unit("인천 조위관측소", locator="heading:1"), Unit("1326", locator="inventory:1"),
             Unit("2019.02.27.", locator="date:1"), Unit("‘19.02.27.", locator="date:2"),
             Unit("수온염분계 교체(SN: 118→1276)", locator="action:1"),
             Unit("군산 조위관측소", locator="heading:2"), Unit("‘20.02.20.-02.21.", locator="date:3"),
             Unit("수온염분계 교체 (S/N: 1326 → 333)", locator="action:2")]
    monkeypatch.setattr(m, "parse", lambda _: units)
    r = m.native_serial_claims(p, sha_file(p))
    assert len(r["claims"]) == 3
    assert r["claims"][0]["inventory_date_claim"]["literal"] == "2019.02.27."
    assert r["claims"][0]["reported_action_date_or_header"] is None
    assert r["claims"][1]["station_heading"]["literal"] == "인천 조위관측소"
    assert r["claims"][2]["station_heading"]["literal"] == "군산 조위관측소"
    assert r["claims"][0]["station_qualified_instrument_candidate"] != r["claims"][2]["station_qualified_instrument_candidate"]
    assert all(c["approved"] is False for c in r["claims"])
    assert r["claims"][2]["reported_action_date_or_header"]["utc"] is None


def test_native_history_tamper_prevents_review(tmp_path):
    p = tmp_path / "history.hwp"; p.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        m.native_serial_claims(p, "0" * 64)
