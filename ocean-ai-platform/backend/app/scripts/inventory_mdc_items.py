# 파일 역할: MDC 관측항목 코드 목록을 조회합니다.
import argparse, json
from app.scripts.sync_mdc_db import fetch_oracle_data, init_oracle, map_mdc_item

TABLES=["WEB_OBS_ST","WEB_OBS_VBU"]
def main(output):
    init_oracle(); result=[]
    for table in TABLES:
        rows=fetch_oracle_data(f"SELECT OBS_ITEM_CODE, COUNT(*) AS ROW_COUNT, MIN(OBS_TIME) AS PERIOD_START, MAX(OBS_TIME) AS PERIOD_END FROM {table} GROUP BY OBS_ITEM_CODE ORDER BY OBS_ITEM_CODE")
        for row in rows:
            source=str(row.get('obs_item_code') or '').upper(); variable,unit,sensor=map_mdc_item(source)
            result.append({'source_item_code':source,'source_table':table,'row_count':row.get('row_count'),'period_start':str(row.get('period_start')),'period_end':str(row.get('period_end')),'standard_variable_code':variable,'standard_unit':unit,'sensor_type':sensor,'mapping_version':'MDC-ITEM-1.0'})
    with open(output,'w',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2,default=str)
    print(json.dumps({'items':len(result),'tables':TABLES},ensure_ascii=False))
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--output',default='mdc_item_inventory.json'); a=ap.parse_args(); main(a.output)
