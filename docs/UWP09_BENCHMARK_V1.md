# UWP-09 benchmark manifest v1 (fixture-only)

This is a small, offline manifest validator for reproducible heterogeneous task
definitions. It does **not** execute agents, judge outputs, authenticate
reviewers, compute quality scores, or grant authority. The committed Slack
plain-text case is a candidate security/accessibility fixture from the issue
discussion; this manifest marks it `NOT_RUN`. The baseline/candidate test
description concerns mocked transport and is not a real Slack-client,
provider, accessibility, or end-user result.

## Replay

```bash
python3 scripts/uwp_benchmark_manifest.py \
  --input scripts/examples/uwp09_fixture_NOT_RUN.json
python3 -m unittest discover -s scripts -p 'test_uwp_benchmark_manifest.py' -v
```

The validator checks the UTF-8 task-text digest, task IDs, the required five
comparison arms, explicit abstention truth, a declared or explicitly unknown
budget, all 13 quality axes, and complete metadata fields for any listed
standard. `MEASURED` axes
require a method, evidence digest, and reviewer reference. These fields remain
self-reported; a digest proves byte integrity, not truth or reviewer identity.
`UNKNOWN` is a valid recorded state, not evidence that a check passed.
Standards are scope references only, not conformance or certification claims;
the WCAG anchor in the fixture remains unverified and its applicability is
unknown.

## Composition and measurement limits

The manifest is deliberately not a second paired-outcome scorer. Same-task
outcomes should be recorded with the existing `holon_eval.py` receipt, and
source/frontier evidence with `frontier_review.py`; the 13-axis contract is
`experience_eval.py`. Those implementations are currently on draft PR #732
and are not in this branch's base. Do not copy their scoring code here or treat
their pending integration as available runtime behavior. This manifest keeps
the expected comparison arms and task denominator visible while that
dependency remains open.

The Slack baseline/candidate/test blob IDs in the fixture are references
reported in the #757 discussion, marked `REPORTED_NOT_REVERIFIED`; they are not
commit identities and no source or test replay is claimed here.

For a real run, bind the exact task bytes and arm revisions, preregister equal
resource limits, retain every attempted case including crashes and abstentions,
and store outputs as source-bound receipts. Do not turn a missing run, a
synthetic case, a public fixture, or an unverified self-report into PASS.
The generated preflight receipt reports `population_denominator` separately
from `executed_denominator`; unrun outcome metrics and confidence intervals are
null. There is no withheld set in this patch, so `hidden_holdout` remains
`NOT_PROVIDED`.

This is a fixture/contract contribution only: it does not meet the ≥10 genuine
pilot tasks or ≥100 public tasks plus independent withheld evaluation
acceptance. No cross-agent comparison, crash-recovery rate, real cost/latency,
manual-intervention count, independent reproduction, or external frontier
ranking is established. `WORLD_BEST=UNESTABLISHED`; authority effect is `NONE`.
