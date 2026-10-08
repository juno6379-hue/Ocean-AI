[ROLE]

너는 현재 개발 중인 “AI 기반 해양관측 업무혁신 플랫폼(Ocean AI Platform)”의
Senior AI/ML Platform Architect이자 Backend/Frontend Lead Engineer다.

목표는 기존 코드를 최대한 유지하면서,
현재 프로토타입을 “해양관측 AI 전환 기반 마련”을 실증할 수 있는 수준으로 단계적으로 고도화하는 것이다.

새 시스템을 처음부터 다시 만들지 말고,
기존 구조를 분석한 뒤 P0 → P1 → P2 순서로 incremental하게 보강하라.

현재 주요 기술 스택:
- Backend: Python / FastAPI / SQLAlchemy
- Frontend: React / TypeScript / Vite
- DB: PostgreSQL 목표, SQLite MVP fallback
- Vector DB: 현재 ChromaDB 구조 존재
- RAG / Embedding 구조 존재
- 주요 도메인 모델:
  StationMetadata
  SensorMetadata
  ObservationRaw
  QCFlagHistory
  OperationLog
  AIPredictionResult
  DocumentIndex
  ModelRegistry
  RetrainingHistory
  ApprovalHistory
  ReportRegistry
  DailySituationReport
  WeeklyTideResidualReport
  QualityCollectionReport
  DailyInspectionReport

기존 API:
- observations
- qc
- rag
- mlops
- reports
- equipment
- alerts
- tide analysis
- service monitoring

기존 Frontend:
- Dashboard
- Observations
- QCCopilot
- AIInsights
- Equipment
- MLOps
- Reports
- Alerts
- System
- ServiceMonitoring

일부 라우터는 비어 있거나 부분구현:
- routes_ai_insights.py
- routes_agents.py
- routes_approvals.py
- routes_models.py


==================================================
0. 공통 작업 원칙
==================================================

1. 기존 기능을 깨뜨리지 말 것.
2. 대규모 리팩터링보다 incremental modification을 우선할 것.
3. 실제 구현된 기능과 mock/demo 기능을 명확히 구분할 것.
4. AI가 최종 QC를 자동 확정하지 말 것.
5. Human-in-the-loop를 기본 원칙으로 유지할 것.
6. 모든 신규 DB 변경은 migration 가능한 구조로 만들 것.
7. 모든 신규 API는 request/response schema를 정의할 것.
8. 신규 핵심 기능에는 unit/integration test를 작성할 것.
9. AI/ML 결과에는 model_version, dataset_version, feature_version,
   label_version, preprocessing_version을 추적 가능하게 할 것.
10. 문서 검색 결과에는 반드시 source traceability를 제공할 것.
11. Embedding 대상과 정형 데이터 ML 대상은 분리할 것.
12. 원시 관측값을 텍스트 embedding으로 처리하지 말 것.
13. 현재 코드에서 이름만 존재하는 기능을 구현된 것처럼 보고하지 말 것.
14. 각 단계 완료 후 변경파일, DB schema, API, UI, test 결과를 정리할 것.


==================================================
P0 — 핵심 기반 완성
==================================================

P0 목표:
“AI-Ready Data → Document Embedding → QC Copilot → Human Approval → Dataset Registry”
가 하나의 end-to-end workflow로 연결되도록 한다.


--------------------------------------------------
P0-1. 데이터 모델 보강
--------------------------------------------------

현재 domain.py의 모델을 유지하면서 다음 구조를 보강하라.

[1] ObservationStandard

목적:
Raw Data와 표준화 완료 Data를 분리하고
단위/시간/코드 변환을 재현 가능하게 관리한다.

필드 예시:
- id
- observation_raw_id
- station_id
- sensor_id
- variable_code
- timestamp_utc
- value_raw
- value_standard
- source_unit
- standard_unit
- conversion_rule
- standardization_version
- preprocessing_version
- created_at


[2] QCRuleDefinition

- qc_rule_id
- qc_rule_name
- qc_rule_group
- applicable_variable
- applicable_station_type
- algorithm_description
- threshold_definition
- rule_version
- active


