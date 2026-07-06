# Integration Ledger

**Generated from code at commit `6fd3ce71`** by `scripts/integration_ledger.py`. Do not hand-edit — regenerate with `python3 scripts/integration_ledger.py --write`. This file is the authority on what is connected; a prose claim of "done" that this contradicts is wrong.

**19 WIRED · 8 LINKED · 6 DORMANT · 0 ORPHAN** across 33 top-level areas.

| Status | Area | Evidence |
|--------|------|----------|
| WIRED | `aegis-cl-psi` | CI, 39 ext-ref |
| WIRED | `aegis-runtime` | CI, 14 ext-ref |
| WIRED | `agents` | CI, 66 ext-ref |
| WIRED | `cockpit` | CI, vercel, 25 ext-ref |
| WIRED | `content-calendar` | CI, vercel, 16 ext-ref |
| WIRED | `crates` | CI, 7 ext-ref |
| WIRED | `genomics` | CI, 5 ext-ref |
| WIRED | `hook-generator` | CI, vercel, 17 ext-ref |
| WIRED | `hub` | CI, vercel, 50 ext-ref |
| WIRED | `packages` | CI, 62 ext-ref |
| WIRED | `platform-picker` | CI, vercel, 18 ext-ref |
| WIRED | `scripts` | CI, 73 ext-ref |
| WIRED | `security` | CI, 6 ext-ref |
| WIRED | `sovereign-omega-v2` | CI, vercel, 52 ext-ref |
| WIRED | `src` | CI, 397 ext-ref |
| WIRED | `studio` | CI, vercel, 16 ext-ref |
| WIRED | `tactical` | CI, 2 ext-ref |
| WIRED | `verifiable` | CI, 2 ext-ref |
| WIRED | `vertex` | CI, 9 ext-ref |
| LINKED | `alignment` | 5 ext-ref |
| LINKED | `clients` | 6 ext-ref |
| LINKED | `core` | 412 ext-ref |
| LINKED | `docs` | 59 ext-ref |
| LINKED | `harness` | 50 ext-ref |
| LINKED | `paperclip` | 4 ext-ref |
| LINKED | `sovereign-mesh` | 7 ext-ref |
| LINKED | `supabase` | 9 ext-ref |
| DORMANT | `aegis-ccil-verifier` | 2 ext-ref |
| DORMANT | `aegisomega-webgpu` | 2 ext-ref |
| DORMANT | `backend` | 2 ext-ref |
| DORMANT | `enterprise` | 2 ext-ref |
| DORMANT | `terraform` | 2 ext-ref |
| DORMANT | `worker-src` | 1 ext-ref |

## What the statuses mean

- **WIRED** — a live entrypoint runs it (a CI workflow references it, or it ships as a Vercel app). The only status that means *connected and running*.
- **LINKED** — imported by other code (≥3 external files) but not exercised by a live entrypoint of its own.
- **DORMANT** — referenced by 1–2 external files. Idle; wire it or archive it.
- **ORPHAN** — nothing outside the directory references it. Sediment.

> A directory being WIRED does not mean every *file* in it is. New files can dangle inside a wired directory until something calls them — check the specific module.

