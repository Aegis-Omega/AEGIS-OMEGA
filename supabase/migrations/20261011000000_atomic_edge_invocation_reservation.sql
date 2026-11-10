-- AEGIS Ω Worker: atomically reserve one invocation BEFORE provider spend.
-- Required by worker-src/invocationGate.ts. Safe default: absent RPC -> 503.
-- Reservations count on admission even if a later provider call fails.
-- This is conservative budget protection; no implicit refund or free-success promise.

CREATE OR REPLACE FUNCTION public.reserve_aegis_edge_collaboration(p_key_hash text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id uuid;
BEGIN
  IF p_key_hash IS NULL OR p_key_hash !~ '^[0-9a-f]{64}$' THEN
    RETURN false;
  END IF;

  UPDATE public.api_key_store
     SET usage_count = usage_count + 1
   WHERE key_hash = p_key_hash
     AND revoked IS FALSE
     AND usage_limit > 0
     AND usage_count >= 0
     AND usage_count < usage_limit
   RETURNING id INTO v_id;

  RETURN v_id IS NOT NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.reserve_aegis_edge_collaboration(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.reserve_aegis_edge_collaboration(text) FROM anon;
REVOKE ALL ON FUNCTION public.reserve_aegis_edge_collaboration(text) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.reserve_aegis_edge_collaboration(text) TO service_role;

COMMENT ON FUNCTION public.reserve_aegis_edge_collaboration(text) IS
  'Atomically consumes one AEGIS Worker request reservation for a valid non-revoked key with remaining quota; returns only a boolean. Service role only.';