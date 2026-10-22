"""Chronological, label-isolated replay of the unchanged regional QC functions."""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
from collections import OrderedDict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

np: Any = importlib.import_module("numpy")
pd: Any = importlib.import_module("pandas")


def json_value(value) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat(sep=" ")
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, deque)):
        return [json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


class _PredictionCache:
    """Cache only exact raw windows; interpolated windows use the original call."""

    def __init__(self, model):
        self.model = model
        self.windows = {}
        self.timestamp = None
        self.force_single = False
        self.enabled = True
        self.hits = self.single_calls = self.precompute_calls = 0

    def predict(self, values, verbose=0):
        entry = self.windows.get(self.timestamp)
        if self.enabled and not self.force_single and entry is not None and np.array_equal(values[0], entry[0]):
            self.hits += 1
            return entry[1].reshape(1, -1).copy()
        self.single_calls += 1
        return self.model.predict(values, verbose=verbose)

    def precompute(self, points, scaler):
        if len(points) < 5:
            self.windows = {}
            return
        if any(getattr(layer, "stateful", False) for layer in getattr(self.model, "layers", [])):
            raise ValueError("상태를 가진 신경망은 원시 입력 예측 캐시를 사용할 수 없습니다.")
        raw = np.asarray([[point["OBS"], point["TIDE_PRE_VAL"]] for point in points], dtype=float)
        raw = np.where(pd.isna(raw), 0.0, raw)
        scaled = np.asarray(scaler.transform(pd.DataFrame(raw, columns=["OBS", "PRD"])))
        windows = np.stack([scaled[index - 4:index] for index in range(4, len(points))])
        # A single API call with microbatch size 1 retains the exact original
        # LSTM batch shape. Larger batches can change floating-point last bits.
        predictions = np.asarray(self.model.predict(windows, batch_size=1, verbose=0))
        if predictions.shape != (len(windows), 1) or not np.isfinite(predictions).all():
            raise ValueError("원시 입력 선계산 예측의 모양이나 값이 올바르지 않습니다.")
        self.precompute_calls += 1
        self.windows = {points[index + 4]["timestamp"]: (window, prediction)
                        for index, (window, prediction) in enumerate(zip(windows, predictions))}


class ReplayEngine:
    """One independent state machine for one sensor and one frozen bundle."""

    def __init__(self, bundle, *, sea=None, config=None, optimize=True, start_time=None, end_time=None):
        from scripts.local_qc.legacy import build_config, get_legacy_module
        self.bundle = bundle
        self.module = get_legacy_module(sea or bundle.sea)
        self.config = copy.deepcopy(config if config is not None else build_config(sea or bundle.sea))
        self.config["db_engine"] = None
        self.config["debug_log_path"] = self._capture
        self.optimize = bool(optimize)
        self.start_time = pd.Timestamp(start_time) if start_time is not None else None
        self.end_time = pd.Timestamp(end_time) if end_time is not None else None
        self.predictor = _PredictionCache(bundle.model)
        self.predictor.enabled = self.optimize
        deployed = getattr(bundle, "operational_deploy_threshold_3sigma_cm", None)
        if deployed is None:
            deployed = bundle.raw_threshold_3sigma_cm
        self.state = {"data_buffer": deque(), "stable_normal_residual": 0.0,
            "last_anomaly_time": None, "analysis_log": OrderedDict(),
            "model": self.predictor, "scaler": bundle.scaler,
            "effective_lstm_threshold_cm": float(bundle.effective_lstm_threshold_cm),
            "dev_file_threshold_cm": float(deployed)}
        self.rows = OrderedDict()
        self.raw_tail = []
        self.last_timestamp = None
        self._details = None
        self.raw_predictions = {}

    def _capture(self, details):
        self._details = copy.deepcopy(details)

    @staticmethod
    def _sanitize(point):
        timestamp = pd.Timestamp(point["timestamp"])
        if pd.isna(timestamp) or timestamp.tzinfo is not None or timestamp.second or timestamp.microsecond:
            raise ValueError("입력 시각은 시간대 정보 없는 정확한 분이어야 합니다.")
        obs, prd = float(point["OBS"]), float(point["TIDE_PRE_VAL"])
        if math.isinf(obs) or math.isinf(prd):
            raise ValueError("QC 입력에 무한대 값을 사용할 수 없습니다.")
        # Neither truth labels nor pre-existing AI decisions enter the engine.
        return {"timestamp": timestamp, "OBS": obs, "TIDE_PRE_VAL": prd,
                "MQC_FLAG": "G", "AI_FLAG": "1", "IS_DB_NULL": bool(pd.isna(obs))}

    def run(self, points):
        incoming = [self._sanitize(point) for point in points]
        previous = self.last_timestamp
        for point in incoming:
            if previous is not None and point["timestamp"] - previous != pd.Timedelta(minutes=1):
                raise ValueError("모든 입력은 중복 없이 연속 1분 간격이어야 합니다. 결측 분도 공급해 주세요.")
            previous = point["timestamp"]
        if self.optimize and incoming:
            self.prepare(incoming)
        for point in incoming:
            self._step(point)
            self.raw_tail = (self.raw_tail + [copy.deepcopy(point)])[-4:]
        return self.result()

    def prepare(self, points):
        """Precompute raw forecasts without advancing any QC state."""
        incoming = [self._sanitize(point) for point in points]
        self.predictor.precompute(self.raw_tail + incoming, self.bundle.scaler)
        for timestamp, (_, scaled_prediction) in self.predictor.windows.items():
            restored = self.bundle.scaler.inverse_transform(
                np.hstack([scaled_prediction.reshape(1, 1), np.zeros_like(scaled_prediction.reshape(1, 1))]))
            self.raw_predictions[timestamp] = float(restored[0, 0])

    def _step(self, point):
        timestamp = point["timestamp"]
        buffer = self.state["data_buffer"]
        before = {item["timestamp"]: str(item["AI_FLAG"]) for item in buffer}
        last_residual = buffer[-1].get("last_residual_applied", 0.0) if buffer else 0.0
        self.predictor.timestamp = timestamp
        self.predictor.force_single = any(item["AI_FLAG"] != "1" and pd.notna(last_residual)
            and pd.notna(item["TIDE_PRE_VAL"]) for item in list(buffer)[-4:])
        self._details = None
        self.module.process_data_point((self.bundle.station, self.bundle.sensor), point,
                                       self.state, self.config)
        log = self.state["analysis_log"][timestamp]
        details = self._details or {"timestamp": timestamp, "real_obs": point["OBS"],
            "tide_pre_val": point["TIDE_PRE_VAL"], "predicted_obs": log["predicted"],
            "diff": log["diff"], "threshold": self.bundle.effective_lstm_threshold_cm,
            "initial_flag": "1", "final_flag": log["AI_FLAG"], "decision_source": "WARMUP_BUFFER",
            "lstm_flag": 1, "sudden_change_flag": 1, "flat_value_flag": 1, "sneaky_drift_flag": 1}
        prediction = details["predicted_obs"]
        raw_lstm = bool(pd.notna(prediction) and abs(point["OBS"] - prediction) > self.bundle.effective_lstm_threshold_cm)
        online = str(details["final_flag"])
        row = {**details, "online_flag": online, "online_source": details["decision_source"],
            "consolidated_flag": online, "consolidated_source": details["decision_source"],
            "interpolate_count": int(log["interpolated_count"]),
            "last_residual_applied": float(log["last_residual_applied"]),
            "raw_lstm_anomaly": raw_lstm, "trend_reversed": raw_lstm and details["lstm_flag"] == 1,
            "warmup": self.start_time is not None and timestamp < self.start_time,
            "retroactive_changes": []}
        row.pop("mqc_flag", None)
        self.rows[timestamp] = row
        before[timestamp] = online
        for item in self.state["data_buffer"]:
            target, new_flag = item["timestamp"], str(item["AI_FLAG"])
            old_flag = before.get(target)
            if old_flag is None or old_flag == new_flag:
                continue
            source = {"7": "SNEAKY_DRIFT", "6": "FLAT_VALUE"}.get(new_flag, "LEGACY_BUFFER_MUTATION")
            change = {"timestamp": target, "old_flag": old_flag, "new_flag": new_flag,
                      "source": source, "notification_time": timestamp, "is_retroactive": target < timestamp}
            row["retroactive_changes"].append(change)
            if target in self.rows:
                self.rows[target]["consolidated_flag"] = new_flag
                self.rows[target]["consolidated_source"] = source
        self.last_timestamp = timestamp

    def _identity(self):
        settings = {key: value for key, value in self.config.items() if key not in ("db_engine", "debug_log_path")}
        # tuple-key maps need a stable representation independent of dict order.
        settings = {key: sorted((repr(k), v) for k, v in value.items()) if isinstance(value, dict) else value
                    for key, value in settings.items()}
        payload = {"station": self.bundle.station, "sensor": self.bundle.sensor,
            "role": self.bundle.role, "metadata": self.bundle.metadata,
            "raw": self.bundle.raw_threshold_3sigma_cm, "effective": self.bundle.effective_lstm_threshold_cm,
            "operational_deploy": getattr(self.bundle, "operational_deploy_threshold_3sigma_cm", None),
            "settings": settings, "start_time": self.start_time, "end_time": self.end_time}
        return hashlib.sha256(json.dumps(json_value(payload), sort_keys=True).encode()).hexdigest()

    def result(self):
        return {"station": self.bundle.station, "sensor": self.bundle.sensor, "role": self.bundle.role,
                "start_time": json_value(self.start_time), "end_time": json_value(self.end_time),
                "metadata": json_value(self.bundle.metadata), "rows": json_value(list(self.rows.values()))}

    def save_state(self, path):
        state = {key: value for key, value in self.state.items() if key not in ("model", "scaler", "analysis_log", "data_buffer")}
        payload = {"schema_version": "local-qc-state-1", "identity": self._identity(),
            "start_time": json_value(self.start_time), "end_time": json_value(self.end_time),
            "state": state, "buffer": list(self.state["data_buffer"]),
            "analysis": list(self.state["analysis_log"].values()), "rows": list(self.rows.values()),
            "raw_tail": self.raw_tail, "last_timestamp": self.last_timestamp,
            "raw_predictions": [[timestamp, value] for timestamp, value in self.raw_predictions.items()]}
        Path(path).write_text(json.dumps(json_value(payload), ensure_ascii=False, allow_nan=False), encoding="utf-8")

    @classmethod
    def load_state(cls, path, bundle, *, config=None, optimize=True):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != "local-qc-state-1":
            raise ValueError("지원하지 않는 QC 상태 파일입니다.")
        engine = cls(bundle, config=config, optimize=optimize,
                     start_time=payload["start_time"], end_time=payload["end_time"])
        if engine._identity() != payload["identity"]:
            raise ValueError("상태 파일과 모델·임계값·해역 설정이 다릅니다.")

        def restore(item):
            item = dict(item)
            item["timestamp"] = pd.Timestamp(item["timestamp"])
            for key in ("OBS", "TIDE_PRE_VAL", "real", "predicted", "diff", "prd_obs_residual"):
                if key in item and item[key] is None:
                    item[key] = float("nan")
            return item

        state = payload["state"]
        if state.get("last_anomaly_time") is not None:
            state["last_anomaly_time"] = pd.Timestamp(state["last_anomaly_time"])
        engine.state.update(state)
        engine.state["data_buffer"] = deque(restore(item) for item in payload["buffer"])
        engine.state["analysis_log"] = OrderedDict((item["timestamp"], item)
                                                  for item in map(restore, payload["analysis"]))
        engine.rows = OrderedDict((pd.Timestamp(item["timestamp"]), item) for item in payload["rows"])
        engine.raw_tail = [restore(item) for item in payload["raw_tail"]]
        engine.raw_predictions = {pd.Timestamp(timestamp): value for timestamp, value in payload["raw_predictions"]}
        engine.last_timestamp = pd.Timestamp(payload["last_timestamp"]) if payload["last_timestamp"] else None
        return engine


def save_state(engine, path):
    engine.save_state(path)


def load_state(path, bundle, **kwargs):
    return ReplayEngine.load_state(path, bundle, **kwargs)


def replay_stream(stream, bundles, *, optimize=True, config=None):
    points = list(stream.iter_points())
    engines = {}
    for bundle in bundles:
        if (bundle.station, bundle.sensor) != (stream.station, stream.sensor):
            raise ValueError("입력 자료와 모델의 관측소·센서가 다릅니다.")
        if bundle.role in engines:
            raise ValueError("동일 역할의 모델을 중복 실행할 수 없습니다.")
        engine = ReplayEngine(bundle, config=config, optimize=optimize,
                              start_time=stream.start_time, end_time=stream.end_time)
        engine.run(points)
        engines[bundle.role] = engine
    result = {"schema_version": "local-qc-replay-1", "station": stream.station, "sensor": stream.sensor,
        "start_time": json_value(stream.start_time), "end_time": json_value(stream.end_time),
        "metadata": json_value(stream.metadata), "models": {key: engine.result() for key, engine in engines.items()}}
    return result, engines
