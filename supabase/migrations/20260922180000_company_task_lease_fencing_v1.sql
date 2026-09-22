-- AEGIS Ω durable task lease + fencing v1
-- Repository migration only. Not applied by this PR.
-- Cross-worker exclusion is established by PostgreSQL row locks, not by model behavior.
-- authority_effect = NONE

alter table public.company_tasks_v1
  add column if not exists task_digest text
    check (task_digest is null or task_digest ~ '^[0-9a-f]{64}
  task_id text not null
    references public.company_tasks_v1(task_id) on delete cascade,
  depends_on_task_id text not null
    references public.company_tasks_v1(task_id) on delete restrict,
  created_at timestamptz not null default now(),
  primary key (task_id, depends_on_task_id),
  check (task_id <> depends_on_task_id)
);

create table if not exists public.company_task_leases_v1 (
  task_id text primary key
    references public.company_tasks_v1(task_id) on delete cascade,
  worker_id text not null check (length(btrim(worker_id)) > 0),
  task_digest text not null check (task_digest ~ '^[0-9a-f]{64}$'),
  lease_digest text not null unique check (lease_digest ~ '^[0-9a-f]{64}$'),
  acquired_generation bigint not null check (acquired_generation >= 0),
  expires_generation bigint not null check (
    expires_generation >= acquired_generation
  ),
  released_generation bigint check (
    released_generation is null or released_generation >= acquired_generation
  ),
  lease_state text not null default 'ACTIVE'
    check (lease_state in ('ACTIVE','RELEASED')),
  external_authority text not null default 'NOT_GRANTED'
    check (external_authority = 'NOT_GRANTED'),
  authority_effect text not null default 'NONE'
    check (authority_effect = 'NONE'),
  updated_at timestamptz not null default now(),
  check (
    (lease_state = 'ACTIVE' and released_generation is null)
    or
    (lease_state = 'RELEASED' and released_generation is not null)
  )
);

create index if not exists company_task_dependencies_reverse_idx
  on public.company_task_dependencies_v1(depends_on_task_id, task_id);
create index if not exists company_task_leases_expiry_idx
  on public.company_task_leases_v1(lease_state, expires_generation);

alter table public.company_task_dependencies_v1 enable row level security;
alter table public.company_task_leases_v1 enable row level security;
alter table public.company_task_dependencies_v1 force row level security;
alter table public.company_task_leases_v1 force row level security;

revoke all on public.company_task_dependencies_v1 from anon, authenticated;
revoke all on public.company_task_leases_v1 from anon, authenticated;

