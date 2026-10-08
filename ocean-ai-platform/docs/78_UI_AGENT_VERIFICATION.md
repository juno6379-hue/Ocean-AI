# 업무 메뉴·상태·조회 범위 UI 검증

2026-10-07. Canonical `D:\AI_Observation\source\ocean-ai-platform`.
구현·HTTP 검증·브라우저 시각 검증을 별도로 기록한다. 서버는 부모 에이전트만 재시작했다.

## 1. 원문 선행 확인

`D:\share\04.요청자료\1차\3. 조석관측 수측기점 측정 관련 매뉴얼\04_해양관측 업무매뉴얼_2장_해양관측시설별업무_v5.pdf`
SHA-256 `ab4aa3f96547c55358e1623d313fad800825a596ece1e842b0299e28e6df917a`.
evidence.sqlite3 추출 원문 p1–7을 탐색하고 **PDF p2–3(인쇄 p4–5)**을 Poppler로 렌더해 직접 확인했다.

- p2 표2-1: 매일 이상점검 → 일일상황보고 → 이상조치 후 감독자 보고, 정기·긴급 점검 후 결과 보고.
- p3 그림2-2: 시설별 일일점검 취합, 그림2-3: 모니터링 요원 → 담당자 보고 → 점검 지시 → 결과·계획 회신.
- p1의 2019-12 시설134개는 당시 집계다. 현재 운영총량으로 복사하지 않는다.
- 당시 조직명·직위를 현재 계정 role과 매핑하지 않는다. 메뉴의 역할 설명은 참고/제품 제안이고 권한 부여가 아니다.

추가 읽은 근거: 품질관리 가이드북(개편), 표지 2023.12, SHA
`d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9`, PDF p15/22/35/36 원문 추출 텍스트.
p15 전주기 자동·수동 분리, p22 매일9시 모니터링과 이상 보고·점검 요청·조치계획/결과 전달,
p35 현행 flag와 수동 최종판정, p36 개선안 채택과 기존체계의 구별을 확인했다.
상세 검토 범위는 74번 문서에 기록된 QC 담당 독립검토와 교차 확인했다.
가이드 전체 항목/HF 세부 절, 전체 업무편람·절차 문서를 읽었다고 주장하지 않는다.
69–72, 74–77, 79번 내부 역할·실제자료 계약을 대조했다. 73번 파일은 현재 canonical docs에 없었다.

## 2. 메뉴별 구현 안내

`menuPurposes.ts`는 다음 표의 입력→조회/행동→산출→다음 메뉴를 정의한다.
`MenuPurpose.tsx`는 짧은 목적과 다음 행동을 먼저 보여주고 상세 역할·범위는 접는다.
Layout의 12개 기존 메뉴명·주소를 보존하고 목적 tooltip과 공통 안내만 삽입했다.

| 메뉴 | 현재 안내하는 행동과 산출 | 다음 메뉴 / 남은 기능 |
|---|---|---|
| 대시보드 | 보유자료·지도·일일보고 요약 조회 | 관측·보고·QC / 당일제출·대조기·편차·운영총량 통합 미완료 |
| 관측 | 실제 값·표본·계보와 공백 확인 | QC·장비 / 수집률의 이론건수·제외정책 필요 |
| QC | 원천표기·결측·사건 근거 조회 | 장비·승인대기 / 가이드 전항목·HF 재검사/Label 승격 미완료 |
| AI 인사이트 | 추이·문서사건·원문인용 확인 | QC·보고 / 검증된 원인·신뢰도·전항목 예측 미완료 |
| 장비 | 설치·정비·날짜·일련번호 후보 대조 | 관측·보고 / 현장지시·완료처리·센서기간 승인 미연결 |
| 서비스 | 연결된 시스템 상태·시각 검토 | 시스템 / 모든 DB·API·배치·검색 감시·복구 미완료 |
| 보고서 | 등록 문서 조회와 연결된 검토·승인 요청 | 장비·승인대기 / 제출 대상·기한 및 대조기 특별보고 연결 미확정 |
| MLOps | 전역 등록부·모델별 차단근거 조회 | Dataset근거·AI분석 / 학습·배포·롤백 실증 미완료 |
| Data Lake | 보유·변환·연결 근거 조회 | QC·MLOps / 후보는 승인 멤버십이 아님 |
| 조위 기준선 | 현재 persistence baseline 요청 | 모델평가·관측 / 대조기 예측조위·범용AI예측이 아님 |
| 알림 | 기존 승인대상 조회와 권한별 승인·반려 | QC·보고 / 장애 접수·배정·종결 전주기 미통합 |
| 시스템 | 구현된 연동시험 요청·결과 조회 | 서비스 / 권한·설정 변경 감사는 별도 구현 필요 |

