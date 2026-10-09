# 36. 품질 현황 운영 대시보드 개발과 검증

기준: 2026-10-09. [사용자 요구사항 19개 영역](35_QC_OPERATIONAL_DASHBOARD_REQUIREMENTS.md), [목적별 데이터셋·모델 준비도 검토](34_PURPOSE_DATASET_MODEL_READINESS_REVIEW.md).

후속 개발: 사용자가 직접 조작하는 별도 [QC 샘플 검증 모드](37_QC_SAMPLE_VALIDATION_MODE.md)를 추가한다. 이 문서의 시험 수치와 원본 대조는 운영 대시보드 release `634c324`의 기록으로 보존하며, 샘플 모드의 최신 검증은 37번 문서에 따로 기록한다.

**목표는 오늘의 1차 QC 문제를 찾고 담당자의 우선 검토와 상세 근거 확인으로 연결하는 화면이다.** 오늘 단위 집계·우선 검토 큐·실제 시계열 상세·저장 AI·장비와 Evidence·기존 workflow 연동을 구현했다. 코드 동결 후 독립 회귀·실제 원본 대조·브라우저 검증을 통과했다. 상세 증거는 [검증 JSON](36_QC_OPERATIONAL_DASHBOARD_VERIFICATION.json)에 남긴다. 기능 구현과 실제 원천·QC·운영 모델 산정의 완료는 구분한다.

## 1. 현재 코드와 실행 근거

프런트엔드는 React·TypeScript의 QC 전용 Workspace·차트·사례 컴포넌트이며, 기존 다른 페이지의 AnalysisWorkspace를 유지한다. FastAPI의 `/api/qc/workspace`는 보존 Parquet의 월·관측소·항목·해역·관측망·동일 native 기준시각을 집계한다. PostgreSQL QC·AI·workflow 원장은 읽기 전용으로 확인한다.

| 확인한 사실 | 현재 근거 | 개발에 미치는 영향 |
|---|---|---|
| 실제 2026-07-09 00:00~15:41:20 보존 원천 | 143개 Parquet에서 당일 541,426행, 610개 관측소×항목 조합. 7/1~동일 cutoff는 7,126,689행 | 과거 원문 재현이며 현재의 실시간 수신량이 아니다 |
| 실제 원문 QC | OK·GR·GD·NQ·SP, MQ·N1 literal과 공백·NULL을 그대로 보존 | source 코드북/판본·센서 구간이 연결되기 전에는 승인 GOOD/SUSPECT/BAD로 바꾸지 않는다 |
| 기존 백엔드 1차/최종 QC 정의 | 1=정상, 3=Suspect, 4=BAD, 9=결측 | 첨부 이미지의 0/1/3/4/9 예시와 다르므로 이미지 숫자로 기존 의미를 바꾸지 않는다. API catalog를 화면 전체에 적용한다 |
| 진도 수온 | 당일 942행, 7/1~cutoff 12,459행. 후자 원문 SP 3행, 최신 15:41:00의 원시 숫자 21.38 | 원문 SP 3행을 확정 이상 3건으로 표시하지 않는다 |
| QC 등록 결과/이력·AI prediction/label·workflow/approval | 2026-10-09 읽기 전용 확인에서 모두 0 | 실제 큐·저장 AI·검토 이력은 없음으로 구분한다 |
| 승인 source/dataset/model | 모두 0 | 물리 QC·운영 모델 성능의 완료 근거는 아직 없다 |
| DB ObservationRaw | 13,621행, 모두 2026-09 SIMULATED source | 실제 운영 Overview의 수신량·정상률에 합산하지 않는다 |
| 개발 시험 모델 | 8011의 기압·수온·염분 next-row PERSISTENCE 3개 | 7월 후반 자료로 선택했으므로 7월 9일 당시 AI로 사용하지 않는다 |

