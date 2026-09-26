# AEGIS Ω Frontier Engineering Baseline v1

**Evidence head:** `495bfd85d79abcb2b4f6898fe9c156488492426a`  
**Scope:** `Aegis-Omega/AEGIS-OMEGA` default branch and repository-source controls.  
**Authority effect:** `NONE`. This document is an engineering/security audit, not a release or authority promotion.

## Reference baseline

AEGIS uses the following external engineering standards as the minimum comparison frame:

1. NIST SSDF SP 800-218 v1.1 as the current final secure-development framework; v1.2 remains draft.
2. NIST SP 800-218A for AI-specific secure-development practices.
3. SLSA provenance principles for build integrity and verifiable supply-chain provenance.
4. OpenSSF Scorecard checks for branch protection, dependency hygiene, token permissions, pinned dependencies, and vulnerability disclosure.
5. CISA Secure by Design principles: secure defaults, least privilege, and security as a product requirement.
6. GitHub artifact attestations / Sigstore for cryptographically verifiable build provenance.

## Verified controls at the evidence head

| Control | State | Evidence |
| --- | --- | --- |
| Vulnerability disclosure policy | PASS | `SECURITY.md` |
| Ownership of critical paths | PASS | `.github/CODEOWNERS` |
| Repository-ruleset verifier | PASS in source | `scripts/check_repository_enforcement.py` |
| Dependency vulnerability scanning | PASS in source | `.github/workflows/osv-scanner.yml` |
| Exact candidate binding in governed transition | PASS | `CANDIDATE_SHA` in Automaton-2 |
| GitHub OIDC provenance permission | PASS | `id-token: write` in Automaton-2 |
| Artifact attestation | PASS | `actions/attest@v4` in Automaton-2 |
| Artifact metadata permission | PASS | `artifact-metadata: write` in Automaton-2 |
| Dependency update automation | GAP at evidence head | no `.github/dependabot.yml` |
| Immutable third-party action refs across critical workflows | PARTIAL | some workflows use mutable major/minor tags |
| OpenSSF Scorecard continuous scan | GAP | no dedicated workflow at evidence head |
| Repository-wide SBOM attestation policy | PARTIAL | attestation exists for governed artifacts; not yet a universal release SBOM policy |
| Live secret-scanning / push-protection state | UNKNOWN from source | requires GitHub admin/security state |
| Live branch/ruleset enforcement | separate verification required | source verifier exists; live API result must be bound to current head |

## Immediate hardening introduced by this change

- Add bounded weekly Dependabot updates for GitHub Actions, the main Node runtime, and the two principal Rust workspaces.
- Add an exact-candidate CI verifier for this baseline.
- Make mutable external GitHub Action refs an explicit machine-reported remediation item instead of silently treating them as secure.
- Keep authority effect at `NONE`: this CI proves source controls only.

## Next hardening wave

1. Pin all third-party GitHub Actions in critical workflows to full commit SHAs, with human-readable version comments.
2. Run OpenSSF Scorecard continuously once its action/runtime image is itself bound to an immutable trusted digest.
3. Extend release/build workflows to emit and verify SBOM attestations.
4. Bind live branch/ruleset, secret scanning, push protection, and dependency-review state into an exact-head repository-security receipt.
5. Promote the baseline check to a required rule only after one hosted successful run on its exact head.

## Fail-closed interpretation

A missing or unknown live control is **not** a pass. Source evidence and hosted-service configuration are separate evidence domains. Repository source may establish that a verifier exists; only an exact-head hosted result can establish that the hosted control executed successfully.
