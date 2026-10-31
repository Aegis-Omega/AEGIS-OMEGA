-- AEGIS funded Nebius budget: atomic, default-deny and service-role-only.
-- Attempts are not USD. A provider-side monetary limit is still required.
begin;

create table if not exists public.nebius_inference_budget_v1 (
  singleton boolean primary key default true check (singleton = true),
  enabled boolean not null default false,
  max_attempts integer not null default 0 check (max_attempts between 0 and 100000),
  attempts_used integer not null default 0 check (attempts_used >= 0),
  modified_at timestamptz not null default now(),
  constraint nebius_budget_within_cap check (attempts_used <= max_attempts)
);
insert into public.nebius_inference_budget_v1
  (singleton, enabled, max_attempts, attempts_used)
values (true, false, 0, 0)
on conflict (singleton) do nothing;

alter table public.nebius_inference_budget_v1 enable row level security;
drop policy if exists nebius_budget_deny_clients on public.nebius_inference_budget_v1;
create policy nebius_budget_deny_clients
on public.nebius_inference_budget_v1 as restrictive for all
to anon, authenticated
using (false) with check (false);
revoke all on table public.nebius_inference_budget_v1 from public, anon, authenticated;
grant select, update on table public.nebius_inference_budget_v1 to service_role;
revoke insert, delete, truncate on table public.nebius_inference_budget_v1 from service_role;

create or replace function public.reserve_nebius_inference_attempt_v1()
returns boolean
language plpgsql
security invoker
set search_path = ''
as $budget$
declare v_reserved boolean := false;
begin
  -- Atomic UPDATE takes a row lock, so concurrent calls cannot exceed the cap.
  -- Count attempts even if the upstream rejects or times out.
  update public.nebius_inference_budget_v1
  set attempts_used = attempts_used + 1, modified_at = now()
  where singleton = true and enabled = true
    and attempts_used < max_attempts
  returning true into v_reserved;
  return coalesce(v_reserved, false);
end;
$budget$;
revoke all on function public.reserve_nebius_inference_attempt_v1()
from public, anon, authenticated;
grant execute on function public.reserve_nebius_inference_attempt_v1()
to service_role;
comment on table public.nebius_inference_budget_v1 is
'AEGIS funded attempt cap, zero by default; not a monetary billing guarantee.';
commit;
