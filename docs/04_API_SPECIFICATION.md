# 04. API 명세

7월 현황 확장: `/api/lake/summary`, `/monitoring`, `/daily-reports`, `/equipment-evidence`, `/stations/{station}`의 기본 월은2026-07이다. `/api/lake/publication-comparison`은 기준월과 원천별 동결 검증 결과·명시적 예외를 제공한다. `/api/stations`와 `/api/stations/catalog/classifications`의 선택 `as_of_month=2026-07`은 승인과 별개인 읽기 전용 문서 참조다. [검증범위·checksum·STALE응답](27_JULY_REPORT_PARQUET_MATCH.md)을 확인한다.

기준일: 2026-10-08. 아래 목록은 읽기 전용 `/openapi.json`의 **154 경로·163 HTTP operation**을 게시된 router/prefix AST와 대조한 것이다. 모든 등록 경로를 포함한다. 코드 기준은 [main.py](../ocean-ai-platform/backend/app/main.py)와 각 행의 router 링크다. 서버가 제공하는 `/docs`와 `/openapi.json`에서 세부 query 타입·enum·response schema를 확인한다. 최신 검증 API 주소는 `http://127.0.0.1:8010`이며 기존 canonical8000을 유지한다.

`GET /api/lake/metric-completion`의 원천·월·관측소·항목·시설·해역 진단과 `GET /api/service-monitoring/overview`의 현재 프로세스 HTTP 집계는 [지표28](28_METRIC_COMPLETION.md)을 따른다. 지표 checksum·월 불일치는409, 손상503, snapshot변경은STALE/null이며 선택 기간 밖 값은 사용하지 않는다.

## 인증·오류·운영 경계

[security.py](../ocean-ai-platform/backend/app/core/security.py)는 일반 쓰기 요청에 bearer Actor의 operator/reviewer/admin 권한을 요구한다. 승인·검토·발행 등 reviewer dependency가 있는 경로는 reviewer/admin만 허용한다. 요청 body의 `user_id`는 서버 인증 Actor를 대신하지 않는다. GET은 대체로 공개 조회이나 `/api/session`은 인증을 요구한다. `GET /api/integrations`와 `POST /api/integrations/{source_id}/test`는 별도의 administrator dependency로 admin만 허용한다. SourceContract GET은 공개 조회이며 serving은 loopback을 요구한다.

분석 POST인 `/api/rag/chat`, `/api/rag/hybrid-search`, `/api/qc/copilot/analyze`, `/api/forecasting/baseline`, `/api/qc/rules/evaluate`, `/api/agents/evidence/analyze`, loopback `/api/anomaly-analysis/fit`·`analyze`는 일반 쓰기 인증 예외다. 실제 계정 설정은 업무 수행 시점으로 유예한다. `/api/agents/workflow`도 분석 예외지만 demo 전용이다. `/api/qc/run-copilot`, `/api/qc/ai-insights-summary`, `/api/test-auto/run`, `/api/agents/workflow`는 live에서 409로 막힌다. 이 경로를 실제 승인·학습 자동화로 사용하지 않는다.

| 응답 | 의미 |
|---|---|
| 401 / 403 | token 부재·불일치 또는 역할 부족 |
| 404 | 해당 대상·근거·dataset 없음 |
| 409 | 상태·hash·원천/승인 무결성·demo 경계 등 충돌. route별 `detail`을 확인한다. |
| 422 | 필수 입력/형식 또는 dependency/protocol 검증 실패 |
| 503 | 인증 Actor 미설정, DB readiness 실패 또는 packet 무결성 실패 등 |
| 500 | 처리 실패. 빈 목록·mock 성공으로 취급하지 않는다. |

2026-10-08 13:09 KST의 운영 `API_IDENTITIES`는 비어 있어 쓰기·승인은 아직 사용할 수 없다. Source/approval/dataset/model/event 계보 table은 0이다. `/api/mlops/readiness`는 BLOCKED, worker는 빈 큐 대기, `/api/mlops/serving/health`는 활성 모델이 없어 409다. `mdc_sensor_catalog` table은 미생성이므로 관련 API 정의가 운영 적재 완료를 뜻하지 않는다.

## 주요 요청과 상태 전이

