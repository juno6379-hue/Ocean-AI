# 사건 중심 관측·문서·학습 계보 연결

작성일: 2026-10-02. 요청한 6단계를 기존 API에 점진적으로 추가한다.

## 구현 계약

1. SensorMetadata를 기준으로 관측소·변수를 검증한다. 장비 별칭은 관측소·센서·변수·유효기간·매핑 버전을 가진 검토된 사전으로 관리한다. 후보가 여러 개이면 자동 확정하지 않는다.
2. 보고일은 DocumentIndex.document_date로 유지한다. 사건 기간은 원문 인용과 시간대가 있는 별도 입력으로 등록하며 `[시작, 종료)` 반개구간을 사용한다. 외부 입력은 UTC offset 필수, DB의 기존 naive 시각은 UTC로 해석한다. 열린 사건은 조회·분석만 허용하고 확정 학습 구간에는 쓰지 않는다.
3. EventEvidence에 실제 외래키를 사용해 문서 청크·표준 관측·개별 QC 결과·운영 기록·AI 라벨을 사건에 다대다로 연결한다. 중복 연결을 막고, 역방향 조회 및 근거 본문·버전·체크섬을 제공한다.
4. QC 결과는 검토 후보의 추천 근거다. 자동 생성 라벨은 항상 PENDING, 원인은 기본 unknown이다. 서버 인증 reviewer의 승인만 학습 자격을 부여하며 승인 당시 라벨 내용을 별도로 고정한다.
5. Dataset snapshot에는 승인 라벨·승인 이력·Feature 정의/값/입력 구간·문서 본문 및 사건 근거를 포함한다. QC 최종 Flag를 AI Label로 대체하지 않는다. 미승인·중복 라벨·Feature 누락·미확정 사건·근거 누락은 검증 실패다. 동일 dataset_name을 평가 실험군으로 보며 분할 간 관측소 중복, 시간 순서 역전, 사건·Feature 구간의 분할 경계 침범을 차단한다.
6. 격리 E2E와 실자료 검증을 구분한다. 실자료가 충족되지 않으면 승인이나 사건을 만들어 완료로 표시하지 않는다.

## 착수 시 실측

- ObservationStandard: 4,074건, 2026-09-15 15:00:15~2026-09-18 02:33:45 UTC.
- DocumentIndex: 15,431청크, 확인 가능한 보고일 2024-12-02~2026-01-16. 보고일이 없는 청크도 포함한다.
- SensorMetadata: 2건. 표준 관측의 센서 조합 전체가 등록됐다는 뜻이 아니다.
- EventRegistry, QCRuleResult, OperationLog, AILabel, FeatureValue, DatasetRegistry: 각각 0건.
- 따라서 현재 DB만으로 실사건의 전체 승인 계보 완료를 주장할 수 없다. 보고일이 사건 발생기간과 같다고 가정하거나 과거 날짜를 현재로 옮겨 연결하지 않는다.

## 검증 및 실행 기록

### 구현 결과

| 요청 | 반영 내용 | 실자료 상태 |
|---|---|---|
| 1. 기준정보 공유·장비 매칭 | 기존 StationMetadata/SensorMetadata/MDCItemMapping 조회, reviewer가 등록한 SensorAlias의 유효기간·버전으로 정확 매칭. 여러 후보면 AMBIGUOUS 반환 | 실자료 센서 불일치 조합 9개 확인. 추정 센서를 생성하지 않음 |
| 2. 보고일·사건기간 분리 | 원문 인용과 offset이 있는 사건기간 입력. UTC 변환 후 반개구간 적용. 보고일은 별도 유지. 열린 사건은 원문 근거와 실제 종료시각으로 종료 | 실제 사건기간 입력·검토 필요 |
| 3. 사건 중심 다대다 근거 | EventEvidence의 대상별 FK·유일성·정확히 한 대상 제약. 문서·관측·QC·운영·라벨 역방향 조회 | PostgreSQL 스키마 적용, 실사건 링크는 아직 0건 |
| 4. 검토 후보·승인 | 원문·관측·QC·운영 근거가 있을 때만 PENDING 후보 생성. 원인은 unknown에서 시작. ApprovalHistory 및 LabelReviewSnapshot에 승인 당시 라벨과 근거 고정 | 실제 reviewer 인증 설정과 담당자 검토 필요 |
| 5. Feature·Dataset 계보 | 과거/현재 관측만 이용하는 표준값·60분 평균·표준편차 및 FeatureProvenance 생성. 승인된 AILabel, 정의/값/버전, 원시 관측, 사건·문서 원문을 SHA-256 snapshot에 포함. DatasetMembership 역추적 | 실자료 승인 라벨·Feature·Dataset은 아직 없음 |
| 6. 실사건 양방향 검증 | 격리 자료에서 문서→사건→관측→QC→라벨 승인→Feature→Dataset 승인 및 역방향 검증 통과 | **실사건은 REAL_CASE_NOT_READY, 검증 완료 0건** |

