"""Operational QC core copied without database or filesystem entry points."""
# These inherited typing diagnostics are disabled to preserve the original AST.
# pyright: reportInvalidTypeForm=false, reportArgumentType=false, reportOperatorIssue=false, reportPossiblyUnboundVariable=false
from __future__ import annotations

import importlib
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple

np: Any = importlib.import_module("numpy")
pd: Any = importlib.import_module("pandas")
# Original annotations are deferred; TensorFlow is intentionally never imported here.
tf: Any = None



SOURCE_METADATA = {'source_relative_path': 'AI_QC_west_sea_no_update.py',
 'source_sha256': '7768d86f2b513ca1412ad1e5d6a82ba58ae07a371a5e49c83b783b81ac1c30a4',
 'core_functions': ['prepare_model_input_data',
                    'predict_and_inverse_transform',
                    'detect_anomaly',
                    'detect_sneaky_drift',
                    'detect_flat_value',
                    'reevaluate_lstm_anomaly_with_trend',
                    'update_last_residual',
                    '_decide_final_flag_and_source',
                    'process_data_point',
                    'create_synthetic_gap_point'],
 'allowed_changes': ['Remove Oracle, TensorFlow and filesystem initialization imports and entry points.',
                     'Remove database credentials and client configuration.',
                     'Defer annotations and load numpy/pandas through importlib.',
                     'Replace log_decision_process with a callable in-memory sink; preserve every core '
                     'function AST.']}

CONFIG = {'MODEL_ASSETS_DIR': './model_output_forecast',
 'LOCAL_DATA_SAVE_PATH': './local_selene_data',
 'DEBUG_LOG_SAVE_PATH': './debug_logs',
 'FILENAMES': {'MAPPING_CSV': 'mappingBySea.csv',
               'SNEAKY_DRIFT_MULTIPLIER_FILE': 'threshold_multiplier.sneaky',
               'RESIDUAL_STD_THRESHOLDS_FILE': 'residual_std_thresholds.csv',
               'MODEL_FILE': 'residual_lstm_forecast.h5',
               'SCALER_FILE': 'scaler.forecast.gz',
               'DEV_SUFFIX': 'Thres.forecast.DEV',
               'STATE_FILE_SUFFIX': '_state.pkl',
               'DEBUG_LOG_PREFIX': 'debug_log_',
               'PERIODIC_LOG_PREFIX': 'log_',
               'FINAL_LOG_PREFIX': 'final_log_',
               'LOCAL_OBS_SUFFIX': '.dat',
               'LOCAL_PRD_SUFFIX': '.PRD'},
 'TARGET_SEA': '서해',
 'DATE_FORMAT_FULL': '%Y%m%d%H%M%S',
 'FETCH_INTERVAL_MINUTES': 1,
 'STATE_SAVE_INTERVAL_MINUTES': 1,
 'UPDATE_DB_FOR_GAPS': False,
 'REALTIME_OFFSET_MINUTES': 90,
 'AI_MODEL_WINDOW_SIZE': 5,
 'SUDDEN_CHANGE_THRESHOLD_CM': 20.0,
 'FLAT_VALUE_THRESHOLD_MINUTES': 50,
 'SNEAKY_DRIFT_CHECK_INTERVAL_MINUTES': 20,
 'SNEAKY_DRIFT_WINDOW_MINUTES': 90,
 'DEFAULT_SNEAKY_DRIFT_MULTIPLIER': 2.5,
 'DEFAULT_RESIDUAL_STD_THRESHOLD': 5.0,
 'LEARNING_QUARANTINE_MINUTES': 30,
 'LOW_FLUCTUATION_PRD_THRESHOLD': 0.5,
 'FINAL_SAFETY_NET_THRESHOLD_CM': 100.0}

AQC_AI_FLAG_POSITION = 11

FLAG_NORMAL = '1'

FLAG_LSTM_ERROR = '4'

FLAG_GAP = '9'

FLAG_SUDDEN_CHANGE = '5'

FLAG_FLAT_VALUE = '6'

FLAG_SNEAKY_DRIFT = '7'

FLAG_FINAL_SAFETY = '8'



