---
name: enterprise
description: Anthropic Enterprise + Google Cloud integration for AEGIS Omega. Covers activating Anthropic Enterprise on the account, wiring the Claude API as a constitutional inference backend, connecting Google Cloud services (Cloud Run, Secret Manager, Artifact Registry, IAM/WIF), and adding the claude-api skill. Invoked when the user asks about "enterprise", "Anthropic API", "Google Cloud", "Claude API", "connect GCP", or "how do I use Claude in production".
---

# Enterprise & Cloud Integration Skill

**Epistemic Tier: T2** — engineering configuration, not yet empirically validated on this account.

---

## Part 1: Anthropic Enterprise

### What enterprise gives you
- Higher rate limits (RPM/TPM)
- claude-opus-4-8 / claude-sonnet-4-6 at scale
- Usage tracking per workspace/team
- SSO (SAML/SCIM) for team management
- Extended context (200K tokens on Opus/Sonnet)
- Priority API access

### Check approval status
Go to: `https://console.anthropic.com` → **Usage** tab
- If you see workspace quotas and team management → **enterprise is active**
- If you see a waitlist message → **pending approval**

### Activate on approval
1. Log in at `console.anthropic.com` with the account that requested enterprise
2. **Settings → Billing** — upgrade prompt will appear
3. **Settings → API Keys** → create a new key scoped to the AEGIS workspace
4. Copy the key — it will not be shown again

### Store the key (NEVER commit it)
```bash
# For local dev:
echo "VITE_CLAUDE_API_KEY=sk-ant-..." >> hub/.env
echo "VITE_CLAUDE_API_KEY=sk-ant-..." >> sovereign-omega-v2/.env

# For Cloud Run (preferred — no secrets on disk):
gcloud secrets create anthropic-api-key --replication-policy automatic
echo -n "sk-ant-your-key" | gcloud secrets versions add anthropic-api-key --data-file=-

# For Vercel:
vercel env add VITE_CLAUDE_API_KEY production
```

---

## Part 2: Claude API as Constitutional Backend

AEGIS already has the multi-backend inference router (`packages/shared/lib/inference-router.ts`).
The `claude` backend is implemented — it just needs `VITE_CLAUDE_API_KEY` to activate.

### How routing works
```
DashScope (Qwen)  → first attempt (fast, cheap)
Ollama (local)    → second attempt (if VITE_OLLAMA_BASE_URL set)
Claude            → third attempt (if VITE_CLAUDE_API_KEY set)
CL-Ψ bridge       → fourth attempt (if VITE_BRIDGE_URL set)
```

Every call, regardless of backend, produces a `ConstitutionalAuditRecord`:
```typescript
{
  call_id: string,          // SHA-256(timestamp + prompt_hash)
  backend: BackendType,     // which backend answered
  chain_hash: string,       // chains to previous call — tamper-evident
  ccil_valid: boolean,      // CCIL-Ψ constitutional constraint check
  is_replay_reconstructable: true
}
```

### Make Claude the primary backend
```bash
# In hub/.env:
VITE_CLAUDE_API_KEY=sk-ant-...
VITE_CLAUDE_MODEL=claude-sonnet-4-6   # or claude-opus-4-8 for premium

# Remove or leave unset to keep Qwen primary:
# VITE_DASHSCOPE_API_KEY=...  (if unset, DashScope fails → Claude is tried)
```

### Test the Claude backend locally
```bash
cd hub && npm run dev
# Open browser → any product → make an AI call
# Check ConstitutionalAuditRecord in localStorage:
# localStorage.getItem('aegis_constitutional_ledger_v1')
# → { chain_hash: "...", total_calls: N, ... }
# audit.backend should be "claude"
```

### Wire Claude as the ONLY backend (production sovereign mode)
```typescript
// In packages/shared/lib/inference-router.ts,
// reorder BACKEND_CHAIN to put claude first:
const BACKEND_CHAIN: Array<[BackendType, BackendFn]> = [
  ['claude',     callClaudeBackend],
  ['dashscope',  callDashScopeBackend],
  ['ollama',     callOllamaBackend],
  ['cl-psi',     callCLPsiBackend],
]
```

---

## Part 3: Google Cloud Setup

### Prerequisites
```bash
gcloud auth login                         # authenticate
gcloud config set project <PROJECT_ID>    # your GCP project
gcloud config set run/region europe-west3 # AEGIS region
```

### Enable required APIs
```bash
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  cloudbuild.googleapis.com
```

### Create Artifact Registry (container images)
```bash
gcloud artifacts repositories create aegis \
  --repository-format docker \
  --location europe-west3 \
  --description "AEGIS service images"

# Authenticate Docker:
gcloud auth configure-docker europe-west3-docker.pkg.dev
```

