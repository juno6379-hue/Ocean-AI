# Dataset Version Registry

작성일: 2026-09-16

## 모델

`DatasetRegistry`(`dataset_registry`)에 다음을 저장한다.

`dataset_id`, `dataset_name`, `dataset_version`, `dataset_split`, `station_scope`, `variable_scope`, `period_start`, `period_end`, `sample_count`, `normal_count`, `suspect_count`, `bad_count`, `missing_count`, `feature_version`, `label_version`, `preprocessing_version`, `created_at`

데이터 분할은 `TRAIN`, `VALIDATION`, `TEST`, `BLIND_TEST`, `RETRAINING_POOL`만 허용한다. `dataset_name + dataset_version`은 유일하다.

## 누수 방지

등록 API는 다음을 거부한다.

- 시작 시각이 종료 시각 이후인 데이터셋
- TRAIN·VALIDATION·TEST·BLIND_TEST 사이에 같은 관측소가 포함되는 경우
- 같은 분할의 버전끼리 동일 관측소의 기간이 겹치는 경우
- 음수 샘플/등급 건수

`station_scope`에 `*`가 있으면 전체 관측소로 간주해 다른 분할과의 겹침을 차단한다. `RETRAINING_POOL`은 운영 학습 후보 영역으로 분리해 일반 평가 분할과의 누수 검사 대상에서 제외한다.

## API

- `GET /api/datasets?dataset_split=TRAIN`
- `POST /api/datasets`

등록 시 `feature_version`, `label_version`, `preprocessing_version`을 함께 요구해 동일 데이터셋을 재현할 수 있게 했다. 현재 Registry는 구조와 검증 API까지 구현했으며, 기존 데이터에 임의 데이터셋 레코드는 생성하지 않았다.