`/copilot`은 QC 안내, `/profile/:id`는 관측 상세 안내를 사용한다.
공통 설명을 개별 페이지의 모든 기능이 연결되었다는 뜻으로 표시하지 않는다.

## 3. 기존 API와 새 요구의 경계

| 요구 | 현재 활용 가능 근거 | 남은 검증·구현 |
|---|---|---|
| 수집률 | monitoring의 실제 보유량·결측과 관측 메뉴 | 가이드 p38 및 보고4장 p1–2/8의 이론건수·월중설치/폐지 제외정책. held_rows를 분모로 대체 금지 |
| 일일모니터링 | `EvidenceMonitor`의 `/api/lake/daily-reports`, 기간과 보고일 선택, document_id·인용 위치 | 전체 게시 색인 기준이며 관측 source와 별도. 보고서 날짜는 사건일·제출일·승인일이 아님 |
| 대조기모니터링 | 일일/점검 원문 탐색은 가능 | 일정·대상관측소·특별점검·당시보고 대응 미검증. UI 실행 미연결 |
| 조위편차 | 기존 `routes_tide_analysis`/`TideResidualAnalysisAgent` 코드 존재 | 임의 residual 리스트·obs/pred 입력에 단위·시각·기준면·sourceID 계약 없음. mock 임계값/현재시각 기간/DB쓰기 있어 이번 UI에 연결하지 않음 |
| 운영총량 | 시설 registry와 lifecycle 문서 주장 | 기준일 운영·신설·폐지·재배치·계획 대비 검증 필요. 357 등록 코드 또는 2025 보고수는 2026 운영총량이 아님 |

`/api/forecasting/baseline`은 마지막 TIDE 값을 유지하는 기준선이다.
unit/datum/source-observation ID가 응답에서 고정되지 않아 이를 OBS−조화예측 또는 대조기 업무로 확대하지 않았다.
기존 분석 POST는 보고서·DB 쓰기를 유발할 수 있어 검증용으로 실행하지 않았다.

## 4. UI 변경과 UX 기준

- 네이비 사이드바·블루 강조·화이트 카드·기존 지도/표를 보존했다. OSM 관련 파일은 변경하지 않았다.
- 목적/다음 행동은 간결한 한 줄·버튼, 기능범위·기술 근거는 details로 접었다.
- 보류는 황색, 실패는 적색, 미확정/미연결은 중립색과 명시적 텍스트를 함께 사용한다.
- 공통 업무 링크, 검색·항목/상태 필터에 접근성 이름과 focus 표시를 넣었다.
- MLOps 숫자는 0/조회중/실패/미확인을 구분한다. readiness 누락을 운영0으로 치환하지 않는다.
- MLOps 모든 건수·분포는 전역 등록부임을 표시한다. 표 검색·항목/상태 필터는 실제 동작하며 카드/차트는 전역임을 밝힌다.
- 원인 패널은 `AIPredictionResult.cause_candidate`를 그대로 표현하도록 '기록된 원인 후보'로 변경했다. 성능저하 확정원인으로 표시하지 않는다.
- 종료시각만 있는 학습 이력은 '종료 기록 · 실행 검증 별도'다. 운영검증과 DB PRODUCTION은 별개다.
- 가짜 페이지번호/미연결 필터·다운로드를 제거하거나 비활성화하고 실제 조회 JSON 내보내기만 제공한다.
- 0모델에서는 비율 분모가 없음을 표시한다. 빈 평가에는 선을 그리지 않으며, RMSE 축을 임의10으로 고정하지 않는다.
- 비교 조건의 동등성이 검증되지 않은 평가 이력은 우수모델 선정으로 제시하지 않는다.
- 새 가짜 endpoint·모델 수치·sparklines를 만들지 않았다.

