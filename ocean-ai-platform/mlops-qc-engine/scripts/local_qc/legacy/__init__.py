"""Select the preserved regional QC core and read its local configuration."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

from scripts.workspace_paths import resolve_backup_code_root

BASE = Path(__file__).resolve().parents[3]
pd: Any = importlib.import_module("pandas")
_SEA_MODULES = {"동해": "east", "남해": "south", "서해": "west"}
_SEA_ALIASES = {"east": "동해", "east_sea": "동해", "동해": "동해",
                "south": "남해", "south_sea": "남해", "남해": "남해",
                "west": "서해", "west_sea": "서해", "서해": "서해"}


def normalize_sea(sea: str) -> str:
    """Return the original Korean sea name for a supported alias."""
    selected = _SEA_ALIASES.get(str(sea).strip().lower())
    if selected is None:
        raise ValueError(f"알 수 없는 해역입니다: {sea}")
    return selected


def get_legacy_module(sea: str) -> ModuleType:
    """Import only the copied decision core, never the operational script."""
    selected = normalize_sea(sea)
    return importlib.import_module(f"{__name__}.{_SEA_MODULES[selected]}_sea")


def _source_file(path: Path) -> dict[str, str | int]:
    return {"path": str(path.resolve(strict=True)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size}


def build_config(sea: str, *, base: Path = BASE) -> dict[str, Any]:
    """Read the actual backup CSVs using the operational parser and filters.

    Missing or malformed inputs raise an error here so a local comparison cannot
    silently run with a different configuration. No DB or log file is opened.
    """
    selected = normalize_sea(sea)
    module = get_legacy_module(selected)
    root = resolve_backup_code_root(Path(base)).resolve(strict=True)
    mapping_path = root / "mappingBySea.csv"
    sneaky_path = root / "model_output_forecast/threshold_multiplier.sneaky"
    residual_path = root / "model_output_forecast/residual_std_thresholds.csv"

    sea_to_sensor_pairs: dict[str, list[tuple[str, str]]] = {"동해": [], "서해": [], "남해": []}
    mapping_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    mapping_df = pd.read_csv(mapping_path, header=0, encoding="utf-8")
    for _, row in mapping_df.iterrows():
        station_code, sea_info = row["CODE"], row["SEA_INFO"]
        for tide_col in ["TIDE1(MAIN)", "TIDE2", "TIDE3"]:
            sensor_type = row.get(tide_col)
            if pd.notna(sensor_type) and sensor_type != "-":
                sensor_code = f"TIDE_LEVEL_{sensor_type.strip()}"
                if sea_info in sea_to_sensor_pairs:
                    pair = (station_code, sensor_code)
                    sea_to_sensor_pairs[sea_info].append(pair)
                    mapping_by_pair[pair] = {"station": station_code, "sensor": sensor_code,
                                             "sea": sea_info, "station_name": row.get("NAME"),
                                             "info_flag": row.get("INFO_FLAG"), "mapping_column": tide_col}

    sneaky_df = pd.read_csv(sneaky_path)
    sneaky_multipliers_map = {(row["station"], row["sensor"]): row["threshold_multiplier"]
                              for _, row in sneaky_df.iterrows()}
    residual_df = pd.read_csv(residual_path)
    residual_std_thresholds_map = {(row["station"], row["sensor"]): row["residual_std_threshold"]
                                   for _, row in residual_df.iterrows()}
    source_metadata = deepcopy(module.SOURCE_METADATA)
    source_metadata["source_path"] = str(root / source_metadata["source_relative_path"])
    source_metadata["current_source_sha256"] = _source_file(Path(source_metadata["source_path"]))["sha256"]
    metadata = {"sea": selected, "source_root": str(root), "legacy_source": source_metadata,
                "configuration_files": {"mapping": _source_file(mapping_path), "sneaky": _source_file(sneaky_path),
                                        "residual_std": _source_file(residual_path)},
                "mapping_filter": "pd.notna(sensor_type) and sensor_type != '-'; known SEA_INFO; no INFO_FLAG filter",
                "operational_database_used": False}
    config = deepcopy(module.CONFIG)
    config.update({"db_engine": None, "debug_log_path": None, "sneaky_multipliers_map": sneaky_multipliers_map,
                   "residual_std_thresholds_map": residual_std_thresholds_map,
                   "sea_to_sensor_pairs": sea_to_sensor_pairs, "mapping_by_pair": mapping_by_pair,
                   "station_sensor_pairs": sea_to_sensor_pairs[selected], "metadata": metadata})
    return config
