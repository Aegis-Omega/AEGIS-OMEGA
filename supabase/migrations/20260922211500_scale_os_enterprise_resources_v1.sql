-- AEGIS Ω Scale OS Enterprise Resource Registry V1
-- SOURCE ONLY. Do not apply without an explicit production schema grant.
-- Resource offers are evidence, not active capacity or authority.

create table if not exists scale_os.enterprise_resources_v1 (
  id uuid primary key default gen_random_uuid(),
  resource_key text not null unique
    check (length(btrim(resource_key)) > 0),
  provider text not null
    check (length(btrim(provider)) > 0),
  resource_class text not null
    check (resource_class in (
      'API_CREDIT','CLOUD_CREDIT','PROGRAM_ACCESS','TRIAL_EXTENSION','CONDITIONAL_REWARD'
    )),
  state text not null default 'OFFERED'
    check (state in ('OFFERED','CLAIMED','ACTIVE','EXPIRED','REJECTED')),
  eligibility_state text not null default 'NOT_VERIFIED'
    check (eligibility_state in ('NOT_VERIFIED','ELIGIBLE','INELIGIBLE','NOT_APPLICABLE')),
  terms_state text not null default 'NOT_REVIEWED'
    check (terms_state in ('NOT_REVIEWED','REVIEWED','NOT_APPLICABLE')),
  known_value_minor_units bigint
    check (known_value_minor_units is null or known_value_minor_units >= 0),
  currency text
    check (currency is null or currency ~ '^[A-Z]{3}$'),
  activation_requires_payment_method boolean,
  source_system text not null
    check (length(btrim(source_system)) > 0),
  source_object_id text not null
    check (length(btrim(source_object_id)) > 0),
  evidence_ref text not null
    check (length(btrim(evidence_ref)) > 0),
  expires_at timestamptz,
  last_event_id uuid
    references scale_os.events(id) on delete restrict,
  external_authority text not null default 'NOT_GRANTED'
    check (external_authority = 'NOT_GRANTED'),
  authority_effect text not null default 'NONE'
    check (authority_effect = 'NONE'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (known_value_minor_units is null and currency is null)
    or
    (known_value_minor_units is not null and currency is not null)
  )
);

create index if not exists scale_os_enterprise_resources_state_v1_idx
  on scale_os.enterprise_resources_v1(state, provider, updated_at desc);

alter table scale_os.enterprise_resources_v1 enable row level security;
alter table scale_os.enterprise_resources_v1 force row level security;

revoke all on scale_os.enterprise_resources_v1
  from public, anon, authenticated, service_role;
grant select on scale_os.enterprise_resources_v1
  to service_role;

create or replace function scale_os.record_enterprise_resource_offer_v1(
  p_resource_key text,
  p_provider text,
  p_resource_class text,
  p_known_value_minor_units bigint,
  p_currency text,
  p_source_system text,
  p_source_object_id text,
  p_evidence_ref text,
  p_expires_at timestamptz
)
returns table (
  outcome text,
  resource_id uuid,
  event_id uuid
)
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
declare
  v_resource_id uuid;
  v_event_id uuid;
  v_existing scale_os.enterprise_resources_v1%rowtype;
