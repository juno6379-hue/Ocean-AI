"""Ocean-AI (ocean-ai-platform) compatible event-evidence-dataset-2 Parquet snapshot authority."""
from __future__ import annotations

import csv
import hashlib
import importlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
for _path_entry in (str(BASE), str(BASE / "scripts")):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)
sys.modules.setdefault("ocean_ai_snapshot", sys.modules[__name__])
sys.modules.setdefault("scripts.ocean_ai_snapshot", sys.modules[__name__])

import scripts.dataset_preview as preview
from scripts.local_trial_manifest import read_json, write_json
from scripts.ocean_ai_bridge import resolve_non_reparse_path
from scripts.workspace_paths import resolve_project_path

np: Any = importlib.import_module("numpy")
pd: Any = importlib.import_module("pandas")
pq: Any = importlib.import_module("pyarrow.parquet")

SNAPSHOTS_ROOT = BASE / "reports/ocean_ai_snapshots"
PARQUET_COLUMNS = (
    "row_id",
    "OBS_POST_ID",
    "OBS_ITEM_CODE",
    "OBS_TIME",
    "SOURCE_OBS_TIMESTAMP",
    "OBS",
    "PRD",
    "SPLIT",
)
SPLIT_NAMES = ("TRAIN", "VALIDATION", "TEST")
CHRONOLOGICAL_SPLIT_POLICY = "CHRONOLOGICAL_STRICTEST_NO_BOUNDARY_CROSSING"
SEASONAL_SPLIT_POLICY = "SEASONAL_VALIDATION_HOLDOUT"
INPUT_WINDOW_MINUTES = 4
HORIZON_MINUTES = 1


def canonical_bytes(value: dict) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_dict(value: dict) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _contiguous_windows_for_frame(frame) -> tuple:
    """Build contiguous 4-input + 1-target windows strictly inside one chronological split."""
    if frame.empty or len(frame) < INPUT_WINDOW_MINUTES + HORIZON_MINUTES:
        return (
            np.empty((0, INPUT_WINDOW_MINUTES, 2), dtype=float),
            np.empty((0, 1), dtype=float),
            [],
            [],
        )
    ordered = frame.sort_values("OBS_TIME").reset_index(drop=True)
    times = pd.to_datetime(ordered["OBS_TIME"], format="%Y-%m-%d %H:%M:%S", errors="raise").to_numpy()
    values = ordered[["OBS", "PRD"]].to_numpy(dtype=float)
    obs_time_strs = ordered["OBS_TIME"].astype(str).tolist()
    src_time_strs = ordered["SOURCE_OBS_TIMESTAMP"].astype(str).tolist()

    eligible = np.isfinite(values).all(axis=1)
    split_labels = ordered["SPLIT"].to_numpy() if "SPLIT" in ordered.columns else None
    for offset in range(1, INPUT_WINDOW_MINUTES + 1):
        eligible &= np.roll(np.isfinite(values).all(axis=1), offset)
        eligible &= (times - np.roll(times, offset)) == np.timedelta64(offset, "m")
        if split_labels is not None:
            eligible &= split_labels == np.roll(split_labels, offset)
    eligible[:INPUT_WINDOW_MINUTES] = False

    indices = np.flatnonzero(eligible)
    if len(indices) == 0:
        return (
            np.empty((0, INPUT_WINDOW_MINUTES, 2), dtype=float),
            np.empty((0, 1), dtype=float),
            [],
            [],
        )
    x_raw = np.asarray([values[idx - INPUT_WINDOW_MINUTES : idx] for idx in indices], dtype=float)
    y_raw = values[indices, 0].reshape(-1, 1).astype(float)
    target_times = [obs_time_strs[idx] for idx in indices]
    target_source_times = [src_time_strs[idx] for idx in indices]
    return x_raw, y_raw, target_times, target_source_times


