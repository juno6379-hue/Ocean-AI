# Ocean-AI: 해양관측 원천·근거·모델 실행 플랫폼

관측 수치, 문서와 사건 근거, QC, 검토 라벨, dataset, 모델 실행의 관계를 보존하는 플랫폼이다. 실제 원천과 승인 기록을 연결해 검증하고, 모델 비교·등록·배포가 필요한 조건을 갖췄는지 확인한다.

**현재 구현과 운영 상태는 [현행 문서 안내](docs/README.md)에서 확인한다.** 2026-10-08 QC12종·fitted anomaly6모드·Evidence Fusion·PostgreSQL stop/resume 승인 gate를 추가했으며 최종 시험과 웹 실행 결과는 현행 문서에 기록한다. 운영 DB의 원천 승인·dataset·학습 이력·model registry는 모두 0건이고 운영 모델도 0개다. 기존 작업본의 worker가 실행 중이어도 승인된 학습 입력이 없으면 모델을 생성하지 않는다. 72개 업무 키는 자료형 기준선의 부분 구현이며 업무별 운영 모델 72개 완료를 뜻하지 않는다.

10/8 단계별 보완은 [13단계 실행·최종 검증](docs/29_DEVELOPMENT_STAGE_EXECUTION.md)에 기록했다. 최종 backend668·frontend17시험과 PostgreSQL48테이블 backup/restore를 통과했다. System에 단계별 상태, MLOps에 legacy→새 v2·고정 정책·승인 입력 검토를 연결했다. 문서1,842경로를 전수 검사하고81개/8,761chunks를 별도 복구했으며 남은705개 임베딩과 원천 사실·실제 운영 승인을 미완료로 구분한다. 현황 기본월은2026-07이고 [월간보고서 대조](docs/27_JULY_REPORT_PARQUET_MATCH.md)와 [지표 보완](docs/28_METRIC_COMPLETION.md)을 따른다.

## 구현 범위

- 원문/Parquet hash와 행·열 locator, 의미·단위·시간대·QC·센서 유효기간을 재검증하는 source 계약·인증된 판정·불변 영수증.
- 승인된 원천 ingest와 observation binding, 사건·문서·QC·라벨의 근거 관계, feature as-of 검증.
- 원천 의존성을 동결하는 v2 dataset snapshot, 고정 train/validation/test 및 평가·수용 계약.
- 6종 자료형·3종 업무 알고리즘의 비교 기준선, 학습 큐·worker, 독립 재현 검토, registry, 승인된 loopback serving·배포·rollback 연결.
- 버전 contract를 사용하는 문서 수집·색인·검색과 React 대시보드의 미확정·빈 상태·오류 표시.

새 영속 workflow는 PENDING에서 멈추고 reviewer 결정 후 별도 resume한다. 승인 후에도 보고서 초안과 MLOps 추천이며 실제 source/dataset/model 승인·학습·배포를 대신하지 않는다. 기존 AI Insights 휴리스틱은 fitted anomaly와 별도다. 원천 의미 확정, 미연결 사건·기간 충돌 판정, 업무별 원천 비교와 운영 성능 수용은 실제 담당 근거와 승인 후 수행해야 한다.

## 저장소 구조

```text
Ocean-AI/
├── docs/                     # 현행 설치·API·계층·승인·운영 상태 문서
├── ocean-ai-platform/
│   ├── backend/              # FastAPI·SQLAlchemy·PostgreSQL, ML·문서 실행 코드와 시험
│   ├── frontend/             # React·TypeScript·Vite UI
│   └── docs/                 # 상세 구현과 날짜별 과거 실행 기록
└── process.md                # 기존 업무 절차 참고 자료
```

운영 원문·Parquet·DB·Chroma 저장소·검토 패킷·승인 영수증·model artifact는 별도 보존·설정한다. clone으로 운영 자료나 승인이 생성되지 않는다. `.env`, 실제 비밀번호 및 사용자 token은 Git에 저장하지 않는다.

## 읽기 및 실행 순서

1. [전체 문서와 현재 상태](docs/README.md)
2. [시스템 아키텍처](docs/01_SYSTEM_ARCHITECTURE.md)
3. [설치 및 실행](docs/02_SETUP_AND_INSTALLATION.md)
4. [API 명세](docs/04_API_SPECIFICATION.md)
5. [현재 단계와 다음 작업](docs/24_P0_END_TO_END_PROGRESS.md)

backend 예제의 `POSTGRES_PASSWORD`는 Docker Compose용이며 `Settings` 필드가 아니다. 예제 전체를 backend `.env`로 그대로 복사하면 validation 오류가 발생할 수 있다. [설치 문서](docs/02_SETUP_AND_INSTALLATION.md)의 분리 절차로 서버 설정과 Compose 비밀번호를 준비한다. 자동 MDC 동기화와 자동 전체 DDL은 기본 꺼져 있다. 데이터 경로나 기존 인덱스를 바꾸기 전에 보존된 contract와 적용 스키마를 확인한다.

[저장소](https://github.com/juno6379-hue/Ocean-AI) · [상세 source/model 연결 구현](ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)
