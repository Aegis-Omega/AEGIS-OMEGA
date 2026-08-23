# Repository Audit — AEGIS-OMEGA

Generated 2026-07-12 by repository audit (session), from commit `a0a74ac6f1c98dd72d4dde8837d2ec0efe4c7849`.

## Scope

This session is repo-scoped to `Aegis-Omega/AEGIS-OMEGA` — this is the only repository
classified here. Sibling projects are referenced in-tree but unreachable from this session:

- **swarm_os** — documented as a parallel, zero-coupling Kaggle track in
  `docs/AUDIT_FINDINGS.md:167-169` (Hallucination Delta / HD metacognition track vs this
  repo's VCG/PGCS governance proof track). Its files were purged from this tree
  (`docs/AUDIT_FINDINGS.md` "Dead content purged: swarm_os (1199 files)").
- **ResearchOS / Sovereign AGI OS** — referenced by `CLAUDE.md` (MYTHOS BOOTSTRAP
  cross-project note: `AdaptivePower(T) ≤ ReplayVerifiability(T)` ↔ `HD = |claimed − actual|`);
  no code from it exists in this tree.

## Classification

| Property | Value |
|----------|-------|
| Default branch | `main` |
| Activity | **Active** — 43 commits on `origin/main` in the 30 days ending 2026-07-12 |
| Merge flow | Squash-merge (PR numbers in subject lines; a single true merge commit in recent history) |
| Remote branches | 2 — `main` + the current session branch. **No stale branches.** |
| Tracked files | 1,752 |
| CI | GitHub Actions (see `reports/ci.md`) — BFT "CEREMONY" quorum at 1/φ |

## WIRED vs TESTED-ONLY vs DORMANT

Derived from `REPO_MAP.md` (the repo's own four-way inspection index, 2026-06-13; per its
header, when a doc and the code disagree, the code wins). Summary:

**WIRED (runs in prod / built / deployed / imported):**
`sovereign-omega-v2/python/` (bridge → Cloud Run `aegis-vertex`), `vertex/` (bundles
`agents/` + `harness/`), `aegis-cl-psi/` (~7,198 Rust tests, CI-gated), `aegis-runtime/`,
`hub/` (the storefront; Vercel + Cloud Run), the 3 commercial tools
(`platform-picker/`, `hook-generator/`, `content-calendar/`) + `packages/shared/`,
`tactical/` (wired to the bridge, no deploy config), `cockpit/` + `studio/` (deployable
dashboards, CI-built), `supabase/functions/` (live edge functions), `worker-src/`
(Cloudflare Worker `/platform/holon/validate`), `genomics/` + `verifiable/`
(cross-platform proof CI), `.claude/` governance hooks, `.github/` CI.

**TESTED-ONLY (real code, only tests touch it):**
- The headline number (REPO_MAP.md §2): **~184 of 189 TS files in `sovereign-omega-v2/src/`
  never reach the running app** — `main.tsx` transitively uses only `components/` +
  `lib/telemetry.ts` (~5 files); everything else (`core/`, `constitutional/`, `agents/`,
  `verifier/`, `consensus/`, `pipeline/`, `memory/`, `api/`, `compliance/`,
  `corpus-engine/`, `skill-harness/`, …) is exercised only by the ~250-file test suite.
- Root `src/` — the Gate 206 `aegis-hypervisor` crate: compiles, 15 tests pass, not in CI
  (REPO_MAP.md §3).
- `crates/constitutional-substrate/` — compiles + has tests, standalone, not in CI.

**DORMANT (nothing references it):**
`backend/` (complete Express server, no CI/deploy/importer), `enterprise/` (React 19
dashboard wired nowhere), `terraform/` (valid GCP IaC, not automated),
`packages/kernel/` (orphaned Rust workspace member), plus manual-run/doc-only dirs:
`paperclip/`, `sovereign-mesh/`, `security/`, `alignment/`, `aegisomega-webgpu/`
(standalone engine), root `core/` (9 TS files, unreferenced), `aegis-ccil-verifier/`
(manual cross-verify scripts).

**DEAD/removed (per REPO_MAP.md §4):** `frontend/`, the Gumroad path, the Lemon Squeezy
subsystem, `eccf/`/`gcce/`, committed `dist/` artifacts — already removed from the tree.

## Languages by tracked-file count

`git ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -15`:

| Count | Extension |
|------:|-----------|
| 547 | ts |
| 461 | rs |
| 183 | md |
| 110 | py |
| 91 | json |
| 81 | tsx |
| 30 | js |
| 29 | svg |
| 23 | sh |
| 17 | yml |
| 15 | yaml |
| 14 | css |
| 13 | sql |
| 12 | html |
| 12 | gitignore |

TypeScript and Rust dominate; the Python surface (110 files) is small but carries the
production bridge. Machine-readable version: `reports/inventory.json`.
