# 파일 역할: 보고서 목록화·의미 청킹·임베딩 적재 배치를 실행합니다.
"""Run with python -m app.scripts.ingest_document_library --source <folder>."""
import argparse
import json
import os
from pathlib import Path
from app.rag.document_contract import STATE_DIR
from app.rag.document_pipeline import run, inventory, status


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--limit',type=int)
    ap.add_argument('--inventory-only',action='store_true')
    ap.add_argument('--retry-failed',action='store_true')
    args=ap.parse_args()
    if args.limit is not None and args.limit<1:ap.error('--limit must be positive')
    result=inventory(args.source) if args.inventory_only else run(args.source,args.limit,args.retry_failed)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)



if __name__=='__main__':main()
