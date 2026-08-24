# Skill Harness Authority Gap

**Status:** Verified repository defect; remediation candidate implemented  
**Baseline:** `main@6ae294402e4bb9b6828546359bda9a5e70ceb307`  
**Epistemic classification:** T1 — code path and static artifact inspected; negative and determinism tests reproduced

## Finding

The Phase 1 documentation harness converted human-authored documentation into positive operational competency scores.

The committed registry represented every newly declared skill with:

- positive confidence derived from its declared epistemic tier;
- `validated_runs = 0`;
- `failure_rate = 0.0`;
- `recency_score = 1.0`;
- a generation timestamp in `last_validated`.

`agents/coordinator.py` then used the registry in role routing through:

```text
confidence × recency_score × (1 − failure_rate)
```

Consequently, prose and tier labels could influence task routing before any runtime validation existed.

## Security property

```text
DeclaredCapability ≠ ObservedCompetence

OperationalAuthority(skill) = 0
when validated_runs < minimum_required_runs
```

Documentation may establish a candidate capability and its provenance. It cannot establish execution competence, failure probability, recency, or mutation authority.

## Remediation

The V2 authority layer provides:

1. `UNOBSERVED` and `OBSERVED` states;
2. authority-safe score `0.0` for unknown, malformed, or under-observed skills;
3. preservation of the prose-derived value only as `documentation_prior`;
4. deterministic canonical JSON and SHA-256 registry binding;
5. a content-bound `registry_root` used as the genesis seal;
6. exact source-commit binding;
7. fail-closed evidence-reference validation;
8. deterministic admission/denial receipts;
9. no wall-clock validation timestamp for zero-run skills or registry-root computation.

The replacement registry contains 41 declared skills. Every zero-run skill has:

```json
{
  "observation_state": "UNOBSERVED",
  "confidence": 0.0,
  "validated_runs": 0,
  "failure_rate_observed": null,
  "recency_score": 0.0,
  "last_validated": null
}
```

Registry root:

```text
191364d55420c8e88ec76cb8f516bc58872a26534df1710053352b23887e5eac
```

## Reproduction

```bash
pytest -q sovereign-omega-v2/python/tests/test_skill_authority.py
```

Expected result:

```text
8 passed
```

The suite verifies:

- documentation-only records have zero operational authority;
- fewer than three observations fail closed even with perfect supplied metrics;
- observed skills use the declared score formula only after the minimum run count;
- identical inputs produce identical registries and roots;
- registry tampering invalidates the content root;
- missing and path-escaping evidence references are denied;
- the committed registry is non-authoritative until observed.

## Falsification boundary

This finding would be refuted if the runtime demonstrated that the Phase 1 registry was never read by any routing or authority path. The inspected coordinator does read it and computes competency scores from the seeded fields, so that falsification condition is not met.

## Remaining boundary

This slice prevents the committed documentation registry from granting positive authority. The legacy coordinator still treats an entirely unmapped capability as a neutral `0.5`; replacing that fallback with a fail-closed `0.0` requires a separate coordinator refactor and dedicated routing tests.

The V2 authority module already defines the required scoring function for that follow-up.
