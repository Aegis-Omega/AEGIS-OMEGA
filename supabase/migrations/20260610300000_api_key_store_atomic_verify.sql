-- AEGIS-Ω · api_key_store — table + atomic verify-and-increment RPC
-- EPISTEMIC TIER: T0 (idempotent DDL + atomic UPDATE RETURNING)
--
-- Addresses:
--   1. api_key_store table (idempotent CREATE TABLE IF NOT EXISTS).
--   2. verify_and_increment_api_key() RPC — replaces the TOCTOU-prone
--      read-then-PATCH pattern in verify_api_key() with a single atomic
--      UPDATE … RETURNING that only succeeds when the row exists, is not
--      revoked, and has remaining quota. Under concurrent requests the DB
--      serialises the UPDATE; the first caller decrements the counter, any
--      racing caller that would push usage_count past usage_limit sees an
--      empty result set and is correctly rejected.

-- ── api_key_store ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS api_key_store (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_email  text        NOT NULL,
  tier            text        NOT NULL CHECK (tier IN ('explorer', 'operator', 'sovereign')),
  key_hash        text        NOT NULL UNIQUE,  -- SHA-256(raw_key) hex, never store plaintext
  usage_count     int         NOT NULL DEFAULT 0,
  usage_limit     int         NOT NULL DEFAULT 10,  -- explorer:10, operator:500, sovereign:1000000
  revoked         bool        NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_key_store_hash_idx ON api_key_store(key_hash);

-- ── verify_and_increment_api_key ──────────────────────────────────────────────
-- Atomically check validity + quota, then increment usage_count in one
-- UPDATE … RETURNING. Called via POST /rest/v1/rpc/verify_and_increment_api_key.
--
-- Returns one row on success; zero rows when the key is unknown, revoked, or
-- exhausted. The caller treats zero rows as rejection (no secondary read needed).
--
-- SECURITY DEFINER runs as the table owner so the REST caller (anon/service role)
-- does not need direct table UPDATE permission.

CREATE OR REPLACE FUNCTION verify_and_increment_api_key(p_key_hash text)
RETURNS TABLE(
  customer_email text,
  tier           text,
  usage_count    int,
  usage_limit    int
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  UPDATE api_key_store AS k
  SET    usage_count = k.usage_count + 1
  WHERE  k.key_hash    = p_key_hash
    AND  k.revoked     = false
    AND  k.usage_count < k.usage_limit
  RETURNING
    k.customer_email,
    k.tier,
    k.usage_count,   -- post-increment value
    k.usage_limit;
END;
$$;

-- Revoke broad access; only service_role may call this function.
REVOKE ALL ON FUNCTION verify_and_increment_api_key(text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION verify_and_increment_api_key(text) TO service_role;
