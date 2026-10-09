# QC Rule Result 계층

현행화: 2026-10-08

## 원천 표기·규칙 결과·최종 판정

세 값은 별도로 관리한다.

| 값 | 저장·역할 |
|---|---|
| 원천 QC/MQC/N1 | 원문·Parquet의 literal. 원천 codebook과 시행기간을 검토해야 해석할 수 있다. |
| `QCRuleResult` | 특정 규칙 버전의 입력·임계값·결과·실행시각. 최종 인간 승인과 별개다. |
| `QCFlagHistory.qc_flag_final` | 검토자가 결정한 최종 QC. 검토 후보 생성은 이 값을 비워 둔다. |

[모델](../ocean-ai-platform/backend/app/models/domain.py)은 `observation_id + qc_rule_id + rule_version`의 규칙 결과 유일키를 사용한다. 입력·임계값·flag·버전·실행시각에 더해 `evaluation_status`, `result_reason`, `provenance_json`으로 미평가 이유와 원문/설정/입력 window SHA를 저장한다. 기존 DB에는 [명시적 migration](../ocean-ai-platform/backend/migrations/20261008_qc_rule_evidence.sql)이 필요하며 자동 DDL을 켜지 않는다.

## 현재 규칙 실행

[QC API](../ocean-ai-platform/backend/app/api/routes_qc.py)는 다음 경로를 제공한다.

| 경로 | 동작 |
|---|---|
| `GET/POST /api/qc/rule-definitions` | 규칙·적용 변수·threshold_definition·버전 등록/조회 |
| `GET /api/qc/rule-catalog` | 2023.12 기준본의 12종 정의, 15항목 적용표, 수치 충돌 조회. 승인된 운영 설정이 아님 |
| `POST /api/qc/rules/evaluate` | 명시한 시계열·규칙·as-of에 대한 순수 조건부 분석. DB/승인/최종 flag 변경 없음 |
| `POST /api/qc/rules/execute` | Standard를 관측소/센서/변수/시각으로 제한해 최대 10,000행에 활성 규칙 적용 |
| `GET/POST /api/qc/rule-results` | 규칙 결과 조회/등록. POST는 Standard 존재·중복 버전을 확인 |
| `POST /api/qc/review-candidates` | 실행 결과로 검토 후보 생성. 결과가 없거나 지원하지 않는 flag는 차단 |
| `POST /api/qc/copilot/analyze` | 저장 결과와 문서 근거의 분석 응답. 최종 QC 자동 확정 없음 |

`threshold_definition.kind`가 있는 규칙은 [12종 엔진](../ocean-ai-platform/backend/app/services/qc_rule_engine.py)을 실행한다. 기존 `min/max`만 있는 규칙은 `LEGACY_RANGE`로 분리하며 가이드 동등성을 주장하지 않는다. 두 임계값 모두 없으면 정상으로 처리하지 않고 미평가한다. 응답은 `ANALYSIS_ONLY`, `approved=false`다.

## 가이드북 12종과 적용 조건

기준본은 표지 `2023.12`, SHA-256 `d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9`이다. PDF 페이지는 1부터 시작한다. [카탈로그](../ocean-ai-platform/backend/app/services/qc_rule_catalog.json)는 표 2-7(PDF 23), 항목 적용표 2-9(PDF 24), 붙임 1(PDF 81)과 세부 원문(PDF 83–92)을 구분한다. 기존 1차 검사 12종이며, 개선안 10종 또는 2차 잔차·일 통계 전체의 구현으로 확대하지 않는다.

| 내부 코드 | 실제 계산 | 필수 조건·미실행 사례 |
|---|---|---|
| WT | 관측 시각이 실제 DB 수신 시각보다 미래인지 비교 | UTC 변환·수신 시각/근거 미확정 |
| LO | 명시한 WGS84 위·경도 사각 범위 비교 | 위치·관측시설 종류·허용 범위 없음 |
| ER | 항목별 명시 sentinel 또는 null 확인 | 모든 음수를 오류로 해석하지 않음 |
| GR | 선택한 범위의 open/closed 경계 검사 | 단위·기준면·물리량 종류·경계 정책 없음 |
| GD | 과거부터 현재까지 완전한 등간격 window의 동일 값 검사 | 간격 누락·결측·센서 구간 변경·window 부족 |
| RL | gust/풍속, 원형 방향 차, 파고/주기 관계 | 동일 시각·실제 paired 센서/단위·분기 정책 없음 |
| SP | 명시된 관측 간격의 연속 값 차 | 간격 변동·미래 이웃·단위 미확정 |
| RR | 과거 지역 최대·최소 기반 한계 | 기준기간·QC 제외 근거·한계 계산 정책 없음 |
| SR | 과거 같은 월의 한계 | 월/원천 scope·as-of·기준기간 불일치 |
| ST | 이전 10년 이상 같은 월 평균±정수배 표준편차 | 짧은 이력·미래 기준자료·통계 정의 없음 |
| DE | 수신 지연이 명시한 초 단위 한계를 초과하는지 비교 | 1–3시간/24시간 원문 차이 미해소 |
| PO | 실제 paired 전압이 명시한 최소 전압보다 낮은지 비교 | 전압 채널·단위 V·동일 시각 연결 없음 |

15항목×12종의 180개 조합 중 135개는 항목 적용표의 표시/공백, 45개는 LO/DE/PO 공통 조건이다. 공백을 정상 또는 전 항목 자동 적용으로 처리하지 않는다. 시정 경계, 기온 범위, 기압 SP의 잘못된 단위 표기, 파주기 SP 수치, RR/PR 코드 충돌 등은 `profile_id`와 명시적 `conflict_resolution` 근거 없이는 `NOT_EVALUATED`다. 상세 인터페이스·설정 예시는 [플랫폼 문서 83](../ocean-ai-platform/docs/83_QC_RULE_ENGINE.md)을 따른다.

