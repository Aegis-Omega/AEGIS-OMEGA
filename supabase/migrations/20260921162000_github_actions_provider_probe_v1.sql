-- AEGIS GitHub Actions provider probe V1.
-- Reads only public GitHub REST resources for PR #569 and derives hosted-runner
-- availability from exact-head job metadata. No reruns, mutations or credentials.
-- authority_effect = NONE.

begin;

create or replace function public.probe_github_actions_provider_v1()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  pr_response extensions.http_response;
  runs_response extensions.http_response;
  jobs_response extensions.http_response;
  pr_json jsonb;
  runs_json jsonb;
  jobs_json jsonb;
  run_json jsonb;
  job_json jsonb;
  workflow_name text;
  target_workflows text[] := array[
    'Sovereignty Contracts',
    'Integration Ledger',
    'AEGIS Automaton-3',
    'Kernel One',
    'Hadolint'
  ];
  head_sha text;
  executed_count integer := 0;
  prestart_count integer := 0;
  pending_count integer := 0;
  missing_count integer := 0;
  api_fail_count integer := 0;
  job_count integer := 0;
  evidence_parts text := '';
  provider_state text := 'UNKNOWN';
  blocker text := 'INCOMPLETE_GITHUB_EVIDENCE';
  evidence_hash text;
begin
  pr_response := extensions.http_get(
    'https://api.github.com/repos/Aegis-Omega/AEGIS-OMEGA/pulls/569'::varchar
  );
  if pr_response.status <> 200 then
    raise exception 'GitHub PR probe failed with HTTP %', pr_response.status;
  end if;

  pr_json := pr_response.content::jsonb;
  head_sha := pr_json #>> '{head,sha}';
  if head_sha is null or head_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'GitHub PR probe returned invalid head';
  end if;

  runs_response := extensions.http_get(
    (
      'https://api.github.com/repos/Aegis-Omega/AEGIS-OMEGA/actions/runs'
      || '?event=pull_request&head_sha=' || head_sha || '&per_page=100'
    )::varchar
  );
  if runs_response.status <> 200 then
    raise exception 'GitHub workflow probe failed with HTTP %', runs_response.status;
  end if;
  runs_json := runs_response.content::jsonb;

  foreach workflow_name in array target_workflows
  loop
    run_json := null;

    select elem
    into run_json
    from jsonb_array_elements(coalesce(runs_json->'workflow_runs','[]'::jsonb)) elem
    where elem->>'name' = workflow_name
    order by (elem->>'created_at')::timestamptz desc
    limit 1;

    if run_json is null then
      missing_count := missing_count + 1;
      evidence_parts := evidence_parts || format(E'%s|MISSING\n', workflow_name);
      continue;
    end if;

    if run_json->>'status' <> 'completed' then
      pending_count := pending_count + 1;
      evidence_parts := evidence_parts || format(
        E'%s|run=%s|status=%s|conclusion=%s|PENDING\n',
        workflow_name,
        coalesce(run_json->>'id',''),
        coalesce(run_json->>'status',''),
        coalesce(run_json->>'conclusion','')
      );
      continue;
    end if;

    jobs_response := extensions.http_get((run_json->>'jobs_url')::varchar);
    if jobs_response.status <> 200 then
      api_fail_count := api_fail_count + 1;
      evidence_parts := evidence_parts || format(
        E'%s|run=%s|JOBS_HTTP_%s\n',
        workflow_name,
        coalesce(run_json->>'id',''),
        jobs_response.status
      );
      continue;
    end if;

    jobs_json := jobs_response.content::jsonb;

    if jsonb_array_length(coalesce(jobs_json->'jobs','[]'::jsonb)) = 0 then
      missing_count := missing_count + 1;
      evidence_parts := evidence_parts || format(
        E'%s|run=%s|NO_JOBS\n',
        workflow_name,
        coalesce(run_json->>'id','')
      );
      continue;
    end if;

    for job_json in
      select elem
      from jsonb_array_elements(coalesce(jobs_json->'jobs','[]'::jsonb)) elem
    loop
      job_count := job_count + 1;

      if coalesce((job_json->>'runner_id')::bigint,0) > 0
         and jsonb_array_length(coalesce(job_json->'steps','[]'::jsonb)) > 0 then
        executed_count := executed_count + 1;
      elsif job_json->>'status' = 'completed'
         and coalesce((job_json->>'runner_id')::bigint,0) = 0
         and jsonb_array_length(coalesce(job_json->'steps','[]'::jsonb)) = 0 then
        prestart_count := prestart_count + 1;
      end if;

      evidence_parts := evidence_parts || format(
        E'%s|run=%s|job=%s|job_status=%s|job_conclusion=%s|runner_id=%s|steps=%s\n',
        workflow_name,
        coalesce(run_json->>'id',''),
        coalesce(job_json->>'id',''),
        coalesce(job_json->>'status',''),
        coalesce(job_json->>'conclusion',''),
        coalesce(job_json->>'runner_id','0'),
        jsonb_array_length(coalesce(job_json->'steps','[]'::jsonb))
      );
    end loop;
  end loop;

  if executed_count > 0 then
    provider_state := 'OBSERVED_AVAILABLE';
    blocker := null;
  elsif pending_count = 0
    and missing_count = 0
    and api_fail_count = 0
    and job_count >= array_length(target_workflows,1)
    and prestart_count = job_count then
    provider_state := 'OBSERVED_UNAVAILABLE';
    blocker := 'RUNNER_UNASSIGNED_PRESTART';
  end if;

  evidence_hash := encode(
    extensions.digest(
      convert_to(
        concat_ws(
          '|',
          'AEGIS_GITHUB_ACTIONS_PROVIDER_PROBE_V1',
          head_sha,
          provider_state,
          coalesce(blocker,''),
          executed_count::text,
          prestart_count::text,
          pending_count::text,
          missing_count::text,
          api_fail_count::text,
          job_count::text,
          evidence_parts
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
    'github-actions',
    'EXECUTION',
    provider_state,
    array['DURABLE_RUNNER','REPOSITORY_WORKFLOW'],
    blocker,
    'AUTO_GITHUB_PUBLIC_API_RUNNER_PROBE_V1',
    evidence_hash,
    'NONE',
    now() + interval '30 minutes'
  );

  return jsonb_build_object(
    'head_sha', head_sha,
    'state', provider_state,
    'blocker', blocker,
    'executed_jobs', executed_count,
    'prestart_jobs', prestart_count,
    'pending_workflows', pending_count,
    'missing_workflows', missing_count,
    'api_failures', api_fail_count,
    'job_count', job_count,
    'evidence_hash', evidence_hash,
    'authority_effect', 'NONE'
  );
end;
$$;

revoke all on function public.probe_github_actions_provider_v1()
  from public, anon, authenticated;
grant execute on function public.probe_github_actions_provider_v1()
  to service_role;

do $$
declare
  job record;
begin
  for job in
    select jobid
    from cron.job
    where jobname = 'aegis-github-actions-provider-probe-v1'
  loop
    perform cron.unschedule(job.jobid);
  end loop;
end
$$;

select cron.schedule(
  'aegis-github-actions-provider-probe-v1',
  '7-59/20 * * * *',
  'select public.probe_github_actions_provider_v1();'
);

commit;
