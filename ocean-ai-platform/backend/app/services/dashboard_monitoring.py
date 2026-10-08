"""Read-only dashboard metrics with explicit denominators and evidence scope.

Source QC presence is not QC correctness. A monthly document overlap is a
review candidate, not proof of a current fault, submission, or sensor cause.
"""
from collections import Counter
from datetime import date
import calendar
import json
import sqlite3

from fastapi import HTTPException
from sqlalchemy import text
from app.api.routes_foundation import snapshot, read_json


CONDITIONS = {
    'station_dictionary_decision': '관측소 코드', 'item_dictionary_decision': '항목 코드',
    'unit_application_decision': '단위 적용', 'sensor_decision': '물리 센서',
    'period_decision': '유효기간', 'timezone_decision': '시간대',
    'qc_evidence_decision': 'QC 근거', 'qc_approval_decision': 'QC 승인',
}


def aggregate(rows):
    total = sum(r['held_rows'] or 0 for r in rows)
    fields = ['missing_value_rows', 'invalid_time_rows', 'source_qc_present_rows', 'numeric_rows']
    sums = {key: sum(r[key] for r in rows) if rows and all(r[key] is not None for r in rows) else None for key in fields}
    def rate(n):
        return round(100*n/total, 3) if n is not None and total else None
    return {'held_rows':total, 'monthly_records':len(rows), **sums,
            'source_qc_presence_rate':rate(sums['source_qc_present_rows']),
            'missing_value_rate':rate(sums['missing_value_rows']),
            'collection_rate':None, 'expected_observations':None,
            'qc_normal_rate':None, 'qc_bad_rate':None,
            'collection_reason':'관측 주기·운영기간·예정 관측건수 미확정',
            'qc_reason':'승인된 QC 분류별 집계 없음 · 원천 QC 표기와 정상 판정은 별개',
            'conditions':[{'key':key,'name':name,'counts':dict(Counter(r[key] or '미확정' for r in rows))} for key,name in CONDITIONS.items()]}


def monitoring(source, start, end, station=None, item=None, station_scope=None):
    run, view = snapshot()
    dbpath = view/'validation.sqlite3'
    if not dbpath.is_file():
        raise HTTPException(503, '검증 원장 미준비')
    with sqlite3.connect(dbpath.as_uri()+'?mode=ro', uri=True, timeout=10) as db:
        db.row_factory = sqlite3.Row
        columns = ','.join(['station_code','station_name','item_code','month','held_rows','missing_value_rows',
                           'invalid_time_rows','source_qc_present_rows','numeric_rows', *CONDITIONS])
        where = 'source_group=? AND month>=? AND month<=?'
        args = [source,start+'-01',end+'-31']
        if station: where += ' AND station_code=?'; args.append(station)
        if item: where += ' AND item_code=?'; args.append(item)
        from app.services.station_classification import sql_scope
        extra,extra_args=sql_scope(station_scope)
        where+=extra;args+=extra_args
        rows = [dict(r) for r in db.execute(f'SELECT {columns} FROM monthly_validation WHERE {where}', args)]
    index = {}
    for r in rows:
        index.setdefault((r['station_code'],r['item_code']),[]).append(r)
    # Current report-event validation was performed against this baseline only.
    events = []
    event_path = view/'report-event-validation.json'
    if source == 'GD_OBS_ST_MONTHLY' and event_path.exists():
        for e in read_json(event_path):
            matched = [r for station in e['station_codes'] for item in e['item_codes']
                       for r in index.get((station,item),[])
                       if e['period_start'][:7] <= r['month'][:7] <= e['period_end_inclusive'][:7]]
            if not matched: continue
            events.append({**e,'relation':'보고서 기간과 보유 월 대응 · 원인 미승인',
                           'linked_monthly_records':len(matched),
                           'linked_held_rows':sum(r['held_rows'] for r in matched)})
    whole = read_json(view/'summary.json')
    extraction = run/'expanded-extraction-status.json'
    extraction_data = None
    if extraction.exists():
        try:
            x = read_json(extraction)
            extraction_data = {k:x.get(k) for k in ['at','state','completed','total','counts','semantic_review']}
        except (OSError, ValueError):
            extraction_data = {'state':'STATUS_UNAVAILABLE'}
    month_groups = {}
    for r in rows: month_groups.setdefault(r['month'],[]).append(r)
    monthly = [{'month':month[:7], **aggregate(group)} for month,group in sorted(month_groups.items())]
    channels = []
    for (code,code_item), group in sorted(index.items()):
        stats = aggregate(group)
        channels.append({'station_code':code,'station_name':group[0]['station_name'],'item_code':code_item,
                         **{k:stats[k] for k in ['held_rows','missing_value_rows','source_qc_present_rows','source_qc_presence_rate','missing_value_rate']}})
    return {'snapshot':view.name,'source':source,'from_month':start,'to_month':end,
            'observation_metrics_available':source != 'HISTORICAL_RECONCILED',
            'observations':aggregate(rows), 'events':events, 'monthly':monthly, 'channels':channels,
            'documents':{'scope':'전체 문서 검증본 · 선택 관측기간과 별도', 'snapshot_at':whole.get('at'),
                'history_documents':whole.get('history_documents'), 'history_claims':whole.get('history_claims'),
                'inspection_candidates':whole.get('inspection_row_candidates'),
                'installation_candidates':whole.get('management_installation_claims'),
                'maintenance_candidates':whole.get('management_maintenance_events'),
                'management_conflicts':whole.get('management_conflicts'), 'extraction':extraction_data},
            'limitations':'보유 행은 고유 관측 건수가 아닙니다. 문서 추출·대응·원천 QC 표기는 담당 승인과 별개입니다.'}


