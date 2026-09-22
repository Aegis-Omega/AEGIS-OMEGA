import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sql = readFileSync(
  new URL('../../../supabase/migrations/20260922211500_scale_os_enterprise_resources_v1.sql', import.meta.url),
  'utf8',
)

function count(pattern) { return (sql.match(pattern) ?? []).length }

test('resource registry stores one current snapshot and reuses scale_os events', () => {
  assert.equal(count(/create table if not exists scale_os\.enterprise_resources_v1/gi), 1)
  assert.equal(sql.includes('create table if not exists scale_os.enterprise_resource_events'), false)
  assert.ok(sql.includes('insert into scale_os.events'))
  assert.ok(sql.includes("'enterprise_resource_state_v1'"))
})

test('eligibility and terms are explicit independent gates', () => {
  assert.ok(sql.includes("eligibility_state in ('NOT_VERIFIED','ELIGIBLE','INELIGIBLE','NOT_APPLICABLE')"))
  assert.ok(sql.includes("terms_state in ('NOT_REVIEWED','REVIEWED','NOT_APPLICABLE')"))
  assert.ok(sql.includes("'DENIED_RESOURCE_REVIEW_INCOMPLETE'"))
})

test('offered to claimed to active transitions are sequential', () => {
  assert.ok(sql.includes("if v_current.state <> 'OFFERED'"))
  assert.ok(sql.includes("if v_current.state <> 'CLAIMED'"))
  assert.ok(sql.includes("'DENIED_RESOURCE_STATE_TRANSITION'"))
})

test('terminal expired or rejected resources cannot be silently revived', () => {
  assert.ok(sql.includes("v_current.state in ('EXPIRED','REJECTED')"))
  assert.ok(sql.includes("'DENIED_TERMINAL_RESOURCE_STATE'"))
})

test('offer recording is idempotent and collision-sensitive', () => {
  assert.ok(sql.includes('on conflict (resource_key) do nothing'))
  assert.ok(sql.includes("'REPLAYED_EXISTING'"))
  assert.ok(sql.includes("'DENIED_RESOURCE_KEY_COLLISION'"))
})

test('resource evidence cannot be reused for a second transition', () => {
  assert.ok(sql.includes("e.evidence_refs @> jsonb_build_array(btrim(p_evidence_ref))"))
  assert.ok(sql.includes("'DENIED_EVIDENCE_REUSE'"))
})

test('snapshot table is read-only to service role and mutations are RPC-only', () => {
  assert.ok(sql.includes('force row level security'))
  assert.ok(sql.includes('revoke all on scale_os.enterprise_resources_v1'))
  assert.ok(sql.includes('grant select on scale_os.enterprise_resources_v1'))
  assert.equal(/grant\s+(insert|update|delete)[^;]*enterprise_resources_v1/i.test(sql), false)
  assert.equal(count(/to service_role;/gi) >= 4, true)
})

test('resource registry remains authority-neutral', () => {
  assert.ok(sql.includes("external_authority text not null default 'NOT_GRANTED'"))
  assert.ok(sql.includes("authority_effect text not null default 'NONE'"))
  assert.ok(sql.includes("'external_authority', 'NOT_GRANTED'"))
  assert.ok(sql.includes("'authority_effect', 'NONE'"))
})
