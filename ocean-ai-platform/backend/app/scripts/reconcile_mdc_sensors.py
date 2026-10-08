# 파일 역할: 운영 MDC의 실제 센서 기준정보를 읽어 버전별 카탈로그 및 미해결 매핑 감사표를 생성합니다.
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Oracle 설정을 읽기 전에 명시한 backend/.env를 로드하며 비밀 값은 기록하지 않는다.
load_dotenv(Path(__file__).resolve().parents[2] / '.env')
from sqlalchemy import func, text
from app.core.database import SessionLocal, engine
from app.models.domain import ObservationRaw, ObservationStandard, StationMetadata, SensorMetadata
from app.models.evidence import MDCSensorCatalog
from app.services.mdc_sensor_catalog import sync_catalog, catalog_records, checksum
from app.scripts.sync_mdc_db import init_oracle, fetch_oracle_data


def read_source():
    # 조회 컬럼은 실제 운영 스키마에서 확인했으며 담당자 개인정보는 수집하지 않는다.
    init_oracle()
    return {
        'equipment': fetch_oracle_data('SELECT OBS_POST_ID, TE_CODE, TE_TYPE, TE_START, TE_END, TE_NAME, TE_FACTORY, TE_NO, USE_YN FROM WEB_EQUIP_INFO'),
        'items': fetch_oracle_data('SELECT OBS_POST_ID, TE_CODE, OBS_ITEM_CODE, OBS_ITEM_NAME, UNIT, USE_START_DATE, USE_END_DATE, USE_YN, INSTALL_DATE, S_MODEL_NM, S_SERIAL_NO, MAKER, SENSOR_STATUS FROM WEB_OBS_ITEM_INFO'),
        'stations': fetch_oracle_data('SELECT OBS_POST_ID, OBS_POST_NAME, DATA_TYPE, OBS_LAT, OBS_LON, TOTAL_STATUS FROM WEB_STATION')}


def reconcile(source, apply=False):
    if apply:
        # 이미 등록된 모델 전체를 수정하지 않고 추가 테이블만 멱등적으로 생성한다.
        with engine.begin() as conn:
            if conn.dialect.name == 'postgresql':
                conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('mdc-sensor-catalog-v1'))"))
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            MDCSensorCatalog.__table__.create(conn, checkfirst=True)
    # 날짜 객체는 원본 JSON 문자열로 보존하여 재실행 시 동일한 버전이 생성되게 한다.
    source = json.loads(json.dumps(source, default=str, ensure_ascii=False))
    with SessionLocal() as db:
        station_ids = sorted(r[0] for r in db.query(ObservationStandard.station_id).distinct())
        records = catalog_records(source, set(station_ids))
        result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'applied': apply,
                  'source_counts': {key: len(value) for key, value in source.items()},
                  'station_ids': station_ids, 'catalog_version': checksum([(r['sensor_id'], r['source_hash']) for r in records]),
                  'source_channel_count': len(records), 'issue_counts': dict(Counter(issue for r in records for issue in r['issues']))}
        if apply:
            if db.bind.dialect.name == 'postgresql':
                db.execute(text("SELECT pg_advisory_xact_lock(hashtext('mdc-sensor-catalog-sync-v1'))"))
            synced = sync_catalog(db, source, station_ids)
            result['inserted_catalog_rows'] = synced['inserted_catalog_rows']
        result['legacy_observation_scopes'] = []
        groups = db.query(ObservationRaw.station_id, ObservationRaw.sensor_id, ObservationRaw.variable_code,
            ObservationRaw.source_item_code, ObservationRaw.source_system, func.count()).group_by(
            ObservationRaw.station_id, ObservationRaw.sensor_id, ObservationRaw.variable_code,
            ObservationRaw.source_item_code, ObservationRaw.source_system).all()
        for station, sensor, variable, item, system, count in groups:
            reasons = []
            if 'SIMULATED' in (system or '').upper() or 'DEMO' in (system or '').upper(): reasons.append('SIMULATED_SOURCE')
            if not item: reasons.append('SOURCE_ITEM_CODE_MISSING')
            matches = [r for r in records if r['station_id'] == station and r['source_item_code'] == item]
            if not matches: reasons.append('NO_EXACT_CATALOG_ITEM')
            elif len(matches) > 1: reasons.append('AMBIGUOUS_EQUIPMENT')
            result['legacy_observation_scopes'].append({'station_id': station, 'sensor_id': sensor,
                'variable_code': variable, 'source_item_code': item, 'source_system': system, 'count': count,
                'status': 'UNRESOLVED', 'reasons': reasons or ['HISTORICAL_IDENTITY_REVIEW_REQUIRED']})
        result['stations'] = [r for r in source['stations'] if r['obs_post_id'] in station_ids]
        result['records'] = records
        if apply: db.commit()
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-json', type=Path, help='재현 검증용 저장된 원본; 생략 시 실제 MDC 조회')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.source_json.read_text(encoding='utf-8')) if args.source_json else read_source()
    result = reconcile(source, args.apply)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in {'records', 'stations', 'legacy_observation_scopes'}}, ensure_ascii=False))
