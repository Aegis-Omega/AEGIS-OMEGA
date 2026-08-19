import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, test } from 'vitest';

import {
  FORMALIZATION_BINDING_AUTHORITY,
  KERNEL_RESULT_AUTHORITY,
  MATH_CLAIM_AUTHORITY,
} from '../../src/math-verification/contracts';
import { aggregateMathVerificationV1 } from '../../src/math-verification/aggregate';
import { auditFormalSource } from '../../src/math-verification/source-audit';

const corpusPath = path.resolve(process.cwd(), '..', 'test-vectors', 'math-verification', 'math-disproval-gate-v1.json');
const A = 'a'.repeat(64);
const B = 'b'.repeat(64);
const C = 'c'.repeat(64);
const D = 'd'.repeat(64);

type AggregateVector = {
  id: string;
  class: 'AGGREGATE';
  scenario: string;
  expected_verdict: 'PROVED' | 'DISPROVED' | 'UNRESOLVED';
  expected_level: 'SINGLE_KERNEL' | 'CROSS_KERNEL';
  expected_rejected?: number;
  expected_diagnostic?: string;
};
type SourceVector = {
  id: string;
  class: 'SOURCE_AUDIT';
  source_kind: 'COQ' | 'LEAN';
  source: string;
  expected_strict: boolean;
  expected_forbidden: string[];
};
type Vector = AggregateVector | SourceVector;
type Corpus = { schema_version: '1.0.0'; corpus_kind: 'MATH_DISPROVAL_GATE_V1_VECTORS'; cases: Vector[] };

const corpus = (): Corpus => JSON.parse(readFileSync(corpusPath, 'utf8')) as Corpus;
const claim = () => ({
  schema_version: '1.0.0', claim_kind: 'MATH_CLAIM_ENVELOPE_V1', claim_id: 'math:claim:001',
  claim_text_digest: A, claim_digest: A, assumptions_digest: B, notation_digest: C,
  source_artifact_digests: [A], policy_commitment: D, authority_epoch: 7, nonce: 'math-nonce-001',
  authority: MATH_CLAIM_AUTHORITY,
});
const binding = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0.0', binding_kind: 'FORMALIZATION_BINDING_V1', claim_id: 'math:claim:001',
  claim_digest: A, assumptions_digest: B, formalization_binding_digest: C,
  lean_source_sha256: A, coq_source_sha256: B, lean_toolchain_commitment: C,
  coq_toolchain_commitment: D, policy_commitment: D, authority_epoch: 7,
  authority: FORMALIZATION_BINDING_AUTHORITY, ...overrides,
});
const result = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0.0', result_kind: 'KERNEL_VERIFICATION_RESULT_V1', kernel_family: 'COQ',
  kernel_version: '8.20', formalization_sha256: B, formalization_binding_digest: C,
  claim_digest: A, assumptions_digest: B, attempt_kind: 'PROVE', process_status: 'VERIFIED',
  proof_artifact_sha256: D, counterexample_artifact_sha256: null, stdout_sha256: A, stderr_sha256: A,
  started_at_ms: 1_000, finished_at_ms: 1_001, authority: KERNEL_RESULT_AUTHORITY, ...overrides,
});

