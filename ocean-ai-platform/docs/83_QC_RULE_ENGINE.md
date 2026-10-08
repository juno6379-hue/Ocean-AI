# 가이드북 12종 Rule QC 엔진

작성·검증: 2026-10-08. 구현은 조건부 분석이며 실제 원천·최종 QC·학습·운영 모델 승인을 생성하지 않는다.

## 기준본과 구현 범위

기준본은 `해양관측자료 품질관리 가이드북(개편)`, 표지 2023.12, SHA-256 `d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9`, 118페이지다. PDF 23페이지 표 2-7의 기존 1차 검사 12종을 구현했다. PDF 24페이지 표 2-9의 15항목 적용 표시, PDF 81페이지 붙임 1의 기존 수치, PDF 83–92의 세부 조건을 [카탈로그](../backend/app/services/qc_rule_catalog.json)에 보존했다. PDF 번호는 1부터 시작하고 인쇄 페이지는 PDF 번호−7이다.

기존 2차 검사 표 2-8, 개선안 10종 표 2-10~2-12/붙임 2, 모든 공간/예측/잔차 알고리즘 구현으로 확대하지 않는다. LO는 명시적 WGS84 사각 범위 방식, RL은 아래 3개 관계만 지원한다. 나머지 방식은 `NOT_EVALUATED`다.

| 검사 | kind | 실제 실행과 필수 설정 | 근거 PDF |
|---|---|---|---|
| 시간 | WT | actual `received_at` < 관측 UTC이면 hard 위반. 수신 근거 필요 | 23, 83 |
| 위치 | LO | `method=WGS84_RECTANGLE`, lat/lon min/max, station_type, 위치/좌표계 근거 | 23, 84 |
| 오류값 | ER | 항목별 `sentinels` exact match; null/명시 sentinel은 MISSING | 23, 81, 83 |
| 전지구 한계 | GR | `min/max/boundary=CLOSED 또는 OPEN`, 단위·물리량·TIDE 기준면 | 23, 81, 83–92 |
| 고정값 | GD | `duration_seconds/interval_seconds/duration_boundary`, 명시 tolerance | 23, 81, 83–92 |
| 내적 일치 | RL | GUST_GE_WIND_SPEED, CIRCULAR_DIRECTION_DIFFERENCE, WAVE_HEIGHT_PERIOD | 23, 89–91 |
| 튐값 | SP | 정확 interval의 `max_delta`, LINEAR 또는 CIRCULAR_DEGREES 차 | 23, 81, 83–91 |
| 지역 한계 | RR | 과거 baseline min/max와 EXACT_EXTREMES 또는 MULTIPLY_EXTREMES | 23, 35, 84 |
| 계절 한계 | SR | RR 조건에 같은 월 제약. 기준기간·방법 명시 | 23, 84 |
| 통계 | ST | 이전 10개 이상 고유 연도·같은 월 평균/표준편차·정수 multiplier | 23, 87, 92 |
| 지연 | DE | actual received−observed > `max_delay_seconds` | 23, 81 |
| 전원 | PO | 같은 시각의 실제 paired 전압 < `minimum_voltage`, 단위 V | 23 |

표 2-7의 hard(WT/LO/ER/GR/GD), soft(나머지) 구분에 따라 조건부 위반 추천은 4 또는 3이다. RL은 PDF 81의 Hard 분류와 충돌하여 `failure_flag=3 또는 4` 및 충돌 검토 근거를 반드시 명시한다. 이는 raw QC 코드의 의미 변환이나 최종 판정이 아니다. ER에서 null/sentinel은 오류 수치로 재분석하지 않고 9/MISSING으로 분리한다. 타 수치 검사는 명시한 `missing_sentinels` 정책으로 결측을 제외한다. 값이 null이어도 WT/LO/DE/PO는 해당 시각/위치/전원 조건을 별도로 검사한다.

## 원문 충돌과 적용표

