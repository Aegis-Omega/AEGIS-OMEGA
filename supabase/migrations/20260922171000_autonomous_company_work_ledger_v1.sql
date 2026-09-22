-- AEGIS Ω autonomous company durable work ledger v1
-- Repository migration only. Not applied by this PR.
-- authority_effect = NONE

create table if not exists public.company_objectives_v1 (
  id uuid primary key default gen_random_uuid(),
  objective text not null check (length(btrim(objective)) > 0),
  status text not null default 'ACTIVE'
    check (status in ('ACTIVE','PAUSED','COMPLETED','CANCELLED')),
  source_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.company_tasks_v1 (
  task_id text primary key check (length(btrim(task_id)) > 0),
  objective_id uuid references public.company_objectives_v1(id) on delete cascade,
  parent_task_id text references public.company_tasks_v1(task_id) on delete restrict,
  department text not null check (length(btrim(department)) > 0),
  objective text not null check (length(btrim(objective)) > 0),
  action_class text not null check (action_class in (
    'RESEARCH_READ','ANALYZE','DRAFT','LOCAL_SANDBOX_WRITE','TEST','EVAL','PROPOSE',
    'EXTERNAL_MESSAGE','REPOSITORY_MUTATION','MERGE','DEPLOY','PRODUCTION_CONFIG',
    'FINANCIAL','LEGAL_COMMITMENT','DELETE_DATA','IDENTITY_OR_CREDENTIAL'
  )),
  status text not null default 'PLANNED' check (status in (
    'PLANNED','RUNNING','AWAITING_OPERATOR','VERIFIED','REJECTED','CANCELLED'
  )),
  model text,
  provider_id text,
  execution_hash text check (
    execution_hash is null or execution_hash ~ '^[0-9a-f]{64}$'
  ),
  verification_hash text check (
    verification_hash is null or verification_hash ~ '^[0-9a-f]{64}$'
  ),
  receipt_root text check (
    receipt_root is null or receipt_root ~ '^[0-9a-f]{64}$'
  ),
  authority_effect text not null default 'NONE'
    check (authority_effect = 'NONE'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.company_evidence_v1 (
  id bigint generated always as identity primary key,
  task_id text not null
    references public.company_tasks_v1(task_id) on delete cascade,
  kind text not null check (length(btrim(kind)) > 0),
  source_ref text,
  evidence_authority text not null check (evidence_authority in (
    'DIRECT_OBSERVATION','PROVIDER_ATTESTATION','DERIVED_FROM_VERIFIED','UNVERIFIED'
  )),
  measurement_state text check (
    measurement_state is null or
    measurement_state in ('MEASURED','NOT_MEASURED','NOT_VERIFIED')
  ),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (task_id, sha256),
  check (
    measurement_state is null
    or measurement_state <> 'MEASURED'
    or evidence_authority <> 'UNVERIFIED'
  )
);

create table if not exists public.company_operator_actions_v1 (
  id uuid primary key default gen_random_uuid(),
  task_id text not null
    references public.company_tasks_v1(task_id) on delete cascade,
  packet_id text not null check (length(btrim(packet_id)) > 0),
  packet_digest text not null unique
    check (packet_digest ~ '^[0-9a-f]{64}$'),
  packet jsonb not null,
  risk_class text not null
    check (risk_class in ('LOW','MEDIUM','HIGH','CRITICAL')),
  cost_class text not null
    check (cost_class in ('NONE','BOUNDED','VARIABLE')),
  max_cost_minor_units bigint,
  currency text,
  rollback text not null check (length(btrim(rollback)) > 0),
  expires_generation bigint not null check (expires_generation >= 0),
  decision text not null default 'PENDING'
    check (decision in ('PENDING','APPROVED','DENIED','EXPIRED','CANCELLED')),
  grant_id text,
  granted_generation bigint
    check (granted_generation is null or granted_generation >= 0),
  decided_at timestamptz,
  decision_receipt_root text check (
    decision_receipt_root is null or
    decision_receipt_root ~ '^[0-9a-f]{64}$'
  ),
  created_at timestamptz not null default now(),
  unique (task_id, packet_id),
  check (
    (cost_class = 'NONE'
      and max_cost_minor_units is null
      and currency is null)
    or
    (cost_class in ('BOUNDED','VARIABLE')
      and max_cost_minor_units is not null
      and max_cost_minor_units >= 0
      and currency is not null
      and length(btrim(currency)) > 0)
  ),
  check (
    (decision <> 'APPROVED'
      and grant_id is null
      and granted_generation is null)
    or
    (decision = 'APPROVED'
      and grant_id is not null
      and length(btrim(grant_id)) > 0
      and granted_generation is not null)
  )
);

create table if not exists public.company_events_v1 (
  id bigint generated always as identity primary key,
  source text not null check (length(btrim(source)) > 0),
  source_ref text not null check (length(btrim(source_ref)) > 0),
  observed_at timestamptz not null,
  event_hash text not null unique
    check (event_hash ~ '^[0-9a-f]{64}$'),
  payload_hash text not null
    check (payload_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create index if not exists company_tasks_status_idx
  on public.company_tasks_v1(status, created_at);
create index if not exists company_tasks_objective_idx
  on public.company_tasks_v1(objective_id, created_at);
create index if not exists company_operator_pending_idx
  on public.company_operator_actions_v1(decision, created_at);
create index if not exists company_events_observed_idx
  on public.company_events_v1(observed_at desc);

alter table public.company_objectives_v1 enable row level security;
alter table public.company_tasks_v1 enable row level security;
alter table public.company_evidence_v1 enable row level security;
alter table public.company_operator_actions_v1 enable row level security;
alter table public.company_events_v1 enable row level security;

alter table public.company_objectives_v1 force row level security;
alter table public.company_tasks_v1 force row level security;
alter table public.company_evidence_v1 force row level security;
alter table public.company_operator_actions_v1 force row level security;
alter table public.company_events_v1 force row level security;

revoke all on public.company_objectives_v1 from anon, authenticated;
revoke all on public.company_tasks_v1 from anon, authenticated;
revoke all on public.company_evidence_v1 from anon, authenticated;
revoke all on public.company_operator_actions_v1 from anon, authenticated;
revoke all on public.company_events_v1 from anon, authenticated;
