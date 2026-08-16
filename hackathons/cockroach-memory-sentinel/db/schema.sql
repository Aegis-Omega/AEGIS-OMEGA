-- AEGIS Memory Sentinel — CockroachDB persistent memory schema
-- Hackathon-specific work. Requires CockroachDB 25.4+ for GA vector indexing.
-- No live deployment claim is implied by this file alone.

CREATE TABLE IF NOT EXISTS mcm_node_state (
  node_id STRING PRIMARY KEY,
  sequence INT8 NOT NULL,
  confidence_bps INT4 NOT NULL CHECK (confidence_bps BETWEEN 0 AND 10000),
  evidence_freshness_bps INT4 NOT NULL CHECK (evidence_freshness_bps BETWEEN 0 AND 10000),
  load_bps INT4 NOT NULL CHECK (load_bps BETWEEN 0 AND 10000),
  reliability_bps INT4 NOT NULL CHECK (reliability_bps BETWEEN 0 AND 10000),
  contradiction_count INT4 NOT NULL CHECK (contradiction_count >= 0),
  observed_authority_envelope STRING NULL,
  state_digest STRING NOT NULL,
  policy_digest STRING NOT NULL,
  authority_epoch INT8 NOT NULL,
  previous_receipt_hash STRING NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcm_evidence_memory (
  memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  node_id STRING NOT NULL REFERENCES mcm_node_state(node_id),
  memory_kind STRING NOT NULL,
  evidence_text STRING NOT NULL,
  evidence_digest STRING NOT NULL UNIQUE,
  source_ref STRING NULL,
  epistemic_tier STRING NOT NULL,
  freshness_bps INT4 NOT NULL CHECK (freshness_bps BETWEEN 0 AND 10000),
  embedding VECTOR(1536) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS mcm_evidence_node_created_idx
  ON mcm_evidence_memory (node_id, created_at DESC);

CREATE VECTOR INDEX IF NOT EXISTS mcm_evidence_vector_idx
  ON mcm_evidence_memory (epistemic_tier, embedding);

CREATE TABLE IF NOT EXISTS mcm_action_receipt (
  receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id STRING NOT NULL,
  action_digest STRING NOT NULL,
  observed_state_digest STRING NOT NULL,
  admitted_state_digest STRING NOT NULL,
  observed_policy_digest STRING NOT NULL,
  admitted_policy_digest STRING NOT NULL,
  observed_authority_epoch INT8 NOT NULL,
  admitted_authority_epoch INT8 NOT NULL,
  verdict STRING NOT NULL CHECK (verdict IN ('ALLOW', 'DENY')),
  reasons STRING[] NOT NULL,
  previous_receipt_hash STRING NULL,
  receipt_hash STRING NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (request_id, action_digest)
);

CREATE INDEX IF NOT EXISTS mcm_receipt_request_idx
  ON mcm_action_receipt (request_id, created_at DESC);

-- MCM observations are evidence only. No table column represents authority
-- grants or authority escalation; only observed/admitted envelopes are stored.
