-- Make provider evidence ledgers append-only at the storage boundary.
-- Selection receipts remain writable only through record_provider_selection_v1().
-- authority_effect = NONE.

begin;

do $guard$
begin
  if to_regclass('public.provider_runtime_observations_v1') is null then
    raise exception 'missing public.provider_runtime_observations_v1';
  end if;
  if to_regclass('public.provider_selection_receipts_v1') is null then
    raise exception 'missing public.provider_selection_receipts_v1';
  end if;
  if to_regprocedure(
    'public.record_provider_selection_v1(text,text,text,text,text)'
  ) is null then
    raise exception 'missing public.record_provider_selection_v1(text,text,text,text,text)';
  end if;
  if not exists (
    select 1
    from pg_catalog.pg_proc p
    where p.oid = to_regprocedure(
      'public.record_provider_selection_v1(text,text,text,text,text)'
    )
      and p.prosecdef
      and pg_catalog.pg_get_userbyid(p.proowner) <> 'service_role'
  ) then
    raise exception 'record_provider_selection_v1 must be SECURITY DEFINER and owned outside service_role';
  end if;
end;
$guard$;

create or replace function public.reject_provider_evidence_ledger_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path = ''
as $function$
begin
  raise exception using
    errcode = '55000',
    message = format(
      'AEGIS provider evidence ledger %I is append-only; %s is forbidden',
      tg_table_name,
      tg_op
    );
end;
$function$;

revoke all on function public.reject_provider_evidence_ledger_mutation_v1()
  from public, anon, authenticated, service_role;

drop trigger if exists provider_runtime_observations_v1_append_only
  on public.provider_runtime_observations_v1;
create trigger provider_runtime_observations_v1_append_only
  before update or delete or truncate
  on public.provider_runtime_observations_v1
  for each statement
  execute function public.reject_provider_evidence_ledger_mutation_v1();

drop trigger if exists provider_selection_receipts_v1_append_only
  on public.provider_selection_receipts_v1;
create trigger provider_selection_receipts_v1_append_only
  before update or delete or truncate
  on public.provider_selection_receipts_v1
  for each statement
  execute function public.reject_provider_evidence_ledger_mutation_v1();

grant select, insert on table public.provider_runtime_observations_v1
  to service_role;
revoke update, delete, truncate, references, trigger
  on table public.provider_runtime_observations_v1
  from service_role;

grant select on table public.provider_selection_receipts_v1
  to service_role;
revoke insert, update, delete, truncate, references, trigger
  on table public.provider_selection_receipts_v1
  from service_role;

grant execute on function public.record_provider_selection_v1(
  text,
  text,
  text,
  text,
  text
) to service_role;

commit;
