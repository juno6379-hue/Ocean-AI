# 파일 역할: 초기 학습 특성 정의를 등록합니다.
"""기본 Feature 정의를 최초 1회 등록한다."""
from app.core.database import SessionLocal
from app.models.domain import FeatureDefinition

FEATURES = [
    ("moving_mean", "Temporal Feature", "이동 평균", "rolling mean(value_standard)", ["observation_standard.value_standard"], "24h"),
    ("moving_std", "Temporal Feature", "이동 표준편차", "rolling std(value_standard)", ["observation_standard.value_standard"], "24h"),
    ("rate_of_change", "Temporal Feature", "시간당 변화율", "(x[t]-x[t-1]) / delta_seconds", ["observation_standard.value_standard", "timestamp_utc"], "1h"),
    ("persistence_duration", "Rule QC Feature", "동일값 지속시간", "consecutive identical standardized values", ["observation_standard.value_standard"], "24h"),
    ("neighbor_difference", "Spatial Feature", "인접 관측소 차이", "x[station]-mean(x[neighbor stations])", ["observation_standard.value_standard", "station_id"], "1h"),
    ("tide_prediction_residual", "Event Feature", "조위 예측 잔차", "observed_tide-predicted_tide", ["observation_standard.value_standard", "prediction.value"], "1h"),
    ("qc_rule_fail_count", "Rule QC Feature", "QC 규칙 실패 횟수", "count(result_flag in failed flags)", ["qc_rule_result.result_flag"], "24h"),
    ("days_since_calibration", "Metadata Feature", "교정 후 경과일", "timestamp - sensor.calibration_date", ["sensor_metadata.calibration_date", "timestamp_utc"], None),
    ("recent_maintenance_flag", "Operation Feature", "최근 유지보수 여부", "exists maintenance event in window", ["operation_log.event_type", "event_time"], "30d"),
]


def seed_features():
    db = SessionLocal()
    try:
        added = 0
        for feature_id, group, description, logic, source_fields, window in FEATURES:
            exists = db.query(FeatureDefinition).filter(
                FeatureDefinition.feature_id == feature_id,
                FeatureDefinition.feature_version == "1.0",
            ).first()
            if exists:
                continue
            db.add(FeatureDefinition(
                feature_id=feature_id,
                feature_name=feature_id,
                feature_group=group,
                description=description,
                calculation_logic=logic,
                source_fields=source_fields,
                window_size=window,
                feature_version="1.0",
            ))
            added += 1
        db.commit()
        print(f"Feature definitions added: {added}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_features()
