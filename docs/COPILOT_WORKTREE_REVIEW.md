# Copilot Worktree Review

This runbook reviews the isolated Copilot branch `copilot/worktree-2026-05-29T02-23-08` in `AEGIS--.worktrees/copilot-worktree-2026-05-29T02-23-08` without mutating it.

## Trigger Conditions

Start a review when any of these becomes true:

- `git status` in the Copilot worktree is no longer clean
- `git log` in the Copilot worktree advances beyond baseline commit `bd9450be`
- `.memory/session_snapshot.md` appears in the Copilot worktree

## Review Sequence

Run:

```bash
powershell -ExecutionPolicy Bypass -File scripts/review-copilot-worktree.ps1
```

The helper prints:

- worktree status and recent commits
- changed files and diff summary
- touched subsystems
- findings-first review notes
- suggested validation commands
- integration guidance with explicit commit IDs when applicable

## Validation Defaults

- `sovereign-omega-v2`: targeted test first, then `npm run typecheck`, then `npm run build`
- `aegis-cl-psi`: `cargo test <module>` when a specific Rust module is obvious, otherwise crate-local `cargo test`
- `aegis-runtime`: `cargo test <module>` when a specific Rust module is obvious, otherwise crate-local `cargo test`
- `.github` or repo config changes: validate branch names, path references, and workflow triggers before broader checks

## Integration Rules

- Prefer `git cherry-pick` into the current branch when the Copilot commit list is clean and reviewable
- Use a branch merge only when the Copilot branch contains multiple dependent commits that must remain grouped
- Do not copy files manually between worktrees
- Re-run the minimal acceptance checks on the exact commit set before integrating
