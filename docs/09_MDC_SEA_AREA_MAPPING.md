# MDC 관측소 해역 및 지도 위치 매핑

현행화: 2026-10-08

현황 기본 조회는2026년7월이다. 단일7월에는 명칭·코드·유형·공개좌표가 유일하게 대응하고 보고서에 직접 해역 근거가 있는52개만 해당 월 참조로 표시한다. 해역 미명시18개는 기존 값을 유지하며 PostgreSQL 해역과 과거 조회는 수정하지 않는다. 기존 분류와22개 차이에는 제주/남해 분류체계 차이도 포함된다. [7월 문서 대조](27_JULY_REPORT_PARQUET_MATCH.md)를 참조한다.

## 적용 범위

해역은 지도와 조회 필터에 쓰는 표시용 분류다. 원천 관측값의 의미, 센서 동일성, 단위 또는 운영 승인을 확정하는 필드가 아니다. `WEB_STATION.DO_NM`은 소속 도·시 행정구역이므로 `sea_area`로 복사하지 않는다.

[MDC 동기화 코드](../ocean-ai-platform/backend/app/scripts/sync_mdc_db.py)의 `sync_metadata()`는 `OBS_LAT`, `OBS_LON`을 저장하고 `map_sea_area()`로 해역을 계산한다. 지원 관측망은 `map_network_type()`에서 먼저 제한한다. 관측망 코드와 예외는 [시설 코드 매핑](08_MDC_STATION_CODE_MAPPING.md)을 참고한다.

## 좌표 기반 분류

다음 조건은 위에서부터 적용한다.

| 조건 | 표시 해역 |
|---|---|
| 숫자 변환 실패 또는 위도·경도의 지리적 범위 오류 | 미상 |
| 위도 ≤ 34.0이고 경도 ≥ 125.0 | 제주해역 |
| 경도 ≥ 128.0 | 동해 |
| 경도 ≤ 126.5 | 서해 |
| 나머지 유효 좌표 | 남해 |

이 구현은 간단한 위경도 경계 규칙이다. 공식 해역 경계의 공간 다각형 판정이나 시점별 시설 위치 이력을 구현한 것으로 보지 않는다. 위치가 변경된 시설의 과거 관측에 현재 좌표를 적용하려면 별도 근거와 기간 검토가 필요하다.

## 실제 자료 화면에서의 사용

- [Dashboard](../ocean-ai-platform/frontend/src/pages/Dashboard.tsx)와 [Observations](../ocean-ai-platform/frontend/src/pages/Observations.tsx)는 선택한 원천·기간의 레이크 보유 자료와 기존 관측소 메타데이터를 구분한다.
- 지도 좌표는 관측소 코드가 정확히 대응하는 메타데이터가 한 개이고, 좌표가 유한하며 범위 안에 있을 때 참조한다. 좌표 미확정 자료를 지도 중심점으로 대체하지 않는다.
- [StationClassifications](../ocean-ai-platform/frontend/src/components/StationClassifications.tsx)와 [LakeExplorer](../ocean-ai-platform/frontend/src/components/LakeExplorer.tsx)는 자료 출처·관측망·해역 조회 문맥을 유지한다. 보유 원천과 메타데이터의 대응이 물리 센서·설치기간 승인까지 의미하지는 않는다.
- [원천 계약](11_OBSERVATION_STANDARD_LAYER.md)의 원천 관측소 literal, 공통 식별자, 물리 센서 및 유효기간은 해역 분류와 별도로 검증한다.

## 과거 실행 기록과 현재 확인

2026-09-16의 재동기화 기록에는 관측소 323건과 남해 77·동해 108·서해 112·제주해역 20·미상 6건이 기재되어 있었다. 이는 당시 자료와 실행의 집계이며 현재 시설 수나 승인된 원천 대응 수로 재사용하지 않는다.

2026-10-08 현행화는 위 코드와 화면의 참조 경로를 확인했다. 해역 집계를 얻기 위해 MDC를 다시 동기화하지 않았다. 실제 운영 설정과 승인 단계는 [구현 실태 점검](10_IMPLEMENTATION_AUDIT.md) 및 [게시 구현 기준](../ocean-ai-platform/docs/82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md)을 따른다.