최종 동결 회귀는 **backend 1,001 passed / 1 skipped / 실패 0(360.36초), frontend 104 passed / 실패 0, TypeScript·Vite build PASS**다. 제외 1개는 Windows symlink 생성 권한 제한이며 별도 reparse-flag 방어 시험은 통과했다. 이번 backend 경고 18개와 기존 frontend lint 경고 12개를 기록하며 신규 QC lint 경고는 0이다. backend 집중 124개와 peer 독립 28개는 전체 회귀와 중복되므로 합산하지 않는다. 통합 회귀 첫 실행의 899 pass·1 fail·1 skip은 실행 중 기간 codec의 SHA 변경으로 실패한 과거 시도이며, 동결 후 전체 회귀 결과로 대체했다. 백엔드 전체 회귀 중 UI의 연속 필터 수정은 독립 진행했으며, 백엔드 271개 파일의 전후 SHA 불변을 별도로 검증했다. UI 최종 동결 뒤 프런트엔드 전체 회귀·build를 다시 실행했고 최종 소스 362개 파일의 SHA가 동일했다. 생성된 tests/.work 자료는 소스 동결 대상과 Git에서 제외했다.

## 2. 역할과 소유 범위

| 담당 | 목표 | 코드 소유 범위 | 완료와 교차 검토 기준 |
|---|---|---|---|
| station_photos 에이전트 | 운영 시계·단일 조회 window·Overview 집계·성능 | qc_overview 서비스, workspace router의 context/overview, 관련 테스트 | 오늘 hourly/7·30일 daily, 동일 분모, source/available 시각·Flag 권위, SQL/Parquet bounded query. 상세 에이전트와 queue 계약 대조 |
| ui_data_review 에이전트 | 실제 후보 상세·저장 AI·센서/운영/문서·workflow 근거 연결 | qc_candidate_review 서비스·독립 candidate router·관련 테스트 | 정확 source/row/sensor/시각 일치, ±2시간 실제값·gap/late, AI 존재/없음, 승인 gate·반려·revision/hash 검증. Overview 에이전트와 ID/Flag 계약 대조 |
| ui_values_graphs 에이전트 | 오늘 운영 UX·동기화·검토 Drawer·화면 상태 | QC 전용 Workspace/Charts/Review/data/CSS/tests | 첨부 톤의 6카드·3×2 패널, presets·filter 전체 동기화, backend Flag catalog, 실제 후보 상세, loading/empty/error/partial·권한 상태. 두 backend 계약 검증 |
| 루트 | 요구사항 정리·통합·독립 최종 검증·실행·Git | 공통 Layout/main·문서·검증 근거·시험 서버 | 전체 회귀·브라우저 실제 동작·원본/집계 대조·성능·변경 파일과 제한 확인, 승인된 GitHub 저장소로 커밋·푸시 |

서로 다른 에이전트가 같은 파일을 동시에 수정하지 않는다. API payload·window·candidate identity는 먼저 합의하고, 변경점과 오류는 서로 전달한다. 실제 원천/운영 DB 수정, 임의 QC·AI 결과 생성, 새 실제 학습·배포, 운영 계정 설정은 이 개발의 대체 수단으로 사용하지 않는다.

## 3. 화면과 데이터 계약

새로 진입한 `/qc`의 기본은 backend에서 확인한 운영 시계의 오늘 00:00부터 현재까지다. 오늘·어제·최근 7일·최근 30일·사용자 지정은 하나의 window를 사용한다. 관측 현황에서 명시적으로 전달한 2026-07-09 native 기준시각은 과거 재현으로 유지하고 실제 오늘이라고 부르지 않는다. naive 보존 시계를 UTC/KST로 추정해 바꾸지 않는다.

운영 Overview는 실제 등록 관측/QC를 사용하고 SIMULATED 원천을 제외한다. 보존 Parquet는 별도 원천 확인 모드다. QC 의미나 실제 수신시각이 없으면 해석 불가·미연결로 표시한다. 데이터 없음, 평가 미실행, 모델 없음, Evidence 없음, 부분 자료, API 오류, 승인 완료는 다른 상태다.

