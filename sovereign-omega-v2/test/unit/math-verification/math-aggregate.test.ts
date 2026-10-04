import { describe, expect, test } from 'vitest';

import {
  FORMALIZATION_BINDING_AUTHORITY,
  KERNEL_RESULT_AUTHORITY,
  MATH_CLAIM_AUTHORITY,
} from '../../../src/math-verification/contracts';
import {
  MATH_RECEIPT_AUTHORITY,
  aggregateMathVerificationV1,
} from '../../../src/math-verification/aggregate';

const A = 'a'.repeat(64);
const B = 'b'.repeat(64);
const C = 'c'.repeat(64);
const D = 'd'.repeat(64);

const claim = () => ({
  schema_version: '1.0.0' as const,
  claim_kind: 'MATH_CLAIM_ENVELOPE_V1' as const,
  claim_id: 'math:claim:001',
  claim_text_digest: A,
  claim_digest: A,
  assumptions_digest: B,
  notation_digest: C,
  source_artifact_digests: [A],
  policy_commitment: D,
  authority_epoch: 7,
  nonce: 'math-nonce-001',
  authority: MATH_CLAIM_AUTHORITY,
});

const binding = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0.0' as const,
  binding_kind: 'FORMALIZATION_BINDING_V1' as const,
  claim_id: 'math:claim:001',
  claim_digest: A,
  assumptions_digest: B,
  formalization_binding_digest: C,
  lean_source_sha256: A,
  coq_source_sha256: B,
  lean_toolchain_commitment: C,
  coq_toolchain_commitment: D,
  policy_commitment: D,
  authority_epoch: 7,
  authority: FORMALIZATION_BINDING_AUTHORITY,
  ...overrides,
});

const kernel = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0.0' as const,
  result_kind: 'KERNEL_VERIFICATION_RESULT_V1' as const,
  kernel_family: 'COQ' as const,
  kernel_version: '8.20',
  formalization_sha256: B,
  formalization_binding_digest: C,
  claim_digest: A,
  assumptions_digest: B,
  attempt_kind: 'PROVE' as const,
  process_status: 'VERIFIED' as const,
  proof_artifact_sha256: D,
  counterexample_artifact_sha256: null,
  stdout_sha256: A,
  stderr_sha256: A,
  started_at_ms: 1_000,
  finished_at_ms: 1_001,
  authority: KERNEL_RESULT_AUTHORITY,
  ...overrides,
});

const aggregate = (results: unknown[], bind = binding()) => aggregateMathVerificationV1({
  claim: claim(),
  binding: bind,
  kernel_results: results,
});

