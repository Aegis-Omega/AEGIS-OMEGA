// ============================================================
// Gate 42 — WASM Frame Hash Certification
// ~24 tests: topology hash parity, lineage hash parity,
//   attestation hash parity (null/non-null variants),
//   epoch hash parity.
//
// Extends Gate 27 (replay-equivalence.test.ts) to cover the
// frame-layer hash functions introduced in Gates 28–40:
//   computeTopologyHash (Gate 29)
//   computeLineageHash  (Gate 30)
//   buildSelfAttestation (Gate 35) → epoch_hash (Gate 39)
//
// PAYLOAD CONTRACTS (verified against src implementations):
//
//   topologyPayload = {
//     aoie_global_state, consensus_qc_hash, constitutional_verdict,
//     dfa_certificate_hash, ledger_root,
//     schema_version: '1.0.0',  ← ADDED by topologyPayload()
//     sequence,                  ← BigInt → JCS serializes as "N"
//     sitr_state,
//   }
//
//   lineagePayload = {
//     topology_hash, previous_topology_hash,
//     sequence,                  ← BigInt → JCS serializes as "N"
//   }
//
//   attestationPayload = {
//     dfa_certificate_hash, topology_hash,
//     lineage_terminal_hash: lth ?? 'genesis',
//     capsule_attestation_hash: cah ?? 'none',
//     sequence: sequence.toString(),  ← pre-converted string
//   }
//
// BigInt contract: JCS serializes BigInt as quoted decimal string.
// WASM path: JSON.stringify(payload, bigintReplacer) → wasm_canonicalize → wasm_sha256.
// Assertion: ts_hash === wasm_hash (64-char hex) for every variant × 3.
//
// Skipped gracefully if WASM binary is absent (CI without Rust).
// ============================================================

import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { computeTopologyHash } from '../../src/frame/topology.js'
import { computeLineageHash } from '../../src/frame/lineage.js'
import { buildSelfAttestation, type AttestationInput } from '../../src/frame/attestation.js'
import { uint8ArrayToHex } from '../../src/core/hashing.js'

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

/** Hash an arbitrary object via WASM: canonicalize then sha256 → 64-char hex. */
function wasmHashObject(k: KernelExports, obj: Record<string, unknown>): string {
  const json = JSON.stringify(obj, bigintReplacer)
  const jsonBytes = new TextEncoder().encode(json)
  const canonical = wasmCanonicalize(k, jsonBytes)
  const hashBytes = wasmSha256(k, canonical)
  return uint8ArrayToHex(hashBytes)
}

// ─── BigInt replacer ───────────────────────────────────────

const bigintReplacer = (_: string, v: unknown): unknown =>
  typeof v === 'bigint' ? v.toString() : v

// ─── Domain helpers ────────────────────────────────────────

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

// ─── Topology hash parity ──────────────────────────────────
// TypeScript: computeTopologyHash(input)
// WASM: wasmHashObject(topologyPayload) where topologyPayload adds schema_version

describe.skipIf(!WASM_READY)('Proof G1 — topology hash parity', () => {
  const topologyInputs = [
    {
      sitr_state: 'STABLE' as const,
      aoie_global_state: 'SECURE' as const,
      constitutional_verdict: 'PERMIT' as const,
      ledger_root: h('a'),
      consensus_qc_hash: null,
      dfa_certificate_hash: h('b'),
      sequence: seq(1),
    },
    {
      sitr_state: 'DEGRADED' as const,
      aoie_global_state: 'ALERT' as const,
      constitutional_verdict: 'ESCALATE' as const,
      ledger_root: h('c'),
      consensus_qc_hash: h('d'),
      dfa_certificate_hash: h('e'),
      sequence: seq(42),
    },
    {
      sitr_state: 'COMPROMISED' as const,
      aoie_global_state: 'COMPROMISED' as const,
      constitutional_verdict: 'REJECT' as const,
      ledger_root: h('f'),
      consensus_qc_hash: h('9'),
      dfa_certificate_hash: h('8'),
      sequence: seq(999),
    },
    {
      sitr_state: 'STABLE' as const,
      aoie_global_state: 'SECURE' as const,
      constitutional_verdict: 'PERMIT' as const,
      ledger_root: h('0'),
      consensus_qc_hash: h('1'),
      dfa_certificate_hash: h('2'),
      sequence: seq(1_000_000),
    },
    {
      sitr_state: 'DEGRADED' as const,
      aoie_global_state: 'SECURE' as const,
      constitutional_verdict: 'PERMIT' as const,
      ledger_root: h('3'),
      consensus_qc_hash: null,
      dfa_certificate_hash: h('4'),
      sequence: seq(7),
    },
  ] as const

  for (const input of topologyInputs) {
    it(`seq=${input.sequence} qc=${input.consensus_qc_hash === null ? 'null' : 'set'}: ts === wasm × 3`, async () => {
      const k = await ensureKernel()
      const tsHash = await computeTopologyHash(input)

      // Replicate topologyPayload() from topology.ts — must include schema_version
      const wasmPayload: Record<string, unknown> = {
        aoie_global_state: input.aoie_global_state,
        consensus_qc_hash: input.consensus_qc_hash,
        constitutional_verdict: input.constitutional_verdict,
        dfa_certificate_hash: input.dfa_certificate_hash,
        ledger_root: input.ledger_root,
        schema_version: '1.0.0',
        sequence: input.sequence,
        sitr_state: input.sitr_state,
      }

      const wh1 = wasmHashObject(k, wasmPayload)
      const wh2 = wasmHashObject(k, wasmPayload)
      const wh3 = wasmHashObject(k, wasmPayload)
      expect(tsHash).toBe(wh1)
      expect(wh1).toBe(wh2)
      expect(wh2).toBe(wh3)
    })
  }
})

