# QC Rule Result 계층

현행화: 2026-10-08

## 원천 표기·규칙 결과·최종 판정

세 값은 별도로 관리한다.

| 값 | 저장·역할 |
|---|---|
| 원천 QC/MQC/N1 | 원문·Parquet의 literal. 원천 codebook과 시행기간을 검토해야 해석할 수 있다. |
| `QCRuleResult` | 특정 규칙 버전의 입력·임계값·결과·실행시각. 최종 인간 승인과 별개다. |
| `QCFlagHistory.qc_flag_final` | 검토자가 결정한 최종 QC. 검토 후보 생성은 이 값을 비워 둔다. |

[모델](../ocean-ai-platform/backend/app/models/domain.py)은 `observation_id + qc_rule_id + rule_version`의 규칙 결과 유일키를 사용한다. 결과에는 관측 scope, stage, input/threshold, result flag/score, rule version 및 executed_at을 저장한다.

## 현재 규칙 실행

[QC API](../ocean-ai-platform/backend/app/api/routes_qc.py)는 다음 경로를 제공한다.

| 경로 | 동작 |
|---|---|
| `GET/POST /api/qc/rule-definitions` | 규칙·적용 변수·threshold_definition·버전 등록/조회 |
| `POST /api/qc/rules/execute` | Standard를 관측소/센서/변수/시각으로 제한해 최대 10,000행에 활성 규칙 적용 |
| `GET/POST /api/qc/rule-results` | 규칙 결과 조회/등록. POST는 Standard 존재·중복 버전을 확인 |
| `POST /api/qc/review-candidates` | 실행 결과로 검토 후보 생성. 결과가 없거나 지원하지 않는 flag는 차단 |
| `POST /api/qc/copilot/analyze` | 저장 결과와 문서 근거의 분석 응답. 최종 QC 자동 확정 없음 |

현재 `/rules/execute` 계산은 `threshold_definition.min/max` 범위 검사다. 값 없음은 `9`, 범위 위반은 `4`, 나머지는 `1`을 기록하고 응답은 `ANALYSIS_ONLY`다. 규칙 이름·algorithm_description만으로 persistence, 공간 비교, 전 규칙의 재현 실행이 구현됐다고 해석하지 않는다. 업무별 threshold, codebook 의미와 시행기간 검토가 필요하다.

## 검토와 최종 QC 변경

검토 후보는 `qc_flag_2nd`에 추천값을 저장하고 `qc_flag_final=None`을 유지한다. [승인 API](../ocean-ai-platform/backend/app/api/routes_approvals.py)의 `QC_CHANGE` 결정을 통해 reviewer/admin이 최종 flag를 설정한다. 요청 body의 `user_id`는 실제 인증 actor로 치환되고 이미 검토된 대상의 중복 결정은 차단한다. 인증 미설정·토큰 없음·권한 부족은 성공으로 처리되지 않는다.

이 QC 최종 결정은 [AI Label](13_AI_LABEL_SEPARATION.md)의 원인 정답이나 source 계약 승인을 생성하지 않는다. 규칙 버전의 결과를 바꿔 같은 입력이라고 주장하지 말고 새로운 버전과 검토 근거를 사용한다.

## 원천 계약 gate

[source_contract_authority](../ocean-ai-platform/backend/app/services/source_contract_authority.py)는 실제 codebook 파일 SHA, rule version·QC 시행기간, source/QC 가용 시각, sensor episode·관측 시각을 요구한다. typed 자료는 성분마다 동일 검증을 수행한다. 원천 `G ` 등 padding 있는 코드를 임의로 정상으로 승격하지 않는다.

[qc_review_agent](../ocean-ai-platform/backend/app/services/qc_review_agent.py)의 `review_bundle()`은 supplied row·등록 근거를 검토하는 분석기다. 코드북·센서·기간·장비 연결이 없거나 recorded recheck의 현재 적용성을 재확인하지 못하면 `NOT_EVALUATED`/차단 조건을 남긴다. 과거 recheck를 현재 실행 결과로 간주하지 않는다. 호환 [multi_agent_workflow](21_MULTI_AGENT_WORKFLOW.md)의 휴리스틱 `range_rule`과 PENDING marker도 운영 승인 gate를 대체하지 않는다.

## 평가와 현재 상태

모델 품질 평가는 [MLOps](19_MLOPS_VERSION_AND_EVALUATION.md)의 별도 fixed evaluation/acceptance 계약을 따른다. human quality label과 rule QC flag를 분리하고 미평가 mask·false-good 위험을 함께 평가한다. source 표기율, rule score, cosine 검색 점수는 품질 정확도나 승인율이 아니다.

[QC 시험](../ocean-ai-platform/backend/tests/test_qc_review_agent.py), [안전 workflow 시험](../ocean-ai-platform/backend/tests/test_safety_workflow.py), [source authority 시험](../ocean-ai-platform/backend/tests/test_source_contract_authority.py)은 규칙/승인 경계와 근거 누락 차단을 확인한다. 2026-10-08 운영 확인에서 승인 원장은 0이었으며, 공개 코드 시험 통과를 실제 QC 전수 승인으로 표시하지 않는다.
