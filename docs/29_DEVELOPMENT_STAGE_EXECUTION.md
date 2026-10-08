# 29. 단계별 실행 결과와 부모 최종 검증

기준일: **2026-10-08** · 확인 UTC: `2026-10-08T11:44:28.046011+00:00`. [기계 판독 결과](29_DEVELOPMENT_STAGE_EXECUTION.json)와 [현행 상태](current_status.json)를 함께 확인한다.

세 에이전트가 구현·원천 검사·격리 실행을 담당하고, 부모가 전체 회귀·실제 PostgreSQL·원문 locator·실 API·브라우저·운영 원장 무변경을 검증했다. 구현, 시험, 자료 준비, 승인, 운영을 별도로 판단한다. 실제 계정 설정은 사용자 지시대로 `DEFERRED_BY_USER`이며 승인·미확정 원천 사실·운영 모델을 임의로 생성하지 않았다.

| 단계 | 담당 | 이번 실행·보완 | 남은 완료 조건 |
|---|---|---|---|
| 1 | `identity_events + 부모` | 소규모 상태 7파일·전체 PostgreSQL 48테이블 복구 검증 | 운영 자동 백업·보존주기와 복구 책임자 이관 |
| 2 | `identity_events` | 이전 SHA 원장 917,943파일·1.89TB 재정산, 파생 메타데이터 18파일 분리·검증, 7월 146파일 fresh 검증 | GD 월말 부족·GR 의미 검토. 전체1.89TB fresh 재해싱으로 표기하지 않음 |
| 3 | `semantic_qc` | 66,190개 typed 원천 단위 검토; naïve MDC 날짜의 임의 KST→UTC 변환 제거 | 의미·단위·배율·기준면·시각·QC 판본/시행기간의 과거 증빙 |
| 4 | `identity_events` | 40사건 후보 원천 SHA, HWP 이력5건·152월 단위 검토 | 인천 재고/교체 날짜 충돌·serial 실물 동일성·연속 기간 확정 |
| 5 | `identity_events` | 1,842경로 전수 parser+보존 해시 검사, 81개 내용·8,761chunks 별도 임베딩; 재개·검토·승격·보호된 rollback 구현 | 암호144·손상1·font partial113 해결, 남은 본문 임베딩·검색 수용 시험, 실제 operator 승격 |
| 6 | `semantic_qc` | 12 Rule 조건부 구현·참조·변조 차단, 실제1,500행×12종=18,000결과 | 실제 결과 전부 NOT_EVALUATED. 확정 물리 조건·QC 적용 계약 필요 |
| 7 | `semantic_qc` | 3원천 raw fit, TRAIN300/CALIBRATION100/TEST100, 552평가+48warm-up | 조위 예측/기준면·paired센서·오염/열화 장비 문맥·truth·수용 기준 |
| 8 | `semantic_qc` | Rule+AI+Metadata+Operation+RAG score, exact report/grain/row·Rule12 재현 검증 | 원시 Fusion3건. 실제 물리 Rule/AI·사건/운영/RAG 근거 미완료 |
| 9 | `부모` | PostgreSQL 영속 PENDING·반려·철회·stale·권한·재개 8검증 | 실제 담당 계정은 사용자 지시대로 업무 시점에 연결 |
| 10 | `model_comparison` | legacy 원본 보존→새 BUILT v2, 승인 의존성·세 분할·고정 정책 검토 및 UI | 실제 승인 source/protocol·Dataset 3버전 생성과 독립 승인 |
| 11 | `model_comparison + 교차검토` | 3실원천 같은 TEST 각97쌍, validation 선정·train 적합, 독립1,500셀/291예측 재산정 | 72업무는 6자료형 기준선 부분 범위. 업무별 승인 어댑터·평가·수용 필요 |
| 12 | `model_comparison` | 격리 worker→독립 재현/등록→인증 예측→배포2회→승인 rollback 완주 | 실제 registry/serving 0. 감시·자동 trigger·운영 SLA 이관 필요 |
| 13 | `부모` | 최종 전체 backend 668통과/1skip, frontend17통과·build, 실API/브라우저·원장 무변경 검증·문서화 | 확정 입력과 실제 운영 수용·계정·담당 이관 |


## 검증 범위

전체 backend **668 passed / 1 skipped / 21 warnings**, 약 229.35초; frontend **17 passed**, TypeScript/Vite build PASS다. 각 담당의 부분 시험은 전체 시험과 겹치므로 통과 수를 더하지 않는다. 현재 review OpenAPI는 **154경로 / 163 operation**이며 실 HTTP13검증을 통과했다.