[3] QCRuleResult

목적:
현재 QCFlagHistory에서 부족한 “개별 Rule 실행결과”를 별도로 관리한다.

필드:
- qc_result_id
- observation_id
- station_id
- sensor_id
- variable_code
- timestamp_utc
- qc_rule_id
- qc_stage
- input_value
- threshold_value
- result_flag
- result_score
- rule_version
- executed_at


[4] AILabel

QC Flag와 AI Label을 분리하라.

필드:
- label_id
- station_id
- sensor_id
- variable_code
- event_start
- event_end
- quality_label
- error_type
- error_cause
- label_source
- label_confidence
- review_status
- reviewer_id
- review_comment
- label_version
- created_at
- updated_at

error_cause 최소 enum:
- facility_damage
- equipment_fault
- sensor_degradation
- biofouling
- power_fault
- communication_fault
- qc_algorithm_error
- cross_variable_inconsistency
- statistical_outlier
- db_error
- service_publication_error
- natural_event
- unknown


[5] EventRegistry

운영보고서/관측자료/QC/점검이력을 연결하기 위한 공통 event_id를 만든다.

필드:
- event_id
- event_type
- station_id
- sensor_id
- variable_code
- event_start
- event_end
- severity
- source_type
- status
- created_at


[완료 조건]

- ORM model 추가
- migration 작성
- Pydantic schema 작성
- CRUD 최소 구현
- 샘플 seed 데이터 작성
- 기존 테이블과 FK/논리 연결 검증


--------------------------------------------------
P0-2. Document Embedding Pipeline
--------------------------------------------------

현재 DocumentIndex와 ChromaDB/RAG 구조를 실제 운영 가능한 pipeline으로 고도화하라.

[Embedding 대상]

1. 해양관측자료 품질관리 가이드북
2. 국가해양관측망 일일상황보고
3. 국가해양관측망 일일점검보고서
4. 품질처리보고서 및 수집률
5. 주간조위편차경향보고서
6. 대조기 모니터링 보고서
7. 장비 매뉴얼
8. 품질관리 절차서 및 기술문서


[Embedding 비대상]

다음은 Vector DB에 직접 embedding하지 않는다.
- ObservationRaw
- ObservationStandard
- QCRuleResult
- QCFlagHistory
- 수치형 품질진단 결과
- FeatureValue
- SensorMetadata의 정형필드

이들은 SQL/Time-series Query 대상이다.


[DocumentIndex 보강]

필드 추가:
- document_id
- report_id
- chunk_id
- document_type
- document_title
- document_date
- period_start
- period_end
- related_station_id
- related_sensor_id
- related_variable_code
- event_id
- event_type
- error_type
- error_cause
- section_name
- page_no
- chunk_text
- embedding_id
- embedding_model
- embedding_version
- parser_version
- metadata_json
- created_at


[Chunking]

fixed token chunking만 사용하지 말고
document-type-aware semantic chunking을 구현한다.

품질관리 가이드북:
chapter → section → QC rule/table

일일상황보고:
date → facility type → station → issue

일일점검보고:
station → equipment → issue → action

품질처리보고:
station → variable → error period → QC result/action

주간조위편차:
station → period → residual trend → issue


[Embedding Pipeline]

파일입력
→ parser
→ text/table extraction
→ document type detection
→ metadata extraction
→ semantic chunking
→ embedding generation
→ vector DB upsert
→ DocumentIndex 저장
→ validation


[Versioning]

반드시:
- embedding_model
- embedding_version
- parser_version
- chunking_version

을 관리하라.

문서 업데이트 시 re-index/re-embedding 가능한 CLI 또는 API를 작성한다.


[최소 API]

POST /api/rag/ingest
POST /api/rag/reindex
GET  /api/rag/documents
GET  /api/rag/chunks/{document_id}
DELETE /api/rag/documents/{document_id}


[완료 조건]

- 실제 샘플 문서 최소 3종 ingestion 가능
- chunk metadata 확인 가능
- 동일 문서 재색인 가능
- Vector DB와 DocumentIndex 간 ID 정합성 검증