상단·도넛·hourly/daily 추이·Rule 집계·Heatmap·priority queue는 같은 기간·source·station/item·available cutoff를 사용한다. 원문 값에 예측값이나 보간값을 쓰지 않는다. 실제 candidate를 BAD→SUSPECT→최근 순서로 선별하고, 원문 표본은 분리한다. Row 선택은 상세 Drawer로 이어져 실제 관측값, Rule, 저장 AI, 센서 epoch, 운영·점검·문서 근거, 담당자 처리 이력을 보여준다.

하루 61개 관측소×10항목×1,440분은 약 878,400행이다. 상세 표본/검토 큐 상한을 전체 KPI 집계 상한으로 쓰지 않도록 SQL 집계·권위 검증의 경계를 검토한다. 안전하게 전수 검증할 수 없는 범위는 `PARTIAL`과 상한·원래 모집단·제외·미산정 값을 반환하고 전체 정상률로 표시하지 않는다. cold와 warm 응답 성능도 구분해 측정한다.

운영 집계는 `timestamp_utc`·`observation_id` keyset으로 500행씩 전수 순회하며 승인 source·원본 값·Rule 판본을 검증한다. receipt와 Rule definition cache는 한 요청에만 사용하고 끝에서 다시 검증한다. PostgreSQL 요청은 `REPEATABLE READ READ ONLY` snapshot을 사용한다. 상세 표본의 10,000행 상한을 Overview 전체 분모에 적용하지 않는다. 현재 격리 10,501행 시험에서 전수 정산·500행 batch·queue pagination을 검증했으며 실제 878,400행의 성능을 검증한 것으로 확대하지 않는다. 40초 시간 예산이나 검증 제외가 발생하면 부분 자료이며 비율과 전체 queue 건수는 null이다.

선택 기간의 실제 linked workflow를 이용해 승인 대기/처리 완료를 집계하며 global 원장 전체 건수를 선택 기간의 성과로 표시하지 않는다. 보존 원천 전체 조회의 첫 최적화 시험은 메모리 상한 오류가 있었지만, 기간 선필터·GROUPING SETS 집계로 보완 후 당일 541,426행과 7/1~cutoff 7,126,689행의 독립 Arrow 대조를 통과했다. 최종 코드로 서버를 재시작한 뒤 서해 첫 조회는 11.2377초, warm 조회는 0.3166초였다. 별도 격리 이전 코드 cold 28.396초와 전체 의미 비교를 남겼으며, 모든 기간·모집단에서 10초 목표 달성을 검증한 것은 아니다.

기존 승인 source 계약은 유한 scalar 값의 정산을 전제로 하므로 값이 없는 예정 관측 슬롯을 등록하는 계약과는 다르다. 실제 미수신 슬롯·예정 주기 근거가 없는 상태에서는 관측 시계 간 gap을 추정할 수 있어도 실제 수신 결측률을 확정할 수 없다. generic naive `created_at`의 과거 offset 또한 현재 DB session timezone만으로 확정하지 않는다.

등록 운영 QC의 현재 지원 범위는 승인 `SCALAR` 관측이다. 방향·radial/vector·profile·trajectory의 typed source를 scalar 정상 분모에 합산하지 않으며 명시 제외한다. 보존 원문 모드에서는 이 항목의 원래 값·QC·수심을 보존할 수 있지만, 물리 QC 해석을 완료한 것은 아니다. typed 목적별 모델·전체 공간장 지원은 [34](34_PURPOSE_DATASET_MODEL_READINESS_REVIEW.md)의 별도 범위다.

