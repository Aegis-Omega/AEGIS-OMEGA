-- AEGIS Automaton-3 PostgreSQL durability contract v1.
-- SOURCE CONTRACT ONLY: applying this file is a separate consequential action.
--
-- Goal: preserve the in-memory Automaton-3 lease/durable semantics across hosts by
-- moving the concurrency boundary into PostgreSQL transactions. This file does not
-- claim distributed exactly-once execution. External effects remain at-least-once
-- transport with idempotent, atomically claimed effect keys.
--
-- Security posture:
--   * private schema only;
--   * SECURITY INVOKER (PostgreSQL default) functions only;
--   * no EXECUTE/table/schema privileges are granted here;
--   * PUBLIC privileges are revoked explicitly;
--   * a deployment must grant the minimum functions/tables to a dedicated runtime role.

create schema if not exists aegis_private;
revoke all on schema aegis_private from public;

create table if not exists aegis_private.a3_writer_generations_v1 (
  authority_domain text primary key,
  generation bigint not null default 0 check (generation >= 0)
);

create table if not exists aegis_private.a3_writer_leases_v1 (
  authority_domain text primary key,
  holder_identity_root text not null check (holder_identity_root ~ '^[0-9a-f]{64}$'),
  source_commit text not null check (source_commit ~ '^[0-9a-f]{40,64}$'),
  lease_generation bigint not null check (lease_generation > 0),
  fencing_token text not null check (fencing_token ~ '^[0-9a-f]{64}$'),
  expected_parent_state text not null check (expected_parent_state ~ '^[0-9a-f]{64}$'),
  unique (authority_domain, lease_generation),
  unique (fencing_token)
);

create table if not exists aegis_private.a3_authoritative_action_claims_v1 (
  authority_domain text not null,
  lease_generation bigint not null check (lease_generation > 0),
  action_digest text not null check (action_digest ~ '^[0-9a-f]{64}$'),
  primary key (authority_domain, lease_generation, action_digest)
);

create table if not exists aegis_private.a3_durable_executions_v1 (
  execution_id text primary key,
  workflow_identity text not null,
  owner text not null,
  source_commit text not null check (source_commit ~ '^[0-9a-f]{40,64}$'),
  workspace_binding text not null check (workspace_binding ~ '^[0-9a-f]{64}$'),
  current_phase text not null,
  current_authority text[] not null default '{}',
  last_completed_transition bigint not null default 0 check (last_completed_transition >= 0),
  pending_external_action text not null default '',
  retry_count bigint not null default 0 check (retry_count >= 0),
  next_retry bigint,
  cancellation_state text not null,
  lease_holder text not null check (lease_holder ~ '^[0-9a-f]{64}$'),
  parent_state_root text not null check (parent_state_root ~ '^[0-9a-f]{64}$'),
  current_receipt_root text not null check (current_receipt_root ~ '^[0-9a-f]{64}$'),
  failure_state text not null default '',
  status text not null check (status in (
    'PLANNED', 'ADMITTED', 'RUNNING', 'WAITING_FOR_APPROVAL', 'BLOCKED',
    'RETRYING', 'DENIED', 'COMPLETED', 'CANCELLED', 'ORPHANED'
  )),
  last_heartbeat_generation bigint not null default 0 check (last_heartbeat_generation >= 0),
  row_revision bigint not null default 0 check (row_revision >= 0)
);

create table if not exists aegis_private.a3_external_action_claims_v1 (
  execution_id text not null references aegis_private.a3_durable_executions_v1(execution_id) on delete restrict,
  idempotency_key text not null,
  primary key (execution_id, idempotency_key)
);

create index if not exists a3_external_action_claims_execution_idx
  on aegis_private.a3_external_action_claims_v1 (execution_id);

