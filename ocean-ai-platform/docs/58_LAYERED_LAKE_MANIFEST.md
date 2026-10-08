# 계층별 manifest 레이크 운영

적용일: 2026-10-04. 사용자 지정 최종 루트: **C:/AI_Observation/data_lake/spool_2001_2026**.

기존 spool_2001_2021 디렉터리를 같은 상위 폴더 안에서 spool_2001_2026으로 이름 변경했다. 이전 경로는 더 이상 존재하지 않는다. 기존 year 파티션과 원래 manifest.json은 변경하지 않았으며, manifest SHA-256은 변경 전후 `7066fd50efd4e8799d44c7bfa69653eb6e3ab4733c4b8a9131a269a948434ac4`로 같다.

```text
spool_2001_2026/
  year=2000/ ... year=2022/         기존 자료 그대로 보존
  manifest.json                   과거 변환 기록, 분석 입력 manifest 아님
  raw/reconciled_v1/               새 원천 보존 Parquet 231개
  standardized/                   아직 승인된 표준 관측 없음
  metadata/
    lake.json                     루트 이름·계층 계약
    raw/manifest.json             RAW_ONLY, 231개/1,098,334행
    raw/evidence/                 기간·월별·결측·센서·정산 스냅샷
    standardized/manifest.json    HOLD, 승인 전 분석 차단
    legacy/manifest.json          HOLD, 기존 catalog 참조; 개별 승인 등록 전
```

폴더명의 2026은 사용자가 선택한 MDC 확인 범위 기준이다. 2001~2026 연속 실측/QC 승인 완료를 뜻하지 않는다. 기존 및 파일럿 자료에 2000년도 포함되어 있으며 실제 범위는 manifest와 기간 프로파일을 기준으로 한다.

## 코드 변경

새 서비스 `backend/app/services/lake_manifest.py`에서 허용 계층, manifest 버전/상태, 루트 내부 경로, 계층 일치, 중복 파일, 전체 SHA-256, 행 수, 표준 스키마·UTC·관측 키를 검증한다. 경로 이탈, 손상, 누락을 조용히 건너뛰지 않는다.

다음 세 소비자는 재귀 Parquet 검색을 제거했다.

- `analyze_long_term`: 장기 분석.
- `build_imputation_dataset`: 보간 학습 후보 생성. 중복을 임의 제거하지 않으며, 유효한 결측 window가 없으면 파일을 만들지 않는다.
- `forecast_tide_baseline`: 예측 기준 모델.

세 함수/CLI는 layer를 반드시 지정해야 하며 승인된 standardized만 허용한다. raw/legacy를 학습 입력으로 우회할 수 없다. 다른 센서가 같은 관측소/변수에 섞이면 명시적 센서 분할이 필요하다는 오류로 중단한다. 이 변경은 위 세 디렉터리 기반 소비자에 적용된다. 별도로 파일 하나를 직접 지정하는 기존 실험용 학습 스크립트 전체를 개편한 것은 아니다.

```powershell
$env:PYTHONPATH='backend'
python -m app.scripts.analyze_long_term --source 'C:\AI_Observation\data_lake\spool_2001_2026' --layer standardized --variable-code TIDE --output trend.json
python -m app.scripts.forecast_tide_baseline --source 'C:\AI_Observation\data_lake\spool_2001_2026' --layer standardized --station-id DT_0001 --output forecast.json
python -m app.scripts.build_imputation_dataset --source 'C:\AI_Observation\data_lake\spool_2001_2026' --layer standardized --station-id DT_0001 --output imputation.parquet
```

현재 실제 standardized manifest는 HOLD이므로 위 명령은 `STANDARDIZED_RELEASE_NOT_APPROVED`로 중단되는 것이 정상이다. 단순히 상태 문자열을 APPROVED로 바꾸는 것이 승인 절차가 아니다. 원천 시각·실측 역할·장비 유효기간·QC 코드/규칙과 중복 계보를 확정하고 검증된 파일 목록/해시/행 수 및 실제 승인 근거를 등록해야 한다.

원천 보존층은 `select_files(root, 'raw')`로 명시적으로 선택해 검사한다. 모델용 `load_observations`와 구분한다. legacy manifest의 빈 files 목록은 '기존 자료 없음'이 아니라 '승인 입력으로 개별 등록하지 않음'이며 선택 요청을 차단한다. 과거 manifest의 절대 경로는 역사 기록으로 남겼으며 신규 selector는 그 경로를 실행 입력으로 사용하지 않는다.

## 실제 배치·검증 결과

- raw 231개 파일 복사 전후 해시 일치, 1,098,334개 항목 레코드 정산.
- 전체 재변환 재실행에서 231개 모두 UNCHANGED.
- 실제 루트의 raw manifest 선택: 231개, 행 합계 일치.
- 실제 루트의 분석/예측/보간: 미승인 표준층을 세 함수 모두 차단. legacy도 보류 상태 차단.
- 회귀 테스트 10개 통과: 목록 밖 파일 배제, manifest/승인 누락, 경로 이탈·계층 혼합, 손상, 중복, 행 수, raw 학습 차단, 세 소비자의 승인 합성 자료 실행.
- 합성 실행 중 기존 결측 개수 계산이 실제 값에 `not`을 적용하던 문제를 발견해 관측 마스크로 수정했다. NaN은 JSON null로 저장한다. timestamp가 마이크로초인 경우 장기 추세가 1,000배 틀어지던 계산도 timedelta 기반 일수로 변경했다.

기존 자료와 새 원천의 **물리적 계층 배치는 완료**, 동일 관측의 의미적 병합과 표준화 사용 기간 승인은 미완료다. 센서/QC가 미확정인 값을 승인된 표준 관측으로 노출하지 않는다.

근거: [배치 결과](<local-evidence-root>/2026-09-29/new-chat/outputs/reconciled-parquet/layer-integration-result.json), [변환·기간 판정](<local-evidence-root>/2026-09-29/new-chat/outputs/reconciled-parquet/PARQUET_AND_USABLE_PERIODS.md), [월별 통계](<local-evidence-root>/2026-09-29/new-chat/outputs/reconciled-parquet/monthly-counts.csv).
