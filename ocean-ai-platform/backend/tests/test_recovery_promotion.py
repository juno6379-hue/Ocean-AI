import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.rag import recovery_promotion as m, document_pipeline as p, document_contract as contract_module
from app.rag.ingestion_recovery import RecoveryStore, canonical, sha_file
from app.core import database
from app.core.config import settings
from app.models.domain import DocumentIndex


class Vectors:
    def __init__(self):self.values={};self.after_upsert=None
    def upsert(self, ids,documents,embeddings,metadatas):
        for i,t,v,meta in zip(ids,documents,embeddings,metadatas):self.values[i]=(t,v,meta)
        if self.after_upsert:self.after_upsert()
    def delete(self,ids):
        for i in ids:self.values.pop(i,None)


@pytest.fixture
def environment(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    database.Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    monkeypatch.setattr(database,'SessionLocal',Session)
    monkeypatch.setattr(p,'SessionLocal',Session)
    monkeypatch.setattr(p,'STATE_DIR',tmp_path/'state')
    monkeypatch.setattr(p,'LEDGER',tmp_path/'state'/'ingestion.sqlite3')
    monkeypatch.setattr(p,'reference_maps',lambda: ({},{}))
    root=tmp_path/'original';root.mkdir()
    source=root/'일일점검_20260101.txt';source.write_text('센서 점검\n\n통신 상태 정상',encoding='utf8')
    p.inventory(root)
    contract={'provider':'ollama','model':'local','model_digest':'known','dimension':2,'metric':'cosine',
              'embedding_version':'test','collection':'active-test','parser_version':contract_module.PARSER_VERSION,
              'chunk_version':contract_module.CHUNK_VERSION,'query_prefix':''}
    cp=tmp_path/'contract.json';cp.write_bytes(canonical(contract))
    monkeypatch.setattr(contract_module,'CONTRACT_PATH',cp)
    vectors=Vectors();monkeypatch.setattr(contract_module,'get_collection',lambda *a,**k:vectors)
    monkeypatch.setattr(m,'local_embedder',lambda _:None)
    monkeypatch.setattr(settings,'API_IDENTITIES',{'operator-one':{'role':'operator','token':'development-test-only'}})
    store=RecoveryStore(tmp_path/'recovery.sqlite3',contract)
    store.ingest({'path':str(source),'original_path':str(source),'sha256':sha_file(source)},'DAILY_INSPECTION_REPORT',lambda texts:[[1.,0.] for _ in texts]);store.close()
    plan=m.build_promotion_plan(tmp_path/'recovery.sqlite3',p.LEDGER,cp)
    request=Request({'type':'http','headers':[(b'authorization',b'Bearer development-test-only')]})
    return plan,request,source,vectors,Session


def test_dry_run_canonical_resume_replay_and_additive_rollback(environment):
    plan,request,source,vectors,Session=environment
    assert m.validate_plan(plan)['production_writes'] is False
    with Session() as db:assert db.query(DocumentIndex).count()==0
    receipt=m.apply_plan(plan,request)
    with Session() as db:assert db.query(DocumentIndex).count()==2
    assert len(vectors.values)==2
    assert m.apply_plan(plan,request)['replayed'] is True
    result=m.rollback_plan(plan,receipt,request)
    assert result['preexisting_deleted'] is False
    with Session() as db:assert db.query(DocumentIndex).count()==0
    assert vectors.values=={}
    assert m.rollback_plan(plan,receipt,request)['replayed'] is True
    assert m.validate_plan(plan)['status']=='PASS'


def test_source_change_during_upsert_is_blocked_before_sql_publication(environment):
    plan,request,source,vectors,Session=environment
    original=source.read_bytes()
    vectors.after_upsert=lambda:source.write_text('tampered source',encoding='utf8')
    with pytest.raises(ValueError,match='SOURCE_OR_CONTRACT_CHANGED'):
        m.apply_plan(plan,request)
    with Session() as db:assert db.query(DocumentIndex).count()==0
    # Deterministic orphan vectors remain unpublished, while original file
    # ledger state is untouched. The same plan resumes after restoring bytes.
    from app.rag.ingestion_recovery import readonly_ledger
    with readonly_ledger(plan['ledger_path']) as c:assert c.execute('SELECT status,checksum FROM files WHERE eligible=1').fetchone()['status']=='PENDING'
    source.write_bytes(original);vectors.after_upsert=None
    assert m.apply_plan(plan,request)['production_writes'] is True


def test_stale_contract_and_ledger_revision_are_rejected(environment):
    plan,request,source,vectors,Session=environment
    import sqlite3
    with sqlite3.connect(plan['ledger_path']) as c:c.execute("UPDATE files SET reason='external change' WHERE eligible=1")
    with pytest.raises(ValueError,match='LEDGER_REVISION_CHANGED'):m.apply_plan(plan,request)
    assert vectors.values=={}
    with Session() as db:assert db.query(DocumentIndex).count()==0


def test_account_is_required_and_body_plan_cannot_grant_it(environment,monkeypatch):
    plan,request,source,vectors,Session=environment
    monkeypatch.setattr(settings,'API_IDENTITIES',{})
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:m.apply_plan(plan,request)
    assert error.value.status_code==503
    assert vectors.values=={}


def test_rollback_stale_publication_is_rejected_before_deletion(environment):
    plan,request,source,vectors,Session=environment
    receipt=m.apply_plan(plan,request)
    with Session() as db:
        row=db.query(DocumentIndex).first();row.metadata_json={'source_checksum':'changed'};db.commit()
    with pytest.raises(ValueError,match='PUBLICATION_CHANGED'):m.rollback_plan(plan,receipt,request)
    with Session() as db:assert db.query(DocumentIndex).count()==2


def test_crash_after_sql_before_file_ledger_can_resume_and_rollback_own_added_ids(environment,monkeypatch):
    plan,request,source,vectors,Session=environment
    original=p.process_file
    def crash(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('crash after SQL commit')
    monkeypatch.setattr(p,'process_file',crash)
    with pytest.raises(RuntimeError,match='after SQL'):m.apply_plan(plan,request)
    with Session() as db:assert db.query(DocumentIndex).count()==2
    monkeypatch.setattr(p,'process_file',original)
    receipt=m.apply_plan(plan,request)
    assert len(receipt['documents'][0]['added_chunk_ids'])==2
    m.rollback_plan(plan,receipt,request)
    with Session() as db:assert db.query(DocumentIndex).count()==0


def test_rollback_preserves_preexisting_exact_document_chunks(environment,monkeypatch):
    plan,request,source,vectors,Session=environment
    import sqlite3
    monkeypatch.setattr(p,'cached_embeddings',lambda texts,*args:[[1.,0.] for _ in texts])
    c=sqlite3.connect(plan['ledger_path']);c.row_factory=sqlite3.Row
    row=c.execute('SELECT * FROM files WHERE eligible=1').fetchone()
    contract=json.loads(Path(plan['contract_path']).read_bytes())
    p.process_file(row,contract,vectors,c,({},{}));c.commit();c.close()
    newer=m.build_promotion_plan(plan['recovery_path'],plan['ledger_path'],plan['contract_path'])
    receipt=m.apply_plan(newer,request)
    assert receipt['documents'][0]['added_chunk_ids']==[]
    m.rollback_plan(newer,receipt,request)
    with Session() as db:assert db.query(DocumentIndex).count()==2
    assert len(vectors.values)==2


def test_rollback_does_not_overwrite_another_ledger_change(environment):
    plan,request,source,vectors,Session=environment
    receipt=m.apply_plan(plan,request)
    import sqlite3
    with sqlite3.connect(plan['ledger_path']) as c:c.execute("UPDATE files SET reason='another operator note' WHERE eligible=1")
    with pytest.raises(ValueError,match='LEDGER_CHANGED'):m.rollback_plan(plan,receipt,request)
    with Session() as db:assert db.query(DocumentIndex).count()==2
    assert len(vectors.values)==2


def test_corrected_text_with_same_source_checksum_blocks_replay_and_rollback(environment):
    plan,request,source,vectors,Session=environment
    receipt=m.apply_plan(plan,request)
    with Session() as db:
        row=db.query(DocumentIndex).first();row.chunk_text='corrected by later reviewer';db.commit()
    with pytest.raises(ValueError,match='REPLAY_PUBLICATION_CHANGED'):m.apply_plan(plan,request)
    with pytest.raises(ValueError,match='ROLLBACK_PUBLICATION_CHANGED'):m.rollback_plan(plan,receipt,request)
    with Session() as db:
        assert db.query(DocumentIndex).count()==2
        assert db.query(DocumentIndex).filter(DocumentIndex.chunk_text=='corrected by later reviewer').count()==1


def test_corrected_text_after_sql_crash_is_not_overwritten_on_resume(environment,monkeypatch):
    plan,request,source,vectors,Session=environment
    original=p.process_file
    def crash(*args,**kwargs):
        original(*args,**kwargs);raise RuntimeError('post SQL crash')
    monkeypatch.setattr(p,'process_file',crash)
    with pytest.raises(RuntimeError):m.apply_plan(plan,request)
    monkeypatch.setattr(p,'process_file',original)
    with Session() as db:
        db.query(DocumentIndex).first().chunk_text='later corrected';db.commit()
    with pytest.raises(ValueError,match='CRASH_RECOVERY_PUBLICATION_CHANGED'):m.apply_plan(plan,request)
    with Session() as db:assert db.query(DocumentIndex).filter(DocumentIndex.chunk_text=='later corrected').count()==1
