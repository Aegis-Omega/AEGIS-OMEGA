# AEGIS Ω — Deployment Guide

**Canonical payment provider:** Lemon Squeezy  
**Branch:** `claude/aegis-setup-Lx7Ji`

---

## Canonical Production URL Map

| App | Production URL | Vercel fallback (staging only) |
|-----|---------------|-------------------------------|
| Hub | https://aegisomega.com | https://aegis-hub.vercel.app |
| Platform Picker | https://platform.aegisomega.com | https://platform-picker.vercel.app |
| Hook Generator | https://hooks.aegisomega.com | https://hook-generator.vercel.app |
| Content Calendar | https://calendar.aegisomega.com | https://content-calendar.vercel.app |

> `.vercel.app` URLs are staging/fallback only. Set Lemon Squeezy redirect URLs and product env vars to the `aegisomega.com` domains above.

---


## Step 0 — Release Preflight

Run the non-interactive deployment readiness check before touching production. It verifies the full-stack app surface, required configuration files, unresolved merge-conflict markers, and optional production secrets.

```bash
bash scripts/prepare-deployment.sh
bash scripts/prepare-deployment.sh --build --docker-config
```

For a launch-blocking check that requires payment and AI-provider secrets to be present in the shell:

```bash
export DASHSCOPE_KEY=sk-XXXXXXXXXXXXXXXX
export VITE_LS_LINK_SINGLE=https://...
export VITE_LS_LINK_STARTER=https://...
export VITE_LS_LINK_FULL=https://...
bash scripts/prepare-deployment.sh --require-secrets --build --docker-config
```

> **HALT:** Do not deploy while the preflight reports unresolved conflict markers, missing app manifests, missing production secrets in `--require-secrets` mode, or failing builds.

## Step 1 — Deploy Product Apps

```bash
export DASHSCOPE_KEY=sk-XXXXXXXXXXXXXXXX
export VITE_LS_LINK_SINGLE=https://...
export VITE_LS_LINK_STARTER=https://...
export VITE_LS_LINK_FULL=https://...
bash scripts/deploy-products.sh
```

The deployment script builds each commercial product locally, runs the release preflight, deploys to Vercel production, and prints the canonical `aegisomega.com` target for each app.

For each project in the Vercel dashboard:
1. **Settings → Environment Variables** — add variables from the app's `.env.example`
2. **Settings → Security → IP Allowlist** — remove all restrictions (must be empty for public access)
3. **Settings → Deployment Protection** — set to **Disabled**
4. Redeploy after env var changes (Deployments → Redeploy)

---

## Step 2 — Set the DashScope API Key

Each product app needs `VITE_DASHSCOPE_API_KEY` for AI calls.

- **Vercel → project → Settings → Environment Variables**
- `VITE_DASHSCOPE_API_KEY` = your DashScope `sk-` key
- `VITE_DASHSCOPE_MODEL` = `qwen-plus`

**Get your key:** dashscope.aliyun.com → Console → API Keys  
Format: `sk-XXXXXXXXXXXXXXXX` (must start with `sk-`, not `LTAI...`)

---

## Step 3 — Set Up Lemon Squeezy Products

Create products at **app.lemonsqueezy.com**:

| Product | Price | Success redirect |
|---------|-------|-----------------|
| Single tool | $19 | `https://aegisomega.com/success?order_id={order_id}` |
| Starter (any 2) | $29 | `https://aegisomega.com/success?order_id={order_id}` |
| Full Toolkit (all 3) | $39 | `https://aegisomega.com/success?order_id={order_id}` |

After creating products, copy the **checkout URLs** into the hub's Vercel environment variables:
- `VITE_LS_LINK_SINGLE`
- `VITE_LS_LINK_STARTER`
- `VITE_LS_LINK_FULL`

---

## Step 4 — Configure Supabase Edge Functions

Deploy the purchase webhook and access-restore functions:

```bash
cd hub
supabase functions deploy ls-webhook
supabase functions deploy restore-access
```

Set secrets in the Supabase dashboard (or via CLI):
```bash
supabase secrets set LS_WEBHOOK_SECRET=<from Lemon Squeezy dashboard>
supabase secrets set GRANT_SECRET=aegis-omega-v1
```

The `ls-webhook` function records purchases. `restore-access` re-issues grant tokens for returning buyers.

---

## Step 5 — Public Access Verification

**Run this before any launch announcement.**

### Vercel settings check (all four projects)
- Settings → Security → IP Allowlist: **empty**
- Settings → Deployment Protection: **Disabled**

### HTTP verification

```bash
curl -o /dev/null -s -w "%{http_code}" https://aegisomega.com          # expect 200
curl -o /dev/null -s -w "%{http_code}" https://platform.aegisomega.com  # expect 200
curl -o /dev/null -s -w "%{http_code}" https://hooks.aegisomega.com     # expect 200
curl -o /dev/null -s -w "%{http_code}" https://calendar.aegisomega.com  # expect 200
```

| URL | Expected | Failure condition |
|-----|----------|------------------|
| aegisomega.com | 200 | 403 / auth wall / Vercel protection screen |
| platform.aegisomega.com | 200 | 403 / auth wall |
| hooks.aegisomega.com | 200 | 403 / auth wall |
| calendar.aegisomega.com | 200 | 403 / auth wall |

### Browser smoke tests
- **Hub** — page loads, no access block, "Enter the System" CTA visible
- **Platform Picker** — loads, AI call returns results with valid DashScope key
- **Hook Generator** — loads, generates hooks
- **Content Calendar** — loads, generates calendar

> **HALT:** Do not announce launch or share URLs publicly while any app returns `403`, an authentication wall, or any Vercel-owned access block.

---

## Pricing
- Platform Picker: **$19** | Hook Generator: **$19** | Content Calendar: **$19**
- Any 2: **$29** | All 3 (Full Creator AI Toolkit): **$39**
