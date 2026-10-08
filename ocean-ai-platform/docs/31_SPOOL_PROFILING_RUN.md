# spool 포맷·품질 프로파일링 실행

`profile_spool.py`는 `spool(2001_2021)` 원본을 읽기 전용으로 조사한다. 파일 전체를 메모리에 올리지 않고 앞부분 샘플만 읽어 확장자, 크기, 샘플 해시, 인코딩 후보, 구분자 후보, 관측항목 코드, 날짜 힌트를 기록한다.

실행:

```powershell
$env:PYTHONPATH="backend"
python -m app.scripts.profile_spool `
  --source "E:\백업\data\old\spool(2001_2021)" `
  --output "data_lake_profile\spool_inventory.json"
```

결과 JSON은 파서 구현의 입력으로 사용한다. `ERROR` 파일은 별도 전용 파서 대상으로 분류하며 원본을 이동·변경하지 않는다. 프로파일 완료 후 확장자별 파서를 확정하고 Parquet 변환을 실행한다.
