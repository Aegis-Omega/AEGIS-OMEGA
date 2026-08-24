# ADR 0001 — The Execution Envelope Contains No Binary Floats

## Status

Accepted (2026-07-11) — Provenance Phase 1.

## Context

Provenance Phase 1 introduces a signed execution envelope emitted by the Python
bridge (`sovereign-omega-v2/python/canonical_envelope.py`) whose digests must be
independently recomputable from the TypeScript T0 path
(`sovereign-omega-v2/src/core/canonicalize.ts`, RFC 8785 JCS → SHA-256).

Floating-point serialization is the weak point of any cross-language digest
contract:

- `verifiable/chain.py`'s `canon()` — the Python canonicalization source of
  truth — rejects floats by design ("float in hashed state is forbidden").
- RFC 8785 mandates ES2020 shortest-round-trip number formatting; matching it
  bit-for-bit from Python, Rust, and future signers is a known cross-language
  hazard. Floating-point canonicalization is already listed among this repo's
  open hard problems.
- A float-free envelope makes cross-language digest equality trivially
  achievable: only strings, integers, booleans, null, arrays, and objects are
  ever canonicalized, and all of those have one unambiguous JCS encoding.

## Decision

1. The hashed envelope body (`canon_version`, `seq`, `prev_hash`,
   `request_digest`, `response_digest`, `model_id`, `tier`, `provider`)
   contains **no binary floating-point values**, and no wall-clock timestamps
   (sequence numbers only, per the repo determinism invariant).
2. Quantities with defined precision are carried as **scaled integers** —
   e.g. confidence in basis points (`confidence_bp: 6180`), latency in
   microseconds (`latency_us: 42000`).
3. Arbitrary-precision or display-only values are carried as **decimal
   strings** — e.g. `"0.6180339887"`.
4. **Digest transform rule:** request/response payloads that may legitimately
   contain floats (model outputs, projections) are digested as
   `sha256(canon(encode_floats(payload)))`. `encode_floats()` recursively
   replaces every float with its shortest round-trip decimal string via
   Python `repr()`. No type tag is attached: the transform is a fixed,
   documented precondition of the digest, applied to every digest input.
5. `canon()` continues to **reject raw floats** — a payload that reaches it
   without the transform fails loudly rather than hashing non-deterministically.

## Consequences

- Cross-language digest equality is enforced mechanically by a shared vector
  file (`sovereign-omega-v2/test/vectors/canon-vectors.json`) asserted from
  both vitest and Python in CI; no vector may contain a raw float.
- `encode_floats` is not injective (`1.0` → `"1.0"` collides with the literal
  string `"1.0"`). This is acceptable for Phase 1: the transform certifies
  what was processed, not the payload's type structure. Consumers needing
  type-faithful payloads use the untransformed payload plus this rule.
- Phase 2 (KMS Ed25519 signatures) signs `envelope_hash` and inherits the
  float-free guarantee unchanged.
- Producers must convert measured quantities at the boundary (basis points,
  microseconds) instead of passing floats through — a small, deliberate tax.
