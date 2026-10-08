# 01. 시스템 아키텍처 (System Architecture)

본 플랫폼은 프론트엔드, 백엔드, AI/데이터베이스 계층으로 나뉘며, 각 계층이 독립적이면서도 유기적으로 통신하도록 설계되었습니다.

## 🏗️ 전체 시스템 구성도

```mermaid
graph TD
    %% 프론트엔드 영역
    subgraph Frontend [프론트엔드 (React / Vite / Tailwind)]
        UI[웹 대시보드 UI]
        Dash[통합 대시보드]
        ReportUI[보고서 및 문서 관리]
        QCUI[품질 현황 모니터링]
        UI --> Dash
        UI --> ReportUI
        UI --> QCUI
    end

    %% API 및 백엔드 라우팅 영역
    subgraph Backend [백엔드 API (FastAPI)]
        Router[API 라우터]
        AgentOrch[에이전트 오케스트레이터 (Orchestrator)]
        Router --> AgentOrch
    end

    %% AI 및 멀티 에이전트 영역
    subgraph Agents [멀티 에이전트 시스템 (Multi-Agent)]
        ReportA[보고서 생성 에이전트]
        TideA[조위 편차 분석 에이전트]
        DailyA[일일 점검 분석 에이전트]
        MonitorA[서비스 모니터링 에이전트]
        QCA[품질 관리 에이전트]
        
        AgentOrch --> ReportA
        AgentOrch --> TideA
        AgentOrch --> DailyA
        AgentOrch --> MonitorA
        AgentOrch --> QCA
    end

    %% 데이터베이스 및 LLM 계층
    subgraph Data_Layer [데이터 및 AI 엔진]
        SQL[(SQLite: 정형 데이터)]
        VDB[(ChromaDB: 비정형 벡터)]
        LLM((Ollama / LLM))
        Embed((Embedding Model))
    end

    %% 데이터 흐름 연결
    Frontend -- REST API --> Backend
    ReportA -.-> SQL
    ReportA -.-> VDB
    TideA -.-> SQL
    DailyA -.-> LLM
    DailyA -.-> VDB
    VDB -.-> Embed
    AgentOrch -.-> LLM
```

## 🛠️ 주요 기술 스택

### 1. 프론트엔드 (Frontend)
- **프레임워크**: React (Vite 빌드 도구 사용)
- **스타일링**: Tailwind CSS, Lucide Icons
- **특징**: SPA(Single Page Application) 형태로 빠르고 반응성 높은 UI를 제공하며, 프리미엄 UI 디자인 원칙을 준수합니다.

### 2. 백엔드 (Backend)
- **프레임워크**: FastAPI (Python 3.10+)
- **특징**: 비동기(Asynchronous) 처리에 특화되어 대량의 센서 데이터 통신 및 다중 에이전트의 LLM 요청을 병목 없이 처리합니다.

### 3. AI 및 데이터베이스 (Data & AI Layer)
- **LLM 엔진**: Ollama 기반 로컬 LLM (데이터 보안 강화 및 사내 구축 용이)
- **RAG 파이프라인**: LangChain 프레임워크를 활용하여 문서 청킹, 임베딩(`jhgan/ko-sroberta-multitask`), 유사도 검색 구현
- **정형 데이터 DB**: SQLite (추후 PostgreSQL/Oracle 등으로 마이그레이션 용이하도록 SQLAlchemy ORM 적용)
- **비정형 벡터 DB**: ChromaDB (오프라인 환경에서도 동작 가능한 로컬 벡터 DB)

## 🔄 핵심 데이터 흐름 (Data Flow)

1. **데이터 수집**: 센서 데이터(수온, 조위 등)는 정형 DB(SQLite)에 실시간으로 적재됩니다.
2. **문서 인덱싱**: 담당자가 업로드한 일일보고서 등의 텍스트는 LangChain에 의해 청크(Chunk)로 나뉘어 임베딩을 거쳐 ChromaDB에 벡터로 저장됩니다.
3. **사용자 요청**: 사용자가 대시보드에서 "최근 1주일간 발생한 수온 이상 원인 분석해줘"라고 요청합니다.
4. **오케스트레이션**: FastAPI 백엔드의 `Orchestrator`가 요청의 맥락을 분석하여 **품질 관리 에이전트(정형)**와 **보고서 분석 에이전트(비정형)**에 작업을 분배합니다.
5. **RAG 및 융합**: AI가 벡터 DB에서 과거 유사 사례를 찾고, 정형 DB에서 실제 수온 급변 시점을 매칭하여 종합 결론을 생성합니다.
6. **결과 응답**: 종합된 결과가 UI로 반환되어 사용자에게 텍스트, 차트, 보고서 초안 형태로 시각화됩니다.
