-- Swarm memory table — stores completed collaboration artifacts so the
-- 39-department swarm can retrieve prior insights on future calls for the
-- same objective (evolutionary corpus building).
--
-- Lookup key: (objective_hash, mode) — indexed for fast retrieval.
-- Retention: no TTL enforced at DB level; prune via scheduled job if needed.

CREATE TABLE IF NOT EXISTS swarm_memory (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  objective_hash        text        NOT NULL,   -- SHA-256 of normalized objective
  mode                  text        NOT NULL,
  customer_email        text        NOT NULL,
  artifacts             jsonb       NOT NULL,   -- [{role, output}]
  projection            jsonb       NOT NULL,   -- {first_year_arr_usd, tier, governed_note}
  constitutional_verdict text       NOT NULL,   -- APPROVED | FLAG | QUARANTINE
  created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS swarm_memory_hash_mode_idx
  ON swarm_memory(objective_hash, mode);

CREATE INDEX IF NOT EXISTS swarm_memory_email_idx
  ON swarm_memory(customer_email);

-- Service role can read/write; anon role has no access (memory is private)
GRANT SELECT, INSERT ON swarm_memory TO service_role;
