"""Explicit operational mapping, shared by MDC sync and preserved-file ingestion.

This policy adopts operational units and KST; it does not establish a physical
sensor, historical source-unit provenance, a QC decision or training approval.
Unknown codes never receive an automatic operational mapping.
"""
import hashlib
import json

VERSION = 'OPS-MDC-MAP-2.0'
ITEMS = {}


def _add(codes, variable, unit, sensor_type, quantity_kind='SCALAR'):
    for code in codes:
        ITEMS[code] = dict(variable=variable or code, unit=unit,
                           sensor_type=sensor_type, quantity_kind=quantity_kind)


_add(['WATER_TEMP', 'WATER_TEMP2', 'TEMP'], 'WATER_TEMP', 'C', 'WATER_QUALITY')
_add(['SALINITY', 'SALINITY2'], 'SALINITY', 'PSU', 'WATER_QUALITY')
_add(['ELECT_CONDUCT', 'ELECT_CONDUCT2'], 'ELECT_CONDUCT', 'MS/CM', 'WATER_QUALITY')
_add(['AIR_TEMP', 'AIR_TEMP2'], 'AIR_TEMP', 'C', 'METEOROLOGY')
_add(['AIR_PRES', 'AIR_PRES2', 'AIR_PRESS'], 'AIR_PRES', 'HPA', 'METEOROLOGY')
_add(['WIND_SPEED'], 'WIND_SPEED', 'M/S', 'METEOROLOGY')
_add(['WIND_GUST', 'MAX_WIND_SPEED'], 'WIND_GUST', 'M/S', 'METEOROLOGY')
_add(['WIND_DIRECT', 'WIND_DIRECTION'], 'WIND_DIRECT', 'DEG', 'METEOROLOGY', 'CIRCULAR_DEGREES')
_add(['HUMIDITY'], 'HUMIDITY', '%', 'METEOROLOGY')
_add(['TIDE_LEVEL', 'TIDE_LEVEL_MIROS', 'TIDE_LEVEL_VEGA', 'TIDE_LEVEL_VEGA_2',
      'TIDE_LEVEL_LASER', 'TIDE_LEVEL_LASER_1', 'TIDE_LEVEL_WLS', 'TIDE_LEVEL_OTT',
      'TIDE_LEVEL_K', 'TIDE_LEVEL_FLOAT'], 'TIDE', 'cm', 'TIDE_GAUGE')
for prefix in ['', 'MOSE_HF_', 'MOSE_LF_', 'HIPPY_']:
    _add([prefix + 'MAX_WAVE_HEIGHT', prefix + 'SIGNIFI_WAVE_HEIGHT'], None, 'm', 'WAVE_SENSOR')
    _add([prefix + 'MAX_WAVE_PERIOD', prefix + 'SIGNIFI_WAVE_PERIOD'], None, 's', 'WAVE_SENSOR')
    _add([prefix + 'WAVE_DIRECT'], None, 'DEG', 'WAVE_SENSOR', 'CIRCULAR_DEGREES')
_add(['WAVE_HEIGHT', 'AVG_WAVE_HEIGHT'], None, 'm', 'WAVE_SENSOR')
_add(['WAVE_PERIOD'], 'WAVE_PERIOD', 's', 'WAVE_SENSOR')


def mapping(code):
    return ITEMS.get(str(code or '').strip().upper())


def map_item(code):
    canonical = str(code or 'UNKNOWN').strip().upper()
    spec = mapping(canonical)
    return (spec['variable'], spec['unit'], spec['sensor_type']) if spec else (canonical, 'UNKNOWN', 'MDC')


def policy():
    return dict(schema_version='source-operational-mapping-policy-1', version=VERSION,
                sources=['GD_OBS_BU', 'GD_OBS_VBU', 'GR_OBS_ST'], timezone='Asia/Seoul',
                identifier_transform='STRIP_UPPER', scale='1', offset='0',
                approval_scope='OPERATIONAL_STANDARDIZATION_ONLY',
                sensor_identity='LOGICAL_SOURCE_CHANNEL_NOT_PHYSICAL_SENSOR',
                source_unit_basis='SYSTEM_ADOPTED_MDC_MAPPING',
                qc_policy='PRESERVE_LITERAL_NO_FINAL_QC_APPROVAL',
                training_eligible=False, historical_availability_asserted=False,
                deleted_original_policy='VERIFIED_PRESERVED_TRANSFORM_ONLY', items=ITEMS)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()
