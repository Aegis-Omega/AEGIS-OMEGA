-- AEGIS Ω encrypted operator-output recovery. Draft migration: NOT DEPLOYED.
-- Depends on 20261010190000_agent_dispatch_claims_v1.sql.
-- Database stores only encrypted result bytes + a channel digest; no plaintext,
-- provider secrets, Slack tokens, user emails, or prompt texts.
create table if not exists public.aegis_agent_result_outbox_v1 (
  event_digest text primary key references public.aegis_agent_dispatch_claims_v1(event_digest),
  destination_digest text not null check (destination_digest ~ '^[0-9a-f]{64}$'),
  ciphertext_b64 text not null check (length(ciphertext_b64) between 1 and 100000),
  iv_b64 text not null check (length(iv_b64) between 1 and 128),
  delivery_state text not null default 'READY' check (delivery_state in ('READY','SENDING','DELIVERED')),
  attempt_id uuid,
  attempt_count integer not null default 0 check (attempt_count between 0 and 3),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '24 hours'),
  delivered_at timestamptz,
  constraint aegis_outbox_state_consistency check (
    (delivery_state = 'SENDING') = (attempt_id is not null)
  )
);
alter table public.aegis_agent_result_outbox_v1 enable row level security;
revoke all on public.aegis_agent_result_outbox_v1 from public, anon, authenticated;
grant select, insert, update on public.aegis_agent_result_outbox_v1 to service_role;

-- Atomically lease at most ONE delivery attempt per event. Never expire an
-- ambiguous SENDING lease automatically: Slack may have accepted a message
-- before the ACK was persisted. Manual reconciliation is required.
create or replace function public.aegis_outbox_claim_delivery_v1(
  p_event_digest text, p_destination_digest text, p_attempt_id uuid
) returns table (ciphertext_b64 text, iv_b64 text)
language sql security invoker set search_path = '' as $func$
  update public.aegis_agent_result_outbox_v1 as o
  set delivery_state = 'SENDING', attempt_id = p_attempt_id,
      attempt_count = o.attempt_count + 1
  where o.event_digest = p_event_digest and o.destination_digest = p_destination_digest
    and o.delivery_state = 'READY' and o.attempt_count < 3
    and o.expires_at > now()
  returning o.ciphertext_b64, o.iv_b64;
$func$;

-- A known Slack ok:false is safe to release for a bounded output-only retry.
-- Unknown network result must NOT invoke this with false: leave SENDING.
create or replace function public.aegis_outbox_complete_delivery_v1(
  p_event_digest text, p_destination_digest text,
  p_attempt_id uuid, p_delivered boolean
) returns boolean
language sql security invoker set search_path = '' as $func$
  with advanced as (
    update public.aegis_agent_result_outbox_v1 as o
    set delivery_state = case when p_delivered then 'DELIVERED' else 'READY' end,
        attempt_id = null,
        delivered_at = case when p_delivered then now() else null end
    where o.event_digest = p_event_digest and o.destination_digest = p_destination_digest
      and o.delivery_state = 'SENDING' and o.attempt_id = p_attempt_id
      and o.expires_at > now()
    returning 1
  ) select exists(select 1 from advanced);
$func$;

revoke all on function public.aegis_outbox_claim_delivery_v1(text,text,uuid)
  from public, anon, authenticated;
revoke all on function public.aegis_outbox_complete_delivery_v1(text,text,uuid,boolean)
  from public, anon, authenticated;
grant execute on function public.aegis_outbox_claim_delivery_v1(text,text,uuid) to service_role;
grant execute on function public.aegis_outbox_complete_delivery_v1(text,text,uuid,boolean) to service_role;

-- Retention: requests cannot read after 24h, but physical deletion is a
-- separate operator-approved job. No cron/billing/production changes herein.