create or replace function public.claim_company_task_lease_v1(
  p_task_id text,
  p_worker_id text,
  p_task_digest text,
  p_lease_digest text,
  p_current_generation bigint,
  p_ttl_generations bigint
)
returns table (
  outcome text,
  granted_lease_digest text,
  granted_expires_generation bigint
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_status text;
  v_canonical_task_digest text;
  v_has_lease boolean := false;
  v_lease public.company_task_leases_v1%rowtype;
  v_expires bigint;
begin
  if p_task_id is null or length(btrim(p_task_id)) = 0 then
    raise exception 'task_id required';
  end if;
  if p_worker_id is null or length(btrim(p_worker_id)) = 0 then
    raise exception 'worker_id required';
  end if;
  if p_task_digest is null or p_task_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid task_digest';
  end if;
  if p_lease_digest is null or p_lease_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid lease_digest';
  end if;
  if p_current_generation is null or p_current_generation < 0 then
    raise exception 'invalid current_generation';
  end if;
  if p_ttl_generations is null or p_ttl_generations < 1 or p_ttl_generations > 16 then
    raise exception 'invalid ttl_generations';
  end if;

  select t.status, t.task_digest
    into v_status, v_canonical_task_digest
    from public.company_tasks_v1 as t
   where t.task_id = p_task_id
   for update;

  if not found then
    return query select 'DENIED_UNKNOWN_TASK'::text, null::text, null::bigint;
    return;
  end if;

  if v_canonical_task_digest is null
     or v_canonical_task_digest <> p_task_digest then
    return query select 'DENIED_TASK_DIGEST_MISMATCH'::text, null::text, null::bigint;
    return;
  end if;

  if exists (
    select 1
      from public.company_task_dependencies_v1 as d
      join public.company_tasks_v1 as dependency
        on dependency.task_id = d.depends_on_task_id
     where d.task_id = p_task_id
       and dependency.status <> 'VERIFIED'
  ) then
    return query select 'DENIED_DEPENDENCY_NOT_VERIFIED'::text, null::text, null::bigint;
    return;
  end if;

  select l.*
    into v_lease
    from public.company_task_leases_v1 as l
   where l.task_id = p_task_id
   for update;
  v_has_lease := found;

  if v_has_lease
     and v_lease.lease_state = 'ACTIVE'
     and p_current_generation >= v_lease.acquired_generation
     and p_current_generation <= v_lease.expires_generation then
    if v_lease.worker_id = p_worker_id
       and v_lease.task_digest = p_task_digest
       and v_lease.lease_digest = p_lease_digest then
      return query
        select 'REPLAYED'::text, v_lease.lease_digest, v_lease.expires_generation;
    else
      return query
        select 'DENIED_ALREADY_LEASED'::text, v_lease.lease_digest, v_lease.expires_generation;
    end if;
    return;
  end if;

  if v_status = 'RUNNING'
     and (
       not v_has_lease
       or v_lease.lease_state <> 'ACTIVE'
     ) then
    return query select 'DENIED_INCONSISTENT_RUNNING'::text, null::text, null::bigint;
    return;
  end if;

  if v_status not in ('PLANNED','RUNNING') then
    return query select 'DENIED_TASK_STATE'::text, null::text, null::bigint;
    return;
  end if;

  v_expires := p_current_generation + p_ttl_generations;

  insert into public.company_task_leases_v1 (
    task_id,
    worker_id,
    task_digest,
    lease_digest,
    acquired_generation,
    expires_generation,
    released_generation,
    lease_state,
    external_authority,
    authority_effect,
    updated_at
  ) values (
    p_task_id,
    p_worker_id,
    p_task_digest,
    p_lease_digest,
    p_current_generation,
    v_expires,
    null,
    'ACTIVE',
    'NOT_GRANTED',
    'NONE',
    now()
  )
  on conflict (task_id) do update set
    worker_id = excluded.worker_id,
    task_digest = excluded.task_digest,
    lease_digest = excluded.lease_digest,
    acquired_generation = excluded.acquired_generation,
    expires_generation = excluded.expires_generation,
    released_generation = null,
    lease_state = 'ACTIVE',
    external_authority = 'NOT_GRANTED',
    authority_effect = 'NONE',
    updated_at = now();

  update public.company_tasks_v1
     set status = 'RUNNING',
         updated_at = now()
   where task_id = p_task_id;

  return query select 'CLAIMED'::text, p_lease_digest, v_expires;
end;
$$;

create or replace function public.complete_company_task_lease_v1(
  p_task_id text,
  p_worker_id text,
  p_lease_digest text,
  p_current_generation bigint,
  p_terminal_status text,
  p_execution_hash text,
  p_verification_hash text,
  p_receipt_root text
)
returns text
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_task_status text;
  v_lease public.company_task_leases_v1%rowtype;
begin
  if p_terminal_status not in ('VERIFIED','REJECTED') then
    raise exception 'invalid terminal status';
  end if;
  if p_current_generation is null or p_current_generation < 0 then
    raise exception 'invalid current_generation';
  end if;
  if p_lease_digest is null or p_lease_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid lease_digest';
  end if;
  if p_execution_hash is null or p_execution_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid execution_hash';
  end if;
  if p_verification_hash is null or p_verification_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid verification_hash';
  end if;
  if p_receipt_root is null or p_receipt_root !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid receipt_root';
  end if;

  select t.status
    into v_task_status
    from public.company_tasks_v1 as t
   where t.task_id = p_task_id
   for update;

  if not found or v_task_status <> 'RUNNING' then
    return 'DENIED_TASK_STATE';
  end if;

  select l.*
    into v_lease
    from public.company_task_leases_v1 as l
   where l.task_id = p_task_id
   for update;

  if not found then
    return 'DENIED_LEASE_MISSING';
  end if;
  if v_lease.lease_state <> 'ACTIVE' then
    return 'DENIED_LEASE_INACTIVE';
  end if;
  if v_lease.worker_id <> p_worker_id or v_lease.lease_digest <> p_lease_digest then
    return 'DENIED_LEASE_FENCE';
  end if;
  if p_current_generation < v_lease.acquired_generation
     or p_current_generation > v_lease.expires_generation then
    return 'DENIED_LEASE_EXPIRED';
  end if;

  update public.company_tasks_v1
     set status = p_terminal_status,
         execution_hash = p_execution_hash,
         verification_hash = p_verification_hash,
         receipt_root = p_receipt_root,
         updated_at = now()
   where task_id = p_task_id;

  update public.company_task_leases_v1
     set lease_state = 'RELEASED',
         released_generation = p_current_generation,
         updated_at = now()
   where task_id = p_task_id;

  return 'COMPLETED';
end;
$$;

revoke all on function public.claim_company_task_lease_v1(
  text, text, text, text, bigint, bigint
) from public, anon, authenticated;
revoke all on function public.complete_company_task_lease_v1(
  text, text, text, bigint, text, text, text, text
) from public, anon, authenticated;

grant execute on function public.claim_company_task_lease_v1(
  text, text, text, text, bigint, bigint
) to service_role;
grant execute on function public.complete_company_task_lease_v1(
  text, text, text, bigint, text, text, text, text
) to service_role;
);