def prepare_model_input_data(data_buffer: Deque[Dict], input_length: int, last_residual: float, scaler: Any) -> Tuple[
    np.ndarray, int]:
    """LSTM 모델의 입력 데이터를 준비하며, 필요시 보간을 수행합니다."""
    window_data_for_input = list(data_buffer)[-(input_length + 1):-1]

    interpolated_obs_input = []
    interpolate_count = 0
    for item in window_data_for_input:
        is_abnormal = item["AI_FLAG"] != FLAG_NORMAL
        can_interpolate = pd.notna(last_residual) and pd.notna(item["TIDE_PRE_VAL"])
        if is_abnormal and can_interpolate:
            # 이상 상태일 경우, (예측조위 + 정상 잔차의 표준편차)로 값을 보간하여 모델 입력을 생성
            interpolated_obs_input.append(item["TIDE_PRE_VAL"] + last_residual)
            interpolate_count += 1
        else:
            interpolated_obs_input.append(item["OBS"])

    prd_input_values = [item["TIDE_PRE_VAL"] for item in window_data_for_input]

    dummy_data = [
        [obs if pd.notna(obs) else 0, prd if pd.notna(prd) else 0]
        for obs, prd in zip(interpolated_obs_input, prd_input_values)
    ]

    if not dummy_data or len(dummy_data) != input_length:
        return np.zeros((1, input_length, 2)), 0

    transformed_data = scaler.transform(pd.DataFrame(dummy_data, columns=["OBS", "PRD"]))
    return transformed_data.reshape(1, input_length, 2), interpolate_count

def predict_and_inverse_transform(model: tf.keras.Model, scaler: Any, X_input: np.ndarray) -> float:
    """예측을 수행하고 결과를 역변환합니다."""
    if X_input.shape[1] == 0:
        return np.nan
    y_pred_scaled = model.predict(X_input, verbose=0)
    # 역변환은 두 개의 열이 필요하므로, PRD를 위한 더미 열을 추가
    inversed_pred = scaler.inverse_transform(np.hstack([y_pred_scaled, np.zeros_like(y_pred_scaled)]))
    return inversed_pred[:, 0][0]

def detect_anomaly(current_obs: float, predicted_obs: float, threshold: float) -> Tuple[float, int]:
    """관측값과 예측값을 비교하여 이상 현상을 탐지합니다."""
    if pd.isna(current_obs) or pd.isna(predicted_obs):
        return np.nan, 4  # 예측조위 값이 누락된 경우 이상으로 플래그

    diff = abs(current_obs - predicted_obs)
    flag = 4 if diff > threshold else 1
    return diff, flag

def detect_sneaky_drift(data_buffer: Deque[Dict], analysis_logs_dict: OrderedDict, check_interval: int,
                        window_minutes: int, station: str, sensor: str, multipliers_map: Dict,
                        default_multiplier: float, threshold_cm_3sigma: float) -> Tuple[bool, List[Dict]]:
    """긴 시간 창에 걸쳐 느리고 지속적인 편향을 탐지합니다."""
    changed_points = []
    is_drift_detected = False
    current_data_point = data_buffer[-1]
    current_time = current_data_point["timestamp"]

    is_check_time = (current_time.minute % check_interval == 0)
    is_buffer_sufficient = len(data_buffer) >= window_minutes + 1

    if is_check_time and is_buffer_sufficient:
        drift_window_data = list(data_buffer)[-(window_minutes + 1):]
        obs_start, obs_end = drift_window_data[0]["OBS"], drift_window_data[-1]["OBS"]
        prd_start, prd_end = drift_window_data[0]["TIDE_PRE_VAL"], drift_window_data[-1]["TIDE_PRE_VAL"]

        if all(pd.notna(v) for v in [obs_start, obs_end, prd_start, prd_end]):
            drift_metric = abs((obs_end - obs_start) - (prd_end - prd_start))
            active_multiplier = multipliers_map.get((station, sensor), default_multiplier)
            sneaky_drift_threshold = threshold_cm_3sigma * active_multiplier

            if drift_metric > sneaky_drift_threshold:
                is_drift_detected = True
                logging.warning(
                    f"교활한 편향(SNEAKY DRIFT) 탐지: {station}/{sensor} ({current_time}), "
                    f"지표: {drift_metric:.2f} > 임계값: {sneaky_drift_threshold:.2f}"
                )
                for point in drift_window_data:
                    if point["AI_FLAG"] != FLAG_SNEAKY_DRIFT:
                        changed_points.append({
                            "timestamp": point["timestamp"],
                            "new_flag": FLAG_SNEAKY_DRIFT,
                            "initial_flag": point["AI_FLAG"]
                        })
                    if point["timestamp"] in analysis_logs_dict:
                        analysis_logs_dict[point["timestamp"]].update({"SNEAKY_DRIFT_FLAG": 1})

    return is_drift_detected, changed_points