부모가 PostgreSQL 실제 임시 schema에서 승인·영속 stop/resume 8건을 검증하고 schema를 제거했다. 전체 `pg_dump`는 읽기 전용 exported snapshot을 사용했으며 약100MB archive를 새 임시 DB에 `pg_restore`했다. 48 public table 전체 건수, column schema, index definitions, 주요 승인/Dataset/모델 원장 row digest가 일치했다. 모든 원문 행을 새로 개별 해싱한 시험은 아니다. 임시 DB와 컨테이너 임시 파일을 제거했고 백업은 로컬 전용으로 보존했다.

운영 source·approval·Dataset·Model·workflow·QC 원장은 시작/종료 건수와 row digest가 같다. 실제 계정0, source/승인/Dataset/Model Registry0이며 `mdc_sensor_catalog`는 미적용이다. 임시 fixture 계정·모델2건을 운영 결과로 집계하지 않는다. canonical 서비스8000/5173·Chroma8001과 기존 worker를 유지했다.

## 실제 원천 실험의 의미

DT_0001의 2023-01 원천 AIR_PRES·WATER_TEMP·SALINITY 각각500행을 원문 숫자/시각/locator 그대로 읽었다. 원시 SPIKE/PERSISTENCE 적합3개·예측600개에서552개를 평가하고48개는 warm-up 미평가로 남겼다. 후보는0/14/0이며 정상·고장 truth가 없어 정확도나 장비 원인을 산정하지 않는다. 별도 forecast TRAIN300/VALIDATION100/TEST100 실험은 각97개 같은 TEST쌍으로 Ridge와 persistence를 비교했다. 세 TEST에서는 persistence 오차가 작았지만 WATER_TEMP의 VALIDATION 선정 Ridge를 TEST 결과로 바꾸지 않았다.

부모/교차검토는 현재 Parquet 전체SHA·manifest SHA·1,500셀·고정 membership과 별도 NumPy/sklearn 계산을 대조했다. 원시 artifact는 production worker와 호환되지 않는다. 단위·시간대·실물 센서·QC·online availability가 미확정인 원시 숫자를 승인 물리 모델 또는 72개 운영 모델로 표기하지 않는다.

## 문서 복구와 원천 사실

대기/실패1,842경로의 원본C·별도D 해시가 모두 일치했다. 경로 기준 parseable1,584·font partial113·암호144·손상1이다. unique 내용951 중 parseable786·partial58·blocked107이다. 읽기 가능한 고유 문서의 parser semantic blocks는 약358만으로 전량 임베딩 완료를 주장하지 않는다. 별도 저장소에서 완료한 **81개 내용 / 8,761chunks**와 정확 ordinal 재개를 보존했다. 추가 PARTIAL1문서/138chunks는 검색·승격에서 제외하며 총 저장은8,899chunks다. parseable786개 중 미완료705개가 남아 있다. 현재 canonical 대기1,697·실패145는 그대로이며 공개 전환0이다.

승격은 현재 원본/보존 SHA, 활성 embedding 모델 digest·차원·contract, 정확 parser chunk/ID, 현재 canonical ledger revision을 재확인한다. SQL 모든 열의 publication postimage를 receipt/checkpoint와 묶어 재실행·crash 재개·rollback 전에 다시 검증한다. 이후 사람이 수정한 본문/metadata와 기존 chunk는 덮어쓰거나 삭제하지 않는다. 실제 적용은 operator 인증을 요구한다. [복구 절차](85_OPERATIONS_RECOVERY_REVIEW.md)를 따른다.

HWP에서 인천2019-02-27 `118→1276`, 2021-03-24~26 `1276→1326`, 군산2020-02-20~21 `1326→333` 문구를 확인했다. 인천 재고의1326/2019-02-27과 교체 날짜는 여전히 충돌하며 관측소 간 같은 serial이 같은 실물이라는 근거가 없다. 날짜는 DAY/header-range 원문이며 UTC나 연속 센서 episode를 임의 생성하지 않았다. 40사건/152월 검토 결과도 인간 승인이 아니다.

## 사용 화면과 증거

[시스템 관리](http://127.0.0.1:5174/system)는13단계의 구현·시험·자료·승인·운영 및 남은 입력을 표시한다. [MLOps](http://127.0.0.1:5174/mlops)는 legacy 검토·정책 초안·승인3Dataset 선택·manifest SHA preflight·큐 요청을 연결한다. 현재 승인 입력0이므로 변경/학습 버튼은 차단된다.

로컬 증거 root는 `D:/AI_Observation/outputs/development-stages-20261008`다. root `stage-index.json`은 receipt 경로와 전체 SHA를 고정한다. receipt 불일치·누락은 FAILED/UNKNOWN이며 문서의 APPROVED/OPERATING 문자열은 권한을 부여하지 않는다. 원문·실험 상세값·SQLite·전체 DB backup·비밀번호·token은 Git에 올리지 않는다.

이전512/548시험과 과거 migration 수치는 이전 확인 기록이다. 현재 판정은 이 문서와 current_status.json의 최신 시각·분모·SHA를 따른다.