카탈로그의 `summary_profile`은 문서상 수치를 보존한 reference다. 운영 기본값이 아니다. 15×12=180 조합 중 135개는 표 2-9의 9검사 적용 표시/공백, 45개는 LO/DE/PO의 공통 조건이다. 예를 들어 TIDE의 ST, SOLAR_RADIATION의 GD는 적용표에 표시되지 않아 자동 적용하지 않는다. 세부 원문에 다른 내용이 있어도 이를 소리 없이 섞지 않는다.

충돌 목록에는 기온 −50/−80℃, 시정 open/closed, 파고·파주기 범위 경계, GD 기간 경계, DE 1–3h/24h, RR/PR 코드, 지역/계절 기준기간, RL hard/soft 분류, 기압 SP의 psu/파주기 오표기와 interval 수치 차이 등이 있다. `provenance.profile_id`, `configuration_reference`, 해당 검사에 필요한 `conflict_resolution` SHA/locator를 명시하지 않으면 계산하지 않는다. `APPENDIX1_SUMMARY_P81`을 선택하면 단위·범위·sentinel·flat duration·SP interval/threshold·DE 24h가 해당 원문 수치와 정확히 같아야 한다. 근거의 SHA/locator 형태 검사는 원문 내용이 운영 승인되었다는 뜻이 아니다. 본 엔진의 값 선택은 호출자가 제공한 조건부 설정이며, 공식 도입 판단은 별도 검토 대상이다.

RL 파고/주기는 기존 PDF 90의 `period>5: height<2.55+period/4`, `period<5: height<1.16×period−2`를 구현한다. `period=5`는 LONG_PERIOD/SHORT_PERIOD/NOT_EVALUATED 정책을 명시해야 한다. 개선안의 다른 분기로 자동 변경하지 않는다. 방향 차는 359°와 1°의 거리를 2°로 계산한다. paired 수치의 station·시각·단위·sensor 연결·효력기간·가용 시각을 독립 확인한다.

## 순수 함수 입력 계약

[execute_rules(records, rules, context)](../backend/app/services/qc_rule_engine.py)는 DB·네트워크·시스템 시각을 읽지 않는다. 10,000행, 100규칙, 행×규칙 120,000개의 상한을 둔다. JSON 비유한 숫자·잘못된 분석 시각은 ValueError, 개별 입력/설정 조건 부족은 구조적 `NOT_EVALUATED`로 반환한다.

각 record에는 아래 값이 필요하다.

* observation_id, station_id, sensor_id, variable_code, unit, scalar value
* 명시한 offset의 timestamp_utc와 실제 available_at
* source_facts의 physical_sensor_id, sensor_episode_id, quantity_kind, clock_semantics, effective_start/end, evidence `{sha256,locator}`
* TIDE는 정확 reference_datum. 본문이 지정하지 않은 기준면을 ML 등으로 추정하지 않는다.
* quantity_kind는 카탈로그의 정확한 의미 종류와 같아야 한다. 특히 CURRENT_SPEED_SCALAR_MAGNITUDE에 SIGNED_RADIAL/vector/profile을 넣지 않는다.

공통 source 효력 구간은 `[start,end)`다. `context.as_of`와 `context.executed_at`은 explicit offset이고 실행 시각은 as-of 이상이다. 수치 검사는 관측 시각 이전 가용이나 as-of 이후 관측값을 소비하지 않는다. WT만 원문 정의에 따라 실제 수신·가용 시각이 확인된 미래 raw clock을 오류로 진단할 수 있다. 이 진단은 미래 관측 수치를 정상 이웃/feature로 쓰는 허가가 아니며 Fusion의 미래 event 제외도 유지한다. raw local timestamp의 UTC 변환이나 DST fold 선택을 이 모듈에서 하지 않는다.

각 rule은 qc_rule_id, rule_version, kind, parameters, provenance를 갖는다. parameters에는 exact variable_code/unit/quantity_kind와 검사별 설정을 넣는다. provenance에는 guide_sha256, one-based pdf_pages, profile_id와 configuration_reference를 넣고 충돌 검사에는 conflict_resolution도 넣는다.

