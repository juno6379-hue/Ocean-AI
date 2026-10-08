# QC Copilot 근거 기반 분석

`POST /api/qc/copilot/analyze`는 표준 관측값을 기준으로 실행된 `QCRuleResult`, 동일 시각의 AI 예측, 최근 운영 이력, Hybrid Retrieval 문서 근거를 한 응답으로 조립한다.

응답의 `recommended_flag`와 `cause_candidates`는 분석·추천 값이다. `approval_required=true`, `status=ANALYSIS_ONLY`를 항상 반환하며 `QCFlagHistory.qc_flag_final`을 자동으로 변경하지 않는다. 승인 API에서 사람의 판단을 기록한 뒤에만 최종 QC와 재학습 풀로 환류한다.