describe('MATH_DISPROVAL_GATE_V1 deterministic aggregation', () => {
  test('verified proof yields PROVED/SINGLE_KERNEL and evidence-only receipt', async () => {
    const receipt = await aggregate([kernel()]);
    expect(receipt.verdict).toBe('PROVED');
    expect(receipt.verification_level).toBe('SINGLE_KERNEL');
    expect(receipt.authority).toBe(MATH_RECEIPT_AUTHORITY);
    expect(receipt.accepted_kernel_result_hashes).toHaveLength(1);
    expect(receipt.rejected_kernel_result_hashes).toEqual([]);
    expect(receipt.proof_artifact_hashes).toEqual([D]);
    expect(receipt.counterexample_artifact_hashes).toEqual([]);
  });

  test('verified proof of formal negation yields DISPROVED and never relies on proof-search failure', async () => {
    const receipt = await aggregate([kernel({ attempt_kind: 'DISPROVE_NEGATION' })]);
    expect(receipt.verdict).toBe('DISPROVED');
    expect(receipt.verification_level).toBe('SINGLE_KERNEL');
  });

  test('verified formal counterexample yields DISPROVED', async () => {
    const receipt = await aggregate([kernel({
      attempt_kind: 'DISPROVE_COUNTEREXAMPLE',
      proof_artifact_sha256: null,
      counterexample_artifact_sha256: D,
    })]);
    expect(receipt.verdict).toBe('DISPROVED');
    expect(receipt.counterexample_artifact_hashes).toEqual([D]);
  });

  test.each(['TIMEOUT', 'ERROR', 'REJECTED'] as const)('%s is UNRESOLVED, never DISPROVED', async (status) => {
    const receipt = await aggregate([kernel({
      process_status: status,
      proof_artifact_sha256: null,
    })]);
    expect(receipt.verdict).toBe('UNRESOLVED');
    expect(receipt.accepted_kernel_result_hashes).toHaveLength(1);
  });

  test('proof and disproof under one exact binding fail closed as kernel inconsistency', async () => {
    const receipt = await aggregate([
      kernel({ proof_artifact_sha256: A }),
      kernel({ attempt_kind: 'DISPROVE_NEGATION', proof_artifact_sha256: B, stdout_sha256: C }),
    ]);
    expect(receipt.verdict).toBe('UNRESOLVED');
    expect(receipt.diagnostics).toContain('KERNEL_INCONSISTENCY_DETECTED');
  });

  test('same-binding Lean and Coq proof results promote verifier diversity to CROSS_KERNEL', async () => {
    const receipt = await aggregate([
      kernel(),
      kernel({ kernel_family: 'LEAN', kernel_version: '4.32.0', formalization_sha256: A, stdout_sha256: B }),
    ]);
    expect(receipt.verdict).toBe('PROVED');
    expect(receipt.verification_level).toBe('CROSS_KERNEL');
  });

  test('same-binding Lean and Coq disproof results yield DISPROVED/CROSS_KERNEL', async () => {
    const receipt = await aggregate([
      kernel({ attempt_kind: 'DISPROVE_NEGATION' }),
      kernel({
        kernel_family: 'LEAN', kernel_version: '4.32.0', formalization_sha256: A,
        attempt_kind: 'DISPROVE_NEGATION', stdout_sha256: B,
      }),
    ]);
    expect(receipt.verdict).toBe('DISPROVED');
    expect(receipt.verification_level).toBe('CROSS_KERNEL');
  });

  test('mismatched claim, assumptions, binding, policy, epoch or family source is rejected from truth evidence', async () => {
    const badBinding = binding({ policy_commitment: A });
    const badPolicyReceipt = await aggregate([kernel()], badBinding);
    expect(badPolicyReceipt.verdict).toBe('UNRESOLVED');
    expect(badPolicyReceipt.rejected_kernel_result_hashes).toHaveLength(1);

    for (const bad of [
      kernel({ claim_digest: D }),
      kernel({ assumptions_digest: D }),
      kernel({ formalization_binding_digest: D }),
      kernel({ formalization_sha256: D }),
    ]) {
      const receipt = await aggregate([bad]);
      expect(receipt.verdict).toBe('UNRESOLVED');
      expect(receipt.rejected_kernel_result_hashes).toHaveLength(1);
    }
  });

  test('different formalization binding cannot acquire CROSS_KERNEL status', async () => {
    const receipt = await aggregate([
      kernel(),
      kernel({
        kernel_family: 'LEAN', kernel_version: '4.32.0', formalization_sha256: A,
        formalization_binding_digest: D,
      }),
    ]);
    expect(receipt.verdict).toBe('PROVED');
    expect(receipt.verification_level).toBe('SINGLE_KERNEL');
    expect(receipt.rejected_kernel_result_hashes).toHaveLength(1);
  });

  test('invalid receipt/authority injection in a kernel payload is rejected, not promoted', async () => {
    const receipt = await aggregate([{ ...kernel(), decision_receipt: { verdict: 'PERMIT' } }]);
    expect(receipt.verdict).toBe('UNRESOLVED');
    expect(receipt.accepted_kernel_result_hashes).toEqual([]);
    expect(receipt.rejected_kernel_result_hashes).toHaveLength(1);
  });

  test('receipt hash and ordered evidence arrays are deterministic across replay and input ordering', async () => {
    const coq = kernel();
    const lean = kernel({ kernel_family: 'LEAN', kernel_version: '4.32.0', formalization_sha256: A, stdout_sha256: B });
    const first = await aggregate([coq, lean]);
    const second = await aggregate([lean, coq]);
    expect(second).toEqual(first);
    expect(first.receipt_hash).toMatch(/^[0-9a-f]{64}$/);
  });
});
