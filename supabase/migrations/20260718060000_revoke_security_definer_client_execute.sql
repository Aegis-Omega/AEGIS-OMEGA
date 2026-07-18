-- AEGIS-Ω · least-privilege repair for privileged RPC functions
-- EPISTEMIC TIER: T0 (catalog-verified privilege correction)
--
-- The original migrations revoked EXECUTE from PUBLIC, but the live project also
-- carried explicit EXECUTE grants for anon and authenticated. PostgreSQL keeps
-- those explicit grants until they are revoked individually.
--
-- Both runtime callers use SUPABASE_SERVICE_ROLE_KEY, so client-role EXECUTE is
-- unnecessary and exposes SECURITY DEFINER mutations through PostgREST RPC.

BEGIN;

REVOKE ALL PRIVILEGES
  ON FUNCTION public.verify_and_increment_api_key(text)
  FROM PUBLIC, anon, authenticated;

REVOKE ALL PRIVILEGES
  ON FUNCTION public.award_grace(uuid, text, text, integer, numeric)
  FROM PUBLIC, anon, authenticated;

GRANT EXECUTE
  ON FUNCTION public.verify_and_increment_api_key(text)
  TO service_role;

GRANT EXECUTE
  ON FUNCTION public.award_grace(uuid, text, text, integer, numeric)
  TO service_role;

DO $$
BEGIN
  IF has_function_privilege(
    'anon',
    'public.verify_and_increment_api_key(text)'::regprocedure,
    'EXECUTE'
  ) OR has_function_privilege(
    'authenticated',
    'public.verify_and_increment_api_key(text)'::regprocedure,
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'verify_and_increment_api_key remains executable by a client role';
  END IF;

  IF has_function_privilege(
    'anon',
    'public.award_grace(uuid,text,text,integer,numeric)'::regprocedure,
    'EXECUTE'
  ) OR has_function_privilege(
    'authenticated',
    'public.award_grace(uuid,text,text,integer,numeric)'::regprocedure,
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'award_grace remains executable by a client role';
  END IF;

  IF NOT has_function_privilege(
    'service_role',
    'public.verify_and_increment_api_key(text)'::regprocedure,
    'EXECUTE'
  ) OR NOT has_function_privilege(
    'service_role',
    'public.award_grace(uuid,text,text,integer,numeric)'::regprocedure,
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'service_role lost required RPC execution privilege';
  END IF;
END
$$;

COMMIT;
