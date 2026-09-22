import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sql = readFileSync(
  new URL('../../../supabase/migrations/20260922171000_autonomous_company_work_ledger_v1.sql', import.meta.url),
  'utf8',
)

function stripLineComments(source) {
  return source.replace(/--.*$/gm, '')
}

function balancedSql(source) {
  let quote = false
  let depth = 0
  for (let i = 0; i < source.length; i += 1) {
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
  return !quote && depth === 0
}

test('migration has balanced SQL quotes and parentheses', () => {
  assert.equal(balancedSql(stripLineComments(sql)), true)
})

test('each company table is defined exactly once', () => {
  const names = [
    'company_objectives_v1',
    'company_tasks_v1',
    'company_evidence_v1',
    'company_operator_actions_v1',
    'company_events_v1',
  ]
  for (const name of names) {
    const matches = sql.match(
      new RegExp('create\\s+table\\s+if\\s+not\\s+exists\\s+public\\.' + name, 'gi'),
    ) ?? []
    assert.equal(matches.length, 1, name)
  }
})

test('all SHA-256 constraints are closed lowercase-hex regexes', () => {
  assert.equal(sql.includes("^[0-9a-f]{64}'"), false)
  assert.equal(sql.includes("^[0-9a-f]{64}\n"), false)
  const valid = sql.match(/\^\[0-9a-f\]\{64\}\$/g) ?? []
  assert.ok(valid.length >= 8, 'expected all content-addressed fields to be constrained')
})

test('approval ledger binds packet, risk, cost, generation interval and grant', () => {
  for (const required of [
    'packet_id text not null',
    'packet_digest text not null unique',
    'packet jsonb not null',
    'risk_class text not null',
    'cost_class text not null',
    'created_generation bigint not null',
    'expires_generation bigint not null',
    'expires_generation >= created_generation',
    "decision = 'APPROVED'",
    'grant_id is not null',
    'granted_generation is not null',
  ]) {
    assert.ok(sql.includes(required), required)
  }
})

test('evidence authority and measurement state are durable fields', () => {
  assert.ok(sql.includes('evidence_authority text not null'))
  assert.ok(sql.includes('measurement_state text'))
  assert.ok(sql.includes("'DIRECT_OBSERVATION'"))
  assert.ok(sql.includes("'PROVIDER_ATTESTATION'"))
  assert.ok(sql.includes("'NOT_MEASURED'"))
  assert.ok(sql.includes("'NOT_VERIFIED'"))
})

test('all company tables enable and force RLS and revoke client roles', () => {
  const names = [
    'company_objectives_v1',
    'company_tasks_v1',
    'company_evidence_v1',
    'company_operator_actions_v1',
    'company_events_v1',
  ]
  for (const name of names) {
    assert.ok(sql.includes(`alter table public.${name} enable row level security;`))
    assert.ok(sql.includes(`alter table public.${name} force row level security;`))
    assert.ok(sql.includes(`revoke all on public.${name} from anon, authenticated;`))
  }
})