## 시계열·단위·가용 시각

입력에는 정확한 관측 ID, station/sensor/variable/unit, physical sensor/episode, 관측 UTC·실제 가용 시각, 효력 구간 `[start,end)`와 근거가 필요하다. 순수 분석의 supplied 근거는 조건부 입력이며 그 hash/locator만으로 사실 승인이나 인간 권위가 생성되지 않는다. `/rules/execute`는 현재 승인된 source receipt/원문 bytes를 다시 검증하고 실제 적재 binding과 Standard의 값·단위·시각·자연키가 일치한 경우에만 이 입력을 구성한다. 미승인·변조·typed 값의 scalar 대표값은 계산하지 않는다.

SI 단위와 가이드 단위가 다르면 `unit_conversion`에 정확한 from/to/scale/offset와 근거를 명시해야 한다. m↔cm, Pa↔hPa, m/s↔cm/s의 허용 인자만 계산 사본에 적용한다. 원문과 Standard를 수정하지 않으며, 원래 값·단위·변환 근거를 결과에 보존한다. signed HF radial 값을 유속 크기로 추정하거나 vector/profile을 scalar로 바꾸지 않는다.

window와 보조 관측·통계 baseline의 `available_at`은 분석 `as_of` 이하여야 한다. 결과 가용 시각은 실제 분석 실행 시각이다. 나중에 계산한 과거 자료의 QC를 과거 online 근거 또는 그 당시 feature로 소급 사용하지 않는다. 정상/의심/불량은 `EVALUATED`, null/sentinel은 `MISSING`, 조건 부족은 `NOT_EVALUATED`이며, 미평가는 정상도 불량도 아니다.

## 검토와 최종 QC 변경

검토 후보는 `qc_flag_2nd`에 추천값을 저장하고 `qc_flag_final=None`을 유지한다. [승인 API](../ocean-ai-platform/backend/app/api/routes_approvals.py)의 `QC_CHANGE` 결정을 통해 reviewer/admin이 최종 flag를 설정한다. 요청 body의 `user_id`는 실제 인증 actor로 치환되고 이미 검토된 대상의 중복 결정은 차단한다. 인증 미설정·토큰 없음·권한 부족은 성공으로 처리되지 않는다.

이 QC 최종 결정은 [AI Label](13_AI_LABEL_SEPARATION.md)의 원인 정답이나 source 계약 승인을 생성하지 않는다. 규칙 버전의 결과를 바꿔 같은 입력이라고 주장하지 말고 새로운 버전과 검토 근거를 사용한다.

## 원천 계약 gate

[source_contract_authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py)는 실제 codebook 파일 SHA, rule version·QC 시행기간, source/QC 가용 시각, sensor episode·관측 시각을 요구한다. typed 자료는 성분마다 동일 검증을 수행한다. 원천 `G ` 등 padding 있는 코드를 임의로 정상으로 승격하지 않는다.

[qc_review_agent](../ocean-ai-platform/backend/app/services/qc_review_agent.py)의 `review_bundle()`은 supplied row·등록 근거를 검토하는 분석기다. 코드북·센서·기간·장비 연결이 없으면 차단 조건을 남긴다. [Evidence Fusion](../ocean-ai-platform/backend/app/services/evidence_fusion.py)은 실제 미평가 상태와 가용 시각을 소비하고, [durable workflow](../ocean-ai-platform/backend/app/agents/multi_agent_workflow.py)는 인간 결정 전에 후속 draft 단계 실행을 중단한다. Workflow 승인도 source/QC/라벨/모델 각각의 승인과 별개다.

## 평가와 현재 상태

2026-10-09 후속 일일 운영 화면과 읽기 전용 context/overview/candidate 경로는 [36](36_QC_OPERATIONAL_DASHBOARD_EXECUTION.md)을 따른다. 12종 엔진 catalog·실제 등록 Rule·저장된 실행 결과를 구분하고 원문 QC/MQ/N1을 임의로 확정 Flag에 매핑하지 않는다. source/QC 판본·exact sensor episode·기간과 가용 시각을 검증하며 현재 운영 입력은 0이다. registered SCALAR 지원과 typed QC·미수신 슬롯·candidate Final QC 연결의 남은 범위도 같은 문서에 명시했다.

모델 품질 평가는 [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md)의 별도 fixed evaluation/acceptance 계약을 따른다. human quality label과 rule QC flag를 분리하고 미평가 mask·false-good 위험을 함께 평가한다. source 표기율, rule score, cosine 검색 점수는 품질 정확도나 승인율이 아니다.

[12종 시험](../ocean-ai-platform/backend/tests/test_qc_rule_engine.py)은 각 검사 정상/이상, 원문 붙임 1의 범위/sentinel/간격별 SP, 미평가·경계·단위 동등성을 검증한다. [API 시험](../ocean-ai-platform/backend/tests/test_qc_rule_api.py)은 격리된 source 승인→적재→QC 저장과 변조/미승인 차단을 검증한다. 2026-10-08 실제 보존 Parquet의 500개 draft locator와 7개 원문 표기는 정확히 일치했지만 source 의미·단위·시간·센서 계약이 미확정이어서 12×500=6,000 결과 모두 `NOT_EVALUATED`였다. 이 표본을 전체 원천 또는 운영 승인으로 확대하지 않는다. 같은 날 운영 확인의 승인 원장 0은 시험 승인과 별개다.
