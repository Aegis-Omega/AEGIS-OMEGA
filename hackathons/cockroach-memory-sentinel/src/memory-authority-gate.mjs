export const MemoryVerdict = Object.freeze({ ALLOW: 'ALLOW', DENY: 'DENY' });

const REQUIRED_STRING_FIELDS = Object.freeze([
  'requestId',
  'actionDigest',
  'observedStateDigest',
  'admittedStateDigest',
  'observedPolicyDigest',
  'admittedPolicyDigest',
]);

export function evaluateMemoryAuthority(input) {
  const reasons = [];

  if (!input || REQUIRED_STRING_FIELDS.some((field) => typeof input[field] !== 'string' || input[field].length === 0)
      || !Number.isSafeInteger(input.observedAuthorityEpoch)
      || !Number.isSafeInteger(input.admittedAuthorityEpoch)) {
    reasons.push('INCOMPLETE_MEMORY_BINDING');
    return Object.freeze({ verdict: MemoryVerdict.DENY, reasons: Object.freeze(reasons) });
  }

  if (input.observedStateDigest !== input.admittedStateDigest) reasons.push('STALE_STATE');
  if (input.observedPolicyDigest !== input.admittedPolicyDigest) reasons.push('STALE_POLICY');
  if (input.observedAuthorityEpoch !== input.admittedAuthorityEpoch) reasons.push('STALE_AUTHORITY_EPOCH');
  if (input.priorReceiptActionDigest === input.actionDigest) reasons.push('ACTION_REPLAY');

  return Object.freeze({
    verdict: reasons.length === 0 ? MemoryVerdict.ALLOW : MemoryVerdict.DENY,
    reasons: Object.freeze(reasons),
  });
}
