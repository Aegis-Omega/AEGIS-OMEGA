import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, test } from 'vitest';

import {
  FORMALIZATION_BINDING_AUTHORITY,
  KERNEL_RESULT_AUTHORITY,
  MATH_CLAIM_AUTHORITY,
  validateFormalizationBindingV1,
  validateKernelVerificationResultV1,
  validateMathClaimEnvelopeV1,
} from '../../../src/math-verification/contracts';
import { auditFormalSource } from '../../../src/math-verification/source-audit';

const H = 'a'.repeat(64);
const B = 'b'.repeat(64);

const claim = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0.0',
  claim_kind: 'MATH_CLAIM_ENVELOPE_V1',
  claim_id: 'math:claim:001',
  claim_text_digest: H,
  claim_digest: H,
  assumptions_digest: H,
  notation_digest: H,
  source_artifact_digests: [H],
  policy_commitment: H,
  authority_epoch: 7,
  nonce: 'math-nonce-001',
  authority: MATH_CLAIM_AUTHORITY,
  ...overrides,
});

const binding = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0.0',
  binding_kind: 'FORMALIZATION_BINDING_V1',
  claim_id: 'math:claim:001',
  claim_digest: H,
  assumptions_digest: H,
  formalization_binding_digest: H,
  lean_source_sha256: H,
  coq_source_sha256: B,
  lean_toolchain_commitment: H,
  coq_toolchain_commitment: B,
  policy_commitment: H,
  authority_epoch: 7,
  authority: FORMALIZATION_BINDING_AUTHORITY,
  ...overrides,
});

const result = (overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0.0',
  result_kind: 'KERNEL_VERIFICATION_RESULT_V1',
  kernel_family: 'COQ',
  kernel_version: '8.20',
  formalization_sha256: B,
  formalization_binding_digest: H,
  claim_digest: H,
  assumptions_digest: H,
  attempt_kind: 'PROVE',
  process_status: 'VERIFIED',
  proof_artifact_sha256: B,
  counterexample_artifact_sha256: null,
  stdout_sha256: H,
  stderr_sha256: H,
  started_at_ms: 1_000,
  finished_at_ms: 1_001,
  authority: KERNEL_RESULT_AUTHORITY,
  ...overrides,
});

describe('MATH_DISPROVAL_GATE_V1 contracts', () => {
  test('accepts exact nominal claim, binding and kernel result surfaces', () => {
    expect(validateMathClaimEnvelopeV1(claim()).claim_kind).toBe('MATH_CLAIM_ENVELOPE_V1');
    expect(validateFormalizationBindingV1(binding()).binding_kind).toBe('FORMALIZATION_BINDING_V1');
    expect(validateKernelVerificationResultV1(result()).result_kind).toBe('KERNEL_VERIFICATION_RESULT_V1');
  });

  test('rejects unknown-field and authority injection fail closed', () => {
    expect(() => validateMathClaimEnvelopeV1(claim({ execute: true }))).toThrow(/UNKNOWN_FIELD/);
    expect(() => validateFormalizationBindingV1(binding({ decision_receipt: {} }))).toThrow(/UNKNOWN_FIELD/);
    expect(() => validateKernelVerificationResultV1(result({ effect_receipt: {} }))).toThrow(/UNKNOWN_FIELD/);
    expect(() => validateKernelVerificationResultV1(result({ authority: 'PERMIT' }))).toThrow(/AUTHORITY/);
  });

  test('rejects malformed digests, discriminators and time reversal', () => {
    expect(() => validateMathClaimEnvelopeV1(claim({ claim_digest: 'abc' }))).toThrow(/DIGEST/);
    expect(() => validateFormalizationBindingV1(binding({ binding_kind: 'GENERIC' }))).toThrow(/KIND/);
    expect(() => validateKernelVerificationResultV1(result({ kernel_family: 'MODEL' }))).toThrow(/KERNEL_FAMILY/);
    expect(() => validateKernelVerificationResultV1(result({ finished_at_ms: 999 }))).toThrow(/TIME/);
  });

  test('verified proof result requires a proof artifact and cannot smuggle counterexample evidence', () => {
    expect(() => validateKernelVerificationResultV1(result({ proof_artifact_sha256: null }))).toThrow(/PROOF_ARTIFACT/);
    expect(() => validateKernelVerificationResultV1(result({ counterexample_artifact_sha256: H }))).toThrow(/COUNTEREXAMPLE/);
  });

  test('verified formal counterexample requires its dedicated artifact', () => {
    const counterexample = result({
      attempt_kind: 'DISPROVE_COUNTEREXAMPLE',
      proof_artifact_sha256: null,
      counterexample_artifact_sha256: H,
    });
    expect(validateKernelVerificationResultV1(counterexample).attempt_kind).toBe('DISPROVE_COUNTEREXAMPLE');
    expect(() => validateKernelVerificationResultV1({ ...counterexample, counterexample_artifact_sha256: null }))
      .toThrow(/COUNTEREXAMPLE_ARTIFACT/);
  });

  test('non-verified process state cannot carry truth-producing artifacts', () => {
    expect(() => validateKernelVerificationResultV1(result({ process_status: 'TIMEOUT' }))).toThrow(/UNVERIFIED_ARTIFACT/);
    expect(validateKernelVerificationResultV1(result({
      process_status: 'TIMEOUT',
      proof_artifact_sha256: null,
    })).process_status).toBe('TIMEOUT');
  });
});