create or replace function aegis_private.a3_writer_snapshot_v1(
  p_authority_domain text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_generation bigint := 0;
  v_lease aegis_private.a3_writer_leases_v1%rowtype;
begin
  select generation
    into v_generation
    from aegis_private.a3_writer_generations_v1
   where authority_domain = p_authority_domain;

  select *
    into v_lease
    from aegis_private.a3_writer_leases_v1
   where authority_domain = p_authority_domain;

  return jsonb_build_object(
    'generation', coalesce(v_generation, 0),
    'active', v_lease.authority_domain is not null,
    'authority_domain', v_lease.authority_domain,
    'holder_identity_root', v_lease.holder_identity_root,
    'source_commit', v_lease.source_commit,
    'lease_generation', v_lease.lease_generation,
    'fencing_token', v_lease.fencing_token,
    'expected_parent_state', v_lease.expected_parent_state
  );
end;
$$;

create or replace function aegis_private.a3_try_acquire_writer_v1(
  p_authority_domain text,
  p_holder_identity_root text,
  p_source_commit text,
  p_expected_parent_state text,
  p_expected_previous_generation bigint,
  p_fencing_token text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_generation bigint;
  v_next_generation bigint;
begin
  if p_holder_identity_root !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'code', 'holder_identity_root:INVALID_SHA256');
  end if;
  if p_source_commit !~ '^[0-9a-f]{40,64}$' then
    return jsonb_build_object('ok', false, 'code', 'source_commit:INVALID_GIT_OBJECT');
  end if;
  if p_expected_parent_state !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'code', 'expected_parent_state:INVALID_SHA256');
  end if;
  if p_fencing_token !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'code', 'fencing_token:INVALID_SHA256');
  end if;
  if p_expected_previous_generation < 0 then
    return jsonb_build_object('ok', false, 'code', 'LEASE_GENERATION_INVALID');
  end if;

  insert into aegis_private.a3_writer_generations_v1(authority_domain, generation)
  values (p_authority_domain, 0)
  on conflict (authority_domain) do nothing;

  select generation
    into v_generation
    from aegis_private.a3_writer_generations_v1
   where authority_domain = p_authority_domain
   for update;

  -- The generation row is the serialization lock for one authority domain.
  if exists (
    select 1
      from aegis_private.a3_writer_leases_v1
     where authority_domain = p_authority_domain
  ) then
    return jsonb_build_object(
      'ok', false,
      'code', 'WRITER_ALREADY_ACTIVE',
      'lease_generation', v_generation + 1
    );
  end if;

  if v_generation <> p_expected_previous_generation then
    return jsonb_build_object(
      'ok', false,
      'code', 'STALE_LEASE_GENERATION',
      'lease_generation', v_generation + 1
    );
  end if;

  v_next_generation := v_generation + 1;

  update aegis_private.a3_writer_generations_v1
     set generation = v_next_generation
   where authority_domain = p_authority_domain;

  insert into aegis_private.a3_writer_leases_v1(
    authority_domain,
    holder_identity_root,
    source_commit,
    lease_generation,
    fencing_token,
    expected_parent_state
  ) values (
    p_authority_domain,
    p_holder_identity_root,
    p_source_commit,
    v_next_generation,
    p_fencing_token,
    p_expected_parent_state
  );

  return jsonb_build_object(
    'ok', true,
    'code', 'NONE',
    'lease_generation', v_next_generation,
    'fencing_token', p_fencing_token,
    'expected_parent_state', p_expected_parent_state
  );
end;
$$;

