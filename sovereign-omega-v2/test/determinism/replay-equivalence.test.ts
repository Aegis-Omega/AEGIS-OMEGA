// ============================================================
// SOVEREIGN OMEGA — WASM Replay Equivalence Proof
// Gate 27: Proves H_TS(f_n) = H_WASM(f_n) ∀ governance frames
//
// This file is the definitive implementation-invariant proof.
// A TypeScript node and a WASM node processing the same governance
// state produce byte-identical frame hashes — enabling cross-
// platform replay equivalence voting without a shared runtime.
//
// BIGINT CONTRACT (empirically verified, documented here):
//   canonicalizeJCS({sequence: 1n}) → {"sequence":"1"}
//   JSON.stringify({sequence: 1n}, bigintReplacer) → '{"sequence":"1"}'
//   Both paths produce the same wire bytes. WASM equivalence holds
//   for LedgerEntry.sequence (bigint) without pre-conversion in TS.
//
// FIVE PROOF GROUPS:
//   A — SHA-256 parity on canonical governance bytes
//   B — Canonicalization parity on governance-representative JSON
//   C — End-to-end hashValue() equivalence (core theorem)
//   D — Ledger chain link hash equivalence via WASM
//   E — Merkle checkpoint equivalence with governance data
//
// Skipped gracefully if WASM binary is absent (CI without Rust).
// Each assertion runs ≥3 times per testing.md determinism rule.
// ============================================================

