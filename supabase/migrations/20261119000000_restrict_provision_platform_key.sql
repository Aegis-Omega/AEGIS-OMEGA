-- Key provisioning is a server-only operation. PostgreSQL grants function
-- execution to PUBLIC by default, so an explicit service_role grant alone does
-- not prevent anon or authenticated PostgREST callers from invoking the RPC.

BEGIN;

REVOKE ALL ON FUNCTION public.provision_platform_key(text, text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.provision_platform_key(text, text, uuid) FROM anon;
REVOKE ALL ON FUNCTION public.provision_platform_key(text, text, uuid) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.provision_platform_key(text, text, uuid) TO service_role;

DO $$
BEGIN
  IF has_function_privilege(
    'anon',
    'public.provision_platform_key(text,text,uuid)',
    'EXECUTE'
  ) OR has_function_privilege(
    'authenticated',
    'public.provision_platform_key(text,text,uuid)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'provision_platform_key must not be executable by Supabase client roles';
  END IF;

  IF NOT has_function_privilege(
    'service_role',
    'public.provision_platform_key(text,text,uuid)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'provision_platform_key must remain executable by service_role';
  END IF;
END;
$$;

COMMIT;
