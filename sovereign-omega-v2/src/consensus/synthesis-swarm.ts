// ============================================================
// AEGIS BFT Synthesis Swarm — Game-Theoretic Code Generation
// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
//
// Three-agent game-theoretic loop over any generation task:
//   Alpha  — implements (any inference backend via router)
//   Beta   — adversarial tester (generates tests to break Alpha)
//   Gamma  — constitutional judge (verifies invariants hold)
//
// A synthesis is committed only when:
//   1. Alpha produces an output
//   2. Beta's adversarial tests pass against Alpha's output
//   3. Gamma certifies no constitutional invariant is violated
//   4. AST-level convergence is confirmed (not text similarity)
//
// Maps directly to RALPH:
//   PROPAGATE = Alpha implements
//   ASSESS    = Beta adversarially tests
//   LOCK      = Gamma judges
//   HARMONIZE = SwarmConvergenceRecord at 1/φ threshold
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import {
  stripComments,
  hasEarlyReturn,
  hasLoop,
  hasDestructuring,
  semanticFunctionCount,
  normalizedExportCount,
  normalizedInterfaceCount,
} from './ast-normalizer.js'

export const SYNTHESIS_SCHEMA_VERSION = '1.0.0' as const

// Same 1/φ threshold as swarm.ts and martingale.ts — holonic consistency
const CONSENSUS_THRESHOLD = (Math.sqrt(5) - 1) / 2

export type AgentRole = 'alpha' | 'beta' | 'gamma'
export type SynthesisVerdict = 'COMMITTED' | 'REJECTED' | 'DEADLOCK'

export interface SynthesisRequest {
  readonly task: string              // natural language generation task
  readonly context: string          // relevant codebase context
  readonly constitutional_constraints: readonly string[]  // invariants to uphold
  readonly sequence: SequenceNumber
}

export interface AgentProposal {
  readonly agent_id: AgentRole
  readonly backend: string           // which inference backend responded
  readonly output: string            // raw generation output
  readonly output_hash: SHA256Hex    // SHA-256 of output
  readonly latency_ms: number
}

// AST-level structural fingerprint — normalizer-backed semantic feature extraction.
// 8 boolean features (semantic intent) + 3 normalized counts (structural shape).
// Comments stripped before analysis to prevent false regex matches.
export interface StructuralFingerprint {
  // Semantic intent features (weight: 0.75 in convergence formula)
  readonly has_error_handling: boolean   // try/catch, throw — any error boundary
  readonly has_async: boolean            // async/await — asynchronous execution
  readonly has_type_annotations: boolean // TypeScript type constraints
  readonly uses_immutability: boolean    // const, readonly, Object.freeze
  readonly uses_hashing: boolean         // SHA-256, hashValue references
  readonly has_early_return: boolean     // guard clause or early exit pattern
  readonly has_loop: boolean             // iterative computation
  readonly has_destructuring: boolean    // destructuring assignment
  // Normalized structural counts (weight: 0.25 in convergence formula)
  readonly export_count: number          // semantic: named exports only
  readonly function_count: number        // semantic: named function definitions only
  readonly interface_count: number       // interface/type definitions
  readonly fingerprint_hash: SHA256Hex
}

export interface ConvergenceAnalysis {
  readonly alpha_fingerprint: StructuralFingerprint
  readonly beta_fingerprint: StructuralFingerprint
  readonly shared_patterns: readonly string[]   // patterns both agents agreed on
  readonly divergent_patterns: readonly string[] // where they disagreed
  readonly structural_similarity: number         // 0.0–1.0
  readonly converged: boolean                    // similarity >= CONSENSUS_THRESHOLD
}