begin
  if p_resource_key is null or length(btrim(p_resource_key)) = 0 then
    raise exception 'resource_key required';
  end if;
  if p_provider is null or length(btrim(p_provider)) = 0 then
    raise exception 'provider required';
  end if;
  if p_resource_class not in (
    'API_CREDIT','CLOUD_CREDIT','PROGRAM_ACCESS','TRIAL_EXTENSION','CONDITIONAL_REWARD'
  ) then
    raise exception 'invalid resource_class';
  end if;
  if (p_known_value_minor_units is null) <> (p_currency is null) then
    raise exception 'value and currency must be supplied together';
  end if;
  if p_known_value_minor_units is not null and p_known_value_minor_units < 0 then
    raise exception 'invalid resource value';
  end if;
  if p_currency is not null and p_currency !~ '^[A-Z]{3}$' then
    raise exception 'invalid currency';
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

  insert into scale_os.enterprise_resources_v1 (
    resource_key, provider, resource_class, state,
    eligibility_state, terms_state,
    known_value_minor_units, currency,
    activation_requires_payment_method,
    source_system, source_object_id, evidence_ref, expires_at,
    external_authority, authority_effect
  ) values (
    btrim(p_resource_key), btrim(p_provider), p_resource_class, 'OFFERED',
    'NOT_VERIFIED', 'NOT_REVIEWED',
    p_known_value_minor_units, p_currency,
    null,
    btrim(p_source_system), btrim(p_source_object_id), btrim(p_evidence_ref), p_expires_at,
    'NOT_GRANTED', 'NONE'
  )
  on conflict (resource_key) do nothing
  returning id into v_resource_id;

  if v_resource_id is null then
    select *
      into v_existing
      from scale_os.enterprise_resources_v1
     where resource_key = btrim(p_resource_key)
     for update;

    if v_existing.provider <> btrim(p_provider)
       or v_existing.resource_class <> p_resource_class
       or v_existing.source_system <> btrim(p_source_system)
       or v_existing.source_object_id <> btrim(p_source_object_id)
       or v_existing.evidence_ref <> btrim(p_evidence_ref)
       or v_existing.known_value_minor_units is distinct from p_known_value_minor_units
       or v_existing.currency is distinct from p_currency then
      return query
        select 'DENIED_RESOURCE_KEY_COLLISION'::text, v_existing.id, v_existing.last_event_id;
      return;
    end if;

    return query
      select 'REPLAYED_EXISTING'::text, v_existing.id, v_existing.last_event_id;
    return;
  end if;

  insert into scale_os.events (
    event_type, service_key, task_id, evidence_refs, payload
  ) values (
    'enterprise_resource_state_v1',
    'company:enterprise-resource',
    null,
    jsonb_build_array(btrim(p_evidence_ref)),
    jsonb_build_object(
      'resource_id', v_resource_id,
      'resource_key', btrim(p_resource_key),
      'provider', btrim(p_provider),
      'resource_class', p_resource_class,
      'from_state', null,
      'to_state', 'OFFERED',
      'eligibility_state', 'NOT_VERIFIED',
      'terms_state', 'NOT_REVIEWED',
      'external_authority', 'NOT_GRANTED',
      'authority_effect', 'NONE'
    )
  )
  returning id into v_event_id;

  update scale_os.enterprise_resources_v1
     set last_event_id = v_event_id,
         updated_at = now()
   where id = v_resource_id;

  return query select 'RECORDED'::text, v_resource_id, v_event_id;
end;
$$;

create or replace function scale_os.update_enterprise_resource_review_v1(
  p_resource_id uuid,
  p_eligibility_state text,
  p_terms_state text,
  p_evidence_authority text,
  p_activation_requires_payment_method boolean,
  p_evidence_ref text,
  p_source_system text,
  p_source_object_id text
)
returns table (
  outcome text,
  resource_id uuid,
  event_id uuid
)
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
declare
  v_current scale_os.enterprise_resources_v1%rowtype;
  v_event_id uuid;