## 5. 실제 API 대조 및 ID 전달

실제 로컬 HTTP를 읽기 전용 조회했다. 기록: workspace `label_agent_stage/ui-api-verification.json`.

| 요청 | HTTP·실제값 | UI 매핑 |
|---|---|---|
| workflow, GD_OBS_ST_MONTHLY, 2023-01~2026-07, network/sea 빈값 | 200;93코드,25,642채널/월,1,017,630,666보유행,센서·기간·간격·승인0 | 코드는 stations, 채널은 channels; 운영시설수는 별도 NULL→미확정 |
| workflow 역기간 | 422 | 실패 메시지·이전값 삭제. 정상0으로 대체하지 않음 |
| workflow HISTORICAL_RECONCILED 2001-01 | 200;coverage_supported=false | 채널집계 대상외 안내. 과거자료없음으로 표시하지 않음 |
| mlops/summary | 200;total0,readinessBLOCKED,operational_model_count0 | 등록0/운영검증0/배포보류를 각각 표시 |
| mlops/retrain-history, approvals/pending | 각각200;각0건 | 조회 성공 후만 빈 이력·대기없음 표시 |
| frontend /mlops | HTTP200 | HTML 제공 확인만. 렌더 검증 아님 |

WorkflowStatus API query: `source/from_month/to_month/network/sea`.
Layout/MenuPurpose/WorkflowStatus의 메뉴 이동 링크는 `source/from/to/network/sea`를 보존한다.
MLOps API들은 원천·기간 필터가 없는 전역 API이며 해당 필터를 적용한 것처럼 표시하지 않는다.
station_id/item_code/equipment_id/document_id는 이 공통 workflow API에 없다.
따라서 이 집계/공통메뉴만으로 station→physical equipment→document→Parquet→embedding→UI
전체 체인 일치를 판정하지 않는다. 개별 페이지의 선택 ID와 연결 근거를 추가 검증해야 한다.
발견 잔여: `EvidenceMonitor`의 별도 Data Lake 링크는 현재 query 보존이 없다(이번 소유범위 밖).
관측소 상세와 예측기준선도 공통 기간/source가 개별 API에 모두 전달되는 계약이 아니다.
위 API 값과 컴포넌트 필드 매핑은 코드로 대조했지만 실제 렌더된 픽셀 수치를 비교한 것은 아니다.

## 6. 검증 상태

- Label 상한 초과 이후 per-event loop를 막고 ORDER BY 및 회귀시험 추가.
- Label11 + QC8 합계19 테스트 PASS. QC 역방향 검토에서 source/recheck/final 판정 분리 확인.
- TypeScript + Vite production build PASS(기존 500kB 초과 bundle 경고 남음).
- 컴퓨터 도구 `cua.getState()` 초기화가 Windows sandbox `helper_sandbox_lock_failed`,
  `SetNamedSecurityInfoW sandbox dir failed: 5`로 실패했다. 대체 helper/프로세스로 우회하지 않았다.
- 브라우저 클릭·실제 배치·모바일·200%확대·키보드 순서·스크린리더 검증: **NOT_VERIFIED**.
  focus/반응형 class를 구현한 것과 실제 사용성 검증은 다르다.
- API 숫자·범위·ID 미연결과 시각 미검증 상태를 독립 QC 검증 담당자에게 전달했다.

