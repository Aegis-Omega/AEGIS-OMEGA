import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sql=readFileSync(
  new URL('../../../supabase/migrations/20260922213000_scale_os_enterprise_event_immutability_v1.sql',import.meta.url),
  'utf8',
)

test('guard scopes only the new enterprise event types',()=>{
  assert.ok(sql.includes("'enterprise_opportunity_stage_v1'"))
  assert.ok(sql.includes("'enterprise_resource_state_v1'"))
  assert.equal(sql.includes("'scale_os.schema_initialized'"),false)
  assert.equal(sql.includes("'request_to_delivery_audit_started'"),false)
})

test('guard rejects both update and delete through a before-row trigger',()=>{
  assert.ok(sql.includes('before update or delete on scale_os.events'))
  assert.ok(sql.includes("raise exception 'AEGIS_ENTERPRISE_EVENT_IMMUTABLE"))
  assert.ok(sql.includes("errcode = '42501'"))
})

test('guard does not rewrite or delete historical rows during migration',()=>{
  assert.equal(/\bupdate\s+scale_os\.events\b/i.test(sql),false)
  assert.equal(/\bdelete\s+from\s+scale_os\.events\b/i.test(sql),false)
})

test('trigger definition is singular and deterministic',()=>{
  assert.equal((sql.match(/create trigger scale_os_enterprise_event_immutability_v1/gi)??[]).length,1)
  assert.equal((sql.match(/create or replace function scale_os\.prevent_enterprise_event_mutation_v1/gi)??[]).length,1)
})

test('client roles receive no mutation path through the guard function',()=>{
  assert.ok(sql.includes('from public, anon, authenticated'))
  assert.ok(sql.includes('to service_role'))
})
