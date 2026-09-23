import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sql = readFileSync(
  new URL('../../../supabase/migrations/20260922193000_scale_os_company_runtime_v2.sql', import.meta.url),
  'utf8',
)

function count(pattern) {
  return (sql.match(pattern) ?? []).length
}

test('migration extends existing scale_os instead of creating parallel company schema', () => {
  assert.ok(sql.includes('alter table scale_os.tasks'))
  assert.ok(sql.includes('alter table scale_os.approvals'))
  assert.equal(sql.includes('public.company_tasks_v1'), false)
  assert.equal(sql.includes('create schema'), false)
})

test('migration function structure is singular and approval regex is intact', () => {
  assert.equal(count(/create or replace function scale_os\.claim_task_lease_v2/gi), 1)
  assert.equal(count(/create or replace function scale_os\.complete_task_lease_v2/gi), 1)
  const claimStart=sql.indexOf('create or replace function scale_os.claim_task_lease_v2(')
  const claimEnd=sql.indexOf('create or replace function scale_os.complete_task_lease_v2(',claimStart)
  const claimSection=sql.slice(claimStart,claimEnd)
  assert.ok(claimSection.includes('p_task_digest text'))
  assert.ok(claimSection.includes('p_action_digest text'))
  assert.equal(claimSection.includes('p_lease_digest'),false)
  assert.ok(sql.includes("p_action_digest !~ '^[0-9a-f]{64}

test('V2 approval packet schema is validated before digest admission', () => {
  assert.ok(sql.includes('create or replace function scale_os.validate_consequential_action_packet_v2'))
  assert.ok(sql.includes('v_evidence_count < 1'))
  assert.ok(sql.includes('v_evidence_distinct <> v_evidence_count'))
  assert.ok(sql.includes("p_packet ->> 'cost_class' = 'NONE'"))
  assert.ok(sql.includes('9007199254740991'))
  assert.ok(sql.includes("'DENIED_PACKET_SCHEMA'"))
  assert.ok(sql.includes('scale_os.validate_consequential_action_packet_v2(approval_packet_v2)'))
  assert.ok(sql.includes('scale_os.validate_consequential_action_packet_v2(a.approval_packet_v2)'))
})

test('V2 approval digest is content-bound and grant generation is packet-bounded', () => {
  assert.ok(sql.includes('create or replace function scale_os.canonical_jsonb_v2'))
  assert.ok(sql.includes('create or replace function scale_os.consequential_action_packet_digest_v2'))
  assert.ok(sql.includes("'AEGIS_CONSEQUENTIAL_ACTION_PACKET_V1' || E'\\n'"))
  assert.ok(sql.includes('action_digest_v2 = scale_os.consequential_action_packet_digest_v2(approval_packet_v2)'))
  assert.ok(sql.includes("approval_packet_v2 ->> 'task_id' = task_id::text"))
  assert.ok(sql.includes("approval_packet_v2 ->> 'authority_effect' = 'NONE'"))
  assert.ok(sql.includes('grant_generation_v2 bigint'))
  assert.ok(sql.includes("grant_generation_v2 >= (approval_packet_v2 ->> 'created_generation')::bigint"))
  assert.ok(sql.includes("grant_generation_v2 <= (approval_packet_v2 ->> 'expires_generation')::bigint"))
  assert.ok(sql.includes('create or replace function scale_os.record_approval_v2'))
  assert.ok(sql.includes('from public, anon, authenticated, service_role'))
  assert.ok(sql.includes('scale_os.consequential_action_packet_digest_v2(a.approval_packet_v2) = a.action_digest_v2'))
  assert.ok(sql.includes('a.grant_generation_v2 <= p_current_generation'))
})

test('V2 approval rows cannot be fabricated by service_role while legacy approvals remain compatible', () => {
  assert.ok(sql.includes('create or replace function scale_os.prevent_direct_v2_approval_mutation_v2'))
  assert.ok(sql.includes('create trigger scale_os_v2_approval_direct_mutation_guard'))
  assert.ok(sql.includes("AEGIS_V2_APPROVAL_DIRECT_MUTATION_DENIED"))
  assert.ok(sql.includes("current_user <> 'postgres' and (v_old_v2 or v_new_v2)"))
  assert.ok(sql.includes('old.action_digest_v2 is not null'))
  assert.ok(sql.includes('new.action_digest_v2 is not null'))
  assert.ok(sql.includes('old.approval_packet_v2 is not null'))
  assert.ok(sql.includes('new.approval_packet_v2 is not null'))
  assert.ok(sql.includes('alter function scale_os.prevent_direct_v2_approval_mutation_v2()'))
})

test('new approvals require exact v2 digest packet grant and expiry without rewriting history', () => {
  assert.ok(sql.includes('action_digest_v2'))
  assert.ok(sql.includes('approval_packet_v2'))
  assert.ok(sql.includes('grant_id_v2'))
  assert.ok(sql.includes('grant_expires_at_v2'))
  assert.ok(sql.includes('not valid'))
})

test('durable DAG and one-row-per-task lease are defined once', () => {
  assert.equal(count(/create table if not exists scale_os\.task_dependencies_v2/gi), 1)
  assert.equal(count(/create table if not exists scale_os\.task_leases_v2/gi), 1)
  assert.ok(sql.includes('task_id uuid primary key'))
  assert.ok(sql.includes('primary key (task_id, depends_on_task_id)'))
})

test('nullable source fields stay inside the V2 digest boundary', () => {
  const start=sql.indexOf('create or replace function scale_os.company_task_digest_v2(')
  const end=sql.indexOf('alter function scale_os.canonical_jsonb_v2',start)
  const fn=sql.slice(start,end)
  assert.ok(fn.includes('called on null input'))
  assert.equal(/\bstrict\b/i.test(fn),false)
  assert.ok(fn.includes("nullif(btrim(coalesce(p_source_system,'')),'')"))
  assert.ok(fn.includes("nullif(btrim(coalesce(p_source_object_id,'')),'')"))
})

test('V2 task digest is server-derived and approval is derived from action class', () => {
  assert.ok(sql.includes('create or replace function scale_os.company_task_digest_v2'))
  assert.ok(sql.includes("'AEGIS_SCALE_OS_TASK_V2' || E'\\n'"))
  assert.ok(sql.includes("'action_class',p_action_class"))
  assert.ok(sql.includes('v_task_digest := scale_os.company_task_digest_v2'))
  assert.ok(sql.includes("v_requires_approval := p_action_class not in ('RESEARCH_READ','ANALYZE','DRAFT','LOCAL_SANDBOX_WRITE','TEST','EVAL','PROPOSE')"))
  assert.ok(sql.includes('add column if not exists action_class_v2 text'))
  assert.ok(sql.includes('scale_os_tasks_v2_authority_class'))
  assert.ok(sql.includes("return query select 'CREATED'::text, v_task_id, v_task_digest"))
  assert.ok(sql.includes("return query select 'REPLAYED'::text, v_existing.id, v_existing.task_digest_v2"))
  const createStart=sql.indexOf('create or replace function scale_os.create_task_v2(')
  const createEnd=sql.indexOf('create or replace function scale_os.add_task_dependency_v2(',createStart)
  const createSection=sql.slice(createStart,createEnd)
  assert.ok(createSection.includes('p_action_class text'))
  assert.equal(createSection.includes('p_requires_approval'),false)
  assert.equal(createSection.includes('p_task_digest text'),false)
  assert.equal(sql.includes("'DENIED_APPROVAL_REQUIRED_FOR_RISK'"),false)
  assert.ok(sql.includes('text, text, text, text, text, jsonb, text, bigint'))
})

test('V2 task admission preserves legacy rows while guarding V2-managed direct mutation', () => {
  assert.ok(sql.includes('create or replace function scale_os.prevent_direct_v2_task_mutation_v2'))
  assert.ok(sql.includes('create trigger scale_os_v2_task_direct_mutation_guard'))
  assert.ok(sql.includes("current_user <> 'postgres'"))
  assert.ok(sql.includes("'AEGIS_V2_TASK_DIRECT_INSERT_DENIED"))
  assert.ok(sql.includes("'AEGIS_V2_TASK_DIRECT_UPDATE_DENIED"))
  assert.ok(sql.includes("'AEGIS_V2_TASK_DIRECT_DELETE_DENIED"))
  assert.ok(sql.includes('new.task_digest_v2 is not null'))
  assert.ok(sql.includes('old.task_digest_v2 is not null'))
  assert.ok(sql.includes('new.action_class_v2 is not null'))
  assert.ok(sql.includes('old.action_class_v2 is not null'))
  assert.ok(sql.includes('create or replace function scale_os.create_task_v2'))
  assert.ok(sql.includes('on conflict (idempotency_key_v2)'))
  assert.ok(sql.includes("'DENIED_IDEMPOTENCY_COLLISION'"))
  assert.ok(sql.includes("return query select 'CREATED'::text"))
  assert.ok(sql.includes("return query select 'REPLAYED'::text"))
  assert.ok(sql.includes('alter function scale_os.create_task_v2'))
  assert.ok(sql.includes('alter function scale_os.prevent_direct_v2_task_mutation_v2'))
})

test('new v2 tables are service-role read-only and mutate only through postgres-owned RPCs', () => {
  assert.ok(sql.includes('revoke all on scale_os.task_dependencies_v2 from public, anon, authenticated, service_role'))
  assert.ok(sql.includes('revoke all on scale_os.task_leases_v2 from public, anon, authenticated, service_role'))
  assert.ok(sql.includes('grant select on scale_os.task_dependencies_v2 to service_role'))
  assert.ok(sql.includes('grant select on scale_os.task_leases_v2 to service_role'))
  assert.equal(/grant\s+select,\s*insert,\s*update,\s*delete\s+on\s+scale_os\.task_leases_v2/i.test(sql), false)
  assert.equal(/grant\s+select,\s*insert,\s*update,\s*delete\s+on\s+scale_os\.task_dependencies_v2/i.test(sql), false)
  assert.ok(sql.includes('create or replace function scale_os.add_task_dependency_v2'))
  assert.ok(sql.includes("'DENIED_SELF_DEPENDENCY'"))
  assert.ok(sql.includes("'DENIED_TASK_ALREADY_STARTED'"))
  assert.ok(sql.includes("'DENIED_DEPENDENCY_CYCLE'"))
  assert.ok(sql.includes("alter function scale_os.add_task_dependency_v2"))
  assert.equal((sql.match(/owner to postgres/gi) ?? []).length >= 3, true)
})

test('claim locks task and lease and requires completed dependencies', () => {
  assert.ok(sql.includes('where t.id = p_task_id\n   for update'))
  assert.ok(sql.includes('where l.task_id = p_task_id\n   for update'))
  assert.ok(sql.includes("dependency.status <> 'completed'"))
  assert.ok(sql.includes("'DENIED_DEPENDENCY_NOT_COMPLETED'"))
})

test('approval-required task claim is exact-action bound and expiry checked', () => {
  assert.ok(sql.includes('t.requires_approval'))
  assert.ok(sql.includes("'DENIED_APPROVAL_DIGEST_REQUIRED'"))
  assert.ok(sql.includes("a.decision = 'approved'"))
  assert.ok(sql.includes('a.action_digest_v2 = p_action_digest'))
  assert.ok(sql.includes("a.approval_packet_v2 ->> 'task_id' = p_task_id::text"))
  assert.ok(sql.includes("a.approval_packet_v2 ->> 'action_class' = v_action_class"))
  assert.ok(sql.includes("lower(coalesce(a.approval_packet_v2 ->> 'risk_class','')) = v_risk_level"))
  assert.ok(sql.includes("'DENIED_APPROVAL_CLASS_INVARIANT'"))
  assert.ok(sql.includes('a.grant_id_v2 is not null'))
  assert.ok(sql.includes('now() >= a.decision_at'))
  assert.ok(sql.includes('now() <= a.grant_expires_at_v2'))
  assert.ok(sql.includes("'DENIED_APPROVAL_NOT_ADMITTED'"))
  assert.ok(sql.includes("'DENIED_UNEXPECTED_APPROVAL_DIGEST'"))
})

test('V2 lease digest is server-derived and replay-bound to the exact claim envelope', () => {
  assert.ok(sql.includes('create or replace function scale_os.company_task_lease_digest_v2'))
  assert.ok(sql.includes("'AEGIS_SCALE_OS_TASK_LEASE_V2' || E'\\n'"))
  const claimStart=sql.indexOf('create or replace function scale_os.claim_task_lease_v2(')
  const claimEnd=sql.indexOf('create or replace function scale_os.complete_task_lease_v2(',claimStart)
  const claimSection=sql.slice(claimStart,claimEnd)
  assert.equal(claimSection.includes('p_lease_digest'),false)
  assert.ok(claimSection.includes('v_candidate_lease_digest := scale_os.company_task_lease_digest_v2'))
  assert.ok(claimSection.includes('v_lease.lease_digest = v_candidate_lease_digest'))
  assert.ok(claimSection.includes("return query select 'CLAIMED'::text, v_candidate_lease_digest"))
  assert.ok(sql.includes('uuid, text, text, text, bigint, bigint'))
  assert.equal(sql.includes('uuid, text, text, text, text, bigint, bigint'),false)
})

test('claim is digest-bound idempotent and cross-worker fail-closed', () => {
  assert.ok(sql.includes('v_canonical_digest <> p_task_digest'))
  assert.ok(sql.includes("'DENIED_TASK_DIGEST_MISMATCH'"))
  assert.ok(sql.includes("'REPLAYED'"))
  assert.ok(sql.includes("'DENIED_ALREADY_LEASED'"))
  assert.ok(sql.includes('p_current_generation >= v_lease.acquired_generation'))
  assert.ok(sql.includes('p_current_generation <= v_lease.expires_generation'))
})

test('completion uses worker plus lease digest as fencing token', () => {
  assert.ok(sql.includes('v_lease.worker_id <> p_worker_id'))
  assert.ok(sql.includes('v_lease.lease_digest <> p_lease_digest'))
  assert.ok(sql.includes("'DENIED_LEASE_FENCE'"))
  assert.ok(sql.includes("'DENIED_LEASE_EXPIRED'"))
})

test('client roles cannot call lease mutation RPCs', () => {
  assert.ok(sql.includes('from public, anon, authenticated'))
  assert.ok(sql.includes('to service_role'))
  assert.ok(sql.includes('force row level security'))
})
"))
  assert.equal(sql.includes("p_action_digest !~ '^[0-9a-f]{64}  if exists"), false)
})

test('V2 approval digest is content-bound and grant generation is packet-bounded', () => {
  assert.ok(sql.includes('create or replace function scale_os.canonical_jsonb_v2'))
  assert.ok(sql.includes('create or replace function scale_os.consequential_action_packet_digest_v2'))
  assert.ok(sql.includes("'AEGIS_CONSEQUENTIAL_ACTION_PACKET_V1' || E'\\n'"))
  assert.ok(sql.includes('action_digest_v2 = scale_os.consequential_action_packet_digest_v2(approval_packet_v2)'))
  assert.ok(sql.includes("approval_packet_v2 ->> 'task_id' = task_id::text"))
  assert.ok(sql.includes("approval_packet_v2 ->> 'authority_effect' = 'NONE'"))
  assert.ok(sql.includes('grant_generation_v2 bigint'))
  assert.ok(sql.includes("grant_generation_v2 >= (approval_packet_v2 ->> 'created_generation')::bigint"))
  assert.ok(sql.includes("grant_generation_v2 <= (approval_packet_v2 ->> 'expires_generation')::bigint"))
  assert.ok(sql.includes('create or replace function scale_os.record_approval_v2'))
  assert.ok(sql.includes('from public, anon, authenticated, service_role'))
  assert.ok(sql.includes('scale_os.consequential_action_packet_digest_v2(a.approval_packet_v2) = a.action_digest_v2'))
  assert.ok(sql.includes('a.grant_generation_v2 <= p_current_generation'))
})

test('V2 approval rows cannot be fabricated by service_role while legacy approvals remain compatible', () => {
  assert.ok(sql.includes('create or replace function scale_os.prevent_direct_v2_approval_mutation_v2'))
  assert.ok(sql.includes('create trigger scale_os_v2_approval_direct_mutation_guard'))
  assert.ok(sql.includes("AEGIS_V2_APPROVAL_DIRECT_MUTATION_DENIED"))
  assert.ok(sql.includes("current_user <> 'postgres' and (v_old_v2 or v_new_v2)"))
  assert.ok(sql.includes('old.action_digest_v2 is not null'))
  assert.ok(sql.includes('new.action_digest_v2 is not null'))
  assert.ok(sql.includes('old.approval_packet_v2 is not null'))
  assert.ok(sql.includes('new.approval_packet_v2 is not null'))
  assert.ok(sql.includes('alter function scale_os.prevent_direct_v2_approval_mutation_v2()'))
})

test('new approvals require exact v2 digest packet grant and expiry without rewriting history', () => {
  assert.ok(sql.includes('action_digest_v2'))
  assert.ok(sql.includes('approval_packet_v2'))
  assert.ok(sql.includes('grant_id_v2'))
  assert.ok(sql.includes('grant_expires_at_v2'))
  assert.ok(sql.includes('not valid'))
})

test('durable DAG and one-row-per-task lease are defined once', () => {
  assert.equal(count(/create table if not exists scale_os\.task_dependencies_v2/gi), 1)
  assert.equal(count(/create table if not exists scale_os\.task_leases_v2/gi), 1)
  assert.ok(sql.includes('task_id uuid primary key'))
  assert.ok(sql.includes('primary key (task_id, depends_on_task_id)'))
})

test('nullable source fields stay inside the V2 digest boundary', () => {
  const start=sql.indexOf('create or replace function scale_os.company_task_digest_v2(')
  const end=sql.indexOf('alter function scale_os.canonical_jsonb_v2',start)
  const fn=sql.slice(start,end)
  assert.ok(fn.includes('called on null input'))
  assert.equal(/\bstrict\b/i.test(fn),false)
  assert.ok(fn.includes("nullif(btrim(coalesce(p_source_system,'')),'')"))
  assert.ok(fn.includes("nullif(btrim(coalesce(p_source_object_id,'')),'')"))
})

test('V2 task digest is server-derived and high-risk admission is approval-gated', () => {
  assert.ok(sql.includes('create or replace function scale_os.company_task_digest_v2'))
  assert.ok(sql.includes("'AEGIS_SCALE_OS_TASK_V2' || E'\\n'"))
  assert.ok(sql.includes('v_task_digest := scale_os.company_task_digest_v2'))
  assert.ok(sql.includes("'DENIED_APPROVAL_REQUIRED_FOR_RISK'"))
  assert.ok(sql.includes("return query select 'CREATED'::text, v_task_id, v_task_digest"))
  assert.ok(sql.includes("return query select 'REPLAYED'::text, v_existing.id, v_existing.task_digest_v2"))
  const createStart=sql.indexOf('create or replace function scale_os.create_task_v2(')
  const createEnd=sql.indexOf('create or replace function scale_os.add_task_dependency_v2(',createStart)
  const createSection=sql.slice(createStart,createEnd)
  assert.equal(createSection.includes('p_task_digest text'),false)
  assert.equal(sql.includes('text, text, boolean, text, text, jsonb, text, text, bigint'),false)
  assert.ok(sql.includes('text, text, boolean, text, text, jsonb, text, bigint'))
})

test('V2 task admission preserves legacy rows while guarding V2-managed direct mutation', () => {
  assert.ok(sql.includes('create or replace function scale_os.prevent_direct_v2_task_mutation_v2'))
  assert.ok(sql.includes('create trigger scale_os_v2_task_direct_mutation_guard'))
  assert.ok(sql.includes("current_user <> 'postgres'"))
  assert.ok(sql.includes("'AEGIS_V2_TASK_DIRECT_INSERT_DENIED"))
  assert.ok(sql.includes("'AEGIS_V2_TASK_DIRECT_UPDATE_DENIED"))
  assert.ok(sql.includes("'AEGIS_V2_TASK_DIRECT_DELETE_DENIED"))
  assert.ok(sql.includes('new.task_digest_v2 is not null'))
  assert.ok(sql.includes('old.task_digest_v2 is not null'))
  assert.ok(sql.includes('create or replace function scale_os.create_task_v2'))
  assert.ok(sql.includes('on conflict (idempotency_key_v2)'))
  assert.ok(sql.includes("'DENIED_IDEMPOTENCY_COLLISION'"))
  assert.ok(sql.includes("return query select 'CREATED'::text"))
  assert.ok(sql.includes("return query select 'REPLAYED'::text"))
  assert.ok(sql.includes('alter function scale_os.create_task_v2'))
  assert.ok(sql.includes('alter function scale_os.prevent_direct_v2_task_mutation_v2'))
})

test('new v2 tables are service-role read-only and mutate only through postgres-owned RPCs', () => {
  assert.ok(sql.includes('revoke all on scale_os.task_dependencies_v2 from public, anon, authenticated, service_role'))
  assert.ok(sql.includes('revoke all on scale_os.task_leases_v2 from public, anon, authenticated, service_role'))
  assert.ok(sql.includes('grant select on scale_os.task_dependencies_v2 to service_role'))
  assert.ok(sql.includes('grant select on scale_os.task_leases_v2 to service_role'))
  assert.equal(/grant\s+select,\s*insert,\s*update,\s*delete\s+on\s+scale_os\.task_leases_v2/i.test(sql), false)
  assert.equal(/grant\s+select,\s*insert,\s*update,\s*delete\s+on\s+scale_os\.task_dependencies_v2/i.test(sql), false)
  assert.ok(sql.includes('create or replace function scale_os.add_task_dependency_v2'))
  assert.ok(sql.includes("'DENIED_SELF_DEPENDENCY'"))
  assert.ok(sql.includes("'DENIED_TASK_ALREADY_STARTED'"))
  assert.ok(sql.includes("'DENIED_DEPENDENCY_CYCLE'"))
  assert.ok(sql.includes("alter function scale_os.add_task_dependency_v2"))
  assert.equal((sql.match(/owner to postgres/gi) ?? []).length >= 3, true)
})

test('claim locks task and lease and requires completed dependencies', () => {
  assert.ok(sql.includes('where t.id = p_task_id\n   for update'))
  assert.ok(sql.includes('where l.task_id = p_task_id\n   for update'))
  assert.ok(sql.includes("dependency.status <> 'completed'"))
  assert.ok(sql.includes("'DENIED_DEPENDENCY_NOT_COMPLETED'"))
})

test('approval-required task claim is exact-action bound and expiry checked', () => {
  assert.ok(sql.includes('t.requires_approval'))
  assert.ok(sql.includes("'DENIED_APPROVAL_DIGEST_REQUIRED'"))
  assert.ok(sql.includes("a.decision = 'approved'"))
  assert.ok(sql.includes('a.action_digest_v2 = p_action_digest'))
  assert.ok(sql.includes("a.approval_packet_v2 ->> 'task_id' = p_task_id::text"))
  assert.ok(sql.includes('a.grant_id_v2 is not null'))
  assert.ok(sql.includes('now() >= a.decision_at'))
  assert.ok(sql.includes('now() <= a.grant_expires_at_v2'))
  assert.ok(sql.includes("'DENIED_APPROVAL_NOT_ADMITTED'"))
  assert.ok(sql.includes("'DENIED_UNEXPECTED_APPROVAL_DIGEST'"))
})

test('V2 lease digest is server-derived and replay-bound to the exact claim envelope', () => {
  assert.ok(sql.includes('create or replace function scale_os.company_task_lease_digest_v2'))
  assert.ok(sql.includes("'AEGIS_SCALE_OS_TASK_LEASE_V2' || E'\\n'"))
  const claimStart=sql.indexOf('create or replace function scale_os.claim_task_lease_v2(')
  const claimEnd=sql.indexOf('create or replace function scale_os.complete_task_lease_v2(',claimStart)
  const claimSection=sql.slice(claimStart,claimEnd)
  assert.equal(claimSection.includes('p_lease_digest'),false)
  assert.ok(claimSection.includes('v_candidate_lease_digest := scale_os.company_task_lease_digest_v2'))
  assert.ok(claimSection.includes('v_lease.lease_digest = v_candidate_lease_digest'))
  assert.ok(claimSection.includes("return query select 'CLAIMED'::text, v_candidate_lease_digest"))
  assert.ok(sql.includes('uuid, text, text, text, bigint, bigint'))
  assert.equal(sql.includes('uuid, text, text, text, text, bigint, bigint'),false)
})

test('claim is digest-bound idempotent and cross-worker fail-closed', () => {
  assert.ok(sql.includes('v_canonical_digest <> p_task_digest'))
  assert.ok(sql.includes("'DENIED_TASK_DIGEST_MISMATCH'"))
  assert.ok(sql.includes("'REPLAYED'"))
  assert.ok(sql.includes("'DENIED_ALREADY_LEASED'"))
  assert.ok(sql.includes('p_current_generation >= v_lease.acquired_generation'))
  assert.ok(sql.includes('p_current_generation <= v_lease.expires_generation'))
})

test('completion uses worker plus lease digest as fencing token', () => {
  assert.ok(sql.includes('v_lease.worker_id <> p_worker_id'))
  assert.ok(sql.includes('v_lease.lease_digest <> p_lease_digest'))
  assert.ok(sql.includes("'DENIED_LEASE_FENCE'"))
  assert.ok(sql.includes("'DENIED_LEASE_EXPIRED'"))
})

test('client roles cannot call lease mutation RPCs', () => {
  assert.ok(sql.includes('from public, anon, authenticated'))
  assert.ok(sql.includes('to service_role'))
  assert.ok(sql.includes('force row level security'))
})