### Service Account + WIF (no long-lived keys in CI)
```bash
# Create service account for AEGIS deployments:
gcloud iam service-accounts create aegis-deployer \
  --display-name "AEGIS CI Deployer"

# Grant minimum required permissions:
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member "serviceAccount:aegis-deployer@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role "roles/run.developer"

gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member "serviceAccount:aegis-deployer@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role "roles/artifactregistry.writer"

# Workload Identity Federation (GitHub Actions — no key files):
gcloud iam workload-identity-pools create github \
  --location global \
  --display-name "GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --workload-identity-pool github \
  --location global \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri "https://token.actions.githubusercontent.com"

# Bind to the aegis-omega/AEGIS-- repo:
gcloud iam service-accounts add-iam-policy-binding \
  aegis-deployer@<PROJECT_ID>.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github/attribute.repository/aegis-omega/AEGIS--"
```

### Store Anthropic key in Secret Manager
```bash
# Store:
echo -n "sk-ant-..." | gcloud secrets versions add anthropic-api-key --data-file=-

# Grant Cloud Run access to the secret:
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --role roles/secretmanager.secretAccessor \
  --member "serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com"
```

### Deploy Python bridge with Anthropic key from Secret Manager
```bash
gcloud run deploy python-bridge \
  --source sovereign-omega-v2 \
  --region europe-west3 \
  --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest" \
  --set-env-vars "CORRUPTION_THRESHOLD=0"
```

---

## Part 4: Connect Claude API Skill (claude.ai/code Agent SDK)

The Claude API skill (`claude-api`) is already listed in the available skills.
When enterprise is active, the following patterns unlock:

### Prompt caching (enterprise: 90% cost reduction on repeated context)
```python
# In python/bridge.py — add cache_control to constitutional system prompts:
messages = [
  {
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": CONSTITUTIONAL_SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"}  # cached for 5 minutes
      },
      {
        "type": "text",
        "text": user_message
      }
    ]
  }
]
```

### Extended thinking (enterprise: claude-opus-4-8)
```python
response = anthropic.messages.create(
  model="claude-opus-4-8",
  max_tokens=16000,
  thinking={
    "type": "enabled",
    "budget_tokens": 10000  # thinking budget
  },
  messages=messages
)
```

### Batch API (enterprise: async, 50% cheaper, large volumes)
```python
# For content calendar generation at scale:
batch = anthropic.messages.batches.create(
  requests=[
    {"custom_id": f"week-{i}", "params": {"model": "claude-sonnet-4-6", ...}}
    for i in range(4)
  ]
)
# Poll: anthropic.messages.batches.retrieve(batch.id)
```

---

## Part 5: The GitHub Actions secret wiring

Add to GitHub repository secrets (Settings → Secrets → Actions):

```
ANTHROPIC_API_KEY       sk-ant-...
VERCEL_TOKEN            from vercel.com → Account Settings → Tokens
GCP_WORKLOAD_IDENTITY_PROVIDER  projects/<NUM>/locations/global/workloadIdentityPools/github/providers/github-provider
GCP_SERVICE_ACCOUNT     aegis-deployer@<PROJECT_ID>.iam.gserviceaccount.com
```

The existing `deploy.yml` workflow already expects `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT`.

---

## Part 6: Validation

After wiring enterprise + GCP:

```bash
# 1. Verify Claude backend responds:
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-4-6","max_tokens":10,"messages":[{"role":"user","content":"ping"}]}'

# Expected: {"content":[{"type":"text","text":"pong"}],...}

# 2. Verify Cloud Run bridge:
curl https://python-bridge-<hash>-ew.a.run.app/health
# Expected: {"status":"ok","corruption_count":0,"t0_verdict":true}

# 3. Verify hub with Claude backend:
# Open hub → make an AI call → check:
# localStorage.getItem('aegis_constitutional_ledger_v1') → audit.backend === "claude"
```

---

## Constitutional note

```
L7: External APIs (Anthropic, GCP) are FIELD-scale dependencies.
    They do not modify governance state.
    They route through the constitutional inference chain.
    Every call produces a ConstitutionalAuditRecord.
    Every record is hash-chained.
    The external world enters through a constitutional boundary
    and exits through a constitutional boundary.

L6: Non-equivalence to remember:
    Having the API key ≠ Constitutional compliance.
    Constitutional compliance = every call hash-chained,
    CCIL-Ψ validated, and replay-reconstructable.
    The inference-router enforces this regardless of backend.
```