def detect_flat_value(data_buffer: Deque[Dict], flat_threshold_minutes: int) -> Tuple[bool, List[Dict]]:
    """관측값이 정의된 기간 동안 동일하게 유지되는지 탐지합니다."""
    if len(data_buffer) < flat_threshold_minutes:
        return False, []

    buffer_df = pd.DataFrame(list(data_buffer))
    if 'OBS' not in buffer_df.columns:
        return False, []

    obs_series = buffer_df['OBS'].dropna()
    if len(obs_series) < flat_threshold_minutes:
        return False, []

    # 연속된 동일 값들을 그룹화
    flat_groups = obs_series.diff().ne(0).cumsum()
    if flat_groups.empty:
        return False, []

    last_group_id = flat_groups.iloc[-1]
    current_flat_group_indices = flat_groups[flat_groups == last_group_id].index

    if len(current_flat_group_indices) >= flat_threshold_minutes:
        flat_period_in_buffer_df = buffer_df.loc[current_flat_group_indices]
        prd_in_flat_period = flat_period_in_buffer_df["TIDE_PRE_VAL"].dropna()
        is_prd_also_flat = not prd_in_flat_period.empty and prd_in_flat_period.nunique() == 1

        if is_prd_also_flat:
            logging.info(
                f"동일값 구간 탐지되었으나, 예측조위(PRD) 또한 동일하여 정상(정조 시간)으로 판단. ({data_buffer[-1]['timestamp']})"
            )
            return False, []
        else:
            logging.warning(
                f"동일값 이상(FLAT VALUE) 탐지: 길이 {len(current_flat_group_indices)}분 >= 임계값 {flat_threshold_minutes}분."
            )
            changed_points = [
                {"timestamp": row["timestamp"], "new_flag": FLAG_FLAT_VALUE, "initial_flag": row["AI_FLAG"]}
                for _, row in flat_period_in_buffer_df.iterrows()
            ]
            return True, changed_points

    return False, []