create table if not exists public.company_task_dependencies_v1 (
  task_id text not null
    references public.company_tasks_v1(task_id) on delete cascade,
  depends_on_task_id text not null
    references public.company_tasks_v1(task_id) on delete restrict,
  created_at timestamptz not null default now(),
  primary key (task_id, depends_on_task_id),
  check (task_id <> depends_on_task_id)
);

create table if not exists public.company_task_leases_v1 (
  task_id text primary key
    references public.company_tasks_v1(task_id) on delete cascade,
  worker_id text not null check (length(btrim(worker_id)) > 0),
  task_digest text not null check (task_digest ~ '^[0-9a-f]{64}$'),
  lease_digest text not null unique check (lease_digest ~ '^[0-9a-f]{64}$'),
  acquired_generation bigint not null check (acquired_generation >= 0),
  expires_generation bigint not null check (
    expires_generation >= acquired_generation
  ),
  released_generation bigint check (
    released_generation is null or released_generation >= acquired_generation
  ),
  lease_state text not null default 'ACTIVE'
    check (lease_state in ('ACTIVE','RELEASED')),
  external_authority text not null default 'NOT_GRANTED'
    check (external_authority = 'NOT_GRANTED'),
  authority_effect text not null default 'NONE'
    check (authority_effect = 'NONE'),
  updated_at timestamptz not null default now(),
  check (
    (lease_state = 'ACTIVE' and released_generation is null)
    or
    (lease_state = 'RELEASED' and released_generation is not null)
  )
);

create index if not exists company_task_dependencies_reverse_idx
  on public.company_task_dependencies_v1(depends_on_task_id, task_id);
create index if not exists company_task_leases_expiry_idx
  on public.company_task_leases_v1(lease_state, expires_generation);

alter table public.company_task_dependencies_v1 enable row level security;
alter table public.company_task_leases_v1 enable row level security;
alter table public.company_task_dependencies_v1 force row level security;
alter table public.company_task_leases_v1 force row level security;

revoke all on public.company_task_dependencies_v1 from anon, authenticated;
revoke all on public.company_task_leases_v1 from anon, authenticated;

