# QC Flag와 AI Label 분리

작성일: 2026-09-16

## 설계 원칙

QC Flag는 규칙 실행 결과와 운영 품질 판정이다. AI Label은 학습·분석을 위한 사건 단위의 품질 라벨과 오류 원인이다. 두 값을 서로 복사하거나 하나의 필드로 취급하지 않는다.

## 추가 모델

`AILabel`(`ai_label` 테이블)에 다음 필드를 추가했다.

`label_id`, `station_id`, `sensor_id`, `variable_code`, `event_start`, `event_end`, `quality_label`, `error_type`, `error_cause`, `label_source`, `label_confidence`, `review_status`, `reviewer_id`, `label_version`, `created_at`, `updated_at`

`error_cause`에는 다음 후보만 허용한다.

`facility_damage`, `equipment_fault`, `sensor_degradation`, `biofouling`, `power_fault`, `communication_fault`, `qc_algorithm_error`, `cross_variable_inconsistency`, `statistical_outlier`, `db_error`, `service_publication_error`, `natural_event`, `unknown`

DB CHECK 제약과 API 입력 검증을 모두 적용했다. 기본 검토 상태는 `PENDING`, 기본 원인은 `unknown`이다.

## API

- `GET /api/qc/ai-labels?station_id=...&review_status=PENDING`
- `POST /api/qc/ai-labels`

등록 시 라벨 ID와 생성·수정 시각을 서버가 관리한다. 현재 QC Flag, QC Rule Result, AI Label 간 자동 변환은 의도적으로 연결하지 않았으며, 검토자는 `review_status`, `reviewer_id`, `label_version`을 별도로 관리한다.

테이블 생성과 Python 컴파일을 확인했다. 기존 데이터에 임의 AI Label은 생성하지 않았다.
