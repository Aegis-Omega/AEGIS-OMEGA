-- Explicit service-only RLS posture for GCP census receipts.
-- The live table is written by the authenticated gcp-census-receipt Edge Function
-- using service_role. Client roles have no legitimate access path.

begin;

alter table public.gcp_census_receipts enable row level security;

drop policy if exists "deny_client_access_service_only"
  on public.gcp_census_receipts;

create policy "deny_client_access_service_only"
  on public.gcp_census_receipts
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

comment on policy "deny_client_access_service_only"
  on public.gcp_census_receipts is
  'AEGIS service-only posture: anon and authenticated are explicitly denied; service_role retains BYPASSRLS access.';

commit;
