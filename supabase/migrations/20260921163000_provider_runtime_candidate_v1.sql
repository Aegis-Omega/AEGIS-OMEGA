-- AEGIS service-only evidence-qualified provider candidate lookup V1.
-- A provider must be fresh OBSERVED_AVAILABLE for the requested capability.
-- authority_effect = NONE.

begin;

create or replace function public.get_provider_runtime_candidate_v1(
  p_capability text,
  p_provider_id text default null
)
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
    and (p_provider_id is null or v.provider_id = p_provider_id)
  order by v.provider_id
  limit 1;
$$;

revoke all on function public.get_provider_runtime_candidate_v1(text,text)
  from public, anon, authenticated;

grant execute on function public.get_provider_runtime_candidate_v1(text,text)
  to service_role;

comment on function public.get_provider_runtime_candidate_v1(text,text) is
  'AEGIS service-only evidence-qualified provider candidate lookup; authority_effect=NONE.';

commit;