## 2026-10-07 추가 구현: 시설 유형 지도와 보고서

### 기존 이미지 직접 검토

직접 `view_image`로 읽은 원본:
- `C:\Users\jochoi\AppData\Local\Temp\codex-clipboard-f0e0dc77-0237-488e-ab48-faec6268f459.png`: 네이비 좌측 메뉴, 블루 선택 상태, 상단 KPI, 지도/자료표/QC 3열, 최근 보고서의 유형 badge→제목→생성일→전체 보기 구조.
- `C:\Users\jochoi\AppData\Local\Temp\codex-clipboard-40335551-8df8-4e80-83d6-fee1fa6aa745.png`: 분석 근거 카드와 하단 보고서 목록/생성일/유형 구조. 샘플의 98.7%, 36건, AI 신뢰도 등은 실제 값으로 전용하지 않았다.

| 원본 패턴 | 이번 실제 구현 | 미검증/구현 경계 |
|---|---|---|
| 지도·표·QC 카드의 나란한 배치 | 기존 3열/모바일 1열 보존. 지도/표 높이 조정, 시설 유형 선택과 범례 추가 | 실제 브라우저 겹침·모바일 크기는 NOT_VERIFIED |
| 지도 범례와 선택 표식 | 시설=서로 다른 SVG 기호, 현재 상태=회색+운영 미확정/QC 미승인. 선택은 파랑 테두리 | 정상/주의/이상 판단 데이터가 없어 상태색을 추정하지 않음 |
| 최근 보고서 유형/제목/일자 | 실제 report_type badge, report_title, created_at, status 각각 별도 표시. /reports?report=ID 이동 | 등록부 0건이므로 양의 실제 보고서 시각 표본은 없음 |
| 목록→미리보기→검토 동선 | Reports 전체 등록부 조회, 선택 ID, 실제 summary, 기간·생성일·수정일 분리, 기존 수동 검토 API | 원문 파일·자동 작성·템플릿 생성은 미연결. 브라우저 클릭 검증 없음 |

### 시설 유형/API 및 선택 범위

변경 파일: `Dashboard.tsx`, 신규 `FacilityMapSymbol.tsx`, `Reports.tsx`, `menuPurposes.ts`.
`OSMBaseLayer.tsx`의 타일/저작표시는 변경하지 않았다. 시설 분류 값은 PostgreSQL station_metadata/catalog의 정확한 `조위관측소`, `해양관측소`, `해양관측부이`, `HF-Radar`, `해양과학기지` 값만 사용한다. 원천 source를 시설 유형으로 추론하지 않는다. `__UNREGISTERED__`는 기존 backend network 필터다. 등록 분류 미지정/코드 중복 대응은 전체에 남고 임의 network 분류를 만들지 않는다.

API와 URL:
- `/api/lake/summary?source=...&from_month=...&to_month=...&network=...&sea=...`: 지도/요약 모집단.
- 유형 범례 수는 위와 동일 source/기간/sea에서 network만 해제한 summary + `/api/stations?limit=10000`로 계산. 필터된 모집단만 가지고 타 유형을 0으로 만드는 오류 방지. snapshot 불일치/분류 조회 실패 시 숫자 대신 `—`.
- `/api/lake/monitoring`은 같은 scope + station/item 필터 지원. Dashboard는 모든 channels 응답에서 실제 관측 항목을 선택하고 station/item의 held_rows만 합산. 지도와 표가 동일 displayedStations를 사용. 상단 KPI/QC/범례는 facility/sea 모집단으로 명시.
- 시설 버튼은 URL network, source/from/to/sea 보존. 관측소/항목 선택은 Dashboard 내부 상태이며 다른 메뉴 전체 필터 구현이라고 주장하지 않음. 관측소 변경 시 항목 초기화. '전체 해제'는 시설/관측소/항목을 해제하고 원천·기간·해역 보존.
- marker click과 표 이름 button은 동일 관측소 선택 함수를 사용. marker title/alt, aria-pressed, focus ring, 2/3열 반응형 선택부와 가로 스크롤 표 제공. 실제 마우스/키보드/픽셀 동작은 NOT_VERIFIED.
- 수집률은 aggregate.collection_reason을 표시. 보유 행을 관측 고유건수/이론건수로 나누지 않음. item별 최종시각이 API에 없으므로 '항목별 시각 미조회'. 항목 이름 사전이 연결되지 않아 실제 item_code를 선택 옵션으로 표시(한국어 명칭은 미연결).
- 2026-07-31 운영 시설 총량은 미확정이다. 부이/HF가 이 원천에서 0이어도 운영수 0을 뜻하지 않는 안내를 표시.