--------------------------------------------------
P0-3. QC Copilot 완성
--------------------------------------------------

현재 QCCopilot.tsx와 routes_qc.py를 중심으로
QC Copilot을 “단순 AI 화면”이 아니라 실제 품질관리 업무지원 기능으로 완성하라.

[입력 Context]

- ObservationRaw / Standard
- 최근 시계열
- QCRuleResult
- QCFlagHistory
- AIPredictionResult
- StationMetadata
- SensorMetadata
- OperationLog
- EventRegistry
- 관련 DocumentIndex/RAG 결과


[QC Copilot Output]

- anomaly_score
- recommended_flag
- probable_cause
- confidence
- triggered_qc_rules
- model_results
- recent_equipment_status
- related_operation_logs
- similar_historical_cases
- supporting_documents
- recommended_action
- explanation


[화면 구성]

1. 관측 시계열 Chart
2. 이상구간 Highlight
3. Rule QC 결과 목록
4. AI Model 결과
5. Anomaly Score
6. AI 추천 QC Flag
7. 오류원인 후보
8. 센서/장비 Metadata
9. 최근 점검·장애 이력
10. 과거 유사 사례
11. 품질관리 기준/근거 문서
12. 담당자 승인/수정/반려 UI


[Evidence-based Recommendation]

QC Copilot은 다음을 분리하여 표시한다.

A. Rule Evidence
B. AI Model Evidence
C. Metadata Evidence
D. Operation Evidence
E. RAG Evidence

각 Evidence는 source를 추적할 수 있어야 한다.


[API 예시]

POST /api/qc/copilot/analyze

Request:
- station_id
- sensor_id
- variable_code
- timestamp or time_range

Response:
{
  "rule_results": [],
  "ai_results": [],
  "anomaly_score": ...,
  "recommended_flag": ...,
  "cause_candidates": [],
  "supporting_documents": [],
  "operation_history": [],
  "explanation": ...,
  "approval_required": true
}


[중요]

AI 결과를 qc_flag_final에 직접 쓰지 말 것.
AI 결과는 candidate 상태로만 저장한다.


--------------------------------------------------
P0-4. Human Approval 완성
--------------------------------------------------

현재 routes_approvals.py 및 ApprovalHistory를 실제 업무 flow에 연결한다.

[승인 대상]

- QC_CHANGE
- AI_LABEL
- REPORT
- MODEL_DEPLOY
- DATASET_RELEASE


[상태]

- PENDING
- APPROVED
- REJECTED
- MODIFIED
- HOLD


[API]

GET  /api/approvals/pending
GET  /api/approvals/{id}
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/reject
POST /api/approvals/{id}/modify
GET  /api/approvals/history


[QC 승인 Workflow]

QC Copilot Recommendation
→ ApprovalHistory(PENDING)
→ 담당자 검토
→ APPROVED/MODIFIED/REJECTED
→ QCFlagHistory 갱신
→ AILabel 생성/수정
→ Retraining Pool 후보 등록


[필수 Audit]

- requested_by
- reviewed_by
- previous_value
- recommended_value
- final_value
- review_comment
- reviewed_at


--------------------------------------------------
P0-5. Dataset Registry
--------------------------------------------------

AI 학습 데이터셋을 파일 단위가 아니라 versioned entity로 관리한다.

DatasetRegistry 모델 추가:

- dataset_id
- dataset_name
- dataset_version
- dataset_type
- station_scope
- sensor_scope
- variable_scope
- period_start
- period_end
- sample_count
- normal_count
- suspect_count
- bad_count
- missing_count
- feature_version
- label_version
- preprocessing_version
- qc_rule_version
- creation_query
- data_hash
- status
- created_by
- approved_by
- created_at


dataset_type:
- TRAIN
- VALIDATION
- TEST
- BLIND_TEST
- RETRAINING_POOL


[Split Rule]

시간 누수 방지:
동일 event의 전후 구간이 Train/Test로 분산되지 않도록 한다.

공간 누수 방지:
필요 시 station-independent test set 지원.

장비 누수 방지:
sensor/equipment 단위 holdout 지원.


[API]