최종 통합에서 신규 실제 ingest의 `created_at`도 timezone 없는 컬럼으로 저장되는 문제가 발견됐다. `bound_at_utc` nullable timestamptz를 추가하고 신규 ingest의 명시 UTC 시각만 같은 트랜잭션에서 기록하도록 수정했다. 기존 `created_at`과 승인 receipt payload를 바꾸거나 NULL legacy 기록을 소급 채우지 않는다. 루트는 현재 binding 0건과 원장을 확인한 뒤 이 열만 명시 추가하고 재적용·PostgreSQL 타입·기존 원장 건수 불변을 대조했다. **실제 schema 변경은 이 nullable 열 1개이며 실제 source/승인/QC/모델 기록 생성은 0건이다.** 설치 순서는 [02](02_SETUP_AND_INSTALLATION.md)를 따른다.

승인·수정·반려는 기존 workflow의 인증·추천 hash·revision·stop/resume 검증을 사용한다. 현재 실제 담당 계정 설정을 유예한 상태에서는 해당 사유를 보이며 권한 없는 요청을 거부한다. 계정·데이터·모델이 없는 상태를 합성 운영 기록으로 채우지 않는다.

## 4. 요구사항별 최종 상태

`VERIFIED`는 아래 명시 범위의 구현·시험 판정이다. 실제 원천 승인·운영 모델·전 관측망 정상 판정 완료를 뜻하지 않는다.

| 번호 | 요구사항 | 상태 | 검증과 제한 |
|---|---|---|---|
| 1 | 오늘 1차 QC 운영 대시보드 | IMPLEMENTED | 6 KPI와 3×2 패널·상세 탐색 |
| 2 | 오늘·어제·7일·30일·사용자 지정 | VERIFIED | 실제 backend offset·자정 refresh·native 과거 cutoff |
| 3 | 기간별 6 KPI | IMPLEMENTED_CONDITIONAL_DATA | 분모·미평가·없음·부분 자료·권고 workflow 완료 구분 |
| 4 | 동적 backend Flag 분포와 클릭 | VERIFIED | 1/3/4/9/NOT_EVALUATED·UNKNOWN; 원문 코드 의미 변경 없음 |
| 5 | hourly/daily 품질 추이 | VERIFIED | 오늘/어제 hourly, 7/30일 daily·빈 구간 공백 |
| 6 | 실제 Rule 결과 | IMPLEMENTED_CONDITIONAL_DATA | 12종 엔진 catalog와 실제 등록 정의·저장 결과 분리 |
| 7 | 지연·결측 이력 | IMPLEMENTED_CONDITIONAL_DATA | 확인된 received time만 계산; 실제값 유지·추정 gap 별도 |
| 8 | Heatmap과 전체 필터 | IMPLEMENTED_SCALAR_SCOPE | 셀 통계·Rule/latest·선택 동기화; typed 운영 QC 미지원 |
| 9 | 우선 검토 Queue | VERIFIED | BAD→Suspect→최근·bounded 페이지; 원문 표본 별도 |
| 10 | QC 상세검토 Drawer | VERIFIED_CONDITIONAL_DATA | 실측±2h/zoom·Rule·저장 AI·정확 epoch·Evidence·history |
| 11 | 저장 AI 조회 | IMPLEMENTED | 정확 관측/source/기간만 조회. 임의 추론·가짜 결과 없음 |
| 12 | QC와 장기 AI 역할 분리 | IMPLEMENTED | 장기 Drift·모델·Residual 분석은 AI 인사이트 |
| 13 | Overview/context/candidate API | VERIFIED | 5개 GET 통합·162 paths/171 operations·읽기 전용 |
| 14 | 성능·대용량 집계 | PARTIAL_PERFORMANCE | 500행 keyset·SQL aggregate·snapshot·부분자료; 과거 cold 10초 목표 미달 |
| 15 | 상태와 오류 처리 | VERIFIED | loading/no-data/error/partial/AI未실행/model없음/evidence없음/review완료 |
| 16 | 금지 사항 준수 | VERIFIED | 운영 DML·raw 변경·가짜 결과·자동 Final QC 저장 0 |
| 17 | 빠른 탐색과 근거 UX | VERIFIED_WITH_LIMITS | 실제 1280×720 확인; cold 과거 조회·다른 viewport 성능은 제한 |
| 18 | 11개 시나리오와 회귀 | VERIFIED | backend1001/skip1·frontend104·build·실제 Arrow/브라우저·격리 양성 |
| 19 | 최종 보고와 미구현 구분 | DOCUMENTED | 본 문서·공개 집계 JSON·변경 파일·입력/성능 한계 |

