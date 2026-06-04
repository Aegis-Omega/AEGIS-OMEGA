import { describe, it, expect } from 'vitest'
import { assertExecutionBoundary, ExecutionBoundaryError } from '../../src/agents/executor/loop.js'

// ============================================================
// Gate 127 — Execution Boundary Tests
// Verifies: k·C_eval ≤ B_max enforcement; pre-flight rejection;
// error message accuracy; boundary and zero-cost cases.
// Source: execution-boundary skill (T2)
// ============================================================

describe('ExecutionBoundaryError', () => {
  it('is an Error subclass with correct name', () => {
    const err = new ExecutionBoundaryError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('ExecutionBoundaryError')
  })
})

describe('assertExecutionBoundary — passing cases', () => {
  it('k * cEval < bMax does not throw', () => {
    expect(() => assertExecutionBoundary(10, 0.01, 0.50)).not.toThrow()
  })

  it('k * cEval === bMax (exact boundary) does not throw', () => {
    // 33 × 0.015 = 0.495; 0.495 ≤ 0.50
    expect(() => assertExecutionBoundary(33, 0.015, 0.495)).not.toThrow()
  })

  it('k=0 never throws regardless of cEval and bMax', () => {
    expect(() => assertExecutionBoundary(0, 99, 0)).not.toThrow()
  })

  it('cEval=0 never throws (zero-cost steps are always within budget)', () => {
    expect(() => assertExecutionBoundary(1_000_000, 0, 0.50)).not.toThrow()
  })

  it('skill example: k=33, cEval=0.015, bMax=0.50 (33×0.015=0.495 ≤ 0.50)', () => {
    expect(() => assertExecutionBoundary(33, 0.015, 0.50)).not.toThrow()
  })
})

describe('assertExecutionBoundary — violation cases', () => {
  it('k * cEval > bMax throws ExecutionBoundaryError', () => {
    expect(() => assertExecutionBoundary(10, 0.10, 0.50)).toThrow(ExecutionBoundaryError)
  })

  it('skill example: k=34, cEval=0.015, bMax=0.50 (34×0.015=0.51 > 0.50)', () => {
    expect(() => assertExecutionBoundary(34, 0.015, 0.50)).toThrow(ExecutionBoundaryError)
  })

  it('error message includes k, C_eval, product, B_max, and k_max', () => {
    let caught: Error | undefined
    try { assertExecutionBoundary(34, 0.015, 0.50) } catch (e) { caught = e as Error }
    expect(caught).toBeDefined()
    expect(caught?.message).toContain('k=34')
    expect(caught?.message).toContain('C_eval=0.015')
    expect(caught?.message).toContain('B_max=0.5')
    expect(caught?.message).toContain('k_max=33')
  })

  it('k_max=0 when bMax < cEval (no steps affordable)', () => {
    let caught: Error | undefined
    try { assertExecutionBoundary(1, 0.10, 0.05) } catch (e) { caught = e as Error }
    expect(caught?.message).toContain('k_max=0')
  })

  it('large k still throws correctly', () => {
    // k=1000, cEval=1.0, bMax=500 → 1000 > 500
    expect(() => assertExecutionBoundary(1_000, 1.0, 500)).toThrow(ExecutionBoundaryError)
  })
})
