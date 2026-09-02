-- AEGIS Ω · Cognitive Recovery Replay State V1
--
-- Durable one-shot replay/consumption state for canonical cognitive recovery.
-- The database owns atomic reservation/consumption. Candidate-controlled
-- verification may observe this state but cannot manufacture or mutate it.
--
-- State machine:
--   UNUSED --reserve(expected generation)--> RESERVED
--   RESERVED --consume(exact reservation, generation)--> CONSUMED
--   RESERVED --unknown(exact reservation, generation)--> UNKNOWN
--   CONSUMED and UNKNOWN are terminal for normal recovery operations.
--
-- All state transitions use one UPDATE ... WHERE ... RETURNING statement so
-- concurrent callers race inside PostgreSQL rather than in application code.

CREATE TABLE IF NOT EXISTS public.cognitive_recovery_replay_state (
  request_digest            text        PRIMARY KEY
    CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  repository_id             text        NOT NULL,
  candidate_sha             text        NOT NULL
    CHECK (candidate_sha ~ '^[0-9a-f]{40}$'),
  operator_approval_digest  text        NOT NULL
    CHECK (operator_approval_digest ~ '^[0-9a-f]{64}$'),
  state                     text        NOT NULL DEFAULT 'UNUSED'
    CHECK (state IN ('UNUSED', 'RESERVED', 'CONSUMED', 'UNKNOWN')),
  generation                bigint      NOT NULL DEFAULT 0
    CHECK (generation >= 0),
  reservation_id            uuid,
  reserved_at               timestamptz,
  consumed_at               timestamptz,
  created_at                 timestamptz NOT NULL DEFAULT now(),
  updated_at                 timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT cognitive_recovery_replay_state_shape CHECK (
    (state = 'UNUSED'
      AND reservation_id IS NULL
      AND reserved_at IS NULL
      AND consumed_at IS NULL)
    OR
    (state = 'RESERVED'
      AND reservation_id IS NOT NULL
      AND reserved_at IS NOT NULL
      AND consumed_at IS NULL)
    OR
    (state = 'CONSUMED'
      AND reservation_id IS NOT NULL
      AND reserved_at IS NOT NULL
      AND consumed_at IS NOT NULL)
    OR
    (state = 'UNKNOWN'
      AND reservation_id IS NOT NULL
      AND reserved_at IS NOT NULL
      AND consumed_at IS NULL)
  )
);

ALTER TABLE public.cognitive_recovery_replay_state ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.cognitive_recovery_replay_state FROM PUBLIC;

-- Idempotently establish one immutable identity binding for a request digest.
-- A conflicting reuse of the same digest with another repository/candidate/
-- approval returns zero rows and never rewrites the existing binding.
CREATE OR REPLACE FUNCTION public.initialize_cognitive_recovery_replay(
  p_request_digest text,
  p_repository_id text,
  p_candidate_sha text,
  p_operator_approval_digest text
)
RETURNS TABLE(
  request_digest text,
  state text,
  generation bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.cognitive_recovery_replay_state AS r (
    request_digest,
    repository_id,
    candidate_sha,
    operator_approval_digest,
    state,
    generation
  )
  VALUES (
    p_request_digest,
    p_repository_id,
    p_candidate_sha,
    p_operator_approval_digest,
    'UNUSED',
    0
  )
  ON CONFLICT ON CONSTRAINT cognitive_recovery_replay_state_pkey DO NOTHING;

  RETURN QUERY
  SELECT r.request_digest, r.state, r.generation
  FROM public.cognitive_recovery_replay_state AS r
  WHERE r.request_digest = p_request_digest
    AND r.repository_id = p_repository_id
    AND r.candidate_sha = p_candidate_sha
    AND r.operator_approval_digest = p_operator_approval_digest;
END;
$$;

-- Atomic compare-and-swap reservation. Exactly one concurrent caller can move
-- a given request from UNUSED at the expected generation to RESERVED.
CREATE OR REPLACE FUNCTION public.reserve_cognitive_recovery_replay(
  p_request_digest text,
  p_expected_generation bigint
)
RETURNS TABLE(
  request_digest text,
  state text,
  generation bigint,
  reservation_id uuid
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  UPDATE public.cognitive_recovery_replay_state AS r
  SET state = 'RESERVED',
      generation = r.generation + 1,
      reservation_id = gen_random_uuid(),
      reserved_at = now(),
      consumed_at = NULL,
      updated_at = now()
  WHERE r.request_digest = p_request_digest
    AND r.state = 'UNUSED'
    AND r.generation = p_expected_generation
  RETURNING r.request_digest, r.state, r.generation, r.reservation_id;
END;
$$;

-- Finalize only the exact live reservation at the exact generation.
CREATE OR REPLACE FUNCTION public.consume_cognitive_recovery_replay(
  p_request_digest text,
  p_reservation_id uuid,
  p_expected_generation bigint
)
RETURNS TABLE(
  request_digest text,
  state text,
  generation bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  UPDATE public.cognitive_recovery_replay_state AS r
  SET state = 'CONSUMED',
      generation = r.generation + 1,
      consumed_at = now(),
      updated_at = now()
  WHERE r.request_digest = p_request_digest
    AND r.state = 'RESERVED'
    AND r.reservation_id = p_reservation_id
    AND r.generation = p_expected_generation
  RETURNING r.request_digest, r.state, r.generation;
END;
$$;

-- A dispatch whose external outcome cannot be reconciled is quarantined as
-- UNKNOWN. There is intentionally no normal transition from UNKNOWN to UNUSED.
CREATE OR REPLACE FUNCTION public.mark_cognitive_recovery_replay_unknown(
  p_request_digest text,
  p_reservation_id uuid,
  p_expected_generation bigint
)
RETURNS TABLE(
  request_digest text,
  state text,
  generation bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  UPDATE public.cognitive_recovery_replay_state AS r
  SET state = 'UNKNOWN',
      generation = r.generation + 1,
      consumed_at = NULL,
      updated_at = now()
  WHERE r.request_digest = p_request_digest
    AND r.state = 'RESERVED'
    AND r.reservation_id = p_reservation_id
    AND r.generation = p_expected_generation
  RETURNING r.request_digest, r.state, r.generation;
END;
$$;

REVOKE ALL ON FUNCTION public.initialize_cognitive_recovery_replay(text, text, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.reserve_cognitive_recovery_replay(text, bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.consume_cognitive_recovery_replay(text, uuid, bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.mark_cognitive_recovery_replay_unknown(text, uuid, bigint) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.initialize_cognitive_recovery_replay(text, text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.reserve_cognitive_recovery_replay(text, bigint) TO service_role;
GRANT EXECUTE ON FUNCTION public.consume_cognitive_recovery_replay(text, uuid, bigint) TO service_role;
GRANT EXECUTE ON FUNCTION public.mark_cognitive_recovery_replay_unknown(text, uuid, bigint) TO service_role;
