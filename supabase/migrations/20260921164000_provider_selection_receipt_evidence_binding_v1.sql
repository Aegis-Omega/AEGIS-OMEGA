-- Harden provider selection receipts against forged provider/evidence bindings.
-- A SELECTED receipt must match the current fresh eligible observation.
-- A NO_OBSERVED_PROVIDER denial is rejected if an eligible provider exists.
-- authority_effect = NONE.

begin;

create or replace function public.record_provider_selection_v1(
  p_capability text,
  p_outcome text,
  p_provider_id text,
  p_provider_evidence_hash text,
  p_denial_code text
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_snapshot_root text;
  v_selected_at timestamptz := clock_timestamp();
  v_selected_at_text text;
  v_receipt_hash text;
  v_candidate_exists boolean;
begin
  if p_outcome not in ('SELECTED','DENIED') then
    raise exception 'invalid provider selection outcome';
  end if;

  if p_outcome = 'SELECTED' then
    if p_provider_id is null or p_provider_evidence_hash is null then
      raise exception 'selected provider receipt requires provider evidence';
    end if;
    if p_provider_evidence_hash !~ '^[0-9a-f]{64}$' then
      raise exception 'invalid provider evidence hash';
    end if;
    if p_denial_code is not null then
      raise exception 'selected provider receipt cannot contain denial code';
    end if;

    select exists(
      select 1
      from public.provider_runtime_latest_v1 v
      where v.provider_id = p_provider_id
        and v.observation_state = 'OBSERVED_AVAILABLE'
        and not v.is_expired
        and p_capability = any(v.capabilities)
        and v.evidence_hash = p_provider_evidence_hash
    )
    into v_candidate_exists;

    if not v_candidate_exists then
      raise exception 'selected provider evidence is not current and eligible';
    end if;
  else
    if p_provider_id is not null or p_provider_evidence_hash is not null then
      raise exception 'denied provider receipt cannot bind provider evidence';
    end if;
    if p_denial_code is null or btrim(p_denial_code) = '' then
      raise exception 'denied provider receipt requires denial code';
    end if;

    if p_denial_code = 'NO_OBSERVED_PROVIDER' then
      select exists(
        select 1
        from public.provider_runtime_latest_v1 v
        where v.observation_state = 'OBSERVED_AVAILABLE'
          and not v.is_expired
          and p_capability = any(v.capabilities)
      )
      into v_candidate_exists;

      if v_candidate_exists then
        raise exception 'cannot record NO_OBSERVED_PROVIDER while an eligible provider exists';
      end if;
    end if;
  end if;

  v_snapshot_root := public.provider_runtime_snapshot_root_v1();
  v_selected_at_text := to_char(
    v_selected_at at time zone 'UTC',
    'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
  );

  v_receipt_hash := encode(
    extensions.digest(
      convert_to(
        concat_ws(
          '|',
          'AEGIS_PROVIDER_SELECTION_RECEIPT_V1',
          p_capability,
          p_outcome,
          coalesce(p_provider_id, ''),
          coalesce(p_provider_evidence_hash, ''),
          coalesce(p_denial_code, ''),
          v_snapshot_root,
          v_selected_at_text,
          'NONE'
        ),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into public.provider_selection_receipts_v1(
    capability,
    outcome,
    provider_id,
    provider_evidence_hash,
    denial_code,
    runtime_snapshot_root,
    authority_effect,
    selected_at,
    receipt_hash
  ) values (
    p_capability,
    p_outcome,
    p_provider_id,
    p_provider_evidence_hash,
    p_denial_code,
    v_snapshot_root,
    'NONE',
    v_selected_at,
    v_receipt_hash
  );

  return v_receipt_hash;
end;
$$;

revoke all on function public.record_provider_selection_v1(text,text,text,text,text)
  from public, anon, authenticated;
grant execute on function public.record_provider_selection_v1(text,text,text,text,text)
  to service_role;

commit;
