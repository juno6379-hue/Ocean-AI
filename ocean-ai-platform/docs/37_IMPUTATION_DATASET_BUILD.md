# 긴 결측 보간 학습 Dataset 생성

`build_imputation_dataset.py`는 Parquet Data Lake에서 관측소·변수별 시계열을 읽어 고정 길이 window와 결측 mask를 생성한다. 원본값을 복원해 정답으로 덮어쓰지 않고, 관측값·mask·target을 별도 JSON 컬럼으로 저장해 GRU-D·BRITS·SAITS가 결측 패턴을 입력으로 사용할 수 있게 한다.

```powershell
$env:PYTHONPATH="backend"
python -m app.scripts.build_imputation_dataset `
  --source "D:\ocean-data-lake\spool_2001_2021" `
  --output "D:\ocean-datasets\imputation\DT_0001_TIDE_v1.parquet" `
  --station-id DT_0001 --variable-code TIDE
```

출력 옆 JSON에는 Dataset/Feature/Label/Preprocessing 버전, 행 수, window 크기와 SHA-256을 기록한다. `RETRAINING_POOL`로 생성되며 Human Approval 전에는 학습·배포에 사용하지 않는다. 실제 학습 전에는 관측소 hold-out, 시간 순서 분할, 인위적 masking MAE/RMSE 평가를 수행한다.
