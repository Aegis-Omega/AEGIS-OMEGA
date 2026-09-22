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

function stripLineComments(source) {
  return source.replace(/--.*$/gm, '')
}

function balancedSql(source) {
  let quote = false
  let dollar = false
  let depth = 0

  for (let i = 0; i < source.length; i += 1) {
    if (!quote && source.slice(i, i + 2) === '$$') {
      dollar = !dollar
      i += 1
      continue
    }
    if (dollar) continue

    const ch = source[i]
    if (ch === "'") {
      if (quote && source[i + 1] === "'") {
        i += 1
        continue
      }
      quote = !quote
      continue
    }
    if (quote) continue
    if (ch === '(') depth += 1
    if (ch === ')') depth -= 1
    if (depth < 0) return false
  }

  return !quote && !dollar && depth === 0
}

test('lease migration has balanced SQL quotes, dollar blocks and parentheses', () => {
  assert.equal(balancedSql(stripLineComments(sql)), true)
})

test('durable lease objects are defined exactly once', () => {
  assert.equal(
    occurrences(/create table if not exists public\.company_task_dependencies_v1/gi),
    1,
  )
  assert.equal(
    occurrences(/create table if not exists public\.company_task_leases_v1/gi),
    1,
  )
  assert.equal(
    occurrences(/create or replace function public\.claim_company_task_lease_v1/gi),
    1,
  )
  assert.equal(
    occurrences(/create or replace function public\.complete_company_task_lease_v1/gi),
    1,
  )
})

test('all lease SHA-256 regexes are closed', () => {
  assert.equal(sql.includes("^[0-9a-f]{64}'"), false)
  assert.equal(sql.includes("^[0-9a-f]{64}\n"), false)
  assert.ok((sql.match(/\^\[0-9a-f\]\{64\}\$/g) ?? []).length >= 7)
})

test('claim path locks task and existing lease rows before decision', () => {
  assert.ok(sql.includes("where t.task_id = p_task_id\n   for update"))
  assert.ok(sql.includes("where l.task_id = p_task_id\n   for update"))
  assert.ok(sql.includes("'DENIED_ALREADY_LEASED'"))
  assert.ok(sql.includes("'REPLAYED'"))
  assert.ok(sql.includes("'CLAIMED'"))
})

test('claim binds request digest to canonical durable task digest', () => {
  assert.ok(sql.includes('add column if not exists task_digest text'))
  assert.ok(sql.includes('into v_status, v_canonical_task_digest'))
  assert.ok(sql.includes('v_canonical_task_digest <> p_task_digest'))
  assert.ok(sql.includes("'DENIED_TASK_DIGEST_MISMATCH'"))
})

test('claim requires all durable dependencies VERIFIED', () => {
  assert.ok(sql.includes('company_task_dependencies_v1 as d'))
  assert.ok(sql.includes("dependency.status <> 'VERIFIED'"))
  assert.ok(sql.includes("'DENIED_DEPENDENCY_NOT_VERIFIED'"))
})

test('idempotent replay is valid only inside acquired-to-expiry interval', () => {
  assert.ok(sql.includes('p_current_generation >= v_lease.acquired_generation'))
  assert.ok(sql.includes('p_current_generation <= v_lease.expires_generation'))
})

test('completion uses lease worker and digest as fencing token', () => {
  assert.ok(sql.includes('v_lease.worker_id <> p_worker_id'))
  assert.ok(sql.includes('v_lease.lease_digest <> p_lease_digest'))
  assert.ok(sql.includes("'DENIED_LEASE_FENCE'"))
  assert.ok(sql.includes("'DENIED_LEASE_EXPIRED'"))
  assert.ok(sql.includes("lease_state = 'RELEASED'"))
})

test('lease cannot grant external authority and RPCs are service-role only', () => {
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
