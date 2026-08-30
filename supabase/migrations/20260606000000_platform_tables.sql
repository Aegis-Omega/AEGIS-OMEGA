-- AEGIS-Ω Platform tables — revenue cycles, API keys, agent activity

-- Revenue cycle results (persisted by vertex/serve.py after each collaboration)
create table if not exists revenue_cycles (
  id                        uuid primary key default gen_random_uuid(),
  cycle_id                  text not null unique,
  objective                 text not null,
  mode                      text not null default 'revenue',
  departments_collaborated  integer not null default 0,
  chain_valid               boolean not null default true,
  projection_arr_usd        bigint,
  projection_tier           text,
  constitutional_verdict    text not null default 'APPROVED'
                              check (constitutional_verdict in ('APPROVED', 'FLAG', 'QUARANTINE')),
  live                      boolean not null default false,
  created_at                timestamptz not null default now()
);

create index if not exists revenue_cycles_created_at_idx on revenue_cycles (created_at desc);
create index if not exists revenue_cycles_verdict_idx on revenue_cycles (constitutional_verdict);

alter table revenue_cycles enable row level security;
-- Service role (platform API) can insert/read; no public access.


-- Platform API keys — one per paying customer
create table if not exists platform_api_keys (
  id              uuid primary key default gen_random_uuid(),
  key_hash        text not null unique,          -- SHA-256(raw_key) — raw never stored
  customer_email  text not null,
  tier            text not null default 'operator'
                    check (tier in ('explorer', 'operator', 'sovereign')),
  runs_used       integer not null default 0,
  runs_limit      integer not null default 500,  -- -1 = unlimited (sovereign)
  active          boolean not null default true,
  purchase_id     uuid references purchases(id),
  created_at      timestamptz not null default now(),
  last_used_at    timestamptz
);

create index if not exists platform_api_keys_email_idx on platform_api_keys (customer_email);
alter table platform_api_keys enable row level security;


-- Agent activity log — what each agent role has done
create table if not exists agent_activity (
  id              uuid primary key default gen_random_uuid(),
  cycle_id        text,
  role            text not null,
  mode            text not null default 'revenue',
  tool_calls      integer not null default 0,
  input_tokens    integer not null default 0,
  output_tokens   integer not null default 0,
  duration_ms     integer not null default 0,
  quality_score   integer,
  created_at      timestamptz not null default now()
);

create index if not exists agent_activity_role_idx on agent_activity (role, created_at desc);
create index if not exists agent_activity_cycle_idx on agent_activity (cycle_id);
alter table agent_activity enable row level security;


-- Helper: provision a new API key (called by verify-payment edge function)
create or replace function provision_platform_key(
  p_customer_email text,
  p_tier text,
  p_purchase_id uuid default null
) returns text
language plpgsql security definer
as $$
declare
  v_raw_key text;
  v_key_hash text;
  v_runs_limit integer;
begin
  -- Generate a random API key
  v_raw_key := 'aegis_' || encode(gen_random_bytes(24), 'base64');
  v_raw_key := replace(replace(replace(v_raw_key, '/', '_'), '+', '-'), '=', '');

  -- Hash it for storage (raw key is never stored)
  v_key_hash := encode(sha256(v_raw_key::bytea), 'hex');

  -- Set run limits by tier
  v_runs_limit := case p_tier
    when 'explorer'  then 10
    when 'operator'  then 500
    when 'sovereign' then -1
    else 10
  end;

  insert into platform_api_keys
    (key_hash, customer_email, tier, runs_limit, purchase_id)
  values
    (v_key_hash, p_customer_email, p_tier, v_runs_limit, p_purchase_id);

  -- Return the raw key (caller sends it to the customer — only time it's visible)
  return v_raw_key;
end;
$$;
