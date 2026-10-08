# Frontend 연결 및 운영 보강

작성일: 2026-09-16

## 화면별 연결 상태

| 화면 | 연결 상태 |
|---|---|
| Dashboard | `/api/dashboard/summary`, `/api/dashboard/performance`, QC·보고서 API 사용. 일부 차트·수집률은 백엔드 고정/Mock 계산이다. |
| QCCopilot | `/api/qc/summary`, `/api/qc/alerts`, `/api/qc/run-copilot` 사용. Copilot 탐지·정확도에는 Mock/랜덤 로직이 남아 있다. |
| AIInsights | `/api/ai-insights/summary`로 전환했다. 위험도·추세·재학습 추천은 분석 전용 응답으로 표시한다. |
| MLOps | `/api/mlops/summary`, `/api/mlops/retrain-history`, `/api/mlops/retrain` 연결. 모델 등록·데이터셋 Registry는 API가 준비되어 있으며 화면 등록 UI는 후속 작업이다. |
| Reports | `/api/reports/list`, `/api/reports/stats`, 생성·승인 API 사용. 승인 요청에 `user_id`와 comment를 포함하도록 수정했다. |
| Equipment | `/api/equipment/status` 사용. 장비 health·원인·티켓은 아직 Mock이며 응답에 `is_demo=true`를 표시한다. |
| Alerts | 기존 Alert와 `/api/alerts/events`의 AI anomaly/OperationLog 이벤트를 분리 제공한다. |

## 운영 보강

- 개발 환경은 CORS 전체 허용, 운영 환경은 `CORS_ORIGINS` 환경변수 목록만 허용
- `.env.example` 추가: DB, 환경, CORS, 로그 레벨 설정
- `/health`: 프로세스 상태
- `/readiness`: PostgreSQL 연결 상태
- JSON 형태 HTTP 요청 구조화 로그와 전역 500 예외 처리 추가
- `audit_log` 테이블 추가. 승인 변경은 기존 `ApprovalHistory`에 기록하며, 일반 운영 감사 이벤트는 후속 요청 처리기에 연결할 수 있다.
- 기존 수동 마이그레이션 스크립트(DocumentIndex, MLOps 등)를 유지하고 모델 테이블을 생성·검증했다.

남은 Mock은 API 응답의 `is_demo` 또는 코드상 분석 상태로 식별되며, 실제 센서 운영 로그·장비 health·실시간 집계 연결 시 해당 플래그를 제거한다.
