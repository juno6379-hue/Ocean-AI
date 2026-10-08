"""Continue an exhaustively reviewed isolated backlog without re-auditing claims."""
import argparse
import json
from pathlib import Path

from app.rag.ingestion_recovery import (RecoveryStore, backlog_snapshot, canonical,
    guarded, local_embedder, now, sha_file)


def run(output, contract_path, *, documents=48, chunks=6000):
    root=guarded(output)
    baseline=json.loads((root/'backlog-before.json').read_bytes())
    current=backlog_snapshot(baseline['ledger_path'])
    if current['snapshot_sha256']!=baseline['snapshot_sha256']:
        raise ValueError('RECOVERY_CANONICAL_LEDGER_CHANGED_REVIEW_REQUIRED')
    rows=[json.loads(line) for line in (root/'backlog-review.jsonl').read_bytes().splitlines()]
    if len(rows)!=len(baseline['backlog']) or {r['original_path'] for r in rows}!={r['path'] for r in baseline['backlog']}:
        raise ValueError('EXHAUSTIVE_REVIEW_MEMBERSHIP_MISMATCH')
    contract=json.loads(guarded(contract_path).read_bytes())
    store=RecoveryStore(root/'recovery.sqlite3',contract,source_ledger=baseline['ledger_path'])
    try:
        embed=local_embedder(contract)
        complete={r[0] for r in store.c.execute("SELECT sha256 FROM documents WHERE status='SUCCEEDED'")}
        candidates={}
        for row in rows:
            if row['parser_status']=='PARSEABLE' and row['preservation']['sha256'] not in complete:
                candidates.setdefault(row['preservation']['sha256'],row)
        selected=sorted(candidates.values(),key=lambda r:(r['chunks'],r['preservation']['sha256']))[:documents]
        results=[];budget=chunks
        progress={'checked_at':now(),'phase':'ISOLATED_RECOVERY_RESUME','batch_results':results,'collection':store.summary(),
                  'exhaustive_review_sha256':sha_file(root/'backlog-review.jsonl'),'production_writes':False}
        for row in selected:
            proof=row['preservation']
            if sha_file(guarded(proof['original_path']))!=proof['sha256']:
                raise ValueError('RECOVERY_ORIGINAL_SOURCE_CHANGED')
            before=store.summary()['chunks']
            result=store.ingest(proof,row['document_type'],embed,chunk_budget=budget)
            results.append(result);budget-=store.summary()['chunks']-before
            progress={'checked_at':now(),'phase':'ISOLATED_RECOVERY_RESUME','batch_results':results,'collection':store.summary(),
                      'exhaustive_review_sha256':sha_file(root/'backlog-review.jsonl'),'production_writes':False}
            (root/'resume-progress.json').write_bytes(canonical(progress))
            if budget<=0:break
        return {**progress,'remaining_parseable_unique_content':len(candidates)-sum(r['status']=='SUCCEEDED' for r in results)}
    finally:store.close()


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--contract',type=Path,required=True)
    p.add_argument('--documents',type=int,default=48);p.add_argument('--chunks',type=int,default=6000);a=p.parse_args()
    if not 1<=a.documents<=1000 or not 1<=a.chunks<=20000:raise ValueError('BOUNDED_RECOVERY_BUDGET_REQUIRED')
    r=run(a.output,a.contract,documents=a.documents,chunks=a.chunks)
    destination=guarded(a.output)/("resume-receipt-"+now().replace(':','').replace('.','')+".json")
    destination.write_bytes(canonical(r));print(json.dumps({'collection':r['collection'],'remaining_parseable_unique_content':r['remaining_parseable_unique_content']}))


if __name__=='__main__':main()
