# MDC 관측항목 inventory 결과

실제 Oracle Thick Client로 inventory를 실행했다. 확인된 항목은 `WEB_OBS_ST` 19개, `WEB_OBS_VBU` 58개다. 부이 자료에는 `SALINITY2`, `SEA_LEVEL`, `CURRENT_H_SPEED`, `WATER_TEMP`, 파고·파주기·풍속·풍향 등 기존 단순 TIDE/WAVE 매핑에 없던 항목이 포함된다.

`mdc_item_inventory.json`은 항목별 건수·기간·표준코드·단위·센서 유형을 포함하며 `load_mdc_item_mapping.py`로 PostgreSQL `MDCItemMapping`에 적재한다. 매핑되지 않은 항목은 원본 코드 그대로 보존하고 표준화 단계에서 별도 규칙을 추가한다.
