# Event Registry API

`EventRegistry`는 이상징후, 장비·통신 장애, 자연현상 등 운영 이벤트를 관측소·센서·변수와 시간 구간으로 추적한다. 이벤트는 자동 확정 판정이 아니라 `source_type`과 `status`를 가진 분석·운영 기록이다.

## Endpoints

- `GET /api/events`: station/event type/status 필터와 최신순 조회
- `POST /api/events`: 이벤트 등록 (`event_type`, `event_start` 필수)
- `PATCH /api/events/{event_id}/status?status=RESOLVED`: 상태 변경. 종료 상태이고 종료 시각이 없으면 현재 시각을 기록한다.

이벤트 ID는 서버가 `EVT-<uuid>`로 생성하며 모든 응답은 `is_demo=false`인 실제 DB 데이터다. 이후 QC Copilot과 Agent workflow는 이 ID를 근거 문서·승인·보고서와 연결한다.
