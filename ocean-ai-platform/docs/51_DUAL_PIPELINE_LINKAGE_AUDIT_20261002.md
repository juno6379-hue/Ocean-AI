# 정형·비정형 파이프라인 및 사건 연결 점검

점검일: 2026-10-02. 활성 PostgreSQL 읽기 조회와 현재 작업 폴더의 코드를 기준으로 판단한다. 테스트 DB나 코드에 정의된 모델 개수를 실제 운영 처리 건수로 간주하지 않는다. 이번 점검에서는 신규 자료 적재 및 라벨 생성은 수행하지 않았다.

## 결론

요청한 두 파이프라인의 종단 간 연결은 미완료다. 일부 파서·표준화·임베딩 및 개별 API는 구현되어 있지만, 실제 보고서 → 사건 → 관측/QC → 승인 라벨 → Feature Store → Dataset의 추적 가능한 연결은 확인되지 않는다.

## 비정형 경로

| 단계 | 구현 및 실측 | 판정 |
|---|---|---|
| Report → Parser | embed_docs.py는 PDF/TXT/DOCX, semantic_ingestion.py는 PDF/TXT를 읽는다. 후자는 PDF 텍스트 레이어 추출 방식이다. | 일부 형식 처리 구현; 전체 형식·OCR 처리 완료 근거 없음 |
| Metadata Extraction | semantic_ingestion.build_metadata는 코드 정규식으로 관측소·변수를 추출한다. related_sensor_id, period_start/end, event_id를 채우지 않는다. document_date는 원문 날짜 대신 실행시각을 기록한다. | 부분 구현 |
| Semantic Chunk | 제목·관측소·페이지 경계 기반 함수가 있다. 기존 embed_docs.py는 1,000자/200자 중첩 분할이다. | 구현 경로와 기존 저장 경로가 다름 |
| Embedding → Vector DB | 같은 날 50번 점검에서 ocean_reports 1,786청크/178개 source, langchain 4청크/테스트 파일 1개 확인. | 일부 실제 저장 |
| DocumentIndex 연결 | 활성 PostgreSQL document_index 0행. Hybrid Retriever는 기본 langchain, 기존 보고서 검색 Agent는 ocean_reports 사용. | 미완료 |

단순 임베딩 존재는 보고서별 메타데이터·사건 연결이 완료되었다는 증거가 아니다. 이번 코드 점검에서 모델 이름·버전 필드를 기록하는 코드가 있더라도 실제 DB에 저장된 이력으로 취급하지 않았다.

## 정형 경로

| 단계 | 구현 및 실측 | 판정 |
|---|---|---|
| Raw CSV → Schema Profiling | profile_spool.py와 build_datalake.py가 있으나 관측 DB 표준화와 일괄 연결된 실행 증거는 없음. build_datalake.normalize 출력에는 sensor_id와 event_id가 없음. | 부분 구현 |
| Standardized Observation | observation_raw 13,621행, observation_standard 4,074행. MDC sync에서 항목 매핑·단위 변환 및 표준화 저장 코드 확인. | 일부 실제 적재; 전체 CSV 처리 완료는 아님 |
| QC Rule Result | qc_rule_definition 2행, qc_rule_result 0행. /api/qc/rules/execute는 표준화 관측에 결측·min/max 검사를 수행해 개별 결과를 저장하는 코드가 있음. | API 구현, 실제 결과 없음 |
| Operation/Event Link | operation_log 0행, event_registry 0행. Event 생성/조회/상태 변경 API는 있으나 문서·QC·운영이력 관계를 생성하지 않음. | 연결 미완료 |
| AI Label | 별도 ai_label 모델 및 등록·승인 API 존재. ai_label 0행. | 구조 분리 구현, 실제 라벨 없음 |
| Feature Store | feature_definition 9행, feature_value 0행. feature_generator는 지연값·이동통계 DataFrame을 생성하지만 이를 FeatureValue로 저장하는 연결은 확인되지 않음. | 정의·API·계산 일부 구현, 저장 흐름 미완료 |
| Dataset Registry | dataset_registry 0행. 등록/build/validate 등 API 있음. _dataset_content는 ObservationStandard와 검토자 기록이 있는 QCFlagHistory로 snapshot을 만들며 AILabel/FeatureValue를 읽지 않음. | 요청한 라벨·Feature 계보 연결 미완료 |

표의 행 수는 조회 시점의 상태이며 생성 경로나 품질 적합성을 보증하지 않는다.

## station_id + sensor_id + time + event_id 연결

- ObservationStandard와 QCRuleResult에는 관측소·센서·시각이 있다. DB에서 QCRuleResult.observation_id → ObservationStandard.observation_id 외래키는 확인됐다.
- DocumentIndex에는 related_station_id, related_sensor_id, period_start/end, event_id 필드가 있지만 데이터가 없고 현 ingestion 코드가 센서·기간·event_id를 채우지 않는다.
- EventRegistry에 사건 ID·관측소·센서·기간은 있으나 현재 0행이다. 사건을 관측·QC·운영이력·라벨에 배정하는 자동 연결 경로는 확인되지 않는다.
- AILabel, OperationLog, FeatureValue에는 event_id 필드가 없다. 별도 관계 테이블을 통한 연결도 이번 점검에서 확인되지 않았다.
- 따라서 네 기준으로 문서와 관측을 연결한 실제 레코드나 종단 간 검증 성공 사례는 없다.

## 완성에 필요한 순서와 검증 기준

1. 연결 규약: station_id·sensor_id·variable_code 기준정보, UTC, 사건의 시작/종료 시각 및 중첩 판정 규칙을 확정한다. 보고서 발행일을 사건 발생시각으로 대체하지 않는다.
2. 문서: 원문 날짜·관측소·장비·변수·오류기간을 추출한다. 해석 불가능한 센서·시각은 미확정 상태로 남기고 검토 대상으로 관리한다. source_id/checksum, parser/chunk/embedding 버전을 보존한다.
3. 사건: EventRegistry와 문서·관측·QC·OperationLog·AILabel 관계 테이블을 통해 다대다 관계를 보존한다. 네 필드를 모든 데이터의 단일 복합 기본키로 강제하지 않는다.
4. 정형: 검증된 CSV 스키마에서 Standard Observation을 생성하고 센서·변수·시각을 보존해 QC 결과를 적재한다.
5. 라벨: QC 결과와 문서/운영 근거로 검토 대상 AILabel을 생성한다. QC Flag를 자동으로 학습 라벨로 확정하지 않는다.
6. Feature/Dataset: 승인 라벨 및 버전별 FeatureValue를 실제 학습 snapshot에 포함하고 원천 관측·QC·사건·문서까지 추적 가능하게 만든다.
7. 실자료 종단 검증: 한 사건에 대해 문서 chunk → event → observation → QC → 승인 label → feature → dataset member를 양방향 조회하고, 재실행 중복·시간대·미확정 매핑·정보 누수를 검증한다. 그 후 전체 자료군으로 확대한다.

## 주요 코드 근거

- backend/app/rag/semantic_ingestion.py
- backend/app/scripts/embed_docs.py
- backend/app/rag/hybrid_retriever.py
- backend/app/scripts/build_datalake.py
- backend/app/scripts/sync_mdc_db.py
- backend/app/api/routes_qc.py
- backend/app/api/routes_events.py
- backend/app/api/routes_features.py
- backend/app/api/routes_datasets.py
- backend/app/api/routes_approvals.py
- backend/app/models/domain.py
