# Locate Artifact

Use this skill whenever the operator asks whether a named AEGIS component, proof, branch, module, document, experiment, or prior implementation exists, or whenever you are about to say that one does not exist.

## Core invariant

A miss in the checked-out worktree is not a repository-wide absence result.

A matching branch/PR/commit name is not proof that implementation content exists.

`main` determines canonical admitted runtime state; it does **not** define the universe of historical, experimental, stacked-PR, Drive, or research artifacts.

## Mandatory discovery sequence

1. Confirm repository root and current HEAD.
2. Run:

```bash
bash "${CLAUDE_PROJECT_DIR:-$PWD}/.claude/hooks/artifact-locator.sh" '<exact user term>'
```

3. Interpret the machine verdict exactly:
   - `IMPLEMENTATION_EVIDENCE_FOUND`: inspect the matched ref/path before describing it.
   - `NAMED_REFERENCE_FOUND`: inspect that ref; report the distinction between a named reference and implementation evidence.
   - `INCOMPLETE`: do not make a global absence claim. State which scope could not be searched.
   - `NO_MATCHES_IN_COMPLETE_REPO_SCAN`: only say that no matching artifact was found in the refreshed Git repository/PR scope.
4. If the requested item could live in the research corpus, Google Drive, a provider workspace, or conversation-derived artifacts, search the relevant connected source before making a global claim. The repository scan alone cannot prove absence from those sources.
5. If a branch name matches, compare it against its base/main and inspect its changed paths. A stale or repurposed branch name must be reported as such; never infer contents from the branch name.

## Required language for negative findings

Bad:

> ProofPrism does not exist.

Good:

> I found no ProofPrism implementation in the refreshed Git content I searched. There is a matching named ref `<ref>`; its contents must be inspected separately. Drive/external corpus scope has not yet established an implementation.

Or, after all relevant scopes were checked:

> No matching implementation was found in the scopes checked: `<scopes>`. This is an evidence-bounded absence result, not a claim about deleted or inaccessible history.

## Why this exists

AEGIS has many stacked PRs, long-lived experiment branches, provider-created branches, and external research artifacts. Claude sessions normally reason from the current checkout plus whatever tools they explicitly call. That creates false negatives when an artifact is outside the current worktree or when a branch has been renamed/reused. This skill turns artifact existence into a scoped evidence query instead of a memory guess.
