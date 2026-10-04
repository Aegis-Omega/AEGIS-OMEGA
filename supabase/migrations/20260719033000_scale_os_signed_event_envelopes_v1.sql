-- AEGIS Scale OS signed control-plane schema v1.
-- Repository migration only: applying this file is a separate consequential action.
-- Cryptographic validation occurs before insert; PostgreSQL enforces append-only
-- identity, sequence, idempotency, hash-shape, and projection invariants.

create schema if not exists aegis_private;

create table if not exists public.scale_os_event_envelopes_v1 (
  event_id text primary key,
  schema_version text not null check (schema_version = '1.0.0'),
  event_type text not null check (event_type in (
    'REQUEST_CREATED',
    'REQUEST_VALIDATED',
    'APPROVAL_REQUESTED',
    'APPROVAL_GRANTED',
    'APPROVAL_DENIED',
    'APPROVAL_REVOKED',
    'APPROVAL_EXPIRED',
    'EXECUTION_STARTED',
    'EXECUTION_SUCCEEDED',
    'EXECUTION_FAILED',
    'EXECUTION_REVERTED',
    'VERIFICATION_RECORDED'
  )),
  aggregate_id text not null,
  sequence numeric(39, 0) not null check (sequence >= 0),
  previous_event_hash text,
  source_object_hash text not null,
  payload_hash text not null,
  idempotency_key text not null unique,
  correlation_id text not null,
  causation_id text,
  emitted_at timestamptz not null,
  identities jsonb not null,
  signer_key_id text not null,
  signer_public_key text not null,
  signature text not null,
  event_hash text not null unique,
  inserted_at timestamptz not null default now(),
  unique (aggregate_id, sequence),
  check (
    (sequence = 0 and previous_event_hash is null) or
    (sequence > 0 and previous_event_hash ~ '^[0-9a-f]{64}$')
  ),
  check (source_object_hash ~ '^[0-9a-f]{64}$'),
  check (payload_hash ~ '^[0-9a-f]{64}$'),
  check (event_hash ~ '^[0-9a-f]{64}$'),
  check (signer_public_key ~ '^[0-9a-f]{64}$'),
  check (signature ~ '^[0-9a-f]{128}$'),
  check (jsonb_typeof(identities) = 'object'),
  check (identities ? 'request'),
  check (identities ? 'approval'),
  check (identities ? 'execution'),
  check (identities ? 'verification')
);

create index if not exists scale_os_event_envelopes_v1_aggregate_order_idx
  on public.scale_os_event_envelopes_v1 (aggregate_id, sequence);

create index if not exists scale_os_event_envelopes_v1_correlation_idx
  on public.scale_os_event_envelopes_v1 (correlation_id);

create table if not exists public.scale_os_approval_projection_v1 (
  aggregate_id text primary key,
  approval_state text not null check (approval_state in (
    'REQUESTED',
    'VALIDATED',
    'PENDING_OPERATOR',
    'APPROVED',
    'EXECUTING',
    'SUCCEEDED',
    'DENIED',
    'EXPIRED',
    'REVOKED',
    'FAILED',
    'REVERTED'
  )),
  sequence numeric(39, 0) not null check (sequence >= 0),
  head_event_hash text not null unique check (head_event_hash ~ '^[0-9a-f]{64}$'),
  applied_event_count numeric(39, 0) not null check (applied_event_count > 0),
  last_event_type text not null,
  updated_at timestamptz not null,
  terminal boolean generated always as (
    approval_state in ('SUCCEEDED', 'DENIED', 'EXPIRED', 'REVOKED', 'FAILED', 'REVERTED')
  ) stored
);

create or replace function aegis_private.reject_scale_os_event_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog
as $$
begin
  raise exception 'scale_os_event_envelopes_v1 is append-only';
end;
$$;

drop trigger if exists scale_os_event_envelopes_v1_append_only
  on public.scale_os_event_envelopes_v1;

create trigger scale_os_event_envelopes_v1_append_only
before update or delete on public.scale_os_event_envelopes_v1
for each row execute function aegis_private.reject_scale_os_event_mutation_v1();

alter table public.scale_os_event_envelopes_v1 enable row level security;
alter table public.scale_os_approval_projection_v1 enable row level security;

revoke all on table public.scale_os_event_envelopes_v1 from anon, authenticated;
revoke all on table public.scale_os_approval_projection_v1 from anon, authenticated;
revoke all on function aegis_private.reject_scale_os_event_mutation_v1() from public;

comment on table public.scale_os_event_envelopes_v1 is
  'Immutable, Ed25519-signed AEGIS Scale OS control-plane events. Inserts require independent application-layer cryptographic verification.';

comment on table public.scale_os_approval_projection_v1 is
  'Deterministic projection of explicit Scale OS approval transitions. This table is derived state and never authorization by itself.';
