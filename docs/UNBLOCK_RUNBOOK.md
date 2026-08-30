# Unblock runbook — the three broken identity bindings

**Diagnosis (2026-07-26).** Every recurring failure in this project traces to one class of
defect: an identity/credential binding that points at a name which no longer matches. None of
them is a code defect. All three require operator console access and cannot be done by an
agent — that is why repeated agent sessions failed to resolve them.

Order matters only in that #2 is the one that produces revenue. Do #2 first if you do only one.

---

## 1. Cloud Run deploys — GCP Workload Identity (≈5 min)

**Symptom:** `.github/workflows/deploy.yml` fails at the GCP auth step on every run:
`"The given credential is rejected by the attribute condition."`
Auto-deploy is currently `workflow_dispatch`-only (billing safety), so this is silent.

**Cause:** the Workload Identity provider's `attributeCondition` is pinned to a repo identity
that no longer matches. The repo now resolves as `Aegis-Omega/AEGIS-OMEGA`. GCP-side config —
not in the repo, not in terraform.

**Values:** `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` are in
GitHub → Settings → Secrets, or GCP → IAM → Workload Identity Federation.

```bash
PROJECT_NUMBER=$(gcloud projects describe aegisomegav1 --format='value(projectNumber)')

# 1a. confirm the stale pin
gcloud iam workload-identity-pools providers describe <PROVIDER> \
  --project=aegisomegav1 --location=global --workload-identity-pool=<POOL> \
  --format='value(attributeCondition)'

# 1b. repoint at the current repo
gcloud iam workload-identity-pools providers update-oidc <PROVIDER> \
  --project=aegisomegav1 --location=global --workload-identity-pool=<POOL> \
  --attribute-condition="assertion.repository=='Aegis-Omega/AEGIS-OMEGA'"

# 1c. fix the service-account binding
gcloud iam service-accounts add-iam-policy-binding <SA_EMAIL> \
  --project=aegisomegav1 --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/<POOL>/attribute.repository/Aegis-Omega/AEGIS-OMEGA"
```

**Verify:** re-run the failed "Deploy to Cloud Run" workflow. Auth step passes → bridge deploys.

---

## 2. Revenue path — PayPal client id (≈5 min) ← do this one first

**Symptom:** the pricing page renders red text `PayPal not configured — set VITE_PAYPAL_CLIENT_ID`
instead of buy buttons. No customer has ever been able to complete a purchase.

**Cause:** `hub/src/components/PricingPage.tsx:13` reads `import.meta.env.VITE_PAYPAL_CLIENT_ID`
and falls back to `''`; line 506 renders the error state. The variable is **not set in the Vercel
`hub` project**. Code is correct; the environment is empty.

**Fix:**
1. Vercel → project `hub` → Settings → Environment Variables → add
   `VITE_PAYPAL_CLIENT_ID` = PayPal **live** Client ID (Production scope), all environments.
2. Redeploy `hub` (env vars are baked at build time — a redeploy is required, not just a save).
3. Supabase → project secrets → confirm `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`,
   `PAYPAL_MODE=live`. Backend `verify-paypal` is live v5 and expects these.

**Verify:** load the deployed pricing page — buttons render instead of the red notice. Then run
one real low-value purchase end to end and confirm the entitlement lands. Until that single
transaction completes, the revenue path is unproven regardless of what the UI shows.

---

## 3. Google Payments card verification (≈2 min)

**Symptom:** billing failures / card not usable.

**Cause:** the Google Payments verification code for Mastercard `••8780` was issued
2026-07-21 with a 3-day expiry and lapsed unverified.

**Fix:** Google Payments → payment methods → re-issue and enter the verification code.

---

## Why this took so long to find

The three defects present as unrelated symptoms (CI red, no sales, billing errors) across three
different vendors, and each one is invisible from inside the repository. Agent sessions
repeatedly investigated the code — which is correct — and therefore found nothing. The failing
component was always the binding between an identity and a name, held in a provider console.

**Rule to carry forward:** when a failure message names a *credential*, an *attribute condition*,
or an *unset environment variable*, stop reading code. The defect is in a console, and it needs
operator hands.
