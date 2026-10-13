# 41. 운영 표준 매핑·자동 계약·실제 Binding

기준일: 2026-10-13. 사용자가 요청한 풍향·풍속·기압·기온·수온 등의 운영 적재와 행별 사람 승인 없이 동작하는 시스템 정책 계약을 구현했다. `sync_mdc_db.py`와 검증된 monthly Parquet 적재가 `OPS-MDC-MAP-2.0`을 공유한다. 이 작업은 [공통 Schema 검토](40_COMMON_OBSERVATION_SCHEMA_REVIEW.md)의 운영 매핑 단계이며 모든 API/QC/학습의 공통 repository 전환은 아직 아니다.

## 실제 적재 범위

요청 화면의 기준시각 **2026-07-09 15:41:20 KST**까지 최근 24시간을 먼저 적재했다. 요청 범위는 2026-07-08 15:41:20 ~ 2026-07-09 15:41:20이며 실제 Binding의 관측시각은 **2026-07-08 15:42 ~ 2026-07-09 15:41 KST**다. UTC로는 2026-07-08T06:42:00Z ~ 2026-07-09T06:41:00Z다. Binding 생성 시각은 실제 실행일인 10월 13일로 기록하고 과거 관측일로 소급하지 않는다.

| 원천 | 실제 Raw/Standard 및 Binding 행 | 정책 밖 코드 행 |
|---|---:|---:|
| GD_OBS_BU | 67,887 | 34,192 |
| GD_OBS_VBU | 6,480 | 4,592 |
| GR_OBS_ST | 671,078 | 159,428 |
| 합계 | **745,445** | **198,212** |

정책 밖 코드는 원천 Parquet에 보존되어 있으며 이번 자동 운영 적재 대상에서 제외했다. 모든 해양 변수의 의미·단위가 이미 검증됐다는 의미가 아니다. 표의 행 수는 source-scoped logical channel 관측 수이며 서로 다른 원천의 중복을 제거한 유일 관측 수와 다르다. 2023~2026 전체 이력 적재 완료도 아니다.

초기 적재에서는 기준정보에 없던 `DT_0095`, `DT_0903`의 17,280행이 격리됐다. 검증된 원문 코드만 `SOURCE_IDENTIFIER_ONLY`로 등록해 모두 재처리했다. 새 참조의 `station_name`은 원천 코드 자체이고 명칭·좌표·관측망·설치일은 추정하지 않았다. 기존 323개 기준정보와 기존 Raw 13,621행·Standard 4,074행은 그대로 보존한다. 이러한 코드 참조는 실제 시설·장비의 동일성과 역사 유효기간 승인이 아니다.

## 자동 계약의 내용과 경계

- 계약 schema: `source-operational-mapping-1`, receipt schema: `source-operational-mapping-receipt-1`.
- 승인 주체: `system:source-standard-mapping`, role: `system`, mode: `SYSTEM_POLICY`.
- 승인 범위: `OPERATIONAL_STANDARDIZATION_ONLY`, `training_eligible=false`, `qc_approved=false`.
- 검증된 7월 파일 3개에 자동 계약 3건을 생성했다. 정책·manifest·Parquet SHA로 계약 ID를 고정하고 원장·판정·receipt·Binding을 연결한다. 사람을 승인자로 기록하지 않는다.
- 매핑은 명시한 코드·단위·KST·identity 배율 정책이다. 원문에 없는 단위·물리 센서 episode·조위 기준면·QC 판본을 역사적 확정 사실로 만들지 않는다. 풍향·파향은 CIRCULAR_DEGREES이며 운영 scalar 숫자 저장이 자료형별 QC 완성을 뜻하지 않는다.
- Raw QC/MQC/N1 literal, 수심과 타입, 수신시각, 파일 SHA와 정확한 `parquet_row_group`/`row_index`를 Binding에 보존한다. 값이 있어도 최종 QC 상태는 UNREVIEWED이며 실제 결측은 nullable 값과 MISSING으로 남긴다.
- 원본 CSV가 삭제됐으면 manifest의 기존 원문 SHA·크기와 현재 검증된 변환본을 유지하고 `VERIFIED_PRESERVED_TRANSFORM_ONLY`로 명시한다. Parquet 보유를 원본 CSV의 현재 별도 보존으로 표현하지 않는다.
- 기존 전체 `source_contract_v2` 및 dataset snapshot 권한 검증은 이 제한된 시스템 receipt를 학습 승인으로 받지 않는다. Dataset·label·event·Final QC·운영 model registry는 생성하지 않았다.

파고를 m, 파주기를 s, 풍향·파향을 DEG로 구분한다. 과거 모든 WAVE 코드를 WAVE/m으로 합치던 mapper를 제거했고 이미 저장된 legacy 행은 덮어쓰지 않는다. [코드 대응표](06_MDC_QUERY_MAPPING.md)를 따른다.

## 실행·재실행

설정 기본값은 `SOURCE_AUTO_MAPPING_ENABLED=false`다. 현재 검증 backend8010/개발 웹5174에서는 true로 실행했다. 기존 canonical8000/5173 환경파일은 수정하지 않았다. 실제 파일은 `SHARE_MONTHLY_LAKE_ROOT` 아래 3개 원천의 월별 `manifest.json`/`raw.parquet`를 사용하며 현재 source authority root인 `D:\AI_Observation` 안에 있어야 한다. DB URL·자격정보는 각 환경의 로컬 설정으로 관리한다.