create or replace function public.claim_company_task_lease_v1(
  p_task_id text,
  p_worker_id text,
  p_task_digest text,
  p_lease_digest text,
  p_current_generation bigint,
  p_ttl_generations bigint
)
returns table (
  outcome text,
  granted_lease_digest text,
  granted_expires_generation bigint
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_status text;
  v_has_lease boolean := false;
  v_lease public.company_task_leases_v1%rowtype;
  v_expires bigint;
begin
  if p_task_id is null or length(btrim(p_task_id)) = 0 then
    raise exception 'task_id required';
  end if;
  if p_worker_id is null or length(btrim(p_worker_id)) = 0 then
    raise exception 'worker_id required';
  end if;
  if p_task_digest is null or p_task_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid task_digest';
  end if;
  if p_lease_digest is null or p_lease_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid lease_digest';
  end if;
  if p_current_generation is null or p_current_generation < 0 then
    raise exception 'invalid current_generation';
  end if;
  if p_ttl_generations is null or p_ttl_generations < 1 or p_ttl_generations > 16 then
    raise exception 'invalid ttl_generations';
  end if;

  select t.status
    into v_status
    from public.company_tasks_v1 as t
   where t.task_id = p_task_id
   for update;

  if not found then
    return query select 'DENIED_UNKNOWN_TASK'::text, null::text, null::bigint;
    return;
  end if;

  if exists (
    select 1
      from public.company_task_dependencies_v1 as d
      join public.company_tasks_v1 as dependency
        on dependency.task_id = d.depends_on_task_id
     where d.task_id = p_task_id
       and dependency.status <> 'VERIFIED'
  ) then
    return query select 'DENIED_DEPENDENCY_NOT_VERIFIED'::text, null::text, null::bigint;
    return;
  end if;

  select l.*
    into v_lease
    from public.company_task_leases_v1 as l
   where l.task_id = p_task_id
   for update;
  v_has_lease := found;

  if v_has_lease
     and v_lease.lease_state = 'ACTIVE'
     and p_current_generation <= v_lease.expires_generation then
    if v_lease.worker_id = p_worker_id
       and v_lease.task_digest = p_task_digest
       and v_lease.lease_digest = p_lease_digest then
      return query
        select 'REPLAYED'::text, v_lease.lease_digest, v_lease.expires_generation;
    else
      return query
        select 'DENIED_ALREADY_LEASED'::text, v_lease.lease_digest, v_lease.expires_generation;
    end if;
    return;
  end if;

  if v_status = 'RUNNING'
     and (
       not v_has_lease
       or v_lease.lease_state <> 'ACTIVE'
     ) then
    return query select 'DENIED_INCONSISTENT_RUNNING'::text, null::text, null::bigint;
    return;
  end if;

  if v_status not in ('PLANNED','RUNNING') then
    return query select 'DENIED_TASK_STATE'::text, null::text, null::bigint;
    return;
  end if;

  v_expires := p_current_generation + p_ttl_generations;

  insert into public.company_task_leases_v1 (
    task_id,
    worker_id,
    task_digest,
    lease_digest,
    acquired_generation,
    expires_generation,
    released_generation,
    lease_state,
    external_authority,
    authority_effect,
    updated_at
  ) values (
    p_task_id,
    p_worker_id,
    p_task_digest,
    p_lease_digest,
    p_current_generation,
    v_expires,
    null,
    'ACTIVE',
    'NOT_GRANTED',
    'NONE',
    now()
  )
  on conflict (task_id) do update set
    worker_id = excluded.worker_id,
    task_digest = excluded.task_digest,
    lease_digest = excluded.lease_digest,
    acquired_generation = excluded.acquired_generation,
    expires_generation = excluded.expires_generation,
    released_generation = null,
    lease_state = 'ACTIVE',
    external_authority = 'NOT_GRANTED',
    authority_effect = 'NONE',
    updated_at = now();

  update public.company_tasks_v1
     set status = 'RUNNING',
         updated_at = now()
   where task_id = p_task_id;

  return query select 'CLAIMED'::text, p_lease_digest, v_expires;
end;
$$;

create or replace function public.complete_company_task_lease_v1(
  p_task_id text,
  p_worker_id text,
  p_lease_digest text,
  p_current_generation bigint,
  p_terminal_status text,
  p_execution_hash text,
  p_verification_hash text,
  p_receipt_root text
)
returns text
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_task_status text;
  v_lease public.company_task_leases_v1%rowtype;
begin
  if p_terminal_status not in ('VERIFIED','REJECTED') then
    raise exception 'invalid terminal status';
  end if;
  if p_current_generation is null or p_current_generation < 0 then
    raise exception 'invalid current_generation';
  end if;
  if p_lease_digest is null or p_lease_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid lease_digest';
  end if;
  if p_execution_hash is null or p_execution_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid execution_hash';
  end if;
  if p_verification_hash is null or p_verification_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid verification_hash';
  end if;
  if p_receipt_root is null or p_receipt_root !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid receipt_root';
  end if;

  select t.status
    into v_task_status
    from public.company_tasks_v1 as t
   where t.task_id = p_task_id
   for update;

  if not found or v_task_status <> 'RUNNING' then
    return 'DENIED_TASK_STATE';
  end if;

  select l.*
    into v_lease
    from public.company_task_leases_v1 as l
   where l.task_id = p_task_id
   for update;

  if not found then
    return 'DENIED_LEASE_MISSING';
  end if;
  if v_lease.lease_state <> 'ACTIVE' then
    return 'DENIED_LEASE_INACTIVE';
  end if;
  if v_lease.worker_id <> p_worker_id or v_lease.lease_digest <> p_lease_digest then
    return 'DENIED_LEASE_FENCE';
  end if;
  if p_current_generation < v_lease.acquired_generation
     or p_current_generation > v_lease.expires_generation then
    return 'DENIED_LEASE_EXPIRED';
  end if;

  update public.company_tasks_v1
     set status = p_terminal_status,
         execution_hash = p_execution_hash,
         verification_hash = p_verification_hash,
         receipt_root = p_receipt_root,
         updated_at = now()
   where task_id = p_task_id;

  update public.company_task_leases_v1
     set lease_state = 'RELEASED',
         released_generation = p_current_generation,
         updated_at = now()
   where task_id = p_task_id;

  return 'COMPLETED';
end;
$$;

revoke all on function public.claim_company_task_lease_v1(
  text, text, text, text, bigint, bigint
) from public, anon, authenticated;
revoke all on function public.complete_company_task_lease_v1(
  text, text, text, bigint, text, text, text, text
) from public, anon, authenticated;

grant execute on function public.claim_company_task_lease_v1(
  text, text, text, text, bigint, bigint
) to service_role;
grant execute on function public.complete_company_task_lease_v1(
  text, text, text, bigint, text, text, text, text
) to service_role;
