# AEGIS Ω Labs: Epistemic Gravity Engine v0.1

**Tracking:** #791. **Organizational North Star / authoritative goal scorecard:** #734.  
**Candidate branch:** existing PR #569 `feat/sovereign-provider-mesh-v1`.  
**Authority effect:** NONE. **Evidence verification:** NOT PERFORMED. **Execution:** NOT PERFORMED.

## Why this exists

#753 already specifies typed provenance/memory, #771 validates exact-head evidence freshness, and #773 governs agent permission. This module does not replace or dilute them. Instead it estimates **which proposed verification checks could unlock the most *potential* downstream knowledge** under an explicit budget. It is an optimization over untrusted input metadata, not a prover or verification engine.

## Interface

- `heads`: current source version pin per source identifier.
- `evidence`: Boolean flags **supplied by the caller**, with version pin and source. These flags are not independently authenticated by this module.
- `claims`: each has a positive declared value and alternative nonempty AND-dependency sets. Any fully supported path is sufficient for model-level support, never mathematical proof.
- `probes`: each can hypothetically acquire one evidence token and has a strictly positive integer *relative* cost. No real currency is spent or quotas reserved.
- `budget`: integer planning budget; zero causes no proposal.
- `minimal_proof_debt`: cheapest candidate probe set to hypothetically satisfy each currently unsupported modeled claim.
- `source_snapshot_digest`: SHA-256 of canonical input. A source head change changes both the plan digest and downstream model-level support.
- `blocked_probes`: stale-source probe IDs mapped to `STALE_SOURCE_BINDING`; blocked checks never enter counterfactual unlocked claims. Renew the input snapshot with independently established current source-head evidence before planning again.

The optimizer exactly enumerates a maximum of 16 probes, chooses the budget-feasible subset maximizing newly supported **declared** claim value, with smaller cost and lexicographic tie-breaking. This finite, explicit bound prevents pretending the algorithm scales unboundedly.

## Reproduce offline

From the existing repository root on the branch:

```sh
python3 -m unittest discover -s agents/tests -p 'test_epistemic_gravity.py' -v
python3 agents/epistemic_gravity.py agents/examples/epistemic_gravity.sample.json
```

Demonstration fixture is synthetic. Expected proposed probes: `kernel_replay` and `ui_benchmark`; hypothetical unlocked value: 50 units, cost: 5 units; **zero actual verified proof outcomes**. No Lean theorem is claimed.

## Bounded baseline comparison (synthetic)

`agents/examples/epistemic_gravity.greedy_trap.json` is a 3-probe, 2-claim complementarity case: cost budget 6, myopic one-probe-gain baseline returns declared value 7 (solo probe), exact subset optimizer returns declared value 11 (two joint probes, cost 6), a 4-unit / 57.1% improvement **for that one synthetic case only**. No actual real-world improvement or new verified fact is claimed. The same scenario is a regression test. The optimization cost is abstract and is not charged money.

## Local receipt

2026-10-31: 22/22 stdlib `unittest` regressions PASS in an offline container for exact source content: `agents/epistemic_gravity.py` Git blob `949391ba00bbecb3af773e89c9bb6070ff387b75`, tests Git blob `44f0dc794ed7d5cd4d707c0c60c78b1cbbfbc52f`. Source hashes were independently compared with GitHub blob readback. These local results do **not** imply hosted CI PASS.

Tests include: competing proof alternatives, multi-hop dependencies, exact minimum debt, budget insufficiency, stale-head revocation propagation, **rejection of stale-source counterfactual probes**, explicit source rebind requirements, input immutability, deterministic receipts, invalid/empty/non-string dependency rejection, missing sources, dependency cycles, noninteger costs, and bounded search.

## Explicit security boundary

- Does not execute agent actions, model calls, network requests or provider selection.
- Never treats its proposed plan as authorization to run a check or dispatch an agent.
- The word "verified" in the fixture is a caller-supplied flag; the optimizer does not verify identities, signatures, kernel proof terms, external claims or statuses.
- All returned conclusions are labeled as hypothetical and `authority_effect=NONE`.
- Never substitute for the existing admission gates, signed policies, independently authenticated evidence, or operator consent.
- No deployment, approval, billing change, secret read or protected-main mutation is made by this candidate.

## Remaining gates

1. Independently replay exact branch-head file bytes and adversarial tests on hosted CI (current status UNKNOWN).
2. Replace synthetic evidence with appropriately authenticated output from the existing typed evidence adapters (#753/#771), after review.
3. Compare greedy and no-planner baselines on real cross-domain tasks under the same fixed cost budget (#757).
4. Assess complexity and resource limits and ensure a 16-probe cap is adequate for bounded tasks; shard larger problems without silently discarding important dependencies.
5. Route all proposed actions through the existing trusted authority chain; never let this module act as a grant.

**Status:** LOCAL_VERIFIED / REPOSITORY_CANDIDATE / CI_UNKNOWN / NOT_ADMITTED.
