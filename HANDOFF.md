# AEGIS-Ω — Handoff (ground truth as of 2026-06-14)

A no-spin snapshot you can hand to any engineer or another AI and have them productive in
30 minutes. Everything here was **verified by probing live systems this session**, not read
from docs. Where a doc and the code/live system disagreed, the live system wins.

---

## 1. One-paragraph status

You have **more working infrastructure than most people who claim to run "AI agent companies"**:
a live storefront, a deployed payment function that mints API keys, a hosted 39-agent
platform, real Rust/TS engines, and ~11k passing tests. What you do **not** yet have is a
single sharp product that *does* a job a customer pays for. Two concrete bugs were hiding the
working parts (both fixed this session). The agents, as built, mostly *describe* work rather
than *do* it. The gap to first revenue is small and unglamorous: ship one tool that produces a
real deliverable, behind the payment you already have.

---

## 2. What is LIVE right now (verified this session)

| System | Probe result | Meaning |
|--------|-------------|---------|
| Store — `https://aegisomega.com` | HTTP 200 | Public, visitable today |
| Platform — `https://aegis-vertex.aegisomega.com/platform/status` | 200 · `total_agents: 39` · `chain_valid: true` · `available: true` | Agent platform is up in production |
| Bridge health — `/health` | `{"status":"OK"}` | Service healthy |
| Payment fn — Supabase `verify-paypal` | deployed, **version 5**, ACTIVE | Live and callable |
| Key minting | **Minted a real free Explorer key in one live call** (`aegis_…`) | The provisioning plumbing works end-to-end |
| Supabase project | `rwehltdwpsncnwxzkwik` ("aegis-omega", eu-central-1, ACTIVE_HEALTHY) | The real DB/functions project |

**The one true money path:** `hub` PricingPage → PayPal Smart Buttons → `supabase/functions/verify-paypal`
captures the order, checks the amount against the tier floor ($48 Operator / $498 Sovereign),
and mints an `aegis_…` API key (free **Explorer** tier provisions directly, 1/email, 100/day cap).

Deployed Supabase edge functions: `verify-paypal`, `verify-stripe`, `github-sponsors`,
`issue-token`, `ls-webhook`, `restore-access`, `chat`, `agent`, `notify`, `slack-events`, `bridge`.

---

## 3. Bugs found AND FIXED this session

1. **All three commercial tools white-screened in production** (`platform-picker`,
   `hook-generator`, `content-calendar`). Root cause: two physical copies of React get bundled
   — the product's own `node_modules/react` **and** `packages/shared/node_modules/react` (both
   19.2.6) — and the vite config had no `dedupe`. Two React instances ⇒ null hooks dispatcher ⇒
   `Cannot read properties of null (reading 'useState')` ⇒ blank page. **Fix:** added
   `resolve.dedupe: ['react','react-dom']` to each product's `vite.config.ts`. **Proven:** the
   tool went from a black screen to fully rendering (screenshot captured). This is almost
   certainly why "there was nothing you could actually use to see."

2. **CI FIELD builds were failing** for the same three products. CI ran `npm ci && npm run build`
   in each product but never installed `packages/shared`'s deps, so `tsc -b` couldn't resolve
   `react`/`lucide-react` when compiling shared `.tsx`. **Fix:** install `packages/shared` deps
   before each product build in `.github/workflows/ci.yml`. **Proven:** reproduced the exact CI
   error locally and confirmed the fix clears it. (Commit `01acf00`.)

