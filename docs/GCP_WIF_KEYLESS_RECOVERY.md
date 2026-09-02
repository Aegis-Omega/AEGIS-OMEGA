# GCP Workload Identity Federation — Keyless Recovery

Status: `PROVIDER_ATTRIBUTE_CONDITION_BLOCKED`

Authority: diagnostic and repair procedure only. No deployment authority is implied by this document.

## What is established

AEGIS CI uses Google Cloud Workload Identity Federation (WIF) with GitHub Actions OIDC. It does **not** require or use a long-lived Google service-account key file.

Project: `aegisomegav1`

Canonical GitHub identity:

- repository: `Aegis-Omega/AEGIS-OMEGA`
- immutable repository ID: `1095915905`
- repository owner: `Aegis-Omega`
- immutable owner ID: `288768655`

The repository was previously named `Aegis-Omega/AEGIS--` and retained repository ID `1095915905` through the rename.

## Machine-bound failure evidence

PR #397 added `.github/workflows/gcp-wif-preflight.yml`, a read-only diagnostic lane.

### Pull-request OIDC arm

Run `33657215159` established:

- both `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` identifiers are present;
- GitHub OIDC issuance succeeds;
- OIDC `repository = Aegis-Omega/AEGIS-OMEGA`;
- OIDC `repository_id = 1095915905`;
- OIDC `repository_owner_id = 288768655`;
- Google STS rejects the credential before project access with:

```text
unauthorized_client
The given credential is rejected by the attribute condition.
```

Receipt SHA-256: `73fadd37e8c05a88126a998cf63943d7b4cb5df27374cbee8b266d8a43508692`

### Push OIDC falsification arm

Run `33657666153` changed the event/ref/subject shape:

- `event_name = push`;
- `ref = refs/heads/ops/gcp-wif-preflight-v1`;
- `sub = repo:Aegis-Omega/AEGIS-OMEGA:ref:refs/heads/ops/gcp-wif-preflight-v1`.

Google STS returned the same `unauthorized_client / rejected by the attribute condition` error.

Receipt SHA-256: `8f5d23ec89519e8036062e9952394d540c9cc4fefdd9e365fea03addd0126d0f`

Therefore PR-event-specific `sub` or `ref` restrictions are not sufficient to explain the failure. The active blocker is the workload identity provider's attribute policy against the current GitHub identity.

Historical GitHub audit evidence also shows WIF authentication failures while the repository was still named `Aegis-Omega/AEGIS--`, so the rename is not assumed to be the sole historical cause.

## Why repository-name trust is deprecated

Historical AEGIS guidance mapped `attribute.repository=assertion.repository` and granted `roles/iam.workloadIdentityUser` to a principal set containing the old mutable repository name.

That design is brittle because repository names can change. Google Cloud's current WIF guidance exposes GitHub `repository_id` and `repository_owner_id`, and recommends immutable attributes for federation policy.

AEGIS canonical trust target is therefore:

```text
repository_id       = 1095915905
repository_owner_id = 288768655
```

The intended provider condition is:

```text
assertion.repository_owner_id=='288768655' && assertion.repository_id=='1095915905'
```

The intended custom mappings are additive to existing mappings:

```text
attribute.repository_id=assertion.repository_id
attribute.repository_owner_id=assertion.repository_owner_id
```

`google.subject=assertion.sub` must remain intact. Existing unrelated mappings must be preserved.

The service-account impersonation binding should use the immutable repository ID:

```text
principalSet://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/<POOL_ID>/attribute.repository_id/1095915905
```

## Fail-closed repair procedure

`scripts/gcp-wif-repair-plan.sh` is the canonical repair tool.

Default invocation is read-only:

```bash
export GCP_WORKLOAD_IDENTITY_PROVIDER='projects/<NUM>/locations/global/workloadIdentityPools/<POOL>/providers/<PROVIDER>'
export GCP_SERVICE_ACCOUNT='<SERVICE_ACCOUNT_EMAIL>'

bash scripts/gcp-wif-repair-plan.sh
```

The planner:

1. requires an already authenticated `gcloud` session;
2. verifies the provider belongs to `aegisomegav1`;
3. reads the current provider mapping and condition;
4. refuses an unexpected `google.subject` mapping;
5. preserves existing mappings and adds immutable repository/owner ID mappings;
6. prints the desired condition and principal set;
7. performs **no mutation** in default mode.

Applying the repair requires two explicit gates:

```bash
export AEGIS_APPROVE_GCP_IAM_MUTATION=YES
bash scripts/gcp-wif-repair-plan.sh --apply
```

Apply mode updates the OIDC provider, adds the immutable `roles/iam.workloadIdentityUser` binding, verifies the provider postcondition, and emits `gcp_wif_repair_receipt.json`.

It does not create a long-lived key and does not remove legacy IAM bindings automatically.

## Admission sequence

After an authorized IAM repair:

1. rerun `GCP WIF Read-Only Preflight`;
2. require `wif_auth = SUCCESS`;
3. require `project_read = SUCCESS`;
4. enumerate Cloud Storage buckets read-only;
5. only then inspect object names for sequencing inputs (`FASTQ/FQ`, `BAM`, `CRAM`, `VCF/BCF`, `FASTA/FNA` and compressed variants);
6. do not execute Cloud Run deployment merely because WIF authentication is repaired.

Until steps 1–3 are machine-green, GCP data discovery remains `BLOCKED_AT_WIF_PROVIDER_ATTRIBUTE_CONDITION`.
