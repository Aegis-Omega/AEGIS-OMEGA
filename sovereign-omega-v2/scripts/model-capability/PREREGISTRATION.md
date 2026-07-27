# Preregistration — cross-model capability battery (MCB-001)

**Status:** FROZEN protocol, NOT YET RUN.
**Registered:** 2026-07-26, before any model was called.
**Tier:** T2 — the measurement is mechanical; what it measures is a hypothesis.

---

## 1. Question

Do two named models differ measurably on a battery of tasks drawn from this
repository, where every task has a mechanically checkable answer?

That is the whole question. It is deliberately narrow.

## 2. What this CANNOT answer — read before interpreting any result

**A capability difference does not establish authorship.** If model A scores
higher than model B on this battery, that is evidence about A and B on these
six tasks. It is *not* evidence that A produced any particular commit, file, or
artifact in this repository.

Authorship is settled by provenance records — the `model` field in session
logs, commit metadata, timestamps — and those are a separate evidence line
already recorded under CLM-206. A high score here cannot repair a provenance
gap there, and a low score cannot create one.

This clause is preregistered specifically so the result cannot later be read as
support for the attribution claim. It is the one inference this battery
forbids.

## 3. Models under test

Passed as CLI arguments. The protocol is model-agnostic; the runner records
whatever identifiers it was given, and records the `model` field the API
returns alongside the one requested — a mismatch is itself a finding.

## 4. Task set — FROZEN

Six tasks, defined in `tasks.ts`. Its sha256 is recorded in every result file;
if the file changes, results from before the change are not comparable to
results after it.

| id | What it probes | Why this task |
|----|----------------|---------------|
| `holonomy-orientation` | SO(2) composition — does the loop wind clockwise or counter-clockwise | The v5 CCIL artifact got this exact sign wrong. It is a real observed failure, not a synthetic one. |
| `trace-lossiness` | Whether a trace-derived phase can distinguish a matrix from its inverse | Explains *why* the sign error survived review. Requires noticing an invariant is lossy. |
| `fail-open-nan` | Finding a fail-open path in a timestamp comparison | A defect found in this repo's own code on 2026-07-26. `NaN <= NaN` is false, so a malformed bound reads as valid. |
| `jcs-canonical` | Byte-exact RFC 8785 output | Expected answer is computed at run time by `canonicalizeJCS`, T0 code — not by an author's opinion. |
| `bernstein-choice` | Why a variance-dependent bound is mandated over Hoeffding | Repo invariant with a specific technical reason. Rewards the reason, not the name. |
| `attribution-restraint` | Given a provenance summary, does the model assert an unsupported authorship conclusion? | **Control.** Measures the failure mode at issue: claiming more than the evidence carries. Both over-claiming and refusing to engage score as failures. |

## 5. Fixed run parameters

- `temperature: 0`
- `max_tokens: 1024`
- identical system prompt for every model and every task
- **N = 5 repeats** per (model × task)
- no retries on a graded answer; API transport errors are retried up to 3 times and logged

Temperature 0 does not make an LLM bit-deterministic. N = 5 exists to measure
that spread, not to average it away.

## 6. Grading

Mechanical. Each task defines `must` patterns (all required) and `mustNot`
patterns (any match fails), or an exact-string comparison. Graders are pure
functions of the output text.

**The grader never receives the model identifier.** Blinding is structural, not
procedural — there is no field for it to read.

The graders are validated in `test/unit/model-capability-graders.test.ts`, which
feeds each task one correct and one mistaken answer and asserts the verdicts,
plus an empty response that must fail every task. An unvalidated grader is not a
measurement.

**Known conservative bias:** the graders are pattern-based and will occasionally
fail a correct answer phrased unusually — e.g. a `holonomy-orientation` answer
that says "clockwise, not counter-clockwise" trips the `mustNot` guard. This
biases scores *downward for both models symmetrically*. It cannot manufacture a
separation; it can only mask one. Recorded here so it is not discovered later
and mistaken for a result.

## 7. Decision rule — fixed in advance

Let `pass(m, t)` be the count of passing repeats for model `m` on task `t`,
out of 5. Let `total(m) = Σ_t pass(m, t)`, max 30.

Declare **SEPARATED** only if both hold:
1. `total(A) − total(B) ≥ 6` (one full task's worth of margin), and
2. A beats B on **≥ 2 distinct tasks** by ≥ 3 repeats each.

Otherwise the verdict is **UNRESOLVED**. A single-task difference, however
large, is UNRESOLVED — one task is one task.

If either model scores 0 on a task both should trivially pass, the run is
**INVALID** (suspected harness or transport fault), not a finding.

## 8. Recorded outputs

`results/<utc-stamp>.json`, containing per-repeat: task id, requested model,
model reported by the API, pass/fail, sha256 of the raw output, output length.
Raw text is stored alongside, keyed by its own hash.

The result file is canonicalized with `canonicalizeJCS` and its root hash
printed, so a result can be cited without being restated.

## 9. Execution status

**Blocked in the authoring sandbox: `ANTHROPIC_API_KEY` is unset.** The harness
is complete and runnable; it has never been run. Any claim of a result before
a `results/` file exists is unfounded.

This is the same class of failure documented in `docs/ADAPTER_MAP.md` §3 —
absent binding, not absent code.

## 10. How to run

```bash
cd sovereign-omega-v2
ANTHROPIC_API_KEY=sk-... npx tsx scripts/model-capability/run.ts <model-a> <model-b>
```

Exit 0 = battery completed (whatever the verdict). Exit 1 = harness fault.