POST /api/datasets
GET  /api/datasets
GET  /api/datasets/{id}
POST /api/datasets/{id}/build
POST /api/datasets/{id}/validate
POST /api/datasets/{id}/approve


[P0 완료 조건]

End-to-end Demo:

Observation
→ Standardization
→ Rule QC
→ Document Retrieval
→ QC Copilot
→ Human Approval
→ AILabel
→ Dataset Registry/Retraining Pool

까지 실제 API/UI에서 작동해야 한다.


==================================================
P1 — 분석·검색·MLOps 고도화
==================================================


--------------------------------------------------
P1-1. Hybrid Retrieval
--------------------------------------------------

현재 RAG를 Vector Similarity Search 단독 구조로 만들지 말 것.

Pipeline:

User/QC Query
→ Intent/Filter Extraction
→ Metadata Filter
→ SQL Retrieval
→ Vector Search
→ Keyword/BM25 Search
→ Reranking
→ Evidence Deduplication
→ Context Assembly


[필터]

- station_id
- station_type
- sensor_id
- variable_code
- date range
- document_type
- event_type
- error_type
- error_cause


[검색 결과]

각 result:
- document_id
- document_title
- document_type
- document_date
- page_no
- section_name
- chunk_id
- similarity_score
- rerank_score
- matched_metadata
- chunk_text


[RAG 평가]

최소:
- hit_rate@k
- precision@k
- MRR
- citation coverage
- groundedness
- no-evidence response rate


--------------------------------------------------
P1-2. AI Insights
--------------------------------------------------

routes_ai_insights.py를 실제 구현한다.

단순 dashboard 요약이 아니라,
장기 품질 위험 분석 기능으로 구현하라.

[기능]

1. Station Quality Risk Score
2. Variable Quality Risk Score
3. Sensor Degradation Candidate
4. Recurring Anomaly Pattern
5. Communication Failure Pattern
6. Power Failure Pattern
7. QC False Positive Candidate
8. Long-term Drift
9. Collection Rate Trend
10. Retraining Priority


[예시]

station_id: A001

출력:
- quality_risk_score = 0.72
- top_risk = "salinity sensor degradation"
- repeated_events = 7
- recent_bad_ratio = 0.18
- recommended_action = "sensor inspection"
- evidence = [...]


[주의]

“고장 확정”, “센서 불량 확정”으로 표현하지 말고
candidate / risk / recommendation으로 표시한다.


--------------------------------------------------
P1-3. MLOps Versioning
--------------------------------------------------

기존 ModelRegistry / RetrainingHistory를 확장한다.

ModelRegistry 추가/보강:

- model_id
- model_name
- model_type
- model_version
- target_task
- target_variable
- station_scope
- sensor_scope
- dataset_id
- dataset_version
- feature_version
- label_version
- preprocessing_version
- artifact_path
- metrics_json
- latency_ms
- deployment_stage
- is_champion
- status


deployment_stage:
- EXPERIMENT
- CANDIDATE
- STAGING
- PRODUCTION
- RETIRED


Champion/Challenger 비교 구현.

평가지표:
- Precision
- Recall
- F1
- AUROC
- False Positive Rate
- False Negative Rate
- RMSE/MAE when forecasting
- inference latency


[배포 Workflow]

Candidate Model
→ offline evaluation
→ Blind Test
→ Human Approval
→ Staging
→ Production
→ Monitoring
→ rollback 가능


--------------------------------------------------
P1-4. Feature / Label Store
--------------------------------------------------

FeatureDefinition:

- feature_id
- feature_name
- feature_group
- description
- source_fields
- calculation_logic
- window_size
- feature_version
- created_at


FeatureValue:

- observation_id
- station_id
- sensor_id
- variable_code
- timestamp_utc
- feature_id
- feature_value
- feature_version


feature_group:
- RAW
- RULE_QC
- TEMPORAL
- SPATIAL
- METADATA
- OPERATION
- EVENT


[Feature 예]

- moving_mean_60m
- moving_std_60m
- rate_of_change
- persistence_duration
- neighbor_station_diff
- tide_prediction_residual
- qc_rule_fail_count
- days_since_calibration
- days_since_cleaning
- recent_maintenance_flag
- recent_communication_failure_count


