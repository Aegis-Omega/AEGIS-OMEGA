// ============================================================
// SOVEREIGN OMEGA — Version-Pinned Projection Compiler tests
// EPISTEMIC TIER: T0
//
// Tests for projection/compiler.ts:
//   compileProjection  — pin validation, frozen result, fingerprint
//   PinValidationError — error subclass
// ============================================================

import { describe, it, expect } from 'vitest'
import { compileProjection, PinValidationError } from '../../src/projection/compiler.js'
import type { RuntimeVersionPin } from '../../src/core/types.js'

function validPin(overrides: Partial<RuntimeVersionPin> = {}): RuntimeVersionPin {
  return {
    schema_version: '1.0.0',
    verifier_versions: { 'v-default': '1.0.0' },
    calibration_model_version: '1.0.0',
    projection_compiler_version: '1.0.0',
    k_measurement_version: '1.0.0',
    ...overrides,
  }
}

// ── PinValidationError ────────────────────────────────────

describe('PinValidationError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new PinValidationError('bad pin')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('PinValidationError')
    expect(e.message).toBe('bad pin')
  })
})

// ── compileProjection — happy path ────────────────────────

describe('compileProjection — valid pin', () => {
  it('returns a frozen object with pin and version_fingerprint', () => {
    const pin = validPin()
    const compiled = compileProjection(pin)
    expect(Object.isFrozen(compiled)).toBe(true)
    expect(compiled.pin).toBe(pin)
    expect(typeof compiled.version_fingerprint).toBe('string')
    expect(compiled.version_fingerprint.length).toBeGreaterThan(0)
  })

  it('execute method is present as a function', () => {
    const compiled = compileProjection(validPin())
    expect(typeof compiled.execute).toBe('function')
  })

  it('version_fingerprint is deterministic — same input produces same output', () => {
    const pin = validPin()
    const fp1 = compileProjection(pin).version_fingerprint
    const fp2 = compileProjection(pin).version_fingerprint
    expect(fp1).toBe(fp2)
  })

  it('version_fingerprint differs when schema_version changes', () => {
    const fp1 = compileProjection(validPin({ schema_version: '1.0.0' })).version_fingerprint
    const fp2 = compileProjection(validPin({ schema_version: '2.0.0' })).version_fingerprint
    expect(fp1).not.toBe(fp2)
  })

  it('version_fingerprint differs when verifier_versions changes', () => {
    const fp1 = compileProjection(validPin({ verifier_versions: { 'v1': '1.0.0' } })).version_fingerprint
    const fp2 = compileProjection(validPin({ verifier_versions: { 'v1': '2.0.0' } })).version_fingerprint
    expect(fp1).not.toBe(fp2)
  })
})

// ── compileProjection — validation failures ───────────────

describe('compileProjection — PinValidationError on invalid pin', () => {
  it('throws when schema_version is missing', () => {
    expect(() => compileProjection(validPin({ schema_version: '' }))).toThrow(PinValidationError)
  })

  it('throws when projection_compiler_version is missing', () => {
    expect(() => compileProjection(validPin({ projection_compiler_version: '' }))).toThrow(PinValidationError)
  })

  it('throws when calibration_model_version is missing', () => {
    expect(() => compileProjection(validPin({ calibration_model_version: '' }))).toThrow(PinValidationError)
  })

  it('throws when k_measurement_version is missing', () => {
    expect(() => compileProjection(validPin({ k_measurement_version: '' }))).toThrow(PinValidationError)
  })

  it('throws when verifier_versions is empty', () => {
    expect(() => compileProjection(validPin({ verifier_versions: {} }))).toThrow(PinValidationError)
  })
})
