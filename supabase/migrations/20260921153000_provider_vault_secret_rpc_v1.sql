-- Service-role-only Vault read path for provider runtime credentials.
-- Secret values remain runtime-only and are never committed.

begin;

create or replace function public.get_provider_secret_v1(p_name text)
returns text
language sql
security definer
set search_path = ''
as $$
  select ds.decrypted_secret
  from vault.decrypted_secrets ds
  where ds.name = p_name
  limit 1;
$$;

revoke all on function public.get_provider_secret_v1(text)
  from public, anon, authenticated;

grant execute on function public.get_provider_secret_v1(text)
  to service_role;

comment on function public.get_provider_secret_v1(text) is
  'AEGIS service-role-only Vault read path for provider runtime credentials.';

commit;
