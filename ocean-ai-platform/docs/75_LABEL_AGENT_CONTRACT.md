# Label·Dataset 에이전트: 근거 선행검토와 읽기 전용 계약

작성: 2026-10-07. 기준일 2026-07-31. 모든 문서 의미검토 완료를 뜻하지 않는다.
추출·임베딩 건수는 아래 페이지를 실제 검토한 범위와 별개다.

## 먼저 확인한 근거와 반례

원장은 `D:\AI_Observation\outputs\share-validation\run-20261006T082954Z\evidence.sqlite3`,
완성 검증표는 같은 폴더의 `validation-20261006T115552Z\validation.sqlite3`이다.
읽기 전용 SQLite 연결로 조회했다. 134056Z 진행 중 표를 최초 탐색했지만 확정 근거표는 115552Z로 다시 확인했다.

| 근거·실제 읽은 위치 | 확인한 내용과 날짜 의미 | 구현상 결론 |
|---|---|---|
| 2025 결과보고 별권 `07 인천_조위관측소_이력집_2024.pdf`, PDF 7쪽(인쇄 -3-), 표2·3, 직접 렌더 확인 | VEGA PS64 46950802 설치 2021-03, OTT Thalimedes 284083 설치 2020-03. 표3 조위 DB 제공 1999-02, 염분 2001-12. 설치월과 DB 제공월은 서로 다른 열 | 월을 실제 설치일로 만들지 않음. 장비 serial/모델만으로 원천 channel을 물리센서에 배정하지 않음. 종료·사용기간 NULL 유지 |
| 2025 결과보고 본권 `제02장_해양관측자료_품질처리_251224.pdf`, PDF 7쪽 표2-4, 저장된 페이지 이미지 직접 확인 | 인천 염분 2024-12~2025-06은 '감도 저하 추정'; 세척일 2024-12-26은 조치일. 태안 2025-09 조위는 MIROS 회수 09-03→VEGA 교체 10-01 | 월 단위 이상기간을 분 단위 고장정답으로 확장 금지. 추정원인과 확인원인 분리. 2025 사후보고를 2024 예측의 입력으로 사용 금지 |
| `국가해양관측망 일일점검 보고서(250901).hwpx`, `Contents/section0.xml:table_row:21`, 원문 추출 행 확인 | 태안 9.1 03:44~08:33 전항목 부분결측, 수집프로그램 멈춤, 관측PC 재부팅. 검증표 AIR_PRES 공백 17,160초, 나머지 일부 항목 17,220초 | 시간상 공백부합은 측정센서 중단 원인확정이 아님. 수신시각/재수집 로그 필요. 양끝 포함 비교 결과를 승인된 반개구간으로 자동 변환하지 않음 |
| `국가해양관측망 일일점검 보고서(241202).hwpx`, `Contents/section0.xml:table_row:6`, 원문 행 확인 | 옹진소청초 10.24 00:02~ 수신지연, CT케이블 또는 센서 손상 '추정', 장비교체 '예정(11월)' | 보고일 12-02, 사건시작 10-24, 조치계획 11월 구별. 열린 구간과 추정을 closed event/확인원인으로 승격 금지 |
| `2-2-3. 해양관측시설관리대장 - 동해.hwp`, `Section0/record:1077/level:3`, `2572/level:3`; 검증표 facility_block:2 | 장비번호 55712217와 레이더식 VEGA 설치 문구 확인. 검증표의 PS64/2022.12 설치월 후보는 문단 순서 재검토 상태 | 원문 paragraph 일부만 읽었으므로 표 전체 의미검토 완료 아님. 이 설치월로 유효기간을 채우지 않음 |
| 2025 제01장·제07장·제14장 각각 PDF 7쪽 추출 텍스트 | 제1장은 월별 보고건수 집계; 제7장은 MODI/WEB 조석성과 불일치와 미산출·기존값 부재 구별; 제14장은 2025-10 부이36개 및 신설·재배치 계획 | 보고건수를 고장사건 수로 복사 금지. 시스템값 차이는 센서고장의 직접증거 아님. 계획·2025 운영수를 2026-07-31 운영확정으로 복사 금지. 세 페이지는 표 영상 검증 미완료 |

SHA-256 (위 순서의 고정 원문 식별):

- 인천 이력집: `45dc1b12fb386540a33de803857d42950f58be677867254563bf39676c8a158f`
- 품질처리 보고: `edd7d6bdac8b8de35a099c8f57be8c5b1f7c33ed283f4bdac9cf23ec3993b125`
- 250901 일일보고: `f9f60e55240400b70efe9f31f578ace091028cc6f35a978b11ca01f65daf27a8`
- 241202 일일보고: `4d2fb573b7df62f08b6f9e156c261df8932615d351565e2665540ba0517b2bfe`
- 동해 관리대장: `ae295f0e52e7ad20632fd56c09cf52e7a3c5b4205fa5ddebfd1539413257dd6b`
- 제01장: `a91190885be50b5daa7507946ff8daca0ecae29bddeb51cf3848bee61536a892`
- 제07장: `efde5b5611b285b8d73bc3c131fff15a6e6dfc7dfaf991936a269387cd90bd0d`
- 제14장: `dd116d76375be2ade7f3869a5db862053c574350f2230269d7eca94419701ae3`

