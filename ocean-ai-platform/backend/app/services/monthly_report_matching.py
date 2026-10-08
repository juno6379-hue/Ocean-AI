"""Serve a checksummed technical comparison without changing source approvals."""
import hashlib
import json
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings
from app.services import lake_browser


def comparison(month, source):
    root = Path(settings.MONTHLY_REPORT_MATCHING_ROOT).resolve()
    directory = root / month.replace('-', '')
    pointer = directory / 'published.json'
    if not pointer.is_file():
        raise HTTPException(404, '해당 월의 보고서–Parquet 대조 결과가 없습니다.')
    try:
        publication = json.loads(pointer.read_text(encoding='utf-8'))
        # A fixed local filename; the pointer cannot redirect outside this month.
        data = (directory / 'publication-match.json').read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != publication['sha256']:
            raise HTTPException(409, '보고서 대조 기록의 checksum이 일치하지 않습니다.')
        packet = json.loads(data)
        if packet['report_month'] != month or publication['report_month'] != month:
            raise HTTPException(409, '보고서 대조 기록의 기준월이 일치하지 않습니다.')
        if len(packet['publication_sha256']) != 64:
            raise HTTPException(409, '보고서 원문 식별 근거가 없습니다.')
        current, _ = lake_browser.context()
        state = 'CURRENT' if packet['snapshot'] == current.name else 'STALE'
        return {**packet, 'audit_state': state, 'current_snapshot': current.name,
                'audit_sha256': digest, 'source': source,
                'selected_source_summary': next((r for r in packet['source_summaries'] if r['source'] == source), None),
                'approval_status': 'UNAPPROVED',
                'stale_note': None if state == 'CURRENT' else '현재 조회 검증본이 달라 기존 대조 결과를 현재 일치 판정으로 사용할 수 없습니다.'}
    except HTTPException:
        raise
    except (OSError, KeyError, ValueError, TypeError):
        raise HTTPException(503, '보고서 대조 기록을 읽을 수 없습니다.')
