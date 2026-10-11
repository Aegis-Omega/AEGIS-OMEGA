import { describe, it, expect } from 'vitest'
import { compileWorkContract, WorkContractError } from '../../src/event/work-contract.js'

const step = (id: string, depends_on: string[] = []) => ({
  id, objective: 'Execute ' + id, kind: 'code', depends_on,
  authority: 'read_only', risk: 'low', scope: [],
  acceptance: [{ id: id + '.a1', criterion: 'Check ' + id, method: 'deterministic', evidence_kind: 'test' }]
})
const spec = () => ({
  schema: 'aegis.work.v1', work_id: 'example', objective: 'Complete task', authority_ceiling: 'read_only',
  max_cost_cents: 0, failure_policy: 'halt', forbidden_effects: ['production_writes'], steps: [step('c', ['b']), step('a'), step('b', ['a'])]
})
const invalid = (fn: (s: any) => void) => {
  const s = spec() as any
  fn(s)
  return s
}

describe('UWP-01 work compiler: bounded exact contract', () => {
  it('compiles deterministic dependency order with no execution/authority', async () => {
    const p = await compileWorkContract(spec())
    expect(p.ordered_steps.map(x => x.id)).toEqual(['a', 'b', 'c'])
    expect(p.authorization).toBe('NOT_GRANTED')
    expect(p.execution).toBe('NOT_EXECUTED')
    expect(p.contract_sha256).toMatch(/^[a-f0-9]{64}$/)
  })
  it('is invariant to task, dependency and acceptance ordering', async () => {
    const a = spec(); const b = spec(); b.steps.reverse()
    expect((await compileWorkContract(a)).contract_sha256).toBe((await compileWorkContract(b)).contract_sha256)
  })
  it('does not mutate caller input', async () => {
    const s = spec(); const frozen = JSON.stringify(s)
    await compileWorkContract(s)
    expect(JSON.stringify(s)).toBe(frozen)
  })
  it('rejects unknown dependencies', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].depends_on = ['missing'] }))).rejects.toThrow('UNKNOWN_DEPENDENCY')
  })
  it('rejects cycles', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[1].depends_on = ['c'] }))).rejects.toThrow('CYCLE_DETECTED')
  })
  it('rejects self dependencies', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].depends_on = ['c'] }))).rejects.toThrow('SELF_DEPENDENCY')
  })
  it('rejects duplicate step ids', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps.push(step('a')) }))).rejects.toThrow('DUPLICATE_STEP')
  })
  it('rejects duplicate acceptance ids across steps', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[1].acceptance[0].id = 'c.a1' }))).rejects.toThrow('DUPLICATE_ACCEPTANCE')
  })
  it('rejects duplicate dependencies', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].depends_on = ['b', 'b'] }))).rejects.toThrow('INVALID_DEPENDENCIES')
  })
  it('rejects missing measurable acceptance', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].acceptance = [] }))).rejects.toThrow('NO_ACCEPTANCE')
  })
  it('rejects unknown schema versions', async () => {
    await expect(compileWorkContract(invalid(s => { s.schema = 'v2' }))).rejects.toThrow('SCHEMA_MISMATCH')
  })
  it('rejects unknown fields', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].debug_mode = true }))).rejects.toThrow('UNKNOWN_OR_MISSING_FIELD')
  })
  it('rejects negative or fractional budget', async () => {
    await expect(compileWorkContract(invalid(s => { s.max_cost_cents = -1 }))).rejects.toThrow('INVALID_BUDGET')
    await expect(compileWorkContract(invalid(s => { s.max_cost_cents = 2.3 }))).rejects.toThrow('INVALID_BUDGET')
  })
  it('rejects authority elevation above the ceiling', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].authority = 'branch_only' }))).rejects.toThrow('AUTHORITY_EXCEEDS_CEILING')
  })
  it('rejects high-risk tasks without operator-bound classification', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].risk = 'critical' }))).rejects.toThrow('HIGH_RISK_REQUIRES_OPERATOR')
  })
  it('still returns NOT_GRANTED when operator approval is required', async () => {
    const s = invalid(s => {
      s.authority_ceiling = 'operator_approved'; s.steps[0].authority = 'operator_approved'
      s.steps[0].risk = 'critical'; s.steps[0].scope = ['repo:branch']
    })
    expect((await compileWorkContract(s)).authorization).toBe('NOT_GRANTED')
  })
  it('rejects undeclared write scope', async () => {
    await expect(compileWorkContract(invalid(s => {
      s.authority_ceiling = 'operator_approved'; s.steps[0].authority = 'branch_only'
    }))).rejects.toThrow('MUTATION_REQUIRES_SCOPE')
  })
  it('rejects non-enumerated method', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].acceptance[0].method = 'self-attested' }))).rejects.toThrow('INVALID_VERIFIER')
  })
  it('rejects invalid step id', async () => {
    await expect(compileWorkContract(invalid(s => { s.steps[0].id = '../../escape' }))).rejects.toThrow('INVALID_STEP_ID')
  })
  it('rejects null and prototype-polluted inputs', async () => {
    await expect(compileWorkContract(null)).rejects.toThrow(WorkContractError)
    await expect(compileWorkContract(Object.assign(Object.create({evil: true}), spec()))).rejects.toThrow('INVALID_OBJECT')
  })

  it('fails closed on missing failure policy or forbidden effects', async () => {
    await expect(compileWorkContract(invalid(s => { delete s.failure_policy }))).rejects.toThrow('UNKNOWN_OR_MISSING_FIELD')
    await expect(compileWorkContract(invalid(s => { s.failure_policy = 'auto_retry' }))).rejects.toThrow('INVALID_FAILURE_POLICY')
    await expect(compileWorkContract(invalid(s => { s.forbidden_effects = [] }))).rejects.toThrow('MISSING_FORBIDDEN_EFFECTS')
  })
  it('binds failure policy and forbidden effects in digest', async () => {
    const a = spec(), b = spec()
    ;(b as any).failure_policy = 'manual_recovery'
    expect((await compileWorkContract(a)).contract_sha256).not.toBe((await compileWorkContract(b)).contract_sha256)
    ;(b as any).failure_policy = 'halt'
    ;(b as any).forbidden_effects = ['secrets_access']
    expect((await compileWorkContract(a)).contract_sha256).not.toBe((await compileWorkContract(b)).contract_sha256)
  })
  it('rejects unbounded mutation scopes, wildcard or traversal', async () => {
    for (const scope of ['*', 'repo:../main', 'repo:foo/../main', 'repo:*', '/etc/shadow']) {
      await expect(compileWorkContract(invalid(s => { s.steps[0].scope = [scope] }))).rejects.toThrow('INVALID_SCOPE')
    }
  })
  it('rejects sparse arrays and accessor properties without invoking getters', async () => {
    const sparse = invalid(s => { s.steps = new Array(2); s.steps[0] = step('a') })
    await expect(compileWorkContract(sparse)).rejects.toThrow('INVALID_STEPS')
    let accessed = false
    const unsafe = invalid(s => {
      Object.defineProperty(s.steps[0], 'objective', { get() { accessed = true; return 'unsafe' }, enumerable: true })
    })
    await expect(compileWorkContract(unsafe)).rejects.toThrow('NON_JSON_PROPERTY')
    expect(accessed).toBe(false)
  })
  it('rejects non-enumerable and symbol hidden fields', async () => {
    await expect(compileWorkContract(invalid(s => {
      Object.defineProperty(s.steps[0], 'hidden', {value: 1})
    }))).rejects.toThrow('NON_JSON_PROPERTY')
    await expect(compileWorkContract(invalid(s => {
      s.steps[0][Symbol.for('bad')] = 1
    }))).rejects.toThrow('NON_JSON_PROPERTY')
  })
  it('returns deeply immutable ordered steps and acceptance', async () => {
    const plan = await compileWorkContract(spec())
    expect(Object.isFrozen(plan.ordered_steps)).toBe(true)
    expect(Object.isFrozen(plan.ordered_steps[0])).toBe(true)
    expect(Object.isFrozen(plan.ordered_steps[0].acceptance[0])).toBe(true)
  })

})
