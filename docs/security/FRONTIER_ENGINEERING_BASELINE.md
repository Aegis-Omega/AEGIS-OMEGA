# AEGIS Ω Frontier Engineering Baseline v1

**Base evidence head:** 495bfd85d79abcb2b4f6898fe9c156488492426a  
**Working PR:** #685 (hardening/frontier-engineering-baseline-v1)  
**Scope:** Aegis-Omega/AEGIS-OMEGA repository-source controls.  
**Authority effect:** NONE. This document is an engineering/security audit, not a release or authority promotion.

## Reference baseline

AEGIS uses the following external engineering standards as the minimum comparison frame:

1. NIST SSDF SP 800-218 v1.1 and NIST SP 800-218A for AI-specific secure-development practices.
2. SLSA provenance principles for build integrity and verifiable supply-chain provenance.
3. OpenSSF Scorecard for branch protection, dependency hygiene, token permissions, pinned dependencies, and vulnerability disclosure.
4. CISA Secure by Design principles: secure defaults, least privilege, and security as a product requirement.
5. GitHub artifact attestations / Sigstore for cryptographically verifiable provenance and SBOM attestations.

## Source controls on the PR

| Control | State | Evidence |
| --- | --- | --- |
| Vulnerability disclosure policy | PASS in source | SECURITY.md |
| Ownership of critical paths | PASS in source | .github/CODEOWNERS |
| Repository-ruleset verifier | PASS in source | scripts/check_repository_enforcement.py |
| Dependency vulnerability scanning | PASS in source | .github/workflows/osv-scanner.yml |
| Dependency update automation | PASS in source | .github/dependabot.yml |
| Immutable third-party action refs across critical workflows | PASS in source when V3 verifier passes | scripts/verify-frontier-engineering-baseline.py |
| Exact candidate binding in governed transition | PASS in source | CANDIDATE_SHA in Automaton-2 |
| GitHub OIDC provenance permission | PASS in source | id-token: write in Automaton-2 |
| Artifact attestation | PASS in source | pinned actions/attest in Automaton-2 |
| OpenSSF Scorecard continuous scan | PASS in source | .github/workflows/scorecard.yml |
| Scorecard authenticated publication | PASS in source | publish_results: true + job-scoped id-token: write |
| Scorecard SARIF → code scanning | PASS in source | pinned github/codeql-action/upload-sarif |
| Repository-wide release SBOM attestation | OPEN | release artifacts still need an explicit SBOM production/verification contract |
| Live secret-scanning / push-protection state | UNKNOWN from source | requires hosted GitHub security-state evidence |
| Live branch/ruleset enforcement | separate verification required | source verifier exists; live API result must be rebound to current exact head |
| Multi-host durable execution | OPEN | Automaton-3 local registry is still a reference implementation |

## Hardening implemented in this PR

- Bounded Dependabot updates for GitHub Actions, Node, and principal Rust workspaces.
- Immutable full-SHA third-party Action refs in critical workflows.
- Exact-candidate frontier baseline receipt with fail-closed enforcement.
- Continuous OpenSSF Scorecard on default-branch pushes and weekly schedule, using current pinned upstream workflow components.
- Authenticated Scorecard result publication via OIDC and SARIF upload to GitHub code scanning.
- Source verifier V3 treats missing/incomplete Scorecard controls as a hard failure.

## Next hardening wave

1. Add release/build SBOM generation and GitHub SBOM attestation only where there is a real distributable artifact, then verify it before consumption/deploy.
2. Bind live repository rulesets, secret scanning, push protection, and dependency-review state into an exact-head repository-security receipt.
3. Add policy-bound agent tracing/evaluation projection over existing EventEnvelope / receipt chains, with deterministic redaction and no hidden authority.
4. Replace the local durable-execution reference registry with a transactional multi-host backend preserving CAS, fencing, idempotency, cancellation, and receipt-root semantics.
5. Promote any new check to required status only after a successful hosted run is bound to the exact candidate.

## Fail-closed interpretation

A missing or unknown live control is not a pass. Source evidence and hosted-service configuration are separate evidence domains. A source verifier can establish that a control is configured and immutable; only a hosted exact-head result can establish that the control actually executed.