문서 검색은 `question`이 아닌 **query**를 보낸다. Hybrid search에는 station/sensor/variable·기간·문서/사건 필터와 `top_k`를 추가할 수 있다. Keyword/vector 결합 상태와 실제 evidence locator를 함께 확인한다. 검색 결과나 similarity가 인간 승인 또는 확정 원인이라는 뜻은 아니다.

```json
{"query":"기압 자료의 점검 근거","top_k":5}
```

위 payload는 `/api/rag/hybrid-search` 예시다. `/api/rag/chat`의 최소 body는 `{"query":"기압 자료의 점검 근거"}`다. 검색·chat은 [RAG route](../ocean-ai-platform/backend/app/api/routes_rag.py), 문서 기반 필터는 [hybrid retrieval](16_HYBRID_RETRIEVAL.md)를 기준으로 한다.

| 경로 / 입력 | 검증 또는 결과 |
|---|---|
| `/api/qc/copilot/analyze`: station_id와 선택 sensor_id/variable_code/timestamp/query/top_k | 근거 분석·후보를 반환한다. 원문 QC·원인·label 최종 승인은 수행하지 않는다. |
| `/api/source-contracts/request`: `{"packet":{...}}` | source_contract_v2 미확정 packet도 PENDING 검토 요청으로 보존한다. packet은 파일 SHA/locator, source literal, 물리 identity/period, 단위·clock/QC·availableAt 근거를 포함해야 한다. |
| `/{contract_id}/decision`: expected_packet_sha256, decision, comment | reviewer가 정확 packet SHA와 현재 원장을 확인해 APPROVED/REJECTED/REVOKED 결정. 누락 근거로 APPROVED 불가. |
| `/{contract_id}/receipt` | 승인 export의 정확 canonical JSON bytes. X-Content-SHA256과 현재 ledger·source를 재검증한다. |
| `/api/datasets/source-candidates`: parquet_path, manifest_path/sha256, source_group, scopes, limit | draft 파일 후보. DatasetRegistry/membership에 승인 레코드를 우회 등록하지 않는다. |
| `/api/datasets/source-ingest`: receipt_path/sha256, register_metadata | 승인 원문과 receipt를 재검증한 뒤 exact binding을 적재한다. register_metadata는 검증된 물리 identity의 명시 등록이다. |
| `/api/datasets`: DatasetRegistry schema | 새 대상은 DRAFT/unbuilt이며 기간·scope·분할·counts를 검증한다. Legacy 등록은 strict leakage 정책을 유지한다. |
| `/api/datasets/register-reviewed`: dataset, split_protocol | 실제 승인 split protocol로 station_holdout/temporal_with_purge/sensor_transition_holdout 전략을 검증한다. |
| `/{dataset_id}/build`: 선택 dependencies[]의 role/path/sha256 | SOURCE_CONTRACT 및 SPLIT_PROTOCOL/EVALUATION_PROTOCOL/ACCEPTANCE_POLICY를 불변 복사하고 실제 membership을 snapshot v2에 동결한다. |
| `/{dataset_id}/validate`, `/approve`, `/lineage` | 현재 원장·파일·membership·as-of·분할을 재검증한다. v1은 운영 입력으로 자동 승격되지 않는다. |
| `/api/mlops/protocols/draft`: body 객체 | 버전별 split/evaluation/acceptance 정책 초안. 임의 필드·threshold를 승인 정책으로 꾸미지 않는다. |
| `/api/mlops/protocols/{sha256}/decision`: decision | MODEL_PROTOCOL 원장에 정확 SHA를 reviewer가 결정한다. |
| `/api/mlops/training/enqueue`: manifest_path | 승인 snapshot·고정 split/protocol과 worker flag를 preflight 후 durable queue에 넣는다. |
| `/api/mlops/candidates/review` 또는 `/register`: receipt_path, model_version | 독립 replay/검토와 후보 등록은 별도 단계다. 등록이 운영 배포 승인은 아니다. |
| `/api/mlops/models/{model_version}/decision`: decision, 선택 rollback query | 현재 candidate/deployment identity에 배포 또는 rollback 검토를 묶는다. |
| `/api/mlops/serving/predict`: scope_key, features[], 선택 typed_payload | loopback, serving flag, 활성 배포 승인·artifact 무결성을 요구한다. |
| `/api/reports/generate`: report_type, period_start/end **query** | 현재 API는 DRAFT 초기 레코드를 만든다. 완성된 분석 보고서를 자동 생성했다고 해석하지 않는다. |
| `/api/reports/{report_id}/review → approve/reject → publish` | 상태 전이와 reviewer를 검증한다. 일부 호환 body의 user_id는 인증 권한이 아니다. |

