// ============================================================
// Skill Harness — Cognitive Triad Seed Skills
// EPISTEMIC TIER: T0/T1 — anchored at genesis
//
// Three constitutional resonance anchors shared across all swarm agents.
// Every position of a character (x) in the swarm must be in resonance
// before its skill propagates. These seeds ARE the verifiability baseline:
//   AdaptivePower(T) ≤ ReplayVerifiability(T)
//
// Each seed satisfies all 4 resonance conditions → CERTIFIED (coefficient > 5.0):
//   name.length has Triadic digital root {dr ∈ {3,6,9}}
//   domain_affinity is palindrome (A-B-A)
//   failure_rate < 1/φ ≈ 0.6180
//   validated_runs > 0 (sequence_monotone)
// ============================================================

import type { SkillInput } from './types.js'

const GENESIS_DATE = '2026-01-01T00:00:00Z'

// "replay-sovereignty": length=18, digital_root(18 % 9 = 0)=9, Triadic
// domain: ["governance","replay","governance"] — palindrome (arr[0]===arr[2])
// T0 — replay sovereignty mechanically proven (WASM equivalence, Gate 27)
const REPLAY_SOVEREIGNTY: SkillInput = {
  skill_id: 'replay_sovereignty',
  name: 'replay-sovereignty',
  confidence: 0.99,
  validated_runs: 2733,
  failure_rate: 0.01,
  recency_score: 1.0,
  domain_affinity: ['governance', 'replay', 'governance'],
  dependencies: [],
  evidence_refs: [
    'genesis:2733-ts-tests',
    'genesis:gate8-passing',
    'genesis:wasm-equivalence-gate27',
  ],
  last_validated: GENESIS_DATE,
  epistemic_tier: 'T0',
  primitive_mapping: 'CANONICALIZE',
}

// "hash-chain-seal": length=15, digital_root(15 % 9 = 6)=6, Triadic
// domain: ["integrity","hash","integrity"] — palindrome
// T0 — SHA-256 + RFC 8785 JCS chain integrity mechanically proven
const HASH_CHAIN_SEAL: SkillInput = {
  skill_id: 'hash_chain_seal',
  name: 'hash-chain-seal',
  confidence: 0.99,
  validated_runs: 305,
  failure_rate: 0.01,
  recency_score: 1.0,
  domain_affinity: ['integrity', 'hash', 'integrity'],
  dependencies: ['replay_sovereignty'],
  evidence_refs: [
    'genesis:305-rust-tests',
    'genesis:sha256-rfc8785',
    'genesis:resonance-monitor-gate222',
  ],
  last_validated: GENESIS_DATE,
  epistemic_tier: 'T0',
  primitive_mapping: 'HASH',
}

// "ring-harmony-verifier": length=21, digital_root(21 % 9 = 3)=3, Triadic
// domain: ["harmony","structure","harmony"] — palindrome
// T1 — ring composition empirically validated (Cuypers 2015, Gate 217)
const RING_HARMONY_VERIFIER: SkillInput = {
  skill_id: 'ring_harmony_verifier',
  name: 'ring-harmony-verifier',
  confidence: 0.95,
  validated_runs: 279,
  failure_rate: 0.05,
  recency_score: 1.0,
  domain_affinity: ['harmony', 'structure', 'harmony'],
  dependencies: ['replay_sovereignty', 'hash_chain_seal'],
  evidence_refs: [
    'genesis:tajweed-dfa-t1',
    'genesis:ring-composition-gate217',
    'genesis:resonance-monitor-gate222',
  ],
  last_validated: GENESIS_DATE,
  epistemic_tier: 'T1',
  primitive_mapping: 'VERIFY',
}

// Minimum 3 seeds shared across all swarm agents — the constitutional sound floor.
export const COGNITIVE_TRIAD: readonly SkillInput[] = Object.freeze([
  REPLAY_SOVEREIGNTY,
  HASH_CHAIN_SEAL,
  RING_HARMONY_VERIFIER,
])

export const COGNITIVE_TRIAD_IDS: readonly string[] = Object.freeze(
  COGNITIVE_TRIAD.map(s => s.skill_id),
)
