# 파일 역할: 관측항목 코드 매핑 기준정보를 DB에 반영합니다.
import argparse, json
from app.core.database import SessionLocal, Base, engine
from app.models.domain import MDCItemMapping
def main(path):
    Base.metadata.create_all(bind=engine); rows=json.loads(open(path,encoding='utf-8').read()); db=SessionLocal(); n=0
    try:
        for x in {x['source_item_code']: x for x in rows}.values():
            row=db.query(MDCItemMapping).filter(MDCItemMapping.source_item_code==x['source_item_code']).first()
            if not row: row=MDCItemMapping(source_item_code=x['source_item_code']); db.add(row)
            row.standard_variable_code=x['standard_variable_code']; row.standard_unit=x['standard_unit']; row.sensor_type=x['sensor_type']; row.network_type=x['source_table']; row.mapping_version=x['mapping_version']; row.active=True; n+=1
        db.commit(); print({'processed':n,'unique_codes':len({x['source_item_code'] for x in rows})})
    finally: db.close()
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); a=ap.parse_args(); main(a.input)
