# CI Audit — .github/workflows/

Generated 2026-07-12 by repository audit (session), from commit `a0a74ac6f1c98dd72d4dde8837d2ec0efe4c7849`.

12 workflow files existed in `.github/workflows/` at audit time; this audit adds a 13th
(`apple-oss-watch.yml`). GitHub additionally runs 3 dynamic (non-file) workflows:
**CodeQL** (default setup), **Dependabot Updates**, **Dependency Graph** — all active.

## ci.yml — "AEGIS-Ω Constitutional Automaton" (the main gate)

Triggers: push + PR on `main` and `claude/*`, `workflow_dispatch`. Job DAG:

```
membrane [T0 frozen-hash gate]
  ├─→ cl-psi  [Rust CL-Ψ, asserts ≥6800 tests] ─┐
  ├─→ runtime [Rust Seven-Pillar]               ├─→ gate8 [TS test+typecheck+build]
  │                                             │      ├─→ python-tests   (NOT in quorum)
  │                                             │      ├─→ coverage-ts    (informational)
  │   coverage-rust (informational) ←───────────┘      ├─→ studio
  │                                                    └─→ toolkit ×6 (hub, cockpit,
  │                                                         platform-picker, hook-generator,
  │                                                         content-calendar, tactical)
  └────────────→ ceremony (if: always()) ← [membrane, cl-psi, runtime, gate8, studio, toolkit]
```

**CEREMONY semantics (verified in ci.yml:298-393):** 6 votes — membrane, cl-psi, runtime,
gate8, studio, toolkit — against threshold 1/φ ≈ 0.6180.

- **The only hard-blocking check is the T0 frozen-hash gate**: if the membrane job's
  `t0_verdict != true` or `corruption_count != 0`, ceremony exits 1 unconditionally
  (ci.yml:353-359).
- Otherwise the BFT quorum **permits 2 job failures**: 4/6 = 0.6667 ≥ 0.618 passes;
  3/6 = 0.5 fails. A red studio + red toolkit, for example, still yields
  "CONSTITUTIONAL: PERMIT".
- `python-tests` (the bridge contract suite) is **not counted in the quorum at all** —
  it fails only its own check, never the ceremony verdict.
- Cancelled upstream jobs defer the ceremony (exit 0) rather than failing it.

## Deploy workflows — both manual-only, auto-deploy disabled

- **deploy.yml** ("Deploy to Cloud Run", 6 jobs incl. hub/products/bridge) —
  `workflow_dispatch` **only**; the in-file comment says auto-deploy was disabled to stop
  GCP billing. Uses WIF via secrets `GCP_WORKLOAD_IDENTITY_PROVIDER` / `GCP_SERVICE_ACCOUNT`.
- **deploy-cloud-run.yml** ("Deploy to Cloud Run (WIF)") — also `workflow_dispatch` only,
  same disabled-trigger comment. Uses WIF via **vars** `WIF_PROVIDER` / `WIF_SERVICE_ACCOUNT`
  and is a no-op until those are set.
- **Overlap:** two parallel WIF Cloud Run deploy paths with different credential plumbing.
  REPO_MAP.md §4 explicitly marks deploy-cloud-run.yml "NOT a no-op duplicate — keep"
  (the manual-only trigger encodes the billing-safety decision).
- **WIF attribute condition is stale** — per HANDOFF.md §0/§4 every Cloud Run deploy fails
  at the GCP auth step ("The given credential is rejected by the attribute condition");
  the identity-pool provider is pinned to a repo identity that no longer matches
  (`Aegis-Omega/AEGIS-OMEGA`). GCP-side fix, ~5 minutes, operator credentials required.

## Dead / inert triggers

- **jekyll-gh-pages.yml** — push trigger targets branch `claude/test-coverage-analysis-keTIk`,
  which no longer exists (remote has only `main` + the current session branch). Never fires
  except manual dispatch; appears to be an unedited GitHub sample workflow.
- **agent-dispatch.yml** — gated on `if: vars.PROXY_URL != ''`; that repo variable is unset,
  so every trigger is a no-op. Also, its `workflow_run` trigger names a workflow called
  "CI" — no workflow has that name (ci.yml is named "⊕ AEGIS-Ω Constitutional Automaton"),
  so that trigger can never match even with PROXY_URL set.

## Real supporting workflows

- **frozen-files.yml** ("Constitutional Integrity") — path-triggered only on the three
  frozen files (`gate.py`, `dna.py`, `router.py`); runs `verify-hashes.mjs`. Real and load-bearing.
- **osv-scanner.yml** — push/PR/weekly cron (`15 13 * * 6`), uses the reusable workflows
  from `google/osv-scanner-action`. **Finding (root-caused and fixed 2026-07-12): every
  run since 2026-05-29 (~656 consecutive, including scheduled runs on `main`) ended
  `startup_failure`** because the `uses:` refs pointed at tags that do not exist upstream —
  run #20 (2026-05-29T05:27Z, pinned `@1f12429…` # v1.7.1) still resolved and ran; run #21
  (05:42Z) onward carried a hallucinated `@v2.3.8` pin, later replaced by `@v2.0.0`
  (also nonexistent — the action repo's first v2 tag is v2.0.2). Not an org allowlist
  issue: third-party actions (`dtolnay/*`, `Swatinem/*`, `hadolint/*`,
  `google-github-actions/*`) and run #20's `google/*` reusable workflow all resolve fine.
  Fix: re-pinned both refs to the real release `@v2.2.4` and dropped the v1-only
  `--skip-git` scan-arg (removed in osv-scanner v2). Verify the next scheduled/push run
  reaches its jobs instead of `startup_failure`.
- **hadolint.yml** — Dockerfile lint on push/PR/weekly cron, but the job sets
  `continue-on-error: true` (hadolint.yml:26) — advisory only, can never block.
- **verifiable-proofs.yml** — genomics + verifiable-envelope proofs on ubuntu x86-64 AND
  macOS arm64, asserting a byte-identical pinned terminal hash across platforms.
  Path-triggered on `genomics/**`, `verifiable/**`. Real cross-platform T0 evidence.
- **aegis-interface.yml** — contract-equivalence gate for `packages/aegis-interface`
  (RFC 0001 WIT→IR compiler), path-triggered. Real.
- **greetings.yml** (first-interaction bot) and **summary.yml** (AI issue summarizer via
  `actions/ai-inference`, with prompt-injection guardrails) — housekeeping, low risk.
- **apple-oss-watch.yml** (added by this audit) — daily cron + dispatch; checks Apple OSS
  releases/tags against `reports/apple-oss-state.json` and opens an issue on change;
  never commits state (see file comments).
