# AEGIS Ω — Cloud KMS Ed25519 ExecutionEnvelope Signing v1

**Status:** SOURCE CONTRACT / LIVE KMS EVIDENCE PENDING  
**Authority effect:** NONE  
**Default runtime behavior:** unchanged (`signature = null` unless explicitly attached).

## Objective

Bind an existing Phase-1 `ExecutionEnvelope.envelope_hash` to a verified
client-principal identity using an exact Google Cloud KMS CryptoKeyVersion.

This is the implementation boundary for CLM-203. It is not yet a production
signature claim.

## Current Cloud KMS contract

The implementation follows the current Google Cloud KMS v1 contract:

- `EC_SIGN_ED25519` is EdDSA / PureEdDSA and signs **raw data**, not a
  pre-hashed digest.
- `cryptoKeyVersions.asymmetricSign` accepts `data` and `dataCrc32c`.
- the response exposes `name`, `verifiedDataCrc32c`,
  `signatureCrc32c`, and `protectionLevel`.
- callers must verify that the response key-version name is the exact intended
  CryptoKeyVersion and verify the request/response CRC32C integrity fields.

Reference:
- https://cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign
- https://cloud.google.com/kms/docs/algorithms
- https://cloud.google.com/kms/docs/data-integrity-guidelines

## Signed statement

The KMS operation signs canonical raw bytes of:

```json
{
  "client_principal": {
    "issuer": "<verified identity issuer>",
    "kind": "<identity class>",
    "subject": "<verified subject>"
  },
  "domain": "AEGIS_EXECUTION_ENVELOPE_SIGNATURE_V1",
  "envelope_hash": "<64 lowercase hex>",
  "schema_version": "1.0.0"
}
```

The statement uses the same float-free canonical JSON primitive as the
ExecutionEnvelope producer. The KMS request uses:

```json
{
  "data": "<base64(canonical statement bytes)>",
  "dataCrc32c": "<CRC-32C decimal integer>"
}
```

It must never substitute a `digest` field for `EC_SIGN_ED25519`.

## Signature record

A successful source-contract call returns metadata shaped as:

```json
{
  "schema_version": "1.0.0",
  "scheme": "GCP_KMS_EC_SIGN_ED25519_V1",
  "algorithm": "EC_SIGN_ED25519",
  "key_version": "projects/.../cryptoKeyVersions/N",
  "client_principal": {
    "issuer": "...",
    "kind": "...",
    "subject": "..."
  },
  "statement_sha256": "<sha256>",
  "statement_crc32c": 0,
  "signature_b64": "...",
  "signature_crc32c": 0,
  "verified_data_crc32c": true,
  "protection_level": "SOFTWARE"
}
```

The exact `protection_level` is recorded from KMS rather than inferred.

## Fail-closed conditions

The signer rejects:

1. malformed or non-exact CryptoKeyVersion resource names;
2. algorithms other than `EC_SIGN_ED25519`;
3. tampered Phase-1 envelope hashes;
4. an already-signed envelope;
5. ambiguous/non-canonical client-principal strings;
6. KMS response key-version mismatch;
7. `verifiedDataCrc32c != true`;
8. malformed or non-64-byte Ed25519 signatures;
9. signature CRC32C mismatch;
10. missing protection-level metadata;
11. transport failure.

Transport failures are not blindly retried by this primitive. Retry authority
belongs to the caller's governed execution/idempotency policy.

## Deliberate boundaries

This source slice does **not**:

- create or rotate a KMS key;
- grant `cloudkms.cryptoKeyVersions.useToSign`;
- mint credentials or OAuth tokens;
- call production KMS by itself;
- prove that a configured KMS key actually uses `EC_SIGN_ED25519`;
- retrieve or verify a KMS public key;
- cryptographically verify the returned signature;
- alter the default `EnvelopeChain.emit()` path;
- update the public transparency log.

Therefore CLM-203 must remain non-Verified until a live exact-key-version sign
operation is independently verified with the matching public key and bound to
an exact source head.

## Promotion evidence required

Minimum promotion package:

1. exact source commit and exact CryptoKeyVersion resource name;
2. key metadata proving `algorithm = EC_SIGN_ED25519` and enabled state;
3. live `asymmetricSign` response with:
   - exact `name`,
   - `verifiedDataCrc32c = true`,
   - matching `signatureCrc32c`;
4. independently fetched public key with its integrity metadata checked;
5. independent Ed25519 verification of the exact canonical statement bytes;
6. client principal derived from a trusted authentication boundary, not user
   input;
7. signed evidence receipt binding all of the above;
8. no authority expansion from signature validity alone.
