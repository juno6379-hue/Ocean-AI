# 04. API 명세서 (API Specification)

본 문서는 프론트엔드 UI 대시보드와 통신하는 백엔드(FastAPI) 주요 REST API 엔드포인트를 요약합니다.
(더 자세한 스펙 및 테스트는 백엔드 구동 후 `http://localhost:8080/docs` 에서 Swagger UI로 확인 가능합니다.)

---

## 📊 1. 통계 및 대시보드 (Dashboard)

### `GET /api/dashboard/stats`
메인 통합 대시보드의 최상단 KPI(핵심 성과 지표) 위젯 데이터를 반환합니다.
- **Response (200 OK)**
  ```json
  {
    "stats": [
      { "title": "정상 가동 관측소", "value": "134/138", "trend": "+2", "status": "good" },
      { "title": "품질 경고 (최근 24시간)", "value": "3건", "trend": "-1", "status": "warning" },
      ...
    ]
  }
  ```

---

## 📑 2. 보고서 및 문서 (Reports & Documents)

### `GET /api/reports/list`
Agent가 자동 생성했거나 시스템에 등록된 운영보고서 목록을 조회합니다.
- **Response (200 OK)**
  ```json
  {
    "reports": [
      {
        "id": "REP-001",
        "title": "국가해양관측망_일일상황보고_20260915",
        "type": "상황보고",
        "author": "ReportAgent",
        "status": "대기중",
        "createdAt": "2026-09-15T09:00:00Z"
      }
    ]
  }
  ```

### `POST /api/reports/{id}/approve`
특정 보고서를 검토 후 '최종 승인' 처리합니다.
- **Path Parameter**: `id` (문서 ID)
- **Response (200 OK)**
  ```json
  {
    "message": "Report approved successfully",
    "report_id": "REP-001",
    "new_status": "승인완료"
  }
  ```

---

## 🤖 3. AI 분석 인사이트 (AI Insights & RAG)

### `GET /api/ai-insights/summary`
RAG 및 멀티 에이전트가 도출한 최신 AI 진단 결과 목록을 반환합니다.
- **Response (200 OK)**
  ```json
  {
    "insights": [
      {
        "id": 1,
        "type": "장비 이상",
        "title": "목포 관측소 수온 센서 결측 원인 진단",
        "description": "최근 3일간의 로그와 과거 3년치 점검보고서를 분석한 결과, 통신 모듈 오류 또는 해조류 얽힘으로 판단됨.",
        "confidence": 88
      }
    ]
  }
  ```

### `POST /api/rag/ask`
기 구축된 벡터 DB(ChromaDB) 내의 문헌(운영보고서, 점검일지 등)을 기반으로 자연어 질의응답을 수행합니다.
- **Request Body**
  ```json
  {
    "question": "대조기 침수 위험 시 어떤 절차로 보고해야 하나요?"
  }
  ```
- **Response (200 OK)**
  ```json
  {
    "answer": "대조기 모니터링 매뉴얼(2025년 판)에 따르면, 1차적으로 조위 편차 에이전트가 경고를 발생시키면...",
    "source_documents": ["대조기모니터링보고서_매뉴얼.pdf"]
  }
  ```

---

## ⚡ 4. 자동화 테스트 (Test Automation)

### `POST /api/test-auto/run`
프론트엔드의 '테스트 자동화' 메뉴에서 E2E(End-to-End) 시스템 검증을 수동으로 트리거합니다.
- **Request Body**
  ```json
  {
    "test_type": "E2E"
  }
  ```
- **Response (200 OK)**
  ```json
  {
    "message": "E2E Test Execution Started",
    "job_id": "TEST-JOB-992"
  }
  ```
