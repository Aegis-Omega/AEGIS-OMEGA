-- AEGIS Cloud SQL authoritative constitutional audit chain V1
-- SOURCE ONLY. Do not apply automatically from application startup.
-- Target: aegisomegav1 / us-central1 / aegis-audit-db / database "default".
-- The Cloud Run IAM DB user must be granted aegis_audit_writer separately.

create schema if not exists aegis_audit;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'aegis_audit_writer') then
    create role aegis_audit_writer nologin;
  end if;
end;
$$;

create table if not exists aegis_audit.constitutional_chain_head_v1 (
  chain_id text primary key,
  next_sequence bigint not null check (next_sequence >= 0),
  terminal_hash text not null check (terminal_hash ~ '^[0-9a-f]{64}$'),
  updated_at timestamptz not null default now()
);

insert into aegis_audit.constitutional_chain_head_v1 (
  chain_id,
  next_sequence,
  terminal_hash
) values (
  'constitutional',
  0,
  repeat('0', 64)
)
on conflict (chain_id) do nothing;

create table if not exists aegis_audit.constitutional_chain_v1 (
  sequence bigint primary key check (sequence >= 0),
  previous_entry_hash text not null
    check (previous_entry_hash ~ '^[0-9a-f]{64}$'),
  entry_hash text not null unique
    check (entry_hash ~ '^[0-9a-f]{64}$'),
  observation jsonb not null,
  tier text not null check (length(btrim(tier)) > 0),
  timestamp_ms bigint not null check (timestamp_ms >= 0),
  inserted_at timestamptz not null default now()
);

create index if not exists constitutional_chain_v1_inserted_at_idx
  on aegis_audit.constitutional_chain_v1(inserted_at);

create or replace function aegis_audit.reject_constitutional_chain_mutation_v1()
returns trigger
language plpgsql
set search_path = aegis_audit, pg_temp
as $$
begin
  raise exception 'constitutional audit entries are append-only';
end;
$$;

drop trigger if exists constitutional_chain_v1_append_only
  on aegis_audit.constitutional_chain_v1;

create trigger constitutional_chain_v1_append_only
before update or delete on aegis_audit.constitutional_chain_v1
for each row execute function aegis_audit.reject_constitutional_chain_mutation_v1();

create or replace function aegis_audit.append_constitutional_entry_v1(
  p_sequence bigint,
  p_previous_entry_hash text,
  p_entry_hash text,
  p_observation jsonb,
  p_tier text,
  p_timestamp_ms bigint
)
returns boolean
language plpgsql
security definer
set search_path = aegis_audit, pg_temp
as $$
declare
  v_next_sequence bigint;
  v_terminal_hash text;
begin
  if p_sequence is null or p_sequence < 0 then
    raise exception 'invalid sequence';
  end if;
  if p_previous_entry_hash is null
     or p_previous_entry_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid previous_entry_hash';
  end if;
  if p_entry_hash is null
     or p_entry_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid entry_hash';
  end if;
  if p_observation is null then
    raise exception 'observation required';
  end if;
  if p_tier is null or length(btrim(p_tier)) = 0 then
    raise exception 'tier required';
  end if;
  if p_timestamp_ms is null or p_timestamp_ms < 0 then
    raise exception 'invalid timestamp_ms';
  end if;

  select next_sequence, terminal_hash
    into v_next_sequence, v_terminal_hash
    from aegis_audit.constitutional_chain_head_v1
   where chain_id = 'constitutional'
   for update;

  if not found then
    raise exception 'constitutional chain head missing';
  end if;

  if p_sequence <> v_next_sequence
     or p_previous_entry_hash <> v_terminal_hash then
    return false;
  end if;

  insert into aegis_audit.constitutional_chain_v1 (
    sequence,
    previous_entry_hash,
    entry_hash,
    observation,
    tier,
    timestamp_ms
  ) values (
    p_sequence,
    p_previous_entry_hash,
    p_entry_hash,
    p_observation,
    p_tier,
    p_timestamp_ms
  );

  update aegis_audit.constitutional_chain_head_v1
     set next_sequence = p_sequence + 1,
         terminal_hash = p_entry_hash,
         updated_at = now()
   where chain_id = 'constitutional';

  return true;
end;
$$;

revoke all on schema aegis_audit from public;
revoke all on all tables in schema aegis_audit from public;
revoke execute on all functions in schema aegis_audit from public;

grant usage on schema aegis_audit to aegis_audit_writer;
grant select on aegis_audit.constitutional_chain_v1 to aegis_audit_writer;
grant select on aegis_audit.constitutional_chain_head_v1 to aegis_audit_writer;
grant execute on function aegis_audit.append_constitutional_entry_v1(
  bigint,
  text,
  text,
  jsonb,
  text,
  bigint
) to aegis_audit_writer;

alter default privileges in schema aegis_audit
  revoke all on tables from public;
alter default privileges in schema aegis_audit
  revoke execute on functions from public;

-- REQUIRED SEPARATE BINDING (operator/deploy step, not encoded here):
-- GRANT aegis_audit_writer TO "<cloud-run-service-account-without-.gserviceaccount.com>";
