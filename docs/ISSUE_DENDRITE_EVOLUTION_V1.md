# AEGIS Ω — Issue-wide Dendritic Evolution v1

This is **one overlay over the existing 37 open Issues**, not 37 cloned agents,
not a new orchestrator, and not a replacement for #734 / #758 / #757 /
#753 / #754 / #746 / #727.

## Verified GitHub inventory (12 October 2026)

A read-only GitHub REST inventory returned 281 open repository issue entries
on three pages: 37 actual open Issues and 244 Pull Requests.
The exact 37 Issue representations (including bodies, titles, labels and
updated_at) are frozen for *offline regression only* in:

`examples/issue_evolution_snapshot_20261012.json`.

That snapshot is **historical** and *not* proof of current state in a later
run. `EXPLICIT_OFFLINE_FIXTURE` intentionally means the offline compiler
does not authenticate its GitHub origin. The optional `--live-repo` CLI
performs explicit read-only paginated GitHub API collection and refuses
incomplete pagination. No automatic polling, commenting or modifications.

## Existing issue contracts -> dendrite edges

`agents/issue_evolution.py` maps every open Issue to a typed,
content-hashed evolution contract, without needing a new agent registry.
Explicit relationship types are `depends_on`, `parent` and `related`.
Unresolved references (including references to PRs or closed Issues) are
listed as unresolved instead of creating fictional issue nodes. The
dependency subset is cycle-checked, while related/parent links may be cyclic.
This is not an AI-generated semantic relationship graph: only literal
issue references are extracted.

Every issue receives a distinct `AEGIS_ISSUE_EVOLUTION_CONTRACT_V1`:
- Preregistered frozen baseline and candidate improvement hypothesis.
- At least **30 paired holdout evaluations** before a candidate can be
  considered for further independent verification.
- Exact one-sided sign test, threshold p <= 0.01 and ZERO safety regressions.
- Mandatory rollback pointer; preserve failures and losses as lessons.
- Scope includes algorithms, task decomposition, tool ordering, scientific
  methods, UX, cost, code and workflow improvements.
- **No self-reported outcome may promote a skill.** The reducer never writes
  `agents/adaptive_lineage.json`, the skill tree, tool permissions, PR
  status or `main`. Even a perfect synthetic result only yields
  `NEEDS_INDEPENDENT_VERIFICATION`, never `ADMITTED`.

The issue-to-dendrite bridge sends a short **informational** topic-specific
summary into the *existing* `agents/dendrite_system.py` 19-node network.
It never treats issue body/markdown as an executable prompt. Issues marked
`needs-operator` remain QUARANTINED for informational forwarding.
Batch size is bounded at 32; separate slices can cover all 37.

## Commands — local offline first

From the candidate checkout of AEGIS PR #773:

```sh
# 1. The captured 37-issue board. NOT current-state evidence.
python3 -m agents.issue_evolution graph \
  --snapshot examples/issue_evolution_snapshot_20261012.json \
  > /tmp/aegis_issue_evolution_graph.json

# 2. Diffuse first 32 issues as inert per-role packets; then remainder 5.
python3 -m agents.issue_evolution graph \
  --snapshot examples/issue_evolution_snapshot_20261012.json \
  --source-head "$(git rev-parse HEAD)" --start 0 --limit 32 \
  > /tmp/aegis_issue_dendrites_1.json
python3 -m agents.issue_evolution graph \
  --snapshot examples/issue_evolution_snapshot_20261012.json \
  --source-head "$(git rev-parse HEAD)" --start 32 --limit 32 \
  > /tmp/aegis_issue_dendrites_2.json

# 3. CURRENT board (only if GitHub API access is explicitly available).
# Set read-only GITHUB_TOKEN if needed; no permissions escalation.
python3 -m agents.issue_evolution graph \
  --live-repo Aegis-Omega/AEGIS-OMEGA \
  > /tmp/aegis_issue_evolution_live.json

# 4. Simulated trial screens an implementation candidate; NOT admission.
python3 -m agents.issue_evolution evaluate \
  --trial examples/issue_evolution_trial_SYNTHETIC.json
```

The synthesized holdout fixture deliberately uses dummy Git SHAs
(`aaaaaaaa...` / `bbbbbbbb...`) and manufactured scores.
It MUST NOT enter historical competence metrics or be described as a
demonstrated optimization. The issue graph's node evolution contracts are
**capabilities to plan and evaluate**, not realized autonomous evolution.

## Connections with existing work — no duplicate engines

| Existing issue/PR | Evolution connection | Hard boundary |
| --- | --- | --- |
| #734 / PR #732 | orient/claim/board and agent attribution | do not replace work protocol |
| #758 | canonical self-improvement acceptance and falsifiers | no self-reported promotion |
| #757 | benchmark harness, frozen baseline, holdout | no invented frontier result |
| #753 / PR #729 | negative/contradictory memory and source lineage | source rights/access |
| #754 / PR #730 | actual competence-ranked routing after authorization | authority stays central |
| #755 | independent adversarial verification | author cannot self-approve |
| #746 / PR #747 | exact-head delivery and signed PR admission | no auto-merge |
| #765 / PR #766 | source-bound scout and negative discoveries | citation is not proof |
| #727 | foundry counterexample/repair evolution | reuse counterexamples |
| #749 / #750 | work-contract DAG and resumable execution | graph does not execute |
| #751 / #752 | typed evidence and least-privilege | all real external effects gated |
| #760 | operator workbench | graph is machine-readable input |
| #773 / formal-conjectures PR #82 | dendrites and Lean source ingress | no RH conclusion |

## Current verification boundary

The Python candidate's 34 falsifier tests are committed to
`agents/tests/test_issue_evolution.py` and referenced by the **existing**
Python CI job. Local synthetic/test-file presence and deterministic JavaScript
independent issue-reference inventory checks must not be promoted to
a Python-native source PASS without actual execution at the exact GitHub SHA.
If Actions is blocked before jobs start, report `NO_HOSTED_TEST_VERDICT`.

This is stage 1: **issue-wide capability and candidate-evaluation contracts**.
Stage 2 requires real programmatic candidate generation and real, independent
execution/evaluation receipts from #757/#746. Stage 3 requires source-bound
negative-result memory, durable archive and separately approved promotion
through existing governance. No production self-modifying agent is claimed.
