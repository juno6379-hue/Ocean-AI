"""실제 RDB의 연결 완전성과 시간 관계를 검증한다. 날짜 후보를 인과 연결로 승격하지 않는다."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json
from sqlalchemy import create_engine,text
from app.core.config import settings

def verify(output):
 e=create_engine(settings.DATABASE_URL,connect_args={'connect_timeout':10})
 result={'checked_at_utc':datetime.now(timezone.utc).isoformat()}
 with e.connect() as c:
  with c.begin():
   c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='60s'"))
   def q(name,sql):result[name]=[dict(r) for r in c.execute(text(sql)).mappings()]
   q('run',"SELECT run_id,status,completed_at,counts FROM foundation.ingestion_run WHERE run_id=(SELECT run_id FROM foundation.v_current_run)")
   assert len(result['run'])==1
   rid=result['run'][0]['run_id'];expected=result['run'][0]['counts'];actual={}
   for name,count in expected.items():
    assert name.replace('_','').isalnum()
    actual[name]=c.execute(text('SELECT count(*) FROM foundation.'+name+' WHERE run_id=:rid'),{'rid':rid}).scalar()
    assert actual[name]==count,(name,actual[name],count)
   result['verified_counts']=actual
   q('source_kind_counts','SELECT source_kind,count(*) AS records FROM foundation.source_asset JOIN foundation.v_current_run USING(run_id) GROUP BY source_kind ORDER BY source_kind')
   q('station_identity','SELECT namespace,metadata_present,count(*) AS records FROM foundation.station_record JOIN foundation.v_current_run USING(run_id) GROUP BY namespace,metadata_present ORDER BY namespace,metadata_present')
   q('contracts',"SELECT count(*) AS total,count(*) FILTER(WHERE unit_raw IS NULL OR unit_raw='') AS missing_unit,count(*) FILTER(WHERE physical_sensor_id IS NOT NULL) AS physical_sensor_bound,count(*) FILTER(WHERE valid_from IS NOT NULL) AS approved_start_present,count(*) FILTER(WHERE timezone_name IS NOT NULL) AS timezone_bound,count(*) FILTER(WHERE approval_status='APPROVED') AS approved FROM foundation.channel_contract JOIN foundation.v_current_run USING(run_id)")
   q('equipment_links',"SELECT count(*) AS candidate_links,count(*) FILTER(WHERE installed_at_raw IS NOT NULL AND installed_at_raw<>'') AS equipment_start_raw_present,count(*) FILTER(WHERE temporal_binding_approved) AS approved_temporal_links FROM foundation.channel_equipment_candidate l JOIN foundation.v_current_run USING(run_id) JOIN foundation.equipment_record e USING(run_id,equipment_id)")
   q('coverage_identity',"SELECT count(*) AS monthly_groups,count(*) FILTER(WHERE s.metadata_present) AS station_metadata_present,count(*) FILTER(WHERE c.physical_sensor_id IS NOT NULL) AS physical_sensor_bound,count(*) FILTER(WHERE s.station_id_raw='UNRESOLVED_STATION') AS unresolved_station_groups,count(*) FILTER(WHERE EXISTS(SELECT 1 FROM foundation.channel_contract cc WHERE cc.run_id=c.run_id AND cc.station_key=c.station_key AND cc.item_code_raw=c.item_code_raw)) AS station_item_contract_candidate_groups FROM foundation.observation_coverage c JOIN foundation.v_current_run USING(run_id) JOIN foundation.station_record s USING(run_id,station_key)")
   q('coverage_by_source',"SELECT a.source_path,count(*) AS monthly_groups,count(DISTINCT c.station_key) AS source_station_ids,count(DISTINCT c.item_code_raw) AS item_codes,min(c.first_raw_clock) AS first_raw_clock,max(c.last_raw_clock) AS last_raw_clock FROM foundation.observation_coverage c JOIN foundation.v_current_run USING(run_id) JOIN foundation.source_asset a USING(run_id,asset_id) GROUP BY a.source_path ORDER BY a.source_path")
   q('coverage_rollup_counts',"SELECT count(*) AS source_station_item_depth_series,count(*) FILTER(WHERE usability='HOLD_UNIT_TIMEZONE_SENSOR_QC_CONTRACT') AS hold_series FROM foundation.v_series_judgement")
   q('operation_summary',"SELECT count(*) AS evidence_records,count(*) FILTER(WHERE event_date IS NOT NULL) AS day_precision,count(*) FILTER(WHERE physical_sensor_id IS NOT NULL) AS physical_sensor_bound,count(*) FILTER(WHERE review_status='PENDING') AS pending FROM foundation.operation_event JOIN foundation.v_current_run USING(run_id)")
   q('operation_timeline',"SELECT station_id_claim,event_date_raw,date_precision,event_type,description,source_locator,document_id,review_status FROM foundation.operation_event JOIN foundation.v_current_run USING(run_id) ORDER BY event_date_raw,event_id")
   q('calendar_candidates',"SELECT count(*) AS candidate_links,count(DISTINCT coverage_id) AS monthly_groups,count(DISTINCT event_id) AS event_records,count(*) FILTER(WHERE causal_link_approved) AS causal_approved FROM foundation.v_operation_calendar_candidates")
   q('calendar_candidate_examples',"SELECT station_id_raw,item_code_raw,first_raw_clock,last_raw_clock,event_date,description,source_locator,match_basis FROM foundation.v_operation_calendar_candidates ORDER BY event_date,item_code_raw LIMIT 12")
   q('qc_evidence',"SELECT count(*) AS intervals,count(*) FILTER(WHERE raw_calendar_event_candidates>0) AS intervals_with_calendar_candidate,sum(raw_calendar_event_candidates) AS candidate_links FROM foundation.v_qc_evidence_judgement")
   q('constraints',"SELECT conname,contype,convalidated FROM pg_constraint WHERE connamespace='foundation'::regnamespace ORDER BY conname")
   assert all(r['convalidated'] for r in result['constraints'])
   q('schema_sizes',"SELECT relname,pg_total_relation_size(relid) AS bytes FROM pg_stat_user_tables WHERE schemaname='foundation' ORDER BY relname")
   q('database_size','SELECT pg_database_size(current_database()) AS bytes')
   q('public_scope',"SELECT 'observation_raw' AS table_name,count(*) AS rows FROM public.observation_raw UNION ALL SELECT 'observation_standard',count(*) FROM public.observation_standard UNION ALL SELECT 'sensor_metadata',count(*) FROM public.sensor_metadata UNION ALL SELECT 'station_metadata',count(*) FROM public.station_metadata")
  # 제약조건 시험은 SAVEPOINT 안에서 실행하고 항상 롤백하여 시험 변경을 남기지 않는다.
  tests={}
  with c.begin():
   checks={
    'reject_unsupported_approval':"UPDATE foundation.channel_contract SET approval_status='APPROVED' WHERE (run_id,contract_id)=(SELECT run_id,contract_id FROM foundation.channel_contract LIMIT 1)",
    'reject_unknown_sensor_candidate_as_approved':"UPDATE foundation.channel_equipment_candidate SET temporal_binding_approved=true WHERE (run_id,contract_id,equipment_id)=(SELECT run_id,contract_id,equipment_id FROM foundation.channel_equipment_candidate LIMIT 1)",
    'reject_orphan_parquet_source':"UPDATE foundation.parquet_artifact SET asset_id='nonexistent-test-source' WHERE (run_id,artifact_id)=(SELECT run_id,artifact_id FROM foundation.parquet_artifact LIMIT 1)",
    'reject_reverse_coverage_interval':"UPDATE foundation.observation_coverage SET last_raw_clock=first_raw_clock-interval '1 day' WHERE (run_id,coverage_id)=(SELECT run_id,coverage_id FROM foundation.observation_coverage WHERE first_raw_clock IS NOT NULL LIMIT 1)"
   }
   for name,sql in checks.items():
    sp=c.begin_nested()
    try:c.execute(text(sql))
    except Exception as ex:
     sp.rollback();tests[name]=getattr(ex.orig,'pgcode',None)
    else:sp.rollback();raise AssertionError('Constraint did not reject '+name)
   expected_codes={'reject_unsupported_approval':'23514','reject_unknown_sensor_candidate_as_approved':'23514','reject_orphan_parquet_source':'23503','reject_reverse_coverage_interval':'23514'}
   assert tests==expected_codes,tests
  result['rollback_only_constraint_tests']=tests
 e.dispose()
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,default=str)
 print(json.dumps({k:result[k] for k in ['verified_counts','contracts','equipment_links','calendar_candidates','qc_evidence','database_size','rollback_only_constraint_tests']},ensure_ascii=False,default=str))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();verify(a.output)
