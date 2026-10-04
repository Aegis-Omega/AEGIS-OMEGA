export const MATH_CLAIM_AUTHORITY = 'NON_AUTHORITATIVE_MATH_CLAIM' as const;
export const FORMALIZATION_BINDING_AUTHORITY = 'FORMALIZATION_BINDING_ONLY' as const;
export const KERNEL_RESULT_AUTHORITY = 'KERNEL_RESULT_ONLY' as const;

export type MathKernelFamilyV1 = 'COQ' | 'LEAN';
export type MathAttemptKindV1 = 'PROVE' | 'DISPROVE_NEGATION' | 'DISPROVE_COUNTEREXAMPLE';
export type KernelProcessStatusV1 = 'VERIFIED' | 'REJECTED' | 'TIMEOUT' | 'ERROR';

export interface MathClaimEnvelopeV1 {
  readonly schema_version: '1.0.0';
  readonly claim_kind: 'MATH_CLAIM_ENVELOPE_V1';
  readonly claim_id: string;
  readonly claim_text_digest: string;
  readonly claim_digest: string;
  readonly assumptions_digest: string;
  readonly notation_digest: string;
  readonly source_artifact_digests: readonly string[];
  readonly policy_commitment: string;
  readonly authority_epoch: number;
  readonly nonce: string;
  readonly authority: typeof MATH_CLAIM_AUTHORITY;
}

export interface FormalizationBindingV1 {
  readonly schema_version: '1.0.0';
  readonly binding_kind: 'FORMALIZATION_BINDING_V1';
  readonly claim_id: string;
  readonly claim_digest: string;
  readonly assumptions_digest: string;
  readonly formalization_binding_digest: string;
  readonly lean_source_sha256: string;
  readonly coq_source_sha256: string;
  readonly lean_toolchain_commitment: string;
  readonly coq_toolchain_commitment: string;
  readonly policy_commitment: string;
  readonly authority_epoch: number;
  readonly authority: typeof FORMALIZATION_BINDING_AUTHORITY;
}

export interface KernelVerificationResultV1 {
  readonly schema_version: '1.0.0';
  readonly result_kind: 'KERNEL_VERIFICATION_RESULT_V1';
  readonly kernel_family: MathKernelFamilyV1;
  readonly kernel_version: string;
  readonly formalization_sha256: string;
  readonly formalization_binding_digest: string;
  readonly claim_digest: string;
  readonly assumptions_digest: string;
  readonly attempt_kind: MathAttemptKindV1;
  readonly process_status: KernelProcessStatusV1;
  readonly proof_artifact_sha256: string | null;
  readonly counterexample_artifact_sha256: string | null;
  readonly stdout_sha256: string;
  readonly stderr_sha256: string;
  readonly started_at_ms: number;
  readonly finished_at_ms: number;
  readonly authority: typeof KERNEL_RESULT_AUTHORITY;
}

const SHA256_RE = /^[0-9a-f]{64}$/;
const SAFE_ID_RE = /^[A-Za-z0-9._:/@+\-]{1,160}$/;
const VERSION_RE = /^[A-Za-z0-9._+\-]{1,80}$/;

