# End-to-End 검증 오류 로그

## 2026-09-18

### E2E-001 — APScheduler 미설치

- 증상: `import app.main` 시 `ModuleNotFoundError: apscheduler`
- 원인: 개발 환경에 선택적 스케줄러 패키지가 설치되지 않음
- 조치: `main.py`에서 선택적 import로 변경하고 스케줄러가 없을 때 API가 기동되도록 수정
- 상태: 수정 완료, import 재검증 예정

### E2E-002 — LangChain Chroma 미설치

- 증상: RAG 라우터 import 시 `ModuleNotFoundError: langchain_chroma`
- 원인: 선택적 RAG 패키지가 개발 환경에 없음
- 조치: RAG 지식 에이전트를 lazy import하고, 패키지가 없으면 Hybrid Retrieval로 fallback
- 상태: 수정 완료

### E2E-004 — Python 3.8 타입 문법

- 증상: `list[float]` 타입 힌트에서 `TypeError: 'type' object is not subscriptable`
- 조치: `typing.List`로 변경
- 상태: 수정 완료

### E2E-005 — TestClient 의존성 누락

- 증상: FastAPI TestClient 실행 시 `httpx` 미설치
- 조치: 개발/검증 의존성에 `httpx`를 추가하고 설치
- 상태: 수정 진행

### E2E-006 — 신규 보간 테이블 미생성

- 증상: QC Copilot에서 `relation "observation_imputation" does not exist`
- 원인: 모델 추가 후 기존 PostgreSQL에 migration/create_all 미실행
- 조치: `Base.metadata.create_all`로 신규 스키마 생성
- 상태: 수정 완료, QC Copilot 200 확인

## 최종 샘플 Prompt 결과

Prompt: `DT_0001 조위 결측과 이상 여부를 분석하고 근거 문서와 승인 대상을 제시해줘`

| 흐름 | 결과 |
|---|---|
| `/health` | 200 |
| `/readiness` | 200 |
| `/api/rag/chat` | 200, Hybrid Retrieval 응답 |
| `/api/qc/copilot/analyze` | 200, 분석 전용·승인 필요 응답 |
| `/api/ai-insights/long-term` | 200, 자료 없음 분석 결과 |
| `/api/forecasting/baseline` | 404, 해당 관측소 TIDE 원천자료 없음으로 정상적인 데이터 부재 응답 |

### E2E-003 — LangChain Ollama 미설치

- 증상: SQL Agent import 시 `ModuleNotFoundError: langchain_ollama`
- 조치: SQL/RAG Agent를 lazy import하고 미설치 환경에서는 Hybrid Retrieval로 fallback
- 상태: 수정 완료

### E2E 실행 기록

샘플 Prompt: `DT_0001 조위 결측과 이상 여부를 분석하고 근거 문서와 승인 대상을 제시해줘`

검증 순서: health/readiness → QC Copilot 분석 → Hybrid Retrieval → 승인 대기 → Forecasting 기준선 → AI Insights 장기 추세.