def reevaluate_lstm_anomaly_with_trend(data_buffer: Deque[Dict], config: Dict) -> bool:
    """추세 일관성을 확인하여 LSTM 이상 탐지 결과를 재검토합니다."""
    window_size = config["AI_MODEL_WINDOW_SIZE"]
    anomaly_threshold_cm = config["effective_lstm_threshold_cm"]
    current_time = data_buffer[-1]["timestamp"]

    if len(data_buffer) < window_size:
        return False

    trend_window_data = list(data_buffer)[-window_size:]

    # 변동이 적거나 방향이 바뀌는 구간에서는 재검토를 생략
    prd_changes = [
        trend_window_data[i + 1]["TIDE_PRE_VAL"] - trend_window_data[i]["TIDE_PRE_VAL"]
        for i in range(len(trend_window_data) - 1)
        if pd.notna(trend_window_data[i + 1]["TIDE_PRE_VAL"]) and pd.notna(trend_window_data[i]["TIDE_PRE_VAL"])
    ]
    if not prd_changes: return False

    avg_abs_prd_change = np.mean(np.abs(prd_changes))
    if avg_abs_prd_change < config["LOW_FLUCTUATION_PRD_THRESHOLD"]:
        logging.info(f"[{current_time}] 저변동 구간. 추세 재검토 생략 (평균 변화량: {avg_abs_prd_change:.2f})")
        return False

    prd_signs = {np.sign(c) for c in prd_changes if abs(c) > 0.001}
    if len(prd_signs) > 1:
        logging.info(f"[{current_time}] 방향 전환 구간. 추세 재검토 생략 (부호: {prd_signs})")
        return False

    if any(item.get("SNEAKY_DRIFT_FLAG", 0) == 1 for item in trend_window_data):
        return False

    # 관측값(OBS)과 예측조위(PRD)의 추세가 유사한지 확인
    trend_is_similar = True
    for i in range(window_size - 1):
        obs_change = trend_window_data[i + 1]["OBS"] - trend_window_data[i]["OBS"]
        prd_change = trend_window_data[i + 1]["TIDE_PRE_VAL"] - trend_window_data[i]["TIDE_PRE_VAL"]

        if pd.isna(obs_change) or pd.isna(prd_change):
            trend_is_similar = False;
            break
        if np.sign(obs_change) != np.sign(prd_change) and (abs(obs_change) > 0.001 or abs(prd_change) > 0.001):
            trend_is_similar = False;
            break
        if abs(obs_change - prd_change) > anomaly_threshold_cm * 0.5:
            trend_is_similar = False;
            break

    if not trend_is_similar:
        logging.info(f"[{current_time}] 추세: OBS/PRD 추세 불일치. 이상 판정 유지.")
        return False

    # 추세가 유사할 경우, 오차(residual)의 안정성을 확인
    window_residuals = [
        item["OBS"] - item["TIDE_PRE_VAL"] for item in trend_window_data
        if pd.notna(item["OBS"]) and pd.notna(item["TIDE_PRE_VAL"])
    ]
    if not window_residuals: return False

    avg_window_residual = np.mean(window_residuals)
    var_window_residual = np.var(window_residuals)
    reference_residual = data_buffer[-1].get("last_residual_applied", 0.0)

    # --- [251020 신규 로직 추가] ---
    # 1. 급격한 잔차(Residual) 점프 임계값 설정
    #    - 기준 잔차의 2배 또는 이상 탐지 임계값 중 더 큰 값을 사용하여,
    #      기준 잔차가 0에 가까울 때도 최소한의 방어(anomaly_threshold_cm)를 하도록 설정
    residual_jump_threshold = max(abs(reference_residual) * 2.0, anomaly_threshold_cm)
    if residual_jump_threshold < config["SUDDEN_CHANGE_THRESHOLD_CM"]:
        residual_jump_threshold = config["SUDDEN_CHANGE_THRESHOLD_CM"]

    # 2. 잔차 점프(Residual Jump) 검사
    #    - 현재 윈도우의 평균 잔차가 기준 잔차로부터 'residual_jump_threshold' 이상 벗어났는지 확인
    residual_jump = abs(avg_window_residual - reference_residual)
    if residual_jump > residual_jump_threshold:
        logging.warning(
            f"[{current_time}] 추세: 추세는 유사하나 잔차(Residual)가 급변함. "
            f"번복(Reversal) 차단. (점프: {residual_jump:.2f} > 임계값: {residual_jump_threshold:.2f}, "
            f"AvgRes: {avg_window_residual:.2f}, RefRes: {reference_residual:.2f})"
        )
        return False  # <-- 번복(Reversal)을 차단하고 '이상' 판정 유지
    # --- [251020신규 로직 종료] ---

    is_consistent = abs(avg_window_residual - reference_residual) <= anomaly_threshold_cm * 0.75
    is_stable = var_window_residual < (anomaly_threshold_cm / 2.0) ** 2

    if is_consistent or is_stable:
        logging.info(f"[{current_time}] 추세: 유사한 추세 및 안정적인 오차 확인. LSTM 이상 판정을 '정상'으로 번복합니다.")
        return True

    return False