describe('formal source audit over existing AEGIS proof substrate', () => {
  const root = path.resolve(process.cwd(), 'formal', 'theories');

  test('current completed Coq proofs are strict-proof eligible', () => {
    for (const relative of ['Core/LockIrreversibility.v', 'Core/LatticeConvergence.v']) {
      const source = readFileSync(path.join(root, relative), 'utf8');
      const audit = auditFormalSource('COQ', source);
      expect(audit.strict_eligible).toBe(true);
      expect(audit.forbidden_tokens).toEqual([]);
    }
  });

  test('current ThreeWay Coq bisimulation scaffold is not strict-proof eligible because it contains an Axiom and Parameters', () => {
    const source = readFileSync(path.join(root, 'Bisimulation/ThreeWay.v'), 'utf8');
    const audit = auditFormalSource('COQ', source);
    expect(audit.strict_eligible).toBe(false);
    expect(audit.forbidden_tokens).toContain('Axiom');
    expect(audit.forbidden_tokens).toContain('Parameter');
  });

  test('current Hash Coq source is assumption-bearing because sha256 is a Parameter', () => {
    const source = readFileSync(path.join(root, 'Core/Hash.v'), 'utf8');
    const audit = auditFormalSource('COQ', source);
    expect(audit.strict_eligible).toBe(false);
    expect(audit.forbidden_tokens).toEqual(['Parameter']);
  });

  test('Coq Axiom/Parameter/Admitted/admit and Lean sorry/admit are rejected while ordinary theorem text is accepted', () => {
    expect(auditFormalSource('COQ', 'Theorem t : True. Proof. exact I. Qed.').strict_eligible).toBe(true);
    expect(auditFormalSource('COQ', 'Axiom x : False.').strict_eligible).toBe(false);
    expect(auditFormalSource('COQ', 'Parameter x : nat.').strict_eligible).toBe(false);
    expect(auditFormalSource('COQ', 'Theorem t : True. Admitted.').strict_eligible).toBe(false);
    expect(auditFormalSource('COQ', 'Theorem t : True. admit.').strict_eligible).toBe(false);
    expect(auditFormalSource('LEAN', 'theorem t : True := by trivial').strict_eligible).toBe(true);
    expect(auditFormalSource('LEAN', 'theorem t : True := by sorry').strict_eligible).toBe(false);
    expect(auditFormalSource('LEAN', 'theorem t : True := by admit').strict_eligible).toBe(false);
  });
});
