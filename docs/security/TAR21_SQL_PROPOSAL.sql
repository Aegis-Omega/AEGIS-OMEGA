-- TAR-21 DRAFT ONLY: reviewed SQL proposal, NOT applied, NOT a migration.
-- Before PR write: create a migration with `supabase migration new tar21_agent_admission`
-- and transfer this reviewed SQL into the generated file. No production SQL executed.
-- Service role remains SERVER-ONLY for the agent's internal DB RPC, never a caller identity.

create schema if not exists aegis_private;
revoke all on schema aegis_private from public;
grant usage on schema aegis_private to service_role;

create table if not exists aegis_private.agent_admission_receipts (
  request_key text primary key,
  actor_kind text not null check (actor_kind in ('slack','operator')),
  actor_id text not null,
  reserved_at timestamptz not null default clock_timestamp()
);
create table if not exists aegis_private.agent_budget_counter (
  bucket text primary key,
  used integer not null default 0 check (used > 0),
  touched_at timestamptz not null default clock_timestamp()
);
alter table aegis_private.agent_admission_receipts enable row level security;
alter table aegis_private.agent_budget_counter enable row level security;
revoke all on aegis_private.agent_admission_receipts from public, anon, authenticated;
revoke all on aegis_private.agent_budget_counter from public, anon, authenticated;
grant select, insert on aegis_private.agent_admission_receipts to service_role;
grant select, insert, update on aegis_private.agent_budget_counter to service_role;

-- Single Postgres transaction; caps fixed in SQL, unchangeable by HTTP args.
-- Slack per-user: 3/day, 1/min. Operator: 10/day, 2/min. Global: 20/day.
-- These are request ceilings, NOT a guaranteed provider currency budget.
create or replace function public.aegis_agent_reserve_budget(
  p_kind text, p_actor_id text, p_request_key text
) returns boolean
language plpgsql security invoker set search_path = ''
as $$
declare
  day_key text := to_char(clock_timestamp() at time zone 'UTC', 'YYYY-MM-DD');
  minute_key text := to_char(clock_timestamp() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI');
  per_day integer;
  per_minute integer;
  n integer;
begin
  if current_user <> 'service_role'
    or p_kind not in ('operator', 'slack')
    or p_actor_id is null or p_actor_id !~ '^[A-Za-z0-9:._-]{1,160}$'
    or p_request_key is null or p_request_key !~ '^[A-Za-z0-9:._-]{8,180}$'
  then return false; end if;
  per_day := case when p_kind = 'slack' then 3 else 10 end;
  per_minute := case when p_kind = 'slack' then 1 else 2 end;
  begin
    -- Unique receipt is recorded before quota work. The nested exception
    -- block atomically rolls back this receipt if a subsequent counter fails.
    insert into aegis_private.agent_admission_receipts(request_key, actor_kind, actor_id)
    values (p_request_key, p_kind, p_actor_id) on conflict do nothing;
    get diagnostics n = row_count;
    if n <> 1 then return false; end if;

    insert into aegis_private.agent_budget_counter as b(bucket, used)
    values ('global:' || day_key, 1)
    on conflict (bucket) do update
      set used = b.used + 1, touched_at = clock_timestamp()
      where b.used < 20;
    get diagnostics n = row_count;
    if n <> 1 then raise exception 'quota exceeded' using errcode = 'P0001'; end if;

    insert into aegis_private.agent_budget_counter as b(bucket, used)
    values (p_kind || ':' || p_actor_id || ':day:' || day_key, 1)
    on conflict (bucket) do update
      set used = b.used + 1, touched_at = clock_timestamp()
      where b.used < per_day;
    get diagnostics n = row_count;
    if n <> 1 then raise exception 'quota exceeded' using errcode = 'P0001'; end if;

    insert into aegis_private.agent_budget_counter as b(bucket, used)
    values (p_kind || ':' || p_actor_id || ':minute:' || minute_key, 1)
    on conflict (bucket) do update
      set used = b.used + 1, touched_at = clock_timestamp()
      where b.used < per_minute;
    get diagnostics n = row_count;
    if n <> 1 then raise exception 'quota exceeded' using errcode = 'P0001'; end if;
    return true;
  exception when sqlstate 'P0001' then
    -- Rollback the nested transaction and all three prior insert/update effects.
    return false;
  end;
end;
$$;
revoke all on function public.aegis_agent_reserve_budget(text,text,text) from public, anon, authenticated;
grant execute on function public.aegis_agent_reserve_budget(text,text,text) to service_role;
