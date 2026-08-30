-- Fix provision_platform_key: write to api_key_store (the table the bridge verifies against).
-- The previous version (20260606) targeted platform_api_keys which was never applied.

CREATE OR REPLACE FUNCTION public.provision_platform_key(
  p_customer_email text,
  p_tier           text,
  p_purchase_id    uuid DEFAULT null
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_raw_key     text;
  v_key_hash    text;
  v_usage_limit int;
BEGIN
  IF p_tier NOT IN ('explorer', 'operator', 'sovereign') THEN
    RAISE EXCEPTION 'Invalid tier: %', p_tier;
  END IF;

  v_raw_key := 'aegis_' || encode(gen_random_bytes(24), 'base64');
  v_raw_key := replace(replace(replace(v_raw_key, '/', '_'), '+', '-'), '=', '');

  v_key_hash := encode(sha256(v_raw_key::bytea), 'hex');

  v_usage_limit := CASE p_tier
    WHEN 'explorer'  THEN 10
    WHEN 'operator'  THEN 500
    WHEN 'sovereign' THEN 1000000
    ELSE 10
  END;

  INSERT INTO public.api_key_store
    (customer_email, tier, key_hash, usage_count, usage_limit, revoked)
  VALUES
    (p_customer_email, p_tier, v_key_hash, 0, v_usage_limit, false)
  ON CONFLICT (key_hash) DO NOTHING;

  RETURN v_raw_key;
END;
$$;

GRANT EXECUTE ON FUNCTION public.provision_platform_key(text, text, uuid) TO service_role;
