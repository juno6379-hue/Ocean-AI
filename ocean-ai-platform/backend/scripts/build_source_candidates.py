"""Read-only source candidate export. It never writes database rows."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.source_contract_snapshot import create_candidate_snapshot,canonical_bytes


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--request',required=True,help='JSON with source/parquet exact hashes, scopes and bounded limit')
    parser.add_argument('--output-root',required=True)
    parser.add_argument('--summary')
    args=parser.parse_args()
    request=json.loads(Path(args.request).read_text(encoding='utf-8'))
    result=create_candidate_snapshot(**request,root=args.output_root)
    summary={k:v for k,v in result.items() if k!='snapshot'}|{k:result['snapshot'][k] for k in
        ('status','training_eligible','candidate_count','operational_membership_count','coverage','validation_errors')}
    if args.summary:Path(args.summary).write_bytes(canonical_bytes(summary))
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