begin
  if p_eligibility_state not in ('NOT_VERIFIED','ELIGIBLE','INELIGIBLE','NOT_APPLICABLE') then
    raise exception 'invalid eligibility_state';
  end if;
  if p_terms_state not in ('NOT_REVIEWED','REVIEWED','NOT_APPLICABLE') then
    raise exception 'invalid terms_state';
  end if;
  if p_evidence_authority not in ('DIRECT_OBSERVATION','PROVIDER_ATTESTATION','DERIVED_FROM_VERIFIED') then
    raise exception 'invalid evidence_authority';
  end if;
  if p_eligibility_state = 'ELIGIBLE'
     and p_evidence_authority not in ('DIRECT_OBSERVATION','DERIVED_FROM_VERIFIED') then
    return query select 'DENIED_ELIGIBILITY_EVIDENCE_AUTHORITY'::text, p_resource_id, null::uuid;
    return;
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

  select *
    into v_current
    from scale_os.enterprise_resources_v1
   where id = p_resource_id
   for update;

  if not found then
    return query select 'DENIED_UNKNOWN_RESOURCE'::text, p_resource_id, null::uuid;
    return;
  end if;

  if v_current.external_authority <> 'NOT_GRANTED'
     or v_current.authority_effect <> 'NONE' then
    return query select 'DENIED_AUTHORITY_INVARIANT'::text, p_resource_id, v_current.last_event_id;
    return;
  end if;

  if exists (
    select 1
      from scale_os.events e
     where e.event_type = 'enterprise_resource_state_v1'
       and e.payload ->> 'resource_id' = p_resource_id::text
       and e.evidence_refs @> jsonb_build_array(btrim(p_evidence_ref))
  ) then
    return query select 'DENIED_EVIDENCE_REUSE'::text, p_resource_id, v_current.last_event_id;
    return;
  end if;

  insert into scale_os.events (
    event_type, service_key, task_id, evidence_refs, payload
  ) values (
    'enterprise_resource_state_v1',
    'company:enterprise-resource',
    null,
    jsonb_build_array(btrim(p_evidence_ref)),
    jsonb_build_object(
      'resource_id', p_resource_id,
      'resource_key', v_current.resource_key,
      'provider', v_current.provider,
      'from_state', v_current.state,
      'to_state', v_current.state,
      'eligibility_state', p_eligibility_state,
      'terms_state', p_terms_state,
      'evidence_authority', p_evidence_authority,
      'activation_requires_payment_method', p_activation_requires_payment_method,
      'external_authority', 'NOT_GRANTED',
      'authority_effect', 'NONE'
    )
  )
  returning id into v_event_id;

  update scale_os.enterprise_resources_v1
     set eligibility_state = p_eligibility_state,
         terms_state = p_terms_state,
         activation_requires_payment_method = p_activation_requires_payment_method,
         last_event_id = v_event_id,
         updated_at = now()
   where id = p_resource_id;

  return query select 'REVIEW_UPDATED'::text, p_resource_id, v_event_id;
end;
$$;

create or replace function scale_os.transition_enterprise_resource_state_v1(
  p_resource_id uuid,
  p_target_state text,
  p_evidence_ref text,
  p_source_system text,
  p_source_object_id text
)
returns table (
  outcome text,
  resource_id uuid,
  event_id uuid
)
language plpgsql
security definer
set search_path = scale_os, pg_temp
as $$
declare
  v_current scale_os.enterprise_resources_v1%rowtype;
  v_event_id uuid;