Source 계약 세부 schema는 [authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py), dataset payload는 [routes_datasets](../ocean-ai-platform/backend/app/api/routes_datasets.py), 모델 요청은 [routes_mlops_execution](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py)와 [구현 기록 82](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)를 참조한다. Worker enqueue가 차단된 상태에서 legacy `/api/mlops/retrain`을 우회 실행 경로로 사용하지 않는다.

## 10/8 분석·영속 승인 흐름

`POST /api/agents/evidence/analyze`는 `{scope:{station_id,sensor_id,variable_code,unit,period_start,period_end,as_of},query,declared_evidence,rule_report,ai_report,file_dependencies}`를 읽기 분석한다. 기간은 timezone offset을 포함한다. Fusion 객체를 직접 반환하며 recommendation_score·coverage_weight·missing_categories·conflicts와 input_sha256을 포함한다. 원본 Rule/AI report checksum·scope·가용시각을 검증한다.

`POST /api/agents/workflows`는 같은 입력에 request_key를 추가하고 operator Actor로 PENDING을 저장한다. 후속 result는 null이다. `GET /workflows`는 선택 scope 필터, `GET /workflows/{id}`는 immutable snapshot을 조회한다. reviewer 결정은 `{request_key,expected_recommendation_sha256,expected_revision,decision:"APPROVED"|"REJECTED",comment}`이며 resume/cancel은 decision을 제외한 동일 검증 값을 요구한다. approve만으로 실행되지 않는다. 별도 resume은 입력/원장/파일 재검증 후 보고서 DRAFT·MLOps 추천만 생성한다. 학습·registry·배포는 수행하지 않는다.

QC 평가·anomaly fit/analyze 상세 payload는 [QC](12_QC_RULE_RESULT_LAYER.md), [anomaly](25_ANOMALY_AI.md)를 따른다. JSON artifact만 다루며 실제 DB/모델 승인 원장에 저장하지 않는다. 업무 DB schema 추가는 [설치](02_SETUP_AND_INSTALLATION.md)를 따른다.

## 전체 경로 목록

표의 body는 OpenAPI request schema 이름이다. `*`는 필수 body, `—`는 body 없는 요청이다. 표에 없는 선택 query·enum·response 필드는 실행 서버의 OpenAPI를 따른다. Path parameter는 경로의 `{...}` 이름을 사용한다. 필수 query는 마지막 열에 표시한다.

### stations

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/stations](../ocean-ai-platform/backend/app/api/routes_stations.py) | GET | — | — |
| [/api/stations/catalog/classifications](../ocean-ai-platform/backend/app/api/routes_stations.py) | GET | — | — |
| [/api/stations/{station_id}](../ocean-ai-platform/backend/app/api/routes_stations.py) | GET | — | — |
| [/api/stations/{station_id}/profile](../ocean-ai-platform/backend/app/api/routes_stations.py) | GET | — | — |

### observations

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/observations](../ocean-ai-platform/backend/app/api/routes_observations.py) | GET | — | — |
| [/api/observations/standard](../ocean-ai-platform/backend/app/api/routes_observations.py) | GET | — | — |
| [/api/observations/summary](../ocean-ai-platform/backend/app/api/routes_observations.py) | GET | — | — |

