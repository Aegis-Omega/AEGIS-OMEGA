# AEGIS UWP-13 — Automaton-3-governed nonce issuance

**Scope:** existing DRAFT PR #766 / issue #765, research evidence only. **NOT_ADMITTED.** This patch does not add capabilities, change the central policy/registry, issue production tokens, authorize tool dispatch, or deploy a new verifier.

## Reproduced failure, exact source

The preceding `scripts/research_challenge.py` Git blob `55f426f522530ed4dd8b28d36f8900998ec4b0f0` claimed "Trusted issuer only" but `issue_challenge()` accepted caller-provided task/head/source IDs and wrote a valid challenge to an owner-only SQLite database without calling the existing constitutional authority service. In an isolated local sandbox, that exact blob **ISSUED** a nonce without any AEGIS execution identity, approval or capability decision. The repaired implementation returns `AdmissionDenied: CENTRAL_AUTHORITY_DENIED` and makes **no ledger file** in that same scenario.

## Minimum authority-preserving repair

- `issue_challenge()` now evaluates `harness.sdk.authority_client.authorize_from_environment()` **before generating a nonce or touching the ledger**. This reuses the existing Automaton-3 single authority pathway used in `agents/coordinator.py`; no parallel access-control system was created.
- The request is explicitly classified **D2 — requires approval**, `requested_capability=research.challenge.issue`, `authority_domain=research:challenge:issue`, `tool=scripts.research_challenge:issue_challenge`. Its action binds the exact task ID, Git SHA, sorted source IDs, requested TTL, and SHA-256 of the chosen ledger path. No key bytes, untrusted source text or secret path is copied into the action.
- Anything other than a typed `ADMITTED` decision with a 64-lowercase-hex `decision_root` is **DENIED**, as are exceptions/absent SDK/identity/workspace/policy. No fallback grant, implicit researcher role, or author-authored `approved=true` input is accepted.
- **No registry expansion:** `harness/policies/capability-map.v1.json` does **not** define `research.challenge.issue` at this exact head. Therefore production issuance is currently BLOCKED by design, even if the rest of the nonce protocol is locally correct. This draft is NOT a grant of D2 authority. A future operator-approved, independently reviewed central registry change and isolated control-plane deployment are required.
- Existing 22 cryptographic challenge tests use an **explicit, visible unit-test mock** of an admitted Automaton-3 decision so they still verify local nonce protocol mechanics. These mocks do NOT prove a genuine authority decision. Eight additional tests inspect the exact central adapter request, deny unknown/malformed decisions, verify D2 classification, check ledger-path scoping, and check denial **before** nonce generation and disk mutation.

## Reproduce

Python 3.13.5, stdlib only, from exact checkout:

```sh
PYTHONWARNINGS=error::ResourceWarning python3 -m unittest discover -s scripts -p 'test_research*.py' -q
python3 -m unittest discover -s scripts -p 'test_research_authority.py' -v
```

**Local observation:** `167/167 PASS`, including eight new authorization regressions. The last verified old-blob comparison and machine-readable receipt are provided in the conversation replay archive. Hosted GitHub source CI was not claimed or used to promote this patch.

## Explicit trust and nonclaims

A Python agent that runs in the same untrusted process as the authorization service, can patch its functions, set its environment, or modify the registry/ledger **cannot be excluded by these source checks**. Real operator identity, workload key custody, immutable ledger location, and issuance must be provided by an isolated trusted control plane. A locally mocked `ADMITTED` decision is only test scaffolding. Evidence still does **not** prove actual web network execution, publisher truth, or superior task outcomes; source capture remains a supplier assertion. 

Aligned with [SLSA v1.2 build control-plane isolation](https://slsa.dev/spec/v1.2/build-requirements) and [OWASP execution evidence](https://cheatsheetseries.owasp.org/cheatsheets/Verifying_Third_Party_Agent_Execution_Evidence_Cheat_Sheet.html).
