-- AEGIS Ω Supabase Advisor Performance Hardening V1
-- SOURCE ONLY. Do not apply without explicit production schema approval.
-- Addresses only current 2026-09-22 advisor findings verified against live definitions.

create index if not exists access_grants_purchase_id_idx
  on public.access_grants(purchase_id);

drop policy if exists service_role_all
  on public.department_fitness_tracking;
create policy service_role_all
  on public.department_fitness_tracking
  as permissive
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists service_role_all
  on public.agent_api_profiles;
create policy service_role_all
  on public.agent_api_profiles
  as permissive
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists grace_events_service_only
  on public.grace_events;
create policy grace_events_service_only
  on public.grace_events
  as permissive
  for all
  to service_role
  using (true)
  with check (true);

drop policy if exists dept_graces_service_write
  on public.dept_graces;
create policy dept_graces_service_write
  on public.dept_graces
  as permissive
  for all
  to service_role
  using (true)
  with check (true);
