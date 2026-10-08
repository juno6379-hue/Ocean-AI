# QC Rule Result 계층

작성일: 2026-09-16

## 목적

`QCFlagHistory`는 관측값의 종합 QC 이력이고, `qc_rule_result`는 개별 QC 규칙이 실행된 결과다. 한 관측값에 여러 규칙을 적용해도 규칙별 판정·임계값·점수·버전을 독립적으로 추적할 수 있다.

## 저장 구조

`QCRuleResult`에 다음 필드를 추가했다.

`qc_result_id`, `observation_id`, `station_id`, `sensor_id`, `variable_code`, `timestamp_utc`, `qc_rule_id`, `qc_rule_name`, `qc_stage`, `input_value`, `threshold_value`, `result_flag`, `result_score`, `rule_version`, `executed_at`

`observation_id`는 `observation_standard.observation_id`를 참조한다. `observation_id + qc_rule_id + rule_version` 복합 유일키로 같은 규칙 버전의 중복 실행 기록을 방지한다.

## API

- `GET /api/qc/rule-results?station_id=...&observation_id=...&limit=100`
- `POST /api/qc/rule-results`

POST 시 Standard Observation 존재 여부를 검증하고 `qc_result_id`와 `executed_at`을 서버에서 생성한다. 현재 기존 데이터에 임의의 QC 결과를 생성하지 않았으며, 실제 규칙 엔진이 실행될 때 이 API 또는 동일한 저장 서비스를 사용해야 한다.

## 운영 원칙

개별 규칙 결과를 먼저 저장한 뒤 QC 종합 플래그를 산출한다. 규칙 변경 시 `rule_version`을 증가시키고 과거 결과는 수정하지 않는다. `input_value`와 `threshold_value`를 함께 보존해 판정 재현성을 확보한다.
