"""Canonical project root and external data workspace path resolution helpers."""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path, PureWindowsPath

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_WORKSPACE = Path.home() / "Desktop" / "관할해역"
DEFAULT_WORKSPACE_ROOT = DEFAULT_DATA_WORKSPACE
DEFAULT_STANDARD_OBS_ROOT = DEFAULT_WORKSPACE_ROOT / "정형데이터" / "GD_OBS_ST"
DEFAULT_STANDARD_PRD_ROOT = DEFAULT_WORKSPACE_ROOT / "정형데이터" / "GO_TIDE_PRE_DATA"
DATA_WORKSPACE_MARKERS = (
    "2026년_AI_품질처리_데이터백업",
    "정형데이터",
    "DB_Exporting",
)
PROJECT_SUBDIRS = (
    "manifests",
    "reports",
    "runtime",
    "schemas",
    "scripts",
    "tests",
    "ui",
    "decisions",
)


def reject_z_path(value: str | Path) -> None:
    """Reject the unavailable drive lexically, before filesystem operations."""
    drive = PureWindowsPath(str(value).strip()).drive.upper()
    if drive in {"Z:", "\\\\?\\Z:", "\\\\.\\Z:"}:
        raise ValueError("Z: 드라이브에는 접근할 수 없습니다.")


def ensure_no_z_access(path: str | Path) -> None:
    """Inspect ancestors before descendants, without resolving an unchecked link.

    Missing components are allowed for prospective output paths. Reparse targets
    must be readable, acyclic, and checked lexically before any target metadata.
    The check assumes links are not concurrently replaced during the following I/O.
    """
    reject_z_path(path)
    candidate = Path(path).expanduser().absolute()

    def inspect(target: Path, active: frozenset[str]) -> None:
        reject_z_path(target)
        current = Path(target.anchor)
        parts = target.parts[1:]
        for index, part in enumerate(("", *parts)):
            if part == "..":
                current = current.parent
            elif part:
                current = current / part
            try:
                info = current.lstat()
            except FileNotFoundError:
                # A later '..' can return to an existing parent. Keep checking
                # so strict=False resolution cannot hide a later linked path.
                continue
            except OSError as error:
                raise ValueError(f"경로를 검사할 수 없습니다: {current}") from error
            if not (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0)
                    & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                continue
            key = os.path.normcase(str(current))
            if key in active or len(active) >= 40:
                raise ValueError(f"링크 순환(cycle)을 발견했습니다: {current}")
            try:
                raw_target = os.readlink(current)
            except OSError as error:
                raise ValueError(f"링크 대상을 검사할 수 없습니다: {current}") from error
            reject_z_path(raw_target)
            link_target = Path(raw_target)
            if not link_target.is_absolute():
                link_target = current.parent / link_target
            # index 0 is the anchor; the remaining components retain '..' so
            # another link is inspected before a parent traversal can remove it.
            inspect(link_target.joinpath(*parts[index:]), active | {key})
            return

    inspect(candidate, frozenset())


def _checked_path(path: Path) -> Path:
    ensure_no_z_access(path)
    return path


def _has_workspace_markers(candidate: Path) -> bool:
    ensure_no_z_access(candidate)
    try:
        return candidate.is_dir() and any(_checked_path(candidate / marker).exists() for marker in DATA_WORKSPACE_MARKERS)
    except OSError:
        return False


def resolve_data_workspace(base: Path | None = None) -> Path:
    """Resolve the read-only data workspace in priority order:
    1) AI_QC_DATA_WORKSPACE environment variable
    2) base.parent (when invoked via junction or co-located under data workspace)
    3) Default data workspace (<USER_HOME>\\Desktop\\관할해역)
    """
    env_override = os.environ.get("AI_QC_DATA_WORKSPACE", "").strip()
    if env_override:
        reject_z_path(env_override)
        return _checked_path(Path(env_override).expanduser()).resolve()

    candidates: list[Path] = []
    if base is not None:
        ensure_no_z_access(base)
        candidates.append(Path(base).parent)
        candidates.append(Path(base).resolve().parent)
    candidates.append(Path(__file__).absolute().parents[1].parent)
    candidates.append(PROJECT_ROOT.parent)

    for candidate in candidates:
        if _has_workspace_markers(candidate):
            return candidate.resolve()

    ensure_no_z_access(DEFAULT_DATA_WORKSPACE)
    if DEFAULT_DATA_WORKSPACE.exists():
        return DEFAULT_DATA_WORKSPACE.resolve()

    anchor = Path(base).resolve() if base is not None else PROJECT_ROOT
    return anchor.parent


def resolve_backup_code_root(base: Path | None = None) -> Path:
    """Return the read-only operational AI backup code directory."""
    return (
        resolve_data_workspace(base)
        / "2026년_AI_품질처리_데이터백업"
        / "운영코드"
        / "AI_anomaly_detection"
    )


def resolve_backup_source_root(base: Path | None = None) -> Path:
    """Return the read-only 2025 baseline source backup directory."""
    return (
        resolve_data_workspace(base)
        / "2026년_AI_품질처리_데이터백업"
        / "소스코드"
    )