// ─── Lineage hash parity ───────────────────────────────────
// TypeScript: computeLineageHash(topHash, prevHash, seq)
// WASM: wasmHashObject({ topology_hash, previous_topology_hash, sequence })

describe.skipIf(!WASM_READY)('Proof G2 — lineage hash parity', () => {
  const lineageCases: Array<{ topHash: SHA256Hex; prevHash: SHA256Hex; seqVal: SequenceNumber }> = [
    { topHash: h('a'), prevHash: h('0'), seqVal: seq(1) },
    { topHash: h('b'), prevHash: h('a'), seqVal: seq(2) },
    { topHash: h('c'), prevHash: h('b'), seqVal: seq(100) },
    { topHash: h('f'), prevHash: h('e'), seqVal: (2n ** 32n) as SequenceNumber },
  ]

  for (const { topHash, prevHash, seqVal } of lineageCases) {
    it(`seq=${seqVal}: ts === wasm × 3`, async () => {
      const k = await ensureKernel()
      const tsHash = await computeLineageHash(topHash, prevHash, seqVal)

      const wasmPayload: Record<string, unknown> = {
        topology_hash: topHash,
        previous_topology_hash: prevHash,
        sequence: seqVal,  // BigInt → bigintReplacer converts to string
      }

      const wh1 = wasmHashObject(k, wasmPayload)
      const wh2 = wasmHashObject(k, wasmPayload)
      const wh3 = wasmHashObject(k, wasmPayload)
      expect(tsHash).toBe(wh1)
      expect(wh1).toBe(wh2)
      expect(wh2).toBe(wh3)
    })
  }
})

// ─── Attestation hash parity ───────────────────────────────
// TypeScript: buildSelfAttestation(input).attestation_hash
// WASM: wasmHashObject(attestationPayload) with null sentinels
//
// Key: sequence is pre-converted to string in attestationPayload.
// null lineage_terminal_hash → 'genesis'
// null capsule_attestation_hash → 'none'

describe.skipIf(!WASM_READY)('Proof G3 — attestation hash parity', () => {
  const attestationCases: AttestationInput[] = [
    {
      dfa_certificate_hash: h('d'),
      topology_hash: h('t'),
      lineage_terminal_hash: null,
      capsule_attestation_hash: null,
      sequence: seq(1),
    },
    {
      dfa_certificate_hash: h('d'),
      topology_hash: h('t'),
      lineage_terminal_hash: h('l'),
      capsule_attestation_hash: null,
      sequence: seq(5),
    },
    {
      dfa_certificate_hash: h('d'),
      topology_hash: h('t'),
      lineage_terminal_hash: null,
      capsule_attestation_hash: h('c'),
      sequence: seq(10),
    },
    {
      dfa_certificate_hash: h('d'),
      topology_hash: h('t'),
      lineage_terminal_hash: h('l'),
      capsule_attestation_hash: h('c'),
      sequence: seq(100),
    },
    {
      dfa_certificate_hash: h('1'),
      topology_hash: h('2'),
      lineage_terminal_hash: h('3'),
      capsule_attestation_hash: h('4'),
      sequence: seq(999),
    },
    {
      dfa_certificate_hash: h('a'),
      topology_hash: h('b'),
      lineage_terminal_hash: null,
      capsule_attestation_hash: h('c'),
      sequence: (2n ** 32n) as SequenceNumber,
    },
  ]

  for (const input of attestationCases) {
    const label = `seq=${input.sequence} lth=${input.lineage_terminal_hash === null ? 'null' : 'set'} cah=${input.capsule_attestation_hash === null ? 'null' : 'set'}`
    it(`${label}: ts === wasm × 3`, async () => {
      const k = await ensureKernel()
      const record = await buildSelfAttestation(input)
      const tsHash = record.attestation_hash

      // Replicate attestationPayload from attestation.ts
      const wasmPayload: Record<string, unknown> = {
        dfa_certificate_hash: input.dfa_certificate_hash,
        topology_hash: input.topology_hash,
        lineage_terminal_hash: input.lineage_terminal_hash ?? 'genesis',
        capsule_attestation_hash: input.capsule_attestation_hash ?? 'none',
        sequence: input.sequence.toString(),
      }

      const wh1 = wasmHashObject(k, wasmPayload)
      const wh2 = wasmHashObject(k, wasmPayload)
      const wh3 = wasmHashObject(k, wasmPayload)
      expect(tsHash).toBe(wh1)
      expect(wh1).toBe(wh2)
      expect(wh2).toBe(wh3)
    })
  }
})

