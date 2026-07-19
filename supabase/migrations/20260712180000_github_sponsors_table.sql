-- github_sponsors: sponsorship state written by the github-sponsors edge function.
-- Rows are upserted from GitHub Sponsors webhook events (onConflict github_username)
-- and updated when a sponsor claims their API key via POST /claim.
-- provision_platform_key() returns only the raw key text (never stored), so the
-- claim is marked with a boolean `provisioned` flag rather than a key id.

CREATE TABLE IF NOT EXISTS public.github_sponsors (
  github_username  text PRIMARY KEY,
  tier_dollars     numeric NOT NULL DEFAULT 0,
  aegis_tier       text NOT NULL DEFAULT 'explorer' CHECK (aegis_tier IN ('explorer', 'operator', 'sovereign')),
  active           boolean NOT NULL DEFAULT false,
  is_one_time      boolean NOT NULL DEFAULT false,  -- one-time sponsorships keep the same tier floors; revocation policy is operator-side
  claimed_email    text,
  claimed_at       timestamptz,
  last_delivery_id text,                            -- x-github-delivery of the last processed webhook (replay dedup)
  provisioned      boolean NOT NULL DEFAULT false,  -- API key already minted for this sponsorship
  issued_tier      text,                            -- tier actually issued at provision time (upgrade detection)
  updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Idempotent column backfill: safe whether the table above was just created or
-- already existed (e.g. manually created before this migration). Every column
-- the github-sponsors edge function reads or writes is guaranteed present.
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS tier_dollars     numeric NOT NULL DEFAULT 0;
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS aegis_tier       text NOT NULL DEFAULT 'explorer';
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS active           boolean NOT NULL DEFAULT false;
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS is_one_time      boolean NOT NULL DEFAULT false;
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS claimed_email    text;
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS claimed_at       timestamptz;
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS last_delivery_id text;
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS provisioned      boolean NOT NULL DEFAULT false;
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS issued_tier      text;
ALTER TABLE public.github_sponsors ADD COLUMN IF NOT EXISTS updated_at       timestamptz NOT NULL DEFAULT now();

-- Service-role only: RLS enabled with no policies. The edge function uses the
-- service role key, which bypasses RLS; anon/authenticated get nothing.
ALTER TABLE public.github_sponsors ENABLE ROW LEVEL SECURITY;
