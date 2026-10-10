-- AEGIS Ω — at-most-once paid agent dispatch across Supabase Edge isolates.
-- No production schema change occurs until this migration is independently
-- reviewed and explicitly deployed by the authorized operator.
--
-- Each receipt is only a domain-separated SHA-256 digest of an authenticated
-- Slack event ID, stable across invoke-token rotation. No task text, person, Slack token or
-- provider response is stored. The unique primary key is the concurrency gate.
-- A CLAIMED dispatch cannot be re-executed automatically, even after an
-- ambiguous timeout: retries could double-charge an API call.
create table if not exists public.aegis_agent_dispatch_claims_v1 (
  event_digest text primary key
    constraint aegis_agent_dispatch_digest_format check (event_digest ~ '^[0-9a-f]{64}$'),
  claimed_at timestamptz not null default now()
);

alter table public.aegis_agent_dispatch_claims_v1 enable row level security;

-- Explicitly prevent browser and authenticated-user access.
revoke all on public.aegis_agent_dispatch_claims_v1 from public, anon, authenticated;
grant insert on public.aegis_agent_dispatch_claims_v1 to service_role;

comment on table public.aegis_agent_dispatch_claims_v1 is
  'Once-only, privacy-minimal dispatch reservations for the AEGIS agent. '
  'Unique-constraint insertion must succeed before the first paid model call. '
  'Retention and retries require a separately reviewed operational policy.';
