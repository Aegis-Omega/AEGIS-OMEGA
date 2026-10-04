# AEGIS Ω Offline ExecutionEnvelope Verifier v1

**Status:** EXTERNAL_HOSTED_REPLAY_VERIFIED  
**Authority effect:** NONE  
**Dependencies:** Python standard library only.

## Purpose

This verifier gives an independent, offline consumer a way to check a Phase-1
`ExecutionEnvelope` or a genesis-relative envelope chain without trusting the
runtime module that emitted it.

The CLI is intentionally implemented separately from
`sovereign-omega-v2/python/canonical_envelope.py`. It independently recomputes
the float-free canonical JSON bytes and SHA-256 envelope hashes.

## CLI

```bash
python scripts/aegis-envelope-verify.py envelope envelope.json
python scripts/aegis-envelope-verify.py --json envelope envelope.json \
  --expected-seq 7 \
  --expected-prev-hash <sha256> \
  --expected-envelope-hash <sha256>

python scripts/aegis-envelope-verify.py chain chain.json
python scripts/aegis-envelope-verify.py --json chain chain.json \
  --expected-terminal-hash <sha256>
```

Exit status:

- `0` — integrity/linkage verification passed;
- `2` — malformed input, hash mismatch, sequence/link break, unsupported signature,
  or expected-root mismatch.

## Verified scope

A valid result establishes only:

- exact Phase-1 field set;
- `canon_version == JCS-1`;
- float-free / finite JSON state;
- SHA-256 shape for all digest fields;
- independent recomputation of `envelope_hash`;
- optional caller-supplied envelope anchors;
- for a chain: genesis root, sequence `0..N-1`, `prev_hash` linkage, terminal hash;
- deterministic chain descriptor hash.

The machine-readable result uses:

```json
{
  "status": "VALID",
  "verification_scope": "INTEGRITY_AND_LINKAGE_ONLY",
  "signature_verified": false,
  "client_principal_verified": false,
  "transparency_log_verified": false,
  "provider_execution_verified": false,
  "model_execution_verified": false
}
```

## Deliberate fail-closed boundary

A non-null `signature` is rejected with
`SIGNATURE_VERIFICATION_UNSUPPORTED`.

That is deliberate. CLM-203 (KMS Ed25519 signing + client-principal binding) is
still a separate open claim. This CLI will not accept a signature merely because
a string is present.

Likewise, this verifier does not claim CLM-204 transparency-log verification,
provider/model execution authenticity, or production admission.

## Falsifiers

The verifier is invalid if any of these can occur without a non-zero exit:

1. a body field changes while the old `envelope_hash` remains accepted;
2. a middle envelope is rehashed but the following `prev_hash` is stale;
3. a sequence number is skipped/reordered;
4. an extra or missing field is silently ignored;
5. raw float / NaN / Infinity enters hashed state;
6. a non-null signature is accepted without a cryptographic trust root;
7. a caller-provided expected hash or terminal root can disagree without failure;
8. the CLI imports the producer's `canonical_envelope` implementation.

## Promotion boundary

Exact-source hosted replay completed on GitLab SaaS shared runner 54907241:
pipeline 2910487369, job 16919605169, Python 3.12.15. The replay verified the
three-file exact scope, 12/12 offline-verifier tests, 45/45 canonical-envelope
checks, and machine-readable CLI output. Evidence receipt SHA-256:
`202ab871ffb6d75956ff698d4e63938fcf1dd73256642864280a8d7d3840c1fd`.

This evidence supports the bounded CLM-205 integrity/linkage claim. KMS signing
(CLM-203) and public transparency (CLM-204) remain independently open and are
not promoted by this verifier.