## 5. 변경한 화면과 API

이전 QC는 장기 AnalysisWorkspace와 일반 workflow가 중심이었다. 당일 Rule 품질 분모·시계·후보 identity·같은 범위의 상세를 하나의 계약으로 검증하기 어려웠다. 원문 최신 표본과 실제 이상 후보도 구분이 필요했다.

이제 오늘 기본 조회, 6 KPI, Flag 분포, hourly/daily 변화, 실제 Rule 결과, 관측소×항목 행렬, 우선 검토 Queue, 상세 지원 패널을 사용한다. 공통 Layout은 관측/품질 화면의 좁은 메뉴를 유지하고 내부 설정과 근거를 접을 수 있게 했다. 관측 현황의 명시 기준일·시각은 QC로 보존하며 공유 AnalysisWorkspace와 다른 메뉴는 유지했다. 본 화면의 실제 상태를 채우기 위한 운영 Mock은 없다.

| API | 역할 | 확인 |
|---|---|---|
| GET `/api/qc/context` | 실제 backend local offset·오늘 시작·source/preset·Flag 계약 | fresh 오늘·자정 갱신·과거/미래 응답 guard |
| GET `/api/qc/overview` | 같은 window의 KPI·Flag·추이·Rule·matrix·검토 큐 | 실제/보존 분리·strict query·500행 전수·부분 자료·집계 |
| GET `/api/qc/flag-catalog` | 기존 Flag와 12종 엔진 catalog | 원문 codebook과 별도 namespace |
| GET `/api/qc/candidates/{candidate_id}` | exact source/row/window SHA의 상세 | 실제±2h/zoom·Rule·저장 AI·epoch·Evidence·history |
| GET `/api/qc/workspace` | 기존 월별 보존 원문 조회 유지 | 원문 QC/MQ/N1·NULL·padding·locator 보존 |

현재 OpenAPI는 162 paths / 171 operations다. 신규 QC 경로는 모두 GET이며 actual Raw·QC·AI·승인·모델 원장에 쓰지 않는다. 기존 workflow 판정과 resume POST는 인증된 기존 경로를 그대로 사용한다. 관측행·sensor episode·source SHA·추천 hash·revision·가용 판본이 일치하지 않으면 capability를 주지 않는다.

## 6. DB·Query·Flag·AI 처리

PostgreSQL에 추가한 것은 `source_observation_binding.bound_at_utc` nullable timestamptz 1열이다. default·기존 행 backfill은 없으며 신규 ingest만 명시 UTC 시각을 기록한다. 현재 binding 0건, Raw 13,621건, Standard 4,074건과 승인/QC/Dataset/Model/Workflow 원장은 변경 전후 동일하다. 새 인덱스는 0개이며 기존 관측시각·관측소·센서·항목 및 자연키 인덱스를 확인했다.

등록 조회는 explicit offset 창을 UTC 저장열에 대응시킨다. 기존 helper가 이미 UTC로 정규화했으며 이번 SQL 명시화와 +09/UTC 동등창·1µs 포함/제외 시험을 UTC 오류 수정으로 기록하지 않는다. Overview는 500행 keyset 전수 검증, 요청 전용 receipt/Rule/workflow cache와 종료 전 재검증, 읽기 전용 repeatable snapshot을 사용한다. 40초 예산·제외·불확실한 이력이 있으면 부분 자료와 null 비율을 반환한다. 검토 큐는 최대 30행, offset 1,000 이내이며 전체 집계 분모와 분리한다.

