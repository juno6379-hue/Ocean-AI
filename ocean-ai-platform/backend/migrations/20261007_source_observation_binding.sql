-- Explicit parent-reviewed migration; no auto-create or changes to legacy data.
BEGIN;
CREATE TABLE IF NOT EXISTS source_observation_binding (
 observation_id varchar(128) PRIMARY KEY REFERENCES observation_standard(observation_id),
 contract_id varchar(128) NOT NULL REFERENCES source_contract_packets(contract_id),
 approval_history_id integer NOT NULL REFERENCES approval_history(id),
 receipt_sha256 varchar(64) NOT NULL,
 source_sha256 varchar(64) NOT NULL,
 parquet_sha256 varchar(64) NOT NULL,
 source_row_locator text NOT NULL,
 exact_scope_key varchar(64) NOT NULL,
 payload json NOT NULL,
 created_by text NOT NULL,
 created_at timestamp DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT uq_source_observation_row UNIQUE(parquet_sha256,source_row_locator)
);
CREATE INDEX IF NOT EXISTS ix_source_observation_binding_exact_scope_key ON source_observation_binding(exact_scope_key);
COMMIT;
