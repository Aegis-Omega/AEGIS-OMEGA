-- AEGIS Ω Scale OS Enterprise Event Insert Guard V1
-- SOURCE ONLY. Do not apply without an explicit production schema grant.
-- Enterprise transition rows may be inserted only from postgres-owned SECURITY DEFINER RPCs.
-- Historical/non-enterprise event types retain their existing behavior.

create or replace function scale_os.prevent_direct_enterprise_event_insert_v1()
returns trigger
language plpgsql
security invoker
set search_path = scale_os, pg_temp
as $$
begin
  if new.event_type in (
    'enterprise_opportunity_stage_v1',
    'enterprise_resource_state_v1'
  ) and current_user <> 'postgres' then
    raise exception 'AEGIS_ENTERPRISE_EVENT_DIRECT_INSERT_DENIED:%:%', current_user, new.event_type
      using errcode = '42501';
  end if;

  return new;
end;
$$;

drop trigger if exists scale_os_enterprise_event_insert_guard_v1
  on scale_os.events;

create trigger scale_os_enterprise_event_insert_guard_v1
before insert on scale_os.events
for each row
execute function scale_os.prevent_direct_enterprise_event_insert_v1();

revoke all on function scale_os.prevent_direct_enterprise_event_insert_v1()
  from public, anon, authenticated;
grant execute on function scale_os.prevent_direct_enterprise_event_insert_v1()
  to service_role;