```json
{
  "qc_rule_id": "SITE_AIRPRES_GR",
  "rule_version": "review-config-1",
  "kind": "GR",
  "parameters": {
    "variable_code": "AIR_PRES",
    "quantity_kind": "AIR_PRES_SCALAR",
    "unit": "hPa",
    "min": 850,
    "max": 1060,
    "boundary": "CLOSED",
    "missing_sentinels": [-9999],
    "unit_conversion": {
      "from": "Pa", "to": "hPa", "scale": "0.01", "offset": "0",
      "evidence": {"sha256": "<실제 근거의 64자리 SHA>", "locator": "<검토한 정확 위치>"}
    }
  },
  "provenance": {
    "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
    "pdf_pages": [23, 81, 87],
    "profile_id": "APPENDIX1_SUMMARY_P81",
    "configuration_reference": {"sha256": "<실제 설정 SHA>", "locator": "<업무·항목·기간 범위>"}
  }
}
```

위 예시의 placeholder는 실행 가능한 근거가 아니다. 원문 pressure 값의 의미/단위가 미확정인 상태에서 이 설정을 넣어 운영 사실을 만들지 않는다. 허용 dimensional conversion은 m↔cm, Pa↔hPa, m/s↔cm/s의 정확 scale/0 offset이며 명시한 from/to/evidence가 있어야 한다. 원본·Standard는 수정하지 않고 계산 사본만 변환한다. 원래 값·단위·source record SHA·변환 근거를 input_normalization에 보존한다. baseline의 min/max/mean/std도 같은 명시적 단위 변환을 적용한다. 알려지지 않은 단위, 온도/psu/HF 의미 변경, angular/vector scalar 변환은 지원하지 않는다.

GD/SP는 현재 이전의 동일 station/sensor/variable/unit/physical episode window만 사용한다. 간격 허용 오차를 명시할 수 있으나 interval보다 작아야 한다. gap·중복 시각·역순·결측·센서 교체·원래 단위 변경을 연결하지 않는다. window가 부족하면 정상으로 판단하지 않는다. 미래 이웃을 사용하지 않는 causal SP다.

RR/SR/ST baseline에는 exact scope/unit, period_start/end, available_at, source_episode_policy, QC 제외 evidence가 필요하다. `calendar_timezone`은 source_facts.source_timezone_name과 baseline의 명시값이 같아야 하며 ZoneInfo로 해당 원천의 연도·월을 계산한다. KST 연말/월말을 UTC calendar로 대체하지 않는다. 기간·as-of 비교는 UTC instant로 유지한다. target보다 뒤의 기간·기준자료는 금지한다. ST는 같은 월, 이전 10개 이상 고유 연도와 MONTHLY_MEAN_STD/sample_count가 있어야 한다. 현재 target으로 기준 통계를 다시 계산하지 않는다. baselines가 없으면 historical extrema를 추정하지 않는다.

## 결과·저장·Fusion

결과는 `guide-qc-report-v1`, status ANALYSIS_ONLY, approved false다. 전체 report의 `result_sha256`은 이 hash 필드를 제외한 canonical JSON의 SHA로, flag/scope/provenance를 함께 묶으며 Fusion 소비 시 재검증한다. 각각 EVALUATED/MISSING/NOT_EVALUATED와 result_flag/reason을 분리한다. 결과의 가용 시각은 `executed_at`이며 나중에 재계산한 과거 QC는 과거 online feature로 소급 사용할 수 없다. rule score는 고장 확률로 만들지 않아 null이다.

provenance_json에는 engine version, guide SHA/pages, 전체 rule 설정 SHA, input window SHA/IDs, evidence_scope, source_facts, event_at, event_clock_policy, input_available_at, available_at, executed_at_utc, as_of와 명시적 단위 변환을 저장한다. `metadata_authority=SUPPLIED_CONDITIONAL_ANALYSIS_INPUT`: supplied reference를 검증된 승인으로 승격하지 않는다.

