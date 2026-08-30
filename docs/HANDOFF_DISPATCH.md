# Handoff to dispatch — recover the missing local artifacts

**Written:** 2026-07-27 · **By:** Claude Code session `3d942217` · **For:** dispatch (has cloud access to the operator's PC filesystem)

**Why you and not me.** Everything in §3 exists — or is believed to exist — on the operator's
machine or in a cloud account this session cannot reach. I verified their absence from the
repository; I could not verify their presence anywhere else. You can open those files. That is
the entire reason this document is addressed to you.

**Rule that governs this handoff.** Report what you find, including finding nothing. An absent
artifact recorded as absent is a result. An absent artifact quietly skipped is how this project
lost four months. If a path in §3 does not exist, say so explicitly and move to the next one.

---

## 1. Repository state as of this writing

Branch `claude/fable-mythos-behavior-analysis-yjm4yr` @ `74f4296`, pushed, fully green.

| Landed today | What it is |
|---|---|
| `src/sovereignty/authorization-inversion.ts` | access ≠ authority decision function |
| `src/sovereignty/commit-admission.ts` | spec §7/§9/§10 decidable fragment, amendments A1–A3, A6–A8 |
| `src/sovereignty/semantic-hash.ts` | spec §5.2–5.4, `Hash_sem` / `V_hash` |
| `src/sovereignty/commit-ingestion.ts` | spec §9.3, the Γ operator |
| `scripts/model-capability/` | MCB-001 preregistered battery — **never run**, needs `ANTHROPIC_API_KEY` |

Gate 8: 4218 passing / 68 skipped, typecheck + build clean, `verify-hashes.mjs` exit 0.

---

## 2. Open pull requests — 17, and 16 are blocked on one thing

`aegis / experiment-admission` requires **exactly one changed `.aegis/experiments/*.json` plan**
between the PR base and head, with `operator_approval.state == "APPROVED"`. A PR carrying no plan
is denied with `found 0`.

**Verified directly (#233):** 4 red — `experiment-admission`, `automaton-2`, `automaton-3`,
`Commit-bound evidence`. Everything else green: Gate 8, CL-Ψ, Seven-Pillar, CodeQL, osv-scanner,
Hadolint, all Vercel and Cloudflare deploys.

**Verified directly (#229):** now fully green. Admission succeeded at 12:29 UTC after 14 denials.

**NOT verified per-PR — check these yourself, do not assume:**

| PR | Branch | Title |
|---|---|---|
| 233 | `codex/review-slack-context-request` | RFCs for IntentEnvelope extraction, EvaluationPlane/EvaluationRecord schema |
| 228 | `dependabot/npm_and_yarn/...a06f58e` | bump npm_and_yarn group across 7 directories |
| 226 | `claude/aegis-epistemic-audit-amendment-ai8be8` | Epistemic Audit Amendment v1.1 + MUSTALAH pilot (DRAFT) |
| 225 | `feat/sol-cross-platform-control-plane` | SOL governed cross-platform control plane |
| 224 | `claude/blissful-rubin-mt9jS` | Admit recovered Kernel One — fail-closed signing, witness provenance |
| 203 | `fix/supabase-security-definer-execute` | revoke client execute on privileged RPCs |
| 201 | `chatgpt/scale-os-handoff-20260718` | Scale OS handoff docs |
| 200 | `codex/update-pr-#192-with-april-2026-package` | bind April 2026 Kaggle submission evidence |
| 199 | `codex/enforce-4096-token-limit-in-managedage` | Managed Agents session token ceiling |
| 198 | `codex/validate-aegis_batch_max_usd-in-config` | validate batch spending caps |
| 197 | `codex/add-provider-neutral-inference-gateway` | governed provider-neutral inference gateway |
| 196 | `codex/define-billing-schema-and-implement-we` | Supabase billing ledger + webhook ingestion |
| 195 | `codex/add-foundry-backend-type-and-integrati` | governed Azure FOUNDRY backend |
| 194 | `codex/create-product-endpoints-and-dashboard` | product quotas, billing lifecycle, dashboard |
| 193 | `codex/add-ultrareview-feature` | harden batch spending cap validation |
| 191 | `fix/autonomous-safety-gates` | contract-legal autonomous audit, fail-closed |

**#226 and #229 overlap.** Both adopt Epistemic Audit Amendment v1.1 + the MUSTALAH pilot. #229 is
now admitted; #226 is not. Determine whether #226 is superseded before doing any work on it —
merging both would duplicate the adoption record.

---

## 3. What to look for on the PC — the actual ask

### 3.1 The holon-gram compiler (HIGHEST VALUE — believed lost)

A ChatGPT/Codex session reported an 8-file change, **+4446 / −889**, then said *"the commit remains
held until those pass."* It was never pushed. I searched 342 commits across 42 remote branches and
every tree in history: **zero matches**. It exists only in that session's working tree, on a
container that gets reclaimed.

Search the PC for:

```
holonogram-compiler.ts          (+770 −770 — symmetric, likely a rename or full rewrite)
holonngram-compiler.ts          (+1599 −58 — note the DOUBLED n)
holonngram-compiler.test.ts     (+441 −15)
```

Likely under a path resembling `...-v2/src/projection/` and `...-v2/test/unit/`. The repo's real
`sovereign-omega-v2/src/projection/` currently contains only `compiler.ts` and `reducer.ts`.

Also grep for the symbol `admitSemanticCommit` — it appears nowhere in the repository.

**Flag before doing anything with it:** the two spellings differ by one `n`. That reads like a file
renamed into a typo with both versions alive in the same diff. Establish which spelling is intended
*before* any of it is committed, or the repo inherits two compilers.

**Report:** full paths, file sizes, mtimes, and whether a `.git` directory nearby has unpushed
commits (`git log --branches --not --remotes`).

### 3.2 `AuthContext.json`

Confirmed **not** in the repo, not in git history, not in the connected Drive. The operator has
confirmed it is not published. Treat it as a restricted local artifact.

**Do not copy its contents into any file, commit, issue, or message.** Report only: does it exist,
what path, what mtime, and what *shape* it has — top-level key names only, never values. If it
holds credentials, the correct outcome is a rotation task, not a transcription.

### 3.3 Kaggle evidence for the Hallucination Delta benchmark

PR #200 is titled "bind the April 2026 Kaggle submission evidence." The corpus notes record that
reported HD benchmark results were **never independently rerun** and that no official Kaggle
receipt or leaderboard confirmation exists in the corpus.

Look for: submission receipts, leaderboard screenshots, `submission.csv`, notebook exports, or
anything under a Kaggle directory dated around April 2026.

Without this, HD stays a calibration-error primitive with no external validation, and PR #200
cannot honestly bind what it claims to bind.

### 3.4 Corpus manifest gaps — explicitly listed as unresolved

From `UNIVERSAL_SOVEREIGN_AGI_OS_CORPUS_MANIFEST_2026-07-24.json`:

- GCP/GCS bucket enumeration
- NVIDIA run receipts
- Gemma 1B / 3B logs
- Drive recursive hashing
- OneDrive traversal
- fresh production deployment verification

Each of these is a claimed capability with no evidence attached. Any one you can locate converts a
claim from asserted to supported.

### 3.5 The macOS/Linux reliability CSV

File `b3d81dcb-c4a6-4368-82c1-598df5e53209.csv` reports macOS failure rate **6.0** vs Linux **0.14**.
That gap is not interpretable without: metric units, reporting window, workload equivalence, the
definition of "failure", and sample sizes. Find the generator or schema.

### 3.6 One billing question with a hard date

Anthropic charges have been declining continuously — ~17 failed attempts between Jul 5 and Jul 20
($5, $6, $10 ×5, $11.96, $20 ×6). Separately, `ACCESS_REGISTER.md` records Google Payments card
••8780 verification **expired Jul 21**.

Determine whether these are the same card. If so it is one problem, not two, and it is currently
the binding that keeps the Claude API org `Aegis Omega` disabled for want of ~$10–20 of credit.

Unrelated but time-boxed: Google Cloud Knowledge Catalog data-insights billing starts
**2026-10-27** on project `aegisomegav1`. I grepped the repo — no BigQuery/Dataplex/Data Catalog
client, no SDK dependency, no API call. The only hit is a comment in `packages/shared/lib/analytics.ts`
describing intent, not invocation. **A repo audit is not a project audit** — automated invocation
could come from Dataplex auto-discovery, scheduled queries, or console usage. That check is in the
GCP console, not the filesystem.

---

## 4. How to admit a PR — the exact recipe, learned the hard way

Do **not** hand-write an approval. The validator recomputes the hash and compares.

1. The plan must be the **only** changed `.aegis/experiments/*.json` between base and head.
2. `expected_parent_sha` must equal the PR base SHA. Re-check it — `main` moves.
3. `expected_parent_state_root` must match `computeExpectedParentStateRootV01(plan)`.
4. `operator_approval` is schema-validated with `additionalProperties: false`. **No extra keys.**
   A `_comment` inside that object is itself a denial, and it will hide underneath the state error
   until you fix the state and hit it second.
5. Derive the hash with the repo's own function, never by hand:

   ```
   computeApprovalRecordHashV01(approval)
     = sha256(JCS({ domain: 'AEGIS_OPERATOR_APPROVAL_V0_1', approval: approvalPayloadV01(approval) }))
   ```

6. Recompute against the written file and confirm it matches before pushing.
7. Validate the plan against `.aegis/experiment-plan.schema.json` locally.

**Authority boundary — do not cross it.** `state: APPROVED` may only be set when the operator has
explicitly instructed approval for that specific plan. Flipping it on your own initiative is
self-granted authority, which is the exact failure `src/sovereignty/authorization-inversion.ts`
exists to refuse. Absence of an instruction is not permission. If unsure, leave it PENDING and let
CI deny — a denial costs nothing and is fully reversible.

---

## 5. What NOT to do

- Do not run the MCB-001 battery casually. It is preregistered; changing `tasks.ts` invalidates
  comparison with any earlier result, and the decision rule in `PREREGISTRATION.md` §7 must not be
  loosened after seeing scores.
- Do not cite an MCB-001 result before a `results/` file exists. It has never been run.
- Do not treat a capability difference between models as evidence about who authored a commit.
  That non-inference is preregistered as CLM-232 specifically so it cannot be read the other way.
- Do not resume the paused Supabase project (`rwehltdwpsncnwxzkwik`, INACTIVE, connection times
  out). That is a billing action and belongs to the operator.
- Do not redeem, move, or transcribe anything financial.

---

## 6. What "done" looks like

For each item in §3: a path, a timestamp, a size, and a one-line verdict of FOUND / ABSENT /
INACCESSIBLE. Nothing more is required, and a table of ABSENT rows is a perfectly good outcome —
it converts six open questions into six settled ones.

The single highest-value result is §3.1. If the holon-gram compiler still exists on that machine,
it is 4,446 lines of work that currently exists in exactly one place and will not survive the
container it was written in.
