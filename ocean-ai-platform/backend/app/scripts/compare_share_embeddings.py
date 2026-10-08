"""Hash-audit current D: documents against published SQL and stored vector IDs.

No source, vector or approval writes. One physical file is not one unique
document. Preserve aliases and distinguish an active published document from
partial vectors, old contracts, extraction failures and unprocessed files.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

from sqlalchemy import text
from app.core.database import engine
from app.rag.document_contract import load_contract, STATE_DIR, CHROMA_DIR
from app.rag.report_parser import classify

EXTENSIONS={'.pdf','.hwp','.hwpx','.xlsx','.xls','.docx','.txt'}


def read_db(p):
    c=sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True,timeout=30)
    c.row_factory=sqlite3.Row
    return c


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=Path(r'D:\share'));ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    root=args.source.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    contract=load_contract()
    with engine.connect() as db:
        published={r['document_id']:dict(r) for r in db.execute(text('''SELECT document_id,document_type,count(*) chunks
          FROM document_index WHERE embedding_version=:v GROUP BY document_id,document_type'''),{'v':contract['embedding_version']}).mappings()}
    by_hash=defaultdict(list)
    with read_db(STATE_DIR/'ingestion.sqlite3') as db:
        for row in db.execute('select path,checksum,document_id,document_type,status,embedding_version,chunks from files where checksum is not null'):
            by_hash[row['checksum']].append(dict(row))
    with read_db(CHROMA_DIR/'chroma.sqlite3') as db:
        vector_docs=dict(db.execute('''select m.string_value,count(*) from embeddings e join segments s on e.segment_id=s.id
          join collections c on c.id=s.collection join embedding_metadata m on m.id=e.id and m.key='document_id'
          where c.name=? group by m.string_value''',[contract['collection']]).fetchall())
    extracted={}
    latest=Path(r'D:\AI_Observation\outputs\share-validation\latest-run.txt')
    if latest.is_file():
        run=Path(latest.read_text(encoding='utf8').strip())
        for filename in ['evidence.sqlite3','expanded-evidence.sqlite3']:
            if (run/filename).exists():
                with read_db(run/filename) as db:
                    extracted.update({r['path']:dict(r) for r in db.execute('select path,sha256,status,error from documents')})
    listing=subprocess.run(['rg','--files','--hidden','--no-ignore',str(root)],capture_output=True,text=True,encoding='utf8',check=True)
    all_paths=[Path(p) for p in listing.stdout.splitlines()]
    paths=sorted(p for p in all_paths if p.suffix.lower() in EXTENSIONS)
    target=out/'share-embedding-comparison.sqlite3'
    c=sqlite3.connect(target);c.execute('pragma journal_mode=WAL')
    c.execute('create table if not exists files(path text primary key,size integer,mtime_ns integer,sha256 text,status text,details text)')
    counts=Counter();errors=0
    def state(done,current=None):
        result={'checked_at':datetime.now(timezone.utc).isoformat(),'state':'COMPLETE' if done==len(paths) else 'RUNNING',
                'root':str(root),'physical_files':len(all_paths),'document_candidates':len(paths),'completed':done,
                'counts':dict(counts),'current':current,'embedding_version':contract['embedding_version'],
                'policy':'SHA-256 matching; no embedding, vector deletion, source modification or approval performed'}
        temp=out/'share-embedding-comparison.tmp.json';temp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(out/'share-embedding-comparison-status.json')
    state(0)
    for i,p in enumerate(paths,1):
        digest=None;size=mtime=0;info={}
        try:
            before=p.stat();size=before.st_size;mtime=before.st_mtime_ns
            if p.name.startswith('~$'):
                status='OFFICE_LOCK_EXCLUDED'
            else:
                cached=c.execute('select sha256,size,mtime_ns from files where path=?',[str(p)]).fetchone()
                if cached and cached[0] and cached[1:]==(size,mtime):digest=cached[0]
                else:
                    with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
                after=p.stat()
                if (size,mtime)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('SOURCE_CHANGED_DURING_HASH')
                matches=by_hash.get(digest,[]);active={m['document_id'] for m in matches if m['document_id'] in published}
                partial={m['document_id'] for m in matches if m['document_id'] in vector_docs and m['document_id'] not in published}
                kind=classify(p.relative_to(root));ex=extracted.get(str(p))
                if ex and ex.get('sha256') and ex['sha256']!=digest:ex={'status':'SOURCE_CHANGED_AFTER_EXTRACTION'}
                if active:
                    same_type=any(published[d]['document_type']==kind for d in active)
                    status='ACTIVE_PUBLISHED_CONTENT_MATCH' if same_type else 'ACTIVE_CONTENT_MATCH_TYPE_REVIEW'
                elif partial:status='PARTIAL_VECTOR_NOT_PUBLISHED'
                elif matches and any(m.get('embedding_version') and m['embedding_version']!=contract['embedding_version'] for m in matches):status='OLDER_VERSION_REVIEW'
                elif ex and ex['status']=='NO_TEXT_OCR_NEEDED':status='OCR_REQUIRED_NOT_EMBEDDED'
                elif ex and ex['status'] in ('EXTRACTION_FAILED','FAILED'):status='EXTRACTION_FAILED_NOT_EMBEDDED'
                elif ex and ex['status']=='TEXT_EXTRACTED_UNREVIEWED':status='EXTRACTED_NOT_EMBEDDED'
                else:status='NOT_INDEXED_REVIEW_REQUIRED'
                info={'document_type_candidate':kind,'active_document_ids':sorted(active),
                      'partial_document_ids':sorted(partial),'partial_vectors':sum(vector_docs[d] for d in partial),
                      'existing_paths':[m['path'] for m in matches],'extraction':ex,
                      'publication':'Published content match does not approve metadata/QC or register this new location automatically.'}
        except Exception as exc:
            status='READ_OR_HASH_FAILED';info={'error':type(exc).__name__+': '+str(exc)};errors+=1
        c.execute('insert or replace into files values(?,?,?,?,?,?)',[str(p),size,mtime,digest,status,json.dumps(info,ensure_ascii=False)])
        counts[status]+=1
        if i%10==0:c.commit();state(i,str(p))
    c.commit();state(len(paths));c.close()
    print(json.dumps({'files':len(paths),'counts':dict(counts),'read_errors':errors},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
