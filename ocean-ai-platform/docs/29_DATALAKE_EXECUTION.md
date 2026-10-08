# Data Lake 시계열 분석 실행

`backend/app/scripts/build_datalake.py`는 백업 원본을 청크 단위로 읽어 Parquet으로 변환한다. 원본 파일은 수정하지 않으며, `year/month/station_id/variable_code` 파티션과 `manifest.json`(SHA-256, 변환 행 수, 변수별 min/max/missing)을 생성한다.

실행 예:

```powershell
python -m app.scripts.build_datalake --source 'E:\백업\data\old\spool(2001_2021)' --lake 'D:\ocean-data-lake\spool_2001_2021'
```

처음에는 `--limit-files 1`로 형식과 인코딩을 검증한 뒤 전체 변환한다. Parquet 엔진은 `pyarrow`이며, 실패한 파일은 manifest에 `UNPARSEABLE`로 남긴다. 생성된 Parquet에서 변수·관측소·월별 통계를 추출해 PostgreSQL DatasetRegistry와 연결하는 작업은 변환 검증 후 수행한다.
