import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sql = readFileSync(
  new URL('../../../supabase/migrations/20260922205500_scale_os_enterprise_opportunities_v1.sql', import.meta.url),
  'utf8',
)

function count(pattern) {
  return (sql.match(pattern) ?? []).length
}

test('enterprise pipeline reuses scale_os events instead of creating a parallel event ledger', () => {
  assert.equal(count(/create table if not exists scale_os\.enterprise_opportunities_v1/gi), 1)
  assert.equal(sql.includes('create table if not exists scale_os.enterprise_opportunity_events'), false)
  assert.ok(sql.includes('insert into scale_os.events'))
  assert.ok(sql.includes("'enterprise_opportunity_stage_v1'"))
})

test('snapshot stage set matches the evidence-bound enterprise pipeline', () => {
  for (const stage of [
    'DISCOVERED','CONTACTED','QUALIFIED_REPLY','SCOPING_CALL_HELD',
    'WRITTEN_SCOPE_AGREED','PAYMENT_RECEIVED','AUDIT_STARTED','CLOSED_LOST',
  ]) assert.ok(sql.includes(`'${stage}'`))
})

test('stage advancement is sequential and terminal stages fail closed', () => {
  assert.ok(sql.includes("v_to_rank <> v_from_rank + 1"))
  assert.ok(sql.includes("'DENIED_STAGE_SKIP'"))
  assert.ok(sql.includes("v_current.stage in ('AUDIT_STARTED','CLOSED_LOST')"))
  assert.ok(sql.includes("'DENIED_TERMINAL_STAGE'"))
})

test('outbound sent payment and audit start require direct observation', () => {
  assert.ok(sql.includes("p_target_stage in ('CONTACTED','PAYMENT_RECEIVED','AUDIT_STARTED')"))
  assert.ok(sql.includes("p_evidence_authority <> 'DIRECT_OBSERVATION'"))
  assert.ok(sql.includes("'DENIED_DIRECT_OBSERVATION_REQUIRED'"))
})

test('payment and audit start require distinct evidence because evidence reuse is denied', () => {
  assert.ok(sql.includes("e.evidence_refs @> jsonb_build_array(btrim(p_evidence_ref))"))
  assert.ok(sql.includes("'DENIED_EVIDENCE_REUSE'"))
  assert.ok(sql.includes("when 'PAYMENT_RECEIVED' then 'PAYMENT_RECORD'"))
  assert.ok(sql.includes("when 'AUDIT_STARTED' then 'AUDIT_START'"))
})

test('opportunity creation is idempotent but collision-sensitive', () => {
  assert.ok(sql.includes('on conflict (opportunity_key) do nothing'))
  assert.ok(sql.includes("'REPLAYED_EXISTING'"))
  assert.ok(sql.includes("'DENIED_OPPORTUNITY_KEY_COLLISION'"))
})

test('generation is monotone across observed commercial transitions', () => {
  assert.ok(sql.includes('p_generation <= v_current.generation_v1'))
  assert.ok(sql.includes("'DENIED_GENERATION_REGRESSION'"))
})

test('snapshot grants read only while mutations are service-role RPC-only', () => {
  assert.ok(sql.includes('force row level security'))
  assert.ok(sql.includes('revoke all on scale_os.enterprise_opportunities_v1'))
  assert.ok(sql.includes('grant select on scale_os.enterprise_opportunities_v1'))
  assert.equal(/grant\s+(insert|update|delete)[^;]*enterprise_opportunities_v1/i.test(sql), false)
  assert.equal(count(/to service_role;/gi) >= 3, true)
})

test('every persisted state and event is authority-neutral', () => {
  assert.ok(sql.includes("external_authority text not null default 'NOT_GRANTED'"))
  assert.ok(sql.includes("authority_effect text not null default 'NONE'"))
  assert.ok(sql.includes("'external_authority', 'NOT_GRANTED'"))
  assert.ok(sql.includes("'authority_effect', 'NONE'"))
})
