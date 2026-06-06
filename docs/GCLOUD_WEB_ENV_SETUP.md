# Connecting Google Cloud to Claude Code + Deploying AEGIS

Three deploy paths, in order of how little local setup they need. You do **not**
need `gcloud` installed in the Claude Code web environment for paths 1 and 2.

---

## Path 1 — Cloud Build trigger (already exists, now fixed)

The `rmgpgab-aegis-hub-…` trigger in project `aegisomegav1` was failing with
*"could not find a valid build file."* Root cause (confirmed by Cloud Assist):
the trigger uses **`autodetect: true`**, which searches the **repository root**,
but the build files lived in subdirectories (`hub/cloudbuild.yaml`, `hub/Dockerfile`).

**Fix applied (repo-side, no gcloud needed):** a root [`cloudbuild.yaml`](../cloudbuild.yaml)
now exists. autodetect finds it, builds the hub (context `hub/`, `hub/Dockerfile`),
pushes to GCR, and deploys Cloud Run service `aegis-hub` in `europe-west3`. The red
check goes green on the next push.

**Cleaner alternative (your choice, needs gcloud once)** — point the trigger at the
hub config explicitly instead of relying on a root file:

```bash
# List triggers to get the ID
gcloud builds triggers list --project aegisomegav1 \
  --format="value(id,name)" | grep aegis-hub

# Point it at the hub build config (replace <TRIGGER_ID>)
gcloud builds triggers update <TRIGGER_ID> \
  --project aegisomegav1 \
  --build-config hub/cloudbuild.yaml
```

Both are compatible — an explicit `--build-config` overrides autodetect, so you can
keep the root file as a fallback or remove it after reconfiguring the trigger.

---

## Path 2 — GitHub Actions → Cloud Run via Workload Identity Federation (keyless)

This is the path that ships AEGIS on merge to `main` with **no service-account keys
and no local gcloud**. The workflow is committed at
[`.github/workflows/deploy-cloud-run.yml`](../.github/workflows/deploy-cloud-run.yml).
It is a no-op until you set the federation variables, so it never blocks CI.

### One-time GCP setup (run once, from any machine with gcloud — e.g. Cloud Shell)

```bash
PROJECT=aegisomegav1
POOL=github-pool
PROVIDER=github-provider
SA=deployer@${PROJECT}.iam.gserviceaccount.com
REPO=Aegis-Omega/AEGIS--

# 1. Create the deployer service account + grant deploy roles
gcloud iam service-accounts create deployer --project "$PROJECT"
for role in roles/run.admin roles/cloudbuild.builds.editor \
            roles/artifactregistry.writer roles/iam.serviceAccountUser \
            roles/storage.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${SA}" --role="$role"
done

# 2. Create the Workload Identity Pool + GitHub OIDC provider
gcloud iam workload-identity-pools create "$POOL" \
  --project="$PROJECT" --location=global --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --project="$PROJECT" --location=global --workload-identity-pool="$POOL" \
  --display-name="GitHub OIDC" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${REPO}'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# 3. Let the GitHub repo impersonate the deployer SA
PROJECT_NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --project="$PROJECT" --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}"

echo "WIF_PROVIDER = projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo "WIF_SERVICE_ACCOUNT = ${SA}"
```

### One-time GitHub setup (Settings → Secrets and variables → Actions → Variables)

| Variable | Value |
|----------|-------|
| `GCP_PROJECT` | `aegisomegav1` |
| `GCP_REGION` | `europe-west3` |
| `WIF_PROVIDER` | the `projects/…/providers/github-provider` string printed above |
| `WIF_SERVICE_ACCOUNT` | `deployer@aegisomegav1.iam.gserviceaccount.com` |

After that, every push to `main` (or a manual **Run workflow**) authenticates via
OIDC and runs `gcloud builds submit --config cloudbuild.yaml` — keyless, auditable,
no keys to rotate. The `BUILD_CONFIG` input is validated against a fixed allow-list.

---

## Path 3 — Interactive gcloud inside the Claude Code web environment

If you want `gcloud` usable *inside this remote environment* (so the agent can run
deploys directly), configure it at the environment level — see
<https://code.claude.com/docs/en/claude-code-on-the-web>:

1. **Setup script** (runs at container start):
   ```bash
   curl -sSL https://sdk.cloud.google.com | bash > /dev/null
   echo 'source /root/google-cloud-sdk/path.bash.inc' >> ~/.bashrc
   ```
