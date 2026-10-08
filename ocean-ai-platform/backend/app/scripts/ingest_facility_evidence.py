"""Publish only explicitly selected, hash-verified facility evidence PDFs.

The normal report inventory excludes OTHER. This bounded adapter assigns a
project-report type explicitly; it does not reinterpret dates as validity or
approve extracted station/sensor candidates. The shared OS lock prevents a
second ingestion worker. Existing vectors and unrelated ledger rows survive.
"""
import argparse, json, hashlib
from pathlib import Path
from sqlalchemy import text
from app.core.database import engine
from app.rag.document_contract import load_contract, verify_model, get_collection, PARSER_VERSION, CHUNK_VERSION
from app.rag.document_pipeline import worker_lock, connect_ledger, reference_maps, process_file, utc_now


def run(manifest):
    entries=json.loads(Path(manifest).read_text(encoding='utf8'))
    with worker_lock():
        contract=load_contract()
        if (contract['parser_version'],contract['chunk_version'])!=(PARSER_VERSION,CHUNK_VERSION):
            raise RuntimeError('Existing parser/chunk contract mismatch')
        verify_model(contract)
        collection=get_collection(contract,create=False)
        ledger=connect_ledger(); references=reference_maps()
        try:
            for entry in entries:
                path=Path(entry['path']).resolve()
                with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
                if sha!=entry['sha256']:raise RuntimeError('Source hash changed: '+str(path))
                kind='PROJECT_RESULT_REPORT'
                did=hashlib.sha256((kind+'\0'+sha).encode()).hexdigest()
                old=ledger.execute('select * from files where path=?',(str(path),)).fetchone()
                if old and old['status']=='SUCCEEDED' and old['document_id']==did and old['embedding_version']==contract['embedding_version']:
                    print(json.dumps({'path':str(path),'state':'ALREADY_PUBLISHED'},ensure_ascii=False),flush=True); continue
                # A prior incomplete upload can resume only under its recorded identity.
                stored=collection.get(where={'document_id':did},limit=1,include=[])
                if stored['ids'] and (not old or old['document_id']!=did):
                    raise RuntimeError('Unowned existing vectors; reconcile before ingestion')
                s=path.stat()
                ledger.execute('''INSERT INTO files(path,root,size,mtime_ns,document_type,eligible,status,reason,checksum,document_id,
                parser_version,chunk_version,embedding_version,model,collection_name,updated_at) VALUES(?,?,?,?,?,1,'RUNNING',?,?,?,?,?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET document_type=excluded.document_type,eligible=1,status='RUNNING',
                reason=excluded.reason,checksum=excluded.checksum,document_id=excluded.document_id,parser_version=excluded.parser_version,
                chunk_version=excluded.chunk_version,embedding_version=excluded.embedding_version,model=excluded.model,
                collection_name=excluded.collection_name,updated_at=excluded.updated_at''',
                (str(path),str(path.parent),s.st_size,s.st_mtime_ns,kind,'EXPLICIT_FACILITY_EVIDENCE_SCOPE',sha,did,
                 PARSER_VERSION,CHUNK_VERSION,contract['embedding_version'],contract['model'],contract['collection'],utc_now()))
                ledger.commit()
                try:
                    state,chunks,duplicate=process_file({'path':str(path),'document_type':kind},contract,collection,ledger,references)
                    with engine.connect() as db:
                        sql_ids=set(db.execute(text('select chunk_id from document_index where document_id=:d and embedding_version=:v'),{'d':did,'v':contract['embedding_version']}).scalars())
                    vector_ids=set(collection.get(where={'document_id':did},include=[])['ids'])
                    if not sql_ids or sql_ids!=vector_ids or len(sql_ids)!=chunks:raise RuntimeError('SQL/vector publication mismatch')
                    ledger.execute('update files set status=?,chunks=?,duplicate_of=?,reason=?,updated_at=? where path=?',
                                   (state,chunks,duplicate,'PUBLISHED_NOT_METADATA_OR_QC_APPROVAL',utc_now(),str(path)))
                    ledger.commit()
                    print(json.dumps({'path':str(path),'state':state,'chunks':chunks,'sql_vector_ids_equal':True},ensure_ascii=False),flush=True)
                except Exception as exc:
                    ledger.execute("update files set status='FAILED',reason=?,updated_at=? where path=?",(str(exc)[:1500],utc_now(),str(path)))
                    ledger.commit();raise
        finally:ledger.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    run(p.parse_args().manifest)
