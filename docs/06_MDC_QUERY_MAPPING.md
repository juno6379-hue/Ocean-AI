# 06. MDC DB 쿼리 및 데이터 매핑 명세서

본 문서는 실제 해양 관측 원천 데이터를 보유하고 있는 **오라클 MDC DB(`ocean_web`)**의 실시간 테이블들과, AI 분석 처리를 위해 구성된 **내부 PostgreSQL DB(`ocean_ai_db`)** 간의 ETL(추출/변환/적재) 테이블 및 컬럼 매핑 관계를 정의합니다.

---

## 🏗️ 1. 메타데이터(관측소 정보) 매핑

관측소 고유 식별자, 위치(위/경도), 운영 상태 등을 1일 1회(서버 재구동 시) 동기화합니다.

### 📌 매핑 상세 (`WEB_STATION` ➡️ `StationMetadata`)

| MDC Source (`WEB_STATION`) | Type | Target (`StationMetadata`) | 비고 및 변환 규칙 |
| :--- | :--- | :--- | :--- |
| `OBS_POST_ID` | `VARCHAR2` | `station_id` (PK) | 관측소 고유 ID (예: ST_JEJU_01) |
| `OBS_POST_NAME` | `VARCHAR2` | `station_name` | `_과거성과`, `_기점` 등 불필요한 접미사 정제 (Regex 사용) |
| `DATA_TYPE` | `VARCHAR2` | `network_type` | `DT`/`SO`➡️조위관측소, `TW`/`KG`➡️해양관측부이, `IE`➡️해양과학기지, `RT`➡️해양관측소, `HF`➡️HF-Radar |
| `OBS_LAT` | `NUMBER` | `latitude` | WGS84 위도 좌표 |
| `OBS_LON` | `NUMBER` | `longitude` | WGS84 경도 좌표 |
| `DO_NM` | `VARCHAR2` | `sea_area` | 소속 행정구역(도/시) |
| `ADDRESS` | `VARCHAR2` | (없음 - 향후 확장) | 상세 주소 정보 |
| `TOTAL_STATUS` | `NUMBER` | `status` | 1➡️'ACTIVE', 2➡️'MAINTENANCE', 기타➡️'ERROR' |

> **💡 메타데이터 수집 화이트리스트 (Data Cleansing)**
> 불필요한 해외 관측망(PA), ARGO 플로트(AG), 테스트/임시 관측소(SF, IC 등)는 AI 분석용 로컬 DB 적재 대상에서 제외한다. 실제 운영 코드는 **조위(DT), 부이(TW), 과학기지(IE), 일반 해양관측소(RT), HF-Radar(HF)**이며, `SO`/`KG`는 구자료 호환 별칭이다.

---

## 🌊 2. 조위관측소 데이터 매핑 (Delta 수집)

매 5분마다 실행되는 스케줄러가 최근 30분 내 생성된 데이터만 가져옵니다.

### 📌 매핑 상세 (`WEB_OBS_ST` ➡️ `ObservationRaw`)

| MDC Source (`WEB_OBS_ST`) | Type | Target (`ObservationRaw`) | 비고 및 변환 규칙 |
| :--- | :--- | :--- | :--- |
| `OBS_POST_ID` | `VARCHAR2` | `station_id` (FK) | 관측소 연동 키 |
| (Script Generated) | - | `sensor_id` | `S_TIDE_{OBS_POST_ID}` 로 조합 |
| `OBS_TIME` | `DATE` | `timestamp_kst` | KST 기준 관측 시간 |
| `OBS_TIME - 9H` | - | `timestamp_utc` | KST에서 9시간 차감하여 계산 |
| (Hardcoded) | - | `variable_code` | 고정값: `"TIDE"` |
| `OBS_VALUE` | `NUMBER` | `value_raw` | 수위 관측값 |
| (Hardcoded) | - | `value_unit` | 고정값: `"cm"` |

---

## 📡 3. 해양관측부이 데이터 매핑 (Delta 수집)

조위 데이터와 동일하게 매 5분마다 최근 30분(Delta) 데이터를 수집하여 적재합니다.

### 📌 매핑 상세 (`WEB_OBS_VBU` ➡️ `ObservationRaw`)

| MDC Source (`WEB_OBS_VBU`) | Type | Target (`ObservationRaw`) | 비고 및 변환 규칙 |
| :--- | :--- | :--- | :--- |
| `OBS_POST_ID` | `VARCHAR2` | `station_id` (FK) | 관측소 연동 키 |
| (Script Generated) | - | `sensor_id` | `S_WAVE_{OBS_POST_ID}` 로 조합 |
| `OBS_TIME` | `DATE` | `timestamp_kst` | KST 기준 관측 시간 |
| `OBS_TIME - 9H` | - | `timestamp_utc` | KST에서 9시간 차감하여 계산 |
| (Hardcoded) | - | `variable_code` | 고정값: `"WAVE"` (유의 파고 등) |
| `OBS_VALUE` | `NUMBER` | `value_raw` | 파고 관측값 |
| (Hardcoded) | - | `value_unit` | 고정값: `"m"` |

---

## ⚡ 4. 쿼리 성능 최적화 (Delta) 방안

* **부하 방지 (Delta 쿼리)**
  수천만 건의 데이터를 보유한 `WEB_OBS_ST`와 `WEB_OBS_VBU` 테이블을 Full Scan하지 않도록, `WHERE OBS_TIME >= :delta_time` 조건을 추가하여 **최근 30분 간 생성된 Row만 선별적**으로 긁어옵니다.
* **배치 저장 (Bulk Insert)**
  수집된 파이썬 List 객체(최대 수십~수백 건)를 `db.bulk_save_objects()` 명령어로 PostgreSQL에 일괄 커밋하여 I/O 성능을 극대화합니다.