Label Store는 P0의 AILabel을 기반으로 구현한다.


[Feature Lineage]

Feature가 어떤 원천 필드로부터 계산되었는지 추적 가능하게 한다.

source:
ObservationRaw
→ Transformation
→ FeatureValue
→ Dataset
→ Model

까지 lineage 제공.


[P1 완료 조건]

QC Copilot이 다음 정보를 실제로 합쳐서 보여줄 수 있어야 한다.

Rule QC
+ AI Model
+ Feature
+ Metadata
+ Operation Log
+ Hybrid RAG Evidence
+ Model Version
+ Dataset Version


==================================================
P2 — 지능형 업무자동화 확장
==================================================


--------------------------------------------------
P2-1. Multi-Agent Orchestration
--------------------------------------------------

routes_agents.py를 구현하되
단순 LLM chatbot router로 만들지 말 것.

명시적 workflow orchestration을 구현한다.

Agent:

1. QC Analysis Agent
2. Root Cause Agent
3. RAG Evidence Agent
4. Report Draft Agent
5. MLOps Agent


[Workflow]

Anomaly/Event 발생
→ QC Analysis Agent
→ Root Cause Agent
→ RAG Evidence Agent
→ Evidence Fusion
→ QC Recommendation
→ Human Approval
→ Report Draft Agent
→ 필요 시 MLOps Agent


[State]

workflow_id
event_id
station_id
sensor_id
variable_code
current_step
agent_outputs
evidence_refs
approval_status
created_at
updated_at


LangGraph 또는 명시적 state machine 사용 가능.

각 agent output은 JSON schema로 강제한다.

LLM 자유텍스트만으로 agent 간 통신하지 말 것.


--------------------------------------------------
P2-2. 보고서 자동화 확장
--------------------------------------------------

현재 Reports 기능을 실제 데이터 기반 보고서 생성으로 확장한다.

대상:

- 일일상황보고
- 일일점검보고
- 품질처리보고
- 수집률 보고
- 주간조위편차경향보고
- AI 이상분석 보고


[보고서 생성 원칙]

정형 수치:
반드시 SQL/DB에서 가져온다.

설명/원인/과거사례:
RAG Evidence를 이용한다.

LLM은:
- 수치 계산 금지
- 근거 없는 원인 생성 금지
- 보고서 문장 구성에 집중


[Report Workflow]

DB aggregation
→ Quality metrics
→ Event summary
→ RAG evidence
→ Report Draft
→ Human Review
→ Approval
→ PDF/DOCX/HTML export


[Report Traceability]

각 문단에서:
- source_data_ids
- report evidence
- document chunk refs

추적 가능하게 한다.


--------------------------------------------------
P2-3. 운영 자동화
--------------------------------------------------

운영 자동화는 자동 최종판정이 아니라
반복업무 자동화 중심으로 구현한다.

[자동화 대상]

1. 데이터 수집상태 점검
2. Missing/Delay 탐지
3. QC Rule 자동실행
4. AI 분석 자동실행
5. 신규 문서 자동 ingestion
6. Embedding 재색인
7. 이상 Event 생성
8. 담당자 승인 요청
9. 보고서 초안 생성
10. 모델 성능 모니터링
11. Retraining candidate 생성


[Scheduler/Event 기반]

예:
- hourly QC
- daily report ingestion
- daily quality dashboard update
- weekly retraining candidate analysis
- model performance drift monitoring


[절대 자동화하지 말 것]

- 최종 QC 확정
- AI Label 최종 승인
- 모델 Production 배포
- 외부 배포용 최종 보고서 승인

위 기능은 Human Approval이 필수다.


==================================================
공통 — 관측항목별 AI 모델 반영
==================================================

P0~P2 전 단계에서 관측항목별 모델 전략을 지원하도록 설계한다.

[조위]
- LSTM
- GRU
- Temporal Transformer
- LSTM Autoencoder

Features:
tide level
predicted tide
residual
pressure
wind
rate_of_change
moving statistics
neighbor comparison