읽기 전용 API 검증 `label_agent_stage/map-api-verification.json` (원본 workspace):
- source `GD_OBS_ST_MONTHLY`, 2023-01~2026-07, 전체 해역, lake snapshot `validation-20261006T134056Z`.
- 전체 93 = 조위 55 + 해양관측소 3 + 해양과학기지 3 + 기준정보 미등록 32. 부이 0, HF 0. 6개 network별 실제 summary의 station 수와 baseline facet 수 모두 일치.
- DT_0001/AIR_PRES channels held_rows 1,875,261: station+item 제한 monitoring API와 전체 channels의 해당 record 정확 일치.
- `/api/reports`, `/api/reports/list`, `/api/reports/stats` 실제 200, 등록 보고서 0. 자동 생성/상태 변경 API는 검증에서 실행하지 않았다.

### Reports 계약 수정

기존 `/reports/list`는 10건 제한이며 관측소/대상기간을 제공하지 않아, `/reports` 전체 등록부를 사용한다. 검색·생성월·실제 유형·상태 필터가 실제 목록에 적용된다. 문서 ID query 선택과 조회 목록 JSON 내보내기 제공. 보고 대상 period_start/end, created_at, updated_at, approved_by, status를 분리한다. 등록부에 station_id/version이 없으므로 가짜 관측소/버전 필터를 만들지 않는다.

삭제/교정한 표시: 하드코딩 124문서, 2025-05-28, 예시94.6%/92.1%/21건/95.7%, 가짜 DOC-2025-0056, 관리자/운영자와 알림12, 양식 버튼의 거짓 생성 성공, 무동작 pagination, 승인=배포완료, summary 존재=AI Generated. 실제0건/로딩/오류/필터결과없음/선택ID없음을 분리했다.

검토 동작은 기존 `/reports/{id}/review` (DRAFT), `/approve`와 `/reject` (REVIEW)만 사용자 클릭에서 요청한다. 승인/반려는 확인창과 검토 의견 후 기존 인증 interceptor를 사용한다. legacy body의 user_id는 빈 값이며 서버 require_reviewer의 실제 actor가 권한/감사 주체다. 임의 'frontend-user' 신원을 표시/전송하지 않는다. 승인과 게시를 구분하며 게시 자동 호출은 없다. DB가0건이라 실제 상태전환/권한반려 UI는 NOT_VERIFIED.

### 메뉴 전수 UI/API 대조 (소스 확인, 실브라우저 아님)

