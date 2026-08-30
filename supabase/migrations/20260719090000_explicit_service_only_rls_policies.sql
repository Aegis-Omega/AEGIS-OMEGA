-- AEGIS operator-approved explicit service-only posture.
--
-- RLS was already enabled on these tables. This migration makes the implicit
-- default-deny posture explicit for Supabase client roles while preserving
-- service_role access through PostgreSQL BYPASSRLS.

begin;

alter table public.access_grants enable row level security;
drop policy if exists "deny_client_access_service_only" on public.access_grants;
create policy "deny_client_access_service_only"
  on public.access_grants
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);
comment on policy "deny_client_access_service_only" on public.access_grants is
  'AEGIS service-only posture: anon and authenticated are explicitly denied; service_role retains BYPASSRLS access.';

alter table public.analytics_events enable row level security;
drop policy if exists "deny_client_access_service_only" on public.analytics_events;
create policy "deny_client_access_service_only"
  on public.analytics_events
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);
comment on policy "deny_client_access_service_only" on public.analytics_events is
  'AEGIS service-only posture: anon and authenticated are explicitly denied; service_role retains BYPASSRLS access.';

alter table public.purchases enable row level security;
drop policy if exists "deny_client_access_service_only" on public.purchases;
create policy "deny_client_access_service_only"
  on public.purchases
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);
comment on policy "deny_client_access_service_only" on public.purchases is
  'AEGIS service-only posture: anon and authenticated are explicitly denied; service_role retains BYPASSRLS access.';

alter table public.swarm_memory enable row level security;
drop policy if exists "deny_client_access_service_only" on public.swarm_memory;
create policy "deny_client_access_service_only"
  on public.swarm_memory
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);
comment on policy "deny_client_access_service_only" on public.swarm_memory is
  'AEGIS service-only posture: anon and authenticated are explicitly denied; service_role retains BYPASSRLS access.';

commit;