def daily_reports(db, start, end, day=None):
    from app.rag.document_contract import load_contract
    try:
        version = load_contract()['embedding_version']
    except (OSError, KeyError, ValueError, RuntimeError):
        raise HTTPException(503, '활성 문서 색인 계약 확인 필요')
    y,m = map(int,end.split('-'))
    args = {'version':version,'start':start+'-01','end':f'{end}-{calendar.monthrange(y,m)[1]:02d}'}
    # Count documents, never chunks; only the active published embedding contract.
    docs = [dict(r) for r in db.execute(text('''SELECT document_id, max(document_title) title,
      max(document_type) document_type, max(document_date) document_date,
      min(chunk_id) citation_chunk_id, count(*) chunks,
      string_agg(DISTINCT related_station_id, ',') station_codes
      FROM document_index WHERE embedding_version=:version
      AND document_type IN ('DAILY_SITUATION_REPORT','DAILY_INSPECTION_REPORT')
      AND (document_date IS NULL OR cast(document_date as date) BETWEEN cast(:start as date) AND cast(:end as date))
      GROUP BY document_id ORDER BY max(document_date) DESC NULLS LAST, document_id'''),args).mappings()]
    dated = [r for r in docs if r['document_date'] is not None]
    selected_day = day or (max(r['document_date'].date() for r in dated) if dated else None)
    if selected_day and not (date.fromisoformat(args['start']) <= selected_day <= date.fromisoformat(args['end'])):
        raise HTTPException(422,'보고 기준일은 선택 기간 안이어야 합니다.')
    selected = [r for r in dated if r['document_date'].date() == selected_day]
    recent = []
    for r in selected[:30]:
        citation = db.execute(text('SELECT page_no,section_name,chunk_text,metadata_json FROM document_index WHERE chunk_id=:id'),{'id':r['citation_chunk_id']}).mappings().first()
        meta = (citation['metadata_json'] or {}) if citation else {}
        recent.append({**r,'document_date':r['document_date'].isoformat(),
                       'stations':r['station_codes'].split(',') if r['station_codes'] else [],
                       'citation':{'page':citation['page_no'],'section':citation['section_name'],
                         'excerpt':(citation['chunk_text'] or '')[:700],
                         'locator':meta.get('locator'), 'date_source':meta.get('date_source') or meta.get('report_date_source') or '추출 기준 확인 필요'} if citation else None,
                       'approval_status':'UNCONFIRMED'})
    return {'scope':'전체 게시 문서 색인 · 원천 필터와 별도 · 날짜는 추출된 문서 기준일',
            'embedding_version':version,'selected_day':str(selected_day) if selected_day else None,
            'selection_mode':'EXPLICIT_DAY' if day else 'LATEST_HELD_DAY_IN_PERIOD',
            'period_documents':len(dated),'unresolved_date_documents_all_periods':len(docs)-len(dated),
            'selected_day_documents':len(selected), 'by_type':dict(Counter(r['document_type'] for r in selected)),
            'expected_submissions':None,'missing_submissions':None,'submission_rate':None,
            'latest_available_day':str(max(r['document_date'].date() for r in dated)) if dated else None,
            'documents':recent,'returned_limit':30,
            'note':'수집·색인된 문서 현황입니다. 제출 대상/기한이 미확정이므로 미수집을 미제출로 판정하지 않습니다. 추출 날짜는 담당 검토 전이며 원문의 사건 발생일과 다를 수 있습니다.'}