class ParquetSnapshotAuthority:
    """File-backed authority for immutable Ocean-AI event-evidence-dataset-2 snapshots."""

    def __init__(self, root: Path = SNAPSHOTS_ROOT, preview_output: Path | None = None):
        self.root = resolve_non_reparse_path(root, BASE)
        self.preview_output = (
            resolve_non_reparse_path(preview_output, BASE)
            if preview_output
            else resolve_non_reparse_path(preview.OUTPUT, BASE)
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_ratios(self, split_ratios: tuple[float, float, float]) -> tuple[float, float, float]:
        if len(split_ratios) != 3 or any(r <= 0 for r in split_ratios):
            raise ValueError("TRAIN/VALIDATION/TEST 분할 비율은 모두 양수여야 합니다.")
        total = sum(split_ratios)
        if abs(total - 1.0) > 1e-6:
            raise ValueError("TRAIN/VALIDATION/TEST 분할 비율의 합은 1.0이어야 합니다.")
        return (float(split_ratios[0]), float(split_ratios[1]), float(split_ratios[2]))

    def build_from_dataset(
        self,
        dataset_id: str,
        split_ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
        snapshot_id: str | None = None,
        split_policy: str = CHRONOLOGICAL_SPLIT_POLICY,
    ) -> dict:
        return self.build_from_datasets(
            [dataset_id],
            split_ratios=split_ratios,
            snapshot_id=snapshot_id,
            split_policy=split_policy,
        )

    def build_from_datasets(
        self,
        dataset_ids: list[str] | tuple[str, ...],
        split_ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
        snapshot_id: str | None = None,
        split_policy: str = CHRONOLOGICAL_SPLIT_POLICY,
    ) -> dict:
        ratios = self._validate_ratios(split_ratios)
        if split_policy not in (CHRONOLOGICAL_SPLIT_POLICY, SEASONAL_SPLIT_POLICY):
            raise ValueError(f"지원하지 않는 split_policy입니다: {split_policy}")
        if not dataset_ids:
            raise ValueError("최소 1개 이상의 dataset_id가 필요합니다.")
        ds_ids = [str(d).strip() for d in dataset_ids if str(d).strip()]
        if not ds_ids:
            raise ValueError("최소 1개 이상의 dataset_id가 필요합니다.")

        manifests = []
        csv_sources = []
        all_sources = []
        by_time = {}
        conflicts = set()
        anomaly_by_time = {}
        anomaly_conflicts = set()
        expected_station = None
        expected_sensor = None

        for dataset_id in ds_ids:
            if not re.fullmatch(r"\d{8}T\d{6}_[0-9a-f]{8}", dataset_id):
                raise ValueError("잘못된 dataset_id 형식입니다.")
            ds_folder = self.preview_output / dataset_id
            manifest_path = ds_folder / "dataset_manifest.json"
            if not manifest_path.is_file():
                raise ValueError(f"데이터셋 기록을 찾을 수 없습니다: {dataset_id}")
            ds_manifest = read_json(manifest_path)
            labeled_source = ds_folder / "joined_labeled.csv"
            if not labeled_source.is_file():
                raise ValueError(
                    "실제 MQC_FLAG 라벨 자료 joined_labeled.csv가 없어 B 0건 스냅샷을 만들 수 없습니다. "
                    "원본 CSV를 다시 분석한 뒤 새 스냅샷을 생성해 주세요."
                )
            labeled_info = ds_manifest.get("joined_labeled_csv")
            if isinstance(labeled_info, dict) and labeled_info.get("sha256"):
                if preview.sha256(labeled_source) != labeled_info["sha256"]:
                    raise ValueError("저장된 joined_labeled.csv 해시가 manifest와 일치하지 않습니다.")
            st = ds_manifest["station"]
            sn = ds_manifest["sensor"]
            if expected_station is None:
                expected_station, expected_sensor = st, sn
            elif (st, sn) != (expected_station, expected_sensor):
                raise ValueError("다중 데이터셋 병합 시 모든 데이터셋의 관측소/센서가 동일해야 합니다.")

            prov_csv = ds_folder / "joined_provenance.csv"
            joined_csv = ds_folder / "joined.csv"
            if prov_csv.is_file() and "joined_provenance_csv" in ds_manifest:
                if preview.sha256(prov_csv) != ds_manifest["joined_provenance_csv"]["sha256"]:
                    raise ValueError("저장된 joined_provenance.csv 해시가 manifest와 일치하지 않습니다.")
                csv_to_read = prov_csv
                has_source_col = True
            else:
                if not joined_csv.is_file() or preview.sha256(joined_csv) != ds_manifest["joined_csv"]["sha256"]:
                    raise ValueError("저장된 joined.csv 해시가 manifest와 일치하지 않습니다.")
                csv_to_read = joined_csv
                has_source_col = False

            manifests.append((dataset_id, manifest_path, ds_manifest, csv_to_read))
            csv_sources.append({
                "dataset_id": dataset_id,
                "dataset_manifest_sha256": preview.sha256(manifest_path),
                "joined_source_path": str(csv_to_read),
                "joined_source_sha256": preview.sha256(csv_to_read),
            })
            all_sources.extend(ds_manifest.get("sources", []))

            with csv_to_read.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                for idx, row in enumerate(reader):
                    obs_time = row["OBS_TIME"].strip()
                    src_time = row["SOURCE_OBS_TIMESTAMP"].strip() if has_source_col else obs_time
                    obs_val = float(row["OBS"])
                    prd_val = float(row["PRD"])
                    station = row["OBS_POST_ID"].strip()
                    sensor = row["OBS_ITEM_CODE"].strip()
                    row_id = digest_dict({
                        "dataset_id": dataset_id,
                        "row_index": idx,
                        "station": station,
                        "sensor": sensor,
                        "obs_time": obs_time,
                        "source_obs_timestamp": src_time,
                    })
                    rec = {
                        "row_id": row_id,
                        "OBS_POST_ID": station,
                        "OBS_ITEM_CODE": sensor,
                        "OBS_TIME": obs_time,
                        "SOURCE_OBS_TIMESTAMP": src_time,
                        "OBS": obs_val,
                        "PRD": prd_val,
                    }
                    if obs_time in anomaly_by_time:
                        anomaly_conflicts.add(obs_time)
                        anomaly_by_time.pop(obs_time, None)
                    if obs_time in conflicts:
                        continue
                    if obs_time in by_time:
                        prev = by_time[obs_time]
                        if (prev["OBS"], prev["PRD"]) != (obs_val, prd_val):
                            conflicts.add(obs_time)
                            del by_time[obs_time]
                    else:
                        by_time[obs_time] = rec

            labeled_csv = ds_folder / "joined_labeled.csv"
            if labeled_csv.is_file():
                with labeled_csv.open(encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    for row in reader:
                        if row.get("MQC_FLAG", "").strip() != "B":
                            continue
                        obs_time = row["OBS_TIME"].strip()
                        if obs_time in conflicts or obs_time in by_time or obs_time in anomaly_conflicts:
                            anomaly_conflicts.add(obs_time)
                            anomaly_by_time.pop(obs_time, None)
                            continue
                        obs_val = float(row["OBS"])
                        prd_val = float(row["PRD"])
                        src_time = row.get("SOURCE_OBS_TIMESTAMP", obs_time).strip()
                        if obs_time in anomaly_by_time:
                            prev_b = anomaly_by_time[obs_time]
                            if (prev_b["OBS"], prev_b["PRD"]) != (obs_val, prd_val):
                                anomaly_conflicts.add(obs_time)
                                del anomaly_by_time[obs_time]
                        else:
                            anomaly_by_time[obs_time] = {
                                "OBS_POST_ID": row["OBS_POST_ID"].strip(),
                                "OBS_ITEM_CODE": row["OBS_ITEM_CODE"].strip(),
                                "OBS_TIME": obs_time,
                                "SOURCE_OBS_TIMESTAMP": src_time,
                                "OBS": obs_val,
                                "PRD": prd_val,
                                "MQC_FLAG": "B",
                            }

        records = [by_time[t] for t in sorted(by_time)]
        if len(records) < 30:
            raise ValueError("스냅샷 생성을 위한 유효 결합 행 수가 부족합니다 (최소 30행 필요).")

        total = len(records)
        train_end = max(INPUT_WINDOW_MINUTES + 1, int(total * ratios[0]))
        val_end = max(train_end + INPUT_WINDOW_MINUTES + 1, int(total * (ratios[0] + ratios[1])))
        if val_end >= total - INPUT_WINDOW_MINUTES:
            raise ValueError("TEST 분할에 최소 5분 이상의 연속 구간을 배정할 수 없습니다.")

        for idx, rec in enumerate(records):
            if idx < train_end:
                rec["SPLIT"] = "TRAIN"
            elif idx < val_end:
                rec["SPLIT"] = "VALIDATION"
            else:
                rec["SPLIT"] = "TEST"

        if split_policy == SEASONAL_SPLIT_POLICY:
            # This validation is interpolation inside the development period;
            # only the final chronological holdout is an independent TEST.
            development_fraction = ratios[0] + ratios[1]
            month_start = 0
            while month_start < val_end:
                month_key = records[month_start]["OBS_TIME"][:7]
                month_end = month_start + 1
                while month_end < val_end and records[month_end]["OBS_TIME"][:7] == month_key:
                    month_end += 1
                month_train_end = month_start + int((month_end - month_start) * ratios[0] / development_fraction)
                for idx in range(month_start, month_end):
                    records[idx]["SPLIT"] = "TRAIN" if idx < month_train_end else "VALIDATION"
                month_start = month_end

        raw_times = [records[0]["OBS_TIME"], records[-1]["OBS_TIME"], *anomaly_by_time]
        interval_start = min(raw_times)
        interval_end = (pd.Timestamp(max(raw_times)) + pd.Timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        split_intervals = {name: [] for name in SPLIT_NAMES}
        run_split = records[0]["SPLIT"]
        for previous, current in zip(records, records[1:]):
            if current["SPLIT"] == run_split:
                continue
            boundary = current["OBS_TIME"]
            if (split_policy == SEASONAL_SPLIT_POLICY and current["SPLIT"] == "TRAIN"
                    and current["OBS_TIME"][:7] != previous["OBS_TIME"][:7]):
                boundary = current["OBS_TIME"][:7] + "-01 00:00:00"
            split_intervals[run_split].append({"start_time": interval_start, "end_time_exclusive": boundary})
            interval_start, run_split = boundary, current["SPLIT"]
        split_intervals[run_split].append({"start_time": interval_start, "end_time_exclusive": interval_end})

        frame = pd.DataFrame(records, columns=list(PARQUET_COLUMNS))
        snap_id = snapshot_id or (datetime.now().strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8])
        if not re.fullmatch(r"\d{8}T\d{6}_[0-9a-f]{8}", snap_id):
            raise ValueError("잘못된 snapshot_id 형식입니다.")
        snap_folder = self.root / snap_id
        snap_folder.mkdir(parents=True, exist_ok=False)

        parquet_path = snap_folder / "snapshot.parquet"
        frame.to_parquet(parquet_path, engine="pyarrow", index=False)
        parquet_sha = preview.sha256(parquet_path)
        with pq.ParquetFile(parquet_path) as pf:
            footer_rows = int(pf.metadata.num_rows)
            num_row_groups = int(pf.num_row_groups)

        anomaly_records = [anomaly_by_time[t] for t in sorted(anomaly_by_time) if t not in by_time and t not in conflicts]
        labeled_anomalies_path = snap_folder / "labeled_anomalies.csv"
        with labeled_anomalies_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["OBS_POST_ID", "OBS_ITEM_CODE", "OBS_TIME", "SOURCE_OBS_TIMESTAMP", "OBS", "PRD", "MQC_FLAG"])
            for item in anomaly_records:
                writer.writerow([
                    item["OBS_POST_ID"],
                    item["OBS_ITEM_CODE"],
                    item["OBS_TIME"],
                    item["SOURCE_OBS_TIMESTAMP"],
                    item["OBS"],
                    item["PRD"],
                    "B",
                ])

        splits_meta = {}
        for split_name in SPLIT_NAMES:
            sub = frame[frame["SPLIT"] == split_name].reset_index(drop=True)
            x_raw, _, target_times, _ = _contiguous_windows_for_frame(sub)
            split_digest = digest_dict({
                "split": split_name,
                "row_ids": sub["row_id"].tolist(),
                "window_targets": target_times,
            })
            splits_meta[split_name] = {
                "row_count": int(len(sub)),
                "window_count": int(len(x_raw)),
                "start_time": str(sub["OBS_TIME"].iloc[0]) if not sub.empty else None,
                "end_time": str(sub["OBS_TIME"].iloc[-1]) if not sub.empty else None,
                "sha256": split_digest,
                "intervals": split_intervals[split_name],
            }

        first_ds = manifests[0][2]
        station = expected_station
        sensor = expected_sensor
        primary_dataset_id = ds_ids[0] if len(ds_ids) == 1 else "+".join(ds_ids)
        snapshot_manifest = {
            "schema_version": "event-evidence-dataset-2",
            "snapshot_id": snap_id,
            "dataset_id": primary_dataset_id,
            "dataset_ids": ds_ids,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "domain": "fixed_station",
            "item_id": "tide",
            "target_variable": "TIDE_LEVEL",
            "station_scope": [station],
            "sensor_scope": [sensor],
            "station": station,
            "sensor": sensor,
            "input_window_minutes": INPUT_WINDOW_MINUTES,
            "horizon_minutes": HORIZON_MINUTES,
            "feature_columns": ["OBS", "PRD"],
            "split_policy": {
                "name": split_policy,
                "order": split_policy,
                "version": 1,
                "interval_closure": "left_closed_right_open",
                "validation_role": "development_interpolation" if split_policy == SEASONAL_SPLIT_POLICY else "chronological_validation",
                "ratios": {"TRAIN": ratios[0], "VALIDATION": ratios[1], "TEST": ratios[2]},
            },
            "time_alignment": first_ds.get("time_alignment", "exact_minute"),
            "column_normalization": first_ds.get("column_normalization", "strict"),
            "applied_column_mapping": first_ds.get("applied_column_mapping"),
            "date_start": min(m[2]["date_start"] for m in manifests),
            "date_end": max(m[2]["date_end"] for m in manifests),
            "total_rows": total,
            "total_windows": sum(s["window_count"] for s in splits_meta.values()),
            "anomaly_rows_count": len(anomaly_records),
            "labeled_anomalies_csv": {
                "path": str(labeled_anomalies_path),
                "sha256": preview.sha256(labeled_anomalies_path),
            },
            "splits": splits_meta,
            "parquet": {
                "path": str(parquet_path),
                "bytes": parquet_path.stat().st_size,
                "sha256": parquet_sha,
                "footer_rows": footer_rows,
                "num_row_groups": num_row_groups,
                "columns": list(PARQUET_COLUMNS),
            },
            "source_provenance": {
                "dataset_manifest_sha256": csv_sources[0]["dataset_manifest_sha256"],
                "joined_source_path": csv_sources[0]["joined_source_path"],
                "joined_source_sha256": csv_sources[0]["joined_source_sha256"],
                "dataset_manifests": csv_sources,
                "sources": all_sources,
            },
        }
        manifest_out = snap_folder / "snapshot_manifest.json"
        write_json(manifest_out, snapshot_manifest)
        return snapshot_manifest

    def validate_snapshot(self, snapshot_id: str) -> dict:
        if not re.fullmatch(r"\d{8}T\d{6}_[0-9a-f]{8}", snapshot_id):
            raise ValueError("잘못된 snapshot_id 형식입니다.")
        snap_folder = self.root / snapshot_id
        manifest_path = snap_folder / "snapshot_manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"스냅샷 manifest를 찾을 수 없습니다: {snapshot_id}")
        manifest = read_json(manifest_path)
        if manifest.get("schema_version") != "event-evidence-dataset-2":
            raise ValueError("지원하지 않는 스냅샷 schema_version입니다.")
        if manifest.get("domain") != "fixed_station" or manifest.get("item_id") != "tide" or manifest.get("target_variable") != "TIDE_LEVEL":
            raise ValueError("Ocean-AI 도메인/항목 규격(fixed_station / tide / TIDE_LEVEL)과 일치하지 않습니다.")
        parquet_info = manifest["parquet"]
        parquet_path = snap_folder / "snapshot.parquet"
        if not parquet_path.is_file():
            raise ValueError("스냅샷 Parquet 파일이 없습니다.")
        if parquet_path.stat().st_size != parquet_info["bytes"] or preview.sha256(parquet_path) != parquet_info["sha256"]:
            raise ValueError("스냅샷 Parquet 파일 해시 또는 크기가 변경되었습니다.")
        with pq.ParquetFile(parquet_path) as pf:
            if pf.metadata.num_rows != parquet_info["footer_rows"]:
                raise ValueError("Parquet footer_rows 불일치")
            if any(col not in pf.schema_arrow.names for col in PARQUET_COLUMNS):
                raise ValueError("Parquet 스키마 필수 컬럼 누락")
        labeled_anom_info = manifest.get("labeled_anomalies_csv")
        if isinstance(labeled_anom_info, dict) and labeled_anom_info.get("sha256"):
            labeled_anom_path = snap_folder / "labeled_anomalies.csv"
            if not labeled_anom_path.is_file():
                raise ValueError("스냅샷에 선언된 labeled_anomalies.csv 파일이 없습니다.")
            if preview.sha256(labeled_anom_path) != labeled_anom_info["sha256"]:
                raise ValueError("스냅샷 labeled_anomalies.csv 해시가 변경되었습니다.")
        return {
            "passed": True,
            "snapshot_id": snapshot_id,
            "sha256": parquet_info["sha256"],
            "total_rows": manifest["total_rows"],
            "total_windows": manifest["total_windows"],
        }

    def load_snapshot(self, snapshot_id: str):
        self.validate_snapshot(snapshot_id)
        snap_folder = self.root / snapshot_id
        manifest = read_json(snap_folder / "snapshot_manifest.json")
        if isinstance(manifest.get("parquet"), dict) and "path" in manifest["parquet"]:
            manifest["parquet"]["path"] = str(resolve_non_reparse_path(manifest["parquet"]["path"], BASE))
        if isinstance(manifest.get("labeled_anomalies_csv"), dict) and "path" in manifest["labeled_anomalies_csv"]:
            manifest["labeled_anomalies_csv"]["path"] = str(
                resolve_non_reparse_path(manifest["labeled_anomalies_csv"]["path"], BASE)
            )
        prov = manifest.get("source_provenance")
        if isinstance(prov, dict):
            for key in ("joined_csv_path", "joined_provenance_csv_path", "joined_source_path"):
                if prov.get(key):
                    prov[key] = str(resolve_non_reparse_path(prov[key], BASE))
            for list_key in ("datasets", "dataset_manifests"):
                for ds_item in prov.get(list_key) or []:
                    if isinstance(ds_item, dict):
                        for key in ("joined_csv_path", "joined_provenance_csv_path", "joined_source_path"):
                            if ds_item.get(key):
                                ds_item[key] = str(resolve_non_reparse_path(ds_item[key], BASE))
        frame = pd.read_parquet(snap_folder / "snapshot.parquet", engine="pyarrow")
        return manifest, frame

    def extract_split_windows(self, snapshot_id: str) -> tuple[dict, dict]:
        manifest, frame = self.load_snapshot(snapshot_id)
        splits = {}
        for split_name in SPLIT_NAMES:
            sub = frame[frame["SPLIT"] == split_name].reset_index(drop=True)
            x_raw, y_raw, target_times, target_source_times = _contiguous_windows_for_frame(sub)
            split_digest = digest_dict({
                "split": split_name,
                "row_ids": sub["row_id"].tolist(),
                "window_targets": target_times,
            })
            if split_digest != manifest["splits"][split_name]["sha256"]:
                raise ValueError(f"{split_name} 분할 행/창 무결성 해시가 스냅샷 기록과 다릅니다.")
            splits[split_name] = {
                "frame": sub,
                "X_raw": x_raw,
                "y_raw": y_raw,
                "timestamps": target_times,
                "source_obs_timestamps": target_source_times,
            }
        return manifest, splits

    def split_target_intervals(
        self, snapshot_id: str, split: str, manifest: dict | None = None,
    ) -> list[tuple[str, str]]:
        """Return raw target membership [start, end), including B-only minutes.

        Old chronological snapshots use the next split's first G minute as the
        exclusive end; the final interval also includes trailing B timestamps.
        """
        if split not in SPLIT_NAMES:
            raise ValueError(f"지원하지 않는 분할입니다: {split}")
        if manifest is None:
            manifest = read_json(self.root / snapshot_id / "snapshot_manifest.json")
        metadata = manifest.get("splits", {}).get(split, {})
        if "intervals" in metadata:
            intervals = [(item["start_time"], item["end_time_exclusive"]) for item in metadata["intervals"]]
            if any(pd.Timestamp(start) >= pd.Timestamp(end) for start, end in intervals):
                raise ValueError(f"{split} 분할 구간의 시작과 끝이 올바르지 않습니다.")
            return intervals
        if manifest.get("split_policy", {}).get("name") == SEASONAL_SPLIT_POLICY:
            raise ValueError("계절 균형 분할의 명시적 intervals가 없습니다.")
        chronological = sorted(
            (item["start_time"], item["end_time"], name)
            for name, item in manifest.get("splits", {}).items()
            if item.get("start_time") and item.get("end_time")
        )
        raw_times = [value for start, end, _ in chronological for value in (start, end)]
        anomaly_path = self.root / snapshot_id / "labeled_anomalies.csv"
        if anomaly_path.is_file():
            with anomaly_path.open(encoding="utf-8-sig", newline="") as stream:
                raw_times.extend(row["OBS_TIME"].strip() for row in csv.DictReader(stream))
        elif not manifest.get("labeled_anomalies_csv"):
            # Legacy extraction reads these same label files. Their trailing B
            # minutes must also determine the inferred final TEST interval.
            for dataset_id in manifest.get("dataset_ids") or [manifest.get("dataset_id", "")]:
                for part in str(dataset_id).split("+"):
                    if not part.strip():
                        continue
                    label_path = self.preview_output / part.strip() / "joined_labeled.csv"
                    if label_path.is_file():
                        with label_path.open(encoding="utf-8-sig", newline="") as stream:
                            raw_times.extend(row["OBS_TIME"].strip() for row in csv.DictReader(stream)
                                             if row.get("MQC_FLAG", "").strip() == "B")
        for index, (start, end, name) in enumerate(chronological):
            if name != split:
                continue
            if index == 0:
                start = min(raw_times)
            exclusive_end = (chronological[index + 1][0] if index + 1 < len(chronological)
                             else (pd.Timestamp(max(raw_times)) + pd.Timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"))
            return [(start, exclusive_end)]
        return []

    def extract_labeled_evaluation_windows(
        self,
        snapshot_id: str,
        manifest: dict | None = None,
        splits: dict | None = None,
        target_start: str | None = None,
        target_end: str | None = None,
        target_intervals: list[tuple[str, str]] | None = None,
    ) -> dict:
        """Extract ground-truth MQC_FLAG ('G'=0 Normal, 'B'=1 Anomaly) 4-input + 1-target windows.

        Keep every real B target with four contiguous reference minutes, regardless of amplitude.
        Intervals are left-closed/right-open and default to the independent TEST.
        Every reference minute must belong to the target's individual interval.
        Legacy inclusive target bounds are retained for explicit callers.
        Preceding B reference values retain the existing last-G-residual policy.
        """
        if manifest is None or splits is None:
            manifest, splits = self.extract_split_windows(snapshot_id)
        snap_folder = self.root / snapshot_id
        if target_intervals is None and not (target_start or target_end) and manifest.get("splits"):
            target_intervals = self.split_target_intervals(snapshot_id, "TEST", manifest=manifest)
        normalized_intervals = None
        if target_intervals is not None:
            normalized_intervals = [
                (pd.Timestamp(start).strftime("%Y-%m-%d %H:%M:%S"),
                 pd.Timestamp(end).strftime("%Y-%m-%d %H:%M:%S"))
                for start, end in target_intervals
            ]
            if any(start >= end for start, end in normalized_intervals):
                raise ValueError("target_intervals의 시작은 끝보다 빨라야 합니다.")

        def target_interval(timestamp: str):
            if (target_start and timestamp < target_start) or (target_end and timestamp > target_end):
                return None
            if normalized_intervals is None:
                return (target_start, None)
            return next(((start, end) for start, end in normalized_intervals if start <= timestamp < end), None)

        raw_anomaly_rows: list[tuple[str, float, float, str]] = []
        seen_anom_ts: set[str] = set()
        labeled_anomalies_csv = snap_folder / "labeled_anomalies.csv"
        label_evidence_available = labeled_anomalies_csv.is_file()
        if manifest.get("labeled_anomalies_csv") and not label_evidence_available:
            raise ValueError("선언된 이상치 라벨 파일 labeled_anomalies.csv가 없습니다.")
        if labeled_anomalies_csv.is_file():
            with labeled_anomalies_csv.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    ts_str = row["OBS_TIME"].strip()
                    if ts_str not in seen_anom_ts:
                        seen_anom_ts.add(ts_str)
                        raw_anomaly_rows.append((
                            ts_str,
                            float(row["OBS"]),
                            float(row["PRD"]),
                            row.get("SOURCE_OBS_TIMESTAMP", ts_str).strip(),
                        ))
        else:
            ds_ids = manifest.get("dataset_ids") or [manifest.get("dataset_id", "")]
            for ds_id in ds_ids:
                for part_id in str(ds_id).split("+"):
                    part_id = part_id.strip()
                    if not part_id:
                        continue
                    labeled_csv = self.preview_output / part_id / "joined_labeled.csv"
                    if labeled_csv.is_file():
                        label_evidence_available = True
                        with labeled_csv.open(encoding="utf-8-sig", newline="") as stream:
                            for row in csv.DictReader(stream):
                                if row.get("MQC_FLAG", "").strip() == "B":
                                    ts_str = row["OBS_TIME"].strip()
                                    if ts_str not in seen_anom_ts:
                                        seen_anom_ts.add(ts_str)
                                        raw_anomaly_rows.append((
                                            ts_str,
                                            float(row["OBS"]),
                                            float(row["PRD"]),
                                            row.get("SOURCE_OBS_TIMESTAMP", ts_str).strip(),
                                        ))

        if not label_evidence_available:
            raise ValueError("실제 MQC_FLAG 라벨 자료가 없어 B 0건으로 판단할 수 없습니다. 원본 CSV로 스냅샷을 다시 생성해 주세요.")
        if not raw_anomaly_rows:
            return {
                "X_test_normal": splits["TEST"]["X_raw"],
                "y_test_normal": splits["TEST"]["y_raw"],
                "test_normal_timestamps": splits["TEST"]["timestamps"],
                "X_natural_b": np.empty((0, INPUT_WINDOW_MINUTES, 2), dtype=float),
                "y_natural_b": np.empty((0, 1), dtype=float),
                "natural_b_timestamps": [],
                "natural_b_prd": np.empty((0,), dtype=float),
                "total_anomaly_rows": 0,
                "strict_4g_1b_windows": 0,
                "all_contiguous_b_windows": 0,
                "contiguous_4g_1b_windows": 0,
            }

        frames = [splits[k]["frame"] for k in SPLIT_NAMES if k in splits and not splits[k]["frame"].empty]
        ordered_g = (
            pd.concat(frames, ignore_index=True).sort_values("OBS_TIME").reset_index(drop=True)
            if frames
            else self.load_snapshot(snapshot_id)[1].sort_values("OBS_TIME").reset_index(drop=True)
        )
        g_map: dict[str, tuple[float, float, str]] = {
            str(ts).strip(): (float(obs_v), float(prd_v), str(src_ts).strip())
            for ts, obs_v, prd_v, src_ts in zip(
                ordered_g["OBS_TIME"].tolist(),
                ordered_g["OBS"].tolist(),
                ordered_g["PRD"].tolist(),
                ordered_g["SOURCE_OBS_TIMESTAMP"].tolist(),
            )
        }

        anomaly_rows = [item for item in raw_anomaly_rows if item[0] not in g_map]
        anomaly_rows.sort(key=lambda item: item[0])
        b_map: dict[str, tuple[float, float, str]] = {
            ts_str: (obs_val, prd_val, src_ts) for ts_str, obs_val, prd_val, src_ts in anomaly_rows
        }
        all_ts_sorted = sorted(set(g_map.keys()) | set(b_map.keys()))
        clean_ref_map: dict[str, tuple[float, float]] = {}
        last_g_residual = (
            float(ordered_g["OBS"].iloc[0] - ordered_g["PRD"].iloc[0])
            if not ordered_g.empty
            else 0.0
        )
        for ts_str in all_ts_sorted:
            if ts_str in g_map:
                o_val, p_val, _ = g_map[ts_str]
                last_g_residual = o_val - p_val
                clean_ref_map[ts_str] = (o_val, p_val)
            else:
                o_val, p_val, _ = b_map[ts_str]
                expected_o = p_val + last_g_residual
                clean_ref_map[ts_str] = (expected_o, p_val)

        strict_4g_1b_count = 0
        all_candidates = []
        for ts_str, obs_val, prd_val, _ in anomaly_rows:
            interval = target_interval(ts_str)
            if interval is None:
                continue
            t_dt = pd.Timestamp(ts_str)
            prev_keys = [(t_dt - pd.Timedelta(minutes=offset)).strftime("%Y-%m-%d %H:%M:%S") for offset in (4, 3, 2, 1)]
            if normalized_intervals is not None and prev_keys[0] < interval[0]:
                continue
            if all(k in g_map for k in prev_keys):
                strict_4g_1b_count += 1
            if all(k in clean_ref_map for k in prev_keys):
                x_win = [[clean_ref_map[k][0], clean_ref_map[k][1]] for k in prev_keys]
                item_tuple = (x_win, [obs_val], ts_str, prd_val)
                all_candidates.append(item_tuple)

        selected_b = all_candidates
        x_b_list = [item[0] for item in selected_b]
        y_b_list = [item[1] for item in selected_b]
        b_timestamps = [item[2] for item in selected_b]

        if x_b_list:
            x_natural_b = np.asarray(x_b_list, dtype=float)
            y_natural_b = np.asarray(y_b_list, dtype=float)
        else:
            x_natural_b = np.empty((0, INPUT_WINDOW_MINUTES, 2), dtype=float)
            y_natural_b = np.empty((0, 1), dtype=float)

        return {
            "X_test_normal": splits["TEST"]["X_raw"],
            "y_test_normal": splits["TEST"]["y_raw"],
            "test_normal_timestamps": splits["TEST"]["timestamps"],
            "X_natural_b": x_natural_b,
            "y_natural_b": y_natural_b,
            "natural_b_timestamps": b_timestamps,
            "natural_b_prd": np.asarray([item[3] for item in selected_b], dtype=float),
            "total_anomaly_rows": sum(
                1 for item in anomaly_rows
                if target_interval(item[0]) is not None
            ),
            "strict_4g_1b_windows": int(strict_4g_1b_count),
            "all_contiguous_b_windows": int(len(all_candidates)),
            "contiguous_4g_1b_windows": int(len(x_natural_b)),
        }

    def list_snapshots(self) -> list[dict]:
        items = []
        for path in sorted(self.root.glob("*/snapshot_manifest.json"), reverse=True):
            try:
                data = read_json(path)
            except (OSError, ValueError):
                continue
            items.append({
                "snapshot_id": data["snapshot_id"],
                "dataset_id": data["dataset_id"],
                "station": data["station"],
                "sensor": data["sensor"],
                "date_start": data["date_start"],
                "date_end": data["date_end"],
                "selected_yms": data.get("selected_yms") or [],
                "total_rows": data["total_rows"],
                "total_windows": data["total_windows"],
                "anomaly_rows_count": data.get("anomaly_rows_count"),
                "time_alignment": data.get("time_alignment", "exact_minute"),
                "column_normalization": data.get("column_normalization", "strict"),
                "split_policy": data.get("split_policy"),
                "splits": data["splits"],
                "created_at": data["created_at"],
            })
        items.sort(key=lambda item: (
            -(datetime.fromisoformat(item["date_end"]) - datetime.fromisoformat(item["date_start"])).days,
            -int(str(item["date_end"]).replace("-", "")),
            item["station"], item["sensor"], str(item["created_at"]),
        ))
        return items

