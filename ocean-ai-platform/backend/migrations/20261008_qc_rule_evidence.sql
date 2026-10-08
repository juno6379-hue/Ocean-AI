-- PostgreSQL, additive migration. Apply explicitly before the new QC API.
-- No legacy verdict is backfilled as evaluated or approved.
BEGIN;
ALTER TABLE qc_rule_result
    ADD COLUMN IF NOT EXISTS evaluation_status VARCHAR(32),
    ADD COLUMN IF NOT EXISTS result_reason TEXT,
    ADD COLUMN IF NOT EXISTS provenance_json JSON;
COMMIT;
