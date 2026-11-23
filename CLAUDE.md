# CLAUDE.md

Read `AGENTS.md` first: the operator, merging and spend rules, environment setup. This file
covers how the repo is laid out and how to verify a change. The previous long version is kept
at `docs/archive/2026-11-23-CLAUDE.md` as history, not as instructions.

## Working rules

- The running code and live systems beat any document. `REPO_MAP.md` says what is wired,
  test-only or dormant; check it (and the code) before fixing something that may never run.
- Make the smallest change that solves the asked problem. Match the existing style. Do not
  refactor or reformat unrelated code; mention dead code instead of deleting it.
- Fixing a bug: reproduce it with a failing test first. Nothing is done until its gate passes
  and it is on `main`.
- Report only what you ran. Mark the rest NOT_RUN or UNKNOWN. A passing test is not proof of
  correctness, and a merged PR is not proof of deployment.

## What runs

| Path | What it is |
|---|---|
| `sovereign-omega-v2/python/bridge.py` | Governance and inference HTTP service (Cloud Run, europe-west3) |
| `sovereign-omega-v2/src/` | TypeScript governance runtime; most of it is exercised only by tests |
| `aegis-cl-psi/`, `aegis-runtime/` | Rust engine and runtime |
| `hub/` | Storefront: PayPal / Stripe checkout, then `supabase/functions/verify-*` mints keys |
| `platform-picker/`, `hook-generator/`, `content-calendar/` | Paid tools, sharing `packages/shared/` |
| `supabase/functions/` | Edge functions; payment tokens are minted server-side only |
| `agents/` | Python coordinator, `cmgl_orchestrator.py`, `aegis-worker/` (Managed Agents definitions) |

## Verify a change

```sh
cd sovereign-omega-v2 && npm run test -- test/unit/<file>.test.ts   # one file
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build   # before any TS commit
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs              # frozen-file hashes, must exit 0
cd aegis-cl-psi && cargo test        # never --all-features (needs ROCm hardware)
cd aegis-runtime && cargo test
python -m pytest agents/tests        # agent code
```

Wrong working directory is the most common cause of false failures: check `pwd` first.

## Invariants

- TypeScript: no `Date.now()` outside `src/event/uuid.ts`; hash only through `canonicalizeJCS`
  / `hashValue` (never `JSON.stringify`); no `Set`/`Map` in hashed state; `deepFreeze` state
  objects; `.js` suffix on relative imports.
- Rust: `BTreeMap`/`BTreeSet`, never `HashMap`, in anything hashed; `to_be_bytes()` in hash
  inputs; `f64` hashed via `to_bits()`; `saturating_*` arithmetic.
- Python: no `time.time()` in determinism-critical paths; use sequence numbers.

## Never

- Modify `sovereign-omega-v2/python/gate.py`, `dna.py` or `router.py` (frozen; hashes checked
  by `verify-hashes.mjs`).
- Commit `.env` files, keys or tokens.
- Mint payment or access tokens client-side.
- Turn on Vertex AI by default (`AEGIS_USE_VERTEX=true` is opt-in only) or re-enable Cloud Run
  auto-deploy: both caused unplanned GCP bills. Deploys are manual `workflow_dispatch`.