def equipment_evidence(source, start, end, station=None, station_scope=None):
    """Station-key document candidates, not a physical-device operating register.

    Installation claims retain their full chronology. Maintenance uses document
    header month, inspections use report date; neither proves sensor validity.
    """
    _, view = snapshot()
    with sqlite3.connect((view/'validation.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        args=[source,start+'-01',end+'-31']
        where='source_group=? AND month>=? AND month<=?'
        if station: where+=' AND station_code=?';args.append(station)
        from app.services.station_classification import sql_scope
        extra,extra_args=sql_scope(station_scope)
        where+=extra;args+=extra_args
        codes={r[0] for r in db.execute(f'SELECT DISTINCT station_code FROM monthly_validation WHERE {where}',args)}
        def candidates(table):
            result=[]
            for raw in db.execute(f'SELECT * FROM {table}'):
                row=dict(raw)
                for key in ['station_codes','date_headers','item_candidates']:
                    if key in row and isinstance(row[key],str):row[key]=json.loads(row[key])
                matched=sorted(codes.intersection(row.get('station_codes',[])))
                if matched:
                    row.update(linked_station_codes=matched,relation='관측소 코드 대응 · 물리 센서/운영기간 미승인')
                    result.append(row)
            return result
        installs=candidates('management_installation_claims')
        maintenance=candidates('management_maintenance_events')
        inspections=candidates('inspection_candidates')
        conflicts=[dict(r) for r in db.execute('SELECT * FROM management_conflicts') if r['station_code'] in codes]
    unknown_maintenance=sum(not r.get('candidate_month') for r in maintenance)
    unknown_inspections=sum(not r.get('report_date') for r in inspections)
    maintenance=[r for r in maintenance if r.get('candidate_month') and start<=r['candidate_month'][:7]<=end]
    inspections=[r for r in inspections if r.get('report_date') and start<=r['report_date'][:7]<=end]
    maintenance.sort(key=lambda r:(r['candidate_month'],r['id']),reverse=True)
    inspections.sort(key=lambda r:(r['report_date'],r['id']),reverse=True)
    installs.sort(key=lambda r:(r.get('station_name') or '',r.get('device') or '',r['id']))
    return dict(snapshot=view.name,source=source,from_month=start,to_month=end,
                station_codes=sorted(codes),installations=installs,maintenance=maintenance,inspections=inspections,
                conflicts=conflicts,undated_maintenance=unknown_maintenance,undated_inspections=unknown_inspections,
                operating_devices=None,scheduled_inspections=None,replacement_due=None,maintenance_completion_rate=None,
                installation_scope='선택 범위에 자료를 보유한 관측소의 전체 설치 이력 후보 · 조회기간 밖 포함',
                event_scope='정비: 문서 날짜 머리글 후보 월 / 점검: 보고서 기준일 · 선택 기간 내',
                limitations='후보 행 수는 실제 장비 수·장애 접수·작업 완료 수가 아닙니다. 설치 주장과 센서 유효기간, 관측소 운영기간을 구분합니다.')
