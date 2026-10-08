# AI 기반 해양관측 업무혁신 플랫폼 (Ocean AI Platform)

본 프로젝트는 국가해양관측망 운영 과정에서 발생하는 방대한 양의 **정형 데이터(센서 관측 수치)**와 **비정형 데이터(운영 보고서, 점검 일지 등)**를 하나로 융합하여 업무를 지능적으로 자동화하는 플랫폼입니다.

## 🌟 주요 특징

1. **정형·비정형 데이터 융합 분석**
   - 수온, 염분, 조위 등의 실시간 센서 데이터 이상 징후 감지.
   - 자연어 처리(NLP)를 통해 과거 운영 보고서, 점검 일지에서 장애 원인 및 조치 이력 추출.
   - 현장 수치와 과거 문헌을 동시에 분석하여 입체적인 장애 진단 제공.

2. **문서 기반 RAG (Retrieval-Augmented Generation)**
   - 6종 이상의 국가해양관측망 운영보고서를 데이터베이스화하고 벡터로 인덱싱.
   - 단순 파일 검색이 아닌 맥락(Context) 기반 검색으로 질문에 대한 해답과 근거를 즉시 제공.

3. **Multi-Agent 자율 워크플로우**
   - **ReportAgent**: 과거 이력과 현재 상황을 종합해 조치 보고서 초안을 자동 작성.
   - **ServiceMonitoringAgent**: 관측망 API 통신 상태, 레이턴시, 오류 코드를 실시간 모니터링하여 알림 생성.
   - **TideResidualAgent**: 천문조와 실관측 조위 편차를 분석해 폭풍해일 및 침수 위험 조기 경보.
   - **DailyInspectionAgent**: 현장 담당자가 올린 비정형 일일 점검 로그에서 실제 Alert를 추출하여 자동 티켓팅.

4. **프리미엄 대시보드 UI**
   - 담당자가 한눈에 관측망 전체 상태를 파악할 수 있는 통계 뷰.
   - AI가 작성한 보고서를 결재하고 승인하는 직관적인 워크플로우 화면 제공.

## 📂 저장소 구조

```text
C:\AI_Observation
├── ocean-ai-platform/
│   ├── backend/        # FastAPI, LangChain, SQLite, ChromaDB 기반 AI 백엔드
│   └── frontend/       # React, Vite, TailwindCSS 기반 사용자 대시보드
├── docs/               # 상세 기술 문서 및 설치 가이드 (이곳부터 읽어주세요)
└── README.md
```

## 📖 문서 가이드

프로젝트 이해 및 실행을 돕기 위해 상세한 문서가 준비되어 있습니다. 
아래 순서대로 읽으시는 것을 권장합니다.

1. **[시스템 아키텍처 (01_SYSTEM_ARCHITECTURE.md)](docs/01_SYSTEM_ARCHITECTURE.md)**
   - 플랫폼의 전체 구조도, 기술 스택, 데이터베이스 및 AI 엔진 설계 개요.
2. **[설치 및 실행 가이드 (02_SETUP_AND_INSTALLATION.md)](docs/02_SETUP_AND_INSTALLATION.md)**
   - 로컬 및 운영 환경에서 프론트엔드/백엔드 서버를 띄우기 위한 A to Z 가이드.
3. **[AI Agent 워크플로우 (03_AGENT_WORKFLOW.md)](docs/03_AGENT_WORKFLOW.md)**
   - Multi-Agent 시스템이 데이터를 어떻게 수집, 판단, 조치하는지에 대한 원리 설명.
4. **[API 명세서 (04_API_SPECIFICATION.md)](docs/04_API_SPECIFICATION.md)**
   - 클라이언트(프론트엔드)에서 호출 가능한 주요 REST API 엔드포인트 목록 및 페이로드 스펙.

---
**유지보수 담당자 노트**: 코드를 수정하거나 새로운 에이전트를 추가하실 때는 반드시 기존 워크플로우에 영향을 주지 않도록 단위 테스트(E2E)를 먼저 수행하시기 바랍니다.
