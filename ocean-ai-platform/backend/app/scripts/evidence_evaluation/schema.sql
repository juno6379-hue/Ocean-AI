-- 승인 원장을 대체하지 않는, 재현 가능한 문서 기간/데이터셋 평가 준비 스냅샷.
CREATE SCHEMA IF NOT EXISTS evidence_eval;
CREATE TABLE IF NOT EXISTS evidence_eval.run (
 run_id text PRIMARY KEY, foundation_run text NOT NULL REFERENCES foundation.ingestion_run,
 fingerprint text NOT NULL, manifest jsonb NOT NULL, completed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS evidence_eval.assertion (
 run_id text NOT NULL REFERENCES evidence_eval.run, assertion_id text NOT NULL,
 foundation_run text NOT NULL, document_id text, station_key text,
 kind text NOT NULL, payload jsonb NOT NULL,
 status text NOT NULL DEFAULT 'UNREVIEWED' CHECK(status='UNREVIEWED'),
 PRIMARY KEY(run_id,assertion_id),
 FOREIGN KEY(foundation_run,document_id) REFERENCES foundation.document_record,
 FOREIGN KEY(foundation_run,station_key) REFERENCES foundation.station_record,
 CHECK(document_id IS NOT NULL OR station_key IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS evidence_eval.period_candidate (
 run_id text NOT NULL REFERENCES evidence_eval.run, period_id text NOT NULL,
 period_kind text NOT NULL CHECK(period_kind IN ('STATION_OPERATION','ITEM_OPERATION','SENSOR_DEPLOYMENT')),
 start_assertion text NOT NULL, end_assertion text,
 payload jsonb NOT NULL, status text NOT NULL DEFAULT 'CANDIDATE' CHECK(status='CANDIDATE'),
 PRIMARY KEY(run_id,period_id),
 FOREIGN KEY(run_id,start_assertion) REFERENCES evidence_eval.assertion,
 FOREIGN KEY(run_id,end_assertion) REFERENCES evidence_eval.assertion
);
CREATE TABLE IF NOT EXISTS evidence_eval.coverage_review (
 run_id text NOT NULL REFERENCES evidence_eval.run, foundation_run text NOT NULL,
 coverage_id text NOT NULL, payload jsonb NOT NULL,
 status text NOT NULL CHECK(status='BLOCKED'),
 PRIMARY KEY(run_id,coverage_id),
 FOREIGN KEY(foundation_run,coverage_id) REFERENCES foundation.observation_coverage
);
CREATE TABLE IF NOT EXISTS evidence_eval.temporal_candidate (
 run_id text NOT NULL, period_id text NOT NULL, foundation_run text NOT NULL,
 coverage_id text NOT NULL, relation text NOT NULL, item_compatible boolean NOT NULL,
 approved boolean NOT NULL DEFAULT false CHECK(approved=false), payload jsonb NOT NULL,
 PRIMARY KEY(run_id,period_id,coverage_id),
 FOREIGN KEY(run_id,period_id) REFERENCES evidence_eval.period_candidate,
 FOREIGN KEY(foundation_run,coverage_id) REFERENCES foundation.observation_coverage
);
CREATE TABLE IF NOT EXISTS evidence_eval.dataset_snapshot (
 run_id text NOT NULL REFERENCES evidence_eval.run, task text NOT NULL,
 dataset_hash text NOT NULL, status text NOT NULL CHECK(status='BLOCKED'),
 eligible_members bigint NOT NULL CHECK(eligible_members=0), payload jsonb NOT NULL,
 PRIMARY KEY(run_id,task)
);
CREATE TABLE IF NOT EXISTS evidence_eval.benchmark_protocol (
 run_id text NOT NULL REFERENCES evidence_eval.run, task text NOT NULL,
 protocol_hash text NOT NULL, payload jsonb NOT NULL,
 PRIMARY KEY(run_id,task)
);
CREATE INDEX IF NOT EXISTS assertion_document ON evidence_eval.assertion(foundation_run,document_id);
CREATE INDEX IF NOT EXISTS coverage_review_source ON evidence_eval.coverage_review(foundation_run,coverage_id);
CREATE OR REPLACE VIEW evidence_eval.v_latest_run AS
 SELECT run_id FROM evidence_eval.run ORDER BY completed_at DESC, run_id DESC LIMIT 1;
CREATE OR REPLACE VIEW evidence_eval.v_dataset_readiness AS
 SELECT d.* FROM evidence_eval.dataset_snapshot d JOIN evidence_eval.v_latest_run USING(run_id);
CREATE OR REPLACE VIEW evidence_eval.v_temporal_review AS
 SELECT t.*,p.period_kind,s.station_id_raw,c.item_code_raw,c.first_raw_clock,c.last_raw_clock
 FROM evidence_eval.temporal_candidate t JOIN evidence_eval.v_latest_run USING(run_id)
 JOIN evidence_eval.period_candidate p USING(run_id,period_id)
 JOIN foundation.observation_coverage c ON c.run_id=t.foundation_run AND c.coverage_id=t.coverage_id
 JOIN foundation.station_record s ON s.run_id=c.run_id AND s.station_key=c.station_key;
