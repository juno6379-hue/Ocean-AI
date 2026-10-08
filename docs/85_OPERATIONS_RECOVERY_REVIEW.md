# 85. 운영 준비·소규모 복구·문서 backlog 재개

기준일: 2026-10-08. [설치](02_SETUP_AND_INSTALLATION.md), [문서 적재](15_DOCUMENT_INDEX_INGESTION.md), [전체 개발 단계](README.md)를 함께 읽는다. 이 문서의 검증 결과는 운영 계정·원천·dataset·모델 승인을 생성하지 않는다.

## 재시작 전에 보존할 것

현재 API/worker 프로세스, 포트, 데이터 root, document contract SHA, embedding model digest·dimension·collection, 승인/정책/dataset snapshot 포인터, PostgreSQL schema/migration 판본, 큐 상태를 기록한다. 환경파일·token·DB 비밀번호는 검토 artifact에 복사하지 않는다. API `health`와 `readiness`는 프로세스/DB 연결이고 실제 모델 운영 완료를 뜻하지 않는다. 승인·training·registry·deployment 수치는 각각 읽기 전용 원장으로 확인한다.

[소규모 backup 서비스](../ocean-ai-platform/backend/app/services/operational_backup_review.py)는 명시한 manifest/policy/receipt/pointer/schema와 작은 SQLite queue만 복사한다. 일반 파일은 복사 전/후 원본 SHA와 대상 SHA를 비교한다. SQLite는 읽기 전용 연결의 `backup()`으로 transaction snapshot을 만들고 `integrity_check`를 검사한다. WAL가 있는 live SQLite의 `.sqlite3` 파일만 복사해서 일관된 큐라고 판단하지 않는다. 64 MiB 기본 상한, reparse 경로, `.env`와 비밀키 JSON, 비어 있지 않은 backup root를 거부한다.

Backend에서 별도 PowerShell로 실행한다. 경로는 실제 보존 위치를 명시한다.

```powershell
$backupRoot = Join-Path $env:TEMP ('ocean-review-backup-' + [guid]::NewGuid().ToString('N'))
$restoreRoot = Join-Path $env:TEMP ('ocean-review-restore-' + [guid]::NewGuid().ToString('N'))
python -B -m app.scripts.operational_state_backup `
  --backup $backupRoot --restore $restoreRoot `
  --source MANIFEST '<actual-document-contract.json>' `
  --source QUEUE_DB '<actual-worker-queue.sqlite3>' `
  --source SCHEMA '<reviewed-schema-and-counts.json>'
```

새 disposable 폴더에서 전 파일 SHA와 SQLite 무결성을 재검증한다. 원본 queue/schema/worker를 변경하거나 복구 폴더를 운영 경로로 전환하지 않는다. `sqlite_readonly_export()`는 schema와 count를 보존하고 실제 row payload를 담지 않는다. 이 export만으로 전체 PostgreSQL·원천·벡터·승인 원장이 복원되는 것은 아니다. 실제 재해복구 전에 현재 운영 snapshot과 일치하는 PostgreSQL dump를 격리 DB에 복구하고 FK/원장 row digest, 불변 dependency SHA, 큐 lease/replay, vector/SQL IDs, 원문 경로를 대조해야 한다. 소규모 서비스와 별도로 부모가10/8 전체 PostgreSQL snapshot dump→임시 DB restore를 실행했고48table count/schema/index/critical원장digest가 일치했다. 전 원문 row 개별재해싱·원천/벡터 전체재해복구를 뜻하지 않는다. [29](29_DEVELOPMENT_STAGE_EXECUTION.md).

## 기존 문서 원장의 읽기 전용 전수 검토

[backlog review CLI](../ocean-ai-platform/backend/app/scripts/review_document_backlog.py)는 production SQLite를 URI `mode=ro`와 `query_only`로 연다. 기존 `document_pipeline.status()`는 schema/WAL를 준비할 수 있으므로 이 전수 검토에서는 호출하지 않는다. `PENDING`과 `FAILED`의 모든 행을 각각 원본/별도 보존본 SHA·size, 실제 parser, 경고, exact content 중복으로 검사한다. 원본 경로를 이름이 비슷한 파일에 연결하지 않고 명시한 root-relative alias만 허용한다.

```powershell
python -B -m app.scripts.review_document_backlog `
  --ledger '<actual-ingestion.sqlite3>' --contract '<actual-contract.json>' `
  --output '<new-isolated-recovery-folder>' `
  --alias '<original-classified-root>' '<preserved-classified-root>' `
  --embed-documents 48 --embed-chunks 12000
```

암호화는 `OWNER_PASSWORD_REQUIRED`, 손상 stream은 `DAMAGED_SOURCE_REEXPORT_REQUIRED`, 불완전 PDF 글꼴은 `PDF_FONT_MAPPING_REVIEW_REQUIRED`로 남긴다. 본문 일부가 추출되었거나 코드상 예외가 없다는 이유만으로 전체 추출 성공이라고 표시하지 않는다. 해당 소유자가 제공하는 password/unprotected export, 온전한 재출력, 글꼴/OCR 검토가 각각 필요하다. 단위/센서/clock/원천 QC를 이 문서 처리로 승인하지 않는다.

