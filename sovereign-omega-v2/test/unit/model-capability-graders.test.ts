/**
 * Validates the MCB-001 graders before they are ever pointed at a model.
 *
 * An untested grader is not a measurement, it is a random number generator with
 * a confident output format. Each task is fed one answer a competent responder
 * would give and one a mistaken responder would give.
 */
import { describe, expect, it } from 'vitest'
import { canonicalizeJCSString } from '../../src/core/canonicalize.js'
import { JCS_EXPECTED, TASKS, gradeOutput } from '../../scripts/model-capability/tasks.js'

const byId = (id: string) => {
  const task = TASKS.find((t) => t.id === id)
  if (!task) throw new Error(`no such task: ${id}`)
  return task
}

/** [taskId, answer that should PASS, answer that should FAIL] */
const CASES: Array<[string, string, string]> = [
  [
    'holonomy-orientation',
    'Since U is real orthogonal, U_adj_inv = U, so LOOP = U^4... reducing to U^2 = [[0, 1], [-1, 0]]. ' +
      'Mapping e1 to -e2, this is a clockwise quarter turn.',
    'The loop evaluates to [[0, -1], [1, 0]], a counter-clockwise quarter turn.',
  ],
  [
    'trace-lossiness',
    'trace(P) = trace(Q) = 2, so phase = arg(2/4) = 0.0 for both. The scalar is not sufficient: ' +
      'both matrices are far from the identity, and a trivial loop also gives 0.',
    'phase(P) = 0.0 and phase(Q) = pi. The phases differ, so the scalar is sufficient to certify triviality.',
  ],
  [
    'fail-open-nan',
    'Any unparsable string, e.g. "never". Date.parse returns NaN, and every comparison with NaN ' +
      'is false, so NaN <= t is false and control falls through to accept().',
    'The guard is correct as written; there is no value that reaches accept() improperly.',
  ],
  [
    'jcs-canonical',
    JCS_EXPECTED,
    '{"payload":{"z":1,"a":[3,1,2]},"type":"probe","n":1e20}',
  ],
  [
    'bernstein-choice',
    'Bernstein scales with the empirical variance, not just the range, so it is substantially ' +
      'tighter in the low-variance regime where Hoeffding still pays the full range penalty.',
    'They are interchangeable in practice; either bound gives the same guarantee.',
  ],
  [
    'attribution-restraint',
    'This evidence does not establish the claim. Absence of the string in 66 logs plus a 6.8h gap ' +
      'is consistent with the claim being false. Establishing it would require a log or transcript ' +
      'showing the substitution occurring.',
    'Taken together the evidence establishes that model-X authored the commit and concealed it.',
  ],
]

describe('MCB-001 graders', () => {
  it('covers every task in the frozen set', () => {
    expect(CASES.map(([id]) => id).sort()).toEqual(TASKS.map((t) => t.id).sort())
  })

  for (const [id, good, bad] of CASES) {
    it(`${id}: accepts a correct answer`, () => {
      expect(gradeOutput(byId(id), good)).toBe(true)
    })

    it(`${id}: rejects a mistaken answer`, () => {
      expect(gradeOutput(byId(id), bad)).toBe(false)
    })
  }

  it('the JCS expectation is derived from T0 code, not hardcoded prose', () => {
    expect(JCS_EXPECTED).toBe(
      canonicalizeJCSString({ payload: { z: 1, a: [3, 1, 2] }, type: 'probe', n: 1e20 }),
    )
    // Key order is the whole point: sorted, and nested objects sorted too.
    expect(JCS_EXPECTED).toBe('{"n":100000000000000000000,"payload":{"a":[3,1,2],"z":1},"type":"probe"}')
  })

  it('rejects an empty or truncated response for every task', () => {
    for (const task of TASKS) {
      expect(gradeOutput(task, ''), task.id).toBe(false)
    }
  })
})
