# 원천 사실 재검증과 확정 범위

확인일: 2026-10-08. 실제 승인 계정 설정과 담당자 판정은 사용자 지시에 따라 이후 운영 단계에서 수행한다. 계정 부재를 이유로 가이드북 검토, 기술 사실 대조, 분석 엔진 구현과 격리 시험을 중단하지 않는다.

## 직접 확인한 사실

| 근거 | 기술적으로 확인한 내용 | 적용 범위 |
|---|---|---|
| 품질관리 가이드북 개편본, SHA `d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9` | 표지 2023.12, 표 2-7의 WT/LO/ER/GR/GD/RL/SP/RR/SR/ST/DE/PO 12종 | 이 문서 판본의 정의다. 개선안 10종이나 과거 운영 채택 이력과 구분한다. |
| 2026-10-06 보존 `items.json`, SHA `506267157606635bc85a7b4f82c8dfa0c9db45f0bcf3290b82d6096a468adb7f` | DT_0001의 AIR_PRES `hPa`, WATER_TEMP `℃`(U+2103), SALINITY `psu`; 저장 간격 literal `1` | 현재 메타데이터 참조다. 과거 모든 채널·파일의 단위, 배율, 센서 유효기간 계약으로 확대하지 않는다. |
| 같은 조회의 items/equipment/stations/qc_codes/column_comments | 기존 보존 SHA 6개를 다시 대조해 모두 일치. item 24,153행의 이름·단위에 U+FFFD 손실 0 | 터미널 표시 깨짐을 파일 자체의 문자 손실로 해석하지 않는다. |
| `08_EXTRACT_QC_RESULT.sql`, SHA `8583aca98c631d6ebfc1efeb61c433d820467be749630078c51adf067f79551b` | DT_0001의 GO_QC_RULE_NEW 11개 항목과 GO_QC_RULE 19개 항목의 캡처가 보존됨(24–36, 42–62행) | 캡처된 설정의 사실이다. SELECT `R.*` 결과의 열 순서·단위·시행기간을 별도 증명하지 않고 실행 정책으로 자동 가져오지 않는다. |
| `07_EXTRACT_QC_RESULT.sql`, SHA `e21a295705ff80a20b0b5b10e67b18e0fe8b5b80bd42a7c5e6b364e32081e4a8` | 2026-09-14 세션 `Asia/Seoul`, DB timezone `+09:00` 기록(3–17행) | 조회 당시 세션/DB 시계다. OBS_TIME 저장 기준과 변환 이력을 증명하지 않는다. |
| 보존 인천 역사 CSV·2024 조위 CSV | 실제 헤더·수치·QC literal을 읽을 수 있음. QC2/MQ의 `G ` 등 공백을 보존 | 헤더에는 역사 단위·시간대·기준면·물리 센서 기간이 없다. 관측 수치 자체와 그 물리적 해석을 구분한다. |

원본·SQL·실측 JSON은 로컬 보존 자료다. 위 표는 기술 사실과 hash만 공개하며 원문 전체, 장비 serial, 계정, 검토 패킷을 Git에 복사하지 않는다. 로컬 재검증 결과는 `metadata/reviews/current-implementation-20261008/source-facts-recheck.json`에 기록했다.

## 근거가 없어 아직 확정할 수 없는 연결

보존 item 24,153행 중 `use_start_date`와 `use_end_date`가 모두 있는 행은 **0**이며, 보존 literal QC 코드북 조회도 **0행**이다. 따라서 현재 메타데이터만으로 다음 사실을 확정할 수 없다.

- source_group·관측소·항목·실물 센서별 역사적 단위, 배율/offset, 기준면과 적용기간
- OBS_TIME/RECEIVE_TIME의 저장 시간대와 추출·변환 이력
- 장비 설치·교정·교체·철거와 원천 채널의 유효기간 양끝
- QC literal 코드·공백·NULL의 의미, 실제 채택 판본과 시행기간
- GR_OBS_ST의 정확 사전/어댑터, 152개 scope의 기간 충돌과 사건 연결

자료가 없는 항목에 현재 단위, 세션 시계, 파일명 또는 가이드북 발행일을 대입하지 않는다. `TECHNICALLY_CONFIRMED_CURRENT_METADATA_REFERENCE`와 `TECHNICALLY_CONFIRMED_CAPTURED_CONFIGURATION`은 범위가 제한된 확인 결과다. `SOURCE_CONTRACT` 승인이나 역사 관측 전체의 계약 확정을 뜻하지 않는다.

## 분석과 실제 운영의 순서

Rule·AI·Fusion의 개발 분석은 명시적인 입력·조건·참조 근거로 실행하고, 필요한 문맥이 없으면 `NOT_EVALUATED` 또는 근거 누락을 반환한다. 기술 검증된 입력과 사용자가 선언한 입력을 분리한다. 입력·정책·근거 hash를 남겨 이후 같은 조건을 재현할 수 있게 한다.

실제 승인 계정은 이후 설정한다. 그때 원천 계약·QC 최종값·학습 데이터셋·배포에 대한 각 판정을 실제 actor와 원장에 기록한다. workflow의 추천 승인으로 이 별도 승인들을 대신하지 않는다. 현재 단계와 운영 조건은 [구현 감사](10_IMPLEMENTATION_AUDIT.md), [진행 현황](24_P0_END_TO_END_PROGRESS.md)을 참조한다.
## 10/8 단계별 보완 결과

66,190 typedgrain 전수 packet와 현재 메타데이터/4SQL SHA를 재검증했다. naïve MDC 날짜는 UTCnull·원문보존·DATE_TIMEZONE_UNVERIFIED이며 명시 offset만 변환한다. HWP serial5claims에 원문/date/header/station locator를 보존했고 40사건/152기간 scope를 전수 기술 검토했다. serial문자열이나 재고날짜는 실물 연속 유효기간의 승인이 아니다. [29](29_DEVELOPMENT_STAGE_EXECUTION.md).
