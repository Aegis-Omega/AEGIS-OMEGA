// ============================================================
// SOVEREIGN OMEGA — WASM Parity Harness Tests
// Ω⁵.7: Verifies the parity detection layer that will enforce
// byte equality between JS fallbacks and the future WASM kernel.
//
// No WASM binary exists yet — these tests verify the harness
// behaves correctly so divergence cannot go undetected once
// the kernel is compiled. The detection contract is tested now;
// the binary parity is deferred (see header note in wasm-interface.ts).
//
// Determinism rule: assertWasmParity runs ≥3 times per input.
// ============================================================

import { describe, it, expect } from 'vitest'
import { assertWasmParity, getWasmKernel } from '../../src/core/wasm-interface'
import {
  bernsteinLCBQ32, toQ32, Q_HALF, Q_ZERO,
} from '../../src/core/fixedpoint'
import type { Q32_32 } from '../../src/core/fixedpoint'

// Deterministic sample builder — same as bernstein-q32-fuzz.test.ts
function buildSamples(seed: number, count: number): { sum: Q32_32; sumSq: Q32_32 } {
  let sum = Q_ZERO
  let sumSq = Q_ZERO
  for (let i = 0; i < count; i++) {
    const v = ((seed * 1618033 + i * 314159) % 1000) / 1000
    const q = toQ32(v)
    sum += q
    sumSq += (q * q) >> 32n
  }
  return { sum, sumSq }
}

// Encode a Q32.32 bigint as a 16-character hex string (8 bytes, big-endian)
// This is the canonical wire format for WASM↔JS parity comparison.
function q32ToHex(v: Q32_32): string {
  const lo = BigInt.asUintN(32, v)
  const hi = BigInt.asUintN(32, v >> 32n)
  const loHex = Number(lo).toString(16).padStart(8, '0')
  const hiHex = Number(hi).toString(16).padStart(8, '0')
  return hiHex + loHex
}

