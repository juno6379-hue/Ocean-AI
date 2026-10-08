# 파일 역할: 개발용 초기 데이터베이스 자료를 구성합니다.
import sys
import os
import datetime
import random
from sqlalchemy.orm import Session

# backend 폴더를 path에 추가하여 app 모듈 임포트 가능하도록 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import engine, SessionLocal, Base
from app.models.domain import StationMetadata, SensorMetadata, ObservationRaw

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

def seed_data():
    db = SessionLocal()
    try:
        # 1. 관측소 메타데이터 시딩
        station_id = "ST_JEJU_01"
        existing_station = db.query(StationMetadata).filter(StationMetadata.station_id == station_id).first()
        if not existing_station:
            station = StationMetadata(
                station_id=station_id,
                station_name="제주 (기본 관측소)",
                network_type="조위관측소",
                sea_area="남해",
                latitude=33.51,
                longitude=126.52,
                status="ACTIVE"
            )
            db.add(station)
            db.commit()
            print(f"Station {station_id} created.")
        
        # 2. 센서 메타데이터 시딩
        sensor_id = "S_TEMP_01"
        existing_sensor = db.query(SensorMetadata).filter(SensorMetadata.sensor_id == sensor_id).first()
        if not existing_sensor:
            sensor = SensorMetadata(
                station_id=station_id,
                sensor_id=sensor_id,
                sensor_type="수온계",
                variable_code="TEMP",
                status="ACTIVE"
            )
            db.add(sensor)
            db.commit()
            print(f"Sensor {sensor_id} created.")

        # 3. 2025년 5월 관측 데이터 시딩 (시계열)
        print("Seeding observation data for May 2025...")
        start_date = datetime.datetime(2025, 5, 1, 0, 0, 0)
        
        # 데이터가 이미 있는지 확인
        existing_data = db.query(ObservationRaw).filter(
            ObservationRaw.station_id == station_id,
            ObservationRaw.timestamp_kst >= start_date
        ).first()
        
        if existing_data:
            print("Data for May 2025 already exists. Skipping data generation.")
            return

        observations = []
        for day in range(31): # 5월 1일 ~ 31일
            for hour in range(24): # 1시간 간격
                t = start_date + datetime.timedelta(days=day, hours=hour)
                
                # 기본 수온은 14~16도
                base_temp = 15.0 + random.uniform(-1, 1)
                
                # 이상치 주입 (5월 15일 오후 2시경)
                if day == 14 and hour in [13, 14, 15]:
                    base_temp = 38.5 + random.uniform(-0.5, 0.5) # 센서 오작동성 고온
                # 이상치 주입 (5월 20일 오전 8시경)
                elif day == 19 and hour in [8, 9]:
                    base_temp = 2.0 + random.uniform(-0.1, 0.1) # 센서 오작동성 저온
                    
                obs = ObservationRaw(
                    station_id=station_id,
                    sensor_id=sensor_id,
                    timestamp_kst=t,
                    timestamp_utc=t - datetime.timedelta(hours=9),
                    variable_code="TEMP",
                    value_raw=round(base_temp, 2),
                    value_unit="°C",
                    source_system="DAQ_01",
                    value_status="OK" if (5.0 < base_temp < 30.0) else "ANOMALY"
                )
                observations.append(obs)
        
        db.bulk_save_objects(observations)
        db.commit()
        print(f"Successfully seeded {len(observations)} observation records for {station_id}.")
        
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    seed_data()
    print("Database initialization and seeding complete.")
