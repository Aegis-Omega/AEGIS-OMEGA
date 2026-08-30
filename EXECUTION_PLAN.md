# Execution Plan — from here to everything live and earning

Ordered by dependency: each track unblocks the next. Every step has a **DONE** check —
nothing counts as done by assertion. Pair this with `HANDOFF.md` (ground truth) and
`REPO_MAP.md` (what's real/dead).

---

## Track 0 — Get onto a machine where it can actually RUN (do this first)

The cloud sandbox blocks the model host (`dashscope.aliyuncs.com`), so tools render but
can't generate here. Your own machine has open network + your keys.

- Teleport this session local: `claude --teleport` (pick this session), or clone the branch
  `claude/anthropic-compliance-docs-df4ogq`.
- **DONE:** `cd hook-generator && VITE_DASHSCOPE_API_KEY=<key> npm run dev` → the localhost URL
  both **renders and generates a real batch of hooks**. (The render bug is already fixed; the
  only thing that was missing here was network.)

Everything below is blocked on this. It's not a mystery step — it's a checklist item.

---

## Track 1 — Close the money loop (the part that actually pays)

Depends on Track 0.

1. **Decide the key model** (the one real cost decision):
   - *Buyer brings their own AI key* — zero cost/exposure to you, ship tonight, lower conversion.
   - *Your key behind a server proxy with a HARD spend cap* — smoother for buyers, a few hours
     more, and the cap is mandatory so it can never become another runaway bill.
   - **DONE:** decision written down.
2. If server-proxy: route tool inference through `supabase/functions/chat` (already a
   server-side Qwen proxy) with a hard monthly cap. **DONE:** browser Network tab shows the tool
   generating with **no API key in the bundle**.
3. **Deploy all 3 tools** (`vercel --prod` per product, root dir set per product).
   **DONE:** 3 public URLs that render + generate.
4. **Prove a real purchase** in PayPal **live** mode (verify `PAYPAL_MODE=live` in Supabase
   secrets — sandbox ≠ real money): buy Operator → `verify-paypal` captures $48 → mints key →
   key unlocks the tool. **DONE:** a real row in `api_key_store` from a live capture, key works.

At the end of Track 1 you have a closed loop: stranger → pays → gets working tool. That is the
whole game most of your system has been hiding.

---

## Track 2 — Make the agents real, not theater (optional for first revenue)

Depends on Track 0; not required for Track 1.

1. Honest baseline (verified this session): demo mode = the same templated string per
   "department"; live mode = **one** Claude call role-playing 39 depts. Decide what "agent"
   means for a buyer.
2. Pick **one** mode (e.g. `gtm`) and make live mode produce a genuinely differentiated, useful
   **deliverable** — real per-domain output, ideally a concrete artifact (a doc/plan file), not
   a paragraph describing one. **DONE:** a stranger reads the output and says "that's worth $X."
3. Wire the `aegis` CLI / `aegis-omega` SDK (`packages/aegis-py`) so it's drivable.
   **DONE:** `aegis collaborate "<objective>" --mode gtm --key <key>` returns the real deliverable.

---

## Track 3 — Get it onto `main` (stop stranding work)

- PR #153: take the SDK/tests, **DROP the Stripe swap** (Stripe can't work in Bosnia; PayPal can).
- PR #156: the compliance/docs + tonight's render & CI fixes.
- Decide the 3 tools: keep (record binding) or remove (record binding) — end the 15× churn.
- **DONE:** `git rev-list --count origin/main..HEAD` = 0 on your active branch; `main` reflects reality.

---

## Track 4 — Distribution (only you can do this — it's the real bottleneck)

No architecture replaces this. Revenue lives here, not in code.

- One niche. One promise ("give me X, get Y, $19"). One link (your deployed tool).
- Put it in front of **50 people** in that niche — posts, DMs, a launch. **DONE:** 50 humans
  saw it; ≥1 paid.

---

## The immediate next action

**Track 0.** Teleport local, confirm one tool generates on localhost. One thing. The rest is a
checklist, not a wall.
