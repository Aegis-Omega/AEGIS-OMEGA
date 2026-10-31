-- ISOLATED TEST FIXTURE ONLY. Not a Supabase migration or production DDL.
-- Fail closed if manually invoked against ANY database other than dedicated CI.
BEGIN;
DO $guard$
BEGIN
  IF current_database() <> 'aegis_budget_test' THEN
    RAISE EXCEPTION 'DENIED: generation checkpoint fixture is test-only';
  END IF;
END
$guard$;

CREATE TABLE IF NOT EXISTS public.aegis_test_generation_floor_v1 (
  policy_id text PRIMARY KEY CHECK (policy_id ~ '^[a-zA-Z0-9._:-]{1,128}$'),
  generation text NOT NULL CHECK (generation ~ '^(0|[1-9][0-9]*)$')
);
REVOKE ALL ON TABLE public.aegis_test_generation_floor_v1
  FROM PUBLIC, anon, authenticated;
GRANT SELECT, UPDATE ON TABLE public.aegis_test_generation_floor_v1 TO service_role;
REVOKE INSERT, DELETE, TRUNCATE ON TABLE public.aegis_test_generation_floor_v1
  FROM service_role;

CREATE OR REPLACE FUNCTION public.aegis_test_observe_advance_v1(
  p_policy_id text, p_generation text
)
RETURNS TABLE(outcome text, persisted_generation text)
LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
AS $checkpoint$
DECLARE
  prior text;
BEGIN
  -- Reject noncanonical generations before read/write, without raising.
  IF p_generation IS NULL
    OR p_generation !~ '^(0|[1-9][0-9]*)$' THEN
    RETURN QUERY SELECT 'UNAVAILABLE'::text, NULL::text;
    RETURN;
  END IF;

  -- A mandatory row lock serializes increments for the same trusted policy.
  -- No row => HOLD. Do NOT bootstrap from user-supplied generation.
  SELECT g.generation INTO prior
    FROM public.aegis_test_generation_floor_v1 AS g
    WHERE g.policy_id = p_policy_id
    FOR UPDATE;
  IF NOT FOUND THEN
    RETURN QUERY SELECT 'UNAVAILABLE'::text, NULL::text;
    RETURN;
  END IF;

  -- Decimal strings: length then bytewise C collation, no numeric overflow.
  IF length(p_generation) < length(prior)
    OR (length(p_generation) = length(prior)
      AND (p_generation COLLATE "C") < (prior COLLATE "C")) THEN
    RETURN QUERY SELECT 'ROLLBACK'::text, NULL::text;
    RETURN;
  END IF;
  UPDATE public.aegis_test_generation_floor_v1 AS g
    SET generation = p_generation WHERE g.policy_id = p_policy_id;
  RETURN QUERY SELECT 'ACCEPTED'::text, p_generation::text;
END;
$checkpoint$;

REVOKE ALL ON FUNCTION public.aegis_test_observe_advance_v1(text,text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.aegis_test_observe_advance_v1(text,text)
  TO service_role;
COMMIT;