def resolve_manifest_root(manifest: dict, base: Path | None = None) -> Path:
    """Resolve manifest['root'] with fallback to resolve_backup_code_root(base)."""
    raw = str(manifest.get("root", "")).strip()
    if not raw:
        raise ValueError("Manifest is missing 'root'")
    ensure_no_z_access(raw)

    env_override = os.environ.get("AI_QC_DATA_WORKSPACE", "").strip()
    normalized = raw.replace("\\", "/").rstrip("/")
    if env_override and normalized.endswith("2026년_AI_품질처리_데이터백업/운영코드/AI_anomaly_detection"):
        override_root = resolve_backup_code_root(base)
        ensure_no_z_access(override_root)
        return override_root.resolve(strict=True)

    candidate = Path(raw)
    if candidate.is_absolute() and candidate.exists():
        return candidate.resolve(strict=True)

    if normalized.endswith("2026년_AI_품질처리_데이터백업/운영코드/AI_anomaly_detection"):
        fallback = resolve_backup_code_root(base)
        ensure_no_z_access(fallback)
        return fallback.resolve(strict=True)

    return candidate.resolve(strict=True)


def resolve_project_path(raw_path: str | Path, base: Path | None = None) -> Path:
    """Resolve a path recorded in a manifest/report against the current project root (BASE)
    when the recorded path points to a previous or relocated project directory.
    """
    ensure_no_z_access(raw_path)
    if base is not None:
        ensure_no_z_access(base)
    anchor = Path(base).resolve() if base is not None else PROJECT_ROOT
    raw_str = str(raw_path).strip()
    if not raw_str:
        return anchor

    normalized = raw_str.replace("\\", "/")
    normalized_lower = normalized.lower()
    legacy_marker = "/" + "_".join(("ai", "mlops", "2026")) + "/"
    for marker in (legacy_marker, "/ai-qc-mlops/"):
        idx = normalized_lower.find(marker)
        if idx != -1:
            suffix = normalized[idx + len(marker) :].lstrip("/")
            first_part = suffix.split("/", 1)[0].lower()
            if first_part in PROJECT_SUBDIRS:
                rebased = anchor / Path(suffix)
                ensure_no_z_access(rebased)
                if rebased.exists():
                    return rebased.resolve()
                return rebased

    backup_marker = "/2026년_AI_품질처리_데이터백업/운영코드/AI_anomaly_detection/"
    if backup_marker in normalized:
        path_candidate = Path(raw_str)
        env_override = os.environ.get("AI_QC_DATA_WORKSPACE", "").strip()
        if env_override or not path_candidate.exists():
            suffix = normalized.split(backup_marker, 1)[1].lstrip("/")
            rebased_backup = resolve_backup_code_root(anchor) / Path(suffix)
            ensure_no_z_access(rebased_backup)
            if rebased_backup.exists():
                return rebased_backup.resolve()
            if not path_candidate.exists():
                return rebased_backup

    path_obj = Path(raw_str)
    if not path_obj.is_absolute():
        return _checked_path(anchor / path_obj).resolve()
    if path_obj.exists():
        return path_obj.resolve()

    for subdir in PROJECT_SUBDIRS:
        token = f"/{subdir}/"
        idx = normalized_lower.find(token)
        if idx != -1:
            suffix = normalized[idx + 1 :]
            rebased = anchor / Path(suffix)
            ensure_no_z_access(rebased)
            if rebased.exists() or rebased.parent.exists():
                return rebased.resolve() if rebased.exists() else rebased

    return path_obj


DEFAULT_EXPORT_ROOT = Path(r"D:\261002_greenblue\01.관측자료\output")
DEFAULT_TIDE_EXPORT_ROOT = Path(r"D:\261008_gb_temp\output")
DEFAULT_TIDE_EXPORT_UTF8_ROOT = Path(r"D:\261008_gb_temp\output_utf8")
DEFAULT_TIDE_2023_EXPORT_ROOT = Path(r"D:\20261021_greenblue\GO_TIDE_PRE_DATA")
TIDE_2023_EXPORT_ROOT_ENV = "AI_QC_TIDE_2023_EXPORT_ROOT"


def get_standard_obs_root(base: Path | None = None) -> Path:
    return resolve_data_workspace(base) / "정형데이터" / "GD_OBS_ST"


def get_standard_prd_root(base: Path | None = None) -> Path:
    return resolve_data_workspace(base) / "정형데이터" / "GO_TIDE_PRE_DATA"


def get_tide_2023_export_root() -> Path:
    raw = os.environ.get(TIDE_2023_EXPORT_ROOT_ENV, "").strip()
    reject_z_path(raw or DEFAULT_TIDE_2023_EXPORT_ROOT)
    target = Path(raw).expanduser() if raw else DEFAULT_TIDE_2023_EXPORT_ROOT
    ensure_no_z_access(target)
    return target.resolve() if target.exists() else target