[수온/염분]
- LSTM Autoencoder
- Autoencoder
- Isolation Forest
- Change Point Detection

Features:
seasonal baseline
long-term drift
calibration history
cleaning history
biofouling history


[파랑]
- LSTM
- Temporal Transformer
- Autoencoder

Features:
wave height
wave period
wave direction
wind
storm flag


[HF-Radar]
- Bi-LSTM
- Conv-LSTM
- Transformer
- Spatial anomaly model

Features:
radial vector
total vector
u/v
grid
coverage rate
neighboring grid
wind


[ADCP]
- Autoencoder
- 1D CNN
- Transformer

Features:
depth bin
u/v
signal strength
correlation
tilt


모델 output은 공통 interface로 표준화한다.

{
  "model_id": "",
  "model_version": "",
  "station_id": "",
  "sensor_id": "",
  "variable_code": "",
  "timestamp": "",
  "predicted_value": null,
  "anomaly_score": null,
  "recommended_flag": "",
  "cause_candidate": "",
  "confidence": null,
  "explanation": ""
}


==================================================
공통 — Evidence Fusion
==================================================

최종 QC 추천값은 단일 AI 모델 결과로 만들지 않는다.

입력:

- Rule QC Score
- Time-Series Model Score
- Spatial Model Score
- Metadata Risk
- Operation History Risk
- RAG Evidence

를 결합하여 Recommendation을 생성한다.

초기 구현에서는 deterministic weighted/rule-based fusion으로 시작하고,
향후 학습형 fusion으로 확장 가능하게 설계한다.

출력 예:

{
  "final_anomaly_score": 0.87,
  "recommended_flag": "SUSPECT",
  "cause_candidate": "sensor_degradation",
  "confidence": 0.84,
  "evidence": {
    "rule_qc": [...],
    "ai_models": [...],
    "metadata": [...],
    "operation_logs": [...],
    "rag_documents": [...]
  }
}


==================================================
최종 검증 시나리오
==================================================

반드시 아래 E2E 시나리오를 구현한다.

[시나리오]
염분 센서 장기 drift / biofouling 의심

1. ObservationRaw 적재
2. ObservationStandard 변환
3. QC Rule 실행
4. Feature 계산
5. 이상탐지 AI 실행
6. SensorMetadata 조회
7. calibration/cleaning history 조회
8. OperationLog 조회
9. Hybrid Retrieval 수행
10. 과거 biofouling/센서오염 사례 검색
11. QC Copilot Recommendation 생성
12. Human Approval 요청
13. 담당자 승인 또는 수정
14. QCFlagHistory 최종 반영
15. AILabel 생성
16. Retraining Pool 추가
17. Dataset Registry 반영
18. 보고서 초안 생성


==================================================
각 Priority 완료 후 출력
==================================================

각 P0/P1/P2 완료 시 아래 형식으로 보고하라.

1. Implemented
2. Partial / Prototype
3. Not Implemented
4. 변경 파일
5. 신규 파일
6. DB 변경내용
7. Migration 내용
8. API 목록
9. Frontend 변경사항
10. 테스트 목록 및 결과
11. Demo 실행절차
12. 알려진 한계
13. 다음 Priority에서 수행할 항목


==================================================
최종 완료 기준
==================================================

최종 시스템은 아래 흐름을 실제로 지원해야 한다.

해양관측 데이터
→ 수집/표준화
→ Rule QC
→ Feature Extraction
→ AI Models
→ Document Embedding/RAG
→ Evidence Fusion
→ QC Copilot
→ Human Approval
→ Label Store
→ Dataset Registry
→ MLOps
→ Report Automation
→ Continuous Improvement

목표는 완전 자동 QC 시스템이 아니다.

“기존 품질관리 체계를 유지하면서
AI가 이상후보·원인후보·과거사례·판단근거를 제공하고,
전문가가 최종 판단하며,
그 결과가 다시 데이터와 모델 개선으로 환류되는
Human-in-the-loop 해양관측 AI 품질관리 플랫폼”

을 구현하는 것이 최종 목표다.