-- AEGIS Ω encrypted outbox retention, draft/not deployed.
-- Depends on 20261011052000_agent_result_outbox_v1.sql.
-- Explicit operator-controlled bounded physical removal, NOT a scheduled job.
-- Logical expiry blocks recovery after 24h; this procedure lets the Operator
-- purge stored encrypted payloads without deleting the once-only dispatch
-- claim and accidentally permitting a second paid inference.
--
-- SECURITY INVOKER requires the service role's actual SQL DELETE privilege.
-- This does not grant browser/anonymous users any table access.
grant delete on public.aegis_agent_result_outbox_v1 to service_role;

-- Expired SENDING rows are also deleted: privacy retention supersedes
-- availability after expiry. The unresolved count is returned for audit.
-- Backups and WAL follow the Supabase provider's separate retention policies.
create or replace function public.aegis_outbox_purge_expired_v1(
  p_batch_limit integer
) returns table(deleted_count bigint, unresolved_count bigint)
language sql security invoker set search_path = '' as $func$
  with expired as (
    select o.ctid
      from public.aegis_agent_result_outbox_v1 as o
      where p_batch_limit between 1 and 500
        and o.expires_at <= now()
      order by o.expires_at, o.created_at
      limit p_batch_limit
      for update skip locked
  ), purged as (
    delete from public.aegis_agent_result_outbox_v1 as o
    using expired as e
    where o.ctid = e.ctid
    returning o.delivery_state
  )
  select count(*)::bigint,
         count(*) filter (where delivery_state = 'SENDING')::bigint
  from purged;
$func$;

revoke all on function public.aegis_outbox_purge_expired_v1(integer)
  from public, anon, authenticated;
grant execute on function public.aegis_outbox_purge_expired_v1(integer)
  to service_role;

comment on function public.aegis_outbox_purge_expired_v1(integer) is
  'Privileged bounded deletion of expired encrypted outbox payloads only. '
  'Preserves once-only dispatch evidence. Not automatically scheduled; '
  'actual Postgres and backup-retention validation required before admission.';
