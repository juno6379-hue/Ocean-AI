from app.services.source_contract_review import exact_scope_key, review_contracts


SHA = "a" * 64
ADAPTER_SHA = "b" * 64
ST = "GD_OBS_ST(조위,해양관측소)"
BU = "GD_OBS_BU(해양관측부이)"
VBU = "GD_OBS_VBU(대형부이)"


def run(rows=None, entries=None, verified=(SHA, ADAPTER_SHA), adapters=None):
    rows = rows or [dict(source_group="GD_OBS_BU", station_code="HB_0001", item_code="CURRENT_DIRECT",
                         depth_step=None, depth_from=None, depth_to=None, month="2024-01", held_rows=4,
                         literal_flags={"MQC": {"G ": 4}}, approval_status="UNAPPROVED")]
    dictionary = {"stations": [dict(code="HB_0001", sheet=BU, sha256=SHA)], "items": entries or [
        dict(code="CURRENT_DIRECT", label="유향", sheet=BU, sha256=SHA, row=10),
        dict(code="CURRENT_DIRECT", label="유향(감천항에만 적용)", sheet=VBU, sha256=SHA, row=30)]}
    return review_contracts(rows, dictionary, adapters or {"GD_OBS_BU": dict(family="GD_OBS_BU", evidence_sha256=ADAPTER_SHA)}, verified)


def test_unknown_station_prefix_exact_source_worksheet_resolves_reference_without_approval():
    result = run()
    row = result["contracts"][0]
    assert row["dictionary_reference"]["status"] == "AUTO_VERIFIED_DICTIONARY_REFERENCE"
    assert row["dictionary_reference"]["source_label_candidates"] == ["유향"]
    assert row["source_qc"]["literal_flags"] == {"MQC": {"G ": 4}}
    assert not row["approved"]
    assert row["unit"]["approved_standard_unit"] is None
    assert row["timezone_name"] is None


def test_wrong_source_family_never_borrows_dictionary():
    rows = [dict(source_group="GR_OBS_ST", station_code="DT_0001", item_code="CURRENT_DIRECT", month="2024-01")]
    assert run(rows=rows)["contracts"][0]["dictionary_reference"]["status"] == "SOURCE_ADAPTER_UNVERIFIED"


def test_same_source_item_two_explicit_units_is_conflict():
    entries = [dict(code="CURRENT_DIRECT", label="유향", source_unit=unit, sheet=BU, sha256=SHA)
               for unit in ("degree", "radian")]
    assert run(entries=entries)["contracts"][0]["dictionary_reference"]["status"] == "DICTIONARY_REFERENCE_CONFLICT"


def test_unverified_dictionary_or_adapter_hash_cannot_auto_verify():
    assert run(verified=(ADAPTER_SHA,))["contracts"][0]["dictionary_reference"]["status"] == "DICTIONARY_SOURCE_HASH_UNVERIFIED"
    assert run(verified=(SHA,))["contracts"][0]["dictionary_reference"]["status"] == "SOURCE_ADAPTER_UNVERIFIED"


def test_multi_worksheet_family_needs_station_worksheet_not_prefix_guess():
    rows = [dict(source_group="GD_OBS_ST_MONTHLY", station_code="DT_UNKNOWN", item_code="WATER_TEMP", month="2024-01")]
    entries = [dict(code="WATER_TEMP", label="수온", sheet=sheet, sha256=SHA)
               for sheet in (ST, "GD_OBS_ST(해양과학기지)")]
    result = run(rows=rows, entries=entries, adapters={"GD_OBS_ST_MONTHLY": dict(family="GD_OBS_ST", evidence_sha256=ADAPTER_SHA)})
    assert result["contracts"][0]["dictionary_reference"]["status"] == "WORKSHEET_SCOPE_UNRESOLVED"


def test_depth_null_numeric_and_text_are_distinct_grains_and_duplicate_is_blocked():
    row = dict(source_group="GD_OBS_BU", station_code="HB_0001", item_code="CURRENT_DIRECT", month="2024-01")
    assert len({exact_scope_key(dict(row, depth_step=v)) for v in (None, 0, "0", "")}) == 4
    result = run(rows=[row, row])
    assert result["summary"]["duplicate_scope_keys"] == 1
    assert result["summary"]["enumeration_complete"] is True
    assert result["summary"]["coverage_complete"] is False
    assert result["summary"]["unique_grain_coverage_complete"] is False
    assert all("DUPLICATE_EXACT_CHANNEL_MONTH_GRAIN" in r["blockers"] for r in result["contracts"])


def test_replay_receipt_changes_with_flags_and_never_converts_input_approval():
    a = run()
    b = run(rows=[dict(source_group="GD_OBS_BU", station_code="HB_0001", item_code="CURRENT_DIRECT", month="2024-01",
                       literal_flags={"MQC": {"G": 4}}, approval_status="APPROVED")])
    assert a["summary"]["receipt_sha256"] != b["summary"]["receipt_sha256"]
    assert b["summary"]["qc_approvals"] == 0
    assert b["contracts"][0]["approved"] is False


def test_missing_station_and_invalid_month_never_verify_grain():
    rows = [dict(source_group="GD_OBS_BU", station_code=None, item_code="CURRENT_DIRECT", month="2024-13")]
    record = run(rows=rows)["contracts"][0]
    assert record["grain_validation"] == "INVALID_KEY"
    assert "EXACT_CHANNEL_MONTH_KEY_INCOMPLETE_OR_INVALID" in record["blockers"]
    assert run(rows=rows)["summary"]["coverage_complete"] is False


def test_signed_hf_velocity_is_not_rejected_as_a_fixed_station_speed_or_mapped_by_name():
    rows = [dict(source_group="HF_RADAR", station_code="HF_1", item_code="RADIAL_VELOCITY",
                 month="2024-01", signed_velocity=-45, source_unit="cm/s", literal_flags={"QC": "OK"})]
    record = run(rows=rows)["contracts"][0]
    assert record["dictionary_reference"]["status"] == "SOURCE_ADAPTER_UNVERIFIED"
    assert record["semantic_mapping"]["approved_standard_variable"] is None
    assert record["source_qc"]["literal_flags"] == {"QC": "OK"}
    assert not any("NEGATIVE" in blocker for blocker in record["blockers"])


def test_empty_scope_has_enumeration_complete_without_complete_grain_coverage():
    result = review_contracts([], {"stations": [], "items": []}, {}, [])
    assert result["summary"]["enumeration_complete"] is True
    assert result["summary"]["coverage_complete"] is False