현재 contract와 같은 로컬 Ollama 모델/digest/dimension만 사용하며 endpoint는 loopback HTTP로 제한한다. 모델 변경, 벡터 수·dimension·비유한 값 오류를 차단한다. 개발 vectors는 별도 SQLite collection에만 기록한다. `PARTIAL` 문서는 검색 대상에 들어가지 않고 정확 ordinal checkpoint로 재개한다. 완성 문서만 source hash·page·document 필터와 citation을 검사한다. Cosine은 검색 관련도이며 QC 확률이 아니다. Self-query/filter 검증만으로 전체 도메인 질의 품질을 검증했다고 주장하지 않는다.

## 검증된 batch를 기존 RAG에 게시하는 경로

[promotion CLI](../ocean-ai-platform/backend/app/scripts/promote_document_recovery.py)는 기본 dry-run이다. 복구 SQLite, 활성 contract, 현재 canonical backlog revision과 원본/보존본 SHA를 재검증하고 원래 pipeline과 동일한 document/chunk IDs를 동결한다.

```powershell
python -B -m app.scripts.promote_document_recovery `
  --plan '<new-promotion-plan.json>' --recovery '<isolated-recovery.sqlite3>' `
  --ledger '<actual-ingestion.sqlite3>' --contract '<actual-contract.json>'
# 같은 계획의 read-only 재검증
python -B -m app.scripts.promote_document_recovery --plan '<promotion-plan.json>'
```

실제 게시에는 별도 `--apply`와 서버가 등록한 operator/reviewer/admin bearer가 필요하다. bearer는 `OCEAN_RAG_PROMOTION_TOKEN` 프로세스 환경에서 받으며 출력하지 않는다. 이 키는 Settings `.env` 필드가 아니다. 실제 계정 설정은 사용자 지시에 따라 유예되어 있으며 검토 작업은 apply를 실행하지 않는다.

게시 경로는 기존 ingestion worker lock과 `process_file()`을 사용한다. 복구 batch의 불변 vectors만 재사용하고, SQL 공개 직전에 현재 source/contract SHA와 재파싱 chunk IDs를 다시 확인한다. 전체 문서의 SQL transaction이 성공한 뒤 canonical 파일 원장 상태를 갱신한다. checkpoint에는 operator/plan hash/원래 행과 새 chunk IDs를 보존한다. 다른 문서의 현재 원장 revision 변경은 stale로 거부하고 동일 계획의 재개·replay는 이미 게시된 행과 정확 source checksum을 검증한다.

게시 후에는 활성 SQL/Chroma ID 전수 일치와 새 document/page/scope 필터 검색을 검증해야 한다. Rollback은 게시 영수증의 새 IDs만 대상으로 삼으며, 원래 있던 chunks·원문·다른 batch·collection을 삭제하지 않는다. 서버 operator와 canonical run history에 묶인 exact receipt, SQL source checksum과 원장 postimage를 검증한 뒤 additive IDs만 비공개로 만들고 원래 파일 원장 행을 복원한다. Rollback 진행 상태는 별도 이력에 남겨 중단 후 재실행할 수 있다. 자동으로 전체 collection을 지우거나 다른 contract로 바꾸지 않는다. 실제 운영 apply/rollback은 아직 실행하지 않았고 격리 시험과 구분한다.

```powershell
# 실제 게시 영수증을 검토한 operator만 실행한다.
python -B -m app.scripts.promote_document_recovery `
  --plan '<promotion-plan.json>' --rollback-receipt '<publication-receipt.json>'
```

추가 개발 batch는 `python -B -m app.scripts.resume_document_recovery --output '<isolated-recovery-folder>' --contract '<actual-contract.json>' --documents 48 --chunks 6000`으로 이어간다. 전수 검토 membership과 현재 canonical backlog revision을 먼저 확인하고 완성된 SHA는 재선정하지 않는다. 선택한 원본 SHA·보존본 parser를 재검사한다. 이 과정도 canonical 원장·Chroma에 게시하지 않는다.

## 원천·기간·사건 검토를 함께 읽는 방법

[source preservation review](../ocean-ai-platform/backend/app/services/source_preservation_review.py)는 기존 copy/hash 원장·과거 재검사와 새 full-SHA 검사를 별도 시각/범위로 보고한다. 기존 1.89 TB 원장 수치를 현재 전 대상 재해시로 표시하지 않는다. Target에 추가된 facility review metadata는 manifest SHA/Parquet footer로 재확인하고 원복사 corpus와 분리한다.

7월 말 공백은 원천 파일의 native clock extent로만 기록한다. Source clock/schedule/센서 운영기간이 미확정이면 센서 장애·공식 수집률로 변환하지 않는다. 다른 source family의 후행 관측을 원래 source의 공백에 채우지 않는다. [사건 검토](../ocean-ai-platform/backend/app/services/event_case_review.py)는 시설 heading·일련번호·원문 record/date locator를 보존한다. 일련번호가 같아도 시설별 instrument 후보는 분리하며 DAY/보고서 기간을 임의 UTC episode로 만들지 않는다. 새 증거가 발견되어도 실제 owner 승인과 물리 identity·구간 경계가 확보될 때까지 사건/센서 승인 원장은 그대로 유지한다.
