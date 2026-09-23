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