### qc

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/qc/rule-definitions](../ocean-ai-platform/backend/app/api/routes_qc.py) | GET, POST | POST: QCRuleDefinitionCreate* | — |
| [/api/qc/rules/execute](../ocean-ai-platform/backend/app/api/routes_qc.py) | POST | POST: ExecuteRulesRequest* | — |
| [/api/qc/rule-results](../ocean-ai-platform/backend/app/api/routes_qc.py) | GET, POST | POST: QCRuleResultCreate* | — |
| [/api/qc/ai-labels](../ocean-ai-platform/backend/app/api/routes_qc.py) | GET, POST | POST: AILabelCreate* | — |
| [/api/qc/review-candidates](../ocean-ai-platform/backend/app/api/routes_qc.py) | POST | POST: ReviewCandidateRequest* | — |
| [/api/qc/copilot/analyze](../ocean-ai-platform/backend/app/api/routes_qc.py) | POST | POST: CopilotAnalyzeRequest* | — |
| [/api/qc/run-copilot](../ocean-ai-platform/backend/app/api/routes_qc.py) | POST | POST: RunCopilotRequest* | — |
| [/api/qc/generate-report](../ocean-ai-platform/backend/app/api/routes_qc.py) | POST | POST: ReportGenerateRequest* | — |
| [/api/qc/alerts](../ocean-ai-platform/backend/app/api/routes_qc.py) | GET | — | — |
| [/api/qc/summary](../ocean-ai-platform/backend/app/api/routes_qc.py) | GET | — | — |
| [/api/qc/ai-insights-summary](../ocean-ai-platform/backend/app/api/routes_qc.py) | GET | — | — |

### dashboard

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/dashboard/summary](../ocean-ai-platform/backend/app/api/routes_dashboard.py) | GET | — | — |
| [/api/dashboard/performance](../ocean-ai-platform/backend/app/api/routes_dashboard.py) | GET | — | — |

### rag

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/rag/ingest](../ocean-ai-platform/backend/app/api/routes_rag.py) | POST | POST: IngestRequest* | — |
| [/api/rag/reindex](../ocean-ai-platform/backend/app/api/routes_rag.py) | POST | POST: IngestRequest* | — |
| [/api/rag/documents](../ocean-ai-platform/backend/app/api/routes_rag.py) | GET | — | — |
| [/api/rag/chunks/{document_id}](../ocean-ai-platform/backend/app/api/routes_rag.py) | GET | — | — |
| [/api/rag/documents/{document_id}](../ocean-ai-platform/backend/app/api/routes_rag.py) | DELETE | — | — |
| [/api/rag/hybrid-search](../ocean-ai-platform/backend/app/api/routes_rag.py) | POST | POST: HybridSearchRequest* | — |
| [/api/rag/chat](../ocean-ai-platform/backend/app/api/routes_rag.py) | POST | POST: ChatRequest* | — |
| [/api/rag/ingestion/status](../ocean-ai-platform/backend/app/api/routes_rag.py) | GET | — | — |
| [/api/rag/ingestion/files](../ocean-ai-platform/backend/app/api/routes_rag.py) | GET | — | — |

