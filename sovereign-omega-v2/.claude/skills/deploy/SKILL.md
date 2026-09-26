---
name: deploy
description: Full production deployment workflow for the AEGIS ecosystem. Covers Vercel, Cloudflare DNS/Worker, Supabase edge functions, and evidence-bound release verification. Invoked when the user says "deploy", "ship to prod", "push to Vercel", "go live", "release", or asks how to get any AEGIS product running in production.
---

# Deploy Skill

**Metacognitive Layer: L5 (Executive Function) + L7 (Self-model)**

Deployment is a membrane propagation event at FIELD scale. Before any production deployment, Gate 8 must pass — a component that fails its viability ring cannot be incorporated into the production membrane.

```
L7 pre-deploy invariant:
  node scripts/verify-hashes.mjs → exit 0
  Gate 8: npm run test && npm run typecheck && npm run build → exit 0

If either fails: T0_ABORT. Do not deploy.
```

---

## 1. Vercel — Commercial Products + Hub

**Products:** `hub`, `platform-picker`, `hook-generator`, `content-calendar`

### Prerequisites
```bash
npm install -g vercel
vercel login
```

### Deploy hub (aegisomega.com landing page)
```bash
cd hub
npm ci
npm run build

# Preview first:
vercel

# Production only after preview verification:
vercel --prod
```

Expected production surface:

```
https://aegisomega.com
```

The apex is served through Vercel. Do not point the apex back to legacy GCP/Cloud Run.

### Deploy commercial products
```bash
cd platform-picker  && npm ci && npm run build && vercel --prod
cd hook-generator   && npm ci && npm run build && vercel --prod
cd content-calendar && npm ci && npm run build && vercel --prod
```

### Environment variables

Use Vercel project environment settings or the CLI. Never commit tokens or secrets.

```bash
vercel env add VITE_DASHSCOPE_API_KEY production
vercel env add VITE_DASHSCOPE_MODEL production
vercel env add VITE_BRIDGE_URL production
```

### Token-based deploy

```bash
export VERCEL_TOKEN="..."
vercel --prod --yes --token "$VERCEL_TOKEN"
```

---

## 2. Cloudflare Worker — API Edge

The current API custom-domain owner is the Cloudflare Worker declared by `/wrangler.jsonc`.

Canonical custom domain:

```
aegis-vertex.aegisomega.com
```

The route is declared with `custom_domain: true`. Cloudflare provisions the certificate when the Worker custom-domain binding is active.

### Deploy

```bash
npx wrangler deploy
```

### Hard rule

Do **not** create or restore a legacy Cloud Run DNS mapping for `aegis-vertex.aegisomega.com`. A stale DNS record can conflict with the Cloudflare Worker custom-domain binding and reintroduce DNS/TLS failures.

---

## 3. Domain & DNS Control Plane

### Registrar and authoritative DNS

- Registrar: **Squarespace Domains**
- Authoritative DNS: **Cloudflare**
- Nameserver set: the active `olivia` / `remy` Cloudflare pair established on 2026-07-02
- Do not restore the stale `noor` / `west` delegation.

### Current canonical routing

```
aegisomega.com                  → Vercel apex (76.76.21.21)
www.aegisomega.com              → Vercel
platform.aegisomega.com         → Vercel
hooks.aegisomega.com            → Vercel
calendar.aegisomega.com         → Vercel DNS record exists; project attachment must still be verified
cockpit.aegisomega.com          → Vercel DNS record exists; project/certificate attachment must still be verified
aegis-vertex.aegisomega.com     → Cloudflare Worker custom domain
```

### OpenAI tenant-domain verification records

These records are verification-only and carry no AEGIS execution authority:

```
TXT _openai-site-verification.aegisomega.com
    openai-site-verification=zchKhAC2vSCoUTOKmlHN9tiwmpzfL81-vX2oA7-nG3c

TXT _cf-custom-hostname.aegisomega.com
    958133c2-046b-4684-b34e-08ac9a553228
```

Hosted verification is implemented by:

```
scripts/verify-openai-domain-dns.py
.github/workflows/openai-domain-dns-verification.yml
```

A DNS PASS proves public TXT visibility only. OpenAI Admin Console must independently transition the domain from pending to verified.

### DNS mutation rules

Before any mutation:

1. Resolve the intended hostname and current owner.
2. Confirm the target platform.
3. Preserve unrelated MX/SPF/DKIM records.
4. Never replace the entire Cloudflare zone for a single service change.
5. Never change nameservers unless the whole-zone migration is intentional and independently reviewed.
6. Record exact before/after values and a verification receipt.

---

## 4. Supabase — Payment Verification

Payment flows use Supabase edge functions to issue server-side tokens.

**Critical invariant:** Tokens MUST be minted server-side. Never client-side.

```bash
supabase functions deploy verify-payment --project-ref <ref>
supabase functions deploy issue-token    --project-ref <ref>
```

---

## 5. Pre-Deploy Checklist

```
[ ] Gate 8 passes: npm run test && npm run typecheck && npm run build
[ ] verify-hashes.mjs exits 0
[ ] No .env files staged
[ ] Exact candidate SHA recorded
[ ] Vercel env vars set for the target environment
[ ] Payment flows still mint tokens server-side
[ ] Hub build passes in hub/
[ ] Worker changes match wrangler.jsonc and custom-domain ownership
[ ] DNS changes, if any, preserve unrelated MX/SPF/DKIM records
[ ] Hosted DNS verification receipt captured when OpenAI domain verification is in scope
```

---

## 6. Rollback

### Vercel

```bash
vercel rollback <deployment-url>
```

### Cloudflare Worker

Roll back to a known-good Worker deployment/version or redeploy the known-good commit. Do **not** use a GCP/Cloud Run rollback as a substitute for the current Worker/Vercel architecture.

DNS rollback must restore the exact previous record values rather than recreate historical infrastructure from old documentation.

---

## 7. What "deploy" means constitutionally

```
L7: Deployment is membrane propagation at FIELD scale.
    The production system IS the organism.
    Deploying broken code = corrupting the organism's boundary.

L5: Gate 8 is not a pre-deploy ritual.
    It is the definition of "ready to deploy."
    A build that has not passed Gate 8 is not a build.
    It is a work in progress.

L6: Test pass ≠ Correctness.
    Gate 8 pass ≠ "the feature works."
    Deploy to staging. Observe. Then deploy to prod.
    The golden path must be tested manually.
```
