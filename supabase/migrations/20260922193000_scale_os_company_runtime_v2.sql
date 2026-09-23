-- AEGIS Ω Scale OS Company Runtime V2
-- SOURCE ONLY. This migration targets the EXISTING production scale_os schema.
-- Do not apply without an explicit production schema grant.
-- Existing July 2026 rows are preserved; v2 authority fields do not reinterpret them.

alter table scale_os.tasks
  add column if not exists task_digest_v2 text
    check (task_digest_v2 is null or task_digest_v2 ~ '^[0-9a-f]{64}$'),
  add column if not exists idempotency_key_v2 text,
  add column if not exists generation_v2 bigint
    check (generation_v2 is null or generation_v2 >= 0);

create unique index if not exists scale_os_tasks_idempotency_key_v2_uidx
  on scale_os.tasks(idempotency_key_v2)
  where idempotency_key_v2 is not null;

alter table scale_os.approvals
  add column if not exists action_digest_v2 text
    check (action_digest_v2 is null or action_digest_v2 ~ '^[0-9a-f]{64}$'),
  add column if not exists approval_packet_v2 jsonb,
  add column if not exists grant_id_v2 text,
  add column if not exists grant_expires_at_v2 timestamptz;

alter table scale_os.approvals
  drop constraint if exists scale_os_approvals_v2_exact_grant;

alter table scale_os.approvals
  add constraint scale_os_approvals_v2_exact_grant
  check (
    decision <> 'approved'
    or (
      action_digest_v2 is not null
      and approval_packet_v2 is not null
      and grant_id_v2 is not null
      and length(btrim(grant_id_v2)) > 0
      and grant_expires_at_v2 is not null
      and decision_at is not null
      and grant_expires_at_v2 >= decision_at
    )
  ) not valid;

create or replace function scale_os.prevent_direct_v2_approval_mutation_v2()
returns trigger
language plpgsql
security invoker
set search_path = scale_os, pg_temp
as $$
declare
  v_old_v2 boolean := false;
  v_new_v2 boolean := false;
begin
  if tg_op <> 'INSERT' then
    v_old_v2 :=
      old.action_digest_v2 is not null
      or old.approval_packet_v2 is not null
      or old.grant_id_v2 is not null
      or old.grant_expires_at_v2 is not null;
  end if;

  if tg_op <> 'DELETE' then
    v_new_v2 :=
      new.action_digest_v2 is not null
      or new.approval_packet_v2 is not null
      or new.grant_id_v2 is not null
      or new.grant_expires_at_v2 is not null;
  end if;

  if current_user <> 'postgres' and (v_old_v2 or v_new_v2) then
    raise exception 'AEGIS_V2_APPROVAL_DIRECT_MUTATION_DENIED:%:%', current_user, tg_op
      using errcode = '42501';
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists scale_os_v2_approval_direct_mutation_guard
  on scale_os.approvals;

create trigger scale_os_v2_approval_direct_mutation_guard
before insert or update or delete on scale_os.approvals
for each row
execute function scale_os.prevent_direct_v2_approval_mutation_v2();

create table if not exists scale_os.task_dependencies_v2 (
  task_id uuid not null
    references scale_os.tasks(id) on delete cascade,
  depends_on_task_id uuid not null
    references scale_os.tasks(id) on delete restrict,
  created_at timestamptz not null default now(),
  primary key (task_id, depends_on_task_id),
  check (task_id <> depends_on_task_id)
);