import { describe, it, expect, beforeAll } from 'vitest'
import { existsSync, readFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { canonicalizeJCS, canonicalizeJCSString } from '../../src/core/canonicalize.js'
import {
  hashValue, sha256Hex, computeMerkleRootFromValues,
  uint8ArrayToHex,
} from '../../src/core/hashing.js'
import { GENESIS_HASH, type LedgerEntry } from '../../src/ledger/types.js'
import { LedgerChain } from '../../src/ledger/chain.js'

// ─── WASM path ─────────────────────────────────────────────

const __filename = fileURLToPath(import.meta.url)
const __dir = dirname(__filename)
const WASM_PATH = join(__dir, '../../target/wasm32-unknown-unknown/release/kernel.wasm')
const WASM_READY = existsSync(WASM_PATH)

interface KernelExports {
  memory: WebAssembly.Memory
  get_input_ptr(): number
  get_output_ptr(): number
  sha256(inputPtr: number, inputLen: number, outPtr: number): void
  merkle_root(leavesPtr: number, leafCount: number, outPtr: number): void
  canonicalize(inputPtr: number, inputLen: number, outPtr: number): number
}

let kernel: KernelExports | null = null

async function ensureKernel(): Promise<KernelExports> {
  if (kernel) return kernel
  const bytes = readFileSync(WASM_PATH)
  const { instance } = await WebAssembly.instantiate(bytes)
  kernel = instance.exports as unknown as KernelExports
  return kernel
}

// ─── WASM call helpers ─────────────────────────────────────

function writeToWasm(k: KernelExports, bytes: Uint8Array, ptr: number): void {
  new Uint8Array(k.memory.buffer).set(bytes, ptr)
}

function readFromWasm(k: KernelExports, ptr: number, len: number): Uint8Array {
  return new Uint8Array(k.memory.buffer).slice(ptr, ptr + len)
}

function wasmSha256(k: KernelExports, input: Uint8Array): Uint8Array {
  const inPtr = k.get_input_ptr()
  const outPtr = k.get_output_ptr()
  writeToWasm(k, input, inPtr)
  k.sha256(inPtr, input.length, outPtr)
  return readFromWasm(k, outPtr, 32)
}

function wasmCanonicalize(k: KernelExports, inputBytes: Uint8Array): Uint8Array {
  const inPtr = k.get_input_ptr()
  const outPtr = k.get_output_ptr()
  writeToWasm(k, inputBytes, inPtr)
  const outLen = k.canonicalize(inPtr, inputBytes.length, outPtr)
  return readFromWasm(k, outPtr, outLen)
}

function buildLeafBuffer(leaves: Uint8Array[]): Uint8Array {
  const totalSize = leaves.reduce((s, l) => s + 4 + l.length, 0)
  const buf = new Uint8Array(totalSize)
  const view = new DataView(buf.buffer)
  let offset = 0
  for (const leaf of leaves) {
    view.setUint32(offset, leaf.length, true)
    offset += 4
    buf.set(leaf, offset)
    offset += leaf.length
  }
  return buf
}

function wasmMerkleRoot(k: KernelExports, leaves: Uint8Array[]): Uint8Array {
  const inPtr = k.get_input_ptr()
  const outPtr = k.get_output_ptr()
  const leafBuf = buildLeafBuffer(leaves)
  writeToWasm(k, leafBuf, inPtr)
  k.merkle_root(inPtr, leaves.length, outPtr)
  return readFromWasm(k, outPtr, 32)
}

// ─── BigInt replacer ───────────────────────────────────────

const bigintReplacer = (_: string, v: unknown): unknown =>
  typeof v === 'bigint' ? v.toString() : v

// ─── Governance fixture objects ────────────────────────────

// These are governance-representative objects — shaped like real
// runtime data but with no live system dependencies.

const FRAME_TRACE = {
  phase: 'HARMONIZE',
  sequence: '7',
  sitr_state: 'STABLE',
  aoie_verdict: 'PERMIT',
  frame_hash: 'a'.repeat(64),
  timestamp_ms: 1_600_000_007_000,
}

const POLICY_AMENDMENT = {
  amendment_id: 'b'.repeat(16),
  proposed_at_sequence: 3,
  target: 'src/constitutional/policy.ts',
  description: 'Tighten ESCALATE threshold',
  constraint_delta: '{"max_escalation_ratio":0.05}',
  status: 'APPROVED',
  guardian_verdict: 'APPROVED',
  schema_version: '1.0.0',
  is_replay_reconstructable: true,
}

const VOTE_RECORD = {
  validator: 'V1',
  block_hash: 'c'.repeat(64),
  sequence: '12',
  signature: 'd'.repeat(128),
}

const DEEP_GOVERNANCE_RECORD = {
  layer: 'L0',
  runtime: {
    phase: 'LOCK',
    consensus: {
      quorum: {
        threshold: 3,
        validators: ['V1', 'V2', 'V3', 'V4'],
        block_hash: 'e'.repeat(64),
      },
    },
  },
}

// FNV-1a seeded deterministic fixture generator (no Math.random)
function governanceFixtures(): Array<Record<string, unknown>> {
  const FNV_PRIME = 16777619
  const FNV_OFFSET = 2166136261
  const seed = 'aegis-gate-27-replay-equivalence'
  let h = FNV_OFFSET
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), FNV_PRIME) >>> 0
  }

  const fixtures: Array<Record<string, unknown>> = []
  for (let i = 0; i < 10; i++) {
    h = Math.imul(h ^ i, FNV_PRIME) >>> 0
    const h2 = Math.imul(h ^ (i + 100), FNV_PRIME) >>> 0
    fixtures.push({
      fixture_id: i,
      phase: ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'][h % 5],
      sequence: String(h % 10000),
      verdict: ['PERMIT', 'DEFER', 'REJECT', 'ESCALATE'][h2 % 4],
      score: (h2 % 1000) / 1000,
      anchor: (h ^ h2).toString(16).padStart(8, '0'),
    })
  }
  return fixtures
}

// ─── LedgerEntry helpers ───────────────────────────────────

function makeEntry(
  seq: bigint,
  prevHash: SHA256Hex,
  frameHash: SHA256Hex,
): LedgerEntry {
  return Object.freeze({
    sequence: seq as SequenceNumber,
    previous_hash: prevHash,
    frame_hash: frameHash,
    governance_hash: ('f'.repeat(64)) as SHA256Hex,
    timestamp_ms: 1_600_000_000_000 + Number(seq) * 1000,
  })
}

async function buildChain(length: number): Promise<readonly LedgerEntry[]> {
  let chain = LedgerChain.empty()
  let prevHash: SHA256Hex = GENESIS_HASH
  for (let i = 1; i <= length; i++) {
    const frameHash = ('0'.repeat(62) + i.toString(16).padStart(2, '0')) as SHA256Hex
    const entry = makeEntry(BigInt(i), prevHash, frameHash)
    chain = chain.append(entry)
    prevHash = await hashValue(entry)
  }
  return chain.getAll()
}

// ─── Tests ─────────────────────────────────────────────────

