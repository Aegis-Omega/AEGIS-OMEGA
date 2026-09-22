import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sql = readFileSync(
  new URL('../../../supabase/migrations/20260922180000_company_task_lease_fencing_v1.sql', import.meta.url),
  'utf8',
)

function occurrences(pattern) {
  return (sql.match(pattern) ?? []).length
}

test('durable lease layer has one dependency and one lease table', () => {
  assert.equal(occurrences(/create table if not exists public\.company_task_dependencies_v1/gi), 1)
  assert.equal(occurrences(/create table if not exists public\.company_task_leases_v1/gi), 1)
  assert.ok(sql.includes('primary key (task_id, depends_on_task_id)'))
  assert.ok(sql.includes('task_id text primary key'))
})

test('claim path locks task and existing lease rows before decision', () => {
  assert.ok(sql.includes("where t.task_id = p_task_id\n   for update"))
  assert.ok(sql.includes("where l.task_id = p_task_id\n   for update"))
  assert.ok(sql.includes("'DENIED_ALREADY_LEASED'"))
  assert.ok(sql.includes("'REPLAYED'"))
  assert.ok(sql.includes("'CLAIMED'"))
})

test('claim requires all durable dependencies VERIFIED', () => {
  assert.ok(sql.includes('company_task_dependencies_v1 as d'))
  assert.ok(sql.includes("dependency.status <> 'VERIFIED'"))
  assert.ok(sql.includes("'DENIED_DEPENDENCY_NOT_VERIFIED'"))
})

test('expired running task may be reclaimed but inconsistent running state fails closed', () => {
  assert.ok(sql.includes("v_status = 'RUNNING'"))
  assert.ok(sql.includes("'DENIED_INCONSISTENT_RUNNING'"))
  assert.ok(sql.includes('p_current_generation <= v_lease.expires_generation'))
})

test('completion uses lease digest and worker as fencing token', () => {
  assert.ok(sql.includes('v_lease.worker_id <> p_worker_id'))
  assert.ok(sql.includes('v_lease.lease_digest <> p_lease_digest'))
  assert.ok(sql.includes("'DENIED_LEASE_FENCE'"))
  assert.ok(sql.includes("'DENIED_LEASE_EXPIRED'"))
  assert.ok(sql.includes("lease_state = 'RELEASED'"))
})

test('lease cannot grant external authority and client roles cannot execute claim RPCs', () => {
  assert.ok(sql.includes("external_authority = 'NOT_GRANTED'"))
  assert.ok(sql.includes("authority_effect = 'NONE'"))
  assert.ok(sql.includes('revoke all on function public.claim_company_task_lease_v1'))
  assert.ok(sql.includes('revoke all on function public.complete_company_task_lease_v1'))
  assert.ok(sql.includes('to service_role;'))
})

test('lease tables force RLS and are not directly client-accessible', () => {
  for (const table of ['company_task_dependencies_v1', 'company_task_leases_v1']) {
    assert.ok(sql.includes(`alter table public.${table} enable row level security;`))
    assert.ok(sql.includes(`alter table public.${table} force row level security;`))
    assert.ok(sql.includes(`revoke all on public.${table} from anon, authenticated;`))
  }
})