| 메뉴/route | 현재 데이터/API | 범위·ID 연결 / 남은 경계 |
|---|---|---|
| 종합 대시보드 / | lake summary/monitoring, stations, reports, 공통 workflow | source/month/network/sea 전달; 지도/요약 station/item 로컬 선택. sensor/document ID 없음. 등록부 report ID는 Reports로 전달 |
| 관측 현황 /observations | lake summary 및 stations, 상세 링크 | source/month/network/sea 적용. station/item URL 선택은 현재 별도 local filter와 연결 안 됨 |
| 관측소 상세 /profile/:id | LakeExplorer lake summary/stations/{id}/series | id/source/month 및 series item/depth/month/offset 전달. network/sea, 진입 URL item은 미적용. 첫 채널을 자동 선택하므로 상세 진입 후 확인 필요 |
| 품질 /qc, /copilot | AnalysisWorkspace lake monitoring + summary | source/month/network/sea/station/item 전달. source QC≠재검사≠human label. 자동 승인/전 가이드 판정 미완료 |
| AI 분석 /ai-insights | 같은 AnalysisWorkspace insights mode | 같은 scope의 문서사건/자료 대응. 실제 모델신뢰도·원인 확정·범용예측 미완료 |
| 장비 /equipment | lake equipment-evidence + summary + stations | source/month/network/sea/station 전달, 물리 sensor/equipment ID 확정 아님. 설치이력 전체시기와 정비기간 분리 |
| 서비스 /service-monitoring | service-monitoring/overview from_time/to_time | 독립 서비스 기록 UTC 범위. 관측 원천/월/network/sea 집계가 아님 |
| 보고서 /reports | reports 전체 등록부, 명시 클릭 review/approve/reject | report ID/대상기간/생성일/상태 연결. 원천 월 필터 미적용 명시; 파일/문서색인/장비ID 미연결 |
| 모델 /mlops | mlops/summary, retrain-history, approvals/pending | 전체 등록부 scope, 준비도 차단 근거. 운영 모델/학습완료/lineage 검증과 구분 |
| Data Lake /data-lake | legacy data-lake/summary + FoundationLake summary/observations/channels | FoundationLake snapshot/필터는 부모 수정 소유. legacy summary catch null은 로딩/오류/없음 미분리(부모 전달) |
| 예측 /forecasting | POST forecasting/baseline station_id+horizon72 | 마지막 관측값 기준선. global source/기간 미적용, 전체항목/HF 학습모델 미완료. POST 미실행 |
| 알림 /alerts | approvals/pending 및 approve/reject | target_type/target_id. 전체 승인대기 scope. 요청시각 없음은 미확인 표시. 운영 장애 전체 이력은 아님 |
| 시스템 /system | integrations + test-auto/results, 수동 test-auto/run | test-auto 기존5시나리오는 Mock Data와 DB 예시보고서 생성 코드 포함. 부모가 security.py demo_paths의 /api/test-auto/run live409 차단을 확인했다. UI는 실행가능처럼 보여 미구현/차단 안내 개선 여지. 호출하지 않음 |

부모에게 별도 전달한 잔여: LakeExplorer의 network/sea/item 진입필터, Observations station/item URL, legacy DataLake 실패/빈값 구분, System 합성시험 실행가능처럼 보이는 UI(부모 확인: live backend409로 차단되어 운영DB 오염을 단정하지 않음). 이 파일들은 이번 소유 범위 밖이라 수정하지 않았다. FoundationLake/EvidenceMonitor는 부모 동시 수정 소유이므로 건드리지 않았다.

빌드 `npm run build` PASS (tsc + Vite), 최종 이 절 작성 전 artifact `index-RvdNx1UH.js`, `index-BUZCNUKi.css`. 기존 bundle>500k 경고 남음. 전체 browser visual/marker click/필터 clear/보고서 action/스크린리더/모바일 레이아웃은 CUA 초기화 sandbox 실패로 NOT_VERIFIED. 소스·API·build 성공을 실제 화면 합격으로 확대하지 않는다.

최종 재빌드 PASS: `index-BjrdBCPW.js`, `index-C1asCxgn.css` (부모 동시 수정 반영 상태). System live409 보호 정정 완료.

## 2026-10-07 후속 실제 화면 검증 및 원본 보존 상태

현재 실행 환경은 full access에서 동작하며, 이전 sandbox helper 오류가 수리되었다는 뜻은 아니다.
주 에이전트가 D: canonical 소스의 실제 브라우저를 검증했다. 아래는 확인한 표본 범위이며
전체 메뉴·승인 행동·스크린리더 검증을 대신하지 않는다.

