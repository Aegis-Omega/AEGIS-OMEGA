from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "docs/claims.json"
LEDGER = ROOT / "docs/CLAIMS_LEDGER.md"
VERIFIED_AT = "f514dcecabeaa7b6d55c308de6349dfcd3f36df6"

new_claims = [
    {
        "id": "CLM-221",
        "claim": "Automaton-3 binds consequential execution to a deterministic workspace root derived from the canonical GitHub remote, logical repository root, project identity, exact source commit, and operator authorization; real paths remain operator-visible metadata and repository escapes fail closed.",
        "tier": "Verified",
        "eq": "EQ-A",
        "dependencies": [],
        "evidence": [
            "Code: harness/sdk/sovereign_execution.py",
            "Test: sovereign-omega-v2/python/tests/test_automaton3.py"
        ],
        "fails_if": "A changed remote, missing root, symlink escape, nested unselected repository, path-view disagreement, missing constitutional file, or empty workspace can receive consequential authority, or host-specific absolute paths alter the deterministic workspace binding.",
        "verified_against": VERIFIED_AT
    },
    {
        "id": "CLM-222",
        "claim": "The central Automaton-3 authority evaluator assigns zero operational authority to unknown, unmapped, unobserved, under-three-run, malformed-evidence, unavailable-registry, or unavailable-authority-service requests; documentation priors do not grant runtime authority.",
        "tier": "Verified",
        "eq": "EQ-A",
        "dependencies": [],
        "evidence": [
            "Code: harness/sdk/sovereign_execution.py",
            "Test: sovereign-omega-v2/python/tests/test_automaton3.py",
            "Test: sovereign-omega-v2/python/tests/test_coordinator_authority.py"
        ],
        "fails_if": "Any listed unknown or unavailable state produces a nonzero authority score, a coordinator executes from a local documentation prior, or a consequential entry point proceeds when the central evaluator cannot be reached.",
        "verified_against": VERIFIED_AT
    },
    {
        "id": "CLM-223",
        "claim": "Automaton-3 implements a deterministic local single-writer reference model with monotone lease generations, fencing tokens, expected-parent validation, active-writer exclusion, and replay rejection.",
        "tier": "Verified",
        "eq": "EQ-A",
        "dependencies": [],
        "evidence": [
            "Code: harness/sdk/sovereign_execution.py",
            "Test: sovereign-omega-v2/python/tests/test_automaton3.py"
        ],
        "fails_if": "Two concurrent writers acquire the same authority domain, or a stale generation, stale token, wrong parent state, duplicate authoritative action, or revoked lease authorizes a write.",
        "verified_against": VERIFIED_AT
    },
    {
        "id": "CLM-224",
        "claim": "Automaton-3 implements a deterministic local durable-execution registry exposing workflow owner, source commit, workspace binding, phase, authority, transition sequence, pending external action, retry state, cancellation, lease holder, parent state, receipt root, failure state, and operator-visible lifecycle status.",
        "tier": "Verified",
        "eq": "EQ-A",
        "dependencies": [],
        "evidence": [
            "Code: harness/sdk/sovereign_execution.py",
            "Test: sovereign-omega-v2/python/tests/test_automaton3.py"
        ],
        "fails_if": "An unregistered, orphaned, completed, or cancelled workflow retains authority; heartbeat or transition sequence regresses; or a retried external action can reuse an idempotency key.",
        "verified_against": VERIFIED_AT
    },
    {
        "id": "CLM-225",
        "claim": "The Law of Silence is separated from operator visibility by an independent deterministic operator-notification ledger for authorization requests, mutation notices, security alerts, failures, cancellations, and receipts; peer-message restrictions cannot suppress this channel.",
        "tier": "Verified",
        "eq": "EQ-A",
        "dependencies": [],
        "evidence": [
            "Code: harness/sdk/operator_visibility.py",
            "Test: sovereign-omega-v2/python/tests/test_operator_visibility.py"
        ],
        "fails_if": "A notification can be marked peer-only, a broken parent or sequence is accepted, required notice kinds are unavailable, or sensitive payload redaction destroys deterministic structural verification.",
        "verified_against": VERIFIED_AT
    },
    {
        "id": "CLM-226",
        "claim": "Automaton-3 emits deterministic mutation and denial receipts bound to execution identity, workspace, policy decision, authority score, action class, tool, target, pre-state, requested action, result, post-state, parent receipt, sequence, outcome, and denial code.",
        "tier": "Verified",
        "eq": "EQ-A",
        "dependencies": [],
        "evidence": [
            "Code: harness/sdk/sovereign_execution.py",
            "Test: sovereign-omega-v2/python/tests/test_automaton3.py"
        ],
        "fails_if": "A receipt root depends on wall-clock time, host path, random ordering, or secret plaintext; a denial lacks a code; or a broken parent or sequence verifies.",
        "verified_against": VERIFIED_AT
    },
    {
        "id": "CLM-227",
        "claim": "The canonical main-branch ruleset requires both aegis / automaton-2 and aegis / automaton-3 with strict up-to-date and merge-queue-compatible evaluation.",
        "tier": "Proposed",
        "eq": "EQ-D",
        "dependencies": [],
        "evidence": ["Spec: docs/operations/BRANCH_RULESET_AUTOMATON3.md"],
        "fails_if": "Presented as configured before repository-administration evidence proves both exact contexts are required on main and merge_group."
    },
    {
        "id": "CLM-228",
        "claim": "Automaton-3 is deployed on Temporal, LangGraph, Kubernetes, or another external durable runtime.",
        "tier": "Removed",
        "eq": "EQ-D",
        "dependencies": [],
        "evidence": [],
        "removal_reason": "No repository or infrastructure evidence proves an external durable runtime deployment; this changeset provides interfaces and a deterministic local reference model only."
    },
    {
        "id": "CLM-229",
        "claim": "Automaton-3 guarantees distributed exact-once external side effects.",
        "tier": "Removed",
        "eq": "EQ-D",
        "dependencies": [],
        "evidence": [],
        "removal_reason": "The implementation enforces local idempotency-key reuse rejection and compensation requirements, but no distributed transaction or provider-level exact-once proof exists."
    },
    {
        "id": "CLM-230",
        "claim": "The aegis / automaton-3 workflow validates the exact candidate, runs the adaptive authority-abuse and operator-visibility suites, emits a deterministic candidate manifest and receipt, builds a checksummed replay package, and requests GitHub OIDC attestation.",
        "tier": "Verified",
        "eq": "EQ-A",
        "dependencies": [],
        "evidence": [
            "Code: .github/workflows/automaton-3.yml",
            "Code: scripts/validate-automaton3.py",
            "Test: sovereign-omega-v2/python/tests/test_automaton3.py",
            "Test: sovereign-omega-v2/python/tests/test_operator_visibility.py"
        ],
        "fails_if": "The stable check omits pull_request, merge_group, or main push; artifacts are not candidate-bound; replay checksums are absent; OIDC is not required; or any negative-test bypass is accepted.",
        "verified_against": VERIFIED_AT
    }
]

