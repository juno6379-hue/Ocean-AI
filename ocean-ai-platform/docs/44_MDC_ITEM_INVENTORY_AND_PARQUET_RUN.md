# MDC 관측항목 inventory·Parquet·통계 적재 실행

실제 Oracle MDC의 `WEB_OBS_ST`, `WEB_OBS_VBU`에서 `OBS_ITEM_CODE`별 건수와 기간을 집계해 `mdc_item_inventory.json`으로 저장한다. 각 원본 코드는 `MDCItemMapping` 규칙으로 표준 변수·단위·센서 유형과 연결한다.

전체 백업 변환 명령:

```powershell
$env:PYTHONPATH="backend"
python -m app.scripts.build_datalake --source "E:\백업\data\old\spool(2001_2021)" --lake "C:\AI_Observation\data_lake\spool_2001_2021"
```

변환 완료 후 통계 적재:

```powershell
python -m app.scripts.load_datalake_stats --manifest "C:\AI_Observation\data_lake\spool_2001_2021\manifest.json" --lake-name spool_2001_2021
```

manifest가 없는 상태에서 통계 적재를 실행하지 않으며, 파싱 실패 파일은 `UNPARSEABLE`로 남긴다.
