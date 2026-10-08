-- Explicit additive PostgreSQL migration. No accounts, approvals or workflow rows are created.
BEGIN;
CREATE TABLE IF NOT EXISTS agent_workflow_run (
 workflow_id VARCHAR(36) PRIMARY KEY, request_key VARCHAR(128) NOT NULL UNIQUE,
 requested_by VARCHAR NOT NULL, input_sha256 VARCHAR(64) NOT NULL,
 recommendation_sha256 VARCHAR(64) NOT NULL, payload JSON NOT NULL,
 recommendation JSON NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
 revision INTEGER NOT NULL DEFAULT 0, approval_history_id INTEGER REFERENCES approval_history(id),
 result JSON, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT ck_agent_workflow_status CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED','RESUMING','COMPLETED'))
);
CREATE TABLE IF NOT EXISTS agent_workflow_transition (
 id SERIAL PRIMARY KEY, workflow_id VARCHAR(36) NOT NULL REFERENCES agent_workflow_run(workflow_id),
 request_key VARCHAR(128) NOT NULL, revision INTEGER NOT NULL,
 actor_id VARCHAR NOT NULL, actor_role VARCHAR(20) NOT NULL,
 from_status VARCHAR(20) NOT NULL, to_status VARCHAR(20) NOT NULL, action VARCHAR(20) NOT NULL,
 request_sha256 VARCHAR(64) NOT NULL, recommendation_sha256 VARCHAR(64) NOT NULL,
 approval_history_id INTEGER REFERENCES approval_history(id), record JSON NOT NULL,
 record_sha256 VARCHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT uq_workflow_transition_request UNIQUE(workflow_id,request_key),
 CONSTRAINT uq_workflow_transition_revision UNIQUE(workflow_id,revision)
);
CREATE INDEX IF NOT EXISTS ix_agent_workflow_transition_workflow_id ON agent_workflow_transition(workflow_id);
COMMIT;