Both fixes are on branch `claude/anthropic-compliance-docs-df4ogq` (PR #156).

---

## 4. What the "agents" actually are (be honest with yourself here)

- `POST /platform/collaborate`, header `x-api-key`, body `{objective, mode, live}`.
- **`live:false` (demo):** returns 39 "department" artifacts — but every department emits the
  **same templated sentence** with its name prepended (Strategy/Finance/Pricing/Brand all said
  the identical thing when probed). It is a mock. Zero API cost.
- **`live:true`:** **one** governed Claude call role-plays all 39 departments in a single
  response. It is one model describing what departments would say — not 39 agents doing work.
- The **commercial tools** (`hook-generator` et al.) are closer to "real agents": they take
  input and call a model (`callConstitutional` → inference-router → DashScope/Qwen → Ollama →
  Claude → CL-Ψ) and return a usable artifact. The fallback chain works (it reports failures
  gracefully instead of crashing). They need a model key + network at runtime (the buyer
  supplies `VITE_DASHSCOPE_API_KEY`, or you bake in your own Claude key).

**The product gap = the difference between "describes a GTM plan" and "produces the deliverable."**
That gap is the whole business and it's smaller than the infra already built.

---

## 5. Money / payments — decisions

- **PayPal is your rail. Locked.** You confirmed you can cash out PayPal in Bosnia. `main`
  already uses PayPal (`verify-paypal`). Keep it.
- **Stripe cannot work for you.** Bosnia and Herzegovina is not on Stripe's supported-seller
  list — you can't hold a Stripe account there. **PR #153 replaces PayPal with Stripe; that part
  must NOT merge** (`verify-stripe` + `github-sponsors`). Drop it or it breaks your ability to
  get paid.
- Lemon Squeezy / Paddle (merchant-of-record + Wise/Payoneer payout) are the usual fallback for
  Stripe-excluded countries — but you said you don't have Lemon Squeezy, so **don't churn
  providers**: PayPal works, ship on it.
- The repo has cycled Gumroad → Lemon Squeezy → PayPal → Stripe across sessions. That churn is a
  top time-sink. **Stop swapping providers.**

---

## 6. Open decisions (yours to make)

- **The three tools — keep / remove / extract?** You asked "do they fit here?" Honest answer:
  strategically they're a *different, simpler business* than the AEGIS-Ω constitutional platform
  (they touch none of the governance machinery). Practically they're your only near-term
  revenue and they now build + render. They've been deleted/re-added ~15× because
  `GTM_ENGINEERING_SPEC.md` ordered them killed and no session recorded a final call. **Pick
  one: keep them (record it binding) or remove them once (record it binding).** Either ends the
  churn; flip-flopping is the only wrong answer.
- **PR #153's Stripe path:** decide to drop it before any merge (see §5).

---

## 7. Open PRs

- **#156** (`claude/anthropic-compliance-docs-df4ogq` → main, draft): full Anthropic compliance
  encoding into the `anthropic-alignment` skill, anti-slop workflow docs (`WORKFLOW.md`,
  `REPO_MAP.md`, `ground-truth.sh`), node_modules cleanup, **the CI fix + the dual-React fix**.
- **#153** (`claude/test-coverage-analysis-keTIk` → main, draft): Python SDK, proof-demo,
  Gate 81, **and the Stripe swap** — merge the SDK/test parts if wanted, **but not the Stripe
  swap.** 30+ commits, never merged → this is why prior sessions' work isn't all on `main`.

---

## 8. Fastest path to the first dollar (concrete)

1. Pick **one** tool — recommend `hook-generator` (smallest, clearest promise).
2. Bake in **your own** Claude/Qwen key so the buyer needs nothing (set `VITE_CLAUDE_API_KEY` or
   `VITE_DASHSCOPE_API_KEY` at build, or proxy through `supabase/functions/chat`). Right now it
   expects the *buyer* to bring a key — that kills conversion.
3. Confirm it renders + generates on a real deploy (the dedupe fix makes it render; it needs
   network + key to generate — both exist in prod, neither existed in this sandbox).
4. Point the **Operator** PayPal tier at it (already wired to `verify-paypal`).
5. Put the URL in front of 50 people in one niche. Charge. Watch one real purchase land in
   `api_key_store`.
6. Only then think about the 39-agent platform.

Everything in steps 1–5 already exists. The work is wiring + one key + telling people — not a rebuild.

### Cloud-session network access (why generation fails in the sandbox)

The tools **render** in a cloud session but won't **generate** unless the environment's
**Network access** allows the model host. The default level is **Trusted** = package
registries + GitHub + cloud SDKs only, which blocks `dashscope.aliyuncs.com` (Qwen) — the
exact `DashScope 501` / `Failed to fetch` seen when driving the tool. The keys are already
present in the env; only the network is closed.

Fix (one-time, in the dashboard — NOT settable from a repo file or setup script):
`claude.ai/code → your environment → Network access → Custom (keep defaults) → add hosts`, or set **Full**.

| Add this host | Unblocks |
|---------------|----------|
| `dashscope.aliyuncs.com` | the 3 tools generating via Qwen (keys already in env) |
| `api.anthropic.com` | the tools' Claude backend, if you bake in your own Claude key |

Production (Cloud Run + Vertex) already has open network — that's why `/platform/status`
returned 200 with 39 agents. Only the sandbox is network-boxed.

---

## 9. Traps that have been eating your time

- **Provider roulette** (§5) — stop.
- **Metaphysics over product** — consciousness / autopoiesis / φ-convergence / 7-layer
  metacognition is impressive and is *not* what customers pay for. It's been a place to hide
  from the unglamorous product work.
- **No ground map** → fixed: read `REPO_MAP.md` (what's real/dead) and run `scripts/ground-truth.sh`
  at the start of every session (branch · drift from main · unpushed · membrane · live).
- **Frozen files** — `sovereign-omega-v2/python/{gate,dna,router}.py` are SHA-pinned; don't edit
  without `/guardian`. Verify: `cd sovereign-omega-v2 && node scripts/verify-hashes.mjs`.
- **Heavy hooks** — `post-write.sh` runs typecheck after every `.ts` edit; `pre-commit-gate.sh`
  runs full Gate 8 on every commit. On an 8 GB box this is the sluggishness.
- **node_modules were committed** (21k files) → removed this session; repo is 1,649 real files.

---

## 10. Where everything is (pointers)

- Map of the whole repo: **`REPO_MAP.md`** · Operating loop: **`WORKFLOW.md`** ·
  Behavioral rules: top of **`CLAUDE.md`**.
- Money: `hub/src/components/PricingPage.tsx`, `supabase/functions/verify-paypal/index.ts`.
- Tools: `hook-generator/`, `platform-picker/`, `content-calendar/`, shared lib `packages/shared/`.
- Agents/platform: `sovereign-omega-v2/python/bridge.py` (`/platform/*`), live at
  `aegis-vertex.aegisomega.com`.
- Build one tool: `cd hook-generator && VITE_DASHSCOPE_API_KEY=… npm run build && npx vite preview`.
- Session sense-organ: `bash scripts/ground-truth.sh`.