### mlops

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/mlops/summary](../ocean-ai-platform/backend/app/api/routes_mlops.py) | GET | — | — |
| [/api/mlops/readiness](../ocean-ai-platform/backend/app/api/routes_mlops.py) | GET | — | — |
| [/api/mlops/retrain-history](../ocean-ai-platform/backend/app/api/routes_mlops.py) | GET | — | — |
| [/api/mlops/models](../ocean-ai-platform/backend/app/api/routes_mlops.py) | POST | POST: ModelRegistrationRequest* | — |
| [/api/mlops/models/{model_version}/deploy](../ocean-ai-platform/backend/app/api/routes_mlops.py) | POST | POST: DeployRequest* | — |
| [/api/mlops/models/{model_version}/rollback](../ocean-ai-platform/backend/app/api/routes_mlops.py) | POST | — | — |
| [/api/mlops/champion-challenger](../ocean-ai-platform/backend/app/api/routes_mlops.py) | GET | — | GET: champion_version<br>GET: challenger_version |
| [/api/mlops/retrain](../ocean-ai-platform/backend/app/api/routes_mlops.py) | POST | POST: RetrainRequest* | — |
| [/api/mlops/adapters](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | GET | — | — |
| [/api/mlops/protocols/draft](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | POST | POST: ProtocolDraft* | — |
| [/api/mlops/protocols/{sha256}/decision](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | POST | POST: Decision* | — |
| [/api/mlops/training/enqueue](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | POST | POST: ManifestRequest* | — |
| [/api/mlops/training/jobs](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | GET | — | — |
| [/api/mlops/candidates/review](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | POST | POST: CandidateRequest* | — |
| [/api/mlops/candidates/register](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | POST | POST: CandidateRequest* | — |
| [/api/mlops/models/{model_version}/decision](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | POST | POST: Decision* | — |
| [/api/mlops/serving/health](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | GET | — | — |
| [/api/mlops/serving/predict](../ocean-ai-platform/backend/app/api/routes_mlops_execution.py) | POST | POST: PredictionRequest* | — |

### reports

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/reports](../ocean-ai-platform/backend/app/api/routes_reports.py) | GET | — | — |
| [/api/reports/generate](../ocean-ai-platform/backend/app/api/routes_reports.py) | POST | — | POST: report_type<br>POST: period_start<br>POST: period_end |
| [/api/reports/{report_id}/review](../ocean-ai-platform/backend/app/api/routes_reports.py) | POST | — | — |
| [/api/reports/{report_id}/approve](../ocean-ai-platform/backend/app/api/routes_reports.py) | POST | POST: ReportUpdateStatusRequest* | — |
| [/api/reports/{report_id}/reject](../ocean-ai-platform/backend/app/api/routes_reports.py) | POST | POST: ReportUpdateStatusRequest* | — |
| [/api/reports/{report_id}/publish](../ocean-ai-platform/backend/app/api/routes_reports.py) | POST | — | — |
| [/api/reports/list](../ocean-ai-platform/backend/app/api/routes_reports.py) | GET | — | — |
| [/api/reports/stats](../ocean-ai-platform/backend/app/api/routes_reports.py) | GET | — | — |
| [/api/reports/{report_id}](../ocean-ai-platform/backend/app/api/routes_reports.py) | GET | — | — |

### equipment

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/equipment/status](../ocean-ai-platform/backend/app/api/routes_equipment.py) | GET | — | — |

### test-auto

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/test-auto/run](../ocean-ai-platform/backend/app/api/routes_test_auto.py) | POST | POST: TestRunRequest* | — |
| [/api/test-auto/results](../ocean-ai-platform/backend/app/api/routes_test_auto.py) | GET | — | — |
| [/api/test-auto/results/{test_id}](../ocean-ai-platform/backend/app/api/routes_test_auto.py) | GET | — | — |

### alerts

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/alerts](../ocean-ai-platform/backend/app/api/routes_alerts.py) | GET | — | — |
| [/api/alerts/{issue_id}/resolve](../ocean-ai-platform/backend/app/api/routes_alerts.py) | POST | — | — |
| [/api/alerts/events](../ocean-ai-platform/backend/app/api/routes_alerts.py) | GET | — | — |

### tide

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/tide/tide-residual/analyze](../ocean-ai-platform/backend/app/api/routes_tide_analysis.py) | POST | POST: WeeklyTideRequest* | — |
| [/api/tide/spring-tide/analyze](../ocean-ai-platform/backend/app/api/routes_tide_analysis.py) | POST | POST: SpringTideRequest* | — |

### service-monitoring

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/service-monitoring/overview](../ocean-ai-platform/backend/app/api/routes_service_monitoring.py) | GET | — | — |
| [/api/service-monitoring/check](../ocean-ai-platform/backend/app/api/routes_service_monitoring.py) | POST | POST: ServiceCheckRequest* | — |
| [/api/service-monitoring/logs](../ocean-ai-platform/backend/app/api/routes_service_monitoring.py) | GET | — | — |

### features

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/features/definitions](../ocean-ai-platform/backend/app/api/routes_features.py) | GET, POST | POST: FeatureDefinition* | — |
| [/api/features/values](../ocean-ai-platform/backend/app/api/routes_features.py) | GET, POST | POST: FeatureValue* | — |

### approvals

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/approvals/pending](../ocean-ai-platform/backend/app/api/routes_approvals.py) | GET | — | — |
| [/api/approvals/approve](../ocean-ai-platform/backend/app/api/routes_approvals.py) | POST | POST: ApprovalRequest* | — |
| [/api/approvals/reject](../ocean-ai-platform/backend/app/api/routes_approvals.py) | POST | POST: ApprovalRequest* | — |
| [/api/approvals/modify](../ocean-ai-platform/backend/app/api/routes_approvals.py) | POST | POST: ApprovalRequest* | — |
| [/api/approvals/comment](../ocean-ai-platform/backend/app/api/routes_approvals.py) | POST | POST: CommentRequest* | — |
| [/api/approvals/history](../ocean-ai-platform/backend/app/api/routes_approvals.py) | GET | — | — |

### datasets

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/datasets/register-reviewed](../ocean-ai-platform/backend/app/api/routes_datasets.py) | POST | POST: ReviewedDatasetRegistration* | — |
| [/api/datasets/source-ingest](../ocean-ai-platform/backend/app/api/routes_datasets.py) | POST | POST: SourceIngestRequest* | — |
| [/api/datasets/source-candidates](../ocean-ai-platform/backend/app/api/routes_datasets.py) | POST | POST: SourceCandidateRequest* | — |
| [/api/datasets](../ocean-ai-platform/backend/app/api/routes_datasets.py) | GET, POST | POST: DatasetRegistry* | — |
| [/api/datasets/{dataset_id}](../ocean-ai-platform/backend/app/api/routes_datasets.py) | GET | — | — |
| [/api/datasets/{dataset_id}/build](../ocean-ai-platform/backend/app/api/routes_datasets.py) | POST | POST: DatasetBuildRequest / null | — |
| [/api/datasets/{dataset_id}/validate](../ocean-ai-platform/backend/app/api/routes_datasets.py) | POST | — | — |
| [/api/datasets/{dataset_id}/approve](../ocean-ai-platform/backend/app/api/routes_datasets.py) | POST | — | — |
| [/api/datasets/{dataset_id}/lineage](../ocean-ai-platform/backend/app/api/routes_datasets.py) | GET | — | — |