function scenario(name: string): { bind: unknown; results: unknown[] } {
  switch (name) {
    case 'COQ_PROVE': return { bind: binding(), results: [result()] };
    case 'LEAN_PROVE': return { bind: binding(), results: [result({ kernel_family: 'LEAN', kernel_version: '4.32.0', formalization_sha256: A })] };
    case 'COQ_NEGATION': return { bind: binding(), results: [result({ attempt_kind: 'DISPROVE_NEGATION' })] };
    case 'COQ_COUNTEREXAMPLE': return { bind: binding(), results: [result({ attempt_kind: 'DISPROVE_COUNTEREXAMPLE', proof_artifact_sha256: null, counterexample_artifact_sha256: D })] };
    case 'CROSS_PROVE': return { bind: binding(), results: [result(), result({ kernel_family: 'LEAN', kernel_version: '4.32.0', formalization_sha256: A, stdout_sha256: B })] };
    case 'CROSS_DISPROVE': return { bind: binding(), results: [result({ attempt_kind: 'DISPROVE_NEGATION' }), result({ kernel_family: 'LEAN', kernel_version: '4.32.0', formalization_sha256: A, attempt_kind: 'DISPROVE_NEGATION', stdout_sha256: B })] };
    case 'TIMEOUT': return { bind: binding(), results: [result({ process_status: 'TIMEOUT', proof_artifact_sha256: null })] };
    case 'ERROR': return { bind: binding(), results: [result({ process_status: 'ERROR', proof_artifact_sha256: null })] };
    case 'REJECTED': return { bind: binding(), results: [result({ process_status: 'REJECTED', proof_artifact_sha256: null })] };
    case 'HEURISTIC_ONLY': return { bind: binding(), results: [] };
    case 'WRONG_CLAIM': return { bind: binding(), results: [result({ claim_digest: D })] };
    case 'WRONG_ASSUMPTIONS': return { bind: binding(), results: [result({ assumptions_digest: D })] };
    case 'WRONG_BINDING': return { bind: binding(), results: [result({ formalization_binding_digest: D })] };
    case 'STALE_POLICY': return { bind: binding({ policy_commitment: A }), results: [result()] };
    case 'UNKNOWN_FIELD': return { bind: binding(), results: [{ ...result(), execute: true }] };
    case 'CONTRADICTION': return { bind: binding(), results: [result({ proof_artifact_sha256: A }), result({ attempt_kind: 'DISPROVE_NEGATION', proof_artifact_sha256: B, stdout_sha256: C })] };
    case 'FORMALIZATION_DIGEST_TAMPER': return { bind: binding(), results: [result({ formalization_sha256: D })] };
    case 'CROSS_DIFFERENT_BINDING': return { bind: binding(), results: [result(), result({ kernel_family: 'LEAN', kernel_version: '4.32.0', formalization_sha256: A, formalization_binding_digest: D })] };
    case 'ATTEMPT_ARTIFACT_LAUNDER': return { bind: binding(), results: [result({ counterexample_artifact_sha256: A })] };
    case 'RECEIPT_INJECTION': return { bind: binding(), results: [{ ...result(), decision_receipt: { verdict: 'PERMIT' } }] };
    default: throw new Error(`UNKNOWN_VECTOR_SCENARIO:${name}`);
  }
}

describe('MATH_DISPROVAL_GATE_V1 canonical falsification corpus', () => {
  test('corpus is versioned, unique and has at least twenty adversarial cases', () => {
    const c = corpus();
    expect(c.schema_version).toBe('1.0.0');
    expect(c.corpus_kind).toBe('MATH_DISPROVAL_GATE_V1_VECTORS');
    expect(c.cases.length).toBeGreaterThanOrEqual(20);
    expect(new Set(c.cases.map((entry) => entry.id)).size).toBe(c.cases.length);
  });

  test('aggregate vectors enforce proof/disproof semantics deterministically', async () => {
    for (const vector of corpus().cases.filter((entry): entry is AggregateVector => entry.class === 'AGGREGATE')) {
      const input = scenario(vector.scenario);
      const receipt = await aggregateMathVerificationV1({ claim: claim(), binding: input.bind, kernel_results: input.results });
      expect(receipt.verdict, vector.id).toBe(vector.expected_verdict);
      expect(receipt.verification_level, vector.id).toBe(vector.expected_level);
      if (vector.expected_rejected !== undefined) expect(receipt.rejected_kernel_result_hashes.length, vector.id).toBe(vector.expected_rejected);
      if (vector.expected_diagnostic !== undefined) expect(receipt.diagnostics, vector.id).toContain(vector.expected_diagnostic);
    }
  });

  test('source-audit vectors reject proof placeholders and assumption laundering', () => {
    for (const vector of corpus().cases.filter((entry): entry is SourceVector => entry.class === 'SOURCE_AUDIT')) {
      const audit = auditFormalSource(vector.source_kind, vector.source);
      expect(audit.strict_eligible, vector.id).toBe(vector.expected_strict);
      expect(audit.forbidden_tokens, vector.id).toEqual(vector.expected_forbidden);
    }
  });

  test('entire corpus replays to byte-identical aggregate receipts', async () => {
    for (const vector of corpus().cases.filter((entry): entry is AggregateVector => entry.class === 'AGGREGATE')) {
      const input = scenario(vector.scenario);
      const first = await aggregateMathVerificationV1({ claim: claim(), binding: input.bind, kernel_results: input.results });
      const secondInput = scenario(vector.scenario);
      const second = await aggregateMathVerificationV1({ claim: claim(), binding: secondInput.bind, kernel_results: secondInput.results });
      expect(JSON.stringify(second), vector.id).toBe(JSON.stringify(first));
    }
  });
});