doc = json.loads(CLAIMS.read_text(encoding="utf-8"))
claims = doc["claims"]
existing = {item["id"] for item in claims}
ids = {item["id"] for item in new_claims}
if existing & ids:
    raise SystemExit(f"Automaton-3 claims already exist: {sorted(existing & ids)}")
claims.extend(new_claims)
CLAIMS.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

marker = "## Automaton-3 sovereign execution claims"
ledger = LEDGER.read_text(encoding="utf-8")
if marker in ledger:
    raise SystemExit("Automaton-3 ledger section already exists")
section = r'''

---

## Automaton-3 sovereign execution claims

The engineering classifications requested for this control plane map onto the ledger's
existing enforced vocabulary as follows: **VERIFIED** → `Verified`; **STRONGLY
SUPPORTED** → `Derived`; **PROPOSED** → `Proposed`; **REJECTED** and
**SUPERSEDED** → `Removed` with an explicit reason. No terminology change weakens
the machine validator.

| Claim ID | Engineering classification | Claim | Ledger status | EQ | Evidence boundary |
|----------|----------------------------|-------|---------------|----|-------------------|
| CLM-221 | VERIFIED | Consequential execution is bound to canonical repository identity, exact source state, logical workspace root, project identity, and operator authorization; path and namespace ambiguity fails closed. | Verified | A | `harness/sdk/sovereign_execution.py`; `test_automaton3.py` |
| CLM-222 | VERIFIED | Unknown, unmapped, unobserved, under-three-run, malformed, or unavailable authority receives score `0.000000`; documentation priors grant no runtime authority. | Verified | A | central evaluator plus coordinator tests |
| CLM-223 | VERIFIED | The local reference model permits one active writer per authority domain and rejects stale generations, tokens, parents, duplicates, revocations, and races. | Verified | A | writer-lease implementation and concurrency tests |
| CLM-224 | VERIFIED | The local durable registry preserves operator-visible lifecycle, authority, retry, cancellation, orphan, parent-state, and receipt state. | Verified | A | durable registry tests; no external-runtime deployment claim |
| CLM-225 | VERIFIED | Operator authorization, mutation, security, failure, cancellation, and receipt notices use an independent deterministic visibility ledger and cannot be hidden by peer-message mediation. | Verified | A | `operator_visibility.py`; `test_operator_visibility.py` |
| CLM-226 | VERIFIED | Consequential actions produce deterministic chained mutation or denial receipts with identity, workspace, policy, authority, state, action, result, and outcome bindings. | Verified | A | receipt implementation and chain-break tests |
| CLM-227 | PROPOSED / OPERATOR ACTION | `main` requires exact contexts `aegis / automaton-2` and `aegis / automaton-3`. | Proposed | D | configuration artifact exists; administration evidence does not yet exist |
| CLM-228 | REJECTED | Temporal, LangGraph, Kubernetes, or another external durable runtime is deployed by this changeset. | Removed | D | no infrastructure evidence; local reference model only |
| CLM-229 | REJECTED | Distributed exact-once external execution is guaranteed. | Removed | D | idempotency and compensation controls exist; distributed proof does not |
| CLM-230 | VERIFIED | `aegis / automaton-3` performs candidate-bound tests, deterministic manifest and receipt generation, replay packaging, checksums, and OIDC-attestation requests. | Verified | A | workflow, validator, and adversarial suites |

Operational exact-head receipt values belong in the admitted PR evidence and final merge
record. They are not copied into this static ledger until generated by the exact candidate.
'''
LEDGER.write_text(ledger.rstrip() + section + "\n", encoding="utf-8")
