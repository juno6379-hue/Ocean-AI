# 파일 역할: MDC 운영 DB의 접근 가능한 테이블과 컬럼을 조사합니다.
import argparse, json
from app.scripts.sync_mdc_db import fetch_oracle_data, init_oracle

TABLES=["WEB_STATION","WEB_OBS_ST","WEB_OBS_VBU","GD_OBS_ST","GD_OBS_VBU"]
def inspect():
    init_oracle()
    result={}
    for table in TABLES:
        rows=fetch_oracle_data("SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE FROM ALL_TAB_COLUMNS WHERE OWNER=USER AND TABLE_NAME=:table_name ORDER BY COLUMN_ID",{"table_name":table})
        result[table]=rows
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--output',default='mdc_schema_inventory.json'); a=ap.parse_args(); data=inspect(); open(a.output,'w',encoding='utf-8').write(json.dumps(data,ensure_ascii=False,indent=2,default=str)); print({k:len(v) for k,v in data.items()})
