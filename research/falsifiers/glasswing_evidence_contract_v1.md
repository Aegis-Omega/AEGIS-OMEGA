# GLASSWING_EVIDENCE_CONTRACT_V1 — RED specification

Status: RED / preregistered falsifier contract
Authority: EVIDENCE_ONLY

This file intentionally defines the target security-evidence contract before implementation.

## Required invariants

1. There is one canonical Glasswing result schema for security findings.
2. Legacy scanners may produce findings only through adapters into that schema.
3. Detector output is evidence-only and MUST NOT directly grant admission authority.
4. `HIGH` and `CRITICAL` findings block a clean security disposition.
5. `MEDIUM`, `LOW`, and `INFO` findings remain visible and cannot be silently dropped.
6. Scanner execution errors fail closed as `UNRESOLVED`/`ERROR`, never as clean.
7. Finding identity binds detector, rule, source digest, canonical location, and normalized vulnerability class.
8. Security reports MUST NOT persist raw secrets; matched secret material must be redacted before serialization.
9. A report binds source digest, detector/rulepack identity, and deterministic report digest.
10. Result evidence MAY be attached to ProofTrace, but `Trace != Authority` and `SecurityEvidence != AdmissionAuthority`.
11. The Artisan pre-scan is advisory/result-evidence generation only; it MUST NOT own final admission semantics.
12. Independent verification remains a separate stage and MAY include CodeQL, OSV, compiler/linter/test evidence, or other verifier-bound checks.

## Legacy divergence this slice must eliminate

Gate 204 and Gate 205 currently encode different pass/fail semantics. The consolidated contract must provide exactly one disposition function over normalized findings so that adapters cannot reinterpret severity locally.

## Target disposition

- `ERROR` if detector execution failed or coverage contract was not satisfied.
- `BLOCKED` if any normalized finding is `CRITICAL` or `HIGH`.
- `REVIEW` if there are findings but none are `CRITICAL`/`HIGH`.
- `CLEAN_WITHIN_COVERAGE` only when the scan completed and there are no findings.

`CLEAN_WITHIN_COVERAGE` is explicitly not a universal security claim.
