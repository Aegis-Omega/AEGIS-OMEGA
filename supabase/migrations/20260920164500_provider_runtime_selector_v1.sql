-- AEGIS Sovereign Provider Mesh runtime selector V1.
-- Chooses only fresh OBSERVED_AVAILABLE providers for one requested capability.
-- Availability evidence does not grant execution authority.
-- authority_effect = NONE

begin;

create or replace function public.select_provider_runtime_v1(p_capability text)
returns table (
  provider_id text,
  evidence_hash text,
  observed_at timestamptz,
  expires_at timestamptz
)
language sql
stable
set search_path = ''
as $$
  select
    v.provider_id,
    v.evidence_hash,
    v.observed_at,
    v.expires_at
  from public.provider_runtime_latest_v1 v
  where v.observation_state = 'OBSERVED_AVAILABLE'
    and not v.is_expired
    and p_capability = any(v.capabilities)
  order by v.provider_id
  limit 1;
$$;

revoke all on function public.select_provider_runtime_v1(text)
  from public, anon, authenticated;

grant execute on function public.select_provider_runtime_v1(text)
  to service_role;

comment on function public.select_provider_runtime_v1(text) is
  'AEGIS service-only provider selector. Availability evidence only; authority_effect=NONE.';

commit;