create table if not exists scale_os.task_leases_v2 (
  task_id uuid primary key
    references scale_os.tasks(id) on delete cascade,
  worker_id text not null check (length(btrim(worker_id)) > 0),
  task_digest text not null check (task_digest ~ '^[0-9a-f]{64}$'),
  lease_digest text not null unique check (lease_digest ~ '^[0-9a-f]{64}$'),
  acquired_generation bigint not null check (acquired_generation >= 0),
  expires_generation bigint not null
    check (expires_generation >= acquired_generation),
  released_generation bigint
    check (released_generation is null or released_generation >= acquired_generation),
  lease_state text not null default 'active'
    check (lease_state in ('active','released')),
  external_authority text not null default 'NOT_GRANTED'
    check (external_authority = 'NOT_GRANTED'),
  authority_effect text not null default 'NONE'
    check (authority_effect = 'NONE'),
  updated_at timestamptz not null default now(),
  check (
    (lease_state = 'active' and released_generation is null)
    or
    (lease_state = 'released' and released_generation is not null)
  )
);

create index if not exists scale_os_task_dependencies_v2_reverse_idx
  on scale_os.task_dependencies_v2(depends_on_task_id, task_id);

create index if not exists scale_os_task_leases_v2_expiry_idx
  on scale_os.task_leases_v2(lease_state, expires_generation);

alter table scale_os.task_dependencies_v2 enable row level security;
alter table scale_os.task_leases_v2 enable row level security;
alter table scale_os.task_dependencies_v2 force row level security;
alter table scale_os.task_leases_v2 force row level security;

revoke all on scale_os.task_dependencies_v2 from public, anon, authenticated, service_role;
revoke all on scale_os.task_leases_v2 from public, anon, authenticated, service_role;
grant select on scale_os.task_dependencies_v2 to service_role;
grant select on scale_os.task_leases_v2 to service_role;

create or replace function scale_os.prevent_direct_v2_task_mutation_v2()
returns trigger
language plpgsql
security invoker
set search_path = scale_os, pg_temp
as $$
begin
  if current_user <> 'postgres' then
    if tg_op = 'INSERT' and new.task_digest_v2 is not null then
      raise exception 'AEGIS_V2_TASK_DIRECT_INSERT_DENIED:%', current_user
        using errcode = '42501';
    elsif tg_op = 'UPDATE'
       and (old.task_digest_v2 is not null or new.task_digest_v2 is not null) then
      raise exception 'AEGIS_V2_TASK_DIRECT_UPDATE_DENIED:%', current_user
        using errcode = '42501';
    elsif tg_op = 'DELETE' and old.task_digest_v2 is not null then
      raise exception 'AEGIS_V2_TASK_DIRECT_DELETE_DENIED:%', current_user
        using errcode = '42501';
    end if;
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists scale_os_v2_task_direct_mutation_guard
  on scale_os.tasks;

create trigger scale_os_v2_task_direct_mutation_guard
before insert or update or delete on scale_os.tasks
for each row
execute function scale_os.prevent_direct_v2_task_mutation_v2();

create or replace function scale_os.create_task_v2(
  p_task_type text,
  p_risk_level text,
  p_requires_approval boolean,
  p_source_system text,
  p_source_object_id text,
  p_payload jsonb,
  p_task_digest text,
  p_idempotency_key text,
  p_generation bigint
)
returns table (
  outcome text,
  task_id uuid
)
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
declare
  v_task_id uuid;
  v_existing scale_os.tasks%rowtype;
