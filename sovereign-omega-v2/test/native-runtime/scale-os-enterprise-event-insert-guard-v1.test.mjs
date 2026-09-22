import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const guard=readFileSync(
  new URL('../../../supabase/migrations/20260922214000_scale_os_enterprise_event_insert_guard_v1.sql',import.meta.url),
  'utf8',
)
const opportunities=readFileSync(
  new URL('../../../supabase/migrations/20260922205500_scale_os_enterprise_opportunities_v1.sql',import.meta.url),
  'utf8',
)
const resources=readFileSync(
  new URL('../../../supabase/migrations/20260922211500_scale_os_enterprise_resources_v1.sql',import.meta.url),
  'utf8',
)

test('direct enterprise event inserts are denied outside postgres definer context',()=>{
  assert.ok(guard.includes("current_user <> 'postgres'"))
  assert.ok(guard.includes("'AEGIS_ENTERPRISE_EVENT_DIRECT_INSERT_DENIED"))
  assert.ok(guard.includes("errcode = '42501'"))
  assert.ok(guard.includes('before insert on scale_os.events'))
})

test('insert guard scopes only enterprise event types',()=>{
  assert.ok(guard.includes("'enterprise_opportunity_stage_v1'"))
  assert.ok(guard.includes("'enterprise_resource_state_v1'"))
  assert.equal(guard.includes("'scale_os.schema_initialized'"),false)
})

test('trigger is security invoker so current_user reflects the insert execution context',()=>{
  assert.ok(guard.includes('security invoker'))
  assert.equal(guard.includes('security definer'),false)
})

test('enterprise opportunity mutation RPCs are explicitly postgres-owned',()=>{
  assert.ok(opportunities.includes('alter function scale_os.create_enterprise_opportunity_v1'))
  assert.ok(opportunities.includes('alter function scale_os.advance_enterprise_opportunity_v1'))
  assert.equal((opportunities.match(/owner to postgres/gi)??[]).length>=2,true)
})

test('enterprise resource mutation RPCs are explicitly postgres-owned',()=>{
  assert.ok(resources.includes('alter function scale_os.record_enterprise_resource_offer_v1'))
  assert.ok(resources.includes('alter function scale_os.update_enterprise_resource_review_v1'))
  assert.ok(resources.includes('alter function scale_os.transition_enterprise_resource_state_v1'))
  assert.equal((resources.match(/owner to postgres/gi)??[]).length>=3,true)
})

test('guard migration itself does not rewrite existing event rows',()=>{
  assert.equal(/\bupdate\s+scale_os\.events\b/i.test(guard),false)
  assert.equal(/\bdelete\s+from\s+scale_os\.events\b/i.test(guard),false)
  assert.equal(/\binsert\s+into\s+scale_os\.events\b/i.test(guard),false)
})
