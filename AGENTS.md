# AEGIS Ω — Agent Operational Directive (AMPS-v1)

Applies to every autonomous agent or tool that edits this repository. The
regime is fail-closed and evidence-first. Machine form: `.agent-contract.json`.
Enforcement: `scripts/agent_governance_lint.py` (CI: `agent-calibration.yml`).

## 1. Reasoning loop, before any code, proof, or push

1. DECOMPOSE — isolate the minimal unit; separate intrinsic identity from relational pairing.
2. MODEL — state constraints, types, working directory, and runtime dependencies explicitly.
3. PREMORTEM — name the three most lethal failure modes: type mismatch, authority escalation, vacuous truth.
4. VERIFY — compile; run the repo's own gate; confirm `Closed under the global context`; confirm discovery parity with the compiler's `.glob` witness (`sovereign-omega-v2/scripts/coq_theorem_discovery.py`).
5. EVIDENCE OVER NARRATIVE — the running system outranks every document. An identifier that is not in the code does not exist.

Authority order when sources disagree: live behaviour > code on the executed path > passing tests and CI logs > `HANDOFF.md` > `REPO_MAP.md` > `CLAUDE.md` > older docs.

## 2. Authority tiers

| tier | examples | admission authority |
|---|---|---|
| T0_FORMAL | Coq theorem closed under the global context, `coq_attestation.py` receipt | yes |
| T0_STRUCTURAL | generated inventory (`coq_inventory.py --check`), acyclic dependency graph | yes |
| T1_BOUNDED_FALSIFICATION | interval bounds, finite-grid fixtures; a failure QUARANTINES | yes |
| T1_DIAGNOSTIC | local Qiskit/Grover fault localisation | none — may mark a failure, never grant admission |
| OPEN | unproven analytic bridges (Weil prime–zero duality) | none — never PASS, default UNKNOWN |

Admission requires every mandatory gate (P1_COQ_KERNEL, P2_EXACT_HEAD,
P3_DEPENDENCY_GRAPH, P4_ARITHMETIC_BOUND) to return PASS. Any FAIL →
QUARANTINED. Any UNKNOWN, UNAVAILABLE, or absent mandatory gate → UNKNOWN.
Information may amplify; authority may not.

## 3. Output protocol

Prohibited: preambles, apologies, progress narration, pseudo-code, mock
implementations, skipped or quarantined tests, empty commits to re-trigger CI,
`admit.`/`Admitted.`, `TODO`, tautological assertions, literal booleans
asserted against themselves.

Mandatory: direct diffs, fully proven lemmas, fail-closed tests, exact commit
SHAs and run ids, RED before GREEN, a receipt derived from tool output.

## 4. Commands

```
sovereign-omega-v2:  python3 scripts/coq_inventory.py --check
                     python3 scripts/coq_theorem_discovery.py formal/theories/<file>.v
                     node scripts/verify-hashes.mjs
clients/python:      python3 -m pytest tests/test_quantum_tourbillon.py -v
repo root:           python3 scripts/agent_governance_lint.py
```

Canonical status, never to be overstated: QuantumTourbillon =
ARCHITECTURAL_HYPOTHESIS · QUANTUM_PHYSICAL_ADVANTAGE = NOT_ESTABLISHED ·
RH = NOT_PROVEN · UCR = PROTO_RESONANT (hypothesis, not machine-established).
