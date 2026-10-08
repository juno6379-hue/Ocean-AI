# 프런트엔드 연결과 운영 상태 표시

현행화: 2026-10-08

## 현재 화면이 조회하는 경로

| 화면 | 실제 연결 | 해석 범위와 남은 연결 |
|---|---|---|
| Dashboard | `/api/lake/summary`, `/api/lake/monitoring`, `/api/stations`, `/api/reports` | 선택 원천·기간·관측망과 전체 기준 범위를 구분한다. 보유 관측소·행 수, 원천 QC 존재 비율은 장비 정상·예상 수집률이 아니다. |
| QC Copilot | `AnalysisWorkspace`의 lake monitoring·summary | 원천·기간·관측소·항목별 검토 자료를 조회한다. 기존 `/qc/run-copilot` 데모 실행 화면이 아니다. |
| AI Insights | 같은 `AnalysisWorkspace`의 Insights 모드와 관측소 기준 좌표 | 보유 자료·근거를 비교한다. 기존 `/ai-insights/summary`의 휴리스틱 위험 점수 화면과 구분한다. |
| Equipment | `/api/lake/equipment-evidence`, lake summary, 관측소 기준 좌표 | 문서의 설치·장비 근거를 표시한다. 설치 문구만으로 센서 운영기간·실시간 health를 확정하지 않는다. |
| MLOps | `/api/mlops/summary`, `/retrain-history`, `/adapters`, 일반 승인 대기 조회 | 코드 구현·worker 설정·프로세스 실행·승인 입력·실제 운영 모델 수를 분리한다. 재학습 입력 선택과 artifact 다운로드 UI는 미연결이다. |
| Reports | `/api/reports`, `/reports/{report_id}/review`, `/approve`, `/reject` | 목록·상세·JSON 내보내기와 검토 제출·담당 승인/반려를 제공한다. 자동 발행이나 모델 배포가 아니다. |
| Alerts | `/api/approvals/pending`, `/approve`, `/reject` | 일반 QC_CHANGE·AI_LABEL·REPORT·MODEL_DEPLOY 대기 업무를 처리한다. Source Contract·Dataset·Protocol 전체의 승인 inbox는 아니다. |

근거 component: [Dashboard](../ocean-ai-platform/frontend/src/pages/Dashboard.tsx), [AnalysisWorkspace](../ocean-ai-platform/frontend/src/components/AnalysisWorkspace.tsx), [EquipmentWorkspace](../ocean-ai-platform/frontend/src/components/EquipmentWorkspace.tsx), [MLOps](../ocean-ai-platform/frontend/src/pages/MLOps.tsx), [Reports](../ocean-ai-platform/frontend/src/pages/Reports.tsx), [Alerts](../ocean-ai-platform/frontend/src/pages/Alerts.tsx).

lake 조회는 같은 snapshot인지 확인하고 로딩·오류·빈 범위를 분리한다. 참조 좌표나 문서 근거 조회 실패는 별도 메시지로 남기며 성공한 모의 값으로 덮지 않는다. 승인되지 않은 의미·단위·QC와 미확정 장비 기간을 정상 성과로 해석하지 않는다.

MLOps의 Registry 내보내기는 표시 중인 모델·readiness·adapter coverage의 JSON 검토 자료다. 학습 artifact 다운로드가 아니다. 재학습 버튼은 승인된 고정 manifest를 선택·전달하는 UI가 없어 비활성화돼 있다. API/CLI의 worker 구현과 버튼 상태는 별도로 설명해야 한다.

## 기존 API와 현재 화면의 구분

기존 `/dashboard/summary`, `/equipment/status`, `/ai-insights/summary` 등 호환 API가 남아 있어도 현재 화면이 모두 호출하는 것은 아니다. live 장비 상태의 미측정 health와 설치 근거를 구분한다. 데모 값·휴리스틱 점수의 존재를 실제 센서 성능으로 세지 않는다. 서버는 `/qc/run-copilot`, `/qc/ai-insights-summary`, `/test-auto/run`, `/agents/workflow`의 prototype 실행을 demo 모드에 제한한다.

특히 기존 agent workflow의 Human Approval은 승인 대기 표시이며 실행을 중단하는 실제 승인 상태가 아니다. [다중 agent 실행 범위](21_MULTI_AGENT_WORKFLOW.md)와 [AI Insights 계산 경계](20_AI_INSIGHTS.md)를 참고한다.

## 인증·로그·상태 조회

[API client](../ocean-ai-platform/frontend/src/api/client.ts)는 설정된 operator token을 메모리에 두고 Bearer header에 전달한다. 토큰을 frontend 환경변수나 Git에 넣지 않는다. 실제 actor와 reviewer 역할은 [서버 security](../ocean-ai-platform/backend/app/core/security.py)가 판정하며 요청 body의 `user_id`로 승인자를 만들지 않는다. 인증 identity가 없으면 보호된 작업은 503, 잘못된 인증은 401, 권한 부족은 403이다.

[main.py](../ocean-ai-platform/backend/app/main.py)의 CORS는 개발·운영 모두 `CORS_ORIGINS` 목록을 사용한다. 개발 환경 전체 허용으로 설명하지 않는다. `/health`는 프로세스, `/readiness`는 DB 연결을 확인한다. 모델 준비 상태는 `/api/mlops/readiness`, 실제 serving은 `/api/mlops/serving/health`에서 확인한다.

JSON HTTP 요청 로그와 승인 이력은 목적이 다르다. `ApprovalHistory` 및 원천·Dataset·모델의 불변 receipt는 실제 승인과 내용 hash를 결합한다. `AuditLog` 모델이 존재하는 것만으로 모든 HTTP 요청이 DB 감사 기록에 자동 저장되는 것은 아니다. 일반 요청의 영속 감사·운영 보존 정책은 별도 연결이 필요하다.

## 검증과 운영 확인

2026-10-08 공개 작업본은 backend 전체 시험 345개 통과·1개 skip, 깨끗한 `npm ci --ignore-scripts`, TypeScript/Vite `npm run build`가 통과했다. 빌드는 모든 화면의 실제 승인·장애·배포 동작을 현장 검증한 결과가 아니다.

13:09 KST 실제 backend `/health`와 frontend HTTP는 200이었고 API identities는 0이었다. 13:10:55 KST canonical worker는 RUNNING과 fresh heartbeat가 확인됐지만 작업 큐는 비어 있었다. 승인 입력은 없고 모델 readiness는 BLOCKED, 수용 기준은 NOT_DEFINED, serving은 409 NO_ACTIVE_LOCAL_MODEL이었다. 기존 canonical 프로세스의 확인이며 공개 복사본을 기동했다는 의미는 아니다.

실제 운영 검증에는 담당 인증, 원천·기간·사건 검토, 승인 입력, 실패/반려 화면, 모델 실행과 identity 검증이 필요하다. [설치 문서](02_SETUP_AND_INSTALLATION.md), [승인 경로](17_HUMAN_IN_THE_LOOP.md), [현재 진행 상태](24_P0_END_TO_END_PROGRESS.md)를 따른다.