보존 Parquet는 기간 선필터와 GROUPING SETS로 집계하며 최신 원문 표본은 15행만 전달한다. 원래 QC/MQ/N1 문자열·NULL·빈값·공백·수심과 원문 행 identity를 보존한다. 원문 `OK/GR/GD/NQ/SP`를 기존 엔진의 `1/3/4/9`로 추정 변환하지 않는다. 실제 사례의 대표 Flag와 catalog 색을 모든 widget에 적용한다. 표시 정책 `QC_DISPLAY_TONES_2`는 결측 9를 보라색, 미확인 UNKNOWN을 회색으로 표시하며 숫자 의미는 그대로다. `COMPLETED`는 권고 workflow 처리 완료이며 Final QC 승인 완료가 아니다.

해역·관측망의 positive DB 관측소 집합은 검증된 source/month 카탈로그와 교집합으로 좁힌다. 카탈로그의 observation accounting·station/item/depth/month grain·Parquet 재독립 확인 3개 PASS와 동결 catalog/source_assets SHA가 없거나 다르면 409로 차단한다. 검증 receipt SHA는 조회 전후 다시 비교한다. 루트와 독립 에이전트는 유효 시각으로 필터하기 전 143개 파일의 관측형 23,694,337행·metadata 947행·610 grain·61개 관측소를 전수 정산했다. 서해 DB 분류 119개 코드 중 원천에 존재하는 28개만 남겨도 당일 240,902행·273개 cell·원문 QC/MQ/N1·invalid clock·빈값·hour 추이·최신 15개 file/row/literal이 정확히 동일하다. 이름을 못 찾았다는 이유로 원문 관측소를 임의로 제거하는 최적화가 아니다.

상세의 실측·Prediction·Residual 수치는 최대 소수 6자리와 작은 값의 과학표기로 표시한다. KPI 비율의 소수 1자리와 분리하므로 실제 `21.38`을 `21.4`로 바꾸지 않는다. AI는 이미 저장된 정확한 관측행·source·sensor·clock·가용 판본 결과만 읽는다. registry가 선언한 production 상태와 실제 승인 검증을 구분하고 이 Drawer에서 현재 serving을 확인했다고 주장하지 않는다. 결과가 없으면 모델 없음/미실행이며 가짜 기대값·confidence·drift를 생성하지 않는다.

장비 설치·교체·검교정, 운영 로그, 점검보고서 content SHA와 RAG 문서는 동일 관측행·물리 sensor episode·범위·명시 event/available/version 시각이 맞을 때만 연결한다. 현재 metadata를 7월 장비 이력으로 소급 사용하지 않는다. 예측·결측 보간·Final QC 자동 저장은 없다.

교차 검토에서 workflow 최신 100개만 읽던 상세를 전수 keyset으로 보완했다. 101번째 match·중복 match·미확정 미래 판본을 놓치지 않고 목록과 상세를 동일 `UNVERIFIED/AMBIGUOUS`로 판정한다. 제외 사유는 관측 ID별로 전달해 명백히 다른 관측의 불확실성이 전파되지 않는다.

최종 실제 브라우저에서 관측소와 항목을 빠르게 연속 선택하면 앞선 관측소가 사라지는 오류를 발견했다. React Router 검색 파라미터의 함수 호출은 같은 tick 변경을 누적하지 않으므로 pending URLSearchParams를 기준으로 변경을 누적했다. 자료 경로 전환 직후 기간 선택·초기화, 해역/망 동시 변경과 뒤로가기 이후 변경도 같은 계약을 사용한다. 수정 전 실제 React DOM 재현과 수정 후 회귀, 최종 진도 수온 942행 동기화를 별도로 검증했다.

## 7. 11개 완료조건 검증

