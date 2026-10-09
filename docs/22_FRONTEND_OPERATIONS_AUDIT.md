# 프런트엔드 연결과 운영 상태 표시

현행화: 2026-10-09

관측 기본 조회는 **2026-07 ~ 2026-07**이다. Dashboard·관측 현황에 공식7월 월간해양정보와 원천별Parquet 대조를 연결했다. 지정한 과거 기간을 유지하고 공식 현황과 선택 기간을 구분한다. 단일7월에는 `as_of_month=2026-07`의 유일 명칭·좌표 참조를 필터·지도에 반영하며 해역 직접 근거가 없으면 기존 값을 유지한다. [7월 검증](27_JULY_REPORT_PARQUET_MATCH.md)에 근거와 수치 차이를 기록한다.

[MetricCompletionPanel](../ocean-ai-platform/frontend/src/components/MetricCompletionPanel.tsx)은 원시 시간격자·결측표현·수치/시각 해석·기본 QC 표기와 원문 코드 분포·보고서 고유 셀 평균을 구분해 표시한다. Dashboard/Observations/QC/Insights가 동일 snapshot·원천·선택 기간의 `/api/lake/metric-completion`을 조회한다. 보유0/미확정/실패/조회 중을 실제0%와 구분하며 운영 지표에는 필요한 근거를 표시한다. Service는 현재 프로세스의 응답 수·오류 수·기록 구간을 표시한다. [28 산정 경계](28_METRIC_COMPLETION.md)를 확인한다.

## 현재 화면이 조회하는 경로

| 화면 | 실제 연결 | 해석 범위와 남은 연결 |
|---|---|---|
| Dashboard | `/api/lake/summary`, `/api/lake/monitoring`, `/api/stations`, `/api/reports` | 선택 원천·기간·관측망과 전체 기준 범위를 구분한다. 보유 관측소·행 수, 원천 QC 존재 비율은 장비 정상·예상 수집률이 아니다. |
| 관측 현황 | `/api/lake/summary`, `/api/stations`, `/api/lake/metric-completion`, `/api/lake/stations/{station_id}`, `/api/lake/series?tail=true` | 큰 지도·휠 확대/축소와 해역·관측소·기간 선택, exact 항목/수심의 최근 24건과 월별 자료 유무를 제공한다. 원천 행 수와 산정 근거는 하단에서 펼친다. [31 검증](31_OBSERVATION_METRIC_RECALCULATION.md)을 따른다. |
| QC Copilot | `WorkflowReviewPanel`의 evidence/analyze·workflows, 기존 `AnalysisWorkspace` lake 조회 | exact scope 분석·score/coverage·누락·충돌·PENDING·승인/반려·재개를 표시한다. 계정 미설정이면 분석/조회만 가능하다. |
| AI Insights | 같은 `AnalysisWorkspace`의 Insights 모드와 관측소 기준 좌표 | 보유 자료·근거를 비교한다. 기존 `/ai-insights/summary`의 휴리스틱 위험 점수 화면과 구분한다. |
| Equipment | `/api/lake/equipment-evidence`, lake summary, 관측소 기준 좌표 | 문서의 설치·장비 근거를 표시한다. 설치 문구만으로 센서 운영기간·실시간 health를 확정하지 않는다. |
| MLOps | `/api/mlops/summary`, `/retrain-history`, `/adapters`, 고정 학습 입력 및 별도 `/experimental-api` | 승인 입력 선택·preflight·큐 요청을 연결하고, 실제 7월 원시 자료의 개발용 학습·시험 배포를 별도 패널로 표시한다. 운영 Registry와 시험 모델을 분리한다. 학습 artifact 다운로드 UI는 미연결이다. |
| Reports | `/api/reports`, `/reports/{report_id}/review`, `/approve`, `/reject` | 목록·상세·JSON 내보내기와 검토 제출·담당 승인/반려를 제공한다. 자동 발행이나 모델 배포가 아니다. |
| Alerts | `/api/approvals/pending`, `/approve`, `/reject` | 일반 QC_CHANGE·AI_LABEL·REPORT·MODEL_DEPLOY 대기 업무를 처리한다. Source Contract·Dataset·Protocol 전체의 승인 inbox는 아니다. |

근거 component: [Dashboard](../ocean-ai-platform/frontend/src/pages/Dashboard.tsx), [AnalysisWorkspace](../ocean-ai-platform/frontend/src/components/AnalysisWorkspace.tsx), [EquipmentWorkspace](../ocean-ai-platform/frontend/src/components/EquipmentWorkspace.tsx), [MLOps](../ocean-ai-platform/frontend/src/pages/MLOps.tsx), [Reports](../ocean-ai-platform/frontend/src/pages/Reports.tsx), [Alerts](../ocean-ai-platform/frontend/src/pages/Alerts.tsx).

lake 조회는 같은 snapshot인지 확인하고 로딩·오류·빈 범위를 분리한다. 참조 좌표나 문서 근거 조회 실패는 별도 메시지로 남기며 성공한 모의 값으로 덮지 않는다. 승인되지 않은 의미·단위·QC와 미확정 장비 기간을 정상 성과로 해석하지 않는다.

MLOps의 Registry 내보내기는 표시 중인 모델·readiness·adapter coverage의 JSON 검토 자료다. 학습 artifact 다운로드가 아니다. 고정 manifest 선택·전달 UI는 연결됐으며 현재 실제 승인 입력·담당 권한·학습 설정이 없어 운영 재학습 요청은 차단된다. API/CLI의 worker 구현과 버튼 상태는 별도로 설명해야 한다.

## 기존 API와 현재 화면의 구분