begin
  if p_target_state not in ('CLAIMED','ACTIVE','EXPIRED','REJECTED') then
    raise exception 'invalid target_state';
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

  select *
    into v_current
    from scale_os.enterprise_resources_v1
   where id = p_resource_id
   for update;

  if not found then
    return query select 'DENIED_UNKNOWN_RESOURCE'::text, p_resource_id, null::uuid;
    return;
  end if;

  if v_current.external_authority <> 'NOT_GRANTED'
     or v_current.authority_effect <> 'NONE' then
    return query select 'DENIED_AUTHORITY_INVARIANT'::text, p_resource_id, v_current.last_event_id;
    return;
  end if;

  if v_current.state in ('EXPIRED','REJECTED') then
    return query select 'DENIED_TERMINAL_RESOURCE_STATE'::text, p_resource_id, v_current.last_event_id;
    return;
  end if;

  if p_target_state = 'CLAIMED' then
    if v_current.state <> 'OFFERED' then
      return query select 'DENIED_RESOURCE_STATE_TRANSITION'::text, p_resource_id, v_current.last_event_id;
      return;
    end if;
    if v_current.eligibility_state not in ('ELIGIBLE','NOT_APPLICABLE')
       or v_current.terms_state not in ('REVIEWED','NOT_APPLICABLE') then
      return query select 'DENIED_RESOURCE_REVIEW_INCOMPLETE'::text, p_resource_id, v_current.last_event_id;
      return;
    end if;
  elsif p_target_state = 'ACTIVE' then
    if v_current.state <> 'CLAIMED' then
      return query select 'DENIED_RESOURCE_STATE_TRANSITION'::text, p_resource_id, v_current.last_event_id;
      return;
    end if;
    if v_current.eligibility_state not in ('ELIGIBLE','NOT_APPLICABLE')
       or v_current.terms_state not in ('REVIEWED','NOT_APPLICABLE') then
      return query select 'DENIED_RESOURCE_REVIEW_INCOMPLETE'::text, p_resource_id, v_current.last_event_id;
      return;
    end if;
  end if;

  if exists (
    select 1
      from scale_os.events e
     where e.event_type = 'enterprise_resource_state_v1'
       and e.payload ->> 'resource_id' = p_resource_id::text
       and e.evidence_refs @> jsonb_build_array(btrim(p_evidence_ref))
  ) then
    return query select 'DENIED_EVIDENCE_REUSE'::text, p_resource_id, v_current.last_event_id;
    return;
  end if;

  insert into scale_os.events (
    event_type, service_key, task_id, evidence_refs, payload
  ) values (
    'enterprise_resource_state_v1',
    'company:enterprise-resource',
    null,
    jsonb_build_array(btrim(p_evidence_ref)),
    jsonb_build_object(
      'resource_id', p_resource_id,
      'resource_key', v_current.resource_key,
      'provider', v_current.provider,
      'from_state', v_current.state,
      'to_state', p_target_state,
      'eligibility_state', v_current.eligibility_state,
      'terms_state', v_current.terms_state,
      'activation_requires_payment_method', v_current.activation_requires_payment_method,
      'external_authority', 'NOT_GRANTED',
      'authority_effect', 'NONE'
    )
  )
  returning id into v_event_id;

  update scale_os.enterprise_resources_v1
     set state = p_target_state,
         last_event_id = v_event_id,
         updated_at = now(),
         external_authority = 'NOT_GRANTED',
         authority_effect = 'NONE'
   where id = p_resource_id;

  return query select 'STATE_UPDATED'::text, p_resource_id, v_event_id;
end;
$$;

revoke all on function scale_os.record_enterprise_resource_offer_v1(
  text, text, text, bigint, text, text, text, text, timestamptz
) from public, anon, authenticated;
revoke all on function scale_os.update_enterprise_resource_review_v1(
  uuid, text, text, text, boolean, text, text, text
) from public, anon, authenticated;
revoke all on function scale_os.transition_enterprise_resource_state_v1(
  uuid, text, text, text, text
) from public, anon, authenticated;

grant execute on function scale_os.record_enterprise_resource_offer_v1(
  text, text, text, bigint, text, text, text, text, timestamptz
) to service_role;
grant execute on function scale_os.update_enterprise_resource_review_v1(
  uuid, text, text, text, boolean, text, text, text
) to service_role;
grant execute on function scale_os.transition_enterprise_resource_state_v1(
  uuid, text, text, text, text
) to service_role;


-- Explicit ownership is part of the direct-enterprise-event INSERT boundary.
alter function scale_os.record_enterprise_resource_offer_v1(
  text, text, text, bigint, text, text, text, text, timestamptz
) owner to postgres;
alter function scale_os.update_enterprise_resource_review_v1(
  uuid, text, text, text, boolean, text, text, text
) owner to postgres;
alter function scale_os.transition_enterprise_resource_state_v1(
  uuid, text, text, text, text
) owner to postgres;
