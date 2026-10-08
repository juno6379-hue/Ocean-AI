# 파일 역할: 문서 추출·중복 방지·벡터 연결·검색 근거 회귀를 검증합니다.
"""Isolated ingestion/retrieval regressions; no operational DB/model calls."""
from datetime import datetime
from pathlib import Path
import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.domain import DocumentIndex
from app.rag import document_pipeline as pipeline, hybrid_retriever as retrieval
from app.rag import document_contract as contract_module
from app.rag.report_parser import Unit, semantic_blocks, report_date, xml_paragraphs, spreadsheet_units


def test_issue_blocks_keep_station_separate_and_real_page():
    units=[Unit('□ 관측소\n인천(3.1): 센서 장애\n센서 교체 예정\n부산(3.2): 통신 장애\n복구 완료',page=3)]
    chunks=semantic_blocks(units,'DAILY_INSPECTION_REPORT')
    assert all(c.page==3 for c in chunks)
    assert not any('인천' in c.text and '부산' in c.text for c in chunks)
    assert any('인천' in c.text and '교체 예정' in c.text for c in chunks)


def test_dates_do_not_default_to_ingestion_time():
    assert report_date(Path('점검(250304).hwp'),[])[0]==datetime(2025,3,4)
    assert report_date(Path('보고20250230.pdf'),[])[0] is None
    assert report_date(Path('manual.pdf'),[Unit('과거 장애 2020.01.01')])[0] is None


def test_nested_hwpx_paragraphs_are_not_duplicated():
    xml=b'<root><p><t>title</t><table><p><t>issue</t></p></table></p></root>'
    assert list(xml_paragraphs(xml))==['title','issue']


def test_pdf_control_characters_do_not_reach_vector_or_sql():
    chunks=semantic_blocks([Unit('관측소: DT_0001\n수온\x00 결측\x07 점검',page=1)],'DAILY_SITUATION_REPORT')
    assert all('\x00' not in c.text and '\x07' not in c.text for c in chunks)
    assert any('수온' in c.text and '결측' in c.text for c in chunks)


def test_excel_headers_and_merged_station_context():
    units=spreadsheet_units([('점검',[('관측소명','자료이상 상세내용'),('인천','센서 장애'),(None,'수온 결측')])])
    assert '관측소명: 인천' in units[-1].text
    assert units[-1].page is None and units[-1].locator=='점검!row:3'


class FakeVectors:
    def __init__(self):self.rows={}
    def upsert(self,ids,documents,embeddings,metadatas):
        for i,d,e,m in zip(ids,documents,embeddings,metadatas):self.rows[i]=(d,e,m)


@pytest.fixture
def isolated(monkeypatch):
    # Ordinary workspace directory avoids pytest's restrictive Windows temp ACL.
    tmp_path=Path(__file__).parent/'.work'/('document-'+uuid.uuid4().hex)
    tmp_path.mkdir(parents=True)
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine)
    monkeypatch.setattr(pipeline,'SessionLocal',sessions)
    monkeypatch.setattr(retrieval,'SessionLocal',sessions)
    monkeypatch.setattr(pipeline,'STATE_DIR',tmp_path)
    monkeypatch.setattr(pipeline,'LEDGER',tmp_path/'ledger.sqlite3')
    contract={'embedding_version':'test-v1','model':'local-test','collection':'test','dimension':2}
    monkeypatch.setattr(pipeline,'embed',lambda texts,c:[[1.,0.] for _ in texts])
    return tmp_path,sessions,contract