def update_last_residual(data_buffer: Deque[Dict], input_length: int, anomaly_threshold_cm: float,
                         current_stable_residual: float, residual_std_threshold: float,
                         last_anomaly_time: Optional[datetime], quarantine_minutes: int) -> Tuple[float, float]:
    """모델 입력 보간에 사용될 '마지막 정상 오차(last_residual_applied)' 값을 업데이트합니다."""
    current_data_point = data_buffer[-1]
    previous_last_residual = current_data_point.get("last_residual_applied", 0.0)

    if current_data_point["AI_FLAG"] == FLAG_NORMAL:
        is_in_quarantine = False
        if last_anomaly_time:
            time_since_anomaly = (current_data_point["timestamp"] - last_anomaly_time).total_seconds()
            if time_since_anomaly < quarantine_minutes * 60:
                is_in_quarantine = True

        if is_in_quarantine:
            logging.warning(
                f"학습 유예 기간입니다. 마지막 이상 발생 시각: {last_anomaly_time}. '정상 오차' 학습을 보류합니다."
            )
            return previous_last_residual, current_stable_residual

        valid_residuals = [
            item["OBS"] - item["TIDE_PRE_VAL"] for item in reversed(data_buffer)
            if item["AI_FLAG"] == FLAG_NORMAL and item.get("SNEAKY_DRIFT_FLAG", 0) == 0
            and pd.notna(item["OBS"]) and pd.notna(item["TIDE_PRE_VAL"])
        ]

        if len(valid_residuals) >= input_length:
            residuals_std = np.std(valid_residuals[:input_length])
            if residuals_std < residual_std_threshold:
                new_residual = np.mean(valid_residuals[:input_length])
                return new_residual, new_residual  # 적용 오차와 안정 오차 모두 업데이트
            else:
                logging.warning(
                    f"오차 불안정 감지 (표준편차: {residuals_std:.2f} > 임계값: {residual_std_threshold}). "
                    "'정상 오차' 업데이트를 보류합니다."
                )
                return previous_last_residual, current_stable_residual
    else:  # 현재 지점이 이상 상태일 경우
        DECAY_RATE = 0.5
        target_residual_for_decay = 0.0
        if abs(current_stable_residual) > anomaly_threshold_cm:
            target_residual_for_decay = current_stable_residual

        decayed_residual = previous_last_residual * DECAY_RATE + target_residual_for_decay * (1.0 - DECAY_RATE)
        return decayed_residual, current_stable_residual

    return previous_last_residual, current_stable_residual

def _decide_final_flag_and_source(details: Dict, config: Dict) -> Tuple[str, str]:
    """탐지된 이상 현상들의 우선순위에 따라 최종 AQC 플래그를 결정합니다."""
    if pd.isna(details['real_obs']):
        return FLAG_GAP, 'GAP'

    # 극단적인 값에 대한 최종 안전망
    obs_prd_residual = details.get('obs_prd_residual')
    final_check_threshold = config.get('FINAL_SAFETY_NET_THRESHOLD_CM', 100.0)
    if pd.notna(obs_prd_residual) and abs(obs_prd_residual) > final_check_threshold:
        return FLAG_FINAL_SAFETY, 'FINAL_SAFETY_NET'

    source_to_flag_map = {
        'SNEAKY_DRIFT': FLAG_SNEAKY_DRIFT,
        'SUDDEN_CHANGE': FLAG_SUDDEN_CHANGE,
        'FLAT_VALUE': FLAG_FLAT_VALUE,
        'LSTM_ERROR': FLAG_LSTM_ERROR
    }

    priority_order = [
        ('sneaky_drift_flag', 'SNEAKY_DRIFT'),
        ('sudden_change_flag', 'SUDDEN_CHANGE'),
        ('flat_value_flag', 'FLAT_VALUE'),
        ('lstm_flag', 'LSTM_ERROR')
    ]

    detected_sources = [source_name for flag_key, source_name in priority_order if details.get(flag_key) == 4]

    if detected_sources:
        highest_priority_source = detected_sources[0]
        final_flag = source_to_flag_map[highest_priority_source]
        decision_source = ",".join(detected_sources)
        return final_flag, decision_source
    else:
        return FLAG_NORMAL, 'NORMAL'

