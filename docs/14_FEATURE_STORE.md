# Feature Store 구조

작성일: 2026-09-16

## 목적

AI 학습 입력을 임의 컬럼이나 코드에 흩어두지 않고 Feature 정의와 계산값을 분리한다. 정의에는 의미·원천 필드·계산 로직·윈도우·버전을 저장하고, 값에는 관측소·센서·변수·시각별 결과와 동일한 Feature 버전을 저장한다.

## 모델

`FeatureDefinition` (`feature_definition`): `feature_id`, `feature_name`, `feature_group`, `description`, `calculation_logic`, `source_fields`, `window_size`, `feature_version`

`FeatureValue` (`feature_value`): `station_id`, `sensor_id`, `variable_code`, `timestamp_utc`, `feature_id`, `feature_value`, `feature_version`

정의는 `feature_id + feature_version`, 값은 관측 식별 정보와 `feature_id + feature_version`의 조합을 유일키로 사용한다.

## Feature 그룹 및 초기 정의

다음 9개 예시 정의를 버전 `1.0`으로 등록했다.

- Temporal Feature: `moving_mean`, `moving_std`, `rate_of_change`
- Rule QC Feature: `persistence_duration`, `qc_rule_fail_count`
- Spatial Feature: `neighbor_difference`
- Event Feature: `tide_prediction_residual`
- Metadata Feature: `days_since_calibration`
- Operation Feature: `recent_maintenance_flag`

허용 그룹은 Raw Feature, Rule QC Feature, Temporal Feature, Spatial Feature, Metadata Feature, Operation Feature, Event Feature이다.

## API

- `GET/POST /api/features/definitions`
- `GET/POST /api/features/values`

Feature 값을 등록할 때 해당 정의와 버전이 존재하는지 확인한다. 아직 계산 엔진은 연결하지 않았으므로 초기 등록 건수는 정의 9건, 계산값 0건이다. 계산 배치가 실행되면 `FeatureValue`를 생성하고, 로직 변경 시 새 `feature_version`을 사용한다.
