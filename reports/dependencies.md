# Dependency Audit — AEGIS-OMEGA

Generated 2026-07-12 by repository audit (session), from commit `a0a74ac6f1c98dd72d4dde8837d2ec0efe4c7849`.
Audit only — nothing was fixed or upgraded in this pass.

## npm (`npm audit`, registry reachable from the audit environment)

| Workspace | `--omit=dev` | Full audit |
|-----------|--------------|------------|
| `sovereign-omega-v2/` | 0 vulnerabilities | 0 vulnerabilities |
| `packages/shared/` | — | 0 vulnerabilities |
| `hub/` | 0 vulnerabilities | **1 low** |
| `platform-picker/` (sampled product) | 0 vulnerabilities | **1 low** |

The single advisory (appearing in both `hub/` and `platform-picker/`, dev-dependency only):

- `@babel/core <=7.29.0` — *Arbitrary File Read via sourceMappingURL Comment*
  (GHSA-4x5r-pxfx-6jf8), severity **low**, fix available via `npm audit fix`.

**Severity totals across audited workspaces:** critical 0 · high 0 · moderate 0 ·
low 1 unique advisory (2 occurrences, both dev-only). Production dependency trees are clean.

## Rust (cargo)

`cargo audit` is **not installed** in this environment (`cargo: no such command: audit`),
so no local RustSec scan was run. Rust dependency scanning is intended to be covered by
the **OSV-Scanner CI workflow** (`.github/workflows/osv-scanner.yml`, push/PR/weekly cron,
scans the whole tree recursively including `Cargo.lock`). **Caveat:** its last 30 runs —
including the scheduled 2026-07-11 run on `main` — all ended `startup_failure` (the
`google/osv-scanner-action@v2.0.0` reusable workflow fails to start), so that coverage is
currently not being delivered. See `reports/ci.md` for the remediation note.

## Python

Best-effort only: the repo pins no Python manifest (no `requirements.txt`/lockfile for the
bridge; CI installs `flask flask-cors scikit-learn numpy` ad hoc in
`.github/workflows/ci.yml`), so `pip list --outdated` reflects the audit sandbox
environment, not a project lockfile. Sample of outdated env packages observed:
`cryptography 41.0.7 → 49.0.0`, `certifi 2026.2.25 → 2026.6.17`, `httplib2 0.20.4 → 0.32.0`,
plus argcomplete/blinker/charset-normalizer/conan/idna and others.
**Observation (not a vulnerability finding):** the absence of a pinned Python manifest
means bridge deps float at image-build time; pinning them would make bridge builds
reproducible and scannable.

## GitHub-side automation

Dependabot Updates + Dependency Graph are active (dynamic workflows), and CodeQL default
setup is active — so npm/Cargo manifests do get GitHub-side alerting even while the
osv-scanner workflow is failing to start.
