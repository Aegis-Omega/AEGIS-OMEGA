import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sql=readFileSync(
  new URL('../../../supabase/migrations/20260922220500_supabase_advisor_performance_hardening_v1.sql',import.meta.url),
  'utf8',
)

function count(pattern){ return (sql.match(pattern)??[]).length }

test('access_grants purchase foreign key receives one covering index',()=>{
  assert.equal(count(/create index if not exists access_grants_purchase_id_idx/gi),1)
  assert.ok(sql.includes('on public.access_grants(purchase_id)'))
})

test('four auth.role per-row service policies are replaced with direct service_role targeting',()=>{
  for(const table of [
    'public.department_fitness_tracking',
    'public.agent_api_profiles',
    'public.grace_events',
    'public.dept_graces',
  ]){
    assert.ok(sql.includes(`on ${table}`))
  }
  assert.equal(sql.includes('auth.role()'),false)
  assert.equal(count(/to service_role/gi),4)
})

test('replacement policies preserve all-command service-role semantics',()=>{
  assert.equal(count(/for all/gi),4)
  assert.equal(count(/using \(true\)/gi),4)
  assert.equal(count(/with check \(true\)/gi),4)
})

test('dept_graces public read policy is not dropped or rewritten',()=>{
  assert.equal(sql.includes('drop policy if exists dept_graces_public_read'),false)
  assert.equal(sql.includes('create policy dept_graces_public_read'),false)
})

test('migration does not touch unrelated tables or delete data',()=>{
  assert.equal(/\bdelete\s+from\b/i.test(sql),false)
  assert.equal(/\btruncate\b/i.test(sql),false)
  assert.equal(sql.includes('scale_os.'),false)
})