// ─── Epoch hash parity ─────────────────────────────────────
// epoch_hash === attestation_hash (by construction in epoch.ts).
// This group verifies that different attestation inputs produce
// distinct, stable hashes — the epoch is implementation-invariant.

describe.skipIf(!WASM_READY)('Proof G4 — epoch hash stability and distinguishability', () => {
  it('different attestation inputs produce different wasm hashes', async () => {
    const k = await ensureKernel()
    const makePayload = (n: number): Record<string, unknown> => ({
      dfa_certificate_hash: h(n.toString(16).slice(-1)!.repeat(1).padEnd(1, '0')),
      topology_hash: h(((n + 1) % 16).toString(16)),
      lineage_terminal_hash: n % 2 === 0 ? h('e') : 'genesis',
      capsule_attestation_hash: 'none',
      sequence: seq(n).toString(),
    })
    const h1 = wasmHashObject(k, makePayload(1))
    const h2 = wasmHashObject(k, makePayload(2))
    const h3 = wasmHashObject(k, makePayload(3))
    expect(h1).not.toBe(h2)
    expect(h2).not.toBe(h3)
    expect(h1).not.toBe(h3)
  })

  it('same attestation input is stable × 5', async () => {
    const k = await ensureKernel()
    const payload: Record<string, unknown> = {
      dfa_certificate_hash: h('d'),
      topology_hash: h('t'),
      lineage_terminal_hash: h('l'),
      capsule_attestation_hash: 'none',
      sequence: '42',
    }
    const hashes = Array.from({ length: 5 }, () => wasmHashObject(k, payload))
    for (const hash of hashes) expect(hash).toBe(hashes[0])
  })

  it('topology hash feeds correctly into attestation hash (composition)', async () => {
    const k = await ensureKernel()
    const input = {
      sitr_state: 'STABLE' as const,
      aoie_global_state: 'SECURE' as const,
      constitutional_verdict: 'PERMIT' as const,
      ledger_root: h('a'),
      consensus_qc_hash: null,
      dfa_certificate_hash: h('b'),
      sequence: seq(5),
    }

    // Step 1: compute topology hash via both paths
    const tsTopHash = await computeTopologyHash(input)
    const wasmTopPayload: Record<string, unknown> = {
      aoie_global_state: input.aoie_global_state,
      consensus_qc_hash: input.consensus_qc_hash,
      constitutional_verdict: input.constitutional_verdict,
      dfa_certificate_hash: input.dfa_certificate_hash,
      ledger_root: input.ledger_root,
      schema_version: '1.0.0',
      sequence: input.sequence,
      sitr_state: input.sitr_state,
    }
    const wasmTopHash = wasmHashObject(k, wasmTopPayload)
    expect(tsTopHash).toBe(wasmTopHash)

    // Step 2: use ts topology_hash in attestation — WASM path also uses same hash
    const attestInput: AttestationInput = {
      dfa_certificate_hash: h('d'),
      topology_hash: tsTopHash,
      lineage_terminal_hash: null,
      capsule_attestation_hash: null,
      sequence: seq(5),
    }
    const tsAttest = await buildSelfAttestation(attestInput)
    const wasmAttestPayload: Record<string, unknown> = {
      dfa_certificate_hash: h('d'),
      topology_hash: wasmTopHash,  // same as tsTopHash
      lineage_terminal_hash: 'genesis',
      capsule_attestation_hash: 'none',
      sequence: seq(5).toString(),
    }
    const wasmAttestHash = wasmHashObject(k, wasmAttestPayload)
    expect(tsAttest.attestation_hash).toBe(wasmAttestHash)
  })
})
