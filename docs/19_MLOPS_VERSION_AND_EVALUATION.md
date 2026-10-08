# MLOps Registry 고도화

작성일: 2026-09-16

## Registry 버전 추적

`ModelRegistry`에 다음 연결 정보를 추가했다.

- `model_version`
- `dataset_version`
- `feature_version`
- `label_version`
- `preprocessing_version`
- `metrics_json`
- `deployment_status`, `deployment_target`, `deployed_at`
- `is_champion`, `rolled_back_from`

`RetrainingHistory`에도 dataset/label 버전을 추가해 학습 실행의 입력 스냅샷을 추적한다.

## 평가 지표

모델 등록 API는 다음 지표를 모두 요구한다.

`precision`, `recall`, `f1`, `auroc`, `false_positive_rate`, `false_negative_rate`, `latency`

Accuracy 단독 등록은 거부한다. 비 latency 지표는 0~1, latency는 0 이상이어야 한다.

## API

- `POST /api/mlops/models`: 버전·데이터셋·Feature·Label·전처리 버전과 평가 지표 등록
- `POST /api/mlops/models/{model_version}/deploy`: Champion 배포
- `POST /api/mlops/models/{model_version}/rollback`: 배포 롤백
- `GET /api/mlops/champion-challenger?champion_version=...&challenger_version=...`: 두 버전 지표 비교
- `POST /api/mlops/retrain`: 재학습 이력 PENDING 등록
- 기존 `GET /api/mlops/summary`, `GET /api/mlops/retrain-history`: 확장 버전·배포 정보 반환

배포 시 기존 Champion을 해제하고 새 모델을 Champion/PRODUCTION으로 지정한다. 롤백 모델은 `ROLLED_BACK/ARCHIVED`로 남겨 감사 추적이 가능하다. 실제 artifact 교체는 배포 시스템 연결이 필요하다.

MLOps 컬럼 마이그레이션, 테이블 모델 반영, API 라우트 컴파일을 완료했다.