코드 구현 및 격리 검증을 실사건 운영 완료와 구분한다. 원문 기간 해석은 현재 operator의 인용 기반 입력이며 모든 문서에서 사건기간을 자동 추출하는 기능으로 보고하지 않는다. 장비 별칭은 실제 reviewer가 확인해야 한다. 초기 Feature 3종은 관측시각 기준의 오프라인 계산이며 실시간 수신 가용 시각의 완전한 재현이나 Spatial/Operation/Event Feature 전체 구현을 의미하지 않는다. 결측값용 Feature 전략이 없는 관측은 검증을 통과시키지 않는다.

### 검증 결과

- 신규 사건 계보 테스트 13개 + 기존 품질관리·승인 15개 + 문서 파이프라인 8개 = **36개 통과**.
- 검증 항목: UTC offset 필수, 종료 경계 제외, 보고일/사건일 분리, 장비 별칭 모호성, 센서/변수 불일치, 링크 중복 방지·다대다 역추적, reviewer 권한, PENDING 제외, 승인 라벨·원문·Feature·관측 및 파일 변조 탐지, 버전 불일치, 관측소/시간 분할 누수, 열린 사건 종료.
- 기존 테스트 중 QC 승인만으로 학습 가능하다고 가정하던 경로를 변경했다. 이제 사건 근거와 Feature가 없는 레거시 라벨은 Dataset 검증에서 INVALID다. 정상 전체 승인 흐름은 신규 테스트가 검증한다.
- 실 PostgreSQL: 신규 테이블 5개 생성 확인. 재실행 시 생성 0개로 멱등성 확인.
- 실제 DB를 연결한 FastAPI 라우터 읽기 검증 HTTP 200. 별도 실행 중인 기존 백엔드를 재시작하거나 배포까지 완료했다는 의미는 아니다.
- 실자료 점검은 `55_EVENT_EVIDENCE_LIVE_CHECK.json`에 저장했다. 테스트용 사건·담당자·승인 결과는 운영 DB에 넣지 않았다.
- 이번 변경에는 프런트엔드 화면 변경이 없다. 제공 API를 기존 승인·QC 화면과 추가 연결하는 UI 작업은 별도다.

### 오류 기록과 수정

| 발견 오류/불일치 | 조치 |
|---|---|
| PostgreSQL DocumentIndex.chunk_id에 모델 코드와 달리 고유 제약이 없어 FK 생성 실패 | 트랜잭션 롤백 후 중복 키를 점검하고 `uq_document_chunk_evidence` 고유 인덱스를 추가. 원본 삭제 없이 재실행 성공 |
| 레거시 테스트가 사건·Feature 없는 QC 승인 데이터를 VALIDATED로 기대 | 새 AI Label 분리 계약에 맞춰 INVALID를 검증하도록 변경. 별도의 전체 계보 성공 테스트 추가 |
| 미승인 관측을 snapshot에서 제외하면 제외된 관측 변경이 해시에 반영되지 않음 | 전체 선택 관측의 selection_hash를 포함해 재빌드 시 변화를 추적 |
| 승인 후 원문 근거가 바뀌어도 라벨 값만 같으면 승인으로 간주할 위험 | 승인 시 라벨뿐 아니라 사건·문서·관측·QC·운영 근거를 고정하고 재검증 |

기존 Pydantic 설정 및 datetime.utcnow 사용에 대한 비권장 경고는 남아 있으며 테스트 실패는 아니다.

## API 순서