def test_idempotent_vector_sql_link_and_content_dedup(isolated):
    root,sessions,contract=isolated
    folder=root/'일일상황보고'; folder.mkdir()
    path=folder/'2025.03.04.txt';path.write_text('관측소: DT_0001\n수온 결측 센서 점검',encoding='utf-8')
    pipeline.inventory(root)
    ledger=pipeline.connect_ledger();row=ledger.execute('select * from files where path=?',(str(path),)).fetchone()
    vectors=FakeVectors()
    result=pipeline.process_file(row,contract,vectors,ledger,({},{}))
    pipeline.process_file(row,contract,vectors,ledger,({},{}))
    with sessions() as db:
        rows=db.query(DocumentIndex).all()
        assert len(rows)==len(vectors.rows)==result[1]
        assert all(r.chunk_id==r.embedding_id and r.chunk_id in vectors.rows for r in rows)
        assert all(r.document_date==datetime(2025,3,4) for r in rows)
    ledger.execute("update files set status='SUCCEEDED',embedding_version=?,chunks=? where path=?",('test-v1',result[1],str(path)));ledger.commit()
    duplicate=folder/'copy2025.03.04.txt';duplicate.write_bytes(path.read_bytes())
    pipeline.inventory(root)
    row=ledger.execute('select * from files where path=?',(str(duplicate),)).fetchone()
    assert pipeline.process_file(row,contract,vectors,ledger,({},{}))[0]=='DUPLICATE'
    ledger.close()


def test_vector_failure_does_not_publish_document_index(isolated,monkeypatch):
    root,sessions,contract=isolated
    folder=root/'일일상황보고';folder.mkdir();path=folder/'20250304.txt';path.write_text('관측소: DT_0001\n센서 장애',encoding='utf-8')
    pipeline.inventory(root);ledger=pipeline.connect_ledger()
    row=ledger.execute('select * from files where path=?',(str(path),)).fetchone()
    def fail(*args):raise RuntimeError('model offline')
    monkeypatch.setattr(pipeline,'embed',fail)
    with pytest.raises(RuntimeError):pipeline.process_file(row,contract,FakeVectors(),ledger,({},{}))
    with sessions() as db:assert db.query(DocumentIndex).count()==0
    ledger.close()


def test_filter_mapping_and_similarity_are_not_rerank_score(isolated,monkeypatch):
    root,sessions,contract=isolated
    with sessions() as db:
        db.add(DocumentIndex(document_id='doc',chunk_id='chunk',embedding_id='chunk',document_type='DAILY_SITUATION_REPORT',
            document_title='일일상황보고',document_date=datetime(2025,3,4),related_station_id='DT_0001',
            related_sensor_id='S1',section_name='점검',page_no=2,chunk_text='센서 장애',embedding_version='test-v1'))
        db.commit()
    class Search:
        def count(self):return 1
        def query(self,**kwargs):
            assert len(kwargs['where']['$and'])==3
            return {'ids':[['chunk']],'distances':[[.25]]}
    monkeypatch.setattr(contract_module,'load_contract',lambda:contract)
    monkeypatch.setattr(contract_module,'get_collection',lambda c:Search())
    monkeypatch.setattr(contract_module,'embed',lambda *a,**k:[[1.,0.]])
    monkeypatch.setattr(retrieval.settings,'VECTOR_SEARCH_ENABLED',True)
    result=retrieval.hybrid_search('센서',{'station_id':'DT_0001','sensor_id':'S1','date_start':datetime(2025,3,1)})
    evidence=result['results'][0]
    assert result['vector_status']=='AVAILABLE'
    assert evidence['similarity']==.75 and evidence['rerank_score']!=.75
    assert {'document_name','report_date','section','page','chunk','similarity'} <= set(evidence)
    assert retrieval.hybrid_search('센서',{'station_id':'DT_9999'})['results']==[]


def test_keyword_only_evidence_has_no_fabricated_cosine(isolated,monkeypatch):
    root,sessions,contract=isolated
    with sessions() as db:
        db.add(DocumentIndex(document_id='doc',chunk_id='keyword',embedding_id='keyword',
            document_type='DAILY_INSPECTION_REPORT',document_title='점검',
            chunk_text='센서 장애',embedding_version='test-v1'))
        db.commit()
    class Search:
        def count(self):return 1
        def query(self,**kwargs):return {'ids':[[]],'distances':[[]]}
    monkeypatch.setattr(contract_module,'load_contract',lambda:contract)
    monkeypatch.setattr(contract_module,'get_collection',lambda c:Search())
    monkeypatch.setattr(contract_module,'embed',lambda *a,**k:[[1.,0.]])
    monkeypatch.setattr(retrieval.settings,'VECTOR_SEARCH_ENABLED',True)
    result=retrieval.hybrid_search('센서')
    assert result['results'][0]['retrieval_method']=='KEYWORD'
    assert result['results'][0]['similarity'] is None
    assert result['results'][0]['keyword_score']>0
