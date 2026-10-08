"""Exact, read-only promotion plan for isolated recovery into existing RAG.

The plan itself is never approval. Application writes use the existing ingestion
worker lock, exact current contract and a server-authenticated operator. An
apply command is intentionally distinct from dry-run and is not run by review.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

from app.rag.ingestion_recovery import (backlog_snapshot, canonical, guarded,
    local_embedder, now, readonly_ledger, sha_file)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path, body):
    path=guarded(path);temporary=guarded(path.with_suffix(path.suffix+'.tmp'),path.parent)
    temporary.write_bytes(canonical(body));temporary.replace(path)


def document_postimage(row):
    from datetime import date,datetime,timezone
    body={}
    for column in row.__table__.columns:
        value=getattr(row,column.name)
        if isinstance(value,datetime):
            value=value.astimezone(timezone.utc).isoformat() if value.tzinfo else value.isoformat()
        elif isinstance(value,date):value=value.isoformat()
        elif isinstance(value,bytes):value=value.hex()
        body[column.name]=value
    return digest(body)


def build_promotion_plan(recovery_path, ledger_path, contract_path):
    recovery = guarded(recovery_path)
    contract_path = guarded(contract_path)
    contract = json.loads(contract_path.read_bytes())
    current = backlog_snapshot(ledger_path)
    rows = {r["path"]: r for r in current["backlog"]}
    documents = []
    with readonly_ledger(recovery) as c:
        frozen = c.execute("SELECT value FROM meta WHERE key='contract'").fetchone()
        if not frozen or digest(json.loads(frozen[0])) != digest(contract):
            raise ValueError("PROMOTION_CONTRACT_MISMATCH")
        for row in c.execute("SELECT * FROM documents WHERE status='SUCCEEDED' ORDER BY sha256"):
            chunks = [dict(r) for r in c.execute("SELECT * FROM chunks WHERE document_sha=? ORDER BY ordinal", (row["sha256"],))]
            if len(chunks) != row["total_chunks"] or [r["ordinal"] for r in chunks] != list(range(len(chunks))):
                raise ValueError("PROMOTION_COMPLETE_MEMBERSHIP_REQUIRED")
            original = json.loads(chunks[0]["citation"])["original_path"]
            candidate = rows.get(original)
            if not candidate or candidate["document_type"] != row["kind"]:
                raise ValueError("PROMOTION_TARGET_NOT_CURRENT_BACKLOG")
            if sha_file(guarded(original)) != row["sha256"] or sha_file(guarded(row["path"])) != row["sha256"]:
                raise ValueError("PROMOTION_SOURCE_CHANGED")
            doc_id = hashlib.sha256((row["kind"] + "\0" + row["sha256"]).encode()).hexdigest()
            canonical_ids = [hashlib.sha256((doc_id + contract["embedding_version"] + str(r["ordinal"]) + r["text"]).encode()).hexdigest() for r in chunks]
            documents.append({"source_sha256": row["sha256"], "original_path": original,
                "preserved_path": row["path"], "document_type": row["kind"], "canonical_document_id": doc_id,
                "canonical_chunk_ids": canonical_ids, "chunks": len(chunks), "original_status": candidate["status"],
                "isolated_content_sha256": digest(chunks)})
    body = {"schema_version": "document-recovery-promotion-v1", "created_at": now(),
        "recovery_path": str(recovery), "ledger_path": str(guarded(ledger_path)),
        "contract_path": str(contract_path), "contract_sha256": sha_file(contract_path),
        "recovery_sha256": sha_file(recovery), "backlog_snapshot_sha256": current["snapshot_sha256"],
        "canonical_ledger_snapshot": {"counts": current["counts"], "backlog": current["backlog"]},
        "documents": documents, "collection": contract["collection"], "embedding_version": contract["embedding_version"],
        "approved": False, "production_writes": False,
        "rollback_policy": "REMOVE_ONLY_NEW_CHUNK_IDS_AFTER_EXACT_POST_WRITE_HASH_CHECK; NEVER_DELETE_PREEXISTING_OR_UNRELATED_CHUNKS",
        "post_apply_required": ["SQL and Chroma exact active ID equality", "Source citation/hash/filter retrieval verification",
                                "Retain original per-file ledger preimage and list only additive IDs in publication receipt"]}
    return {**body, "plan_sha256": digest(body)}


def validate_plan(plan, *, completed=None):
    if not isinstance(plan, dict) or plan.get("schema_version") != "document-recovery-promotion-v1" or plan.get("plan_sha256") != digest({k:v for k,v in plan.items() if k != "plan_sha256"}):
        raise ValueError("PROMOTION_PLAN_HASH_MISMATCH")
    if sha_file(guarded(plan["recovery_path"])) != plan["recovery_sha256"]:
        raise ValueError("PROMOTION_ISOLATED_INDEX_CHANGED")
    if sha_file(guarded(plan["contract_path"])) != plan["contract_sha256"]:
        raise ValueError("PROMOTION_ACTIVE_CONTRACT_CHANGED")
    current = backlog_snapshot(plan["ledger_path"])
    expected = plan.get("canonical_ledger_snapshot")
    if completed:
        expected = json.loads(canonical(expected))
        for doc in completed:
            path = doc["original_path"]
            row = next((r for r in expected["backlog"] if r["path"] == path), None)
            if row:
                expected["backlog"].remove(row)
                expected["counts"][row["status"]] -= 1
                if expected["counts"][row["status"]] == 0:
                    del expected["counts"][row["status"]]
                expected["counts"][doc["status"]] = expected["counts"].get(doc["status"], 0) + 1
    if current["snapshot_sha256"] != digest(expected):
        raise ValueError("PROMOTION_CANONICAL_LEDGER_REVISION_CHANGED")
    for doc in plan["documents"]:
        if sha_file(guarded(doc["original_path"])) != doc["source_sha256"] or sha_file(guarded(doc["preserved_path"])) != doc["source_sha256"]:
            raise ValueError("PROMOTION_SOURCE_CHANGED")
    return {"status": "PASS", "failed": 0, "passed": len(plan["documents"]), "checked_at": now(),
            "plan_sha256": plan["plan_sha256"], "documents": len(plan["documents"]), "production_writes": False}


def apply_plan(plan, request):
    """Normal application worker path; no fake authority/auto-creation/migration.

    A deterministic per-document operation receipt is saved beside the plan's
    isolated DB. A replay verifies source+contract and published metadata before
    returning; fresh plans cannot replace an active plan's ledger revision.
    """
    from app.core.security import current_actor
    actor = current_actor(request)
    if actor.role not in {"operator", "reviewer", "admin"}:
        raise ValueError("PROMOTION_OPERATOR_REQUIRED")
    # These are imported only for the explicitly requested write path.
    from app.rag import document_pipeline as p
    from app.rag.document_contract import get_collection, CONTRACT_PATH
    from app.models.domain import DocumentIndex
    from app.core.database import SessionLocal
    if guarded(p.LEDGER) != guarded(plan["ledger_path"]) or guarded(CONTRACT_PATH) != guarded(plan["contract_path"]):
        raise ValueError("PROMOTION_CONFIG_TARGET_MISMATCH")
    receipt_path = guarded(Path(plan["recovery_path"]).parent / ("promotion-" + plan["plan_sha256"] + ".json"))
    with p.worker_lock():
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_bytes())
            if receipt.get("plan_sha256") != plan["plan_sha256"] or receipt.get("operator") != actor.user_id:
                raise ValueError("PROMOTION_RECEIPT_ACTOR_OR_PLAN_MISMATCH")
            if receipt.get('receipt_sha256')!=digest({k:v for k,v in receipt.items() if k!='receipt_sha256'}):
                raise ValueError('PROMOTION_RECEIPT_HASH_MISMATCH')
            with readonly_ledger(plan['ledger_path']) as history:
                recorded=history.execute('SELECT * FROM runs WHERE run_id=?',('promotion-'+plan['plan_sha256'],)).fetchone()
                if not recorded or recorded['status']!='COMPLETED_RECOVERY_BATCH' or json.loads(recorded['summary']).get('receipt_sha256')!=receipt['receipt_sha256']:
                    raise ValueError('PROMOTION_REPLAY_HISTORY_MISMATCH')
            validate_plan(plan, completed=receipt["documents"])
            # Replay requires the actual publication to remain intact.
            with SessionLocal() as db:
                for doc in receipt["documents"]:
                    for chunk in doc["added_chunk_ids"]:
                        actual = db.query(DocumentIndex).filter(DocumentIndex.chunk_id == chunk).one_or_none()
                        if actual is None or document_postimage(actual)!=doc.get('document_postimages',{}).get(chunk):
                            raise ValueError("PROMOTION_REPLAY_PUBLICATION_CHANGED")
            return {**receipt, "replayed": True}
        # Incomplete publication journals are durable restart checkpoints.
        checkpoint_path = receipt_path.with_suffix(".checkpoint.json")
        checkpoint = json.loads(checkpoint_path.read_bytes()) if checkpoint_path.exists() else {"plan_sha256": plan["plan_sha256"], "operator": actor.user_id, "documents": [], "intents": {}}
        if checkpoint.get("plan_sha256") != plan["plan_sha256"] or checkpoint.get("operator") != actor.user_id:
            raise ValueError("PROMOTION_CHECKPOINT_ACTOR_OR_PLAN_MISMATCH")
        with readonly_ledger(plan["ledger_path"]) as current:
            for doc in plan["documents"]:
                intent = checkpoint.get("intents", {}).get(doc["original_path"])
                row = current.execute("SELECT * FROM files WHERE path=?", (doc["original_path"],)).fetchone()
                if intent and row and row["status"] in {'SUCCEEDED','DUPLICATE'} and row['checksum']==doc['source_sha256'] and not any(d['original_path']==doc['original_path'] for d in checkpoint['documents']):
                    with SessionLocal() as db:
                        records=db.query(DocumentIndex).filter(DocumentIndex.document_id==doc['canonical_document_id']).all()
                        ids = {r.chunk_id for r in records}
                        if ids != set(doc['canonical_chunk_ids']):
                            raise ValueError('PROMOTION_CRASH_RECOVERY_PUBLICATION_CHANGED')
                        postimages={r.chunk_id:document_postimage(r) for r in records}
                        if intent.get('document_postimages')!=postimages:raise ValueError('PROMOTION_CRASH_RECOVERY_PUBLICATION_CHANGED')
                    checkpoint['documents'].append({**intent, 'status':row['status'],'ledger_postimage':dict(row)})
        validate_plan(plan, completed=checkpoint["documents"])
        contract = json.loads(Path(plan["contract_path"]).read_bytes())
        local_embedder(contract)  # Verify the active local model digest.
        collection = get_collection(contract, create=False)
        references = p.reference_maps()
        results = list(checkpoint["documents"])
        with readonly_ledger(plan["ledger_path"]) as current:
            source_rows = {r["path"]: dict(r) for r in current.execute("SELECT * FROM files")}
        # Per-file commit is the existing pipeline's restart granularity. A
        # failure leaves deterministic vector IDs unpublished until a full
        # SQL transaction succeeds; subsequent upsert uses the same IDs.
        ledger = sqlite3.connect(plan["ledger_path"])
        ledger.row_factory = sqlite3.Row
        try:
            for doc in plan["documents"]:
                if any(r["original_path"] == doc["original_path"] for r in results):
                    continue
                if sha_file(guarded(doc["original_path"])) != doc["source_sha256"]:
                    raise ValueError("PROMOTION_SOURCE_CHANGED")
                with SessionLocal() as db:
                    old_records=db.query(DocumentIndex).filter(DocumentIndex.document_id == doc["canonical_document_id"]).all()
                    preexisting = {r.chunk_id for r in old_records}
                    current_postimages={r.chunk_id:document_postimage(r) for r in old_records}
                old_intent=checkpoint.get('intents',{}).get(doc['original_path'])
                if old_intent and preexisting and old_intent.get('document_postimages')!=current_postimages:
                    raise ValueError('PROMOTION_CRASH_RECOVERY_PUBLICATION_CHANGED')
                row = source_rows[doc["original_path"]]
                intent = checkpoint.setdefault('intents',{}).setdefault(row['path'], {
                    'original_path':row['path'],'source_sha256':doc['source_sha256'],
                    'added_chunk_ids':[v for v in doc['canonical_chunk_ids'] if v not in preexisting],
                    'preexisting_chunk_ids':sorted(preexisting),'preexisting_postimages':current_postimages,'ledger_preimage':row})
                atomic_json(checkpoint_path,checkpoint)
                with readonly_ledger(plan['recovery_path']) as recovered:
                    frozen_vectors={r['text']:json.loads(r['vector']) for r in recovered.execute('SELECT text,vector FROM chunks WHERE document_sha=?',(doc['source_sha256'],))}
                original_factory, original_embeddings = p.SessionLocal,p.cached_embeddings
                def guarded_factory():
                    db=original_factory(); commit=db.commit
                    def checked_commit():
                        if sha_file(guarded(doc['original_path']))!=doc['source_sha256'] or sha_file(guarded(plan['contract_path']))!=plan['contract_sha256']:
                            raise ValueError('PROMOTION_SOURCE_OR_CONTRACT_CHANGED_BEFORE_SQL_PUBLICATION')
                        records=db.query(DocumentIndex).filter(DocumentIndex.document_id==doc['canonical_document_id']).all()
                        ids={r.chunk_id for r in records}
                        if ids!=set(doc['canonical_chunk_ids']):raise ValueError('PROMOTION_REPARSED_IDS_DIFFER_FROM_PLAN')
                        postimages={r.chunk_id:document_postimage(r) for r in records}
                        if any(postimages.get(cid)!=h for cid,h in intent.get('preexisting_postimages',{}).items()):
                            raise ValueError('PROMOTION_PREEXISTING_PUBLICATION_CONFLICT')
                        intent['document_postimages']=postimages
                        atomic_json(checkpoint_path,checkpoint)
                        commit()
                    db.commit=checked_commit
                    return db
                class ReadOnlyProgress:
                    def execute(self, sql, args=()):
                        return ledger.execute(sql,args) if sql.lstrip().lower().startswith('select') else None
                    def commit(self):pass
                def recovered_embeddings(texts, active_contract, unused_ledger):
                    if active_contract!=contract or any(t not in frozen_vectors for t in texts):raise ValueError('PROMOTION_TEXT_NOT_IN_FROZEN_RECOVERY')
                    return [frozen_vectors[t] for t in texts]
                p.SessionLocal,p.cached_embeddings=guarded_factory,recovered_embeddings
                try:
                    state, chunks, duplicate = p.process_file(row, contract, collection, ReadOnlyProgress(), references)
                finally:
                    p.SessionLocal,p.cached_embeddings=original_factory,original_embeddings
                # process_file is the normal parser/publisher. Re-verify its
                # exact identities against the approved-for-publication plan;
                # source changes or different parsing cannot be called success.
                if sha_file(guarded(doc["original_path"])) != doc["source_sha256"]:
                    raise ValueError("PROMOTION_SOURCE_CHANGED_DURING_PUBLICATION")
                with SessionLocal() as db:
                    published = db.query(DocumentIndex).filter(DocumentIndex.document_id == doc["canonical_document_id"]).all()
                    if state == 'SUCCEEDED' and {r.chunk_id for r in published} != set(doc["canonical_chunk_ids"]):
                        raise ValueError("PROMOTION_PUBLISHED_IDS_DIFFER_FROM_PLAN")
                    intent['document_postimages']={r.chunk_id:document_postimage(r) for r in published}
                # Save exact ORM postimage before updating the file ledger so
                # a crash/replay cannot silently bless a corrected document.
                atomic_json(checkpoint_path,checkpoint)
                ledger.execute("UPDATE files SET status=?,chunks=?,duplicate_of=?,reason=?,updated_at=?,checksum=?,document_id=?,embedding_version=?,model=?,collection_name=?,parser_version=?,chunk_version=? WHERE path=?",
                    (state, chunks, duplicate, "CONTENT_IDENTICAL" if duplicate else "", now(),doc['source_sha256'],doc['canonical_document_id'],contract['embedding_version'],contract['model'],contract['collection'],contract['parser_version'],contract['chunk_version'],row["path"]))
                ledger.commit()
                results.append({**intent,"status":state,'ledger_postimage':dict(ledger.execute('SELECT * FROM files WHERE path=?',(row['path'],)).fetchone())})
                checkpoint["documents"] = results
                atomic_json(checkpoint_path,checkpoint)
        finally:
            ledger.close()
        receipt = {"schema_version": "document-recovery-publication-receipt-v1", "checked_at": now(),
            "plan_sha256": plan["plan_sha256"], "operator": actor.user_id, "documents": results,
            "production_writes": True, "source_approval_created": False, "approval_created": False, "replayed": False}
        receipt['receipt_sha256']=digest(receipt)
        with sqlite3.connect(plan['ledger_path']) as history:
            history.execute('INSERT OR REPLACE INTO runs(run_id,root,status,started_at,ended_at,summary) VALUES(?,?,?,?,?,?)',
                ('promotion-'+plan['plan_sha256'],str(Path(plan['recovery_path']).parent),'COMPLETED_RECOVERY_BATCH',receipt['checked_at'],receipt['checked_at'],canonical({'plan_sha256':plan['plan_sha256'],'receipt_sha256':receipt['receipt_sha256'],'operator':actor.user_id}).decode()))
        atomic_json(receipt_path,receipt)
        return receipt


def rollback_plan(plan, receipt, request):
    """Authenticated additive rollback; only exact IDs newly added by this run."""
    from app.core.security import current_actor
    actor=current_actor(request)
    if actor.role not in {'operator','reviewer','admin'} or (actor.role!='admin' and actor.user_id!=receipt.get('operator')):
        raise ValueError('PROMOTION_ROLLBACK_OPERATOR_REQUIRED')
    if receipt.get('plan_sha256')!=plan.get('plan_sha256') or receipt.get('receipt_sha256')!=digest({k:v for k,v in receipt.items() if k!='receipt_sha256'}):
        raise ValueError('PROMOTION_ROLLBACK_RECEIPT_HASH_MISMATCH')
    from app.rag import document_pipeline as p
    from app.rag.document_contract import get_collection,CONTRACT_PATH
    from app.models.domain import DocumentIndex
    from app.core.database import SessionLocal
    if guarded(p.LEDGER)!=guarded(plan['ledger_path']) or guarded(CONTRACT_PATH)!=guarded(plan['contract_path']) or sha_file(CONTRACT_PATH)!=plan['contract_sha256']:
        raise ValueError('PROMOTION_ROLLBACK_CONFIG_OR_CONTRACT_CHANGED')
    with p.worker_lock():
        with readonly_ledger(plan['ledger_path']) as history:
            row=history.execute('SELECT * FROM runs WHERE run_id=?',('promotion-'+plan['plan_sha256'],)).fetchone()
            if not row or json.loads(row['summary']).get('receipt_sha256')!=receipt['receipt_sha256']:
                raise ValueError('PROMOTION_ROLLBACK_HISTORY_MISMATCH')
            if row['status']=='ROLLED_BACK_RECOVERY_BATCH':return {'status':'ROLLED_BACK','replayed':True,'deleted_chunk_ids':[]}
            if row['status'] not in {'COMPLETED_RECOVERY_BATCH','ROLLBACK_STARTED'}:raise ValueError('PROMOTION_ROLLBACK_STATE_INVALID')
            rollback_started=row['status']=='ROLLBACK_STARTED'
            for doc in receipt['documents']:
                state=history.execute('SELECT * FROM files WHERE path=?',(doc['original_path'],)).fetchone()
                acceptable=[doc['ledger_postimage']]
                if rollback_started:acceptable.append(doc['ledger_preimage'])
                if not state or dict(state) not in acceptable:raise ValueError('PROMOTION_ROLLBACK_LEDGER_CHANGED')
        collection=get_collection(json.loads(Path(plan['contract_path']).read_bytes()),create=False)
        added=[]
        with SessionLocal() as db:
            # Validate the entire rollback before any SQL or vector removal.
            for doc in receipt['documents']:
                expected=next(d for d in plan['documents'] if d['original_path']==doc['original_path'])
                if set(doc['added_chunk_ids']) & set(doc['preexisting_chunk_ids']) or not set(doc['added_chunk_ids'])<=set(expected['canonical_chunk_ids']):
                    raise ValueError('PROMOTION_ROLLBACK_NOT_ADDITIVE')
                for cid in doc['added_chunk_ids']:
                    actual=db.query(DocumentIndex).filter(DocumentIndex.chunk_id==cid).one_or_none()
                    if actual is None and rollback_started:continue
                    if actual is None or document_postimage(actual)!=doc.get('document_postimages',{}).get(cid) or actual.document_id!=expected['canonical_document_id']:
                        raise ValueError('PROMOTION_ROLLBACK_PUBLICATION_CHANGED')
                    added.append(actual)
            with sqlite3.connect(plan['ledger_path']) as history:
                history.execute("UPDATE runs SET status='ROLLBACK_STARTED' WHERE run_id=?",('promotion-'+plan['plan_sha256'],))
            for actual in added:db.delete(actual)
            db.commit()  # Unpublish before removing vectors; orphans stay unreachable.
        ids=[cid for doc in receipt['documents'] for cid in doc['added_chunk_ids']]
        if ids:collection.delete(ids=ids)
        with sqlite3.connect(plan['ledger_path']) as history:
            for doc in receipt['documents']:
                preimage=doc['ledger_preimage']; columns=[k for k in preimage if k!='path']
                current=history.execute('SELECT status,checksum FROM files WHERE path=?',(preimage['path'],)).fetchone()
                if current not in [(doc['status'],doc['source_sha256']),(preimage['status'],preimage['checksum'])]:raise ValueError('PROMOTION_ROLLBACK_LEDGER_CHANGED')
                history.execute('UPDATE files SET '+','.join('"'+k+'"=?' for k in columns)+' WHERE path=?',[preimage[k] for k in columns]+[preimage['path']])
            history.execute("UPDATE runs SET status='ROLLED_BACK_RECOVERY_BATCH' WHERE run_id=?",('promotion-'+plan['plan_sha256'],))
        return {'status':'ROLLED_BACK','replayed':False,'deleted_chunk_ids':ids,'preexisting_deleted':False}