create or replace function aegis_private.a3_authorize_write_v1(
  p_authority_domain text,
  p_holder_identity_root text,
  p_fencing_token text,
  p_lease_generation bigint,
  p_expected_parent_state text,
  p_action_digest text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_lease aegis_private.a3_writer_leases_v1%rowtype;
  v_reasons text[] := '{}';
begin
  select *
    into v_lease
    from aegis_private.a3_writer_leases_v1
   where authority_domain = p_authority_domain
   for update;

  if v_lease.authority_domain is null then
    v_reasons := array_append(v_reasons, 'LEASE_MISSING');
  else
    if v_lease.holder_identity_root <> p_holder_identity_root then
      v_reasons := array_append(v_reasons, 'LEASE_HOLDER_MISMATCH');
    end if;
    if v_lease.fencing_token <> p_fencing_token then
      v_reasons := array_append(v_reasons, 'STALE_FENCING_TOKEN');
    end if;
    if v_lease.lease_generation <> p_lease_generation then
      v_reasons := array_append(v_reasons, 'STALE_LEASE_GENERATION');
    end if;
    if v_lease.expected_parent_state <> p_expected_parent_state then
      v_reasons := array_append(v_reasons, 'PARENT_STATE_MISMATCH');
    end if;
  end if;

  if p_action_digest !~ '^[0-9a-f]{64}$' then
    v_reasons := array_append(v_reasons, 'action_digest:INVALID_SHA256');
  elsif exists (
    select 1
      from aegis_private.a3_authoritative_action_claims_v1
     where authority_domain = p_authority_domain
       and lease_generation = p_lease_generation
       and action_digest = p_action_digest
  ) then
    v_reasons := array_append(v_reasons, 'REPLAYED_AUTHORITATIVE_ACTION');
  end if;

  if cardinality(v_reasons) > 0 then
    return jsonb_build_object('ok', false, 'codes', to_jsonb(v_reasons));
  end if;

  insert into aegis_private.a3_authoritative_action_claims_v1(
    authority_domain, lease_generation, action_digest
  ) values (
    p_authority_domain, p_lease_generation, p_action_digest
  );

  return jsonb_build_object('ok', true, 'codes', '[]'::jsonb);
end;
$$;

create or replace function aegis_private.a3_advance_writer_v1(
  p_authority_domain text,
  p_fencing_token text,
  p_new_parent_state text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_lease aegis_private.a3_writer_leases_v1%rowtype;
begin
  select *
    into v_lease
    from aegis_private.a3_writer_leases_v1
   where authority_domain = p_authority_domain
   for update;

  if v_lease.authority_domain is null then
    return jsonb_build_object('ok', false, 'code', 'LEASE_MISSING', 'lease_generation', 0);
  end if;
  if v_lease.fencing_token <> p_fencing_token then
    return jsonb_build_object(
      'ok', false, 'code', 'STALE_FENCING_TOKEN',
      'lease_generation', v_lease.lease_generation
    );
  end if;
  if p_new_parent_state !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object(
      'ok', false, 'code', 'new_parent_state:INVALID_SHA256',
      'lease_generation', v_lease.lease_generation
    );
  end if;

  update aegis_private.a3_writer_leases_v1
     set expected_parent_state = p_new_parent_state
   where authority_domain = p_authority_domain;

  return jsonb_build_object(
    'ok', true, 'code', 'NONE',
    'lease_generation', v_lease.lease_generation
  );
end;
$$;

create or replace function aegis_private.a3_revoke_writer_v1(
  p_authority_domain text,
  p_holder_identity_root text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_lease aegis_private.a3_writer_leases_v1%rowtype;
begin
  select *
    into v_lease
    from aegis_private.a3_writer_leases_v1
   where authority_domain = p_authority_domain
   for update;

  if v_lease.authority_domain is null then
    return jsonb_build_object('ok', false, 'code', 'LEASE_MISSING', 'lease_generation', 0);
  end if;
  if v_lease.holder_identity_root <> p_holder_identity_root then
    return jsonb_build_object(
      'ok', false, 'code', 'LEASE_HOLDER_MISMATCH',
      'lease_generation', v_lease.lease_generation,
      'fencing_token', v_lease.fencing_token
    );
  end if;

  delete from aegis_private.a3_writer_leases_v1
   where authority_domain = p_authority_domain;

  return jsonb_build_object(
    'ok', true, 'code', 'NONE',
    'lease_generation', v_lease.lease_generation,
    'fencing_token', v_lease.fencing_token
  );
end;
$$;

create or replace function aegis_private.a3_register_execution_v1(
  p_execution_id text,
  p_workflow_identity text,
  p_owner text,
  p_source_commit text,
  p_workspace_binding text,
  p_current_phase text,
  p_current_authority text[],
  p_last_completed_transition bigint,
  p_pending_external_action text,
  p_retry_count bigint,
  p_next_retry bigint,
  p_cancellation_state text,
  p_lease_holder text,
  p_parent_state_root text,
  p_current_receipt_root text,
  p_failure_state text,
  p_status text,
  p_last_heartbeat_generation bigint
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_inserted integer;
begin
  if p_status <> 'PLANNED' then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_MUST_REGISTER_AS_PLANNED');
  end if;

  insert into aegis_private.a3_durable_executions_v1(
    execution_id, workflow_identity, owner, source_commit, workspace_binding,
    current_phase, current_authority, last_completed_transition,
    pending_external_action, retry_count, next_retry, cancellation_state,
    lease_holder, parent_state_root, current_receipt_root, failure_state,
    status, last_heartbeat_generation
  ) values (
    p_execution_id, p_workflow_identity, p_owner, p_source_commit, p_workspace_binding,
    p_current_phase, coalesce(p_current_authority, '{}'), p_last_completed_transition,
    p_pending_external_action, p_retry_count, p_next_retry, p_cancellation_state,
    p_lease_holder, p_parent_state_root, p_current_receipt_root, p_failure_state,
    p_status, p_last_heartbeat_generation
  )
  on conflict (execution_id) do nothing;

  get diagnostics v_inserted = row_count;
  if v_inserted <> 1 then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_EXECUTION_ALREADY_REGISTERED');
  end if;

  return jsonb_build_object('ok', true, 'code', 'NONE');
exception
  when check_violation then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_RECORD_INVALID');
end;
$$;

create or replace function aegis_private.a3_transition_execution_v1(
  p_execution_id text,
  p_status text,
  p_phase text,
  p_transition_sequence bigint,
  p_receipt_root text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_record aegis_private.a3_durable_executions_v1%rowtype;
begin
  select *
    into v_record
    from aegis_private.a3_durable_executions_v1
   where execution_id = p_execution_id
   for update;

  if v_record.execution_id is null then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_EXECUTION_UNKNOWN');
  end if;
  if v_record.status in ('CANCELLED', 'COMPLETED', 'ORPHANED') then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_TERMINAL_STATE');
  end if;
  if p_status not in (
    'PLANNED', 'ADMITTED', 'RUNNING', 'WAITING_FOR_APPROVAL', 'BLOCKED',
    'RETRYING', 'DENIED', 'COMPLETED', 'CANCELLED', 'ORPHANED'
  ) then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_STATUS_INVALID');
  end if;
  if p_transition_sequence <> v_record.last_completed_transition + 1 then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_SEQUENCE_INVALID');
  end if;
  if p_receipt_root !~ '^[0-9a-f]{64}$' then
    return jsonb_build_object('ok', false, 'code', 'receipt_root:INVALID_SHA256');
  end if;

  update aegis_private.a3_durable_executions_v1
     set status = p_status,
         current_phase = p_phase,
         last_completed_transition = p_transition_sequence,
         current_receipt_root = p_receipt_root,
         row_revision = row_revision + 1
   where execution_id = p_execution_id;

  return jsonb_build_object('ok', true, 'code', 'NONE');
end;
$$;

create or replace function aegis_private.a3_heartbeat_execution_v1(
  p_execution_id text,
  p_generation bigint
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_record aegis_private.a3_durable_executions_v1%rowtype;
begin
  select *
    into v_record
    from aegis_private.a3_durable_executions_v1
   where execution_id = p_execution_id
   for update;

  if v_record.execution_id is null then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_EXECUTION_UNKNOWN');
  end if;
  if p_generation <= v_record.last_heartbeat_generation then
    return jsonb_build_object('ok', false, 'code', 'HEARTBEAT_NOT_MONOTONE');
  end if;

  update aegis_private.a3_durable_executions_v1
     set last_heartbeat_generation = p_generation,
         row_revision = row_revision + 1
   where execution_id = p_execution_id;

  return jsonb_build_object('ok', true, 'code', 'NONE');
end;
$$;

create or replace function aegis_private.a3_claim_external_action_v1(
  p_execution_id text,
  p_idempotency_key text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_record aegis_private.a3_durable_executions_v1%rowtype;
  v_inserted integer;
begin
  select *
    into v_record
    from aegis_private.a3_durable_executions_v1
   where execution_id = p_execution_id
   for update;

  if v_record.execution_id is null then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_EXECUTION_UNKNOWN');
  end if;
  if v_record.status not in ('RUNNING', 'RETRYING') then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_NOT_RUNNING');
  end if;
  if p_idempotency_key is null or p_idempotency_key = '' or length(p_idempotency_key) > 512 then
    return jsonb_build_object('ok', false, 'code', 'idempotency_key:INVALID_AUTHORITY_STRING');
  end if;

  insert into aegis_private.a3_external_action_claims_v1(execution_id, idempotency_key)
  values (p_execution_id, p_idempotency_key)
  on conflict do nothing;

  get diagnostics v_inserted = row_count;
  if v_inserted <> 1 then
    return jsonb_build_object('ok', false, 'code', 'DUPLICATE_EXTERNAL_ACTION');
  end if;

  update aegis_private.a3_durable_executions_v1
     set pending_external_action = p_idempotency_key,
         row_revision = row_revision + 1
   where execution_id = p_execution_id;

  return jsonb_build_object('ok', true, 'code', 'NONE');
end;
$$;

create or replace function aegis_private.a3_cancel_execution_v1(
  p_execution_id text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_record aegis_private.a3_durable_executions_v1%rowtype;
begin
  select *
    into v_record
    from aegis_private.a3_durable_executions_v1
   where execution_id = p_execution_id
   for update;

  if v_record.execution_id is null then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_EXECUTION_UNKNOWN');
  end if;

  update aegis_private.a3_durable_executions_v1
     set status = 'CANCELLED',
         cancellation_state = 'REVOKED',
         current_authority = '{}',
         row_revision = row_revision + 1
   where execution_id = p_execution_id;

  -- Same transaction: revoke only leases actually held by this execution identity.
  delete from aegis_private.a3_writer_leases_v1
   where authority_domain = any(v_record.current_authority)
     and holder_identity_root = v_record.lease_holder;

  return jsonb_build_object('ok', true, 'code', 'NONE');
end;
$$;

create or replace function aegis_private.a3_mark_orphaned_v1(
  p_execution_id text,
  p_current_generation bigint,
  p_maximum_gap bigint
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_record aegis_private.a3_durable_executions_v1%rowtype;
begin
  select *
    into v_record
    from aegis_private.a3_durable_executions_v1
   where execution_id = p_execution_id
   for update;

  if v_record.execution_id is null then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_EXECUTION_UNKNOWN');
  end if;
  if p_current_generation - v_record.last_heartbeat_generation <= p_maximum_gap then
    return jsonb_build_object('ok', false, 'code', 'ORPHAN_THRESHOLD_NOT_REACHED');
  end if;

  update aegis_private.a3_durable_executions_v1
     set status = 'ORPHANED',
         current_authority = '{}',
         row_revision = row_revision + 1
   where execution_id = p_execution_id;

  delete from aegis_private.a3_writer_leases_v1
   where authority_domain = any(v_record.current_authority)
     and holder_identity_root = v_record.lease_holder;

  return jsonb_build_object('ok', true, 'code', 'NONE');
end;
$$;

create or replace function aegis_private.a3_execution_snapshot_v1(
  p_execution_id text
) returns jsonb
language plpgsql
set search_path = pg_catalog, aegis_private
as $$
declare
  v_record aegis_private.a3_durable_executions_v1%rowtype;
  v_actions jsonb;
begin
  select *
    into v_record
    from aegis_private.a3_durable_executions_v1
   where execution_id = p_execution_id;

  if v_record.execution_id is null then
    return jsonb_build_object('ok', false, 'code', 'DURABLE_EXECUTION_UNKNOWN');
  end if;

  select coalesce(jsonb_agg(idempotency_key order by idempotency_key), '[]'::jsonb)
    into v_actions
    from aegis_private.a3_external_action_claims_v1
   where execution_id = p_execution_id;

  return jsonb_build_object(
    'ok', true,
    'code', 'NONE',
    'record', jsonb_build_object(
      'workflow_identity', v_record.workflow_identity,
      'owner', v_record.owner,
      'source_commit', v_record.source_commit,
      'workspace_binding', v_record.workspace_binding,
      'current_phase', v_record.current_phase,
      'current_authority', to_jsonb(v_record.current_authority),
      'last_completed_transition', v_record.last_completed_transition,
      'pending_external_action', v_record.pending_external_action,
      'retry_count', v_record.retry_count,
      'next_retry', v_record.next_retry,
      'cancellation_state', v_record.cancellation_state,
      'lease_holder', v_record.lease_holder,
      'parent_state_root', v_record.parent_state_root,
      'current_receipt_root', v_record.current_receipt_root,
      'failure_state', v_record.failure_state,
      'status', v_record.status,
      'last_heartbeat_generation', v_record.last_heartbeat_generation,
      'used_external_actions', v_actions
    ),
    'row_revision', v_record.row_revision
  );
end;
$$;

revoke all on table aegis_private.a3_writer_generations_v1 from public;
revoke all on table aegis_private.a3_writer_leases_v1 from public;
revoke all on table aegis_private.a3_authoritative_action_claims_v1 from public;
revoke all on table aegis_private.a3_durable_executions_v1 from public;
revoke all on table aegis_private.a3_external_action_claims_v1 from public;

revoke all on function aegis_private.a3_writer_snapshot_v1(text) from public;
revoke all on function aegis_private.a3_try_acquire_writer_v1(text, text, text, text, bigint, text) from public;
revoke all on function aegis_private.a3_authorize_write_v1(text, text, text, bigint, text, text) from public;
revoke all on function aegis_private.a3_advance_writer_v1(text, text, text) from public;
revoke all on function aegis_private.a3_revoke_writer_v1(text, text) from public;
revoke all on function aegis_private.a3_register_execution_v1(text, text, text, text, text, text, text[], bigint, text, bigint, bigint, text, text, text, text, text, text, bigint) from public;
revoke all on function aegis_private.a3_transition_execution_v1(text, text, text, bigint, text) from public;
revoke all on function aegis_private.a3_heartbeat_execution_v1(text, bigint) from public;
revoke all on function aegis_private.a3_claim_external_action_v1(text, text) from public;
revoke all on function aegis_private.a3_cancel_execution_v1(text) from public;
revoke all on function aegis_private.a3_mark_orphaned_v1(text, bigint, bigint) from public;
revoke all on function aegis_private.a3_execution_snapshot_v1(text) from public;
