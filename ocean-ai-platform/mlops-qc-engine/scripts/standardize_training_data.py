"""Lossless, bounded-memory normalization of the approved SQL*Plus exports.

Only explicitly recognized export artifacts are removed. Data stays binary:
there is no CSV parsing/re-serialization, decoding, sorting, or row-wise Python
loop. A second implementation recognizes source artifacts with a regex and
compares its data spans directly with the output before atomic publication.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import BinaryIO, Iterator


OBS_HEADER = b"OBS_POST_ID,OBS_ITEM_CODE,OBS_TIME,OBS_VALUE,QC_FLAG,MQC_FLAG,N1_AQC_FLAG"
PRD_HEADER = b"OBS_POST_ID,OBS_TIME,TIDE_PRE_VAL"
SQLPLUS_HEADER = b"OBS_POST_I,OBS_ITEM_CODE                                     ,OBS_TIME           , OBS_VALUE,QC,MQ,N1_AQC_FLA"
SQLPLUS_SEPARATOR = b"----------,--------------------------------------------------,-------------------,----------,--,--,----------"
HEADERS = {"obs": OBS_HEADER, "prd": PRD_HEADER}
DEFAULT_CHUNK_SIZE = 64 * 1024 * 1024
MAX_LINE = 1024 * 1024
APPROVED_DATA_ROOT = Path.home() / "Desktop" / "관할해역" / "정형데이터"
_PROTECTED_NAME = "2026년_AI_품질처리_데이터백업"
_PREAMBLE = re.compile(rb"(?:old|new)[ \t]+[0-9]+:[^\r\n]*")
_BLANKS = re.compile(rb"(?m)^[ \t]*\r?\n")
_NON_DELIMITERS = bytes(i for i in range(256) if i not in (10, 13, 44))
_D_PREDICTION_SOURCE = re.compile(
    r"D:\\(?:20261021_greenblue\\GO_TIDE_PRE_DATA|261008_gb_temp\\output\\GO_TIDE_PRE_DATA)"
    r"\\GO_TIDE_PRE_DATA_[0-9]{4}(?:0[1-9]|1[0-2])\.csv", re.IGNORECASE
)


def _may_have_blank_lines(data: bytes) -> bool:
    return (data.startswith((b"\r\n", b"\n", b" ", b"\t"))
            or any(marker in data for marker in (b"\n\r\n", b"\n\n", b"\n ", b"\n\t")))


def _guard_path(value: str | os.PathLike[str], *, prediction_source: bool = False) -> Path:
    """Allow only C writes and the two exact D prediction source families.

    The D exception is available only to source arguments for ``kind='prd'``.
    Those sources are opened exclusively in ``rb`` mode by both passes.
    """
    raw = os.fspath(value)
    drive, _ = ntpath.splitdrive(raw)
    approved_d_source = prediction_source and _D_PREDICTION_SOURCE.fullmatch(raw) is not None
    if drive and drive.upper() != "C:" and not approved_d_source:
        raise ValueError(f"forbidden drive: {drive}")
    if _PROTECTED_NAME in ntpath.normpath(raw).split("\\"):
        raise ValueError("protected backup path")
    path = Path(raw).absolute()
    # A leaf lstat can already traverse an ancestor junction. Inspect the root
    # first and reject any reparse point before querying its descendants.
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("symlink/reparse path is forbidden")
    resolved = path.resolve()
    resolved_drive, _ = ntpath.splitdrive(str(resolved))
    if resolved_drive and resolved_drive.upper() != "C:" and not (
            approved_d_source and _D_PREDICTION_SOURCE.fullmatch(str(resolved))):
        raise ValueError("forbidden resolved drive")
    if approved_d_source and ntpath.normcase(str(resolved)) != ntpath.normcase(raw):
        raise ValueError("forbidden prediction source path resolution")
    if _PROTECTED_NAME in resolved.parts:
        raise ValueError("protected backup path")
    return resolved


def _identity(path: Path) -> dict[str, int]:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("source/destination must be a regular file")
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns,
            "ctime_ns": info.st_ctime_ns, "device": info.st_dev, "inode": info.st_ino}


def _options(kind: str, chunk_size: int) -> bytes:
    if kind not in HEADERS:
        raise ValueError("kind must be 'obs' or 'prd'")
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    return HEADERS[kind]


def _counts() -> dict[str, int]:
    return {"preamble_lines": 0, "blank_lines": 0, "repeated_headers": 0,
            "separator_lines": 0, "row_count_footers": 0}


def _read_header(stream: BinaryIO, kind: str, digest, removed: dict[str, int]) -> str:
    """The only line-wise loop is the small preamble, bounded to 1 MiB."""
    consumed = 0
    while consumed <= MAX_LINE:
        line = stream.readline(MAX_LINE + 1)
        digest.update(line)
        consumed += len(line)
        if not line or len(line) > MAX_LINE:
            raise ValueError("missing or invalid header")
        text = line.rstrip(b"\r\n")
        if not text.strip(b" \t"):
            removed["blank_lines"] += 1
            continue
        if kind == "obs" and _PREAMBLE.fullmatch(text):
            removed["preamble_lines"] += 1
            continue
        expected = HEADERS[kind]
        quoted = b",".join(b'"' + col + b'"' for col in expected.split(b","))
        if text in (expected, quoted):
            return text.decode("ascii")
        if kind == "obs" and text == SQLPLUS_HEADER:
            separator = stream.readline(MAX_LINE + 1)
            digest.update(separator)
            if separator.rstrip(b"\r\n") != SQLPLUS_SEPARATOR:
                raise ValueError("truncated header requires its exact separator")
            removed["separator_lines"] += 1
            return text.decode("ascii")
        raise ValueError("unrecognized or wrong-schema header")
    raise ValueError("preamble exceeds bounded header limit")


def _writer_blocks(stream: BinaryIO, chunk_size: int, digest) -> Iterator[bytes]:
    """Keep two complete lines so a repeated header/separator never splits."""
    pending = b""
    while True:
        part = stream.read(chunk_size)
        digest.update(part)
        if not part:
            if pending:
                yield pending
            return
        pending += part
        last = pending.rfind(b"\n")
        previous = pending.rfind(b"\n", 0, last) if last >= 0 else -1
        boundary = pending.rfind(b"\n", 0, previous) + 1 if previous >= 0 else 0
        if boundary:
            prior_start = pending.rfind(b"\n", 0, boundary - 1) + 1
            prior_line = pending[prior_start:boundary].rstrip(b"\r\n")
            if prior_line in (SQLPLUS_HEADER, OBS_HEADER, PRD_HEADER):
                boundary = prior_start
        if boundary:
            yield pending[:boundary]
            pending = pending[boundary:]
        elif len(pending) > MAX_LINE * 3:
            raise ValueError("invalid data: line exceeds bounded limit")


def _data_valid(data: bytes, kind: str) -> None:
    """Validate a tiny delimiter projection rather than regex-scanning values."""
    if not data:
        return
    columns = 7 if kind == "obs" else 3
    validation = _BLANKS.sub(b"", data) if kind == "prd" and _may_have_blank_lines(data) else data
    delimiters = validation.translate(None, _NON_DELIMITERS)
    invalid = rb"(?m)^(?!,{" + str(columns - 1).encode("ascii") + rb"}\r?$)(?!\Z)"
    if (re.search(invalid, delimiters) or validation.startswith(b",") or b"\n," in validation):
        raise ValueError("unrecognized artifact or invalid data row/schema")
    if b"\r" in delimiters.replace(b"\r\n", b""):
        raise ValueError("invalid data: bare CR")
    if HEADERS[kind] in data and re.search(rb"(?m)^" + re.escape(HEADERS[kind]) + rb"\r?$", data):
        raise ValueError("residual repeated header in data")


def _replace_artifacts(block: bytes, kind: str, removed: dict[str, int]) -> tuple[bytes, int | None]:
    """Use C-level bytes.replace for the exact, fixed-width export blocks."""
    if kind == "prd":
        return block, None
    headers = [HEADERS[kind]]
    if kind == "obs":
        headers.append(SQLPLUS_HEADER)
    payload = b"\n" + block
    for header in headers:
        for ending in (b"\r\n", b"\n"):
            terminal = b"\n" + header + ending + SQLPLUS_SEPARATOR
            if payload.endswith(terminal):
                payload = payload[:-len(terminal)] + b"\n"
                removed["repeated_headers"] += 1
                removed["separator_lines"] += 1
            for sep_ending in (b"\r\n", b"\n"):
                artifact = b"\n" + header + ending + SQLPLUS_SEPARATOR + sep_ending
                while artifact in payload:
                    count = payload.count(artifact)
                    payload = payload.replace(artifact, b"\n")
                    removed["repeated_headers"] += count
                    removed["separator_lines"] += count
        if header != SQLPLUS_HEADER:
            terminal = b"\n" + header
            if payload.endswith(terminal):
                payload = payload[:-len(terminal)] + b"\n"
                removed["repeated_headers"] += 1
            for ending in (b"\r\n", b"\n"):
                artifact = b"\n" + header + ending
                while artifact in payload:
                    count = payload.count(artifact)
                    payload = payload.replace(artifact, b"\n")
                    removed["repeated_headers"] += count
    block = payload[1:]
    footer = None
    footer_pattern = rb"(?m)^[ \t]*([0-9]+) rows? selected\.[ \t]*\r?(?:\n|$)"
    match = re.search(footer_pattern, block) if b" selected." in block else None
    if match:
        if block[match.end():].strip(b" \t\r\n"):
            raise ValueError("data or unrecognized text follows row count footer")
        footer = int(match.group(1))
        removed["row_count_footers"] += 1
        block = block[:match.start()] + block[match.end():]
    padded = b"\n" + block
    for empty_line in (b"\n\r\n", b"\n\n"):
        while empty_line in padded:
            removed["blank_lines"] += padded.count(empty_line)
            padded = padded.replace(empty_line, b"\n")
    block = padded[1:]
    if block.startswith((b" ", b"\t")) or b"\n " in block or b"\n\t" in block:
        block, blank_count = _BLANKS.subn(b"", block)
        removed["blank_lines"] += blank_count
    if block and not block.strip(b" \t\r\n"):
        removed["blank_lines"] += 1
        block = b""
    if SQLPLUS_HEADER in block or SQLPLUS_SEPARATOR in block:
        raise ValueError("unpaired repeated header/separator artifact")
    return block, footer


def _verification_blocks(stream: BinaryIO, chunk_size: int, digest) -> Iterator[bytes]:
    """Independent boundary handling: complete a read with at most two lines."""
    while True:
        block = stream.read(chunk_size)
        if not block:
            return
        if not block.endswith(b"\n"):
            suffix = stream.readline(MAX_LINE + 1)
            if len(suffix) > MAX_LINE:
                raise ValueError("invalid data: oversized line")
            block += suffix
        tail = block[block.rfind(b"\n", 0, max(0, len(block) - 1)) + 1:].rstrip(b"\r\n")
        if tail in (SQLPLUS_HEADER, OBS_HEADER, PRD_HEADER):
            block += stream.readline(MAX_LINE + 1)
        digest.update(block)
        yield block


def _artifact_regex(kind: str) -> re.Pattern[bytes]:
    if kind == "prd":
        return re.compile(rb"(?!)")
    full = re.escape(HEADERS[kind]) + rb"\r?(?:\n|$)"
    sep = re.escape(SQLPLUS_SEPARATOR) + rb"\r?(?:\n|$)"
    header = rb"(?P<header>" + full + rb"(?:" + sep + rb")?)"
    if kind == "obs":
        header += rb"|(?P<truncated>" + re.escape(SQLPLUS_HEADER) + rb"\r?\n" + sep + rb")"
    return re.compile(
        rb"(?m)^(?:(?P<blank>[ \t]*\r?\n)|" + header
        + rb"|(?P<footer>[ \t]*(?P<count>[0-9]+) rows? selected\.[ \t]*\r?(?:\n|$)))"
    )


def _verification_matches(block: bytes, kind: str, artifact: re.Pattern[bytes]):
    """Locate sparse artifact candidates in C, then independently parse them.

    Regex is applied at candidate line starts instead of walking every data
    byte with a multiline alternation. Python visits artifacts, not rows.
    """
    if kind == "prd":
        return
    candidates = {0}
    for marker in (HEADERS[kind], SQLPLUS_HEADER, b" selected.", b"\n\r\n", b"\n\n"):
        position = block.find(marker)
        while position >= 0:
            if marker.startswith(b"\n"):
                candidates.add(position + 1)
            else:
                candidates.add(block.rfind(b"\n", 0, position) + 1)
            position = block.find(marker, position + 1)
    if block.startswith((b" ", b"\t")) or b"\n " in block or b"\n\t" in block:
        candidates.update(match.start() for match in _BLANKS.finditer(block))
    consumed = 0
    for position in sorted(candidates):
        if position < consumed:
            continue
        match = artifact.match(block, position)
        if match is not None:
            consumed = match.end()
            yield match


def verify_file(source, destination, kind: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict:
    """Independently compare every ordered source data byte with destination.

    The verifier never uses the writer's block iterator or replacement routine.
    Its Python loop visits only chunks and artifacts, never individual data rows.
    """
    header = _options(kind, chunk_size)
    src, dst = _guard_path(source, prediction_source=kind == "prd"), _guard_path(destination)
    before_source, before_destination = _identity(src), _identity(dst)
    if src == dst or (before_source["device"], before_source["inode"]) == (
            before_destination["device"], before_destination["inode"]):
        raise ValueError("source and destination must be independent files")
    source_hash, destination_hash, data_hash = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    removed = _counts()
    data_rows = data_bytes = 0
    last_data = b""
    footer = None
    artifact = _artifact_regex(kind)
    with src.open("rb") as source_stream, dst.open("rb") as target:
        source_header = _read_header(source_stream, kind, source_hash, removed)
        actual_header = target.readline(MAX_LINE + 1)
        if actual_header != header + b"\r\n":
            raise ValueError("destination header is not canonical CRLF schema")
        destination_hash.update(actual_header)
        for block in _verification_blocks(source_stream, chunk_size, source_hash):
            cursor = 0
            spans = []
            for match in _verification_matches(block, kind, artifact):
                spans.append((block[cursor:match.start()], footer is not None))
                cursor = match.end()
                if match.lastgroup == "blank":
                    removed["blank_lines"] += 1
                elif match.group("footer") is not None:
                    if footer is not None:
                        raise ValueError("multiple row count footers")
                    footer = int(match.group("count"))
                    removed["row_count_footers"] += 1
                else:
                    removed["repeated_headers"] += 1
                    if SQLPLUS_SEPARATOR in match.group():
                        removed["separator_lines"] += 1
            spans.append((block[cursor:], footer is not None))
            # Artifact positions are few (one SQL*Plus page per ~50k rows).
            for span, follows_footer in spans:
                if not span:
                    continue
                if kind == "obs" and not span.strip(b" \t\r\n"):
                    removed["blank_lines"] += 1
                    continue
                if follows_footer:
                    raise ValueError("data follows row count footer")
                _data_valid(span, kind)
                if SQLPLUS_HEADER in span or SQLPLUS_SEPARATOR in span:
                    raise ValueError("residual header/separator artifact")
                actual = target.read(len(span))
                if actual != span:
                    raise ValueError("independent verification: ordered data bytes differ")
                data_hash.update(actual)
                destination_hash.update(actual)
                data_rows += actual.count(b"\n")
                data_bytes += len(actual)
                last_data = actual[-1:]
        if target.read(1):
            raise ValueError("independent verification: destination has extra bytes/artifacts")
    if last_data and last_data != b"\n":
        data_rows += 1
    if footer is not None and footer != data_rows:
        raise ValueError("row count footer does not match preserved rows")
    if _identity(src) != before_source:
        raise ValueError("source changed during verification")
    if _identity(dst) != before_destination:
        raise ValueError("destination changed during verification")
    return {"source_sha256": source_hash.hexdigest(),
            "destination_sha256": destination_hash.hexdigest(),
            "data_sha256": data_hash.hexdigest(), "data_rows": data_rows,
            "data_bytes": data_bytes, "removed": removed, "source_header": source_header,
            "verified_destination_identity": before_destination}


def _delete_guard(source: Path, destination: Path, kind: str, manifest_path) -> None:
    allowed_root = APPROVED_DATA_ROOT
    match = re.fullmatch(r"data_([0-9]{4}(?:0[1-9]|1[0-2]))\.csv", source.name)
    if (kind != "obs" or source.parent != allowed_root or match is None
            or destination != allowed_root / "GD_OBS_ST" / f"GD_OBS_ST_{match.group(1)}.csv"):
        raise ValueError("source path is not the exact approved monthly deletion target")
    if manifest_path is None:
        raise ValueError("source deletion requires a durable manifest journal")


def _append_journal(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as journal:
        journal.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        journal.flush()
        os.fsync(journal.fileno())


def _validate_journal(path: Path, source: Path, destination: Path) -> None:
    """Never append metadata to a source/output alias or an unrelated file."""
    if not path.exists():
        return
    identity = _identity(path)
    for data_path in (source, destination):
        if data_path.exists():
            data_identity = _identity(data_path)
            if (identity["device"], identity["inode"]) == (
                    data_identity["device"], data_identity["inode"]):
                raise ValueError("manifest journal must be independent of data files")
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except (ValueError, UnicodeError) as exc:
                raise ValueError("manifest journal contains unrelated/invalid content") from exc
            if not isinstance(item, dict) or item.get("status") != "verified" or not item.get("source"):
                raise ValueError("manifest journal contains unrelated content")


def convert_file(source, destination, kind: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
                 delete_source: bool = False, manifest_path=None) -> dict:
    """Normalize, independently verify, atomically publish, and optionally delete.

    ``manifest_path`` is an append-only UTF-8 JSONL journal. The root orchestrator
    may additionally maintain its aggregate JSON manifest. Deletion is disabled
    by default and limited to the exact approved checkout/month counterpart.
    Existing output is retained and resumed only after independent verification.
    """
    header = _options(kind, chunk_size)
    src, dst = _guard_path(source, prediction_source=kind == "prd"), _guard_path(destination)
    journal = _guard_path(manifest_path) if manifest_path is not None else None
    if src == dst:
        raise ValueError("source and destination must be independent files")
    if journal is not None and journal in (src, dst):
        raise ValueError("manifest must be independent of source and destination")
    if delete_source:
        _delete_guard(src, dst, kind, journal)
    source_identity = _identity(src)
    if journal is not None:
        _validate_journal(journal, src, dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    resumed = dst.exists()
    temporary = None
    written_source_hash = None
    try:
        if not resumed:
            handle, name = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".tmp", dir=dst.parent)
            temporary = Path(name)
            source_digest, data_digest = hashlib.sha256(), hashlib.sha256()
            removed = _counts()
            rows = 0
            last = b""
            footer = None
            with os.fdopen(handle, "wb") as output, src.open("rb") as input_stream:
                _read_header(input_stream, kind, source_digest, removed)
                output.write(header + b"\r\n")
                for raw_block in _writer_blocks(input_stream, chunk_size, source_digest):
                    data, new_footer = _replace_artifacts(raw_block, kind, removed)
                    if new_footer is not None:
                        if footer is not None:
                            raise ValueError("multiple row count footers")
                        footer = new_footer
                    elif footer is not None and data:
                        raise ValueError("data follows row count footer")
                    _data_valid(data, kind)
                    output.write(data)
                    data_digest.update(data)
                    rows += data.count(b"\n")
                    if data:
                        last = data[-1:]
                if last and last != b"\n":
                    rows += 1
                if footer is not None and footer != rows:
                    raise ValueError("row count footer does not match data rows")
                output.flush()
                os.fsync(output.fileno())
            written_source_hash = source_digest.hexdigest()
            checked = verify_file(src, temporary, kind, chunk_size=chunk_size)
            if checked["source_sha256"] != written_source_hash:
                raise ValueError("source changed between conversion and verification")
            if checked["data_sha256"] != data_digest.hexdigest() or checked["data_rows"] != rows:
                raise ValueError("independent verification differs from conversion")
        else:
            checked = verify_file(src, dst, kind, chunk_size=chunk_size)
        if _identity(src) != source_identity:
            raise ValueError("source changed before publication")
        checked_path = temporary if temporary is not None else dst
        if _identity(checked_path) != checked["verified_destination_identity"]:
            raise ValueError("destination changed after verification")
        if temporary is not None:
            # Creating a hard link is atomic and fails if destination appeared.
            # Unlike os.replace(), this never clobbers an unrelated output.
            os.link(temporary, dst)
            temporary.unlink()
            temporary = None
        destination_identity = _identity(dst)
        # NTFS link creation can change ctime. Size, mtime and file identity must
        # still be those of the independently verified temporary file.
        for key in ("size", "mtime_ns", "device", "inode"):
            if destination_identity[key] != checked["verified_destination_identity"][key]:
                raise ValueError("destination changed during publication")
        record = {"kind": kind, "source": str(src), "destination": str(dst),
                  "source_size": source_identity["size"],
                  "source_mtime_ns": source_identity["mtime_ns"],
                  "source_identity": source_identity,
                  "destination_size": destination_identity["size"],
                  "destination_mtime_ns": destination_identity["mtime_ns"],
                  "destination_identity": destination_identity,
                  "header": header.decode("ascii"), "header_newline": "CRLF",
                  "status": "verified", "resumed": resumed,
                  "source_deleted": False, **checked}
        if journal is not None:
            _validate_journal(journal, src, dst)
            _append_journal(journal, record)
        if delete_source:
            assert journal is not None  # _delete_guard already requires this.
            _delete_guard(_guard_path(src), _guard_path(dst), kind, journal)
            if _identity(src) != source_identity or _identity(dst) != destination_identity:
                raise ValueError("source or destination changed before deletion")
            src.unlink()
            record["source_deleted"] = True
            _append_journal(journal, record)
        return record
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