기존 `/dashboard/summary`, `/equipment/status`, `/ai-insights/summary` 등 호환 API가 남아 있어도 현재 화면이 모두 호출하는 것은 아니다. live 장비 상태의 미측정 health와 설치 근거를 구분한다. 데모 값·휴리스틱 점수의 존재를 실제 센서 성능으로 세지 않는다. 서버는 `/qc/run-copilot`, `/qc/ai-insights-summary`, `/test-auto/run`, `/agents/workflow`의 prototype 실행을 demo 모드에 제한한다.

새 workflow는 PostgreSQL PENDING에서 중단하고 reviewer 결정 후 별도 resume한다. 예상 추천 SHA와 revision을 전달하며 stale scope를 승인하지 않도록 서버 snapshot scope를 표시한다. 호환 demo도 PENDING에서 멈춘다. [다중 agent 실행 범위](21_MULTI_AGENT_WORKFLOW.md)와 [AI Insights 계산 경계](20_AI_INSIGHTS.md)를 참고한다.

## 인증·로그·상태 조회

[API client](../ocean-ai-platform/frontend/src/api/client.ts)는 설정된 operator token을 메모리에 두고 Bearer header에 전달한다. 토큰을 frontend 환경변수나 Git에 넣지 않는다. 실제 actor와 reviewer 역할은 [서버 security](../ocean-ai-platform/backend/app/core/security.py)가 판정하며 요청 body의 `user_id`로 승인자를 만들지 않는다. 인증 identity가 없으면 보호된 작업은 503, 잘못된 인증은 401, 권한 부족은 403이다.

[main.py](../ocean-ai-platform/backend/app/main.py)의 CORS는 개발·운영 모두 `CORS_ORIGINS` 목록을 사용한다. 개발 환경 전체 허용으로 설명하지 않는다. `/health`는 프로세스, `/readiness`는 DB 연결을 확인한다. 모델 준비 상태는 `/api/mlops/readiness`, 실제 serving은 `/api/mlops/serving/health`에서 확인한다.

JSON HTTP 요청 로그와 승인 이력은 목적이 다르다. `ApprovalHistory` 및 원천·Dataset·모델의 불변 receipt는 실제 승인과 내용 hash를 결합한다. `AuditLog` 모델이 존재하는 것만으로 모든 HTTP 요청이 DB 감사 기록에 자동 저장되는 것은 아니다. 일반 요청의 영속 감사·운영 보존 정책은 별도 연결이 필요하다.

## 검증과 운영 확인

10/8 감사는 [당시 검증](10_IMPLEMENTATION_AUDIT.md)에 보존한다. 10/9 최신 전체 회귀는 backend 776 passed / 1 skipped, frontend 29 passed와 production build 통과이며 관측현황 브라우저 9개 검증을 [31](31_OBSERVATION_METRIC_RECALCULATION.md)과 [current_status.json](current_status.json)에 기록한다. 깨끗한 `npm ci --ignore-scripts`와 TypeScript/Vite build를 검증했다. 빌드는 모든 화면의 실제 승인·장애·배포 동작을 현장 검증한 결과가 아니다.

13:09 KST 실제 backend `/health`와 frontend HTTP는 200이었고 API identities는 0이었다. 13:10:55 KST canonical worker는 RUNNING과 fresh heartbeat가 확인됐지만 작업 큐는 비어 있었다. 승인 입력은 없고 모델 readiness는 BLOCKED, 수용 기준은 NOT_DEFINED, serving은 409 NO_ACTIVE_LOCAL_MODEL이었다. 기존 canonical 프로세스의 확인이며 공개 복사본을 기동했다는 의미는 아니다.

실제 운영 검증에는 담당 인증, 원천·기간·사건 검토, 승인 입력, 실패/반려 화면, 모델 실행과 identity 검증이 필요하다. [설치 문서](02_SETUP_AND_INSTALLATION.md), [승인 경로](17_HUMAN_IN_THE_LOOP.md), [현재 진행 상태](24_P0_END_TO_END_PROGRESS.md)를 따른다.

최신 개발 UI는 `http://127.0.0.1:5174`이며 backend8010에 연결한다. 기존 canonical5173/8000·Chroma8001·worker는 유지한다. [WorkflowReviewPanel](../ocean-ai-platform/frontend/src/components/WorkflowReviewPanel.tsx)은 새 흐름의 상태/권한별 버튼을 제공하며 실제 담당 계정은 아직 설정하지 않았다.
## 10/8 단계별 보완 결과

System의 DevelopmentStageReview는13단계×구현/시험/자료/승인/운영을 표시하고 SHA증거·남은 입력을 펼친다. MLOps의 TrainingWorkbench/InputPreparationReview는 legacy 검토·정책 양식·세 승인Dataset 선택·manifest preflight·학습 큐를 연결한다. 입력/권한/worker가 없으면 변경 버튼을 비활성화하고 async응답을 revision guard로 차단한다. frontend17시험/build와 부모 실제 브라우저를 통과했다. 7월 기본 기간과 미산정 지표 경계를 유지한다. [29](29_DEVELOPMENT_STAGE_EXECUTION.md).

후속 개발용 학습·시험 배포는 [30](30_EXPERIMENTAL_TRAIN_DEPLOYMENT.md)을 따른다. ExperimentalDeploymentPanel은 별도8011 서버의 release/readiness 동등성·정확 입력·artifact SHA를 검증하고 실 예측을 요청한다. 7월 GR 인천 3항목의 고정 분할·후보 오차·참여 SHA를 표시한다. 133,876행의 학습 결과를 운영 모델 수에 합산하지 않는다. 최신20개 frontend 시험과 build 결과는30의 검증 기록으로 분리한다.
