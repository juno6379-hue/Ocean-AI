"""Scope, denominators and evidence boundaries for monitoring UI (no live MDC)."""
from datetime import date, datetime
from pathlib import Path
import json
import sqlite3
import uuid
import pytest
from fastapi import HTTPException
from app.services import dashboard_monitoring as m


def row(total=100, missing=5, qc=90, **extra):
    return dict(held_rows=total, missing_value_rows=missing, source_qc_present_rows=qc,
                invalid_time_rows=0, numeric_rows=total-missing,
                **{key:'근거 부족' for key in m.CONDITIONS}, **extra)


def test_weighted_denominators_and_unknowns_are_not_qc_approval():
    result=m.aggregate([row(10,1,10),row(90,9,0)])
    assert result['source_qc_presence_rate']==10
    assert result['missing_value_rate']==10
    assert result['qc_normal_rate'] is None
    assert result['qc_bad_rate'] is None
    assert result['collection_rate'] is None
    assert m.aggregate([row(),row(qc=None)])['source_qc_present_rows'] is None
    assert m.aggregate([])['missing_value_rate'] is None
    assert m.aggregate([row(0,0,0)])['source_qc_presence_rate'] is None


def test_source_period_station_item_and_ambiguous_event_isolation(monkeypatch):
    root=Path(__file__).parent/'.work'/('monitoring-'+uuid.uuid4().hex)
    root.mkdir(parents=True)
    values=[]
    for source,station,item,month in [('GD_OBS_ST_MONTHLY','DT_1','TEMP','2026-07-01'),
             ('GD_OBS_ST_MONTHLY','DT_2','TEMP','2026-07-01'),('GD_OBS_ST_MONTHLY','DT_1','SALT','2026-07-01'),
             ('GD_OBS_ST_MONTHLY','DT_1','TEMP','2026-08-01'),('GD_OBS_BU','DT_1','TEMP','2026-07-01')]:
        values.append(row(source_group=source,station_code=station,station_name=station,item_code=item,month=month))
    with sqlite3.connect(root/'validation.sqlite3') as db:
        keys=list(values[0]);types=['INTEGER' if isinstance(values[0][k],int) else 'TEXT' for k in keys]
        db.execute('CREATE TABLE monthly_validation ('+','.join(k+' '+t for k,t in zip(keys,types))+')')
        db.executemany('INSERT INTO monthly_validation VALUES ('+','.join('?' for _ in keys)+')',[[r[k] for k in keys] for r in values])
    base=dict(station_codes=['DT_1'],item_codes=['TEMP'],period_start='2026-07',period_end_inclusive='2026-07')
    events=[dict(base,id='exact'),dict(base,id='wildcard',item_codes=['*']),dict(base,id='unknown',station_codes=[]),dict(base,id='future',period_start='2026-08',period_end_inclusive='2026-08')]
    (root/'report-event-validation.json').write_text(json.dumps(events),encoding='utf-8')
    (root/'summary.json').write_text('{}',encoding='utf-8')
    monkeypatch.setattr(m,'snapshot',lambda:(root,root))
    result=m.monitoring('GD_OBS_ST_MONTHLY','2026-07','2026-07','DT_1','TEMP')
    assert result['observations']['held_rows']==100
    assert [e['id'] for e in result['events']]==['exact']
    assert result['events'][0]['linked_monthly_records']==1
    assert len(result['monthly'])==len(result['channels'])==1
    assert not m.monitoring('GD_OBS_BU','2026-07','2026-07')['events']
    assert m.monitoring('GD_OBS_ST_MONTHLY','2026-07','2026-07',"DT_1' OR 1=1 --")['observations']['held_rows']==0


class Results:
    def __init__(self,rows):self.rows=rows
    def mappings(self):return self
    def __iter__(self):return iter(self.rows)
    def first(self):return self.rows[0] if self.rows else None