### ai-insights

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/ai-insights/long-term](../ocean-ai-platform/backend/app/api/routes_ai_insights.py) | GET | — | — |
| [/api/ai-insights/summary](../ocean-ai-platform/backend/app/api/routes_ai_insights.py) | GET | — | — |

### agents

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/agents/workflow](../ocean-ai-platform/backend/app/api/routes_agents.py) | POST | POST: WorkflowRequest* | — |
| [/api/agents/workflow/stages](../ocean-ai-platform/backend/app/api/routes_agents.py) | GET | — | — |

### events

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/events](../ocean-ai-platform/backend/app/api/routes_events.py) | GET, POST | POST: EventCreate* | — |
| [/api/events/{event_id}/status](../ocean-ai-platform/backend/app/api/routes_events.py) | PATCH | — | PATCH: status |
| [/api/events/sensor-aliases](../ocean-ai-platform/backend/app/api/routes_events.py) | POST | POST: AliasCreate* | — |
| [/api/events/resolve-sensor](../ocean-ai-platform/backend/app/api/routes_events.py) | POST | POST: SensorResolve* | — |
| [/api/events/reference-catalog](../ocean-ai-platform/backend/app/api/routes_events.py) | GET | — | — |
| [/api/events/mdc-sensor-catalog](../ocean-ai-platform/backend/app/api/routes_events.py) | GET | — | — |
| [/api/events/from-document](../ocean-ai-platform/backend/app/api/routes_events.py) | POST | POST: DocumentEventCreate* | — |
| [/api/events/{event_id}/evidence](../ocean-ai-platform/backend/app/api/routes_events.py) | POST | POST: EvidenceCreate* | — |
| [/api/events/{event_id}/link-observations](../ocean-ai-platform/backend/app/api/routes_events.py) | POST | — | — |
| [/api/events/{event_id}/lineage](../ocean-ai-platform/backend/app/api/routes_events.py) | GET | — | — |
| [/api/events/evidence/{kind}/{target_id}](../ocean-ai-platform/backend/app/api/routes_events.py) | GET | — | — |
| [/api/events/{event_id}/label-candidates](../ocean-ai-platform/backend/app/api/routes_events.py) | POST | POST: CandidateCreate* | — |
| [/api/events/{event_id}/features](../ocean-ai-platform/backend/app/api/routes_events.py) | POST | — | — |
| [/api/events/feature-lineage/{observation_id}/{feature_id}/{feature_version}](../ocean-ai-platform/backend/app/api/routes_events.py) | GET | — | — |
| [/api/events/{event_id}/close](../ocean-ai-platform/backend/app/api/routes_events.py) | POST | POST: EventClose* | — |

