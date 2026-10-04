-- AEGIS Cloudflare provider probe V1.
-- Distinguishes a live Worker from a source-bound Worker and checks only
-- pre-model Anthropic secret presence using a malformed request.
-- No model inference is executed. authority_effect = NONE.

begin;

create or replace function public.probe_cloudflare_provider_v1()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  health_response extensions.http_response;
  secret_response extensions.http_response;
  health_json jsonb;
  worker_state text := 'UNKNOWN';
  worker_blocker text := 'HEALTH_PROBE_FAILED';
  bridge_state text := 'UNKNOWN';
  bridge_blocker text := 'SECRET_PROBE_UNCLASSIFIED';
  worker_hash text;
  bridge_hash text;
begin
  health_response := extensions.http_get(
    'https://aegis-vertex.aegisomega.com/health'::varchar
  );

  if health_response.status = 200 then
    begin
      health_json := health_response.content::jsonb;
    exception when others then
      health_json := '{}'::jsonb;
    end;

    if health_json ->> 'verified' = 'false'
       and health_json ->> 'verification' = 'no_gate_at_edge'
       and not (health_json ? 'pgcs_passes') then
      worker_state := 'OBSERVED_AVAILABLE';
      worker_blocker := null;
    else
      worker_state := 'NETWORK_REACHABLE';
      worker_blocker := 'DEPLOYED_SOURCE_DRIFT';
    end if;
  end if;

  worker_hash := encode(
    extensions.digest(
      convert_to(
        concat_ws(
          '|',
          'AEGIS_CLOUDFLARE_WORKER_PROBE_V1',
          health_response.status::text,
          health_response.content,
          worker_state,
          coalesce(worker_blocker,'')
        ),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into public.provider_runtime_observations_v1(
    provider_id, plane, observation_state, capabilities,
    blocker_code, evidence_kind, evidence_hash, authority_effect, expires_at
  ) values (
    'cloudflare-worker',
    'EXECUTION',
    worker_state,
    array['SERVERLESS_FUNCTION','HTTP_EGRESS'],
    worker_blocker,
    'AUTO_CLOUDFLARE_HEALTH_SEMANTICS_V1',
    worker_hash,
    'NONE',
    now() + interval '20 minutes'
  );

  secret_response := extensions.http_post(
    'https://aegis-vertex.aegisomega.com/platform/collaborate'::varchar,
    'AEGIS_NOT_JSON'::varchar,
    'text/plain'::varchar
  );

  if secret_response.status = 401
     and secret_response.content like '%ANTHROPIC_API_KEY not configured%' then
    bridge_state := 'CREDENTIAL_MISSING';
    bridge_blocker := 'ANTHROPIC_API_KEY_NOT_CONFIGURED';
  elsif secret_response.status = 500 then
    bridge_state := 'CONFIGURED';
    bridge_blocker := 'SECRET_PRESENT_NOT_VALIDATED';
  end if;

  bridge_hash := encode(
    extensions.digest(
      convert_to(
        concat_ws(
          '|',
          'AEGIS_CLOUDFLARE_ANTHROPIC_SECRET_PROBE_V1',
          secret_response.status::text,
          secret_response.content,
          bridge_state,
          coalesce(bridge_blocker,'')
        ),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  insert into public.provider_runtime_observations_v1(
    provider_id, plane, observation_state, capabilities,
    blocker_code, evidence_kind, evidence_hash, authority_effect, expires_at
  ) values (
    'cloudflare-anthropic',
    'INTELLIGENCE',
    bridge_state,
    array['AGENT_EXECUTION','MODEL_INFERENCE'],
    bridge_blocker,
    'AUTO_CLOUDFLARE_ANTHROPIC_SECRET_PROBE_V1',
    bridge_hash,
    'NONE',
    now() + interval '20 minutes'
  );

  return jsonb_build_object(
    'cloudflare_worker_state', worker_state,
    'cloudflare_worker_evidence_hash', worker_hash,
    'cloudflare_anthropic_state', bridge_state,
    'cloudflare_anthropic_evidence_hash', bridge_hash,
    'authority_effect', 'NONE'
  );
end;
$$;

revoke all on function public.probe_cloudflare_provider_v1()
  from public, anon, authenticated;
grant execute on function public.probe_cloudflare_provider_v1()
  to service_role;

do $$
declare
  job record;
begin
  for job in
    select jobid
    from cron.job
    where jobname = 'aegis-cloudflare-provider-probe-v1'
  loop
    perform cron.unschedule(job.jobid);
  end loop;
end
$$;

select cron.schedule(
  'aegis-cloudflare-provider-probe-v1',
  '5-59/10 * * * *',
  'select public.probe_cloudflare_provider_v1();'
);

commit;
