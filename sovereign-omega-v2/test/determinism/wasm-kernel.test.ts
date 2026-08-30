// ============================================================
// SOVEREIGN OMEGA — WASM Kernel Parity Tests
// Gate 16: Verifies byte-identical output between the Rust WASM
// kernel and the TypeScript JS fallbacks.
//
// Skipped automatically if the WASM binary is not compiled.
// To compile: cargo build --target wasm32-unknown-unknown --release -p kernel
//
// Determinism rule: each parity assertion runs ≥3 times.
// ============================================================

import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import { sha256Hex, computeMerkleRoot, uint8ArrayToHex } from '../../src/core/hashing.js'
import { canonicalizeJCSString } from '../../src/core/canonicalize.js'
import {
  bernsteinLCBQ32, toQ32, Q_HALF, Q_ZERO,
  type Q32_32,
} from '../../src/core/fixedpoint.js'

// ─── WASM path ─────────────────────────────────────────────

const __filename = fileURLToPath(import.meta.url)
const __dir = dirname(__filename)
const WASM_PATH = join(__dir, '../../target/wasm32-unknown-unknown/release/kernel.wasm')
const WASM_READY = existsSync(WASM_PATH)

// ─── Typed WASM exports ────────────────────────────────────

interface KernelExports {
  memory: WebAssembly.Memory
  get_input_ptr(): number
  get_output_ptr(): number
  sha256(inputPtr: number, inputLen: number, outPtr: number): void
  merkle_root(leavesPtr: number, leafCount: number, outPtr: number): void
  bernstein_lcb(sumQ32: bigint, sumSqQ32: bigint, n: number, alphaQ32: bigint): bigint
  canonicalize(inputPtr: number, inputLen: number, outPtr: number): number
  reduce_state(
    statePtr: number, stateLen: number,
    eventPtr: number, eventLen: number,
    outPtr: number
  ): number
}

// ─── Loader ────────────────────────────────────────────────

let kernel: KernelExports | null = null

async function ensureKernel(): Promise<KernelExports> {
  if (kernel) return kernel
  const bytes = readFileSync(WASM_PATH)
  const { instance } = await WebAssembly.instantiate(bytes)
  kernel = instance.exports as unknown as KernelExports
  return kernel
}

// ─── Memory helpers ────────────────────────────────────────

function writeToWasm(k: KernelExports, bytes: Uint8Array, ptr: number): void {
  new Uint8Array(k.memory.buffer).set(bytes, ptr)
}

function readFromWasm(k: KernelExports, ptr: number, len: number): Uint8Array {
  return new Uint8Array(k.memory.buffer).slice(ptr, ptr + len)
}

/** Build length-prefixed leaf buffer for merkle_root WASM function. */
function buildLeafBuffer(leaves: Uint8Array[]): Uint8Array {
  const totalSize = leaves.reduce((s, l) => s + 4 + l.length, 0)
  const buf = new Uint8Array(totalSize)
  const view = new DataView(buf.buffer)
  let offset = 0
  for (const leaf of leaves) {
    view.setUint32(offset, leaf.length, true) // little-endian u32 length
    offset += 4
    buf.set(leaf, offset)
    offset += leaf.length
  }
  return buf
}

// ─── Deterministic sample builder (same as wasm-parity.test.ts) ──────

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

// ─── Tests ─────────────────────────────────────────────────

