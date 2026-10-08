-- 원천 스냅샷의 시점과 실제 유효기간을 분리한다. 기존 public 서비스 테이블은 변경하지 않는다.
CREATE SCHEMA IF NOT EXISTS foundation;
CREATE TABLE IF NOT EXISTS foundation.ingestion_run (
 run_id text PRIMARY KEY, input_manifest jsonb NOT NULL, started_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz, status text NOT NULL CHECK(status IN ('LOADING','COMPLETE')),
 counts jsonb, schema_version text NOT NULL DEFAULT '1'
);
CREATE TABLE IF NOT EXISTS foundation.source_asset (
 run_id text NOT NULL REFERENCES foundation.ingestion_run, asset_id text NOT NULL,
 source_kind text NOT NULL, namespace text NOT NULL, source_path text NOT NULL,
 source_sha256 text, byte_size bigint CHECK(byte_size>=0), mtime_ns bigint,
 processing_status text NOT NULL, role_hint text, metadata jsonb NOT NULL DEFAULT '{}',
 PRIMARY KEY(run_id,asset_id), UNIQUE(run_id,namespace,source_path)
);
CREATE TABLE IF NOT EXISTS foundation.station_record (
 run_id text NOT NULL REFERENCES foundation.ingestion_run, station_key text NOT NULL,
 namespace text NOT NULL, station_id_raw text NOT NULL, station_name_raw text,
 metadata_present boolean NOT NULL, source_payload jsonb NOT NULL,
 identity_status text NOT NULL DEFAULT 'SOURCE_ID_ONLY_HISTORY_UNVERIFIED',
 PRIMARY KEY(run_id,station_key), UNIQUE(run_id,namespace,station_id_raw)
);
CREATE TABLE IF NOT EXISTS foundation.equipment_record (
 run_id text NOT NULL REFERENCES foundation.ingestion_run, equipment_id text NOT NULL,
 station_key text, source_table text NOT NULL, equipment_code text, serial_raw text,
 installed_at_raw text, removed_at_raw text, checked_at_raw text,
 physical_sensor_id text, valid_from timestamptz, valid_to timestamptz,
 end_status text NOT NULL DEFAULT 'UNKNOWN' CHECK(end_status IN ('UNKNOWN','KNOWN','REVIEWED_OPEN')),
 binding_status text NOT NULL DEFAULT 'SOURCE_METADATA_UNVERIFIED', source_payload jsonb NOT NULL,
 PRIMARY KEY(run_id,equipment_id), FOREIGN KEY(run_id,station_key) REFERENCES foundation.station_record,
 CHECK(valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>=valid_from))
);
CREATE TABLE IF NOT EXISTS foundation.channel_contract (
 run_id text NOT NULL REFERENCES foundation.ingestion_run, contract_id text NOT NULL,
 station_key text NOT NULL, item_code_raw text NOT NULL, equipment_code text, unit_raw text,
 timezone_name text, physical_sensor_id text, valid_from timestamptz, valid_to timestamptz,
 validity_status text NOT NULL DEFAULT 'UNKNOWN', qc_policy_reference text,
 approval_status text NOT NULL DEFAULT 'HOLD', reviewer_reference text,
 blockers jsonb NOT NULL, source_payload jsonb NOT NULL,
 PRIMARY KEY(run_id,contract_id), FOREIGN KEY(run_id,station_key) REFERENCES foundation.station_record,
 CHECK(valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to>=valid_from)),
 CHECK(approval_status IN ('HOLD','APPROVED')),
 CHECK(approval_status <> 'APPROVED' OR (reviewer_reference IS NOT NULL AND unit_raw IS NOT NULL
  AND timezone_name IS NOT NULL AND physical_sensor_id IS NOT NULL AND valid_from IS NOT NULL
  AND validity_status='REVIEWED' AND qc_policy_reference IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS foundation.channel_equipment_candidate (
 run_id text NOT NULL, contract_id text NOT NULL, equipment_id text NOT NULL, match_status text NOT NULL,
 temporal_binding_approved boolean NOT NULL DEFAULT false CHECK(temporal_binding_approved=false),
 PRIMARY KEY(run_id,contract_id,equipment_id),
 FOREIGN KEY(run_id,contract_id) REFERENCES foundation.channel_contract,
 FOREIGN KEY(run_id,equipment_id) REFERENCES foundation.equipment_record
);
CREATE TABLE IF NOT EXISTS foundation.parquet_artifact (
 run_id text NOT NULL, artifact_id text NOT NULL, asset_id text NOT NULL,
 artifact_path text NOT NULL, sha256 text NOT NULL, row_count bigint NOT NULL CHECK(row_count>=0),
 source_format text NOT NULL, original_manifest text NOT NULL, manifest_sha256 text NOT NULL,
 approval_status text NOT NULL DEFAULT 'RAW_ONLY', PRIMARY KEY(run_id,artifact_id),
 FOREIGN KEY(run_id,asset_id) REFERENCES foundation.source_asset, UNIQUE(run_id,artifact_path)
);
CREATE TABLE IF NOT EXISTS foundation.document_record (
 run_id text NOT NULL REFERENCES foundation.ingestion_run, document_id text NOT NULL,
 sha256 text NOT NULL, extraction_status text NOT NULL, chunk_count integer,
 evidence_metadata jsonb NOT NULL, PRIMARY KEY(run_id,document_id), UNIQUE(run_id,sha256)
);
CREATE TABLE IF NOT EXISTS foundation.document_location (
 run_id text NOT NULL, document_id text NOT NULL, asset_id text NOT NULL,
 binding_status text NOT NULL DEFAULT 'EXTRACTION_SNAPSHOT_NOT_CURRENT_REHASH',
 PRIMARY KEY(run_id,document_id,asset_id),
 FOREIGN KEY(run_id,document_id) REFERENCES foundation.document_record,
 FOREIGN KEY(run_id,asset_id) REFERENCES foundation.source_asset
);
CREATE TABLE IF NOT EXISTS foundation.operation_event (
 run_id text NOT NULL, event_id text NOT NULL, document_id text NOT NULL,
 station_id_claim text NOT NULL, event_type text NOT NULL, event_date_raw text NOT NULL,
 date_precision text NOT NULL, event_date date, event_start_utc timestamptz, event_end_utc timestamptz,
 physical_sensor_id text, equipment_expression text, description text NOT NULL,
 source_locator text NOT NULL, source_excerpt text, review_status text NOT NULL DEFAULT 'PENDING',
 source_payload jsonb NOT NULL, PRIMARY KEY(run_id,event_id),
 FOREIGN KEY(run_id,document_id) REFERENCES foundation.document_record,
 CHECK(date_precision='day' OR event_date IS NULL)
);
CREATE TABLE IF NOT EXISTS foundation.observation_coverage (
 run_id text NOT NULL, coverage_id text NOT NULL, asset_id text NOT NULL, station_key text NOT NULL,
 item_code_raw text NOT NULL, depth_identity jsonb NOT NULL DEFAULT '{}', physical_sensor_id text,
 month_raw text NOT NULL, first_raw_clock timestamp, last_raw_clock timestamp,
 row_count bigint NOT NULL CHECK(row_count>=0), null_count bigint,
 time_basis text NOT NULL DEFAULT 'SOURCE_NAIVE_UNVERIFIED', qc_valid_count bigint,
 profile_reference text NOT NULL, PRIMARY KEY(run_id,coverage_id),
 FOREIGN KEY(run_id,asset_id) REFERENCES foundation.source_asset,
 FOREIGN KEY(run_id,station_key) REFERENCES foundation.station_record,
 CHECK(last_raw_clock IS NULL OR (first_raw_clock IS NOT NULL AND last_raw_clock>=first_raw_clock))
);
CREATE TABLE IF NOT EXISTS foundation.qc_review_interval (
 run_id text NOT NULL, interval_id text NOT NULL, asset_id text NOT NULL, station_key text NOT NULL,
 item_code_raw text NOT NULL, first_source_record bigint NOT NULL, last_source_record bigint NOT NULL,
 first_raw_clock timestamp NOT NULL, last_raw_clock timestamp NOT NULL,
 guide_document_id text NOT NULL, review_status text NOT NULL, confirmed_causal_evidence jsonb NOT NULL DEFAULT '[]',
 PRIMARY KEY(run_id,interval_id), FOREIGN KEY(run_id,asset_id) REFERENCES foundation.source_asset,
 FOREIGN KEY(run_id,station_key) REFERENCES foundation.station_record,
 FOREIGN KEY(run_id,guide_document_id) REFERENCES foundation.document_record,
 CHECK(last_raw_clock>=first_raw_clock), CHECK(last_source_record>=first_source_record)
);
CREATE TABLE IF NOT EXISTS foundation.reference_definition (
 run_id text NOT NULL REFERENCES foundation.ingestion_run, reference_id text NOT NULL,
 document_id text NOT NULL, reference_type text NOT NULL, source_locator text NOT NULL,
 definition jsonb NOT NULL, source_application_status text NOT NULL DEFAULT 'HISTORICAL_BINDING_UNVERIFIED',
 PRIMARY KEY(run_id,reference_id), FOREIGN KEY(run_id,document_id) REFERENCES foundation.document_record
);
CREATE INDEX IF NOT EXISTS foundation_asset_status ON foundation.source_asset(run_id,processing_status);
CREATE INDEX IF NOT EXISTS foundation_contract_station_item ON foundation.channel_contract(run_id,station_key,item_code_raw);
CREATE INDEX IF NOT EXISTS foundation_equipment_station ON foundation.equipment_record(run_id,station_key,equipment_code);
CREATE INDEX IF NOT EXISTS foundation_artifact_source ON foundation.parquet_artifact(run_id,asset_id);
CREATE INDEX IF NOT EXISTS foundation_coverage_lookup ON foundation.observation_coverage(run_id,station_key,item_code_raw,first_raw_clock,last_raw_clock);
CREATE INDEX IF NOT EXISTS foundation_event_station_date ON foundation.operation_event(run_id,station_id_claim,event_date);
CREATE INDEX IF NOT EXISTS foundation_qc_station_time ON foundation.qc_review_interval(run_id,station_key,first_raw_clock,last_raw_clock);

-- 最新 스냅샷만 명시적으로 선택한다. 과거 스냅샷을 합쳐 중복 건수를 만들지 않는다.
CREATE OR REPLACE VIEW foundation.v_current_run AS
 SELECT run_id FROM foundation.ingestion_run WHERE status='COMPLETE' ORDER BY completed_at DESC,run_id DESC LIMIT 1;
CREATE OR REPLACE VIEW foundation.v_series_judgement AS
 SELECT c.run_id,s.namespace,s.station_id_raw,s.station_name_raw,c.asset_id,a.source_path,c.item_code_raw,c.depth_identity,
 min(c.first_raw_clock) AS first_raw_clock,max(c.last_raw_clock) AS last_raw_clock,
 sum(c.row_count) AS profiled_item_rows,count(*) AS monthly_groups,
 bool_or(c.physical_sensor_id IS NOT NULL) AS any_sensor_id_present,
 'SOURCE_CLOCK_ONLY_NOT_APPROVED_USABLE_PERIOD'::text AS temporal_judgement,
 'HOLD_UNIT_TIMEZONE_SENSOR_QC_CONTRACT'::text AS usability
 FROM foundation.observation_coverage c JOIN foundation.v_current_run v USING(run_id)
 JOIN foundation.station_record s USING(run_id,station_key) JOIN foundation.source_asset a USING(run_id,asset_id)
 GROUP BY c.run_id,s.namespace,s.station_id_raw,s.station_name_raw,c.asset_id,a.source_path,c.item_code_raw,c.depth_identity;
CREATE OR REPLACE VIEW foundation.v_operation_calendar_candidates AS
 SELECT c.run_id,c.coverage_id,c.asset_id,s.station_id_raw,c.item_code_raw,c.first_raw_clock,c.last_raw_clock,
 e.event_id,e.event_date,e.description,e.document_id,e.source_locator,
 'RAW_STATION_TEXT_AND_CALENDAR_OVERLAP_ONLY'::text AS match_basis,
 false AS sensor_match_approved,false AS timezone_match_approved,false AS causal_link_approved
 FROM foundation.observation_coverage c JOIN foundation.v_current_run v USING(run_id)
 JOIN foundation.station_record s USING(run_id,station_key)
 JOIN foundation.operation_event e ON e.run_id=c.run_id AND e.station_id_claim=s.station_id_raw
 AND e.event_date BETWEEN c.first_raw_clock::date AND c.last_raw_clock::date;
CREATE OR REPLACE VIEW foundation.v_qc_evidence_judgement AS
 SELECT q.run_id,q.interval_id,s.station_id_raw,q.item_code_raw,q.first_raw_clock,q.last_raw_clock,
 count(e.event_id) AS raw_calendar_event_candidates,
 'NO_CONFIRMED_SENSOR_TIMEZONE_CAUSAL_BINDING'::text AS evidence_judgement
 FROM foundation.qc_review_interval q JOIN foundation.v_current_run v USING(run_id)
 JOIN foundation.station_record s USING(run_id,station_key)
 LEFT JOIN foundation.operation_event e ON e.run_id=q.run_id AND e.station_id_claim=s.station_id_raw
 AND e.event_date BETWEEN q.first_raw_clock::date AND q.last_raw_clock::date
 GROUP BY q.run_id,q.interval_id,s.station_id_raw,q.item_code_raw,q.first_raw_clock,q.last_raw_clock;