function record(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label}_TYPE_INVALID`);
  }
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, allowed: readonly string[], label: string): void {
  const allowedSet = new Set(allowed);
  for (const key of Object.keys(value)) {
    if (!allowedSet.has(key)) throw new Error(`${label}_UNKNOWN_FIELD:${key}`);
  }
  for (const key of allowed) {
    if (!(key in value)) throw new Error(`${label}_MISSING_FIELD:${key}`);
  }
}

function exact(value: unknown, expected: string, label: string): void {
  if (value !== expected) throw new Error(`${label}_KIND_INVALID`);
}

function text(value: unknown, label: string, max = 160): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > max) {
    throw new Error(`${label}_TEXT_INVALID`);
  }
  return value;
}

function safeId(value: unknown, label: string): string {
  const v = text(value, label);
  if (!SAFE_ID_RE.test(v)) throw new Error(`${label}_ID_INVALID`);
  return v;
}

function digest(value: unknown, label: string): string {
  if (typeof value !== 'string' || !SHA256_RE.test(value)) throw new Error(`${label}_DIGEST_INVALID`);
  return value;
}

function nonNegativeInteger(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new Error(`${label}_INTEGER_INVALID`);
  }
  return value;
}

function nullableDigest(value: unknown, label: string): string | null {
  if (value === null) return null;
  return digest(value, label);
}

const CLAIM_KEYS = [
  'schema_version', 'claim_kind', 'claim_id', 'claim_text_digest', 'claim_digest',
  'assumptions_digest', 'notation_digest', 'source_artifact_digests', 'policy_commitment',
  'authority_epoch', 'nonce', 'authority',
] as const;

export function validateMathClaimEnvelopeV1(input: unknown): MathClaimEnvelopeV1 {
  const value = record(input, 'MATH_CLAIM');
  exactKeys(value, CLAIM_KEYS, 'MATH_CLAIM');
  exact(value.schema_version, '1.0.0', 'MATH_CLAIM_SCHEMA');
  exact(value.claim_kind, 'MATH_CLAIM_ENVELOPE_V1', 'MATH_CLAIM');
  if (value.authority !== MATH_CLAIM_AUTHORITY) throw new Error('MATH_CLAIM_AUTHORITY_INVALID');

  const artifacts = value.source_artifact_digests;
  if (!Array.isArray(artifacts) || artifacts.length === 0 || artifacts.length > 128) {
    throw new Error('MATH_CLAIM_SOURCE_ARTIFACTS_INVALID');
  }
  const normalizedArtifacts = artifacts.map((entry, index) => digest(entry, `MATH_CLAIM_SOURCE_${index}`));
  if (new Set(normalizedArtifacts).size !== normalizedArtifacts.length) {
    throw new Error('MATH_CLAIM_SOURCE_ARTIFACT_DUPLICATE');
  }

  return Object.freeze({
    schema_version: '1.0.0',
    claim_kind: 'MATH_CLAIM_ENVELOPE_V1',
    claim_id: safeId(value.claim_id, 'MATH_CLAIM'),
    claim_text_digest: digest(value.claim_text_digest, 'MATH_CLAIM_TEXT'),
    claim_digest: digest(value.claim_digest, 'MATH_CLAIM'),
    assumptions_digest: digest(value.assumptions_digest, 'MATH_CLAIM_ASSUMPTIONS'),
    notation_digest: digest(value.notation_digest, 'MATH_CLAIM_NOTATION'),
    source_artifact_digests: Object.freeze(normalizedArtifacts),
    policy_commitment: digest(value.policy_commitment, 'MATH_CLAIM_POLICY'),
    authority_epoch: nonNegativeInteger(value.authority_epoch, 'MATH_CLAIM_AUTHORITY_EPOCH'),
    nonce: safeId(value.nonce, 'MATH_CLAIM_NONCE'),
    authority: MATH_CLAIM_AUTHORITY,
  });
}

const BINDING_KEYS = [
  'schema_version', 'binding_kind', 'claim_id', 'claim_digest', 'assumptions_digest',
  'formalization_binding_digest', 'lean_source_sha256', 'coq_source_sha256',
  'lean_toolchain_commitment', 'coq_toolchain_commitment', 'policy_commitment',
  'authority_epoch', 'authority',
] as const;

export function validateFormalizationBindingV1(input: unknown): FormalizationBindingV1 {
  const value = record(input, 'FORMALIZATION_BINDING');
  exactKeys(value, BINDING_KEYS, 'FORMALIZATION_BINDING');
  exact(value.schema_version, '1.0.0', 'FORMALIZATION_BINDING_SCHEMA');
  exact(value.binding_kind, 'FORMALIZATION_BINDING_V1', 'FORMALIZATION_BINDING');
  if (value.authority !== FORMALIZATION_BINDING_AUTHORITY) {
    throw new Error('FORMALIZATION_BINDING_AUTHORITY_INVALID');
  }

  return Object.freeze({
    schema_version: '1.0.0',
    binding_kind: 'FORMALIZATION_BINDING_V1',
    claim_id: safeId(value.claim_id, 'FORMALIZATION_BINDING_CLAIM'),
    claim_digest: digest(value.claim_digest, 'FORMALIZATION_BINDING_CLAIM'),
    assumptions_digest: digest(value.assumptions_digest, 'FORMALIZATION_BINDING_ASSUMPTIONS'),
    formalization_binding_digest: digest(value.formalization_binding_digest, 'FORMALIZATION_BINDING'),
    lean_source_sha256: digest(value.lean_source_sha256, 'FORMALIZATION_BINDING_LEAN_SOURCE'),
    coq_source_sha256: digest(value.coq_source_sha256, 'FORMALIZATION_BINDING_COQ_SOURCE'),
    lean_toolchain_commitment: digest(value.lean_toolchain_commitment, 'FORMALIZATION_BINDING_LEAN_TOOLCHAIN'),
    coq_toolchain_commitment: digest(value.coq_toolchain_commitment, 'FORMALIZATION_BINDING_COQ_TOOLCHAIN'),
    policy_commitment: digest(value.policy_commitment, 'FORMALIZATION_BINDING_POLICY'),
    authority_epoch: nonNegativeInteger(value.authority_epoch, 'FORMALIZATION_BINDING_AUTHORITY_EPOCH'),
    authority: FORMALIZATION_BINDING_AUTHORITY,
  });
}

const RESULT_KEYS = [
  'schema_version', 'result_kind', 'kernel_family', 'kernel_version', 'formalization_sha256',
  'formalization_binding_digest', 'claim_digest', 'assumptions_digest', 'attempt_kind',
  'process_status', 'proof_artifact_sha256', 'counterexample_artifact_sha256', 'stdout_sha256',
  'stderr_sha256', 'started_at_ms', 'finished_at_ms', 'authority',
] as const;

export function validateKernelVerificationResultV1(input: unknown): KernelVerificationResultV1 {
  const value = record(input, 'KERNEL_RESULT');
  exactKeys(value, RESULT_KEYS, 'KERNEL_RESULT');
  exact(value.schema_version, '1.0.0', 'KERNEL_RESULT_SCHEMA');
  exact(value.result_kind, 'KERNEL_VERIFICATION_RESULT_V1', 'KERNEL_RESULT');
  if (value.authority !== KERNEL_RESULT_AUTHORITY) throw new Error('KERNEL_RESULT_AUTHORITY_INVALID');

  if (value.kernel_family !== 'COQ' && value.kernel_family !== 'LEAN') {
    throw new Error('KERNEL_RESULT_KERNEL_FAMILY_INVALID');
  }
  if (value.attempt_kind !== 'PROVE' && value.attempt_kind !== 'DISPROVE_NEGATION'
      && value.attempt_kind !== 'DISPROVE_COUNTEREXAMPLE') {
    throw new Error('KERNEL_RESULT_ATTEMPT_KIND_INVALID');
  }
  if (value.process_status !== 'VERIFIED' && value.process_status !== 'REJECTED'
      && value.process_status !== 'TIMEOUT' && value.process_status !== 'ERROR') {
    throw new Error('KERNEL_RESULT_PROCESS_STATUS_INVALID');
  }

  const version = text(value.kernel_version, 'KERNEL_RESULT_VERSION', 80);
  if (!VERSION_RE.test(version)) throw new Error('KERNEL_RESULT_VERSION_INVALID');
  const started = nonNegativeInteger(value.started_at_ms, 'KERNEL_RESULT_START_TIME');
  const finished = nonNegativeInteger(value.finished_at_ms, 'KERNEL_RESULT_FINISH_TIME');
  if (finished < started) throw new Error('KERNEL_RESULT_TIME_INVALID');

  const proof = nullableDigest(value.proof_artifact_sha256, 'KERNEL_RESULT_PROOF_ARTIFACT');
  const counterexample = nullableDigest(value.counterexample_artifact_sha256, 'KERNEL_RESULT_COUNTEREXAMPLE_ARTIFACT');

  if (value.process_status !== 'VERIFIED') {
    if (proof !== null || counterexample !== null) throw new Error('KERNEL_RESULT_UNVERIFIED_ARTIFACT_INVALID');
  } else if (value.attempt_kind === 'DISPROVE_COUNTEREXAMPLE') {
    if (counterexample === null) throw new Error('KERNEL_RESULT_COUNTEREXAMPLE_ARTIFACT_REQUIRED');
    if (proof !== null) throw new Error('KERNEL_RESULT_PROOF_ARTIFACT_FORBIDDEN_FOR_COUNTEREXAMPLE');
  } else {
    if (proof === null) throw new Error('KERNEL_RESULT_PROOF_ARTIFACT_REQUIRED');
    if (counterexample !== null) throw new Error('KERNEL_RESULT_COUNTEREXAMPLE_ARTIFACT_FORBIDDEN');
  }

  return Object.freeze({
    schema_version: '1.0.0',
    result_kind: 'KERNEL_VERIFICATION_RESULT_V1',
    kernel_family: value.kernel_family,
    kernel_version: version,
    formalization_sha256: digest(value.formalization_sha256, 'KERNEL_RESULT_FORMALIZATION'),
    formalization_binding_digest: digest(value.formalization_binding_digest, 'KERNEL_RESULT_BINDING'),
    claim_digest: digest(value.claim_digest, 'KERNEL_RESULT_CLAIM'),
    assumptions_digest: digest(value.assumptions_digest, 'KERNEL_RESULT_ASSUMPTIONS'),
    attempt_kind: value.attempt_kind,
    process_status: value.process_status,
    proof_artifact_sha256: proof,
    counterexample_artifact_sha256: counterexample,
    stdout_sha256: digest(value.stdout_sha256, 'KERNEL_RESULT_STDOUT'),
    stderr_sha256: digest(value.stderr_sha256, 'KERNEL_RESULT_STDERR'),
    started_at_ms: started,
    finished_at_ms: finished,
    authority: KERNEL_RESULT_AUTHORITY,
  });
}
