# 기능 구현 실태 점검

점검일: 2026-09-16  
대상: `ocean-ai-platform/backend`, `ocean-ai-platform/frontend`

판정 기준은 이름·주석·모델 선언의 존재가 아니라, 실행 경로(API/작업/DB 저장)와 현재 PostgreSQL 데이터까지 확인하는 것이다.

## 종합 결과

| 항목 | 판정 | 실제 확인 내용 |
|---|---|---|
| 데이터 표준화 | 부분 구현 | `sync_mdc_db.py`에서 MDC 관측소 코드·좌표·상태·시각·값을 변환해 `station_metadata`, `observation_raw`에 적재한다. 중앙 단위 사전, 센서 표준화, 원본 행·배치 추적은 없다. `sensor_metadata` 현재 0건이다. |
| QC 이력 | 부분 구현 | `QCFlagHistory` 모델, 시드 스크립트, `/api/qc/summary`·`/api/qc/alerts` 조회는 있다. MDC 동기화/실제 QC 실행이 이 테이블에 기록하지 않으며 현재 DB 0건이다. |
| AI Label | 부분 구현 | `ai_flag_candidate`, `recommended_flag` 필드와 Copilot 추천 결과는 있다. 추천 라벨을 QC 이력에 저장·승인 후 확정하는 연결은 없다. 현재 `AIPredictionResult` 0건이다. |
| Feature 관리 | 이름만 존재 | `backend/app/ml/feature_generator.py`가 비어 있고 Feature 테이블·버전 API·등록/승인 흐름이 없다. |
| 문서 Embedding | 부분 구현 | PDF 로더, chunking, HuggingFace embedding, Chroma 저장 코드와 초기화 데이터가 있다. 문서 인덱스 DB(`DocumentIndex`)와 증분/중복 관리가 연결되지 않았고 현재 0건이다. |
| Hybrid Retrieval | 미구현 | RAG 경로는 Chroma 벡터 검색만 수행한다. SQL 질의는 intent 분류로 RAG와 분기할 뿐, 벡터·키워드·구조화 결과를 결합하는 hybrid rank/fusion은 없다. |
| QC Copilot | 부분 구현 | LangGraph가 DB의 하루 데이터를 읽고 이상 탐지·원인 진단·보고서 초안을 생성한다. 탐지 조건과 정확도는 random/mock 값이며 결과 영속화가 없다. |
| Human Approval | 부분 구현 | 보고서 draft/review/approve/reject/publish API는 있다. QC Copilot 결과의 승인 API는 없고 `AgentTaskApproval` 생성 코드도 라우터가 `main.py`에 등록되지 않았다. |
| 모델 Registry | 부분 구현 | `ModelRegistry` 모델과 `/api/mlops/summary` 조회가 있다. 현재 DB 0건이며 모델 등록·배포·승인 API는 없다. |
| Retraining History | 부분 구현 | `RetrainingHistory` 모델, 시드 데이터 코드, `/api/mlops/retrain-history` 조회가 있다. 실제 학습 실행/기록 생성 API가 없으며 프론트의 `POST /api/mlops/retrain`은 현재 404이다. |
| Dataset Version | 미구현 | Dataset/스냅샷/버전 모델, 저장소, API, UI 연결을 찾지 못했다. |
| Explainability | 부분 구현 | `AIPredictionResult.explanation`, QC Copilot의 LLM 설명 문구는 있다. SHAP/기여도/입력 특성·모델 버전·근거 데이터 추적은 없다. |
| API 완성도 | 부분 구현 | 주요 관측·QC·RAG·MLOps·보고서 API는 등록되어 있다. `routes_models`, `routes_approvals`, `routes_agents`, `routes_ai_insights`는 파일이 있어도 `main.py`에 등록되지 않았다. 일부 응답은 고정값/Mock이다. |
| Frontend-Backend 연결 상태 | 부분 연결 | 주요 화면의 조회 호출은 연결된다. MLOps 재학습 POST는 백엔드 라우트가 없고, Reports 승인 호출은 백엔드가 요구하는 `user_id` 요청 본문을 보내지 않아 422가 발생한다. API 기본 URL과 여러 화면이 `localhost:8080`에 하드코딩되어 배포 환경 설정도 없다. |

## 현재 DB 확인값

점검 시점의 PostgreSQL 건수는 `StationMetadata 323`, `ObservationRaw 15,875`, `SensorMetadata 0`, `QCFlagHistory 0`, `AIPredictionResult 0`, `DocumentIndex 0`, `ModelRegistry 0`, `RetrainingHistory 0`, `ApprovalHistory 0`, `AgentTaskApproval 0`, `ReportRegistry 0`이었다. 따라서 화면에 보이는 QC·AI·MLOps 수치는 일부가 시드/고정값이며, 현재 MDC 관측 적재와 직접 연결된 운영 이력으로 볼 수 없다.

## 우선 보완 순서

1. 표준 코드·단위·센서 기준정보와 `ingestion_batch_id`를 도입하고 `SensorMetadata`를 MDC와 연결한다.
2. 실제 QC 실행 결과와 AI 라벨을 `QCFlagHistory`/`AIPredictionResult`에 저장하고 자연키·버전을 부여한다.
3. Feature 정의·Dataset Version·모델 버전을 하나의 학습 스냅샷으로 묶는다.
4. 문서 인덱스와 Chroma 메타데이터를 배치 ID로 관리하고 벡터+키워드+SQL 결합 검색을 구현한다.
5. Copilot 결과에 승인 API와 감사 이력을 연결한다.
6. 누락 라우터를 등록하고 프론트의 재학습·보고서 승인 요청 계약을 API와 일치시킨다.
