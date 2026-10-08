# 파일 역할: MDC 메타데이터·관측자료를 조회해 원시 및 표준화 관측으로 동기화합니다.
import sys
import os
import datetime
import traceback
import hashlib
from typing import List, Dict, Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import oracledb
except ImportError:
    print("oracledb 패키지가 설치되어 있지 않습니다. pip install oracledb 로 설치해주세요.")
    oracledb = None

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.core.database import SessionLocal
from app.core.config import settings
from zoneinfo import ZoneInfo
from app.models.domain import StationMetadata, SensorMetadata, ObservationRaw, ObservationStandard, MDCItemMapping

# ==========================================
# 사용자 설정 영역 (Oracle Instant Client 경로)
# ==========================================
ORACLE_CLIENT_LIB_DIR = settings.ORACLE_CLIENT_LIB_DIR

# ==========================================
# MDC DB (ocean_web) 접속 정보
# ==========================================
MDC_DSN = settings.MDC_DSN
MDC_USER = settings.MDC_USER
MDC_PWD = settings.MDC_PWD

def init_oracle():
    """Oracle Thick Mode 활성화"""
    if oracledb is None:
        raise RuntimeError("Install oracledb before running MDC sync")
    if not all((MDC_DSN, MDC_USER, MDC_PWD)):
        raise RuntimeError("MDC connection environment variables are required")
    if not ORACLE_CLIENT_LIB_DIR:
        return
    oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB_DIR)


