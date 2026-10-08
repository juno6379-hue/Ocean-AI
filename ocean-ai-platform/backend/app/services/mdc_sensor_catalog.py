# 파일 역할: 실제 MDC 장비·항목 기준정보를 원본 코드별로 보존하고 불명확한 매핑을 표시합니다.
import hashlib
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
from app.models.domain import StationMetadata, SensorMetadata
from app.models.evidence import MDCSensorCatalog


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    default=str).encode('utf-8')).hexdigest()


def normalized_unit(value):
    unit = str(value or '').strip().lower()
    return {'m': 'm', 'cm': 'cm', 'mm': 'mm', 's': 's', 'sec': 's', '초': 's',
            'm/s': 'm/s', '℃': 'degC', '°c': 'degC', 'c': 'degC', 'psu': 'PSU',
            'hpa': 'hPa', '%': '%', 'deg': 'deg', 'degree': 'deg', '도': 'deg'}.get(unit)


def item_semantics(code, unit):
    """주기·방향을 파고로 합치지 않으며 해수위 기준면이나 누락 단위를 추정하지 않는다."""
    code = str(code).strip().upper()
    base = re.sub(r'\d+$', '', code)
    aliases = {'TEMP': 'WATER_TEMP', 'TIDE_LEVEL': 'TIDE', 'TIDE_LEVEL_VEGA': 'TIDE',
               'TIDE_LEVEL_K': 'TIDE', 'TIDE_LEVEL_FLOAT': 'TIDE'}
    variable = aliases.get(base, base)
    if base.startswith('TIDE_LEVEL_'):
        variable = 'TIDE'
    expected = None
    if 'WAVE' in base:
        # 통계 종류(MAX/MEAN 등)는 유지하고 차원만 검사한다.
        expected = {'s'} if 'PERIOD' in base else {'deg'} if ('DIRECT' in base or 'DIR' in base) else {'m', 'cm'} if 'HEIGHT' in base else None
    else:
        expected = {'TIDE': {'m', 'cm', 'mm'}, 'SEA_LEVEL': {'m', 'cm', 'mm'},
                    'WATER_TEMP': {'degC'}, 'AIR_TEMP': {'degC'}, 'SALINITY': {'PSU'},
                    'WIND_SPEED': {'m/s'}, 'WIND_DIRECT': {'deg'}, 'AIR_PRES': {'hPa'},
                    'HUMIDITY': {'%'}}.get(variable)
    normalized = normalized_unit(unit)
    issues = []
    if not str(unit or '').strip(): issues.append('SOURCE_UNIT_MISSING')
    elif normalized is None: issues.append('SOURCE_UNIT_UNSUPPORTED')
    elif expected and normalized not in expected: issues.append('SOURCE_UNIT_CONFLICT')
    if expected is None: issues.append('VARIABLE_SEMANTICS_REVIEW_REQUIRED')
    if variable == 'SEA_LEVEL': issues.append('VERTICAL_DATUM_UNVERIFIED')
    return variable, normalized, issues


def source_datetime(value):
    # MDC 메타데이터 시각은 KST로 해석한다. 임의의 시작일을 만들지 않는다.
    if not value: return None
    value = datetime.fromisoformat(str(value))
    if value.tzinfo is not None:
        from datetime import timezone
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value - timedelta(hours=9)


def catalog_records(source, station_ids):
    equipment = defaultdict(list)
    for row in source['equipment']:
        equipment[(str(row['obs_post_id']).strip(), str(row['te_code']).strip())].append(row)
    grouped = defaultdict(list)
    for row in source['items']:
        if str(row['obs_post_id']).strip() in station_ids:
            key = tuple(str(row.get(k) or '').strip() for k in ('obs_post_id', 'te_code', 'obs_item_code'))
            grouped[key].append(row)
    records = []
    for (station, te_code, item), rows in sorted(grouped.items()):
        rows = sorted(rows, key=checksum)
        equips = sorted(equipment[(station, te_code)], key=checksum)
        payload = {'items': rows, 'equipment': equips}
        row = rows[0]
        variable, unit, issues = item_semantics(item, row.get('unit'))
        if len(rows) != 1: issues.append('DUPLICATE_SOURCE_KEY')
        if len(equips) != 1: issues.append('EQUIPMENT_MISSING_OR_AMBIGUOUS')
        if not station or not te_code or not item: issues.append('SOURCE_KEY_INCOMPLETE')
        start, end = source_datetime(row.get('use_start_date')), source_datetime(row.get('use_end_date'))
        if start is None: issues.append('HISTORICAL_VALIDITY_UNKNOWN')
        if start and end and end <= start: issues.append('INVALID_VALIDITY_INTERVAL')
        # 사용여부 코드의 의미는 소스 그대로 보존하고 운영중이라고 단정하지 않는다.
        issues.append('PHYSICAL_IDENTITY_REVIEW_REQUIRED')
        records.append(dict(sensor_id='MDC-' + checksum([station, te_code, item])[:40],
            station_id=station, te_code=te_code, source_item_code=item, variable_code=variable,
            source_unit=row.get('unit'), normalized_unit=unit, valid_start=start, valid_end=end,
            issues=sorted(set(issues)), source_payload=payload, source_hash=checksum(payload)))
    return records


def sync_catalog(db, source, station_ids):
    records = catalog_records(source, set(station_ids))
    version = checksum([(r['sensor_id'], r['source_hash']) for r in records])
    # 전체 목록을 검증한 뒤 기록하여 일부 성공만 커밋되는 일을 막는다.
    missing = sorted({r['station_id'] for r in records if not db.query(StationMetadata).filter_by(station_id=r['station_id']).first()})
    if missing: raise ValueError('Shared station metadata missing: ' + ','.join(missing))
    inserted = 0
    for record in records:
        sensor = db.query(SensorMetadata).filter_by(sensor_id=record['sensor_id']).first()
        if sensor and (sensor.station_id != record['station_id'] or sensor.variable_code != record['variable_code']):
            raise ValueError('Existing canonical sensor scope conflict: ' + record['sensor_id'])
        if sensor is None:
            db.add(SensorMetadata(sensor_id=record['sensor_id'], station_id=record['station_id'],
                variable_code=record['variable_code'], sensor_type='MDC_SOURCE_CHANNEL', status='REVIEW_REQUIRED'))
            db.flush()
        saved = db.get(MDCSensorCatalog, (record['sensor_id'], version))
        if saved is None:
            db.add(MDCSensorCatalog(catalog_version=version, **record)); inserted += 1
        elif saved.source_hash != record['source_hash']:
            raise ValueError('Immutable catalog content conflict')
    db.flush()
    return {'catalog_version': version, 'source_channel_count': len(records), 'inserted_catalog_rows': inserted,
            'review_required': len(records), 'records': records}


def resolve_catalog(db, version, station_id, item_code, timestamp):
    """관측 테이블에 TE_CODE가 없을 때 후보를 제시하되 시간·장비를 자동 확정하지 않는다."""
    rows = db.query(MDCSensorCatalog).filter_by(catalog_version=version, station_id=station_id,
                                              source_item_code=item_code).all()
    candidates = [row for row in rows if (row.valid_start is None or timestamp >= row.valid_start)
                  and (row.valid_end is None or timestamp < row.valid_end)]
    return {'status': 'NOT_FOUND' if not candidates else 'AMBIGUOUS' if len(candidates) > 1 else 'REVIEW_REQUIRED',
            'candidates': [{'sensor_id': r.sensor_id, 'te_code': r.te_code, 'issues': r.issues} for r in candidates]}
