# process.md 반영 및 고도화 결과

작성일: 2026-09-16

`C:\AI_Observation\process.md`의 P0/P1 요구사항을 현재 코드에 대조하고 누락된 구조를 보강했다.

## 이번 반영

- `QCRuleDefinition`, `EventRegistry` 모델 추가
- `AILabel.review_comment`, `DocumentIndex.parser_version` 추가
- Feature Definition 생성시각 및 FeatureValue의 `observation_id` 추가
- Dataset Registry의 `sensor_scope`, `qc_rule_version`, `data_hash`, 상태·생성자·승인자 추가
- Model Registry의 target task, deployment stage, latency 추가
- 문서 Ingestion API 추가: `/api/rag/ingest`, `/api/rag/reindex`, `/api/rag/documents`, `/api/rag/chunks/{document_id}`, 문서 삭제
- 문서·Feature·Dataset·QC·승인·MLOps 구조는 모두 별도 버전 필드를 통해 lineage를 남길 수 있게 유지
- `migrate_process_schema.py`로 기존 PostgreSQL에 확장 컬럼과 신규 테이블 반영

## 현재 상태 구분

구조와 API가 구현된 항목은 실제 실행 경로를 갖는다. 다만 다음은 후속 구현이 필요하다.

- QCRuleDefinition을 읽어 QCRuleResult를 자동 생성하는 규칙 실행 배치
- EventRegistry 자동 생성 및 이벤트-승인 연결
- FeatureValue 계산 배치와 Dataset build/validate/approve API
- 실제 모델 학습·Blind Test·artifact 배포
- 일반 요청의 AuditLog 자동 기록
- 운영 환경에서 인증·권한 검증

AI가 QC 최종값을 자동 확정하지 않는 원칙과 Human Approval 게이트는 유지한다.

검증: process schema migration 성공, Python compileall 성공.