[QC API](../backend/app/api/routes_qc.py)의 POST `/api/qc/rules/evaluate`는 순수 분석, GET `/api/qc/rule-catalog`는 reference 조회다. 기존 POST `/api/qc/rules/execute`는 현재 source ledger+exact receipt+원문/Parquet bytes와 실제 [SourceObservationBinding](../backend/app/models/source_observation_binding.py)의 proof를 재검증하고 Standard scope/시각/단위/값과 일치할 때만 guide 입력을 구성한다. 현재 bridge는 승인된 scalar 원천과 그 시각/단위/episode/receive proof를 지원한다. 위치·전원·관련 채널·통계 baseline의 실제 DB 연결은 아직 자동으로 구성하지 않으므로 그러한 자료가 없는 저장 실행은 해당 검사 N/E다. 해당 보조 자료를 명시적으로 제공하는 순수 엔진에서는 검사할 수 있다.

min/max만 있는 legacy 정의는 LEGACY_RANGE로 저장하고 가이드 동등성을 주장하지 않는다. 모든 조건을 놓친 legacy 정의를 GOOD으로 저장하지 않는다. 기존 result unique key를 덮어쓰지 않으므로 수정된 설정은 새로운 rule_version으로 기록해야 한다. 결과를 조회하는 API는 evaluation_status/result_reason/provenance_json을 포함한다. 기존 DB의 새 nullable 3컬럼은 [명시적 migration](../backend/migrations/20261008_qc_rule_evidence.sql)으로 적용하며 이 작업에서는 운영 DB를 변경하지 않았다.

[to_fusion_evidence](../backend/app/services/qc_rule_engine.py)는 EVALUATED flag4/3에 ANOMALY, flag1에 NORMAL, 결측/미평가에 UNKNOWN·strength0을 제공한다. 이는 확률이 아니라 규칙 severity 근거다. final flag, AI label, source/dataset/model 승인은 별도다. 미평가가 있으면 기존 final-QC review candidate 생성은 409로 막고 Copilot은 미평가를 BAD/GOOD으로 세지 않는다.

[seed_qc_rules](../backend/app/scripts/seed_qc_rules.py)의 기본 CLI는 DRY_RUN이다. `--apply`는 명시적으로 configured DB에 쓰므로 별도 실행 범위를 확인한다. 새로운 GUIDE2023_* 12개는 inactive, source-specific parameters/approval 근거 없음 상태로 생성되어 운영 적용을 주장하지 않는다. 기존 두 legacy range 정의와 멱등성은 유지한다.

## 검증과 실제 원천 한계

[엔진 시험](../backend/tests/test_qc_rule_engine.py)은 12종 정상/이상, 붙임 1의 모든 15항목 범위·sentinel 및 9항목 interval SP, 경계/기간/미평가/shape/단위 변환을 검증한다. [API 시험](../backend/tests/test_qc_rule_api.py)은 격리 원천·SQLite에서 실제 source 승인/ingest/QC 저장, Standard 변조 차단, inactive seed/순수 분석 무변경을 확인한다. 각 코드 경로 통과를 실운영 검토자 승인이나 실제 정확도로 표시하지 않는다.

2026-10-08 read-only 대표 원천 평가에서는 기존 AIR_PRES draft 500개 locator의 Parquet bytes SHA와 7개 raw literal/type(station/item/time/value/QC/MQC/N1)가 모두 일치했다. 단위·시간대·canonical sensor·물리 sensor episode·QC codebook·가용 시각이 미확정이어서 12×500=6,000개 요청 결과는 전부 NOT_EVALUATED, 실제 수치 품질 분류와 승인 생성은 0이다. MQC `G `를 GOOD으로 바꾸지 않았다. 이는 표본 500개 검토이며 전체 월·전체 원천 실행은 아니다. 운영 계정 설정은 별도 후속이며 순수 분석 시험에 가짜 actor를 만들지 않는다.