begin
  if p_task_type is null or length(btrim(p_task_type)) = 0 then
    raise exception 'task_type required';
  end if;
  if p_risk_level not in ('low','medium','high','critical') then
    raise exception 'invalid risk_level';
  end if;
  if p_requires_approval is null then
    raise exception 'requires_approval required';
  end if;
  if p_payload is null then
    raise exception 'payload required';
  end if;
  if p_task_digest is null or p_task_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid task_digest';
  end if;
  if p_idempotency_key is null or length(btrim(p_idempotency_key)) = 0 then
    raise exception 'idempotency_key required';
  end if;
  if p_generation is null or p_generation < 0 then
    raise exception 'invalid generation';
  end if;

  insert into scale_os.tasks(
    task_type,status,risk_level,requires_approval,
    source_system,source_object_id,payload,result,
    task_digest_v2,idempotency_key_v2,generation_v2
  ) values (
    btrim(p_task_type),'queued',p_risk_level,p_requires_approval,
    nullif(btrim(coalesce(p_source_system,'')),''),
    nullif(btrim(coalesce(p_source_object_id,'')),''),
    p_payload,'{}'::jsonb,
    p_task_digest,btrim(p_idempotency_key),p_generation
  )
  on conflict (idempotency_key_v2)
    where idempotency_key_v2 is not null
  do nothing
  returning id into v_task_id;

  if v_task_id is not null then
    return query select 'CREATED'::text, v_task_id;
    return;
  end if;

  select *
    into v_existing
    from scale_os.tasks
   where idempotency_key_v2 = btrim(p_idempotency_key)
   for update;

  if not found then
    return query select 'DENIED_IDEMPOTENCY_LOOKUP_FAILED'::text, null::uuid;
    return;
  end if;

  if v_existing.task_type <> btrim(p_task_type)
     or v_existing.risk_level <> p_risk_level
     or v_existing.requires_approval <> p_requires_approval
     or v_existing.source_system is distinct from nullif(btrim(coalesce(p_source_system,'')),'')
     or v_existing.source_object_id is distinct from nullif(btrim(coalesce(p_source_object_id,'')),'')
     or v_existing.payload <> p_payload
     or v_existing.task_digest_v2 <> p_task_digest
     or v_existing.generation_v2 <> p_generation then
    return query select 'DENIED_IDEMPOTENCY_COLLISION'::text, v_existing.id;
    return;
  end if;

  return query select 'REPLAYED'::text, v_existing.id;
end;
$$;

create or replace function scale_os.add_task_dependency_v2(
  p_task_id uuid,
  p_depends_on_task_id uuid
)
returns text
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
declare
  v_task_status text;
  v_dependency_exists boolean;
  v_inserted integer := 0;
begin
  if p_task_id is null or p_depends_on_task_id is null then
    raise exception 'task ids required';
  end if;
  if p_task_id = p_depends_on_task_id then
    return 'DENIED_SELF_DEPENDENCY';
  end if;

  perform t.id
    from scale_os.tasks as t
   where t.id in (p_task_id, p_depends_on_task_id)
   order by t.id
   for update;

  select t.status
    into v_task_status
    from scale_os.tasks as t
   where t.id = p_task_id;

  if not found then
    return 'DENIED_UNKNOWN_TASK';
  end if;

  select exists (
    select 1 from scale_os.tasks as t
     where t.id = p_depends_on_task_id
  ) into v_dependency_exists;

  if not v_dependency_exists then
    return 'DENIED_UNKNOWN_DEPENDENCY';
  end if;

  if v_task_status not in ('queued','awaiting_approval') then
    return 'DENIED_TASK_ALREADY_STARTED';
  end if;

  if exists (
    with recursive dependency_walk(task_id) as (
      select d.depends_on_task_id
        from scale_os.task_dependencies_v2 as d
       where d.task_id = p_depends_on_task_id
      union
      select d.depends_on_task_id
        from scale_os.task_dependencies_v2 as d
        join dependency_walk as w on d.task_id = w.task_id
    )
    select 1 from dependency_walk where task_id = p_task_id
  ) then
    return 'DENIED_DEPENDENCY_CYCLE';
  end if;

  insert into scale_os.task_dependencies_v2(task_id, depends_on_task_id)
  values (p_task_id, p_depends_on_task_id)
  on conflict do nothing;

  get diagnostics v_inserted = row_count;
  if v_inserted = 0 then
    return 'REPLAYED';
  end if;

  return 'ADDED';
end;
$$;

