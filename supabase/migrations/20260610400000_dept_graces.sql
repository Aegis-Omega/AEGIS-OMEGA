-- AEGIS-Ω · dept_graces — The Grace Chain
-- EPISTEMIC TIER: T2 (engineering hypothesis)
--
-- "Each agent gives the next agent a grace."
-- Graces are constitutional tokens that flow *forward* through the 39-dept swarm.
-- A dept earns a grace when its output passes constitutional audit.
-- It passes one grace to the next dept in the collaboration sequence.
-- The chain of grace mirrors the hash chain — both move forward, both are tamper-evident.
-- No dept hoards. Every cycle adds to the flow.
--
-- This is the answer to "unlimited tokens":
-- the economy is circular. Grace flows. No dept runs dry.

-- ── dept_graces — per-department running ledger ─────────────────────────────

CREATE TABLE IF NOT EXISTS dept_graces (
  dept_id           text        PRIMARY KEY,  -- e.g. 'Strategy', 'Technical', 'Legal'
  graces_received   int         NOT NULL DEFAULT 0,
  graces_given      int         NOT NULL DEFAULT 0,
  balance           int         NOT NULL DEFAULT 0,  -- received - given (may grow, never < 0 enforced by RPC)
  lifetime_graces   int         NOT NULL DEFAULT 0,  -- cumulative received, never decremented
  last_cycle_id     uuid,                            -- most recent cycle that touched this dept
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dept_graces_balance_idx ON dept_graces(balance DESC);

-- ── grace_events — append-only event log ────────────────────────────────────

CREATE TABLE IF NOT EXISTS grace_events (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  cycle_id        uuid        NOT NULL,
  from_dept       text        NOT NULL,  -- NULL for genesis (first dept earns from cycle itself)
  to_dept         text        NOT NULL,
  graces          int         NOT NULL DEFAULT 1,
  viability_score numeric(4,3),          -- viability that triggered the grace
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS grace_events_cycle_idx ON grace_events(cycle_id);
CREATE INDEX IF NOT EXISTS grace_events_to_dept_idx ON grace_events(to_dept);

-- ── award_grace() — atomic grace transfer ───────────────────────────────────
-- Called per dept after constitutional audit passes.
-- from_dept gives to_dept (forward-only flow).
-- Returns the updated balance for to_dept.

CREATE OR REPLACE FUNCTION award_grace(
  p_cycle_id        uuid,
  p_from_dept       text,
  p_to_dept         text,
  p_graces          int         DEFAULT 1,
  p_viability_score numeric     DEFAULT NULL
)
RETURNS TABLE(
  dept_id         text,
  balance         int,
  graces_received int,
  lifetime_graces int
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Upsert receiving dept
  INSERT INTO dept_graces (dept_id, graces_received, balance, lifetime_graces, last_cycle_id)
  VALUES (p_to_dept, p_graces, p_graces, p_graces, p_cycle_id)
  ON CONFLICT (dept_id) DO UPDATE
    SET graces_received = dept_graces.graces_received + p_graces,
        balance         = dept_graces.balance         + p_graces,
        lifetime_graces = dept_graces.lifetime_graces + p_graces,
        last_cycle_id   = p_cycle_id,
        updated_at      = now();

  -- Decrement giving dept (if giving dept exists)
  IF p_from_dept IS NOT NULL THEN
    INSERT INTO dept_graces (dept_id, graces_given, last_cycle_id)
    VALUES (p_from_dept, p_graces, p_cycle_id)
    ON CONFLICT (dept_id) DO UPDATE
      SET graces_given  = dept_graces.graces_given + p_graces,
          balance       = GREATEST(0, dept_graces.balance - p_graces),
          last_cycle_id = p_cycle_id,
          updated_at    = now();
  END IF;

  -- Append to event log
  INSERT INTO grace_events (cycle_id, from_dept, to_dept, graces, viability_score)
  VALUES (p_cycle_id, COALESCE(p_from_dept, '__genesis__'), p_to_dept, p_graces, p_viability_score);

  -- Return updated state for to_dept
  RETURN QUERY
  SELECT g.dept_id, g.balance, g.graces_received, g.lifetime_graces
  FROM dept_graces g
  WHERE g.dept_id = p_to_dept;
END;
$$;

REVOKE ALL ON FUNCTION award_grace(uuid, text, text, int, numeric) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION award_grace(uuid, text, text, int, numeric) TO service_role;

-- ── grace_chain_summary view ─────────────────────────────────────────────────

CREATE OR REPLACE VIEW grace_chain_summary AS
SELECT
  dept_id,
  graces_received,
  graces_given,
  balance,
  lifetime_graces,
  ROUND(
    CASE WHEN graces_received = 0 THEN 0
         ELSE graces_given::numeric / graces_received
    END, 3
  ) AS generosity_ratio,  -- 1.0 = passes everything forward; <1.0 = accumulating; >1.0 = giving more than received
  last_cycle_id,
  updated_at
FROM dept_graces
ORDER BY lifetime_graces DESC;