describe('WASM Parity Harness — Ω⁵.7', () => {

  it('assertWasmParity passes when string outputs are identical (3 runs)', () => {
    const jsOut = 'deadbeefcafe0001'
    const wasmOut = 'deadbeefcafe0001'
    for (let i = 0; i < 3; i++) {
      expect(() => assertWasmParity(jsOut, wasmOut, 'bernstein_lcb')).not.toThrow()
    }
  })

  it('assertWasmParity detects single-byte divergence in strings (3 runs)', () => {
    const jsOut = 'deadbeefcafe0001'
    const wasmOut = 'deadbeefcafe0000'  // last nibble differs
    for (let i = 0; i < 3; i++) {
      expect(() => assertWasmParity(jsOut, wasmOut, 'bernstein_lcb'))
        .toThrow('DETERMINISM_VIOLATION')
    }
  })

  it('assertWasmParity passes when Uint8Array outputs are byte-identical (3 runs)', () => {
    const buf = new Uint8Array([0xde, 0xad, 0xbe, 0xef, 0xca, 0xfe, 0x00, 0x01])
    const copy = new Uint8Array(buf)
    for (let i = 0; i < 3; i++) {
      expect(() => assertWasmParity(buf, copy, 'sha256')).not.toThrow()
    }
  })

  it('assertWasmParity detects single-byte divergence in Uint8Arrays (3 runs)', () => {
    const jsOut = new Uint8Array([0xde, 0xad, 0xbe, 0xef])
    const wasmOut = new Uint8Array([0xde, 0xad, 0xbe, 0xf0])  // last byte differs
    for (let i = 0; i < 3; i++) {
      expect(() => assertWasmParity(jsOut, wasmOut, 'sha256'))
        .toThrow('DETERMINISM_VIOLATION')
    }
  })

  it('assertWasmParity accepts mixed string/Uint8Array with matching hex', () => {
    // JS returns a hex string; WASM returns bytes — both must produce same hex
    const jsHex = 'deadbeef'
    const wasmBytes = new Uint8Array([0xde, 0xad, 0xbe, 0xef])
    expect(() => assertWasmParity(jsHex, wasmBytes, 'canonicalize')).not.toThrow()
  })

  it('WASM kernel starts unloaded — loaded=false, exports=null, hash=null', () => {
    const kernel = getWasmKernel()
    // Run 3× — state is deterministic (no binary loaded in test env)
    for (let i = 0; i < 3; i++) {
      expect(getWasmKernel().loaded).toBe(false)
      expect(getWasmKernel().exports).toBeNull()
      expect(getWasmKernel().hash).toBeNull()
    }
    // Verify the object reference is stable
    expect(kernel).toBe(getWasmKernel())
  })

  it('JS bernstein_lcb produces stable hex across 20 inputs — parity reference values', () => {
    const alpha = Q_HALF >> 1n  // 0.25 in Q32.32
    const hexOutputs: string[] = []
    for (let seed = 0; seed < 20; seed++) {
      const n = BigInt(10 + seed)
      const { sum, sumSq } = buildSamples(seed, Number(n))
      const lcb = bernsteinLCBQ32(sum, sumSq, n, alpha)
      hexOutputs.push(q32ToHex(lcb))
    }
    // Each value stable across 3 independent calls (determinism check)
    for (let seed = 0; seed < 20; seed++) {
      const n = BigInt(10 + seed)
      const { sum, sumSq } = buildSamples(seed, Number(n))
      const lcb1 = q32ToHex(bernsteinLCBQ32(sum, sumSq, n, alpha))
      const lcb2 = q32ToHex(bernsteinLCBQ32(sum, sumSq, n, alpha))
      const lcb3 = q32ToHex(bernsteinLCBQ32(sum, sumSq, n, alpha))
      expect(lcb1).toBe(hexOutputs[seed])
      expect(lcb1).toBe(lcb2)
      expect(lcb2).toBe(lcb3)
    }
  })

  it('simulated WASM divergence on bernstein_lcb is detected by assertWasmParity', () => {
    const alpha = Q_HALF >> 1n
    const { sum, sumSq } = buildSamples(7, 100)
    const n = 100n
    const jsLcb = bernsteinLCBQ32(sum, sumSq, n, alpha)
    const jsHex = q32ToHex(jsLcb)

    // Simulate a WASM kernel returning a slightly wrong answer (off by one ULP)
    const wasmWrongHex = q32ToHex(jsLcb + 1n)

    // Must detect the divergence in all 3 runs
    for (let i = 0; i < 3; i++) {
      expect(() => assertWasmParity(jsHex, wasmWrongHex, 'bernstein_lcb'))
        .toThrow('DETERMINISM_VIOLATION')
    }

    // Correct WASM output passes all 3 runs
    for (let i = 0; i < 3; i++) {
      expect(() => assertWasmParity(jsHex, jsHex, 'bernstein_lcb')).not.toThrow()
    }
  })

  it('q32ToHex is deterministic — same bigint always produces same hex (3 runs)', () => {
    const values = [Q_ZERO, Q_HALF, toQ32(0.1), toQ32(0.99), toQ32(-0.5), -(Q_HALF >> 1n)]
    for (const v of values) {
      const h1 = q32ToHex(v)
      const h2 = q32ToHex(v)
      const h3 = q32ToHex(v)
      expect(h1).toBe(h2)
      expect(h2).toBe(h3)
      expect(h1).toHaveLength(16)  // 8 bytes = 16 hex chars
    }
  })

  it('empty output divergence is detected (zero-length edge case)', () => {
    expect(() => assertWasmParity('', 'aa', 'edge')).toThrow('DETERMINISM_VIOLATION')
    expect(() => assertWasmParity('aa', '', 'edge')).toThrow('DETERMINISM_VIOLATION')
    expect(() => assertWasmParity('', '', 'edge')).not.toThrow()
  })

})
