# 파일 역할: 개발용 확장 예제 자료를 구성합니다.
import sys
import os
import datetime
import random
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import engine, SessionLocal
from app.models.domain import StationMetadata, SensorMetadata, ObservationRaw

def seed_extended_data():
    db = SessionLocal()
    try:
        stations_info = [
            {"id": "ST_HUPO_01", "name": "후포", "lat": 36.68, "lon": 129.45, "base_val": 140, "unit": "cm", "type": "조위계", "code": "TIDE"},
            {"id": "ST_INCHEON_01", "name": "인천", "lat": 37.45, "lon": 126.60, "base_val": 400, "unit": "cm", "type": "조위계", "code": "TIDE"},
            {"id": "ST_MOKPO_01", "name": "목포", "lat": 34.78, "lon": 126.38, "base_val": 250, "unit": "cm", "type": "조위계", "code": "TIDE"}
        ]
        
        start_date = datetime.datetime(2025, 5, 1, 0, 0, 0)
        
        for st in stations_info:
            # 1. 관측소
            if not db.query(StationMetadata).filter(StationMetadata.station_id == st["id"]).first():
                station = StationMetadata(
                    station_id=st["id"],
                    station_name=st["name"],
                    network_type="조위관측소",
                    sea_area="연안",
                    latitude=st["lat"],
                    longitude=st["lon"],
                    status="ACTIVE"
                )
                db.add(station)
                print(f"Station {st['id']} created.")
            
            # 2. 센서
            sensor_id = f"S_{st['code']}_{st['id'].split('_')[1]}" # 예: S_TIDE_HUPO
            if not db.query(SensorMetadata).filter(SensorMetadata.sensor_id == sensor_id).first():
                sensor = SensorMetadata(
                    station_id=st["id"],
                    sensor_id=sensor_id,
                    sensor_type=st["type"],
                    variable_code=st["code"],
                    status="ACTIVE"
                )
                db.add(sensor)
                print(f"Sensor {sensor_id} created.")
            
            # 3. 데이터 적재 확인
            existing_data = db.query(ObservationRaw).filter(
                ObservationRaw.station_id == st["id"],
                ObservationRaw.timestamp_kst >= start_date
            ).first()
            
            if existing_data:
                print(f"Data for {st['id']} already exists. Skipping.")
                continue
                
            observations = []
            print(f"Seeding observation data for {st['id']}...")
            for day in range(31):
                for hour in range(24):
                    t = start_date + datetime.timedelta(days=day, hours=hour)
                    
                    import math
                    # 조석 효과 주기 시뮬레이션
                    tidal_effect = math.sin(hour * math.pi / 6) * 100 
                    val = st["base_val"] + tidal_effect + random.uniform(-5, 5)
                    
                    status = "OK"
                    # 인위적 이상치
                    if st["id"] == "ST_INCHEON_01" and day == 10 and hour in [4, 5, 6]:
                        val = val + 300 # 비정상 튀는 값
                        status = "ANOMALY"
                        
                    obs = ObservationRaw(
                        station_id=st["id"],
                        sensor_id=sensor_id,
                        timestamp_kst=t,
                        timestamp_utc=t - datetime.timedelta(hours=9),
                        variable_code=st["code"],
                        value_raw=round(val, 1),
                        value_unit=st["unit"],
                        source_system="DAQ_EXT",
                        value_status=status
                    )
                    observations.append(obs)
            db.bulk_save_objects(observations)
            print(f"Successfully seeded {len(observations)} records for {st['id']}.")
            
        db.commit()
    except Exception as e:
        print(f"Error seeding extended data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_extended_data()
    print("Extended data seeding complete.")
