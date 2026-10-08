"""Technical publication integrity and unavailable states, without the live DB."""
import hashlib
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import routes_technical_review
from app.services import technical_review_receipt as service


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False).encode()
    path.write_bytes(raw)
    return {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def publication(root):
    bundle_id = "review-test-1"
    bundle = root / bundle_id
    bundle.mkdir(parents=True)
    semantic = dict(status="BLOCKED_DRAFT", approved=False, input_rows=2, output_rows=2,
        exact_scope_keys=2, duplicate_scope_keys=0, invalid_grain_rows=0,
        enumeration_complete=True, unique_grain_coverage_complete=True,
        receipt_sha256="a"*64, universe_sha256="b"*64, live_run_id="facility-test",
        live_manifest_sha256="d"*64, reviewer_sha256="e"*64,as_of="2026-07-31",
        artifact_files={"contracts":{"sha256":"f"*64},"contract_index":{"sha256":"1"*64}},
        semantic_approvals=0, unit_application_approvals=0, timezone_approvals=0,
        qc_approvals=0, operational_rule_approvals=0,
        dictionary_reference_counts={"AUTO_VERIFIED_DICTIONARY_REFERENCE":2},
        source_group_counts={"GD_OBS_BU":{"AUTO_VERIFIED_DICTIONARY_REFERENCE":2}})
    receipt = dict(status="BLOCKED_DRAFT", approved=False, coverage_complete=True,
        universe=dict(rows=2, run_id="facility-test", scope_keys_sha256="b"*64,live_manifest_sha256="d"*64,as_of="2026-07-31"),
        technical_receipt_sha256="a"*64,reviewer_sha256="e"*64,contracts_sha256="f"*64,contract_index_sha256="1"*64,
        validation_errors=["SOURCE_SEMANTICS_NOT_APPROVED"])
    identity = dict(registry_run_id="facility-test", channel_census={"count":2,"sql_count":2,"exact_grain_and_held_rows_match":True,
        "missing_in_sql":0,"extra_in_sql":0},
        eligible_members=0, approved_identity_period_event_scopes=0)
    parent = dict(status="VERIFIED_TECHNICAL_REVIEW_ONLY", overall_verified=True, approved=False,
        common_scope_keys_sha256="b"*64,channel_month_count=2,run_id="facility-test")
    documents = dict(semantic_summary=semantic, semantic_receipt=receipt, identity_summary=identity, parent_verification=parent)
    files = {name: write(bundle/(name+".json"), value) for name,value in documents.items() if name != "parent_verification"}
    parent["verified_publication_inputs"] = {name:{k:entry[k] for k in ("sha256","bytes")} for name,entry in files.items()}
    files["parent_verification"] = write(bundle/"parent_verification.json",parent)
    manifest = dict(schema_version="technical-review-publication-1", bundle_id=bundle_id,
        status="TECHNICAL_REVIEW_ONLY", approved=False, files=files)
    write(bundle/"publication-manifest.json", manifest)
    (root/"latest-review.txt").write_text(bundle_id, encoding="ascii")
    return bundle, manifest, documents


def rewrite(bundle, manifest, documents, name):
    manifest["files"][name] = write(bundle/(name+".json"), documents[name])
    if name != "parent_verification":
        documents["parent_verification"]["verified_publication_inputs"] = {
            k:{field:manifest["files"][k][field] for field in ("sha256","bytes")}
            for k in service.REQUIRED_FILES if k != "parent_verification"}
        manifest["files"]["parent_verification"] = write(bundle/"parent_verification.json",documents["parent_verification"])
    write(bundle/"publication-manifest.json", manifest)


def blocked(root, code):
    with pytest.raises(service.ReviewReceiptUnavailable) as error:
        service.load_review_receipt(root)
    assert error.value.code == code


def test_verified_zero_is_real_and_only_small_publication_files_are_read(tmp_path, monkeypatch):
    bundle, _, _ = publication(tmp_path)
    # An unrelated large census ledger is never opened per API request.
    (bundle/"contracts.jsonl").write_text("DO NOT READ OR HASH THIS LEDGER")
    original = Path.read_bytes
    def guarded(path):
        if path.name == "contracts.jsonl":
            pytest.fail("whole ledger read on a request")
        return original(path)
    monkeypatch.setattr(Path,"read_bytes",guarded)
    result = service.load_review_receipt(tmp_path)
    assert result["status"] == "TECHNICAL_REVIEW_ONLY" and result["approved"] is False
    assert result["semantic"]["qc_approvals"] == 0
    assert len(result["verified_files"]) == 4
    assert result["ledger_integrity_scope"] == "PARENT_VERIFIED_AT_PUBLICATION_NOT_REHASHED_PER_REQUEST"


def test_missing_publication_returns_503_without_zero_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(service,"REVIEW_ROOT",tmp_path)
    app = FastAPI();app.include_router(routes_technical_review.router)
    response = TestClient(app).get("/api/data-lake/foundation/review-receipt")
    assert response.status_code == 503
    assert response.json()["detail"]["state"] == "UNAVAILABLE_OR_UNVERIFIED"
    assert "semantic" not in response.json()


@pytest.mark.parametrize("identifier",["../outside", "D:\\outside", "review-test-1/child", ".", "", "a/../review-test-1"])
def test_latest_pointer_is_only_a_relative_bundle_identifier(tmp_path, identifier):
    publication(tmp_path)
    (tmp_path/"latest-review.txt").write_text(identifier)
    blocked(tmp_path,"LATEST_REVIEW_ID_INVALID")


@pytest.mark.parametrize("relative",["../outside.json", "C:/outside.json", "a\\b.json", "./semantic_summary.json", "a//b.json"])
def test_file_paths_must_be_canonical_and_contained(tmp_path,relative):
    bundle,manifest,_ = publication(tmp_path)
    manifest["files"]["semantic_summary"]["path"] = relative
    write(bundle/"publication-manifest.json",manifest)
    blocked(tmp_path,"REVIEW_RELATIVE_PATH_INVALID" if relative != "a//b.json" else "REVIEW_RELATIVE_PATH_NOT_CANONICAL")


def test_tampered_summary_and_bad_manifest_are_unavailable(tmp_path):
    bundle,_,_ = publication(tmp_path)
    (bundle/"semantic_summary.json").write_text("{}")
    blocked(tmp_path,"REVIEW_PUBLICATION_FILE_HASH_MISMATCH")
    (bundle/"publication-manifest.json").write_text('{"status":"TECHNICAL_REVIEW_ONLY","status":"APPROVED"}')
    blocked(tmp_path,"REVIEW_DUPLICATE_JSON_KEY")


def test_duplicate_or_nonfinite_child_json_fails_after_matching_bytes_hash(tmp_path):
    bundle,manifest,_ = publication(tmp_path)
    for body,code in [('{"approved":false,"approved":true}',"REVIEW_DUPLICATE_JSON_KEY"),('{"value":NaN}',"REVIEW_NONFINITE_JSON_LITERAL")]:
        path = bundle/"semantic_summary.json";raw=body.encode();path.write_bytes(raw)
        manifest["files"]["semantic_summary"].update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        write(bundle/"publication-manifest.json",manifest)
        blocked(tmp_path,code)


def test_parent_verification_does_not_grant_approval(tmp_path):
    bundle,manifest,docs = publication(tmp_path)
    docs["parent_verification"]["approved"] = True
    rewrite(bundle,manifest,docs,"parent_verification")
    blocked(tmp_path,"PARENT_TECHNICAL_VERIFICATION_INCOMPLETE")
    docs["parent_verification"]["approved"] = False
    docs["parent_verification"]["overall_verified"] = False
    rewrite(bundle,manifest,docs,"parent_verification")
    blocked(tmp_path,"PARENT_TECHNICAL_VERIFICATION_INCOMPLETE")


def test_mismatched_census_approval_or_dependency_never_serves_mixed_summary(tmp_path):
    bundle,manifest,docs = publication(tmp_path)
    docs["identity_summary"]["channel_census"]["count"] = 3
    rewrite(bundle,manifest,docs,"identity_summary")
    blocked(tmp_path,"REVIEW_CENSUS_SCOPE_INCONSISTENT")
    docs["identity_summary"]["channel_census"]["count"] = 2
    rewrite(bundle,manifest,docs,"identity_summary")
    docs["semantic_summary"]["qc_approvals"] = 1
    rewrite(bundle,manifest,docs,"semantic_summary")
    blocked(tmp_path,"REVIEW_APPROVAL_COUNTS_INVALID")
    docs["semantic_summary"]["qc_approvals"] = 0
    rewrite(bundle,manifest,docs,"semantic_summary")
    docs["semantic_receipt"]["technical_receipt_sha256"] = "c"*64
    rewrite(bundle,manifest,docs,"semantic_receipt")
    blocked(tmp_path,"REVIEW_RECEIPT_DEPENDENCY_MISMATCH")


def test_reparse_or_symlink_cannot_escape_publication_root(tmp_path):
    root = tmp_path/"root";outside = tmp_path/"outside"
    bundle,manifest,_ = publication(root)
    outside.mkdir();(outside/"payload.json").write_text("{}")
    try:
        (bundle/"alias").symlink_to(outside,target_is_directory=True)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    manifest["files"]["semantic_summary"]["path"]="alias/payload.json"
    write(bundle/"publication-manifest.json",manifest)
    blocked(root,"REVIEW_PATH_OUTSIDE_ROOT")


def test_reparse_flag_is_rejected_without_windows_symlink_privilege(tmp_path, monkeypatch):
    from types import SimpleNamespace
    bundle,_,_ = publication(tmp_path)
    original = Path.lstat
    def flagged(path):
        info = original(path)
        if path == bundle/"semantic_summary.json":
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=service.stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return info
    monkeypatch.setattr(Path,"lstat",flagged)
    blocked(tmp_path,"REVIEW_REPARSE_PATH_REJECTED")


def test_boolean_count_and_missing_blockers_do_not_look_complete(tmp_path):
    bundle,manifest,docs = publication(tmp_path)
    docs["semantic_summary"]["duplicate_scope_keys"] = False
    rewrite(bundle,manifest,docs,"semantic_summary")
    blocked(tmp_path,"REVIEW_CENSUS_SCOPE_INCONSISTENT")
    docs["semantic_summary"]["duplicate_scope_keys"] = 0
    rewrite(bundle,manifest,docs,"semantic_summary")
    docs["semantic_receipt"]["validation_errors"] = []
    rewrite(bundle,manifest,docs,"semantic_receipt")
    blocked(tmp_path,"REVIEW_SEMANTIC_BLOCKERS_MISSING")


def test_changed_summary_descriptor_cannot_reuse_previous_parent_verification(tmp_path):
    bundle,manifest,docs = publication(tmp_path)
    docs["semantic_summary"]["newly_exact_scoped_reference_rows"] = 99999
    manifest["files"]["semantic_summary"] = write(bundle/"semantic_summary.json",docs["semantic_summary"])
    write(bundle/"publication-manifest.json",manifest)
    blocked(tmp_path,"PARENT_VERIFIED_INPUT_HASH_MISMATCH")


def test_parent_common_scope_and_event_counts_must_be_exact(tmp_path):
    bundle,manifest,docs = publication(tmp_path)
    docs["parent_verification"]["common_scope_keys_sha256"] = "c"*64
    rewrite(bundle,manifest,docs,"parent_verification")
    blocked(tmp_path,"PARENT_VERIFIED_SCOPE_MISMATCH")
    docs["parent_verification"]["common_scope_keys_sha256"] = "b"*64
    rewrite(bundle,manifest,docs,"parent_verification")
    docs["identity_summary"]["report_scope_extension"] = dict(status="REVIEWED_ROWS",approved=False,
        reviewed_report_rows=2,tide_current_rows=2,buoy_rows=1,hf_rows=0,science_rows=0,
        newly_added_report_rows=0,exact_event_link_candidates=0,unlinked_rows=0,scope_description="Only this table")
    rewrite(bundle,manifest,docs,"identity_summary")
    blocked(tmp_path,"REPORT_EVENT_SCOPE_INVALID")
    docs["identity_summary"]["report_scope_extension"]["buoy_rows"] = 0
    rewrite(bundle,manifest,docs,"identity_summary")
    assert service.load_review_receipt(tmp_path)["identity"]["report_scope_extension"]["exact_event_link_candidates"] == 0


def test_asof_and_artifact_hash_links_are_not_separate_unchecked_claims(tmp_path):
    bundle,manifest,docs = publication(tmp_path)
    docs["semantic_receipt"]["universe"]["as_of"] = "2026-06-30"
    rewrite(bundle,manifest,docs,"semantic_receipt")
    blocked(tmp_path,"REVIEW_RECEIPT_DEPENDENCY_MISMATCH")
    docs["semantic_receipt"]["universe"]["as_of"] = "2026-07-31"
    docs["semantic_receipt"]["contracts_sha256"] = "2"*64
    rewrite(bundle,manifest,docs,"semantic_receipt")
    blocked(tmp_path,"REVIEW_RECEIPT_DEPENDENCY_MISMATCH")