describe.skipIf(!WASM_READY)('WASM Kernel Parity — Gate 16', () => {

  // ── SHA-256 ──────────────────────────────────────────────

  describe('sha256 parity', () => {
    const inputs = [
      new Uint8Array([]),
      new TextEncoder().encode('hello'),
      new TextEncoder().encode('AEGIS Ω deterministic kernel'),
      new Uint8Array(32).fill(0xff),
      new Uint8Array(64).map((_, i) => i),
    ]

    for (const [idx, input] of inputs.entries()) {
      it(`sha256 input[${idx}] matches TypeScript 3×`, async () => {
        const k = await ensureKernel()
        const inPtr = k.get_input_ptr()
        const outPtr = k.get_output_ptr()

        const jsHash = await sha256Hex(input)

        for (let run = 0; run < 3; run++) {
          writeToWasm(k, input, inPtr)
          k.sha256(inPtr, input.length, outPtr)
          const wasmHash = uint8ArrayToHex(readFromWasm(k, outPtr, 32))
          expect(wasmHash).toBe(jsHash)
        }
      })
    }

    it('sha256("") === known SHA-256 empty hash (3 runs)', async () => {
      const k = await ensureKernel()
      const expected = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
      const inPtr = k.get_input_ptr()
      const outPtr = k.get_output_ptr()
      for (let run = 0; run < 3; run++) {
        k.sha256(inPtr, 0, outPtr)
        const result = uint8ArrayToHex(readFromWasm(k, outPtr, 32))
        expect(result).toBe(expected)
      }
    })
  })

  // ── Merkle root ──────────────────────────────────────────

  describe('merkle_root parity', () => {
    const leafSets = [
      [new TextEncoder().encode('leaf1'), new TextEncoder().encode('leaf2')],
      [new TextEncoder().encode('1'), new TextEncoder().encode('2'), new TextEncoder().encode('3')],
      [new TextEncoder().encode('a'), new TextEncoder().encode('b'),
       new TextEncoder().encode('c'), new TextEncoder().encode('d')],
    ]

    for (const [idx, leaves] of leafSets.entries()) {
      it(`merkle_root leafSet[${idx}] (${leaves.length} leaves) matches TypeScript 3×`, async () => {
        const k = await ensureKernel()
        const inPtr = k.get_input_ptr()
        const outPtr = k.get_output_ptr()

        const jsRoot = await computeMerkleRoot(leaves)
        const leafBuf = buildLeafBuffer(leaves)

        for (let run = 0; run < 3; run++) {
          writeToWasm(k, leafBuf, inPtr)
          k.merkle_root(inPtr, leaves.length, outPtr)
          const wasmRoot = uint8ArrayToHex(readFromWasm(k, outPtr, 32))
          expect(wasmRoot).toBe(jsRoot)
        }
      })
    }

    it('merkle_root single leaf parity (3 runs)', async () => {
      const k = await ensureKernel()
      const leaf = new TextEncoder().encode('single')
      const jsRoot = await computeMerkleRoot([leaf])
      const leafBuf = buildLeafBuffer([leaf])
      const inPtr = k.get_input_ptr()
      const outPtr = k.get_output_ptr()

      for (let run = 0; run < 3; run++) {
        writeToWasm(k, leafBuf, inPtr)
        k.merkle_root(inPtr, 1, outPtr)
        const wasmRoot = uint8ArrayToHex(readFromWasm(k, outPtr, 32))
        expect(wasmRoot).toBe(jsRoot)
        expect(wasmRoot).toHaveLength(64)
      }
    })
  })

  // ── Bernstein LCB ────────────────────────────────────────

  describe('bernstein_lcb parity', () => {
    const alpha = Q_HALF >> 1n // 0.25 in Q32.32

    for (let seed = 0; seed < 5; seed++) {
      it(`bernstein_lcb seed=${seed} n=50 matches TypeScript 3×`, async () => {
        const k = await ensureKernel()
        const n = BigInt(50 + seed)
        const { sum, sumSq } = buildSamples(seed, Number(n))
        const jsLcb = bernsteinLCBQ32(sum, sumSq, n, alpha)

        for (let run = 0; run < 3; run++) {
          // WASM takes n as i32 (the sample count), BigInt for Q32.32 values
          const wasmLcb = k.bernstein_lcb(sum, sumSq, Number(n), alpha)
          expect(wasmLcb).toBe(jsLcb)
        }
      })
    }

    it('bernstein_lcb n=0 returns -Infinity proxy 3×', async () => {
      const k = await ensureKernel()
      const expected = bernsteinLCBQ32(0n, 0n, 0n, alpha)
      for (let run = 0; run < 3; run++) {
        const result = k.bernstein_lcb(0n, 0n, 0, alpha)
        expect(result).toBe(expected)
      }
    })
  })

  // ── Canonicalize ─────────────────────────────────────────

  describe('canonicalize parity', () => {
    const cases: Array<[string, string]> = [
      ['{}',                   '{}'],
      ['{"b":1,"a":2}',        '{"a":2,"b":1}'],
      ['{"z":1,"a":2,"m":3}',  '{"a":2,"m":3,"z":1}'],
      ['[1,2,3]',              '[1,2,3]'],
      ['null',                 'null'],
    ]

    for (const [input, expected] of cases) {
      it(`canonicalize ${JSON.stringify(input)} → ${JSON.stringify(expected)} 3×`, async () => {
        const k = await ensureKernel()
        const inPtr = k.get_input_ptr()
        const outPtr = k.get_output_ptr()
        const inputBytes = new TextEncoder().encode(input)

        for (let run = 0; run < 3; run++) {
          writeToWasm(k, inputBytes, inPtr)
          const outLen = k.canonicalize(inPtr, inputBytes.length, outPtr)
          const result = new TextDecoder().decode(readFromWasm(k, outPtr, outLen))
          expect(result).toBe(expected)
        }
      })
    }

    it('canonicalize matches TypeScript canonicalizeJCSString for nested object (3 runs)', async () => {
      const k = await ensureKernel()
      const inPtr = k.get_input_ptr()
      const outPtr = k.get_output_ptr()

      const obj = { payload: { b: 2, a: 1 }, type: 'test' }
      const jsonInput = JSON.stringify(obj) // non-canonical key order
      const tsCanonical = canonicalizeJCSString(obj)

      const inputBytes = new TextEncoder().encode(jsonInput)

      for (let run = 0; run < 3; run++) {
        writeToWasm(k, inputBytes, inPtr)
        const outLen = k.canonicalize(inPtr, inputBytes.length, outPtr)
        const wasmResult = new TextDecoder().decode(readFromWasm(k, outPtr, outLen))
        expect(wasmResult).toBe(tsCanonical)
      }
    })
  })

  // ── reduce_state ─────────────────────────────────────────

  describe('reduce_state determinism', () => {
    it('reduce_state(state, event) produces 32-byte hash deterministically 3×', async () => {
      const k = await ensureKernel()
      const inPtr = k.get_input_ptr()
      const outPtr = k.get_output_ptr()

      const state = new TextEncoder().encode('{"phase":"LOCK","sequence":1}')
      const event = new TextEncoder().encode('{"type":"COMMIT","id":"abc"}')

      // Write state at inPtr, event at inPtr + state.length
      const statePtr = inPtr
      const eventPtr = inPtr + state.length

      let firstHash: string | null = null
      for (let run = 0; run < 3; run++) {
        writeToWasm(k, state, statePtr)
        writeToWasm(k, event, eventPtr)
        k.reduce_state(statePtr, state.length, eventPtr, event.length, outPtr)
        const hash = uint8ArrayToHex(readFromWasm(k, outPtr, 32))
        expect(hash).toHaveLength(64)
        if (firstHash === null) { firstHash = hash }
        else { expect(hash).toBe(firstHash) }
      }
    })

    it('different state produces different hash (3 runs each)', async () => {
      const k = await ensureKernel()
      const inPtr = k.get_input_ptr()
      const outPtr = k.get_output_ptr()
      const event = new TextEncoder().encode('{}')

      const state1 = new TextEncoder().encode('{"a":1}')
      const state2 = new TextEncoder().encode('{"a":2}')

      writeToWasm(k, state1, inPtr)
      writeToWasm(k, event, inPtr + state1.length)
      k.reduce_state(inPtr, state1.length, inPtr + state1.length, event.length, outPtr)
      const hash1 = uint8ArrayToHex(readFromWasm(k, outPtr, 32))

      writeToWasm(k, state2, inPtr)
      writeToWasm(k, event, inPtr + state2.length)
      k.reduce_state(inPtr, state2.length, inPtr + state2.length, event.length, outPtr)
      const hash2 = uint8ArrayToHex(readFromWasm(k, outPtr, 32))

      expect(hash1).not.toBe(hash2)
    })
  })

})