def resolve_training_csv_path(raw_path: str | Path, base: Path | None = None) -> Path:
    """Keep existing paths, or find a missing CSV's standard/legacy alias."""
    ensure_no_z_access(raw_path)
    if base is not None:
        ensure_no_z_access(base)
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path(base) if base is not None else PROJECT_ROOT) / candidate
    candidate = _checked_path(candidate).resolve()
    reject_z_path(candidate)
    if candidate.exists():
        return candidate
    workspace = resolve_data_workspace(base)
    legacy_root = workspace / "정형데이터"
    obs_root = get_standard_obs_root(base)
    prd_root = get_standard_prd_root(base)
    exports = resolve_export_roots()
    prediction_roots = [prd_root, exports["tide_2023_export_root"],
                        exports["tide_export_root"], exports["tide_export_utf8_root"],
                        exports["export_root"]]
    candidates = []
    obs = re.fullmatch(r"(?:data_|GD_OBS_ST_)(.+)\.csv", candidate.name, re.I)
    prd = re.fullmatch(r"(?:pred_|GO_TIDE_PRE_DATA_)(.+)\.csv", candidate.name, re.I)
    if obs and candidate.parent in {legacy_root, obs_root}:
        suffix = obs.group(1)
        legacy_name = f"data_{suffix}.csv" if re.fullmatch(r"\d{6}", suffix) else f"GD_OBS_ST_{suffix}.csv"
        candidates = [obs_root / f"GD_OBS_ST_{suffix}.csv", legacy_root / legacy_name]
    elif prd and candidate.parent in {legacy_root, *prediction_roots}:
        suffix = prd.group(1)
        candidates = [root / f"GO_TIDE_PRE_DATA_{suffix}.csv" for root in prediction_roots]
        candidates.extend([legacy_root / f"pred_{suffix}.csv", legacy_root / f"GO_TIDE_PRE_DATA_{suffix}.csv"])
    for alias in candidates:
        ensure_no_z_access(alias)
        if alias.is_file():
            resolved = alias.resolve()
            reject_z_path(resolved)
            return resolved
    return candidate


def resolve_export_roots() -> dict[str, Path]:
    """Resolve configurable external CSV export roots from environment variables."""
    mapping = {
        "export_root": ("AI_QC_EXPORT_ROOT", DEFAULT_EXPORT_ROOT),
        "tide_export_root": ("AI_QC_TIDE_EXPORT_ROOT", DEFAULT_TIDE_EXPORT_ROOT),
        "tide_export_utf8_root": ("AI_QC_TIDE_EXPORT_UTF8_ROOT", DEFAULT_TIDE_EXPORT_UTF8_ROOT),
        "tide_2023_export_root": (TIDE_2023_EXPORT_ROOT_ENV, DEFAULT_TIDE_2023_EXPORT_ROOT),
    }
    resolved_map: dict[str, Path] = {}
    for key, (env_name, default_path) in mapping.items():
        raw = os.environ.get(env_name, "").strip()
        reject_z_path(raw or default_path)
        target = Path(raw).expanduser() if raw else default_path
        ensure_no_z_access(target)
        try:
            resolved_map[key] = target.resolve() if target.exists() else target
        except OSError:
            resolved_map[key] = target
    return resolved_map


def resolve_additional_data_roots(base: Path | None = None) -> list[Path]:
    """Resolve external CSV data roots beyond the primary data workspace.

    Supports environment variable overrides:
    - AI_QC_EXPORT_ROOT (default: D:\\261002_greenblue\\01.관측자료\\output)
    - AI_QC_TIDE_EXPORT_ROOT (default: D:\\261008_gb_temp\\output)
    - AI_QC_TIDE_EXPORT_UTF8_ROOT (default: D:\\261008_gb_temp\\output_utf8)
    - AI_QC_EXTRA_DATA_ROOTS (os.pathsep-separated list of additional directories)
    """
    ws = resolve_data_workspace(base)
    if base is not None:
        ensure_no_z_access(base)
    anchor = Path(base).resolve() if base is not None else PROJECT_ROOT
    export_map = resolve_export_roots()
    roots: list[Path] = [ws, anchor]
    seen: set[str] = {str(ws).lower(), str(anchor).lower()}

    for target in export_map.values():
        key = str(target).lower()
        if key not in seen:
            seen.add(key)
            roots.append(target)

    extra_raw = os.environ.get("AI_QC_EXTRA_DATA_ROOTS", "").strip()
    if extra_raw:
        for item in extra_raw.split(os.pathsep):
            cleaned = item.strip()
            if not cleaned:
                continue
            reject_z_path(cleaned)
            target = Path(cleaned).expanduser()
            ensure_no_z_access(target)
            try:
                resolved = target.resolve() if target.exists() else target
            except OSError:
                resolved = target
            key = str(resolved).lower()
            if key not in seen:
                seen.add(key)
                roots.append(resolved)

    return roots


def get_allowed_roots(base: Path | None = None) -> list[Path]:
    """Compatibility name for the configured CSV roots, workspace first."""
    return resolve_additional_data_roots(base)


