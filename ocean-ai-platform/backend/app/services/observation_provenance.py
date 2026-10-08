# 파일 역할: 원시자료 출처를 확인하여 시뮬레이션·데모를 운영 사건과 학습 계보에서 배제합니다.
from app.models.domain import ObservationRaw


def raw_for_standard(db, observation):
    # 표준화 ID와 원시 PK가 다르므로 동일 자연키로 원본을 찾는다.
    return db.query(ObservationRaw).filter_by(**{key: getattr(observation, key) for key in
        ('station_id', 'sensor_id', 'variable_code', 'timestamp_utc')}).first()


def source_issue(raw):
    if raw is None:
        return 'raw_observation_missing'
    source = (raw.source_system or '').strip().upper()
    if not source:
        return 'source_system_missing'
    if 'SIMULATED' in source or 'DEMO' in source:
        return 'simulated_source_not_allowed'
    return None
