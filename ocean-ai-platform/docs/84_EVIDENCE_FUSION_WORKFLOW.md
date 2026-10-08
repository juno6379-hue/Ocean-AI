# Evidence Fusion과 영속 Human Approval

기준일: 2026-10-08. [Fusion service](../backend/app/services/evidence_fusion.py), [workflow](../backend/app/agents/multi_agent_workflow.py), [API](../backend/app/api/routes_agents.py)의 현재 계약을 설명한다. 최종 원천/QC/모델 승인 경계는 [승인 문서](../../docs/17_HUMAN_IN_THE_LOOP.md)와 [원천·모델 실행](82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)을 따른다.

## 정확한 입력과 분석 권위

```json
{
  "scope": {
    "station_id": "EXAMPLE_STATION",
    "sensor_id": "EXAMPLE_SENSOR",
    "variable_code": "AIR_PRES",
    "unit": "hPa",
    "period_start": "2026-01-01T00:00:00+00:00",
    "period_end": "2026-01-02T00:00:00+00:00",
    "as_of": "2026-01-03T00:00:00+00:00"
  },
  "query": "관측 이상 점검 근거",
  "declared_evidence": []
}
```

위 값은 형식 예시이며 실제 등록 센서나 승인 기록이 아니다. 관측 기간은 `[period_start, period_end)`이고 end는 as_of보다 뒤일 수 없다. 모든 시간은 명시적 offset이 있어야 하며 UTC로 정규화한다. 관측소·센서·변수·단위를 각각 명시한다. 선택값 `sensor_episode_id`를 지정했다면 근거에도 같은 episode가 필요하다. 시설명 유사성, unit alias, naive 원천 시각으로 자동 연결하지 않는다.

`POST /api/agents/evidence/analyze`는 위 입력으로 분석만 한다. 선택 입력은 `rule_report`, `ai_report`, `file_dependencies:[{path,sha256}]`이다. 선언 근거 최대 5,000개, 파일 의존 최대 64개, query 최대 4,000자를 허용하고 알 수 없는 최상위 필드는 거부한다. 파일은 허용된 source root와 경로/reparse guard를 거친 exact SHA로 대조한다. 응답은 Fusion object에 input SHA, bounded scope 설명과 잘린 부분을 더한 직접 응답이다.

DB 수집은 같은 station/sensor/variable과 standard unit의 관측을 조회한다. 주요 관측·Rule·Label·운영 로그 조회는 각 최대 500개이고 501행 조회로 잘림을 표시한다. 해당 identity의 센서 metadata도 수집한다. DB 참여 목록과 행별 hash를 frozen 입력에 남기며 bounded 결과를 전수 원천 승인이라고 표시하지 않는다. SIMULATED/DEMO 원천의 저장 Rule은 점수로 승격하지 않는다.

caller의 Rule·AI·Metadata·Operation·RAG 입력은 `DECLARED_REVIEW_INPUT`이다. hash나 caller의 `approved=true`는 실제 승인 actor를 만들지 않는다. 결과는 `ANALYSIS_ONLY`, `approved=false`, `definitive_qc=false`이며 계정 설정 전에도 조건부 분석 조회가 가능하다.

## Recommendation score와 설명

| category | weight | 이상/정상 지지도 연결 |
|---|---:|---|
| RULE | 0.30 | EVALUATED flag 4: 이상 1, flag 3: 이상 0.5, flag 1: 정상 1 |
| AI | 0.25 | 결과의 empirical support strength; calibration rank는 별도 provenance |
| METADATA | 0.15 | exact scope/time/출처가 명시된 검토 근거 |
| OPERATION | 0.15 | exact scope/time/출처가 명시된 검토 근거 |
| RAG | 0.15 | exact scope/time/출처가 명시된 검토 근거 |

각 category에서 이상·정상 지지도의 최댓값을 따로 취한다. `recommendation_score = Σ(weight × max anomaly support)`이고 고정 분모를 유지한다. coverage가 낮다고 가중치를 재정규화하지 않는다. Rule 이상 지지도 1만 확인되면 score는 0.30이다. 정상/이상 지지도가 모두 없으면 score는 `null`이다. 유효 정상 근거만 있으면 score 0과 별도 normal support를 반환하며 최종 정상 QC를 뜻하지 않는다. `score_kind=WEIGHTED_EVIDENCE_SUPPORT_NOT_PROBABILITY`를 항상 표시한다.