create or replace function scale_os.claim_task_lease_v2(
  p_task_id uuid,
  p_worker_id text,
  p_task_digest text,
  p_lease_digest text,
  p_action_digest text,
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
set search_path = scale_os, pg_temp
as $$
declare
  v_status text;
  v_canonical_digest text;
  v_requires_approval boolean;
  v_has_lease boolean := false;
  v_lease scale_os.task_leases_v2%rowtype;
  v_expires bigint;
begin
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

  select t.status, t.task_digest_v2, t.requires_approval
    into v_status, v_canonical_digest, v_requires_approval
    from scale_os.tasks as t
   where t.id = p_task_id
   for update;

  if not found then
    return query select 'DENIED_UNKNOWN_TASK'::text, null::text, null::bigint;
    return;
  end if;

  if v_canonical_digest is null or v_canonical_digest <> p_task_digest then
    return query select 'DENIED_TASK_DIGEST_MISMATCH'::text, null::text, null::bigint;
    return;
  end if;

  if v_requires_approval then
    if p_action_digest is null or p_action_digest !~ '^[0-9a-f]{64}$' then
      return query select 'DENIED_APPROVAL_DIGEST_REQUIRED'::text, null::text, null::bigint;
      return;
    end if;

    if not exists (
      select 1
        from scale_os.approvals as a
       where a.task_id = p_task_id
         and a.decision = 'approved'
         and a.action_digest_v2 = p_action_digest
         and a.approval_packet_v2 is not null
         and a.approval_packet_v2 ->> 'task_id' = p_task_id::text
         and a.grant_id_v2 is not null
         and length(btrim(a.grant_id_v2)) > 0
         and a.decision_at is not null
         and a.grant_expires_at_v2 is not null
         and now() >= a.decision_at
         and now() <= a.grant_expires_at_v2
    ) then
      return query select 'DENIED_APPROVAL_NOT_ADMITTED'::text, null::text, null::bigint;
      return;
    end if;
  elsif p_action_digest is not null then
    return query select 'DENIED_UNEXPECTED_APPROVAL_DIGEST'::text, null::text, null::bigint;
    return;
  end if;

  if exists (
    select 1
      from scale_os.task_dependencies_v2 as d
      join scale_os.tasks as dependency on dependency.id = d.depends_on_task_id
     where d.task_id = p_task_id
       and dependency.status <> 'completed'
  ) then
    return query select 'DENIED_DEPENDENCY_NOT_COMPLETED'::text, null::text, null::bigint;
    return;
  end if;

  select l.*
    into v_lease
    from scale_os.task_leases_v2 as l
   where l.task_id = p_task_id
   for update;
  v_has_lease := found;

  if v_has_lease
     and v_lease.lease_state = 'active'
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

  if v_status = 'running'
     and (
       not v_has_lease
       or (
         v_lease.lease_state = 'active'
         and p_current_generation <= v_lease.expires_generation
       )
     ) then
    return query select 'DENIED_INCONSISTENT_RUNNING'::text, null::text, null::bigint;
    return;
  end if;

  if v_status not in ('queued','running') then
    return query select 'DENIED_TASK_STATE'::text, null::text, null::bigint;
    return;
  end if;

  v_expires := p_current_generation + p_ttl_generations;

  insert into scale_os.task_leases_v2 (
    task_id, worker_id, task_digest, lease_digest,
    acquired_generation, expires_generation, released_generation,
    lease_state, external_authority, authority_effect, updated_at
  ) values (
    p_task_id, p_worker_id, p_task_digest, p_lease_digest,
    p_current_generation, v_expires, null,
    'active', 'NOT_GRANTED', 'NONE', now()
  )
  on conflict (task_id) do update set
    worker_id = excluded.worker_id,
    task_digest = excluded.task_digest,
    lease_digest = excluded.lease_digest,
    acquired_generation = excluded.acquired_generation,
    expires_generation = excluded.expires_generation,
    released_generation = null,
    lease_state = 'active',
    external_authority = 'NOT_GRANTED',
    authority_effect = 'NONE',
    updated_at = now();

  update scale_os.tasks
     set status = 'running',
         generation_v2 = p_current_generation,
         updated_at = now()
   where id = p_task_id;

  return query select 'CLAIMED'::text, p_lease_digest, v_expires;
end;
$$;

create or replace function scale_os.complete_task_lease_v2(
  p_task_id uuid,
  p_worker_id text,
  p_lease_digest text,
  p_current_generation bigint,
  p_terminal_status text,
  p_result jsonb
)
returns text
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
declare
  v_task_status text;
  v_lease scale_os.task_leases_v2%rowtype;
begin
  if p_terminal_status not in ('completed','failed','quarantined') then
    raise exception 'invalid terminal status';
  end if;
  if p_worker_id is null or length(btrim(p_worker_id)) = 0 then
    raise exception 'worker_id required';
  end if;
  if p_lease_digest is null or p_lease_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid lease_digest';
  end if;
  if p_current_generation is null or p_current_generation < 0 then
    raise exception 'invalid current_generation';
  end if;
  if p_result is null then
    raise exception 'result required';
  end if;

  select t.status
    into v_task_status
    from scale_os.tasks as t
   where t.id = p_task_id
   for update;

  if not found or v_task_status <> 'running' then
    return 'DENIED_TASK_STATE';
  end if;

  select l.*
    into v_lease
    from scale_os.task_leases_v2 as l
   where l.task_id = p_task_id
   for update;

  if not found then
    return 'DENIED_LEASE_MISSING';
  end if;
  if v_lease.lease_state <> 'active' then
    return 'DENIED_LEASE_INACTIVE';
  end if;
  if v_lease.worker_id <> p_worker_id or v_lease.lease_digest <> p_lease_digest then
    return 'DENIED_LEASE_FENCE';
  end if;
  if p_current_generation < v_lease.acquired_generation
     or p_current_generation > v_lease.expires_generation then
    return 'DENIED_LEASE_EXPIRED';
  end if;

  update scale_os.tasks
     set status = p_terminal_status,
         result = p_result,
         generation_v2 = p_current_generation,
         updated_at = now()
   where id = p_task_id;

  update scale_os.task_leases_v2
     set lease_state = 'released',
         released_generation = p_current_generation,
         updated_at = now()
   where task_id = p_task_id;

  return 'COMPLETED';
end;
$$;

revoke all on function scale_os.create_task_v2(
  text, text, boolean, text, text, jsonb, text, text, bigint
) from public, anon, authenticated;

revoke all on function scale_os.add_task_dependency_v2(
  uuid, uuid
) from public, anon, authenticated;

revoke all on function scale_os.claim_task_lease_v2(
  uuid, text, text, text, text, bigint, bigint
) from public, anon, authenticated;

revoke all on function scale_os.complete_task_lease_v2(
  uuid, text, text, bigint, text, jsonb
) from public, anon, authenticated;

grant execute on function scale_os.create_task_v2(
  text, text, boolean, text, text, jsonb, text, text, bigint
) to service_role;

grant execute on function scale_os.add_task_dependency_v2(
  uuid, uuid
) to service_role;

grant execute on function scale_os.claim_task_lease_v2(
  uuid, text, text, text, text, bigint, bigint
) to service_role;

grant execute on function scale_os.complete_task_lease_v2(
  uuid, text, text, bigint, text, jsonb
) to service_role;

alter function scale_os.prevent_direct_v2_approval_mutation_v2()
  owner to postgres;

alter function scale_os.prevent_direct_v2_task_mutation_v2()
  owner to postgres;

alter function scale_os.create_task_v2(
  text, text, boolean, text, text, jsonb, text, text, bigint
) owner to postgres;

alter function scale_os.add_task_dependency_v2(
  uuid, uuid
) owner to postgres;

alter function scale_os.claim_task_lease_v2(
  uuid, text, text, text, text, bigint, bigint
) owner to postgres;

alter function scale_os.complete_task_lease_v2(
  uuid, text, text, bigint, text, jsonb
) owner to postgres;
