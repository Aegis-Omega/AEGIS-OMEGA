---
name: AEGIS agent work contract
about: Bounded, evidence-driven work item for any model or discipline
labels: [task]
---

## Context and existing work
Link any overlapping Issue or PR before claiming. Run the existing PR #732 context preflight first. UNKNOWN is not an empty board.

## Acceptance contract
Edit the JSON, not just the prose. An exact check name must specify the trusted GitHub Actions publisher integration ID 15368.

<!-- AEGIS_WORK_V1
{
  "schema": "aegis.issue-work.v1",
  "objective": "Replace this with a specific, measurable objective",
  "kind": "code",
  "authority": "branch_only",
  "risk": "moderate",
  "scope": ["path/to/change/**"],
  "forbidden": ["Production writes", "Secrets changes", "Claims without independent evidence"],
  "acceptance": [
    {
      "id": "A1",
      "criterion": "Replace with an observable success criterion",
      "method": "github_check",
      "check": "aegis / issue-gate-tests",
      "app_id": 15368
    }
  ]
}
-->

## Execution and counterexamples
State the baseline, exact repository/ref, smallest change, specific negative test, and rollback path. A domain_evidence criterion intentionally remains blocked until independently verified by a domain-specific adapter.

## Deliverable and claim ledger
Record artifacts as OBSERVED, TESTED, INDEPENDENTLY_VERIFIED, UNVERIFIED or BLOCKED, with immutable identifiers. Opening a PR is not delivery.

## Review and admission
Link PR using exact line AEGIS-WORK-ISSUE: #NUMBER. Model labels do not establish identity. No auto-merge, prod changes, billing or policy expansion.
