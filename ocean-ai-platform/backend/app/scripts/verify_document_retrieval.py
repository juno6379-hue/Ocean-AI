# 파일 역할: 실제 저장된 문서와 검색 API의 근거·벡터 연결을 읽기 전용으로 검증합니다.
"""운영 DB 조회와 로컬 임베딩 질의만 수행하며 문서/관측을 추가하지 않는다."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func
from app.api.routes_rag import router
from app.core.database import SessionLocal
from app.models.domain import DocumentIndex
from app.rag.document_contract import load_contract, get_collection
from app.rag.document_pipeline import status, connect_ledger, utc_now


def verify():
    contract=load_contract()
    collection=get_collection(contract)
    checks=[]
    with SessionLocal() as db:
        query=db.query(DocumentIndex).filter(DocumentIndex.embedding_version==contract['embedding_version'])
        grouped=query.with_entities(DocumentIndex.document_type,func.count()).group_by(DocumentIndex.document_type).all()
        counts=dict(grouped)
        linked=0;missing=[]
        ids=[r[0] for r in query.with_entities(DocumentIndex.chunk_id).all()]
        # 모든 색인을 벡터 ID로 대조하여 본문을 반복 다운로드하지 않는다.
        for start in range(0,len(ids),500):
            got=collection.get(ids=ids[start:start+500],include=[])['ids']
            linked+=len(got);missing.extend(sorted(set(ids[start:start+500])-set(got)))
        assert not missing, 'DocumentIndex points to missing vectors'
        app=FastAPI();app.include_router(router)
        # 동기화 스케줄러를 시작하지 않고 실제 라우터와 DB로 HTTP 응답을 검증한다.
        prompts=[('DAILY_SITUATION_REPORT','일일상황보고 조위 수온 염분 수신장애'),
                 ('DAILY_INSPECTION_REPORT','센서 고장 배터리 방전 통신 장애 점검 조치'),
                 ('QUALITY_GUIDEBOOK','해양관측자료 품질관리 결측 범위 검사 규칙'),
                 ('QUALITY_PROCESSING_REPORT','품질처리 오류기간 조위 처리결과'),
                 ('QUALITY_COLLECTION_REPORT','관측소 자료 수집률'),
                 ('WEEKLY_TIDE_RESIDUAL_REPORT','주간 조위 편차 경향'),
                 ('SPRING_TIDE_MONITORING_REPORT','대조기 고조 조위 모니터링')]
        with TestClient(app) as client:
            for kind,prompt in prompts:
                if not counts.get(kind):
                    checks.append({'report_type':kind,'status':'NOT_READY','reason':'No indexed chunks for the active version'});continue
                response=client.post('/api/rag/hybrid-search',json={'query':prompt,'report_type':kind,'top_k':3})
                assert response.status_code==200,response.text[:500]
                body=response.json();assert body['vector_status']=='AVAILABLE',body
                assert body['results'],'No evidence returned'
                sample=[]; vector_hits=0; keyword_only_hits=0
                for result in body['results']:
                    assert {'document_name','report_date','section','page','chunk','similarity'}<=result.keys()
                    # Hybrid ranking legitimately includes keyword-only evidence.
                    # Require actual vector evidence per query without inventing
                    # a cosine similarity for the keyword-only results.
                    if result['similarity'] is not None:
                        assert isinstance(result['similarity'],(int,float))
                        assert -1 <= result['similarity'] <= 1
                        vector_hits+=1
                    else:
                        assert result['keyword_score'] > 0
                        assert result['retrieval_method']=='KEYWORD'
                        keyword_only_hits+=1
                    stored=query.filter(DocumentIndex.chunk_id==result['chunk_id']).one()
                    assert stored.embedding_id==stored.chunk_id
                    assert stored.chunk_text==result['chunk'] and stored.document_type==kind
                    assert Path(stored.metadata_json['source_path']).is_file()
                    sample.append({k:result[k] for k in ['document_name','report_date','section','page','similarity','chunk_id','retrieval_method']})
                assert vector_hits>0, 'No actual vector evidence returned for this report type'
                checks.append({'report_type':kind,'prompt':prompt,'status':'PASS','vector_hits':vector_hits,'keyword_only_hits':keyword_only_hits,'sample_evidence':sample})
            # 존재하지 않는 관측소 조건이 벡터 검색에서도 무시되지 않는지 확인한다.
            empty=client.post('/api/rag/hybrid-search',json={'query':'조위 센서 결측','station_id':'NONEXISTENT_AUDIT_STATION'}).json()
            assert empty['results']==[]
            checks.append({'status':'PASS','test':'negative_station_filter'})
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'contract':contract,
            'document_index_chunks':len(ids),'matched_vector_ids':linked,'missing_vector_ids':missing,
            'vector_count_including_unpublished_inflight':collection.count(),'checks':checks,'ingestion':status(),
            'note':'실제 HTTP 경로·원문·ID·필터·유사도 검증이며, 전문가의 검색 관련성 평가는 별도 수행한다.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:
        result=verify()
    except Exception as exc:
        # 검증 실패도 처리 원장에 남겨 성공 결과만 보이는 것을 막는다.
        reason=f'{type(exc).__name__}: {exc}'[:2000]
        with connect_ledger() as ledger:
            ledger.execute('insert into errors(path,stage,reason,created_at) values(?,?,?,?)',
                           ('retrieval_verification','RETRIEVAL',reason,utc_now()))
        raise
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'indexed':result['document_index_chunks'],'matched':result['matched_vector_ids'],
                     'checks':[{k:v for k,v in r.items() if k!='sample_evidence'} for r in result['checks']]},ensure_ascii=False))
