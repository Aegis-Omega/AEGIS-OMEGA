-- api_key_store: persistent AEGIS API key registry
-- Keys are issued by verify-paypal edge function via provision_platform_key() RPC.
-- Bridge verifies keys at runtime via Supabase REST API (SUPABASE_SERVICE_ROLE_KEY).

CREATE TABLE IF NOT EXISTS public.api_key_store (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_email  text NOT NULL,
  tier            text NOT NULL CHECK (tier IN ('explorer', 'operator', 'sovereign')),
  key_hash        text NOT NULL UNIQUE,  -- SHA-256 of the raw key (never store raw)
  usage_count     int  NOT NULL DEFAULT 0,
  usage_limit     int  NOT NULL DEFAULT 10,  -- 10 explorer, 500 operator, 1M sovereign
  revoked         bool NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_key_store_hash_idx  ON public.api_key_store(key_hash);
CREATE INDEX IF NOT EXISTS api_key_store_email_idx ON public.api_key_store(customer_email);

ALTER TABLE public.api_key_store ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'api_key_store' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY service_role_all ON public.api_key_store
      FOR ALL USING (true) WITH CHECK (true);
  END IF;
END
$$;