def process_data_point(sensor_id: Tuple[str, str], data_point: Dict, sensor_state: Dict, config: Dict) -> Dict:
    """주어진 센서에 대해 단일 데이터 포인트를 처리합니다."""
    station, sensor = sensor_id
    db_engine, debug_log_path = config["db_engine"], config["debug_log_path"]

    data_buffer = sensor_state["data_buffer"]
    stable_normal_residual = sensor_state["stable_normal_residual"]
    analysis_log = sensor_state["analysis_log"]
    model = sensor_state["model"]
    scaler = sensor_state["scaler"]
    last_anomaly_time = sensor_state.get("last_anomaly_time")
    is_db_null = data_point.get("IS_DB_NULL", False)

    # 이 센서에 대한 동적 설정 항목 업데이트
    sensor_config = config.copy()
    sensor_config["effective_lstm_threshold_cm"] = sensor_state["effective_lstm_threshold_cm"]
    sensor_config["anomaly_threshold_cm"] = sensor_state["effective_lstm_threshold_cm"]
    dev_file_threshold_cm = sensor_state["dev_file_threshold_cm"]

    residual_std_threshold = config["residual_std_thresholds_map"].get(sensor_id, config["DEFAULT_RESIDUAL_STD_THRESHOLD"])
    window_size = config["AI_MODEL_WINDOW_SIZE"]
    input_length = window_size - 1

    decision_details = {
        'timestamp': data_point["timestamp"], 'station': station, 'sensor': sensor,
        'real_obs': data_point["OBS"], 'predicted_obs': np.nan,
        'tide_pre_val': data_point["TIDE_PRE_VAL"], 'diff': np.nan,
        'threshold': sensor_config["effective_lstm_threshold_cm"],
        'initial_flag': data_point.get("AI_FLAG", '1'),
        'mqc_flag': data_point.get("MQC_FLAG", 'G'),
        'sudden_change_flag': 1, 'lstm_flag': 1,
        'sneaky_drift_flag': 1, 'flat_value_flag': 1,
        'final_flag': FLAG_NORMAL, 'decision_source': 'NONE'
    }

    if data_buffer and (data_point["timestamp"] - data_buffer[-1]["timestamp"]) > timedelta(minutes=10):
        logging.warning(f"장시간 데이터 결측 감지. {station}/{sensor}의 데이터 버퍼를 초기화합니다.")
        data_buffer.clear()

    # 급격한 변화 탐지
    if data_buffer and pd.notna(data_point["OBS"]) and pd.notna(data_buffer[-1]["OBS"]):
        if abs(data_point["OBS"] - data_buffer[-1]["OBS"]) > config["SUDDEN_CHANGE_THRESHOLD_CM"]:
            decision_details['sudden_change_flag'] = 4

    data_point["AI_FLAG"] = decision_details['initial_flag']
    data_point["last_residual_applied"] = data_buffer[-1].get("last_residual_applied", 0.0) if data_buffer else 0.0
    data_buffer.append(data_point)

    # 현재 타임스탬프에 대한 로그 항목 초기화
    current_time_point = data_point["timestamp"]
    obs_prd_residual = data_point["OBS"] - data_point["TIDE_PRE_VAL"] if pd.notna(data_point["OBS"]) and pd.notna(
        data_point["TIDE_PRE_VAL"]) else np.nan
    log_entry = {
        "timestamp": current_time_point, "real": data_point["OBS"], "predicted": np.nan, "diff": np.nan,
        "threshold": sensor_config["effective_lstm_threshold_cm"], "AI_FLAG": data_point["AI_FLAG"],
        "interpolated_count": 0, "prd_obs_residual": obs_prd_residual,
        "last_residual_applied": data_point["last_residual_applied"], "SNEAKY_DRIFT_FLAG": 0
    }
    analysis_log[current_time_point] = log_entry
    decision_details['obs_prd_residual'] = obs_prd_residual

    # --- 이상 탐지 시작 (버퍼가 충분히 채워져야 함) ---
    if len(data_buffer) < window_size:
        if pd.isna(data_point["OBS"]):
            final_flag, decision_source = _decide_final_flag_and_source(decision_details, sensor_config)
            decision_details.update({'final_flag': final_flag, 'decision_source': decision_source})
            data_buffer[-1]["AI_FLAG"] = final_flag
            analysis_log[current_time_point]["AI_FLAG"] = final_flag

            # [DB 업데이트 주석 처리 1] - 버퍼 부족 시 결측치 업데이트
            # if (str(decision_details['initial_flag']) != str(final_flag)) or is_db_null:
            #    update_n1_aqc_flag(db_engine, current_time_point, station, sensor, AQC_AI_FLAG_POSITION,
            #                       str(final_flag))

            log_decision_process(decision_details, debug_log_path)

        sensor_state.update({
            "data_buffer": data_buffer, "stable_normal_residual": stable_normal_residual,
            "analysis_log": analysis_log, "last_anomaly_time": last_anomaly_time
        })
        return sensor_state
    if pd.notna(data_point["OBS"]):
        # LSTM 예측
        X_input, interp_count = prepare_model_input_data(data_buffer, input_length,
                                                         data_buffer[-1]["last_residual_applied"], scaler)
        y_pred = predict_and_inverse_transform(model, scaler, X_input)
        diff, lstm_flag = detect_anomaly(data_point["OBS"], y_pred, sensor_config["effective_lstm_threshold_cm"])

        if lstm_flag == 4 and reevaluate_lstm_anomaly_with_trend(data_buffer, sensor_config):
            lstm_flag = 1  # 정상으로 번복

        decision_details.update({'predicted_obs': y_pred, 'diff': diff, 'lstm_flag': lstm_flag})
        analysis_log[current_time_point].update({"predicted": y_pred, "interpolated_count": interp_count, "diff": diff})

        # Sneaky Drift 탐지
        is_sneaky, sneaky_changes = detect_sneaky_drift(
            data_buffer, analysis_log, config["SNEAKY_DRIFT_CHECK_INTERVAL_MINUTES"], config["SNEAKY_DRIFT_WINDOW_MINUTES"],
            station, sensor, config["sneaky_multipliers_map"], config["DEFAULT_SNEAKY_DRIFT_MULTIPLIER"],
            dev_file_threshold_cm
        )
        if is_sneaky: decision_details['sneaky_drift_flag'] = 4

    # 동일값 탐지
    is_flat, flat_changes = detect_flat_value(data_buffer, config["FLAT_VALUE_THRESHOLD_MINUTES"])
    if is_flat: decision_details['flat_value_flag'] = 4

    # 최종 결정
    final_flag, decision_source = _decide_final_flag_and_source(decision_details, sensor_config)
    decision_details.update({'final_flag': final_flag, 'decision_source': decision_source})

    # 최종 결정에 따라 상태 업데이트
    data_buffer[-1]["AI_FLAG"] = final_flag
    analysis_log[current_time_point]["AI_FLAG"] = final_flag
    if final_flag != FLAG_NORMAL:
        last_anomaly_time = current_time_point

    if pd.notna(data_point["OBS"]):
        last_residual, stable_normal_residual = update_last_residual(
            data_buffer, input_length, sensor_config["effective_lstm_threshold_cm"],
            stable_normal_residual, residual_std_threshold,
            last_anomaly_time, config["LEARNING_QUARANTINE_MINUTES"]
        )
        data_buffer[-1]["last_residual_applied"] = last_residual
        analysis_log[current_time_point]["last_residual_applied"] = last_residual

    # --- 결과 저장 ---
    # [DB 업데이트 주석 처리 2] - 현재 시점 플래그 업데이트
    # if (str(decision_details['initial_flag']) != str(final_flag)) or is_db_null:
    #    update_n1_aqc_flag(db_engine, current_time_point, station, sensor, AQC_AI_FLAG_POSITION, str(final_flag))

    if pd.notna(data_point["OBS"]):
        all_past_changes = sneaky_changes + flat_changes
        for change in all_past_changes:
            for point in data_buffer:
                if point["timestamp"] == change["timestamp"]:
                    point["AI_FLAG"] = change["new_flag"]
                    break

            # [DB 업데이트 주석처리 3] -  과거 데이터(sneaky drift / flat value) 업데이트
            # if str(change["initial_flag"]) != str(change["new_flag"]):
            #    update_n1_aqc_flag(db_engine, change["timestamp"], station, sensor, AQC_AI_FLAG_POSITION,
            #                       str(change["new_flag"]))

    log_decision_process(decision_details, debug_log_path)

    # 버퍼 크기 관리
    buffer_max_len = max(config["SNEAKY_DRIFT_WINDOW_MINUTES"] + 1, config["FLAT_VALUE_THRESHOLD_MINUTES"],
                         input_length + 1) + 10
    while len(data_buffer) > buffer_max_len:
        data_buffer.popleft()

    sensor_state.update({
        "data_buffer": data_buffer, "stable_normal_residual": stable_normal_residual,
        "analysis_log": analysis_log, "last_anomaly_time": last_anomaly_time
    })
    return sensor_state

def create_synthetic_gap_point(timestamp: datetime, prd_value: float) -> Dict:
    """결측 데이터 포인트를 나타내는 딕셔너리를 생성합니다."""
    return {
        "timestamp": timestamp, "OBS": np.nan, "TIDE_PRE_VAL": prd_value,
        "SNEAKY_DRIFT_FLAG": 0
    }

def log_decision_process(decision_details: Dict, log_path: Any) -> None:
    """Send a detached decision record to a caller-supplied memory sink."""
    if callable(log_path):
        log_path(dict(decision_details))
