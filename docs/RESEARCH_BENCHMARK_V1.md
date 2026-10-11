# AEGIS Research Scout — Paired Structural Preflight Evaluation V1

**Issues:** #765 (research) and #757 (universal evaluation) · **PR:** #766 (DRAFT, NOT_ADMITTED).

This is a *component regression benchmark*, NOT an AGI test, a human-calibrated task-success study, a proof of external publisher authenticity or evidence that AEGIS beats LangGraph, Claude Code or any frontier agent.

## Test design

- **Synthetic, public development set:** 100 examples = 20 mutation families × 5 deterministic repetitions. Five positive and 15 negative mutation families: 25 structurally ready / 75 invalid or incomplete. Positive cases now contain HMAC receipts created by a publicly known synthetic test key; these are not authenticated web captures.
- **Predeclared structural labels:** a legitimate candidate has at least two fresh, distinct-issuer, distinct-byte capture receipts with valid MACs under separately configured trusted keys and a falsifiable metric. This is only enough to **start an independently verified experiment**. Source text may still be false or injected.
- **Three actual scorers:** (a) intentionally naive two-URL baseline; (b) genuine original AEGIS scout module pinned to exact Git blob `595cd180aa4c1e8c73f7dd73d2496350923aeb81` and `git show`; (c) updated AEGIS scout with manual-note abstention.
- **Mutation families:** single/same-publisher/stale/future/source mirror/manual notes, tampered bytes, malformed schema, bad acceptance definition, unknown/duplicate reference, unknown-issuer GitHub mirrors, plus five positive structural mixtures.
- **Metrics:** explicit TP/FP/TN/FN, false-ready rate among 75 negative samples, acceptance recall among 25 positive samples, per-mutation-family decisions, SHA-256 result digest.
- **No holdout and no independent human labels.** Repeated cases are dependent; any Wilson intervals included in the JSON are **descriptive only** and do not license population-level statistical claims.
- All fixtures are locally generated; there are **no genuine website captures**, provider costs, LLM responses, end-user task outcomes or measured effects from the proposed improvements.

## Observed results (Python 3.13.5; local exact-code replay 2026-10-11)

| Scorer | TP / 25 | FP / 75 | TN / 75 | FN / 25 |
|---|---:|---:|---:|---:|
| Naive two-URL baseline | 25 | 75 | 0 | 0 |
| **Previous AEGIS source blob** | 25 | **10** | 65 | 0 |
| **Updated AEGIS source** | 25 | **0** | 75 | 0 |

**Observed improvement:** 10 fewer incorrect `READY_FOR_INDEPENDENT_TEST` classifications relative to the actual previous source blob, confined to the 10 duplicated examples for `two_manual_notes` and `one_manual_note`. The newer HMAC gate additionally blocks unverified `connector_capture` flags; synthetic cases are signed by a public test key, not a real protected collector. This is a fixed-policy bug repair on a synthetic test family, **not** a statistically generalizable 13.33-percentage-point improvement in AI research.

The latest native Python unittest coverage is **110/110 PASS** at the local exact-source bytes. Commit-specific source/code hashes and the full 100-case machine JSON receipt are in the portable conversation replay bundle. Repo-hosted CI verification and independently attested inputs remain open.

## Execute independently

```bash
# From repository checkout at the exact head of draft PR #766:
python3 -m unittest discover -s scripts -p 'test_research*.py' -q

# Reconstruct prior version from the literal pinned ancestor, and ensure
# the Python benchmark independently verifies its Git blob SHA:
git show c1e54b7dea2faeb4a552ed3c3268d9f2442ff61b:scripts/research_intelligence.py > /tmp/aegis-previous-scout.py
python3 scripts/research_benchmark.py --legacy-source /tmp/aegis-previous-scout.py > /tmp/aegis-research-benchmark.json
```

Check `actual_prior_source_blob`, `actual_prior_false_ready_reduction`, the confusion matrices, and `receipt_sha256`. Any comparator not exactly matching the pinned old source is rejected as `LEGACY_BLOB_MISMATCH`.

## Remaining critical unknowns

1. A `connector_capture` string is caller-supplied but no longer sufficient for readiness: a local verified HMAC is now required. The public deterministic test key `bytes(range(32))` is NOT deployable. Holder-of-key integrity does not prove publisher truth or isolated honest runner execution; root-of-trust configuration remains unverified.
2. Semantic relevance of cited content to a proposed change is not machine checked. Research and review must falsify the actual claim, not just check the URL count.
3. External source captures and full end-user task quality are not measured. Future #757 must use **real representative tasks**, independent hidden holdouts, standardized tools/budgets, blind grading, safety abstentions and matched baselines.
4. GitHub Actions for this branch historically returned zero-step failures; CI must be independently executed against the current exact commit. No bypass of signed-commit/protected-main or human authorization.

### Evaluation methodology references

- NIST AI measurement: https://www.nist.gov/ai-measurement-and-evaluation
- NIST RMF Measure: https://airc.nist.gov/airmf-resources/playbook/measure/
- OpenAI (2026-02-23): https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/ explains benchmark leakage, false negatives and why public repeated evaluation data cannot establish frontier capability.
