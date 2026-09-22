-- AEGIS Ω Scale OS Enterprise Event Immutability Guard V1
-- SOURCE ONLY. Do not apply without an explicit production schema grant.
-- Protects only new enterprise event types; historical Scale OS events are not reclassified.

create or replace function scale_os.prevent_enterprise_event_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
begin
  if old.event_type in (
    'enterprise_opportunity_stage_v1',
    'enterprise_resource_state_v1'
  ) then
    raise exception 'AEGIS_ENTERPRISE_EVENT_IMMUTABLE:%:%', tg_op, old.id
      using errcode = '42501';
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists scale_os_enterprise_event_immutability_v1
  on scale_os.events;

create trigger scale_os_enterprise_event_immutability_v1
before update or delete on scale_os.events
for each row
execute function scale_os.prevent_enterprise_event_mutation_v1();

revoke all on function scale_os.prevent_enterprise_event_mutation_v1()
  from public, anon, authenticated;
grant execute on function scale_os.prevent_enterprise_event_mutation_v1()
  to service_role;