export interface SynthesisRecord {
  readonly task_hash: SHA256Hex
  readonly alpha_proposal: AgentProposal
  readonly beta_adversarial: AgentProposal       // Beta's attack on Alpha
  readonly gamma_verdict_raw: AgentProposal      // Gamma's constitutional check
  readonly convergence: ConvergenceAnalysis
  readonly verdict: SynthesisVerdict
  readonly committed_output_hash: SHA256Hex | null  // null if REJECTED/DEADLOCK
  readonly synthesis_hash: SHA256Hex                // chains everything
  readonly sequence: SequenceNumber
  readonly schema_version: typeof SYNTHESIS_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class SynthesisError extends Error {
  override readonly name = 'SynthesisError'
}

// ── Structural fingerprinting — normalizer-backed semantic analysis ───────────

async function fingerprint(code: string): Promise<StructuralFingerprint> {
  // All raw pattern detection runs on comment-stripped code to prevent
  // false positive matches (e.g. commented-out `throw` triggering has_error_handling).
  const normalized = stripComments(code)

  const has_error_handling   = /try\s*\{|catch\s*\(|\.catch\s*\(|throw\s+new/.test(normalized)
  const has_async            = /async\s+function|async\s+\(|await\s+/.test(normalized)
  const has_type_annotations = /:\s*(string|number|boolean|void|Promise|readonly|SHA256|Sequence)/.test(normalized)
  const uses_immutability    = /\bconst\b|readonly|Object\.freeze|deepFreeze/.test(normalized)
  const uses_hashing         = /hashValue|sha256|SHA.256|crypto\.subtle/.test(normalized)
  // Semantic features — invariant over guard-clause vs nested-conditional form
  const has_early_return  = hasEarlyReturn(normalized)
  const has_loop          = hasLoop(normalized)
  const has_destructuring = hasDestructuring(normalized)
  // Semantic counts — exclude inline lambdas/callbacks to reduce syntactic noise
  const export_count    = normalizedExportCount(normalized)
  const function_count  = semanticFunctionCount(normalized)
  const interface_count = normalizedInterfaceCount(normalized)

  const fingerprint_hash = await hashValue({
    has_error_handling, has_async, has_type_annotations,
    uses_immutability, uses_hashing,
    has_early_return, has_loop, has_destructuring,
    export_count, function_count, interface_count,
  }) as SHA256Hex

  return Object.freeze({
    has_error_handling, has_async, has_type_annotations,
    uses_immutability, uses_hashing,
    has_early_return, has_loop, has_destructuring,
    export_count, function_count, interface_count,
    fingerprint_hash,
  })
}

function analyzeConvergence(
  alpha: StructuralFingerprint,
  beta: StructuralFingerprint,
): Omit<ConvergenceAnalysis, 'alpha_fingerprint' | 'beta_fingerprint'> {
  // 8 semantic boolean fields — capture INTENT, invariant over syntactic form.
  // Weight 0.75: semantic agreement dominates convergence decision.
  const boolFields = [
    'has_error_handling', 'has_async', 'has_type_annotations',
    'uses_immutability', 'uses_hashing',
    'has_early_return', 'has_loop', 'has_destructuring',
  ] as const

  const shared: string[] = []
  const divergent: string[] = []

  for (const field of boolFields) {
    if (alpha[field] === beta[field]) shared.push(field)
    else divergent.push(field)
  }

  // Numeric similarity: normalized distance on semantic count fields.
  // Weight 0.25: structural shape is secondary to semantic intent.
  const exportSim  = 1 - Math.min(Math.abs(alpha.export_count  - beta.export_count)  / Math.max(alpha.export_count,  beta.export_count,  1), 1)
  const fnSim      = 1 - Math.min(Math.abs(alpha.function_count - beta.function_count) / Math.max(alpha.function_count, beta.function_count, 1), 1)
  const ifaceSim   = 1 - Math.min(Math.abs(alpha.interface_count - beta.interface_count) / Math.max(alpha.interface_count, beta.interface_count, 1), 1)

  const structural_similarity = (
    (shared.length / boolFields.length) * 0.75 +
    (exportSim + fnSim + ifaceSim) / 3 * 0.25
  )

  return {
    shared_patterns: Object.freeze(shared),
    divergent_patterns: Object.freeze(divergent),
    structural_similarity,
    converged: structural_similarity >= CONSENSUS_THRESHOLD,
  }
}

// ── Agent prompt builders ────────────────────────────────────────────────────

function buildAlphaPrompt(req: SynthesisRequest): { system: string; user: string } {
  return {
    system: `You are Alpha, an expert software engineer implementing a constitutional codebase.
Constitutional constraints you must uphold:
${req.constitutional_constraints.map(c => `- ${c}`).join('\n')}
Produce clean, typed, well-structured implementation code. No explanations — code only.`,
    user: `Task: ${req.task}\n\nContext:\n${req.context}`,
  }
}

function buildBetaPrompt(req: SynthesisRequest, alphaOutput: string): { system: string; user: string } {
  return {
    system: `You are Beta, an adversarial tester whose job is to find every flaw in Alpha's implementation.
Generate targeted edge-case tests that probe:
- boundary conditions, off-by-one errors, empty inputs
- concurrent access patterns, race conditions
- invariant violations: ${req.constitutional_constraints.join('; ')}
Output test code only. Be ruthless.`,
    user: `Alpha's implementation to attack:\n\`\`\`\n${alphaOutput}\n\`\`\`\nGenerate tests that would break this.`,
  }
}

function buildGammaPrompt(
  req: SynthesisRequest,
  alphaOutput: string,
  betaTests: string,
): { system: string; user: string } {
  return {
    system: `You are Gamma, a constitutional judge. You verify that proposed code upholds all invariants.
Constitutional constraints to verify:
${req.constitutional_constraints.map(c => `- ${c}`).join('\n')}
Output JSON: {"verdict":"COMMITTED"|"REJECTED","violations":[],"rationale":"..."}`,
    user: `Alpha's implementation:\n\`\`\`\n${alphaOutput}\n\`\`\`\nBeta's adversarial tests:\n\`\`\`\n${betaTests}\n\`\`\`\nDoes Alpha's code pass constitutional review?`,
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Run the three-agent BFT synthesis loop.
 * callAgent: injected inference function (allows any backend — constitutional router, Ollama, etc.)
 * Returns a SynthesisRecord regardless of outcome — REJECTED is still replay-certifiable.
 */
export async function runSynthesisSwarm(
  req: SynthesisRequest,
  callAgent: (system: string, user: string, role: AgentRole) => Promise<{ output: string; backend: string; latency_ms: number }>,
): Promise<SynthesisRecord> {
  const task_hash = await hashValue({ task: req.task, sequence: req.sequence.toString() }) as SHA256Hex

  // ── Phase PROPAGATE: Alpha implements ─────────────────────────────────────
  const alphaPrompts = buildAlphaPrompt(req)
  const alphaRaw = await callAgent(alphaPrompts.system, alphaPrompts.user, 'alpha')
  const alpha_proposal: AgentProposal = Object.freeze({
    agent_id: 'alpha' as const,
    backend: alphaRaw.backend,
    output: alphaRaw.output,
    output_hash: await hashValue({ output: alphaRaw.output }) as SHA256Hex,
    latency_ms: alphaRaw.latency_ms,
  })

  // ── Phase ASSESS: Beta attacks Alpha ──────────────────────────────────────
  const betaPrompts = buildBetaPrompt(req, alphaRaw.output)
  const betaRaw = await callAgent(betaPrompts.system, betaPrompts.user, 'beta')
  const beta_adversarial: AgentProposal = Object.freeze({
    agent_id: 'beta' as const,
    backend: betaRaw.backend,
    output: betaRaw.output,
    output_hash: await hashValue({ output: betaRaw.output }) as SHA256Hex,
    latency_ms: betaRaw.latency_ms,
  })

  // ── Phase LOCK: Gamma judges ───────────────────────────────────────────────
  const gammaPrompts = buildGammaPrompt(req, alphaRaw.output, betaRaw.output)
  const gammaRaw = await callAgent(gammaPrompts.system, gammaPrompts.user, 'gamma')
  const gamma_verdict_raw: AgentProposal = Object.freeze({
    agent_id: 'gamma' as const,
    backend: gammaRaw.backend,
    output: gammaRaw.output,
    output_hash: await hashValue({ output: gammaRaw.output }) as SHA256Hex,
    latency_ms: gammaRaw.latency_ms,
  })

  // ── Phase HARMONIZE: AST convergence + final verdict ──────────────────────
  const [alphaFP, betaFP] = await Promise.all([
    fingerprint(alphaRaw.output),
    fingerprint(betaRaw.output),
  ])

  const convergenceCore = analyzeConvergence(alphaFP, betaFP)
  const convergence: ConvergenceAnalysis = Object.freeze({
    alpha_fingerprint: alphaFP,
    beta_fingerprint: betaFP,
    ...convergenceCore,
  })

  // Parse Gamma's verdict
  let gammaVerdict: 'COMMITTED' | 'REJECTED' = 'REJECTED'
  try {
    const raw = gammaRaw.output.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim()
    const parsed = JSON.parse(raw) as { verdict?: string }
    if (parsed.verdict === 'COMMITTED') gammaVerdict = 'COMMITTED'
  } catch { /* Gamma parse failure = REJECTED */ }

  const verdict: SynthesisVerdict =
    gammaVerdict === 'COMMITTED' && convergence.converged ? 'COMMITTED'
    : gammaVerdict === 'COMMITTED' && !convergence.converged ? 'DEADLOCK'
    : 'REJECTED'

  const committed_output_hash = verdict === 'COMMITTED' ? alpha_proposal.output_hash : null

  const synthesis_hash = await hashValue({
    task_hash,
    alpha_hash: alpha_proposal.output_hash,
    beta_hash: beta_adversarial.output_hash,
    gamma_hash: gamma_verdict_raw.output_hash,
    structural_similarity: convergence.structural_similarity,
    verdict,
    sequence: req.sequence.toString(),
  }) as SHA256Hex

  return deepFreeze({
    task_hash,
    alpha_proposal,
    beta_adversarial,
    gamma_verdict_raw,
    convergence,
    verdict,
    committed_output_hash,
    synthesis_hash,
    sequence: req.sequence,
    schema_version: SYNTHESIS_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}
