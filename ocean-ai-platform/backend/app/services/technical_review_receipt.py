"""Read an independently published technical review; no approval or DB mutations."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import hashlib
import json
import re
import stat

REVIEW_ROOT = Path(r"D:\AI_Observation\metadata\reviews")
MAX_JSON_BYTES = 1024 * 1024
REQUIRED_FILES = ("semantic_summary", "semantic_receipt", "identity_summary", "parent_verification")
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")


class ReviewReceiptUnavailable(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _fail(code):
    raise ReviewReceiptUnavailable(code)


def _inside(root, path):
    root, path = Path(root).resolve(), Path(path)
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        _fail("REVIEW_FILE_UNAVAILABLE")
    if not resolved.is_relative_to(root):
        _fail("REVIEW_PATH_OUTSIDE_ROOT")
    cursor = path
    while cursor != root:
        info = cursor.lstat()
        if cursor.is_symlink() or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            _fail("REVIEW_REPARSE_PATH_REJECTED")
        if cursor == cursor.parent:
            _fail("REVIEW_PATH_OUTSIDE_ROOT")
        cursor = cursor.parent
    return resolved


def _read_bytes(root, path, maximum):
    path = _inside(root, path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
        _fail("REVIEW_FILE_NOT_BOUNDED_REGULAR_FILE")
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(raw) != before.st_size:
        _fail("REVIEW_FILE_CHANGED_DURING_READ")
    return raw


def _json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                _fail("REVIEW_DUPLICATE_JSON_KEY")
            value[key] = item
        return value

    def invalid_constant(value):
        _fail("REVIEW_NONFINITE_JSON_LITERAL")

    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail("REVIEW_JSON_INVALID")
    if not isinstance(result, dict):
        _fail("REVIEW_JSON_OBJECT_REQUIRED")
    return result


def _relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        _fail("REVIEW_RELATIVE_PATH_INVALID")
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or any(p in {".", ".."} for p in value.split("/")):
        _fail("REVIEW_RELATIVE_PATH_INVALID")
    if posix.as_posix() != value or "//" in value or value.endswith("/"):
        _fail("REVIEW_RELATIVE_PATH_NOT_CANONICAL")
    return value


def _nonnegative_integer(value):
    return type(value) is int and value >= 0


def load_review_receipt(root=None):
    """Validate only bounded publication JSON, never large census ledgers per read.

    `latest-review.txt` contains a relative bundle identifier.  The publisher is
    responsible for independently checking the full artifacts before publishing
    its parent-verification receipt.  This function grants no operational status.
    """
    configured_root = Path(root or REVIEW_ROOT).absolute()
    try:
        # The configured canonical directory is a trust boundary too. A junction
        # at the root must not silently choose another storage location.
        for ancestor in (configured_root, *configured_root.parents):
            if ancestor.exists():
                info = ancestor.lstat()
                if ancestor.is_symlink() or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    _fail("REVIEW_ROOT_REPARSE_PATH_REJECTED")
        root = configured_root.resolve()
        latest_raw = _read_bytes(root, root / "latest-review.txt", 256)
        try:
            bundle_id = latest_raw.decode("ascii").strip()
        except UnicodeError:
            _fail("LATEST_REVIEW_ID_INVALID")
        if not ID_PATTERN.fullmatch(bundle_id):
            _fail("LATEST_REVIEW_ID_INVALID")
        bundle = _inside(root, root / bundle_id)
        if not bundle.is_dir():
            _fail("REVIEW_BUNDLE_DIRECTORY_REQUIRED")
        manifest_raw = _read_bytes(bundle, bundle / "publication-manifest.json", MAX_JSON_BYTES)
        manifest = _json(manifest_raw)
        if (manifest.get("schema_version") != "technical-review-publication-1"
                or manifest.get("bundle_id") != bundle_id
                or manifest.get("status") != "TECHNICAL_REVIEW_ONLY"
                or manifest.get("approved") is not False):
            _fail("REVIEW_MANIFEST_INVALID")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != set(REQUIRED_FILES):
            _fail("REVIEW_REQUIRED_FILES_INCOMPLETE")
        documents, verified_files = {}, {}
        paths = set()
        for name in REQUIRED_FILES:
            entry = files[name]
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "bytes"}:
                _fail("REVIEW_FILE_DESCRIPTOR_INVALID")
            relative = _relative_path(entry["path"])
            if relative in paths:
                _fail("REVIEW_FILE_DESCRIPTOR_PATH_REUSED")
            paths.add(relative)
            if (not isinstance(entry["sha256"], str) or not SHA_PATTERN.fullmatch(entry["sha256"])
                    or not _nonnegative_integer(entry["bytes"]) or entry["bytes"] > MAX_JSON_BYTES):
                _fail("REVIEW_FILE_DESCRIPTOR_INVALID")
            raw = _read_bytes(bundle, bundle / relative, MAX_JSON_BYTES)
            if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                _fail("REVIEW_PUBLICATION_FILE_HASH_MISMATCH")
            documents[name] = _json(raw)
            verified_files[name] = {"sha256": entry["sha256"], "bytes": len(raw)}
        semantic = documents["semantic_summary"]
        receipt = documents["semantic_receipt"]
        identity = documents["identity_summary"]
        parent = documents["parent_verification"]
        if (parent.get("status") != "VERIFIED_TECHNICAL_REVIEW_ONLY"
                or parent.get("overall_verified") is not True or parent.get("approved") is not False):
            _fail("PARENT_TECHNICAL_VERIFICATION_INCOMPLETE")
        parent_inputs = parent.get("verified_publication_inputs")
        input_names = set(REQUIRED_FILES) - {"parent_verification"}
        if not isinstance(parent_inputs, dict) or set(parent_inputs) != input_names:
            _fail("PARENT_VERIFIED_INPUTS_INCOMPLETE")
        for name in input_names:
            entry = parent_inputs[name]
            if (not isinstance(entry, dict) or set(entry) != {"sha256", "bytes"}
                    or not _nonnegative_integer(entry.get("bytes")) or entry != verified_files[name]):
                _fail("PARENT_VERIFIED_INPUT_HASH_MISMATCH")
        if semantic.get("status") != "BLOCKED_DRAFT" or semantic.get("approved") is not False:
            _fail("REVIEW_APPROVAL_SCOPE_INVALID")
        if receipt.get("status") != "BLOCKED_DRAFT" or receipt.get("approved") is not False:
            _fail("REVIEW_APPROVAL_SCOPE_INVALID")
        approvals = ("semantic_approvals", "unit_application_approvals", "timezone_approvals", "qc_approvals", "operational_rule_approvals")
        if any(type(semantic.get(k)) is not int or semantic[k] != 0 for k in approvals):
            _fail("REVIEW_APPROVAL_COUNTS_INVALID")
        if (type(identity.get("approved_identity_period_event_scopes")) is not int
                or identity["approved_identity_period_event_scopes"] != 0
                or type(identity.get("eligible_members")) is not int or identity["eligible_members"] != 0):
            _fail("REVIEW_APPROVAL_COUNTS_INVALID")
        count = semantic.get("input_rows")
        universe = receipt.get("universe", {})
        channel_census = identity.get("channel_census", {})
        counts_to_check = [count, semantic.get("output_rows"), semantic.get("exact_scope_keys"),
                           semantic.get("duplicate_scope_keys"), semantic.get("invalid_grain_rows"),
                           universe.get("rows"), channel_census.get("count")]
        if (any(not _nonnegative_integer(v) for v in counts_to_check) or count == 0 or semantic.get("output_rows") != count
                or universe.get("rows") != count or channel_census.get("count") != count
                or type(channel_census.get("sql_count")) is not int or channel_census["sql_count"] != count
                or channel_census.get("exact_grain_and_held_rows_match") is not True
                or type(channel_census.get("missing_in_sql")) is not int or channel_census["missing_in_sql"] != 0
                or type(channel_census.get("extra_in_sql")) is not int or channel_census["extra_in_sql"] != 0
                or semantic.get("exact_scope_keys") != count or semantic.get("duplicate_scope_keys") != 0
                or semantic.get("invalid_grain_rows") != 0
                or semantic.get("enumeration_complete") is not True
                or semantic.get("unique_grain_coverage_complete") is not True
                or receipt.get("coverage_complete") is not True):
            _fail("REVIEW_CENSUS_SCOPE_INCONSISTENT")
        errors = receipt.get("validation_errors")
        if (not isinstance(errors, list) or not errors or any(not isinstance(e, str) or not e for e in errors)
                or "SOURCE_SEMANTICS_NOT_APPROVED" not in errors):
            _fail("REVIEW_SEMANTIC_BLOCKERS_MISSING")
        dictionary_counts = semantic.get("dictionary_reference_counts")
        group_counts = semantic.get("source_group_counts")
        if (not isinstance(dictionary_counts, dict) or not dictionary_counts
                or any(not _nonnegative_integer(v) for v in dictionary_counts.values())
                or sum(dictionary_counts.values()) != count
                or not isinstance(group_counts, dict) or not group_counts
                or any(not isinstance(values, dict) or not values
                       or any(not _nonnegative_integer(v) for v in values.values()) for values in group_counts.values())
                or sum(sum(values.values()) for values in group_counts.values()) != count):
            _fail("REVIEW_CENSUS_SCOPE_INCONSISTENT")
        run_id = semantic.get("live_run_id")
        if (not isinstance(run_id, str) or not run_id or universe.get("run_id") != run_id
                or identity.get("registry_run_id") != run_id
                or receipt.get("technical_receipt_sha256") != semantic.get("receipt_sha256")
                or universe.get("scope_keys_sha256") != semantic.get("universe_sha256")):
            _fail("REVIEW_RECEIPT_DEPENDENCY_MISMATCH")
        linked_hashes = ((universe.get("live_manifest_sha256"), semantic.get("live_manifest_sha256")),
                         (receipt.get("reviewer_sha256"), semantic.get("reviewer_sha256")),
                         (receipt.get("contracts_sha256"), semantic.get("artifact_files", {}).get("contracts", {}).get("sha256")),
                         (receipt.get("contract_index_sha256"), semantic.get("artifact_files", {}).get("contract_index", {}).get("sha256")))
        if (any(not isinstance(left, str) or not SHA_PATTERN.fullmatch(left) or left != right for left, right in linked_hashes)
                or not isinstance(semantic.get("as_of"), str) or universe.get("as_of") != semantic["as_of"]):
            _fail("REVIEW_RECEIPT_DEPENDENCY_MISMATCH")
        common = parent.get("common_scope_keys_sha256")
        if (not isinstance(common, str) or not SHA_PATTERN.fullmatch(common)
                or common != semantic.get("universe_sha256") or parent.get("run_id") != run_id
                or type(parent.get("channel_month_count")) is not int or parent["channel_month_count"] != count):
            _fail("PARENT_VERIFIED_SCOPE_MISMATCH")
        event_scope = identity.get("report_scope_extension")
        if event_scope is not None:
            event_counts = ("reviewed_report_rows", "tide_current_rows", "buoy_rows", "hf_rows", "science_rows",
                            "newly_added_report_rows", "exact_event_link_candidates", "unlinked_rows")
            if (not isinstance(event_scope, dict) or event_scope.get("approved") is not False
                    or any(not _nonnegative_integer(event_scope.get(k)) for k in event_counts)
                    or sum(event_scope[k] for k in ("tide_current_rows", "buoy_rows", "hf_rows", "science_rows")) != event_scope["reviewed_report_rows"]
                    or event_scope["newly_added_report_rows"] > event_scope["reviewed_report_rows"]
                    or event_scope["unlinked_rows"] > event_scope["reviewed_report_rows"]
                    or not isinstance(event_scope.get("scope_description"), str) or not event_scope["scope_description"]
                    or not isinstance(event_scope.get("status"), str) or not event_scope["status"]):
                _fail("REPORT_EVENT_SCOPE_INVALID")
        # A pointer change during this bounded read cannot mix two publications.
        if _read_bytes(root, root / "latest-review.txt", 256) != latest_raw:
            _fail("LATEST_REVIEW_CHANGED_DURING_READ")
        return dict(status="TECHNICAL_REVIEW_ONLY", approved=False, bundle_id=bundle_id,
                    scope_label="등록된 채널-월 전수 기술검토 및 명시한 보고서 표 범위. 전체 문서·전체기간 의미/QC 승인이 아닙니다.",
                    manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(), verified_files=verified_files,
                    integrity_scope="SMALL_PUBLICATION_JSON_REHASHED_ON_READ",
                    ledger_integrity_scope="PARENT_VERIFIED_AT_PUBLICATION_NOT_REHASHED_PER_REQUEST",
                    operational_approval_status="NOT_GRANTED_BY_TECHNICAL_REVIEW",
                    training_execution="NOT_EXECUTED_BY_TECHNICAL_REVIEW",
                    semantic=semantic, semantic_receipt=receipt, identity=identity, parent_verification=parent)
    except ReviewReceiptUnavailable:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        _fail("TECHNICAL_REVIEW_NOT_AVAILABLE")