describe.skipIf(!WASM_READY)('WASM Replay Equivalence — Gate 27', () => {

  let k: KernelExports

  beforeAll(async () => {
    k = await ensureKernel()
  })

  // ── Proof A: SHA-256 parity on canonical governance bytes ──

  describe('Proof A — SHA-256 parity on canonical governance bytes', () => {
    const subjects = [
      { label: 'FramePhaseTrace', obj: FRAME_TRACE },
      { label: 'PolicyAmendment', obj: POLICY_AMENDMENT },
      { label: 'VoteRecord', obj: VOTE_RECORD },
      { label: 'DeepGovernanceRecord', obj: DEEP_GOVERNANCE_RECORD },
      { label: 'EmptyObject', obj: {} },
    ]

    for (const { label, obj } of subjects) {
      it(`SHA-256 parity: ${label} — TS sha256Hex == WASM sha256 × 3`, async () => {
        // Both receive the IDENTICAL input bytes (TypeScript's JCS output)
        const canonicalBytes = canonicalizeJCS(obj)
        const tsHash = await sha256Hex(canonicalBytes)

        for (let run = 0; run < 3; run++) {
          const wasmHashBytes = wasmSha256(k, canonicalBytes)
          const wasmHash = uint8ArrayToHex(wasmHashBytes)
          expect(wasmHash).toBe(tsHash)
          expect(wasmHash).toHaveLength(64)
        }
      })
    }

    it('SHA-256 parity: edge cases (array, number, null) × 3', async () => {
      const edgeCases: unknown[] = [[1, 2, 3], 42, null]
      for (const edge of edgeCases) {
        const bytes = canonicalizeJCS(edge)
        const tsHash = await sha256Hex(bytes)
        for (let run = 0; run < 3; run++) {
          const wasmHash = uint8ArrayToHex(wasmSha256(k, bytes))
          expect(wasmHash).toBe(tsHash)
        }
      }
    })
  })

  // ── Proof B: Canonicalization parity on governance JSON ───

  describe('Proof B — Canonicalization parity on governance JSON', () => {
    it('Parity: reverse-alphabetical 10-key object × 3', async () => {
      const obj = {
        z_field: 'z', y_field: 'y', x_field: 'x', w_field: 'w', v_field: 'v',
        u_field: 'u', t_field: 't', s_field: 's', r_field: 'r', q_field: 'q',
      }
      const tsBytes = canonicalizeJCS(obj)
      const jsonStr = JSON.stringify(obj, bigintReplacer)
      const inputBytes = new TextEncoder().encode(jsonStr)

      for (let run = 0; run < 3; run++) {
        const wasmBytes = wasmCanonicalize(k, inputBytes)
        expect(uint8ArrayToHex(wasmBytes)).toBe(uint8ArrayToHex(tsBytes))
        expect(new TextDecoder().decode(wasmBytes)).toBe(canonicalizeJCSString(obj))
      }
    })

    it('Parity: mixed-case key ordering (ASCII code point) × 3', async () => {
      // Uppercase letters (65-90) sort BEFORE lowercase (97-122) in RFC 8785
      const obj = { zebra: 1, Apple: 2, mango: 3, Banana: 4, cherry: 5 }
      const tsBytes = canonicalizeJCS(obj)
      const inputBytes = new TextEncoder().encode(JSON.stringify(obj, bigintReplacer))

      for (let run = 0; run < 3; run++) {
        const wasmBytes = wasmCanonicalize(k, inputBytes)
        expect(uint8ArrayToHex(wasmBytes)).toBe(uint8ArrayToHex(tsBytes))
      }
    })

    it('Parity: deeply nested governance object × 3', async () => {
      const obj = DEEP_GOVERNANCE_RECORD
      const tsBytes = canonicalizeJCS(obj)
      const inputBytes = new TextEncoder().encode(JSON.stringify(obj, bigintReplacer))

      for (let run = 0; run < 3; run++) {
        const wasmBytes = wasmCanonicalize(k, inputBytes)
        expect(uint8ArrayToHex(wasmBytes)).toBe(uint8ArrayToHex(tsBytes))
      }
    })

    it('Parity: LedgerEntry-shaped with pre-converted BigInt × 3', async () => {
      // BigInt contract: TS canonicalizeJCS(entry) serializes bigint as string.
      // WASM path uses JSON.stringify with bigintReplacer — same result.
      const entry = { sequence: '5', previous_hash: GENESIS_HASH, frame_hash: 'a'.repeat(64) }
      const tsBytes = canonicalizeJCS(entry)
      const inputBytes = new TextEncoder().encode(JSON.stringify(entry, bigintReplacer))

      for (let run = 0; run < 3; run++) {
        const wasmBytes = wasmCanonicalize(k, inputBytes)
        expect(uint8ArrayToHex(wasmBytes)).toBe(uint8ArrayToHex(tsBytes))
      }
    })

    it('Parity: string-escape stress (tab, newline, backslash, quote) × 3', async () => {
      const obj = { msg: 'line1\nline2', path: 'a\\b', quote: '"hello"', tab: '\there' }
      const tsBytes = canonicalizeJCS(obj)
      const inputBytes = new TextEncoder().encode(JSON.stringify(obj, bigintReplacer))

      for (let run = 0; run < 3; run++) {
        const wasmBytes = wasmCanonicalize(k, inputBytes)
        expect(uint8ArrayToHex(wasmBytes)).toBe(uint8ArrayToHex(tsBytes))
      }
    })
  })

  // ── Proof C: End-to-end hashValue() equivalence ───────────

  describe('Proof C — End-to-end hashValue() equivalence (core theorem)', () => {
    // TypeScript path:  hashValue(obj) = sha256Hex(canonicalizeJCS(obj))
    // WASM path:        sha256(canonicalize(json_str(obj, bigintReplacer)))
    // Assertion:        ts_hash === wasm_hash

    const coreSubjects = [
      { label: 'MinimalGovernanceRecord', obj: { sitr_state: 'STABLE', verdict: 'PERMIT', sequence: '1' } },
      { label: 'FramePhaseTrace', obj: FRAME_TRACE },
      { label: 'PolicyAmendment', obj: POLICY_AMENDMENT },
      { label: 'VoteRecord', obj: VOTE_RECORD },
    ]

    for (const { label, obj } of coreSubjects) {
      it(`Core theorem: ${label} — hashValue == wasm(canonicalize→sha256) × 3`, async () => {
        const tsHash = await hashValue(obj)

        const jsonStr = JSON.stringify(obj, bigintReplacer)
        const inputBytes = new TextEncoder().encode(jsonStr)

        for (let run = 0; run < 3; run++) {
          const wasmCanonical = wasmCanonicalize(k, inputBytes)
          const wasmHashBytes = wasmSha256(k, wasmCanonical)
          const wasmHash = uint8ArrayToHex(wasmHashBytes)
          expect(wasmHash).toBe(tsHash)
          expect(wasmHash).toHaveLength(64)
        }
      })
    }

    it('Core theorem: 10 deterministic governance fixtures × 3 runs each', async () => {
      const fixtures = governanceFixtures()
      for (const fixture of fixtures) {
        const tsHash = await hashValue(fixture)
        const inputBytes = new TextEncoder().encode(JSON.stringify(fixture, bigintReplacer))

        for (let run = 0; run < 3; run++) {
          const wasmCanonical = wasmCanonicalize(k, inputBytes)
          const wasmHash = uint8ArrayToHex(wasmSha256(k, wasmCanonical))
          expect(wasmHash).toBe(tsHash)
        }
      }
    })

    it('Core theorem: LedgerEntry with real bigint sequence × 3', async () => {
      // TS: canonicalizeJCS({sequence: 7n}) → {"sequence":"7"} (bigint→string)
      // WASM: JSON.stringify({sequence: 7n}, bigintReplacer) → '{"sequence":"7"}'
      // Contract: byte-identical after WASM canonicalize
      const entry = makeEntry(7n, GENESIS_HASH, ('b'.repeat(64)) as SHA256Hex)
      const tsHash = await hashValue(entry)

      // bigintReplacer converts 7n → "7" — same as TS canonicalizeJCS
      const inputBytes = new TextEncoder().encode(JSON.stringify(entry, bigintReplacer))

      for (let run = 0; run < 3; run++) {
        const wasmCanonical = wasmCanonicalize(k, inputBytes)
        const wasmHash = uint8ArrayToHex(wasmSha256(k, wasmCanonical))
        expect(wasmHash).toBe(tsHash)
      }
    })
  })

  // ── Proof D: Ledger chain link hash equivalence ───────────

  describe('Proof D — Ledger chain link hash equivalence', () => {
    let entries: readonly LedgerEntry[]

    beforeAll(async () => {
      entries = await buildChain(5)
    })

    it('WASM can independently verify all 5 chain links (3 full passes)', async () => {
      for (let pass = 0; pass < 3; pass++) {
        for (let i = 0; i < entries.length - 1; i++) {
          const entry = entries[i]!
          const nextEntry = entries[i + 1]!

          // WASM path: canonicalize the entry JSON (bigint pre-converted) → sha256
          const entryJson = JSON.stringify(entry, bigintReplacer)
          const inputBytes = new TextEncoder().encode(entryJson)
          const wasmCanonical = wasmCanonicalize(k, inputBytes)
          const wasmHash = uint8ArrayToHex(wasmSha256(k, wasmCanonical))

          // The next entry's previous_hash must equal the WASM-computed hash
          expect(nextEntry.previous_hash).toBe(wasmHash)
        }
      }
    })

    it('WASM chain hash is deterministic — identical across 3 passes', async () => {
      const hashes: string[][] = [[], [], []]

      for (let pass = 0; pass < 3; pass++) {
        for (const entry of entries) {
          const inputBytes = new TextEncoder().encode(JSON.stringify(entry, bigintReplacer))
          const wasmCanonical = wasmCanonicalize(k, inputBytes)
          const wasmHash = uint8ArrayToHex(wasmSha256(k, wasmCanonical))
          hashes[pass]!.push(wasmHash)
        }
      }

      // All three passes must produce identical hash sequences
      for (let i = 0; i < entries.length; i++) {
        expect(hashes[1]![i]).toBe(hashes[0]![i])
        expect(hashes[2]![i]).toBe(hashes[0]![i])
      }
    })

    it('WASM hash[0] matches TypeScript hashValue(entry[0]) — genesis anchor', async () => {
      const entry = entries[0]!
      const tsHash = await hashValue(entry)
      const inputBytes = new TextEncoder().encode(JSON.stringify(entry, bigintReplacer))
      const wasmCanonical = wasmCanonicalize(k, inputBytes)
      const wasmHash = uint8ArrayToHex(wasmSha256(k, wasmCanonical))
      expect(wasmHash).toBe(tsHash)
      // The second entry's previous_hash must match
      expect(entries[1]!.previous_hash).toBe(wasmHash)
    })
  })

  // ── Proof E: Merkle checkpoint equivalence ─────────────────

  describe('Proof E — Merkle checkpoint equivalence with governance data', () => {
    // TypeScript: computeMerkleRootFromValues([e1, e2, ...])
    //   = computeMerkleRoot([canonicalizeJCS(e1), canonicalizeJCS(e2), ...])
    // WASM: merkle_root(leaf_buffer_of([wasm_canonicalize(json(e1)), ...]))
    // Assertion: ts_root === wasm_root

    async function merkleEquivalenceTest(entryCount: number): Promise<void> {
      const entries = await buildChain(entryCount)

      // TypeScript path
      const tsRoot = await computeMerkleRootFromValues(entries)

      // WASM path: canonicalize each entry with bigintReplacer, then pass leaves to WASM merkle_root
      const wasmLeaves = entries.map(entry => {
        const inputBytes = new TextEncoder().encode(JSON.stringify(entry, bigintReplacer))
        return wasmCanonicalize(k, inputBytes)
      })

      for (let run = 0; run < 3; run++) {
        const wasmRootBytes = wasmMerkleRoot(k, wasmLeaves)
        const wasmRoot = uint8ArrayToHex(wasmRootBytes)
        expect(wasmRoot).toBe(tsRoot)
        expect(wasmRoot).toHaveLength(64)
      }
    }

    it('Merkle equivalence: 1 entry × 3', async () => {
      await merkleEquivalenceTest(1)
    })

    it('Merkle equivalence: 3 entries (odd — tests duplicate padding) × 3', async () => {
      await merkleEquivalenceTest(3)
    })

    it('Merkle equivalence: 4 entries (even) × 3', async () => {
      await merkleEquivalenceTest(4)
    })

    it('Merkle equivalence: 5 entries (odd) × 3', async () => {
      await merkleEquivalenceTest(5)
    })

    it('Merkle equivalence: empty chain → SHA-256 of empty bytes × 3', async () => {
      const tsRoot = await computeMerkleRootFromValues([])

      for (let run = 0; run < 3; run++) {
        const wasmRootBytes = wasmMerkleRoot(k, [])
        const wasmRoot = uint8ArrayToHex(wasmRootBytes)
        expect(wasmRoot).toBe(tsRoot)
      }
    })

    it('Different entry count produces different Merkle root', async () => {
      const entries3 = await buildChain(3)
      const entries4 = await buildChain(4)
      const root3 = await computeMerkleRootFromValues(entries3)
      const root4 = await computeMerkleRootFromValues(entries4)
      expect(root3).not.toBe(root4)
    })
  })

})