backend 폴더에서 먼저 dry-run으로 전체 요청 파일의 SHA·행 수·매핑별 census·자연키 충돌을 검증한다. 다음 예제의 기간은 source-native KST이며 offset을 붙이지 않는다.

```powershell
python -m app.scripts.ingest_operational_parquet `
  --from-native 2026-07-08T15:41:20 --to-native 2026-07-09T15:41:20 `
  --receipt D:\AI_Observation\outputs\new-dry-run.json

$env:SOURCE_AUTO_MAPPING_ENABLED = 'true'
python -m app.scripts.ingest_operational_parquet `
  --from-native 2026-07-08T15:41:20 --to-native 2026-07-09T15:41:20 `
  --receipt D:\AI_Observation\outputs\new-apply.json `
  --apply --batch-size 2000 --register-source-identifiers
```

`--register-source-identifiers`는 누락된 정확한 코드 참조만 만들며 물리 시설 metadata를 확정하지 않는다. 이 옵션을 생략하면 미등록 관측소 행을 격리한다. 매핑 코드가 없거나 수치·수심·시계가 유효하지 않은 행은 별도 격리 건수와 이유로 남는다. `COMPLETE_WITH_QUARANTINE`을 전체 성공으로 표시하지 않는다.

CLI는 기본 dry-run이며 apply에는 명시한 LIVE 설정이 필요하다. 각 batch의 Raw·Standard·Binding은 같은 트랜잭션으로 commit한다. 중단 후 같은 기간을 **새 receipt 파일명**으로 재실행하면 이미 확인된 binding을 검증·재사용한다. 기존 숫자값이나 receipt가 달라진 자연키는 덮어쓰지 않는다. CLI 한 번의 receipt가 전체 적재를 단일 트랜잭션으로 보장하는 것은 아니다.

계약별 PostgreSQL advisory lock으로 중복 worker와 reviewer 철회를 직렬화한다. 철회된 계약은 다음 batch부터 거부하며 이미 저장된 행을 삭제하지 않는다. 원장·Binding은 현재 활성 데이터셋의 membership과 별도다. 파일 바이트 변경·ledger hash 불일치·철회·권한 부족은 차단한다.

## 화면·API

Data Lake 화면의 **운영 표준 매핑 · 자동 계약 및 Binding** 카드에 자동 계약 수, 등록 Binding, 변수별 실제 행 수, UTC 관측기간과 매핑 판본을 표시하고 30초마다 조회한다. 실패는 오류로 표시하며 0건으로 숨기지 않는다. 이 카드의 범위는 PostgreSQL에 등록된 자료이며 아래 Parquet 표본 선택의 source/month와 같은 집계가 아니다.

`GET /api/source-contracts/auto-mapping/status`는 읽기 전용이다. 계약 목록·상세·receipt는 SYSTEM_POLICY 범위를 구분하고 실제 파일/원장을 재검증한다. reviewer/admin은 예상 packet SHA로 REVOKED할 수 있으나 자동 정책을 사람의 전체 원천 승인으로 재승인하는 API는 없다. [API 문서](04_API_SPECIFICATION.md)를 따른다.

## 검증 기록

격리 backend 자동 매핑 시험 **19 passed**: exact literal·수층·clock·cutoff, unmapped 배제, 시스템 actor·범위, source-only 코드 참조, 멱등 replay, 파일 변조·철회·바뀐 기존 숫자 차단, API 조회와 reviewer 권한을 검증했다. source authority/snapshot·workflow·MDC를 포함한 관련 묶음은 최종 **143 passed / 0 failed**다. PostgreSQL 격리 schema에서는 실제 bulk insert·재실행·명시 UTC·원문 receipt·기존 값 변조 차단 5개 항목을 통과하고 schema를 제거했다.

Frontend 관련 시험 **11 passed**, TypeScript/Vite build 통과, lint 새 오류·새 경고 0이며 기존 경고 12개가 남아 있다. 실제 backend health/readiness/status API와 브라우저 카드의 최종 745,445행·3계약·관측기간도 확인했다. 최종 독립 검증은 **PASS**이며 전체 745,445행의 원본 Parquet literal 불일치는 **0건**이다. PostgreSQL 원장·수치·단위·시각·원문 QC join, source/item별 census, 3파일의 실제 SHA, 기존 행 보존과 dataset/model/Final QC 미생성을 함께 검증했다. 당시 DB 전체 Raw는 759,066행, Standard는 749,519행, 관측소 참조는 325개, sensor 참조는 834개다. 새 sensor 832개는 source-scoped logical channel이며 실제 설치 장비 개수와 다르다. 결과는 최종 독립 검증 receipt 및 [current_status.json](current_status.json)에 기록한다.

실제 원문·DB backup·행 literal export·승인 receipt는 GitHub에 올리지 않는다. 로컬 보존 폴더는 `D:\AI_Observation\outputs\source-auto-mapping-20261013`이며 주요 파일은 `before-ingest-state.json`, `dry-run.json`, `apply-run.json`, `apply-resumed.json`, `source-identifier-recovery.json`, `postgres-bulk-validation.json`, `actual-postgres-validation.json`이다. 최초 적재 중 bulk insertion 최적화를 위해 중단한 receipt와 이후 재개·격리 해소 receipt는 별도로 보존한다.
