# 전체 Parquet 변환 상태 (2026-10-01)

## 확인 결과

`E:\백업\data\old\spool(2001_2021)` 전체 변환 작업은 완료 상태다. 변환 대상 Lake는 `C:\AI_Observation\data_lake\spool_2001_2021`이며, `manifest.json`의 모든 입력 항목이 `CONVERTED`로 기록되어 있다.

| 항목 | 결과 |
|---|---:|
| manifest 입력 파일 | 360,133 |
| 변환 성공 | 360,133 |
| 변환 실패 | 0 |
| Parquet 파일 | 93,649 |
| Parquet 용량 | 약 37.94 GB |
| 변환 행 수 | 3,595,161,514 |
| 기간 파티션 | 2000~2022 |
| 변수 파티션 | `TIDE` |
| manifest 갱신 시각 | 2026-09-19 15:44:50 (KST) |

## PostgreSQL 적재

`data_lake_stat`의 카운터 컬럼을 `BIGINT`로 확장한 뒤 manifest 통계를 적재했다.

- `lake_name`: `spool_2001_2021`
- `variable_code`: `TIDE`
- `row_count`: 3,595,161,514
- `missing_count`: 0 (현재 파서가 `-999` 센티널을 결측으로 재분류하지 않은 상태)
- `min_value`: -999.0
- `max_value`: 1010.02382
- 적재 레코드: 1건

## 운영 상태 및 후속 조치

현재 변환 프로세스가 백그라운드에서 실행 중인 상태는 아니다. 결과 파일과 manifest가 존재하므로 재실행할 필요는 없다. 다만 이번 spool 원본은 파서 결과가 `TIDE` 하나로 분류되었으므로, 다음 단계에서 원본 파일명·헤더·관측항목 코드 기반으로 `WAVE`, 수온, 염분, 기상 등 비조위 항목을 식별하는 전용 매핑을 보강해야 한다. 또한 `-999` 등 결측 센티널을 `missing_count`에 반영하고, 재생성 시 변수별 통계를 갱신해야 한다.

검증 명령:

```powershell
$lake = 'C:\AI_Observation\data_lake\spool_2001_2021'
Get-ChildItem $lake -Filter '*.parquet' -Recurse -File | Measure-Object
$env:PYTHONPATH = 'backend'
python -m app.scripts.load_datalake_stats `
  --manifest "$lake\manifest.json" --lake-name spool_2001_2021
```