현재 DB Metadata·Operation 및 RAG adapter는 유효한 시간·scope를 가진 설명을 `CONTEXT`, strength 0으로 보존한다. 서술이나 cosine relevance로 이상 지지도를 자동 생성하지 않는다. 해당 종류에 이상/정상 지지도를 제공하려면 exact provenance를 가진 명시적 검토 입력이 필요하고 선언 권위로 표시된다. 유효 context가 있으면 coverage는 PRESENT일 수 있지만 정상/이상 점수는 늘지 않는다.

반환값은 `recommendation_score`, `anomaly_support`, `normal_support`, `coverage_weight`, 종류별 `coverage`, `missing_categories`, `conflicts`, `accepted_evidence`, `excluded_evidence`, `duplicate_count`, `recipe`이다. Recommendation은 `REVIEW_ANOMALY`, `REVIEW_NORMAL_CANDIDATE`, `REVIEW_CONFLICT`, `INSUFFICIENT_EVIDENCE` 중 하나다. missing을 정상 값으로 평균하지 않는다.

### 출처·시간·충돌 검사

근거마다 category에 맞는 source_kind, source_id, 64자리 lowercase SHA, 비어 있지 않은 string 또는 typed object locator, exact scope, event_at, available_at, 평가 상태와 0..1 유한 support가 필요하다. bool/NaN 점수, 다른 단위/항목/센서, 미평가·missing 상태는 제외한다. event/available이 as_of 뒤이거나 available이 event보다 앞이면 제외한다. Rule/AI event는 관측 기간 안에 있어야 한다. 원래 근거와 제외 이유를 반환한다.

동일 SHA와 typed locator는 한 provenance로 계산하고 반복 입력으로 점수를 더하지 않는다. 같은 provenance의 category·assessment·strength·scope·시간 주장이 다르면 전부 격리한다. 같은 event/scope의 정상/이상 주장도 conflict로 표시한다. 다른 시각의 정상과 이상이 같은 기간에 있다는 이유만으로 충돌을 만들지 않는다.

저장 Rule은 evaluation_status/result_reason/provenance_json을 읽는다. native `source_facts.clock_semantics=OBSERVED_AT`와 UTC storage 표현은 다른 개념이다. 별도 `event_clock_policy=EXPLICIT_OFFSET_INSTANT`, exact event/관측 UTC, available/executed UTC 및 물리 센서·episode를 확인한다. legacy naive 실행시각은 실제 가용시각으로 해석하지 않는다. Rule·AI report는 result_sha256를 제외한 전체 canonical JSON SHA를 재계산한다. flag·score·scope를 바꾸고 과거 SHA를 재사용하면 각각 RULE_REPORT_CHECKSUM_MISMATCH 또는 AI_REPORT_CHECKSUM_MISMATCH로 차단한다. 이 hash는 내용 무결성 검사이고 선언 입력을 실제 원천 승인으로 바꾸지 않는다.

RAG는 station/sensor/variable/기간을 검색 조건에 포함한다. 성공한 빈 조회는 MISSING, 검색 서비스 오류는 ERROR로 보존한다. 보고일·발행일·ingested_at이 event/available을 증명하지 않으면 unscored로 남긴다. relevance는 trace이며 추천 probability가 아니다.

## 영속 상태와 실제 승인

[ORM](../backend/app/models/agent_workflow.py)은 PostgreSQL의 `agent_workflow_run`과 `agent_workflow_transition`에 업무를 저장한다. [migration](../backend/migrations/20261008_agent_workflow.sql)은 기존 ApprovalHistory를 참조하는 두 additive table과 index를 정의한다. 명시적 migration 적용은 실제 계정·승인을 만들지 않는다. SQLite는 격리 unit test/local ledger 환경이고 application persistence를 대체하지 않는다.

```text
NEW → PENDING → APPROVED → RESUMING → COMPLETED
              ↘ REJECTED
       PENDING 또는 APPROVED → CANCELLED
```

`POST /api/agents/workflows`에는 analyze 입력에 request_key를 추가한다. 서버 operator/reviewer/admin만 생성하며 PENDING ApprovalHistory와 REQUEST 전이를 기록한다. 응답은 workflow_id/status/revision/input_sha256/recommendation_sha256/scope/recommendation/human_approval/result의 직접 object다. PENDING에서 result=null, 단계 로그는 Human Approval까지이며 보고서·MLOps 함수는 실행하지 않는다. 목록 GET `/api/agents/workflows`는 station_id/sensor_id/variable_code/unit 조건을 적용한 후 최대 200개를 반환한다.