| 시나리오 | 결과·확인 내용 | 검증 범위 |
|---|---|---|
| 최초 진입 | PASS · 실제 오늘 기본·실제 데이터 없음과 비율 null | ACTUAL_HTTP_BROWSER |
| 날짜 변경 | PASS · 오늘/어제/7/30일/custom·자정 refresh·모든 widget 동일 window | ACTUAL_AND_ISOLATED_DOM |
| 지연 자료 | PASS · 실측 유지·receipt clock/delay marker·미확정 clock 제외 | ISOLATED_BACKEND_DOM |
| 결측 자료 | PASS · NULL·빈값·duplicate·추정 gap·no interpolation | ACTUAL_ARROW_AND_ISOLATED_DOM |
| 사례 상세 | PASS · 원문121점·21.38·Rule threshold/version 양성 | ACTUAL_ARCHIVE_AND_ISOLATED_QC |
| AI 존재 | PASS · 저장 prediction/residual/score·정밀도·미래/잘못된 센서 제외 | ISOLATED_BACKEND_DOM |
| AI 없음 | PASS · 실제 모델 없음/未실행·가짜 예측 path 0 | ACTUAL_HTTP_BROWSER |
| 리뷰 처리 | PASS · role/owner/hash/revision·승인/반려/resume·401/403/409·완료 이력 | ISOLATED_BACKEND_DOM_AND_DATED_POSTGRES_GATE |
| Frontend | PASS · 104 PASS·TypeScript/Vite PASS·기존 lint12 warning | FROZEN_FULL_REGRESSION |
| Backend | PASS · 1001 PASS·1 Windows symlink privilege skip·18 warning | FROZEN_FULL_REGRESSION |
| 기존 기능 회귀 | PASS · 원천/Rule/AI/Fusion/workflow/MLOps/관측현황 전체 회귀 | FROZEN_FULL_REGRESSION |

실제 운영 원장의 양성 후보·저장 AI·linked approval 기록은 0이므로 이 경로의 양성 시험은 SQLite/임시 Parquet·React DOM 격리 fixture에서 수행했다. 실제 시험 서버에는 샘플 QC·승인·AI를 넣지 않았다. 기존 PostgreSQL 영속 stop/resume 8개 검증은 10/8 기록으로 유지하며 이번 실제 승인 실행으로 확대하지 않는다.

루트는 동결 서버 GET 결과를 별도 PyArrow로 143개 원본 파일과 대조했다. 당일 541,426행, 7/1~cutoff 7,126,689행, 610개 matrix cell, 원문 QC/MQ/N1·빈값·시간 집계와 진도 수온 121개 원문 cell의 SHA가 일치했다. 변경된 scope/window SHA·중복 query·잘못된 Flag·source clock·future 컷오프는 오류로 차단했다. 실제 브라우저에서 오늘/어제/7·30일/custom, 7월 9일 기준 전달, 서해 필터(240,902행·28개소·85항목), 원문 표본→상세·zoom·예측선 없음·승인 잠금을 확인했다.

브라우저 실제 검증 크기는 1280×720이다. viewport override 요청은 실제 크기에 적용되지 않아 다른 크기의 검증 완료를 주장하지 않는다. 임시 override는 reset했다. frozen runtime 이후 새 console error는 없었다. 스크린샷·전체 로그·원본 대조 packet은 로컬 private 증거로 남기고 공개 JSON에는 SHA와 집계만 포함한다.

## 8. 남은 기능과 운영 조건

