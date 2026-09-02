---
name: gcp-wif
description: Diagnose and repair AEGIS Google Cloud Workload Identity Federation for GitHub Actions. Use for GCP auth, WIF, OIDC, Cloud Run deploy authentication, GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_SERVICE_ACCOUNT, unauthorized_client, or attribute-condition failures.
---

# AEGIS GCP WIF — Keyless, ID-Bound

Canonical project: `aegisomegav1`

Canonical GitHub identity:

- repository: `Aegis-Omega/AEGIS-OMEGA`
- repository ID: `1095915905`
- owner ID: `288768655`

## Invariants

1. GitHub Actions authentication is WIF/OIDC. Do not ask for or create a long-lived Google service-account key.
2. `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` are federation identifiers, not private key material.
3. Trust immutable GitHub IDs, not repository names that can change.
4. No Cloud Run deployment follows directly from an auth repair. Establish read-only project access first.
5. Never call WIF GREEN from secret presence alone. Require a successful STS token exchange at the exact workflow head.

## Current established failure

PR #397 `GCP WIF Read-Only Preflight` proves:

- GitHub OIDC issuance succeeds;
- repository ID is `1095915905`;
- owner ID is `288768655`;
- the provider and service-account identifiers are present;
- both pull-request and push OIDC arms fail at Google STS with `unauthorized_client: The given credential is rejected by the attribute condition.`

This falsifies an event-specific `sub`/`ref` explanation. Treat the provider attribute policy as the active boundary.

## Recovery

Read `docs/GCP_WIF_KEYLESS_RECOVERY.md`.

Run the repair planner in default read-only mode:

```bash
bash scripts/gcp-wif-repair-plan.sh
```

Apply is forbidden unless the operator explicitly authorizes GCP IAM mutation. The script itself additionally requires:

```bash
AEGIS_APPROVE_GCP_IAM_MUTATION=YES bash scripts/gcp-wif-repair-plan.sh --apply
```

Target provider policy:

```text
assertion.repository_owner_id=='288768655' && assertion.repository_id=='1095915905'
```

Target custom mappings:

```text
attribute.repository_id=assertion.repository_id
attribute.repository_owner_id=assertion.repository_owner_id
```

Preserve `google.subject=assertion.sub` and unrelated existing mappings.

## Verification order

`OIDC_ISSUED -> STS_ACCEPTED -> PROJECT_READ -> GCS_BUCKET_CENSUS -> OBJECT_DISCOVERY`

Anything before `STS_ACCEPTED` is not GCP access.
