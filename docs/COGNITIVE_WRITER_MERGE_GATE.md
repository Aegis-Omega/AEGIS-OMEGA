# Cognitive writer merge gate

The `aegis / cognitive-writer-merge` job in the existing trusted cognitive
workflow checks the resulting PR merge commit, not the feature branch snapshot.
It requires exact 40-character commit IDs and the ordered parents `[base, head]`.
A stale base, wrong head, non-merge candidate or unavailable object fails closed.

The approved policy is the exact gated dispatch writer from
`0b656256813a23f07a280ca0e1f8358bb4eb9979`:

```text
.github/workflows/cognitive-manifest-refresh.yml
SHA-256 99f4c39ad780a77511347f7ac039557f428a0983f990f3304953dd2f636dd356
```

The resulting file must be a regular, non-executable Git blob (`100644`) with
those exact bytes. Missing files, symlinks, old auto-writers, read-only replacements
and other changes are rejected. An intentional policy update requires reviewing
the new workflow and updating the trusted evaluator's pin. The candidate cannot
supply its own approved digest. This is exact-byte preservation, not a general
YAML security analyzer or an exhaustive scan for other writers.

The evaluator reads Git objects with replacement objects disabled and never
executes candidate scripts. The JSON result binds the base, head, merge, tree,
writer blob, SHA-256 and evaluator SHA-256. It is a check record, not a digital
signature or a general admission receipt.

```bash
python scripts/test-cognitive-writer-merge-gate.py
python /trusted/source/scripts/check-cognitive-writer-merge.py \
  --repo /candidate/repository \
  --base-sha FULL_BASE_SHA --head-sha FULL_HEAD_SHA --merge-sha FULL_MERGE_SHA
```

Tests construct real old-base/main/feature histories. An unchanged old writer
on a feature head passes when Git preserves the hardened writer in the merge.
Explicitly restoring the old writer in the resolved merge fails. Tests also
cover deletion, symlinks, stale parent bindings, missing objects and `git replace`.

## CI and enforcement scope

The existing workflow remains read-only. A separate job checks GitHub's exact
`pull_request` merge SHA and its event base/head bindings; the candidate checkout
is data only. The evaluator follows the existing workflow-source checkout pattern.
Independent trust requires the workflow source to be controlled through required
workflow rules or an equivalent protected source. An ordinary candidate-controlled
workflow is not self-enforcing merely because it contains this job.

This change does not activate rulesets or update the existing external workflow
source pin. Hosted execution and required-check enforcement need separate evidence
after integration. Merge conflicts prevent normal PR execution/merging and must
be resolved before this check can pass. This gate is scoped to two-parent PR
merges; it does not claim merge-queue, squash-commit or branch-local execution
coverage. The existing broader single-writer tests remain in place.

## Local verification

Implemented on the isolated branch `fix/cognitive-writer-merge-gate-v1`, based on
local main `6eb2ac201bbe60ebaa9cebad714b8696683772e8`.
Six real-Git merge-gate tests and thirteen existing writer/authority tests pass.
The actual workflow shell was also executed against a valid merge and a wrong-head
case: exit 0/PASS and exit 1/DENIED respectively, with the expected JSON records.
Gate 1–8 passed: 4,130 runtime tests passed, 68 skipped; typecheck and production
build passed. Frozen Python file hashes remain unchanged. These counts belong to
this base and are separate from the earlier Coq candidate's verification results.
Hosted CI and live merge enforcement have not been exercised by this local run.