def fetch_oracle_data(query: str, params: dict = None) -> List[Dict[str, Any]]:
    """Run a bounded, read-only source query; connection failures are not empty data."""
    with oracledb.connect(user=MDC_USER, password=MDC_PWD, dsn=MDC_DSN, tcp_connect_timeout=10) as connection:
        connection.call_timeout = 30000
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(query, params or {})
            columns = [col[0].lower() for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_with_fallback(primary: str, fallback: str, params: dict = None) -> List[Dict[str, Any]]:
    """Only missing optional columns permit a fallback; never hide a DB outage."""
    try:
        return fetch_oracle_data(primary, params)
    except oracledb.DatabaseError as exc:
        if getattr(exc.args[0], "code", None) != 904:
            raise
        return fetch_oracle_data(fallback, params)


def clean_station_name(name: str) -> str:
    import re
    # Remove _과거성과, _기점, _한강홍수통제소, etc.
    name = re.sub(r'_(과거성과|기점|한강홍수통제소).*', '', name)
    # Remove 10년(...) prefix like 10년(마라도)_기점
    name = re.sub(r'^\d+년\([^\)]+\)_?', '', name)
    # Remove any trailing parenthetical notes if they look like test data
    return name.strip()

def map_status_code(code) -> str:
    # 1: ACTIVE, 2: MAINTENANCE, 0 or other: ERROR
    try:
        code_int = int(code)
    except:
        code_int = -1
    
    if code_int == 1:
        return 'ACTIVE'
    elif code_int == 2:
        return 'MAINTENANCE'
    else:
        return 'ERROR'


# MDC WEB_STATION.DATA_TYPE의 실제 운영 코드와 화면 표시명 매핑
MDC_NETWORK_TYPES = {
    'DT': '조위관측소',
    'SO': '조위관측소',
    'TW': '해양관측부이',
    'KG': '해양관측부이',
    'IE': '해양과학기지',
    'RT': '해양관측소',
    'HF': 'HF-Radar',
}
MDC_RT_STATION_OVERRIDES = {
    'DT_0046', 'DT_0047', 'DT_0048', 'DT_0039', 'DT_0041', 'DT_0042'
}


def map_sea_area(latitude: Any, longitude: Any) -> str:
    """MDC 좌표를 UI용 해역으로 변환한다.

    WEB_STATION.DO_NM은 해역이 아니라 소속 도/시(행정구역)이므로
    관측소 위치 표시에 사용하지 않는다. 경계가 겹치는 연안은 경도와
    위도를 함께 사용해 동해·서해·남해·제주해역으로 일관되게 분류한다.
    """
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return "미상"
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return "미상"
    if lat <= 34.0 and lon >= 125.0:
        return "제주해역"
    if lon >= 128.0:
        return "동해"
    if lon <= 126.5:
        return "서해"
    return "남해"


def map_network_type(data_type: Any, station_id: str) -> Optional[str]:
    """MDC 관측망 코드를 플랫폼 표시명으로 변환한다."""
    code = str(data_type or '').strip().upper()
    station_id = str(station_id or '').strip().upper()
    if station_id in MDC_RT_STATION_OVERRIDES:
        return '해양관측소'
    return MDC_NETWORK_TYPES.get(code)

def sync_metadata(db: Session):
    """WEB_STATION 테이블 연동 (관측소 메타데이터)"""
    print("--- WEB_STATION (관측소 메타데이터) 동기화 시작 ---")
    query = """
        SELECT OBS_POST_ID, DATA_TYPE, OBS_POST_NAME, OBS_LAT, OBS_LON, DO_NM, ADDRESS, TOTAL_STATUS 
        FROM WEB_STATION
    """
    rows = fetch_oracle_data(query)
    if not rows:
        print("메타데이터가 없습니다.")
        return

    new_count, update_count = 0, 0
    for row in rows:
        st_id = str(row.get('obs_post_id', '')).strip().upper()
        data_type = row.get('data_type', '')
        
        # MDC 운영 코드가 아닌 외부망/시험망은 적재하지 않는다.
        mapped_network_type = map_network_type(data_type, st_id)
        if mapped_network_type is None:
            continue
            
        if not st_id: continue
        
        st_name_raw = row.get('obs_post_name', 'Unknown')
        # 2. Clean station name
        st_name = clean_station_name(st_name_raw)
        
        if not st_name:
            continue
            
        # 3. Standardize Network Type
        lat = row.get('obs_lat', 0.0)
        lon = row.get('obs_lon', 0.0)
        # DO_NM은 MDC의 행정구역 값이다. 해역 필드에는 좌표 기반 분류를 저장한다.
        sea_area = map_sea_area(lat, lon)
        
        # 4. Standardize Status
        status_code = row.get('total_status', 0)
        status_str = map_status_code(status_code)
        
        existing = db.query(StationMetadata).filter(StationMetadata.station_id == st_id).first()
        if existing:
            existing.station_name = st_name
            existing.network_type = mapped_network_type
            existing.latitude = lat
            existing.longitude = lon
            existing.sea_area = sea_area
            existing.status = status_str
            update_count += 1
        else:
            new_st = StationMetadata(
                station_id=st_id,
                station_name=st_name,
                network_type=mapped_network_type,
                latitude=lat,
                longitude=lon,
                sea_area=sea_area,
                status=status_str
            )
            db.add(new_st)
            new_count += 1
            
    db.commit()
    print(f"메타데이터 동기화 완료: 신규 {new_count}건, 업데이트 {update_count}건.")

def get_simulated_time_range(delta_seconds: int = 10):
    """Compatibility name: return the actual Korean local observation window."""
    now = datetime.datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    return now - datetime.timedelta(seconds=delta_seconds), now


def shift_time_to_present(obs_time: datetime.datetime) -> datetime.datetime:
    """Preserve the source observation timestamp; never rewrite its year."""
    if obs_time is None:
        raise ValueError("Source observation timestamp is required")
    return obs_time


def insert_observations_idempotent(db: Session, observations: List[ObservationRaw]) -> int:
    """관측 자연키 중복을 제거하며 PostgreSQL에 적재한다."""
    if not observations:
        return 0

    values = []
    for observation in observations:
        values.append({
            "station_id": observation.station_id,
            "sensor_id": observation.sensor_id,
            "timestamp_kst": observation.timestamp_kst,
            "timestamp_utc": observation.timestamp_utc,
            "variable_code": observation.variable_code,
            "value_raw": observation.value_raw,
            "value_unit": observation.value_unit,
            "source_system": observation.source_system,
            "value_status": observation.value_status,
            "qc_flag": observation.qc_flag, "mqc_flag": observation.mqc_flag,
            "water_step": observation.water_step, "from_depth": observation.from_depth, "to_depth": observation.to_depth,
            "receive_time": observation.receive_time, "source_item_code": observation.source_item_code,
        })

    statement = pg_insert(ObservationRaw).values(values).on_conflict_do_nothing(index_elements=["station_id","sensor_id","variable_code","timestamp_utc"])
    result = db.execute(statement)
    # One sensor row per source item/depth, even when a batch has many observations.
    sensor_specs = {o.sensor_id: o for o in observations}
    existing_sensors = {sensor.sensor_id: sensor for sensor in db.query(SensorMetadata).filter(SensorMetadata.sensor_id.in_(sensor_specs)).all()}
    for sensor_id, observation in sensor_specs.items():
        variable, _, sensor_type = map_mdc_item(observation.source_item_code or observation.variable_code)
        sensor = existing_sensors.get(sensor_id)
        if sensor is None:
            sensor = SensorMetadata(sensor_id=sensor_id, status="ACTIVE")
            db.add(sensor)
        sensor.station_id, sensor.variable_code, sensor.sensor_type = observation.station_id, variable, sensor_type
    db.commit()
    return result.rowcount or 0


STANDARDIZATION_VERSION = "OBS-STD-1.0"

def map_mdc_item(item_code: str):
    code=(item_code or "UNKNOWN").strip().upper()
    if code.startswith("TIDE_LEVEL"): return "TIDE", "cm", "TIDE_GAUGE"
    if "WAVE" in code or code in {"SEA_LEVEL","WAVE_HEIGHT","WAVE_PERIOD"}: return "WAVE", "m", "WAVE_SENSOR"
    units={"WATER_TEMP":("WATER_TEMP","C","WATER_QUALITY"),"TEMP":("WATER_TEMP","C","WATER_QUALITY"),"SALINITY":("SALINITY","PSU","WATER_QUALITY"),"SALINITY2":("SALINITY","PSU","WATER_QUALITY"),"ELECT_CONDUCT":("ELECT_CONDUCT","MS/CM","WATER_QUALITY"),"WIND_SPEED":("WIND_SPEED","M/S","METEOROLOGY"),"WIND_DIRECT":("WIND_DIRECT","DEG","METEOROLOGY"),"WIND_GUST":("WIND_GUST","M/S","METEOROLOGY"),"AIR_PRES":("AIR_PRES","HPA","METEOROLOGY"),"AIR_TEMP":("AIR_TEMP","C","METEOROLOGY")}
    return units.get(code,(code,"UNKNOWN","MDC"))

def as_float(value):
    try: return float(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError): return None


def standardize_observation(observation: ObservationRaw) -> ObservationStandard:
    """원시 관측값을 표준 단위로 변환하고 재현 가능한 ID를 만든다."""
    source_unit = observation.value_unit or "UNKNOWN"
    variable_code, mapped_unit, _ = map_mdc_item(observation.source_item_code or observation.variable_code)
    source_unit = source_unit if source_unit != "UNKNOWN" else mapped_unit
    # Keep source units for meteorological/water-quality items; tide metres convert to cm.
    unit_rules = {
        ("TIDE", "CM"): ("cm", "IDENTITY_CM"),
        ("WAVE", "M"): ("m", "IDENTITY_M"),
    }
    if variable_code == "TIDE" and source_unit.strip().upper() == "M":
        standard_unit, conversion_rule = "cm", "M_TO_CM"
    else:
        standard_unit, conversion_rule = unit_rules.get(
            (variable_code, source_unit.strip().upper()),
            (source_unit, "IDENTITY_UNMAPPED_UNIT"),
        )
    key = "|".join([
        observation.station_id,
        observation.sensor_id,
        variable_code,
        observation.timestamp_utc.isoformat() if observation.timestamp_utc else "",
    ])
    observation_id = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return ObservationStandard(
        observation_id=observation_id,
        station_id=observation.station_id,
        sensor_id=observation.sensor_id,
        variable_code=variable_code,
        timestamp_utc=observation.timestamp_utc,
        value_raw=observation.value_raw,
        value_standard=observation.value_raw * 100 if conversion_rule == "M_TO_CM" and observation.value_raw is not None else observation.value_raw,
        source_unit=source_unit,
        standard_unit=standard_unit,
        conversion_rule=conversion_rule,
        standardization_version=STANDARDIZATION_VERSION,
        qc_flag=observation.qc_flag, mqc_flag=observation.mqc_flag, water_step=observation.water_step,
        from_depth=observation.from_depth, to_depth=observation.to_depth, receive_time=observation.receive_time,
        source_item_code=observation.source_item_code,
    )


def insert_standardized_idempotent(db: Session, observations: List[ObservationRaw]) -> int:
    """표준화 행을 자연키 충돌 없이 PostgreSQL에 적재한다."""
    standardized = [standardize_observation(o) for o in observations if o.timestamp_utc]
    if not standardized:
        return 0
    values = [{
        "observation_id": o.observation_id,
        "station_id": o.station_id,
        "sensor_id": o.sensor_id,
        "variable_code": o.variable_code,
        "timestamp_utc": o.timestamp_utc,
        "value_raw": o.value_raw,
        "value_standard": o.value_standard,
        "source_unit": o.source_unit,
        "standard_unit": o.standard_unit,
        "conversion_rule": o.conversion_rule,
        "standardization_version": o.standardization_version,
        "qc_flag": o.qc_flag, "mqc_flag": o.mqc_flag, "water_step": o.water_step, "from_depth": o.from_depth, "to_depth": o.to_depth, "receive_time": o.receive_time, "source_item_code": o.source_item_code,
    } for o in standardized]
    statement = pg_insert(ObservationStandard).values(values).on_conflict_do_nothing(index_elements=["station_id","sensor_id","variable_code","timestamp_utc"])
    result = db.execute(statement)
    db.commit()
    return result.rowcount or 0

def observation_from_mdc(row: Dict[str, Any], source_table: str) -> ObservationRaw:
    """Preserve item, depth, original KST and missing QC rather than synthesizing them."""
    if source_table not in {"WEB_OBS_ST", "WEB_OBS_VBU", "TP_OBS_SO"}:
        raise ValueError("Unsupported MDC source table")
    station_id = str(row["obs_post_id"]).strip()
    item = str(row["obs_item_code"]).strip().upper()
    timestamp = shift_time_to_present(row["obs_time"])
    variable, unit, _ = map_mdc_item(item)
    unit = row.get("source_unit") or unit
    depth = [row.get(key) for key in ("water_step", "fr_depth", "to_depth")]
    suffix = ""
    if any(value is not None for value in depth):
        suffix = "_" + hashlib.sha256("|".join(str(as_float(v)) for v in depth).encode()).hexdigest()[:12]
    qc = str(row.get("mqc_flag") or row.get("qc_flag") or "").upper()
    return ObservationRaw(
        station_id=station_id, sensor_id=f"S_{item}_{station_id}{suffix}",
        timestamp_kst=timestamp, timestamp_utc=timestamp - datetime.timedelta(hours=9),
        variable_code=variable, value_raw=as_float(row.get("obs_value")), value_unit=unit,
        source_system=f"MDC_{source_table}", source_item_code=item,
        value_status="OK" if qc in {"1", "G"} else "ANOMALY" if qc in {"4", "B"} else "UNREVIEWED",
        qc_flag=row.get("qc_flag"), mqc_flag=row.get("mqc_flag"), receive_time=row.get("receive_time"),
        water_step=as_float(depth[0]), from_depth=as_float(depth[1]), to_depth=as_float(depth[2]),
    )


def _sync_observations(db: Session, table: str, start_time=None, end_time=None):
    if table not in {"WEB_OBS_ST", "WEB_OBS_VBU", "TP_OBS_SO"}:
        raise ValueError("Unsupported MDC source table")
    if start_time is None or end_time is None:
        start_time, end_time = get_simulated_time_range(10)
    depth = ", WATER_STEP, FR_DEPTH, TO_DEPTH" if table == "WEB_OBS_VBU" else ""
    base = f"SELECT OBS_POST_ID, OBS_ITEM_CODE, OBS_TIME, OBS_VALUE{depth}"
    where = f" FROM {table} WHERE OBS_TIME > :start_time AND OBS_TIME <= :end_time"
    rows = fetch_with_fallback(base + ", QC_FLAG, MQC_FLAG, RECEIVE_TIME" + where, base + where, {"start_time": start_time, "end_time": end_time})
    inserted = standardized = 0
    for offset in range(0, len(rows), 1000):
        observations = [observation_from_mdc(row, table) for row in rows[offset:offset + 1000]]
        inserted += insert_observations_idempotent(db, observations)
        standardized += insert_standardized_idempotent(db, observations)
    return {"source_rows": len(rows), "inserted_raw": inserted, "inserted_standard": standardized}


def sync_station_data(db: Session, start_time=None, end_time=None):
    """Synchronize all station items, preserving their individual units and timestamps."""
    return _sync_observations(db, "WEB_OBS_ST", start_time, end_time)


def sync_tide_data(db: Session, start_time=None, end_time=None):
    """Read actual tide observations from TP_OBS_SO, not the meteorological table."""
    return _sync_observations(db, "TP_OBS_SO", start_time, end_time)


def sync_buoy_data(db: Session, start_time=None, end_time=None):
    """Synchronize buoy items; depth bins have distinct sensor identities."""
    return _sync_observations(db, "WEB_OBS_VBU", start_time, end_time)


def sync_today_bulk(db: Session):
    """Collect today's source observations without shifting the observation time."""
    _, now = get_simulated_time_range()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sync_station_data(db, start_time=start_of_day, end_time=now)
    sync_tide_data(db, start_time=start_of_day, end_time=now)
    sync_buoy_data(db, start_time=start_of_day, end_time=now)


def sync_job():
    """스케줄러에 의해 10초 주기로 실행될 동기화 작업"""
    init_oracle()
    
    db = SessionLocal()
    try:
        sync_station_data(db)
        sync_tide_data(db)
        sync_buoy_data(db)
    except Exception as e:
        print(f"ETL 프로세스 중 치명적인 에러 발생: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

def main():
    print("==================================================")
    print(" 외부 Oracle MDC DB -> 로컬 PostgreSQL 동기화 파이프라인 (수동 실행)")
    print("==================================================\n")
    init_oracle()
    db = SessionLocal()
    try:
        sync_metadata(db)
        sync_station_data(db)
        sync_tide_data(db)
        sync_buoy_data(db)
    finally:
        db.close()

if __name__ == "__main__":
    main()
