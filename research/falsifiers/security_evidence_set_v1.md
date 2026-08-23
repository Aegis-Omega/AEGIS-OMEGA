# SECURITY_EVIDENCE_SET_V1 — RED specification

Status: RED / preregistered falsifier contract
Authority: EVIDENCE_ONLY

Purpose: normalize digest-bound outputs from security detectors/checkers without turning detector success, set integrity, or trace attachment into admission authority.

## Required invariants

1. A `SecurityEvidenceSetV1` contains only normalized digest references, not raw scanner payloads or findings.
2. Every member binds evidence kind, producer identity, subject digest, evidence digest, disposition, authority class, independence class, and metadata digest.
3. Member identity is deterministic and domain-separated.
4. Set identity is deterministic, domain-separated, and order-independent over members and required evidence kinds.
5. The set itself and every accepted member are `EVIDENCE_ONLY`.
6. A member claiming `ADMISSION_AUTHORITY`, `EFFECT_EVIDENCE`, or another non-evidence authority invalidates integrity verification.
7. Offline verification re-derives member IDs, completeness, aggregate disposition, and set digest from serialized data without invoking any detector or model.
8. Integrity validity and security disposition are separate. A structurally valid set may still be `BLOCKED`.
9. Missing required evidence kinds produce `complete=false` and aggregate `ERROR`; they are never treated as clean.
10. Aggregate precedence is fail-closed: `ERROR` > `BLOCKED` > `REVIEW` > `CLEAN_WITHIN_COVERAGE`.
11. A Glasswing report is referenced by its `report_digest`; raw findings and matched secret material are not copied into the aggregate set.
12. This contract does not grant admission, effect, execution, deployment, merge, or world-state mutation authority.

## Intended evidence kinds

The schema is producer-neutral. Initial evidence kinds include `GLASSWING`, `OSV`, `CODEQL`, `COMPILER`, `LINTER`, and `TEST`, but consumers may require any explicit set of kinds. Presence is not inferred from tool names or workflow labels.

## ProofTrace boundary

A future stacked bridge may attach only the verified `set_digest` plus non-sensitive type metadata to a ProofTrace evidence artifact. `SecurityEvidenceSet != ProofTrace != AdmissionAuthority`.

ProofTrace is intentionally not copied into this PR because its canonical implementation currently lives on the separate DRAFT lineage `trace/proof-trace-sdk-v1`.