### data-lake

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/data-lake/stats](../ocean-ai-platform/backend/app/api/routes_datalake.py) | GET | — | — |
| [/api/data-lake/summary](../ocean-ai-platform/backend/app/api/routes_datalake.py) | GET | — | — |
| [/api/data-lake/foundation/workflow](../ocean-ai-platform/backend/app/api/routes_foundation.py) | GET | — | — |
| [/api/data-lake/foundation/summary](../ocean-ai-platform/backend/app/api/routes_foundation.py) | GET | — | — |
| [/api/data-lake/foundation/channels](../ocean-ai-platform/backend/app/api/routes_foundation.py) | GET | — | — |
| [/api/data-lake/foundation/observations](../ocean-ai-platform/backend/app/api/routes_foundation.py) | GET | — | GET: source<br>GET: month<br>GET: station<br>GET: item |
| [/api/data-lake/foundation/review-receipt](../ocean-ai-platform/backend/app/api/routes_technical_review.py) | GET | — | — |

### source-contracts

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/source-contracts](../ocean-ai-platform/backend/app/api/routes_source_contracts.py) | GET | — | — |
| [/api/source-contracts/request](../ocean-ai-platform/backend/app/api/routes_source_contracts.py) | POST | POST: ReviewRequest* | — |
| [/api/source-contracts/{contract_id}](../ocean-ai-platform/backend/app/api/routes_source_contracts.py) | GET | — | — |
| [/api/source-contracts/{contract_id}/decision](../ocean-ai-platform/backend/app/api/routes_source_contracts.py) | POST | POST: ReviewDecision* | — |
| [/api/source-contracts/{contract_id}/receipt](../ocean-ai-platform/backend/app/api/routes_source_contracts.py) | GET | — | — |

### integrations

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/integrations](../ocean-ai-platform/backend/app/api/routes_integrations.py) | GET | — | — |
| [/api/integrations/{source_id}/test](../ocean-ai-platform/backend/app/api/routes_integrations.py) | POST | — | — |

### imputation

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/imputation/long-gap/detect](../ocean-ai-platform/backend/app/api/routes_imputation.py) | GET | — | GET: station_id<br>GET: sensor_id |
| [/api/imputation/run](../ocean-ai-platform/backend/app/api/routes_imputation.py) | POST | POST: ImputeRequest* | — |
| [/api/imputation](../ocean-ai-platform/backend/app/api/routes_imputation.py) | GET | — | — |
| [/api/imputation/long-gap/plan](../ocean-ai-platform/backend/app/api/routes_imputation.py) | POST | — | — |

### forecasting

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/forecasting/baseline](../ocean-ai-platform/backend/app/api/routes_forecasting.py) | POST | POST: ForecastRequest* | — |
| [/api/forecasting/models](../ocean-ai-platform/backend/app/api/routes_forecasting.py) | GET | — | — |

### 서비스·세션

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/health](../ocean-ai-platform/backend/app/main.py) | GET | — | — |
| [/readiness](../ocean-ai-platform/backend/app/main.py) | GET | — | — |
| [/](../ocean-ai-platform/backend/app/main.py) | GET | — | — |
| [/api/session](../ocean-ai-platform/backend/app/main.py) | GET | — | — |
| [/api/runtime](../ocean-ai-platform/backend/app/main.py) | GET | — | — |

### lake

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/api/lake/monitoring](../ocean-ai-platform/backend/app/api/routes_lake_browser.py) | GET | — | — |
| [/api/lake/daily-reports](../ocean-ai-platform/backend/app/api/routes_lake_browser.py) | GET | — | — |
| [/api/lake/equipment-evidence](../ocean-ai-platform/backend/app/api/routes_lake_browser.py) | GET | — | — |
| [/api/lake/summary](../ocean-ai-platform/backend/app/api/routes_lake_browser.py) | GET | — | — |
| [/api/lake/publication-comparison](../ocean-ai-platform/backend/app/api/routes_lake_browser.py) | GET | — | — |
| [/api/lake/metric-completion](../ocean-ai-platform/backend/app/api/routes_lake_browser.py) | GET | — | — |
| [/api/lake/stations/{station}](../ocean-ai-platform/backend/app/api/routes_lake_browser.py) | GET | — | — |
| [/api/lake/series](../ocean-ai-platform/backend/app/api/routes_lake_browser.py) | GET | — | GET: source<br>GET: month<br>GET: station<br>GET: item |

## 검증 범위

