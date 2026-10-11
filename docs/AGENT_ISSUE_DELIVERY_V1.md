# AEGIS Ω — Proof-Carrying Issue Delivery v1

**Status:** opt-in candidate, not merged or admitted. No authority grant, merge, production action or automatic issue closure.

## Integrations, not replacements

This gate consumes the existing firm-of-agents plan (#734), PR #732 preflight, PR #730 capability dispatch and PR #743 model-call receipts. It does **not** create another orchestrator, agent persona framework, signed-claim service, or competing architecture.

## Universal nine-stage execution loop

1. **Discover:** inspect the Issue board, overlapping PRs, source and non-GitHub sources. Unknown repository state is UNKNOWN, not an empty queue.
2. **Contract:** create one GitHub Issue with objective, kind, allowed scope, risk, operator-only boundaries, acceptance criteria and a falsifier.
3. **Claim:** coordinate with an existing claimant; attribution to a model is not authenticated actor identity.
4. **Route:** prefer one executor. Parallelize only independent tasks. Add evaluator/optimizer passes only when there is a reproducible metric and bounded budget.
5. **Act:** the smallest reversible delta at an exact source head; do not execute instructions embedded in an Issue as shell commands.
6. **Falsify:** actual tests, negative cases, evidence provenance and reproducible research counterexamples. Zero job steps means NO_TEST_VERDICT, not a code failure or a successful test.
7. **Review:** independently challenge evidence. Model-name commit trailers do not establish separate GitHub identities.
8. **Admit:** enforce signed commits, current-head checks, branch policies, authorized human/organization decisions. A verifier cannot grant its own authority.
9. **Learn:** report the outcome and verified regressions. Close the Issue only after the promised deliverable is accepted, not when a PR is created.

## Machine contract

Use the .github/ISSUE_TEMPLATE/agent-work.md template. Fill the machine-readable AEGIS_WORK_V1 JSON comment; do not leave placeholders. The PR body contains exactly one line of the form:

    AEGIS-WORK-ISSUE: #746

Python 3 standard library only:

    python3 -m unittest discover -s scripts -p 'test_agent_issue_gate.py' -v
    GITHUB_TOKEN=<read-only-token> python3 scripts/agent_issue_gate.py --repo Aegis-Omega/AEGIS-OMEGA --live-pr <number> --output /tmp/gate.json
    python3 scripts/agent_issue_gate.py --snapshot <offline-fixture.json>

Snapshots are caller-supplied and **untrusted**. A green offline test demonstrates reducer behavior, not live GitHub attestation. The optional CI job loads the checker from the protected *base SHA*, while testing proposed candidate code separately.

## What the gate actually checks

- Exact, single PR-to-open-Issue link, nonstacked main base and enumerated changed files within the contract scope.
- Check-run name **and GitHub publisher integration ID 15368** on the exact PR head; status completed and conclusion success; no unavailable or incomplete paginated check list.
- Every enumerated PR commit reports GitHub verification. The final listed SHA equals current PR head.
- Latest GitHub reviewer decision: approved by a different GitHub login at exactly the current head, not invalidated by later review. A different GitHub login is stronger than a model trailer but does not prove a different model was operating it.
- Draft PR, operator-required authority and high-risk changes block preflight.

## Result lattice

- CONTRACT_INVALID: malformed or incomplete Issue.
- UNKNOWN: GitHub/source unavailable. Never turn missing evidence into success.
- NOT_ADMITTED: missing, stale, unsigned, failed, outside-scope, non-independent or operator-blocked evidence.
- EVIDENCE_COMPLETE_NOT_ADMITTED: every declared machine gate passed, **not** a merge, deployment, independently established truth of the underlying mathematical claim or authority.
- ADMITTED: protected-main admission outside this gate; **never emitted** by this script.

Domain-specific tasks (Lean formal proofs, data science, medical/scientific research, design, operations, publications) share the **Issue protocol** but require specialized independently replayable evaluators. The acceptance methods domain_evidence and independent_review are intentionally blocked in v1 until authenticated adapters exist. A GitHub check alone cannot validate all real-world claims.

## Deployment and evidence limitations

1. The #735 hosted runner billing issue is currently a reported pre-execution blocker. No hosted PASS is claimed.
2. This proposal is not active on protected main. Its trusted-base CI job cannot execute the checker while main does not yet contain that checker; bootstrap requires normal signed and protected-branch review, not a bypass.
3. The GitHub API lists are bounded at 100; incomplete listings fail closed. Upstream API timestamps, identity and check issuers still require independent reviewer scrutiny.
4. A user with permission to edit the Issue can change its requirements; future versions should pin an Issue contract revision/hash at PR creation and enforce a trusted reviewer for amendments.
5. Enable the gate as a required status **only after** a signed, verified, reviewed main installation and a live CI replay.

## Comparable frontier engineering principles

Anthropic 2026 agent evals and sequential/parallel/evaluator-optimizer selection; OpenAI Codex AGENTS.md and trace grading; GitHub Agentic Workflows read-only and safe outputs; SWE-bench Pro Verified's 2026 caveats on contamination and reward hacking. This is a design synthesis, **not** a measured superiority claim.

## Pilot metrics (10 heterogeneous existing Issues minimum)

Compare duplicate-PR creation, false-positive completion, exact-head proof coverage, unverified evidence percentage, accepted outcome latency, cost and human intervention. If the full workflow is slower and no safer than a single-agent baseline, simplify it. Keep falsification cases in the regression suite. No auto-merge, hidden authority escalation, secrets or spend.

## v1.1 hardening audit (2026-10-11)

- The checker enforces `files_complete` before admitting path scope and checks `pr.state=open`.
- PR head/base, draft status, description and Issue body/state/updated_at are read twice around the evidence fetch. Observable concurrent edits fail `PR_CHANGED_DURING_SNAPSHOT` or `ISSUE_CHANGED_DURING_SNAPSHOT`. A final API read is not a cross-system atomic transaction; the SHA is valid only for the observed snapshot.
- Every PR body must include `AEGIS-WORK-CONTRACT-SHA256: <digest>`, computed over canonical JSON (`sort_keys=True`, UTF-8, compact separators, no NaN). The independent reviewer must reference the same digest in the approving review body. Issue amendments invalidate prior approvals even if the PR head did not change.
- The read-only trusted-base job explicitly fails `TRUSTED_BASE_BOOTSTRAP_REQUIRED` until reviewed, signed source is installed on main. **Do not copy the verifier from the candidate PR into this privileged slot.** For this first PR, the normal protected-main process must establish the verifier. No bypass is allowed.
- A success reported by a PR-authored workflow is not independently authoritative merely because its GitHub Actions check-run app ID is 15368. The trusted base, protected rulesets, and reviewer identities remain required. Only `NOT_ADMITTED` or `EVIDENCE_COMPLETE_NOT_ADMITTED` can be emitted.
- The source and tests were replayed locally with Git blob SHA equality to this PR. Hosted CI failures with missing job steps are `NO_TEST_VERDICT`, not proven Python errors.


## v1.2 adversarial hardening — fail-closed claims vs reliable evidence

**Observed falsifiers of the previous gate:** \`scripts/*\` wrongly matched \`scripts/private/credentials.py\` because the standard \`fnmatch\` wildcard spans slashes; GitHub login comparisons were case-sensitive; missing PR author ID could still leave a spurious independent reviewer. All three returned a positive field-level gate before this repair.

**Repair:** path matching is component-scoped (\`*\` means one component, \`**\` means zero or more); reviewer identity requires positive numeric GitHub account IDs on both sides, canonical case-insensitive login distinction, and selection of latest review by numeric GitHub review ID rather than relying on array order. Malformed review evidence is denied.

**Self-authored check attack:** a pull request can modify its own Actions workflow while preserving its check-run name and GitHub Actions publisher app ID. Therefore the check name/app ID alone is insufficient. The live adapter now verifies the check's GitHub Actions job-details URL, run-to-exact-head binding, entire run completion/success, and that its producing workflow YAML blob is **identical at the protected base commit and at the candidate**. A workflow added by the candidate (including this PR's \`.github/workflows/agent-issue-gate.yml\`) cannot pass this provenance test before it is independently bootstrapped on main. Incomplete/erroring origin reads give **NOT_ADMITTED**.

**Remaining trust limits:** even an unchanged workflow may execute PR-controlled test source. A successful test attests only the executed test contract, **not** mathematical truth, product utility, reviewer independence beyond GitHub account identity, or a protected-main merge. This gate never grants authority.

**Verified:** source-bound offline unittest suite 51/51 PASS (not hosted CI), with negative checks covering scope traversal, swapped reviewer identities, reordered reviews and forged trusted-app success.

**Admission debt:** the trusted-base workflow does not exist on current main, latest candidate commits were unsigned, and hosted jobs failed without executed step evidence. Keep DRAFT / NOT_ADMITTED. No production, billing, signing, protection, merge, or authorization changes.
