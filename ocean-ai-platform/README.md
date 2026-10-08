# Ocean AI Platform

기준일: **2026-10-08**. 현재 설치·API·운영 판정은 저장소 루트의 [현행 문서 안내](../docs/README.md)를 기준으로 확인한다.

FastAPI·SQLAlchemy 백엔드와 React·TypeScript·Vite 프런트엔드가 관측 수치, QC, 문서·사건 근거, 검토 라벨, dataset과 모델 실행을 연결한다. PostgreSQL은 운영 계보·승인 원장, Parquet는 실측 수치 조회, Chroma는 문서 vector 색인을 담당한다. SQLite는 격리 시험과 로컬 학습 큐에 사용한다.

## 현재 범위

- source 계약과 인증된 판정, 원문·Parquet locator/hash 및 의미·시간·QC·센서 기간 검증.
- 승인 source ingest·관측 binding과 v2 dataset snapshot 의존성 동결.
- 고정 split/evaluation/acceptance 계약, 자료형별 비교 기준선, fenced worker와 독립 재현 검토.
- candidate registry, 승인된 배포 identity, loopback JSON serving·실패 복원·rollback.
- 문서 contract에 따른 수집·파싱·vector 색인 및 키워드/vector 검색, 실 API 기반 UI.

72개 업무는 `REPRESENTATION_BASELINE_SCOPE_PARTIAL`이다. 6종 자료형·3종 업무 알고리즘의 구현을 72개 업무별 운영 모델 완료로 해석하지 않는다. prototype agent 흐름과 휴리스틱 Insights는 승인된 모델 실행과 별도다.

2026-10-08 읽기 전용 확인에서 원천 계약·승인·dataset·학습 이력·model registry는 0건, 운영 모델도 0개다. canonical 작업본의 worker가 실행 중이고 queue는 비어 있다. 서빙 health의 `409 NO_ACTIVE_LOCAL_MODEL`은 현재 상태에 맞는 차단 응답이다. 자세한 완료 조건은 [현재 단계와 다음 작업](../docs/24_P0_END_TO_END_PROGRESS.md)을 확인한다.

## 구성

```text
ocean-ai-platform/
├── backend/
│   ├── app/api/          # 조회·계약·판정·dataset·모델 실행 API
│   ├── app/services/     # 원천·snapshot·계보·검토 서비스
│   ├── app/ml/           # adapter, 비교, protocol, queue, registry, serving
│   ├── app/rag/          # 문서 contract, 파싱, 색인·검색
│   ├── app/scripts/      # 명시적 migration·batch·worker CLI
│   └── tests/            # 운영 DB와 분리한 회귀 시험
├── frontend/             # 실제 API, 인증 세션, 미확정·오류·빈 상태 UI
├── docs/                 # 상세 구현과 날짜별 실행 기록
└── docker-compose.yml    # PostgreSQL만 실행
```

## 설치·검증

[설치 및 실행 문서](../docs/02_SETUP_AND_INSTALLATION.md)에 Windows PowerShell 명령, 런타임 요구 사항, PostgreSQL 스키마와 외부 자료 경로를 정리했다. backend `.env.example`의 `POSTGRES_PASSWORD`는 Compose용이므로 `Settings`가 읽는 backend `.env`에서 제외한다. `API_IDENTITIES`에는 실제 담당자별 역할·token을 서버에 설정하며 frontend 환경변수나 Git에 token을 넣지 않는다. `MDC_SYNC_ENABLED`와 `AUTO_CREATE_TABLES`는 기본 `false`다.

backend에서 격리 시험 `python -B -m pytest tests -q -p no:cacheprovider`, frontend에서 lock 기반 `npm ci --ignore-scripts`와 `npm run build`를 실행한다. 게시 구현 검증은 **345 passed / 1 skipped**, clean install 및 production build 통과다. 데이터와 운영 승인은 별도로 검증한다.

기존 문서 색인을 사용하려면 `start_web_local.ps1 -Service Backend -DocumentDataRoot <verified-root>`에 검증된 `document_pipeline/contract.json` 경로를 전달한다. 이 launcher는 contract가 없으면 중단한다. 빈 대체 인덱스를 만들어 기존 문서 실행을 덮어쓰지 않는다. 직접 backend 실행과 schema 준비는 설치 문서를 따른다.

## AI·문서 경계

Ollama chat 설정은 [ollama_client.py](backend/app/llm/ollama_client.py)의 `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`을 사용한다. 이 legacy client의 모델 조회 실패는 표시된 `MockOllama` 응답으로 이어질 수 있으며 실제 생성 성능이나 운영 승인 근거가 아니다. 문서 pipeline의 embedding/model contract와 legacy [embedder_factory.py](backend/app/rag/embedder_factory.py)의 기본값은 별도다. 실제 색인 시 등록된 contract의 모델·차원·vector 성공 상태를 검증한다. OpenAI embedding 선택은 현재 legacy factory에서 `NotImplementedError`다.

실제 원문·Parquet·DB·Chroma·검토 패킷·승인 영수증·학습 산출물은 외부 보존 대상이다. 과거 fixture나 보고서 파일이 Git에 존재해도 승인된 운영 데이터가 되지는 않는다. [상세 source/model 연결 구현](docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)과 [문서 기록 안내](docs/README.md)를 참고한다.
