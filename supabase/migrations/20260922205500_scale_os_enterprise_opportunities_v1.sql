-- AEGIS Ω Scale OS Enterprise Opportunity Pipeline V1
-- SOURCE ONLY. Stacked on the existing scale_os production schema.
-- Do not apply without an explicit production schema grant.
-- Current opportunity state is stored once; transition evidence is appended to scale_os.events.

create table if not exists scale_os.enterprise_opportunities_v1 (
  id uuid primary key default gen_random_uuid(),
  opportunity_key text not null unique
    check (length(btrim(opportunity_key)) > 0),
  account_name text not null
    check (length(btrim(account_name)) > 0),
  stage text not null default 'DISCOVERED'
    check (stage in (
      'DISCOVERED',
      'CONTACTED',
      'QUALIFIED_REPLY',
      'SCOPING_CALL_HELD',
      'WRITTEN_SCOPE_AGREED',
      'PAYMENT_RECEIVED',
      'AUDIT_STARTED',
      'CLOSED_LOST'
    )),
  generation_v1 bigint not null default 0
    check (generation_v1 >= 0),
  origin_source_system text not null
    check (length(btrim(origin_source_system)) > 0),
  origin_source_object_id text not null
    check (length(btrim(origin_source_object_id)) > 0),
  origin_evidence_ref text not null
    check (length(btrim(origin_evidence_ref)) > 0),
  last_event_id uuid
    references scale_os.events(id) on delete restrict,
  external_authority text not null default 'NOT_GRANTED'
    check (external_authority = 'NOT_GRANTED'),
  authority_effect text not null default 'NONE'
    check (authority_effect = 'NONE'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists scale_os_enterprise_opportunities_stage_v1_idx
  on scale_os.enterprise_opportunities_v1(stage, updated_at desc);

alter table scale_os.enterprise_opportunities_v1 enable row level security;
alter table scale_os.enterprise_opportunities_v1 force row level security;

revoke all on scale_os.enterprise_opportunities_v1
  from public, anon, authenticated, service_role;
grant select on scale_os.enterprise_opportunities_v1
  to service_role;

create or replace function scale_os.create_enterprise_opportunity_v1(
  p_opportunity_key text,
  p_account_name text,
  p_source_system text,
  p_source_object_id text,
  p_evidence_ref text,
  p_evidence_authority text,
  p_generation bigint
)
returns table (
  outcome text,
  opportunity_id uuid,
  event_id uuid
)
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
declare
  v_opportunity_id uuid;
  v_event_id uuid;
  v_existing scale_os.enterprise_opportunities_v1%rowtype;
begin
  if p_opportunity_key is null or length(btrim(p_opportunity_key)) = 0 then
    raise exception 'opportunity_key required';
  end if;
  if p_account_name is null or length(btrim(p_account_name)) = 0 then
    raise exception 'account_name required';
  end if;
  if p_source_system is null or length(btrim(p_source_system)) = 0 then
    raise exception 'source_system required';
  end if;
  if p_source_object_id is null or length(btrim(p_source_object_id)) = 0 then
    raise exception 'source_object_id required';
  end if;
  if p_evidence_ref is null or length(btrim(p_evidence_ref)) = 0 then
    raise exception 'evidence_ref required';
  end if;
  if p_evidence_authority not in ('DIRECT_OBSERVATION','DERIVED_FROM_VERIFIED') then
    return query select 'DENIED_DISCOVERY_EVIDENCE_AUTHORITY'::text, null::uuid, null::uuid;
    return;
  end if;
  if p_generation is null or p_generation < 0 then
    raise exception 'invalid generation';
  end if;

  insert into scale_os.enterprise_opportunities_v1 (
    opportunity_key,
    account_name,
    stage,
    generation_v1,
    origin_source_system,
    origin_source_object_id,
    origin_evidence_ref,
    external_authority,
    authority_effect
  ) values (
    btrim(p_opportunity_key),
    btrim(p_account_name),
    'DISCOVERED',
    p_generation,
    btrim(p_source_system),
    btrim(p_source_object_id),
    btrim(p_evidence_ref),
    'NOT_GRANTED',
    'NONE'
  )
  on conflict (opportunity_key) do nothing
  returning id into v_opportunity_id;

  if v_opportunity_id is null then
    select *
      into v_existing
      from scale_os.enterprise_opportunities_v1
     where opportunity_key = btrim(p_opportunity_key)
     for update;

    if v_existing.account_name <> btrim(p_account_name)
       or v_existing.origin_source_system <> btrim(p_source_system)
       or v_existing.origin_source_object_id <> btrim(p_source_object_id)
       or v_existing.origin_evidence_ref <> btrim(p_evidence_ref) then
      return query
        select 'DENIED_OPPORTUNITY_KEY_COLLISION'::text, v_existing.id, v_existing.last_event_id;
      return;
    end if;

    return query
      select 'REPLAYED_EXISTING'::text, v_existing.id, v_existing.last_event_id;
    return;
  end if;

  insert into scale_os.events (
    event_type,
    service_key,
    task_id,
    evidence_refs,
    payload
  ) values (
    'enterprise_opportunity_stage_v1',
    'company:enterprise-opportunity',
    null,
    jsonb_build_array(btrim(p_evidence_ref)),
    jsonb_build_object(
      'opportunity_id', v_opportunity_id,
      'opportunity_key', btrim(p_opportunity_key),
      'from_stage', null,
      'to_stage', 'DISCOVERED',
      'evidence_kind', 'DISCOVERY',
      'evidence_authority', p_evidence_authority,
      'source_system', btrim(p_source_system),
      'source_object_id', btrim(p_source_object_id),
      'generation', p_generation,
      'external_authority', 'NOT_GRANTED',
      'authority_effect', 'NONE'
    )
  )
  returning id into v_event_id;

  update scale_os.enterprise_opportunities_v1
     set last_event_id = v_event_id,
         updated_at = now()
   where id = v_opportunity_id;

  return query select 'CREATED'::text, v_opportunity_id, v_event_id;
end;
$$;

create or replace function scale_os.advance_enterprise_opportunity_v1(
  p_opportunity_id uuid,
  p_target_stage text,
  p_evidence_kind text,
  p_evidence_authority text,
  p_evidence_ref text,
  p_source_system text,
  p_source_object_id text,
  p_generation bigint
)
returns table (
  outcome text,
  opportunity_id uuid,
  event_id uuid
)
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
declare
  v_current scale_os.enterprise_opportunities_v1%rowtype;
  v_required_kind text;
  v_from_rank integer;
  v_to_rank integer;
  v_event_id uuid;
begin
  if p_opportunity_id is null then
    raise exception 'opportunity_id required';
  end if;
  if p_target_stage is null or p_target_stage not in (
    'CONTACTED',
    'QUALIFIED_REPLY',
    'SCOPING_CALL_HELD',
    'WRITTEN_SCOPE_AGREED',
    'PAYMENT_RECEIVED',
    'AUDIT_STARTED',
    'CLOSED_LOST'
  ) then
    raise exception 'invalid target_stage';
  end if;
  if p_evidence_ref is null or length(btrim(p_evidence_ref)) = 0 then
    raise exception 'evidence_ref required';
  end if;
  if p_source_system is null or length(btrim(p_source_system)) = 0 then
    raise exception 'source_system required';
  end if;
  if p_source_object_id is null or length(btrim(p_source_object_id)) = 0 then
    raise exception 'source_object_id required';
  end if;
  if p_generation is null or p_generation < 0 then
    raise exception 'invalid generation';
  end if;

  select *
    into v_current
    from scale_os.enterprise_opportunities_v1
   where id = p_opportunity_id
   for update;

  if not found then
    return query select 'DENIED_UNKNOWN_OPPORTUNITY'::text, p_opportunity_id, null::uuid;
    return;
  end if;

  if v_current.external_authority <> 'NOT_GRANTED'
     or v_current.authority_effect <> 'NONE' then
    return query select 'DENIED_AUTHORITY_INVARIANT'::text, p_opportunity_id, null::uuid;
    return;
  end if;

  if v_current.stage in ('AUDIT_STARTED','CLOSED_LOST') then
    return query select 'DENIED_TERMINAL_STAGE'::text, p_opportunity_id, v_current.last_event_id;
    return;
  end if;

  if p_generation <= v_current.generation_v1 then
    return query select 'DENIED_GENERATION_REGRESSION'::text, p_opportunity_id, v_current.last_event_id;
    return;
  end if;

  if exists (
    select 1
      from scale_os.events e
     where e.event_type = 'enterprise_opportunity_stage_v1'
       and e.payload ->> 'opportunity_id' = p_opportunity_id::text
       and e.evidence_refs @> jsonb_build_array(btrim(p_evidence_ref))
  ) then
    return query select 'DENIED_EVIDENCE_REUSE'::text, p_opportunity_id, v_current.last_event_id;
    return;
  end if;

  if p_target_stage = 'CLOSED_LOST' then
    if p_evidence_kind <> 'LOSS_REASON'
       or p_evidence_authority not in ('DIRECT_OBSERVATION','DERIVED_FROM_VERIFIED') then
      return query select 'DENIED_LOSS_EVIDENCE'::text, p_opportunity_id, v_current.last_event_id;
      return;
    end if;
  else
    v_required_kind := case p_target_stage
      when 'CONTACTED' then 'OUTBOUND_SENT'
      when 'QUALIFIED_REPLY' then 'QUALIFYING_REPLY'
      when 'SCOPING_CALL_HELD' then 'SCOPING_CALL'
      when 'WRITTEN_SCOPE_AGREED' then 'SCOPE_AGREEMENT'
      when 'PAYMENT_RECEIVED' then 'PAYMENT_RECORD'
      when 'AUDIT_STARTED' then 'AUDIT_START'
      else null
    end;

    if p_evidence_kind <> v_required_kind then
      return query select 'DENIED_EVIDENCE_KIND'::text, p_opportunity_id, v_current.last_event_id;
      return;
    end if;

    if p_target_stage in ('CONTACTED','PAYMENT_RECEIVED','AUDIT_STARTED') then
      if p_evidence_authority <> 'DIRECT_OBSERVATION' then
        return query select 'DENIED_DIRECT_OBSERVATION_REQUIRED'::text, p_opportunity_id, v_current.last_event_id;
        return;
      end if;
    elsif p_evidence_authority not in ('DIRECT_OBSERVATION','DERIVED_FROM_VERIFIED') then
      return query select 'DENIED_EVIDENCE_AUTHORITY'::text, p_opportunity_id, v_current.last_event_id;
      return;
    end if;

    v_from_rank := case v_current.stage
      when 'DISCOVERED' then 0
      when 'CONTACTED' then 1
      when 'QUALIFIED_REPLY' then 2
      when 'SCOPING_CALL_HELD' then 3
      when 'WRITTEN_SCOPE_AGREED' then 4
      when 'PAYMENT_RECEIVED' then 5
      when 'AUDIT_STARTED' then 6
      else -1
    end;

    v_to_rank := case p_target_stage
      when 'DISCOVERED' then 0
      when 'CONTACTED' then 1
      when 'QUALIFIED_REPLY' then 2
      when 'SCOPING_CALL_HELD' then 3
      when 'WRITTEN_SCOPE_AGREED' then 4
      when 'PAYMENT_RECEIVED' then 5
      when 'AUDIT_STARTED' then 6
      else -1
    end;

    if v_to_rank <> v_from_rank + 1 then
      return query select 'DENIED_STAGE_SKIP'::text, p_opportunity_id, v_current.last_event_id;
      return;
    end if;
  end if;

  insert into scale_os.events (
    event_type,
    service_key,
    task_id,
    evidence_refs,
    payload
  ) values (
    'enterprise_opportunity_stage_v1',
    'company:enterprise-opportunity',
    null,
    jsonb_build_array(btrim(p_evidence_ref)),
    jsonb_build_object(
      'opportunity_id', p_opportunity_id,
      'opportunity_key', v_current.opportunity_key,
      'from_stage', v_current.stage,
      'to_stage', p_target_stage,
      'evidence_kind', p_evidence_kind,
      'evidence_authority', p_evidence_authority,
      'source_system', btrim(p_source_system),
      'source_object_id', btrim(p_source_object_id),
      'generation', p_generation,
      'external_authority', 'NOT_GRANTED',
      'authority_effect', 'NONE'
    )
  )
  returning id into v_event_id;

  update scale_os.enterprise_opportunities_v1
     set stage = p_target_stage,
         generation_v1 = p_generation,
         last_event_id = v_event_id,
         updated_at = now(),
         external_authority = 'NOT_GRANTED',
         authority_effect = 'NONE'
   where id = p_opportunity_id;

  return query select 'ADVANCED'::text, p_opportunity_id, v_event_id;
end;
$$;

revoke all on function scale_os.create_enterprise_opportunity_v1(
  text, text, text, text, text, text, bigint
) from public, anon, authenticated;

revoke all on function scale_os.advance_enterprise_opportunity_v1(
  uuid, text, text, text, text, text, text, bigint
) from public, anon, authenticated;

grant execute on function scale_os.create_enterprise_opportunity_v1(
  text, text, text, text, text, text, bigint
) to service_role;

grant execute on function scale_os.advance_enterprise_opportunity_v1(
  uuid, text, text, text, text, text, text, bigint
) to service_role;


-- Explicit ownership is part of the direct-enterprise-event INSERT boundary.
alter function scale_os.create_enterprise_opportunity_v1(
  text, text, text, text, text, text, bigint
) owner to postgres;
alter function scale_os.advance_enterprise_opportunity_v1(
  uuid, text, text, text, text, text, text, bigint
) owner to postgres;