| 남은 항목 | 현재 판정 | 다음 작업 |
|---|---|---|
| 실제 원천·QC 판본·물리 sensor와 수신시각 | 승인 source/QC 후보/모델 0 | 담당 근거를 확정하고 실제 운영 시 계정·원천 계약 승인·ingest |
| 미수신·예정 슬롯 | 계약 없음, 추정 gap만 가능 | 예정 주기·유효기간·heartbeat/수신 이력을 연결해 실제 수집률·미수신 분모 검증 |
| typed 운영 QC | SCALAR만 지원 | 방향·radial/vector·profile/trajectory 전용 해석과 동일 source/version 정산 |
| candidate의 Final QC 수정 | exact 승인 대상·판본 gate 미연결, 버튼 비활성 | 일반 승인 API에 원문 후보를 직접 보내지 않고 후보/source/epoch/revision 계약 연결 |
| 새 AI 실행·목적별 학습/평가·serving | 저장 조회만 연결; 전용 drift/공간장 worker 미완성 | [34](34_PURPOSE_DATASET_MODEL_READINESS_REVIEW.md)의 고정 Dataset/정답/reference/split/수용 정책을 준비한 뒤 별도 구현·검증 |
| 10초 UX 목표·실제 878,400행 규모 | 실제 과거 cold query가 목표 초과; 10,501행 격리 전수 시험만 있음 | full-scale approved population·cold/warm/동시 요청 profile, 집계 cache·incremental 전략 및 query 최적화 검증 |
| 모바일·다른 화면 크기 | CSS 대응 있음, 실제 1280 검증 | viewport가 적용되는 환경에서 추가 breakpoint 및 키보드·스크린리더 확인 |

실제 계정·운영 승인·새 학습·배포는 사용자가 실제 실행 단계로 유예한 범위다. 7월 후반에 학습된 개발 시험 release 3개를 7월 9일 당시 모델로 연결하지 않았다. 등록 QC/자료가 없다는 사실은 국가망 전체 정상 판정이 아니다.

## 9. 변경 파일과 실행 결과

| 파일 묶음 | 변경 이유 |
|---|---|
| backend `main.py`, `routes_qc_workspace.py`, `routes_qc_candidates.py` | 신규 read-only QC 계약을 앱에 등록하고 strict query·snapshot·오류 연결 |
| `qc_overview.py`, `qc_workspace.py`, `qc_candidate_review.py`와 관련 tests | 실제 집계·원문·후보·Rule·AI·장비/Evidence·workflow 동일 권위 검증 |
| `source_observation_binding.py`, `source_contract_snapshot.py`, `migrate_binding_clock_20261009.py`, binding tests | 신규 적재의 명시 UTC clock; legacy receipt/NULL 불변 |
| `qc_analysis_readiness.py`, `anomaly_analysis.py`, `qc_rule_engine.py`, `anomaly_artifact.py`, source fact period tests | 공통 strict 기간 codec와 아티팩트 fingerprint·준비도 정합성 |
| frontend `QCCopilot.tsx`, QCWorkspace/Charts/CaseReview/CandidateDrawer, `qcWorkspace.ts`, `qc.css` | 오늘 기본 운영 dashboard·동적 Flag·실제 상세·정밀도·loading/오류/권한 상태 |
| `Layout.tsx`, `observationPeriod.ts`, 관련 tests | 화면 전용 메뉴·설정 접기·관측 기준시각의 QC 전달 |
| QC test/fixture, `package.json`·lock | 실제 React DOM 격리 검증용 happy-dom 개발 의존성; 운영 Mock 추가 없음 |
| docs 02/04/12/22/25/34/35/36, README/current_status | 설치·API·Rule/AI 연결·목적별 준비도·사용자 요구·최종 검증 현행화 |

전체 파일 경로와 실제 code SHA는 [검증 JSON](36_QC_OPERATIONAL_DASHBOARD_VERIFICATION.json)에 기록했다. 환경파일·원본 데이터·DB·모델·token·private 테스트 증거는 Git에 포함하지 않는다. 새 코드의 개발 웹은 `http://127.0.0.1:5174/qc`, backend는 8010이며 기존 canonical 8000/5173·Chroma 8001·시험 모델 8011은 유지했다.

## 10. 최종 판정

**일일 QC 화면·실제 조회·상세와 기존 승인 workflow 연동은 명시 범위에서 구현·시험 완료다.** 실제 승인 입력, typed QC·예정 수신 슬롯·candidate Final QC gate·운영 모델 및 성능/breakpoint의 남은 범위는 위 표의 조건을 따른다. 화면과 격리 시험의 성공을 72개 업무의 운영 모델이나 전 관측망 물리 QC 완료로 표시하지 않는다.