- MLOps 실제 조회: 등록 모델/데이터셋/승인 데이터셋/운영 검증 모델 모두 0, 배포 보류.
  차단 사유 펼치기에서 실행 환경 미연결과 승인 자료 없음 확인.
- System: `/api/runtime`의 실제 live 응답에 따라 데모 합성 E2E 버튼 비활성화.
  조회 중/조회 실패/등록 이력 없음 구분. 375px에서 제목·버튼을 줄바꿈해 화면 배치 확인.
- 관측소 상세: DT_0001, 2023-01, 조위관측소, AIR_PRES 요청이 해당 채널을 선택하며
  WATER_TEMP 변경이 URL과 선택 항목에 반영됨. 원천 검증 링크는 source/from/to/network/sea/item 유지.
  없는 항목 요청은 명시적인 경고와 값 미반환, 해양관측부이 scope의 DT_0001은 채널 미표시 확인.
- Data Lake: 기존 통계의 조회 중/실패/0건을 구분. 현재 CSV99개 원래 경로 MISSING와
  기존 Parquet99개 변환 정산 완료를 별도 표시. `source_availability`는 현재 stat 결과이며
  현재 원본 SHA 재검사나 원본 CSV 복구 증거가 아니다.

검증: foundation API 관련 6 테스트 PASS, TypeScript/Vite build PASS.
빌드 산출물 `index-NUdlxqy1.js`, `index-etcFRx7G.css`.
증거는 현재 workspace `outputs/ui-verification/browser-checks.json`, `implementation-receipt.json`,
`review.patch` 및 PNG들에 보존했다. 2026-10-07 재개한 3명의 의미/QC·기간/사건·모델 에이전트
작업과 운영 모델 선정은 별도이며, 이 UI 검증을 전수 의미 승인 또는 운영 완료로 해석하지 않는다.

## 공통 의미·기간·사건 검토 게시본 실제 화면 확인 (2026-10-07)

Data Lake에 읽기 전용 기술검토 기록을 연결했다. 실제 backend
`GET /api/data-lake/foundation/review-receipt` HTTP 200과 브라우저 최신 게시본
`review-20261007T064041Z`가 일치한다. 이 API는 승인 기록이나 모델 등록을 쓰지 않는다.
게시본 미조회/오류를 승인 0건과 구별하고 다시 조회할 수 있다.

실제 화면에서 전수 분모 66,190개, 정확 사전 참조 44,213개, 판정 철회 20,048개,
보고서 표 118행, 연결 후보 851개, 의미/단위/시간대/규칙/QC 승인 0을 대조했다.
미확정 사유 펼침과 다시 조회를 검증했다. 375px에서 문서 가로폭 375px로
페이지 가로 넘침이 없었고 표는 자체 스크롤 영역이다. 임시 viewport는 해제했다.

최종 build `index-BOAZmkFJ.js`, `index-etcFRx7G.css` PASS.
해당 component/API를 포함한 관련 backend 시험 78 PASS, 1 SKIP.
기존 Pydantic deprecated 경고 및 Vite 큰 bundle 경고는 남는다.
전체 메뉴/승인 전환/스크린리더/모든 브라우저를 검증한 것은 아니다.

최신 증거는 현재 workspace `outputs/ui-verification/technical-review-checks-final.json`,
`technical-review-counts-final.png`, `technical-review-final.png`,
`technical-review-375px.png` 및 `outputs/parent-verification/live-review-api.json`이다.
`/health` ok, `/readiness` ready/database ok, runtime live이며 MLOps는
승인 dataset/운영 모델/배포 실행기가 없어 BLOCKED를 유지한다.

최종 API/UI PNG와 조회 기록, 시험/build 로그는
`D:\AI_Observation\metadata\review-integration\review-20261007T064041Z\evidence`에도
복사·SHA 확인해 보존했다. 해당 통합 폴더의 `integration-verification.json`은
최신 게시본과 실제 화면/서버/구현 파일 해시의 일치 및 운영 승인 0을 기록한다.
