# AEGIS Ω — shared operational handoff for all models

**As observed 2026-10-11.** This is a read-only, **advisory** coordination view on draft PR #732, not a live daemon, agent notification, signer, release attestation, approval, or a change to protected `main`.

## Read these existing sources, in order

1. Run `python3 scripts/agent_context.py --json "#ISSUE task summary"`. Inspect **all** blockers, missing sources, open issues, PR heads and their base branches. If preflight cannot fetch a trustworthy state, report HOLD/UNKNOWN.
2. Inspect [the dated machine snapshot](AEGIS_AGENT_SHARED_STATE_20261011.json) **only as a locator**. Run the existing `scripts/agent_context.py --json "#ISSUE task"` which now includes a **read-only `shared_state` SHA comparison** when the primary GitHub PR board and main are fresh. If it says `STALE_HEAD`, `OPEN_PR_NOT_IN_SNAPSHOT_BOARD`, or `HOLD_SHARED_STATE_UNVERIFIED`, inspect GitHub live metadata rather than trusting the snapshot. **An unchanged PR SHA does not imply unchanged merge/draft/review state.** Re-fetch every referenced PR's current head, merge state, source blobs, CI jobs and executed steps before relying on a claim. The snapshot was captured *before the commits that install these files*; its #732 head is deliberately historical.
3. Consult `ASSETS.md`, `REPO_MAP.md`, `INDEX.md`, and `sovereign-omega-v2/ARTIFACT_REGISTRY.md`; confirm statements against actual code/runtime. These historic documents do not supersede measurements.
4. Locate archived evidence via Library `/AEGIS Research Archive/00_INDEX/AEGIS_RESEARCH_LIBRARY_INDEX.md`, `AEGIS_Resource_Locator_2026-10-10.json`, and `AEGIS_Archive_File_Index_2026-10-10.jsonl.gz`.
5. Consult staged artifacts at Library `/AEGIS/Artifact Registry/2026-10-11/`, specifically `06_Portfolio_Operations/AEGIS_Library_Implementation_Crosswalk_V3_2026-10-11.csv`. A partial Library inventory is **not** an exhaustive project inventory.
6. Use the existing Issue board (including #734 coordination, #735 Actions billing lock, #737 PR queue) and contribute on the **existing lane/PR**. Do not create another coordination framework.

## Truthful per-component state machine

`HISTORICAL_SOURCE` → `LOCAL_VERIFIED_CANDIDATE` → `BRANCH_SOURCE_EXACT_HEAD` → `HOSTED_CHECKS_EXECUTED` → `ADMITTED_TO_PROTECTED_MAIN` → `DEPLOYMENT_OBSERVED`.

These are evidence categories, **not automatic progression**. A component may skip or lack any category, and must carry `UNKNOWN` when the required evidence was not inspected. A SHA match proves byte identity only. A test receipt does not authenticate the author. A CI conclusion of failure **without steps or logs** is not proof of a source defect. A signed Git commit plus passing CI is not by itself a production deployment. Formal mathematical results require actual kernel-checked closure and explicit axiom scope.

## Current handoff priorities

- **Cross-model coordinator:** existing #732 on draft. Its PR body can lag the current branch; use GitHub heads, not prose.
- **Work/evidence paths:** #761 WorkPack, #747 evidence gate, #762 work compiler, #766 research scout, #767 Circle/Codex preflight — distinct responsibilities, no presumed integration.
- **Product:** #745 Holon Glass has branch code. Standalone Library demos (Sovereign Workbench v21, Research Fabric v8, Holon Glass v1/v2) must be tracked independently from React/runtime deployment. Verify licenses for copied image assets.
- **M2:** #764 remains stacked on #720; do not silently promote to main.
- **Formal RH:** `tarikskalic33/formal-conjectures` #79 was **merged** on 2026-10-11 at merge commit `e9dd3abf717dc0f844f460b66b3a01c602fc8b43` (PR head `f9b1fbc7817ff2556b5131cf1455e05acc00743a`). This is a merge of conditional proof-fusion work, **not** closure of RH or permission to weaken the official target. The PR body retains historic draft wording; the live GitHub merge metadata wins.
- **Cross-PR conflicts:** #724↔#727 on `.github/workflows/integration-ledger.yml`; #724↔#730 on `vertex/serve.py`; #727↔#730 on `agents/coordinator.py` and `sovereign-mesh/nodes/auditor/evaluator.py`. Recheck at current heads.
- **External execution blocker:** #735 records a GitHub Actions billing lock; require executed steps to classify source or test errors. No payment changes authorized here.

## New exact-head regression (candidate on PR #732)

`scripts/shared_state_audit.py` now compares stored SHA-40 PR identity to `agent_context.py`'s existing full fresh GitHub PR list, without a new network transport. It returns `OTHER_REPOSITORY_NOT_CHECKED` for formal-conjectures and any other repo outside the primary source; separate repository checks are required. This is **an advisory warning**, not an authenticated global lock and not a replacement for actual review of protected-main state.

`python3 -m unittest discover -s scripts -p 'test_shared_state_audit.py' -v`

The 15 negative/positive test cases were executed locally from exact-byte-matched files; GitHub-hosted full-suite/CI is not established while jobs start with no executed steps. Do not promote until required independent verification.

## Before declaring a task complete

Record exact repo and PR/Issue, current 40-character head and parent/base, touched paths/blob hashes, negative control/falsifier, executed test and CI evidence, admission/merge status, observed deployment endpoint (or `UNKNOWN`), any shared-file overlap, and one next responsible work item. Reuse `scripts/holon_contract.py`, `scripts/holon_gate.py` and the #743 receipt lane as applicable; do not grant authority from a coordination JSON file.

**Safety:** no auto-merge, branch deletion, release, payment, signer change, secret/credential mutation, permission expansion, or proof promotion. Operator approval plus existing protected-main and external approval gates remain required.
