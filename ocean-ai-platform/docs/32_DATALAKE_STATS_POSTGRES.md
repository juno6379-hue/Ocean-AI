# Data Lake 통계 PostgreSQL 적재

Parquet 원본 관측값은 PostgreSQL에 일괄 적재하지 않는다. 변환기가 생성한 `manifest.json`의 변수별 행 수·결측 수·최소/최대값을 `DataLakeStat`에 저장한다.

```powershell
$env:PYTHONPATH="backend"
python -m app.scripts.load_datalake_stats --manifest "D:\ocean-data-lake\spool_2001_2021\manifest.json" --lake-name spool_2001_2021
```

API: `GET /api/data-lake/stats`, `GET /api/data-lake/summary`. 응답은 실제 DB 통계이며 `is_demo=false`다. 다음 단계에서 파티션별 평균·QC 분포·관측소·기간을 manifest에 추가하고 동일 모델에 적재한다.