위 154개 경로·163개 operation은 2026-10-08 최신 backend 읽기 전용 OpenAPI와 등록 라우터를 대조했다. 이는 API 등록·입력 계약 확인이다. 실원천 승인, 전체 endpoint 쓰기 성공, 모델 학습·배포 완료를 뜻하지 않는다. 상태를 변경하는 endpoint는 실제 검토 자료와 권한·현재 승인 원장이 준비된 뒤 사용한다.

### 10/8 추가 경로

| 경로 / 구현 | Method | Request body | 필수 query |
|---|---|---|---|
| [/](../ocean-ai-platform/backend/app/main.py) | GET | — | — |
| [/api/agents/evidence/analyze](../ocean-ai-platform/backend/app/api/routes_agents.py) | POST | POST: AnalysisRequest* | — |
| [/api/agents/workflows](../ocean-ai-platform/backend/app/api/routes_agents.py) | GET, POST | POST: StartRequest* | — |
| [/api/agents/workflows/{workflow_id}](../ocean-ai-platform/backend/app/api/routes_agents.py) | GET | — | — |
| [/api/agents/workflows/{workflow_id}/cancel](../ocean-ai-platform/backend/app/api/routes_agents.py) | POST | POST: TransitionRequest* | — |
| [/api/agents/workflows/{workflow_id}/decision](../ocean-ai-platform/backend/app/api/routes_agents.py) | POST | POST: DecisionRequest* | — |
| [/api/agents/workflows/{workflow_id}/resume](../ocean-ai-platform/backend/app/api/routes_agents.py) | POST | POST: TransitionRequest* | — |
| [/api/anomaly-analysis/analyze](../ocean-ai-platform/backend/app/api/routes_anomaly_analysis.py) | POST | POST: AnalyzeRequest* | — |
| [/api/anomaly-analysis/fit](../ocean-ai-platform/backend/app/api/routes_anomaly_analysis.py) | POST | POST: FitRequest* | — |
| [/api/qc/rule-catalog](../ocean-ai-platform/backend/app/api/routes_qc.py) | GET | — | — |
| [/api/qc/rules/evaluate](../ocean-ai-platform/backend/app/api/routes_qc.py) | POST | POST: EvaluateRulesRequest* | — |
## 10/8 단계별 보완 결과

| 경로 | Method | 입력·권한 |
|---|---|---|
| `/api/development-stages/review` | GET | 고정 artifact root·SHA·13축 검토, 운영 승인 아님 |
| `/api/model-development/task-readiness` | GET | 72 source keys·현재 승인 입력 준비; 실제 serving 원장 별도 |
| `/api/model-development/training-manifests` | GET, POST | 조회 / operator·reviewer·admin의 승인 TRAIN/VALIDATION/TEST dataset IDs |
| `/api/model-development/training-preflight` | GET | 허용 manifest_path·expected_sha256·현재 승인 검증 |
| `/api/model-development/policy-bundle` | GET | selection_json 정책 초안 검토; 잘못된 shape409 |
| `/api/model-development/datasets/{dataset_id}/migration-review` | GET | new_dataset_id·new_version·dependencies_json, 읽기 전용 |
| `/api/model-development/datasets/{dataset_id}/migrate-v2` | POST | MigrationRequest·actor·expected legacy/review SHA, 새 BUILT v2만 생성 |

enqueue/retrain은 선택한 manifest expected SHA를 받는다. preflight 실패는 큐 생성 이전에 차단하며 큐가 다시 현재 입력을 검증한다. 실제 계정 미설정503, 범위 밖 경로·malformed nested 입력409를 실검증했다. [29](29_DEVELOPMENT_STAGE_EXECUTION.md).

별도 개발용8011 서버의 `/health`, `/readiness`, `/release`, `/predict`는 운영 backend OpenAPI와 구분한다. 3개 원시 수치 시험 모델을 exact release/artifact/입력에 연결하고 운영 Registry를 쓰지 않는다. `/predict`는3개의 유한 값과 expected release/artifact SHA를 받는다. 오래된 선택409·잘못된 입력422·본문크기413·원격Origin/Host403·MIME415를 검증했다. 웹은 운영 token 없이 `/experimental-api`로 연결한다. [30 실행·API](30_EXPERIMENTAL_TRAIN_DEPLOYMENT.md).