쓰기 요청에는 설정된 operator 토큰, 별칭 확정과 승인에는 reviewer/admin 토큰이 필요하다. 토큰은 문서·소스·로그에 저장하지 않는다.

1. `GET /api/events/reference-catalog?station_id=...` — 실제 관측소·센서·변수 매핑 확인.
2. `POST /api/events/sensor-aliases` — reviewer가 station_id, sensor_id, variable_code, alias_text, mapping_version, valid_start/end를 등록.
3. `POST /api/events/resolve-sensor` — station_id, variable_code, expression, event_start/end로 매칭 상태 확인.
4. `POST /api/events/from-document` — chunk_id, 장비 표현과 관측소/변수, event_start/end, event_type, period_quote 입력. 보고서의 운영 기록을 함께 전사할 때는 operation_quote와 operation_time을 모두 제공. 전사 기록은 DOCUMENT_RECORD이며 실제 조치를 시스템이 수행했다는 의미가 아니다.
5. `POST /api/events/{event_id}/close` — 열린 사건을 원문 source_quote와 실제 event_end로 닫음. 이미 종료됐거나 라벨이 연결된 사건을 덮어쓰지 않음.
6. 기존 `POST /api/qc/rules/execute`로 해당 관측의 개별 검사 결과 생성 후 `POST /api/events/{event_id}/link-observations` 실행. 최대 10,000건이며 초과 시 구간을 좁히도록 오류 반환.
7. 추가 근거는 `POST /api/events/{event_id}/evidence`에 kind/target_id로 연결. DOCUMENT는 정확한 원문 quote 필수.
8. `POST /api/events/{event_id}/label-candidates`에 label_version 지정. 실제 담당자가 `/api/approvals/modify`, `/approve`, `/reject`, `/comment`로 검토. approve에서 임의 변경을 함께 전달하지 않고 modify 이력을 먼저 남김.
9. `POST /api/events/{event_id}/features` — `event-causal-1` Feature 생성. 기존 값의 입력이 바뀌면 새 버전을 요구.
10. `/api/datasets` 등록 → `/{id}/build` → `/validate` → reviewer `/approve`. `dataset_name`이 같은 실험군에서는 TRAIN→VALIDATION→TEST→BLIND_TEST 시간 순서와 관측소 분리를 동시에 강제. RETRAINING_POOL은 별도 후보군이며 평가 분할로 사용하려면 다시 검증.

조회:

- `GET /api/events/{event_id}/lineage`: 사건에서 원문·관측·검사·운영·라벨·Dataset으로 추적.
- `GET /api/events/evidence/{kind}/{target_id}`: DOCUMENT / OBSERVATION / QC_RESULT / OPERATION_LOG / AI_LABEL에서 사건으로 역추적.
- `GET /api/events/feature-lineage/{observation_id}/{feature_id}/{feature_version}`: Feature 입력과 관련 Dataset 조회.
- `GET /api/datasets/{dataset_id}/lineage`: 고정 snapshot 파일의 해시를 확인한 뒤 원문까지 반환하고 Dataset 승인 이력 제공.

## 적용 명령 및 실사건 확대 조건

프로젝트 루트에서:

```powershell
$env:PYTHONPATH = 'backend'
python -m app.scripts.migrate_event_evidence
python -m app.scripts.verify_event_evidence_live --output docs/55_EVENT_EVIDENCE_LIVE_CHECK.json
```

기존 데이터는 변경하지 않는 추가형 마이그레이션이다. FK 참조 키가 중복되면 자동 삭제하지 않고 적용을 중단한다. PostgreSQL 잠금 대기는 5초로 제한한다. 이전 라벨에 승인 스냅샷이 없으면 승인 이력을 소급 생성하지 않으며 별도 검토가 필요하다.

현재 실사건 확대의 전제는 (1) 9개 센서 조합의 실제 기준정보 확인, (2) 원문으로 확인한 사건기간과 같은 시기의 원시/표준 관측 확보, (3) 운영·QC 근거 연결, (4) 실제 reviewer 인증 및 승인이다. 보고일 불일치만으로 사건기간 불일치를 단정하지는 않지만, 사건기간이 확인되지 않은 문서를 현재 관측에 강제로 연결하지 않는다.
