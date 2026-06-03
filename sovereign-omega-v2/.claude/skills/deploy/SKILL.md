---
name: deploy
description: Full production deployment workflow for the AEGIS ecosystem. Covers Vercel (hub, platform-picker, hook-generator, content-calendar), Cloud Run (aegisomega.com services), and the Python bridge. Invoked when the user says "deploy", "ship to prod", "push to Vercel", "go live", "release", or asks how to get any AEGIS product running in production.
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
npm install -g vercel   # once, globally
vercel login            # authenticate — uses tarikskalic33@gmail.com
```

### Deploy hub (aegisomega.com landing page)
```bash
cd hub
npm ci
npm run build           # must exit 0 — tsc -b && vite build

# Preview deploy (staging URL, no custom domain):
vercel

# Production deploy (hits aegisomega.com):
vercel --prod
```

Expected output:
```
✓ Deployed to Production
  https://aegisomega.com  (custom domain, DNS via Cloudflare)
  https://hub-one-kappa.vercel.app  (Vercel preview URL)
```

### Deploy commercial products
```bash
# Each product is an independent Vercel project:
cd platform-picker && npm ci && npm run build && vercel --prod
cd hook-generator  && npm ci && npm run build && vercel --prod
cd content-calendar && npm ci && npm run build && vercel --prod
```

### Environment variables (set in Vercel dashboard or via CLI)
```bash
# Per-product, set via dashboard: vercel.com → project → Settings → Environment Variables
# OR via CLI:
vercel env add VITE_DASHSCOPE_API_KEY production    # Qwen API key
vercel env add VITE_DASHSCOPE_MODEL production      # qwen-plus (default)
vercel env add VITE_BRIDGE_URL production           # optional: bridge proxy URL

# Hub-specific (optional — overlay live bridge telemetry):
vercel env add VITE_BRIDGE_URL production           # e.g. https://bridge.aegisomega.com
```

### Vercel project setup (first time only)
```bash
cd hub
vercel link    # links to existing project OR creates new
# Root Directory: hub
# Build Command: npm run build
# Output Directory: dist
# Framework: Vite
```

### Token-based deploy (CI / non-interactive)
```bash
# Export token (from vercel.com → Account Settings → Tokens):
export VERCEL_TOKEN="your_token_here"   # NEVER commit this

vercel --prod --yes --token "$VERCEL_TOKEN"
```

---

## 2. Cloud Run — Core AEGIS Services

**Domain:** `aegisomega.com` (Cloudflare DNS → Cloud Run)
**Region:** `europe-west3`
**GCP account:** `info@aegisomega.com`

### Authenticate
```bash
gcloud auth login
gcloud config set project <PROJECT_ID>   # find via: gcloud projects list
gcloud config set run/region europe-west3
```

### Deploy via GitHub Actions (preferred — no credentials on disk)
```bash
# This is automatic on push to main via WIF:
git push origin main   # triggers .github/workflows/deploy.yml
```

### Manual Cloud Run deploy
```bash
# Build and push container:
docker build -t europe-west3-docker.pkg.dev/<PROJECT>/aegis/<service>:latest .
docker push europe-west3-docker.pkg.dev/<PROJECT>/aegis/<service>:latest

# Deploy:
gcloud run deploy <service-name> \
  --image europe-west3-docker.pkg.dev/<PROJECT>/aegis/<service>:latest \
  --region europe-west3 \
  --allow-unauthenticated \
  --min-instances 1
```

### Services on Cloud Run
| Service | Port | Purpose |
|---------|------|---------|
| `python-bridge` | 7890 | Python governance bridge (bridge.py) |
| `sovereign-omega` | 8080 | TypeScript governance runtime |
| `studio` | 3001 | Observability studio (projection only) |

### Python bridge deploy
```bash
cd sovereign-omega-v2
# Bridge is containerized — Dockerfile at python/Dockerfile (create if missing):
gcloud run deploy python-bridge \
  --source . \
  --port 7890 \
  --region europe-west3 \
  --set-env-vars "CORRUPTION_THRESHOLD=0,EPOCH_FAILSAFE=true"
```

---

## 3. Domain & DNS (Cloudflare)

**DNS is managed at Cloudflare.** Do not modify DNS records without checking here first.

```
aegisomega.com     → Cloud Run (governance runtime)
hub.aegisomega.com → Vercel (hub landing page)
bridge.aegisomega.com → Cloud Run (Python bridge — only if making bridge public)
```

To verify:
```bash
curl -I https://aegisomega.com/health   # should return 200 from Python bridge
curl -I https://hub.aegisomega.com      # should return 200 from Vercel
```

---

## 4. Supabase — Payment Verification

Payment flows use Supabase edge functions to issue server-side tokens.

**Critical invariant:** Tokens MUST be minted server-side. Never client-side.
(Client-side minting was a critical vulnerability patched 2026-05-30.)

```bash
# Deploy edge functions:
supabase functions deploy verify-payment --project-ref <ref>
supabase functions deploy issue-token    --project-ref <ref>
```

---

## 5. Pre-Deploy Checklist

```
[ ] Gate 8 passes: npm run test && npm run typecheck && npm run build
[ ] verify-hashes.mjs exits 0 (frozen files intact)
[ ] No .env files staged: git status | grep env → empty
[ ] Vercel env vars set for the target environment
[ ] If touching payment flows: server-side token minting verified
[ ] Hub: npm run build exits 0 in hub/ directory specifically
[ ] VITE_BRIDGE_URL: either set correctly or unset (graceful fallback)
```

---

## 6. Rollback

```bash
# Vercel — instant rollback via dashboard or CLI:
vercel rollback <deployment-url>

# Cloud Run — traffic split or previous revision:
gcloud run services update-traffic <service> \
  --to-revisions <previous-revision>=100 \
  --region europe-west3
```

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
    The golden path must be tested manually — type checkers cannot do this.
```