2. **Credentials** — prefer a short-lived federated credential over a key. If a key
   is unavoidable, store the service-account JSON as an environment **secret**
   (`GOOGLE_APPLICATION_CREDENTIALS` pointing at a file the setup script writes), and
   set the network policy to allow `*.googleapis.com`.

This is the only path that requires giving the environment standing GCP credentials,
so prefer Paths 1–2 (keyless / trigger-based) for production.

---

## Path 4 — Deploy the Agent Platform API as its own Cloud Run service

The platform backend (`vertex/serve.py`) is a **separate service** from the hub.
It exposes the 39 Mythos agents as a callable plane:

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /health` | public | liveness |
| `GET /metrics` | public | per-instance request/latency/error counters |
| `GET /platform/catalog` | public | all 39 agents + pricing tiers (discovery) |
| `POST /platform/collaborate` | **gated** | swarm collaboration (revenue / cognitive) |
| `POST /agents/run` | **gated** | single governed agent run |
| `POST /v1/messages` | **gated** | Anthropic-compatible governed gateway |
| `GET /v1/audit/certify` | public | chain integrity |

**Hardening (already in `serve.py`):** the gated routes require header
`x-api-key: $PLATFORM_API_KEY` **when** the `platform-api-key` secret is set
(catalog/health/metrics stay public for discovery). Per-IP rate limiting
(`RATE_LIMIT_PER_MIN`, default 60), a global JSON error handler, and structured
JSON access logs (→ Cloud Logging) are on by every request.

### Build context fix (required)

`vertex/cloudbuild.yaml` builds with **repo-root context + `-f vertex/Dockerfile`**
so the `agents/` package and `harness/skill_tree.json` land in the image. Without
this the `/platform/*` and `/agents/*` routes return 503. A root `.dockerignore`
keeps the upload small (excludes `node_modules`, rust `target/`, other frontends).

### One-time secret (so the gate is live)

```bash
# Create the platform API key secret (clients send it as x-api-key)
printf '%s' "$(openssl rand -hex 32)" | \
  gcloud secrets create platform-api-key --data-file=- --project aegisomegav1
```

### Deploy — option A: dedicated Cloud Build trigger (mirrors the hub trigger)

```bash
gcloud builds triggers create github \
  --project aegisomegav1 --region global \
  --name aegis-platform \
  --repo-owner Aegis-Omega --repo-name AEGIS-- \
  --branch-pattern '^claude/test-coverage-analysis-keTIk$' \
  --build-config vertex/cloudbuild.yaml

# fire it
gcloud builds triggers run aegis-platform --region global \
  --branch claude/test-coverage-analysis-keTIk
```

### Deploy — option B: keyless WIF workflow (already wired)

`.github/workflows/deploy-cloud-run.yml` allow-lists `vertex/cloudbuild.yaml`.
Once the WIF vars are set (Path 2), trigger it: **Actions → Deploy to Cloud Run
(WIF) → Run workflow → service = `vertex/cloudbuild.yaml`**.

### Verify (after deploy — service `aegis-platform`, region `us-central1`)

```bash
URL=$(gcloud run services describe aegis-platform --region us-central1 \
  --project aegisomegav1 --format='value(status.url)')

curl -s "$URL/health"
curl -s "$URL/platform/catalog" | jq '{agent_count, mythos_count}'   # → 39 / 39
curl -s "$URL/metrics" | jq '{requests_total, auth_enabled}'

# First end-to-end platform transaction (the swarm makes a revenue plan):
curl -s -X POST "$URL/platform/collaborate" \
  -H "x-api-key: $PLATFORM_API_KEY" -H 'content-type: application/json' \
  -d '{"mode":"revenue","objective":"Sell constitutional governance to AI labs"}' \
  | jq '{departments_collaborated, projection: .projection.tier, chain_valid}'
```

---

## Why this is constitutionally sound

Paths 1 and 2 keep deploy authority **outside** the agent runtime: the GitHub OIDC
token and the Cloud Build trigger are the deploy principals, not the automaton. This
preserves the constitutional separation — agents have no autonomous mutation authority
over production infrastructure. The deploy is replay-auditable (every build has a
`$COMMIT_SHA`), satisfying `AdaptivePower(T) ≤ ReplayVerifiability(T)` at the
deployment boundary.
