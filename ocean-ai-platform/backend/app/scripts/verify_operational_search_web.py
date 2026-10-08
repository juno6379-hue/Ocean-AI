"""Check the running HTTP service, source citation identity and web data scope."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,time
import requests
from sqlalchemy import text
from app.core.database import engine


def main():
    out=Path('tests/.work/operations-20261006');out.mkdir(parents=True,exist_ok=True)
    base='http://127.0.0.1:5173/api'
    cases=[('DAILY_SITUATION_REPORT','일일상황보고 조위 수온 염분 수신장애'),
           ('DAILY_INSPECTION_REPORT','센서 고장 배터리 방전 통신 장애 점검 조치'),
           ('QUALITY_GUIDEBOOK','해양관측자료 품질관리 결측 범위 검사 규칙'),
           ('QUALITY_PROCESSING_REPORT','품질처리 오류기간 조위 처리결과'),
           ('QUALITY_COLLECTION_REPORT','관측소 자료 수집률'),
           ('WEEKLY_TIDE_RESIDUAL_REPORT','주간 조위 편차 경향'),
           ('SPRING_TIDE_MONITORING_REPORT','대조기 고조 조위 모니터링')]
    checks=[];hashes={}
    def save():
        (out/'live-search-web-verification.json').write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'checks':checks,'state':'RUNNING'},ensure_ascii=False,indent=2),encoding='utf8')
    with engine.connect() as db:
        for kind,query in cases:
            start=time.monotonic();r=requests.post(base+'/rag/hybrid-search',json={'query':query,'report_type':kind,'top_k':3},timeout=120);r.raise_for_status();b=r.json()
            assert b['vector_status']=='AVAILABLE' and b['results']
            hits=0;examples=[]
            for row in b['results']:
                stored=db.execute(text('select document_id,document_type,chunk_text from document_index where chunk_id=:id'),{'id':row['chunk_id']}).mappings().one()
                assert stored['document_id']==row['document_id'] and stored['document_type']==kind and stored['chunk_text']==row['chunk']
                meta=row['metadata'];p=Path(meta['source_path']);assert p.is_file()
                if str(p) not in hashes:
                    with p.open('rb') as f:hashes[str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
                assert hashes[str(p)]==meta['source_checksum']
                assert row['page'] is not None or meta.get('source_locator')
                if row['similarity'] is not None:hits+=1
                else:assert row['retrieval_method']=='KEYWORD' and row['keyword_score']>0
                examples.append({'document_id':row['document_id'],'document_name':row['document_name'],'chunk_id':row['chunk_id'],
                                 'page':row['page'],'locator':meta.get('source_locator'),'similarity':row['similarity'],
                                 'method':row['retrieval_method'],'source_sha256':hashes[str(p)]})
            assert hits>0
            checks.append({'name':kind,'passed':True,'vector_hits':hits,'keyword_only_hits':len(b['results'])-hits,'seconds':round(time.monotonic()-start,3),'citations':examples});save();print(kind,'PASS',flush=True)
    for filt in [{'station_id':'NONEXISTENT_AUDIT_STATION'},{'sensor_id':'NONEXISTENT_AUDIT_SENSOR'},{'date_start':'1900-01-01','date_end':'1900-01-02'}]:
        r=requests.post(base+'/rag/hybrid-search',json={'query':'조위 센서 결측',**filt},timeout=60);r.raise_for_status();assert r.json()['results']==[]
        checks.append({'name':'negative_filter','filter':filt,'passed':True});save()
    args={'source':'GD_OBS_ST_MONTHLY','from_month':'2023-01','to_month':'2026-07'}
    s=requests.get(base+'/lake/summary',params=args,timeout=60);s.raise_for_status();s=s.json()
    d=requests.get(base+'/lake/stations/DT_0001',params=args,timeout=60);d.raise_for_status();d=d.json()
    f=requests.get(base+'/data-lake/foundation/summary',timeout=60);f.raise_for_status();f=f.json()
    assert s['snapshot']==d['snapshot']==f['validation_snapshot']
    assert next(x for x in s['stations'] if x['station_code']=='DT_0001')['held_rows']==sum(x['held_rows'] for x in d['months'])
    assert s['simulated_included'] is False
    checks.append({'name':'dashboard_list_detail_scope','passed':True,'snapshot':s['snapshot'],'totals':s['totals']});save()
    for page in ['/','/observations','/profile/DT_0001']:
        r=requests.get('http://127.0.0.1:5173'+page,timeout=10);r.raise_for_status()
        assert 'root' in r.text
    checks.append({'name':'spa_http_routes','passed':True,'visual_render_validation':False})
    result={'at':datetime.now(timezone.utc).isoformat(),'state':'PASS','checks':checks,
            'limits':'Source checksum, stored extracted text, locators and API filters checked. Expert relevance/causal judgment and visual UI inspection not claimed.'}
    (out/'live-search-web-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('PASS',len(checks),flush=True)


if __name__=='__main__':main()