보고서 파일명의 날짜는 판본 식별에만 쓰며 정식 발행일/업무상 최초 가용시각으로 간주하지 않는다.
원문 전체, 다른 관측소 이력집 전체, 센서 관리대장 표 전체, 모든 점검일자의 검토는 남아 있다.

## 업무 절차

입력(원문 hash/위치, 관측소·항목·구간) → 검사(원천자료·실제 센서·시각 일치) →
판정 후보(원천 QC와 재검사와 원인추정 별도) → 담당자 근거검토 → 인증된 reviewer 승인 →
승인 snapshot·멤버십 기록 순서다. 문서가 현행 소프트웨어 승인 API 자체를 규정한다고 주장하지 않는다.
승인 API는 기존 프로젝트 계약 `routes_approvals`와 `routes_datasets`를 따른다.

## 구현 계약

`app.services.label_review_agent.propose(db, request, qc_output=None)`와
`app.agents.label_agent.run`은 JSON 직렬화 가능 결과를 반환한다.
입력: `event_id`, `observation_ids`(최대100), `registry_run_id`와 `channel_record_ids`(최대100),
선택 `dataset_id`. 단독 QC 맥락도 미확인 근거 후보로 표시한다.
QC `audit.run_id`와 `interval_evidence.channels[].record_id`가 있으면 이를 DB 재조회 선택자로만 사용한다.
upstream의 sensor/승인/원인 payload는 사실로 채택하지 않는다.
`prediction_document_ids`(chunk ID)와 offset 포함 `prediction_at`을 주면 원문 metadata의
`available_at`과 보고일을 비교한다. 가용시각이 없거나 미래이면 feature 사용·승격을 차단한다.
이 검사는 요청에 지정된 문서에 한정되며 모든 Feature 정의의 의미를 자동 추론했다고 주장하지 않는다.

출력은 `DRAFT` 또는 `NEEDS_EVIDENCE`, `human_label=null`, `error_cause=unknown`,
`training_eligible=false`, `read_only=true`다. source_flags, recheck_flags는 별도 필드다.
PG registry record_id를 재조회하여 실제 NULL sensor/valid_from/valid_to를 보존한다.
ai_label의 NOT NULL을 맞추기 위한 가짜 센서 생성, commit/flush/approve, 학습셋 membership 생성은 없다.

Dataset은 최대500관측 범위에서 기존 `validation_errors`를 재사용하여 승인 라벨 proof,
FeatureProvenance 가용시각·window·source hash, snapshot 무결성, split 시간·관측소 누수를 확인한다.
같은 dataset_name 실험군의 다른 split에 동일 event가 있으면 추가 차단한다.
검증상한을 넘으면 부분검사를 성공으로 보고하지 않는다.
`promotion_eligible`은 검토 진입 가능 여부이며 담당자 승인이나 실제 학습허용이 아니다.

## 검증 및 잔여 범위

선행 사례 확인 후 코드·시험을 보완했다. 격리 SQLite 테스트 10건 통과:
원천/재검사/정답 분리, NULL센서, simulated배제, 사건반개구간/범위,
미승인 dataset 차단, 동일 사건 split중복·시간누수, 상한, 호출자 변경 autoflush방지,
사후보고 가용시각·미래누수, QC payload 재검증을 확인했다.
실제 PostgreSQL READ ONLY 트랜잭션에서 `facility-20261006T161343Z`의 channel 3건을 검사했다.
모두 NULL sensor/valid_from/valid_to를 유지하고 NEEDS_EVIDENCE, human_label NULL을 반환했다.
위조 sensor를 포함한 QC envelope도 record_id로 재조회해 같은 결과였다.
전후 ai_label/dataset_membership/approval_history는 각각 0으로 변화 없었다.
실제 운영데이터를 쓰거나 학습·승인하지 않았다.
실행기록: workspace `label_agent_stage/live-check.json`.
QC 에이전트에 교차검토 요청했고, MLOps에 승인자 일치·현재 멤버십·계보 추가검증 항목을 전달했다.
MLOps 에이전트는 reviewer 동일성, snapshot hash 확인과 계보검증을 분리하고
계보 미검증을 명시적 blocker로 반환하도록 반영한다고 회신했다. QC 교차검토 회신은 아직 미수신이다.
후속 회신: QC 담당자는 실제 QC→Label 3채널 연동을 독립 재검증했고 자동승인/가짜센서 경계를 확인했다.
QC의 선택 ORDER BY 권고와 MLOps의 event 상한 초과 후 loop 지속 결함을 반영했다.
100건 상한 초과 시 즉시 중단하며 per-event count/계보 조회를 하지 않는 회귀시험을 추가했다.
Label 11개 + QC 8개 합계 19개 테스트가 통과했다.
기존 `test_event_evidence.py` 13건을 함께 실행하는 회귀검증은 pytest 임시 폴더
PermissionError로 setup 단계에서 막혔다(기본 TEMP와 지정 workspace basetemp 둘 다).
이 13건을 통과했다고 보고하지 않는다. 신규 Label 10건은 해당 재실행에서도 통과했다.
원천 파일의 실제 timestamp가 없는 registry channel에는 사건시각이나 물리센서 ID를 추정하지 않는다.