class Documents:
    def execute(self,query,args):
        if 'GROUP BY document_id' in str(query):
            assert args=={'version':'verified-contract','start':'2024-02-01','end':'2024-02-29'}
            return Results([dict(document_id='a',title='daily',document_type='DAILY_SITUATION_REPORT',document_date=datetime(2024,2,29),citation_chunk_id='a1',chunks=20,station_codes='DT_1'),
                            dict(document_id='unknown',title='no date',document_type='DAILY_INSPECTION_REPORT',document_date=None,citation_chunk_id='x1',chunks=2,station_codes=None)])
        return Results([dict(page_no=7,section_name='inspection',chunk_text='source evidence',metadata_json={'locator':'pdf_page:7'})])


def test_daily_reports_count_documents_not_chunks_and_keep_missing_schedule_unknown(monkeypatch):
    from app.rag import document_contract
    monkeypatch.setattr(document_contract,'load_contract',lambda:{'embedding_version':'verified-contract'})
    result=m.daily_reports(Documents(),'2024-02','2024-02')
    assert result['period_documents']==1
    assert result['selected_day_documents']==1
    assert result['selected_day']=='2024-02-29'
    assert result['unresolved_date_documents_all_periods']==1
    assert result['expected_submissions'] is result['missing_submissions'] is result['submission_rate'] is None
    assert result['documents'][0]['citation']['page']==7
    assert result['documents'][0]['approval_status']=='UNCONFIRMED'
    empty=m.daily_reports(Documents(),'2024-02','2024-02',date(2024,2,28))
    assert empty['selected_day_documents']==0 and empty['submission_rate'] is None
    with pytest.raises(HTTPException) as exc:m.daily_reports(Documents(),'2024-02','2024-02',date(2024,3,1))
    assert exc.value.status_code==422


def test_equipment_history_keeps_installation_claims_separate_from_period_and_sensor(monkeypatch):
    root=Path(__file__).parent/'.work'/('equipment-'+uuid.uuid4().hex);root.mkdir(parents=True)
    with sqlite3.connect(root/'validation.sqlite3') as db:
        db.execute('CREATE TABLE monthly_validation(source_group TEXT,station_code TEXT,month TEXT)')
        db.execute("INSERT INTO monthly_validation VALUES ('GD_OBS_ST_MONTHLY','DT_1','2026-07-01')")
        db.execute('CREATE TABLE management_installation_claims(id TEXT, station_codes TEXT,station_name TEXT,device TEXT,date_raw TEXT,valid_from TEXT,valid_to TEXT)')
        db.execute('INSERT INTO management_installation_claims VALUES (?,?,?,?,?,?,?)',('install','["DT_1"]','station','sensor','2019.02.',None,None))
        db.execute('CREATE TABLE management_maintenance_events(id TEXT,station_codes TEXT,candidate_month TEXT)')
        db.executemany('INSERT INTO management_maintenance_events VALUES (?,?,?)',[('match','["DT_1"]','2026-07'),('outside','["DT_1"]','2026-08'),('undated','["DT_1"]',None),('other','["DT_2"]','2026-07')])
        db.execute('CREATE TABLE inspection_candidates(id TEXT,station_codes TEXT,report_date TEXT)')
        db.execute('INSERT INTO inspection_candidates VALUES (?,?,?)',('inspection','["DT_1"]','2026-07-02'))
        db.execute('CREATE TABLE management_conflicts(id TEXT,station_code TEXT)')
    monkeypatch.setattr(m,'snapshot',lambda:(root,root))
    result=m.equipment_evidence('GD_OBS_ST_MONTHLY','2026-07','2026-07')
    assert result['installations'][0]['date_raw']=='2019.02.'
    assert result['installations'][0]['valid_from'] is None
    assert [r['id'] for r in result['maintenance']]==['match']
    assert result['undated_maintenance']==1
    assert result['inspections'][0]['report_date']=='2026-07-02'
    assert result['operating_devices'] is result['maintenance_completion_rate'] is None
    assert not m.equipment_evidence('GD_OBS_BU','2026-07','2026-07')['installations']
