# Integration Ledger

**Generated from the working tree based on commit `31bcb7e`** by `scripts/integration_ledger.py`. Do not hand-edit — regenerate with `python3 scripts/integration_ledger.py --write`. This file is the authority on what is connected; a prose claim of "done" that this contradicts is wrong.

**19 WIRED · 3 LINKED · 2 DORMANT · 9 ORPHAN** across 33 top-level areas.

| Status | Area | Evidence |
|--------|------|----------|
| WIRED | `aegis-cl-psi` | CI, 8 ext-ref |
| WIRED | `aegis-runtime` | CI, 3 ext-ref |
| WIRED | `agents` | CI, 43 ext-ref |
| WIRED | `cockpit` | CI, vercel, 4 ext-ref |
| WIRED | `content-calendar` | CI, vercel, 1 ext-ref |
| WIRED | `crates` | CI, 1 ext-ref |
| WIRED | `genomics` | CI, 2 ext-ref |
| WIRED | `hook-generator` | CI, vercel, 1 ext-ref |
| WIRED | `hub` | CI, vercel, 15 ext-ref |
| WIRED | `packages` | CI, 31 ext-ref |
| WIRED | `platform-picker` | CI, vercel, 1 ext-ref |
| WIRED | `scripts` | CI, 10 ext-ref |
| WIRED | `security` | CI, 1 ext-ref |
| WIRED | `sovereign-omega-v2` | CI, vercel, 11 ext-ref |
| WIRED | `src` | CI, 295 ext-ref |
| WIRED | `studio` | CI, vercel, 2 ext-ref |
| WIRED | `tactical` | CI |
| WIRED | `verifiable` | CI |
| WIRED | `vertex` | CI, 2 ext-ref |
| LINKED | `core` | 384 ext-ref |
| LINKED | `docs` | 14 ext-ref |
| LINKED | `harness` | 37 ext-ref |
| DORMANT | `clients` | 1 ext-ref |
| DORMANT | `worker-src` | 1 ext-ref |
| ORPHAN | `aegis-ccil-verifier` | no external reference |
| ORPHAN | `aegisomega-webgpu` | no external reference |
| ORPHAN | `alignment` | no external reference |
| ORPHAN | `backend` | no external reference |
| ORPHAN | `enterprise` | no external reference |
| ORPHAN | `paperclip` | no external reference |
| ORPHAN | `sovereign-mesh` | no external reference |
| ORPHAN | `supabase` | no external reference |
| ORPHAN | `terraform` | no external reference |

## What the statuses mean

- **WIRED** — a live entrypoint runs it (a CI workflow references it, or it ships as a Vercel app). The only status that means *connected and running*.
- **LINKED** — imported by other code (≥3 external files) but not exercised by a live entrypoint of its own.
- **DORMANT** — referenced by 1–2 external files. Idle; wire it or archive it.
- **ORPHAN** — nothing outside the directory references it. Sediment.

> A directory being WIRED does not mean every *file* in it is. New files can dangle inside a wired directory until something calls them — check the module.