판정 요청은 GET `/api/agents/workflows/{workflow_id}`의 최신 hash/revision을 사용한다.

```json
{
  "request_key": "review-example-unique-key",
  "expected_recommendation_sha256": "<GET에서 받은 정확한 64자리 SHA>",
  "expected_revision": 0,
  "decision": "APPROVED",
  "comment": "추천 근거 검토 의견"
}
```

`POST /api/agents/workflows/{id}/decision`은 reviewer/admin만 APPROVED/REJECTED를 기록한다. requester/reviewer는 서버 Bearer identity로 확인하고 body user_id로 바꾸지 못한다. 승인 상태 조회 뒤 `/resume`에 새로운 request_key, 현재 hash/revision/comment를 제출한다. resume은 operator/reviewer/admin에게 허용되며 decision 필드를 받지 않는다. 요청자 또는 reviewer/admin의 `/cancel`도 같은 전이 입력을 사용한다.

승인·재개는 frozen payload와 추천 전체 hash, 코드 fingerprint·Fusion recipe replay, 현재 DB 행과 참여 목록, 파일 bytes SHA를 대조한다. 최신 AGENT_WORKFLOW 승인과 requester/reviewer 및 전이 record SHA도 재개 시 확인한다. row lock과 status/revision compare-and-swap으로 경쟁 요청 중 하나만 후속 함수를 실행한다. 후속 초안 생성과 전이는 같은 transaction에서 처리하고 실패 시 rollback한다.

request_key는 1..128자이고 동일 actor/내용의 재전송만 기존 결과를 재사용한다. 다른 actor/내용의 key 재사용, stale 입력·추천·revision, 최신 승인 불일치, 변조 이력은 차단한다. 외부 파일/DB 근거가 바뀐 업무도 저장 payload/추천 자체와 actor/hash/revision이 온전하면 취소할 수 있다. 취소·거부·완료는 새 재개 요청으로 실행할 수 없다.

### 초안 결과의 한계

COMPLETED의 report_draft는 dict이며 status=DRAFT, text, score, score_kind, approved=false를 포함한다. mlops는 status=RECOMMENDATION, action과 training_enqueued/model_registered/deployment_performed=false를 반환한다. workflow 승인 id와 추천 SHA를 기록하고 `source_qc_dataset_model_approval_granted=false`를 유지한다. ReportRegistry 적재·보고서 승인/발행·최종 QC·학습 job·Model Registry·배포는 실행하지 않는다.

기존 `POST /api/agents/workflow`는 demo 전용으로 남지만 정확 scope를 요구하고 PENDING에서 중단한다. 영속 workflow가 아니므로 승인/재개는 새 API를 사용한다. live/demo 정책은 [security](../backend/app/core/security.py)를 따르며 단계 설명은 `GET /api/agents/workflow/stages`에서 조회한다.

## 검증과 운영 경계

[Fusion 시험](../backend/tests/test_evidence_fusion.py)과 [workflow 시험](../backend/tests/test_agent_workflow_gate.py)은 score·coverage·중복/충돌·미래 시간·unit/episode 분리, 실제 guide/AI report와 전체 checksum, 원문/DB 변경, actor/replay/CAS, reject/cancel/resume를 검증한다. 최종 focused 46개가 통과했다. 격리 source 승인→원문 재검증 ingest→저장 Rule→Fusion 양성 경로는 native OBSERVED_AT을 보존하고, 두 동시 resume는 초안을 한 번만 만든다.

시험 source/reviewer/파일은 임시 환경이다. PostgreSQL 임시 schema에서도 migration·재시작·승인 전/후 재개를 검증했고 public 원천·승인·Dataset·Model 기록은 불변이었다. 실제 API identities와 원천 담당자 승인 설정은 별도이며 개발 분석 계산과 구분한다. 2026-10-08 13:09 KST 운영 source packet/decision/binding·ApprovalHistory·Dataset·Model Registry는 0이었다. 72 업무는 representation baseline의 부분 구현이다. 최신 웹·운영 검증은 [P0 현황](../../docs/24_P0_END_TO_END_PROGRESS.md)에 기록한다.
