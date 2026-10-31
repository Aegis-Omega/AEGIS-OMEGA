# AEGIS Ω Federated Execution Lanes V1

Status: **DRAFT / source integration**, not provider admission. Authority effect: **NONE**. No automatic deployments, new cloud instances, credential reads, or paid jobs.

## One broker, multiple substrates

The existing `sovereign-omega-v2/src/sovereignty/provider-mesh.ts` is the common broker and remains the source of truth for declared capabilities. The added generic providers are `azure-devops-pipelines`, `gitlab-ci`, `github-codespaces`, `vercel-sandbox`, `microsoft-azure` and `digitalocean`. Provider descriptors are **not** account inventory, entitlement, approval or evidence of a currently callable runner.

`buildProviderMeshSnapshotV1` + `selectProviderV1` already support deterministic cross-provider selection, evidence hashes, request-specific capabilities, observation generations and fail-closed freshness checks. Only a successful terminal durable execution with a terminal receipt hash can create `OBSERVED_AVAILABLE`. Historical pipeline success on another commit does not prove this PR's head is verified.

| Substrate | Verified source-bound discovery | Current authority |
| --- | --- | --- |
| Azure DevOps | Microsoft invitation dated 2026-07-19 identifies **https://dev.azure.com/aegisomega**; project ID, pipeline ID, OAuth/ARM API access, service connections and free parallel-job quota unverified. | UNKNOWN / no start |
| GitLab CI | Existing project **aegis-omega-group/AEGIS-OMEGA**, project ID **84781556**; historical pipeline **2953906140** SUCCEEDED at source **69cbb9b3…**, 2026-10-16. | Historical source only; current PR head not verified |
| GitHub Actions | **Aegis-Omega/AEGIS-OMEGA** PR #569 has queued/pending workflows. | Queue state is not evidence of runnable capacity |
| GitHub Codespaces | Historical codespaces identified, live instance status UNKNOWN. Repo devcontainer JSON repaired on PR #569, not necessarily main. | No active terminal access |
| Vercel Sandbox | Named **aegis-optimus-workbench-20261031** exists with snapshot, session stopped. | STOPPED; do not resume without hard cost assurance |
| Supabase Edge | Existing **aegis-omega** project and `provider-router`; actual SQL selector `select_provider_runtime_v1` already used read-only. | Observed availability must be refreshed; not execution authorization |
| Cloudflare Worker | Existing `aegisomega` Worker verified; quota and billing hard stop not established. | No new paid job |
| DigitalOcean | Connected read-only API returned **0 droplets** and account balance zero on 2026-10-31. | No existing compute |
| Hugging Face Jobs | Connected Jobs list reported no currently running jobs. | No running compute; entitlement UNKNOWN |
| AWS | Read-only AWS account observations exist; insufficient credit / least-privilege proof. | HOLD, no paid workload |

## Azure Pipelines opt-in

The root `azure-pipelines.yml` is a **manual-only, network-free application-test definition** with disabled push/PR triggers. It executes only if a separate, authorized Azure DevOps project administrator registers it and explicitly starts it after checking parallel-job entitlement and cost limits. It uses `checkout: self` and `persistCredentials: false`; it never deploys or calls paid models. No Azure Pipeline has been registered or executed by adding this file.

Existing GitHub `Sovereignty Contracts` adds two local regression gates: provider federation (Vitest) and Azure YAML safeties (Python). Every provider remains `authority_effect: NONE` until the existing Automaton-3 and independent operator authorization process admits a specific action.

## No synthetic proof

Never synthesize `OBSERVED_AVAILABLE` from an invitation, a connector installation, a cloud account, a stopped sandbox or a historical runner. Sample `OBSERVED_AVAILABLE` states in unit tests are **hypothetical test fixtures** only. The production Supabase runtime selector and the GitHub source broker are distinct surfaces; adding providers to the Git catalog does not silently update the database's policy or production state. This PR intentionally changes neither.

## Minimum real follow-up

Read Azure DevOps **project and pipeline IDs, repository service connection, and parallel-job entitlement** through an authorized Azure DevOps connection; inspect without starting or billing. Then, once a terminal execution receipt at an exact requested commit exists, translate it to the existing ProviderObservationV1 and run the *same* selector that handles GitLab, GitHub and Vercel. No new standalone optimizer, user database, or fork is required.


## Executed-job GitLab adapter V1.1

`src/sovereignty/provider-adapters/gitlab-ci.ts` consumes a **sanitized pair** of GitLab REST pipeline and job responses, obtained by a trusted, authenticated caller using the same `project_id`. The adapter checks `pipeline_id = job_pipeline_id`, `pipeline_head_sha = job_head_sha = expected_head_sha`, terminal statuses, a positive assigned `runner_id`, and actual start/end timestamps. If any of these is absent or mismatched, output is `UNKNOWN` with zero observed capabilities. The domain-separated SHA-256 is a **local integrity checksum**, not a GitLab signature or independently authenticated REST transcript. A failed workload that actually ran is valid evidence of runner substrate use, not successful workload execution.

2026-10-31 read-only connector witness: project `84781556`, pipeline `2953906140` status `success` (Oct 16), job `17223279657` status `success`, runner `54907241`, pipeline and job source `69cbb9b398c8fe036ed340e37fb630872d8c0706`. This is *historical* and will produce `UNKNOWN` when the selector's trusted caller requires any other SHA, including PR #569. Unit tests preserve this mismatch gate, and the existing Sovereignty Contracts GitHub Actions workflow runs them. No GitLab runner is triggered, no GitLab branch is pushed, and production observations remain unchanged.

**HOLD:** Executed GitLab job metadata can establish an observed substrate at a specified source, but it is not a signed attestation, successful execution of the caller's task, current billing entitlement, or privilege grant. Caller must independently authenticate the GitLab responses and enforce separate operator authority.

## Azure DevOps Run + Timeline evidence adapter V1.2

The exact-source, network-free adapter `src/sovereignty/provider-adapters/azure-devops.ts` normalizes an independently authenticated pair of Azure DevOps REST reads: [Pipelines Runs Get](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/get?view=azure-devops-rest-7.1) and [Build Timeline Get](https://learn.microsoft.com/en-us/rest/api/azure/devops/build/timeline/get?view=azure-devops-rest-7.1). A trusted caller must bind both requests to the **same organization/project**, the same pipeline/build/run ID, and the exact expected `resources.repositories.self.version` Git SHA. Only a completed terminal run with an executed `Job` timeline record, real `workerName`, and valid start/finish timestamps can emit an `OBSERVED_AVAILABLE` metadata observation. Failed jobs that actually ran can establish *runner substrate usage*, not successful task execution.

This adapter **does not fetch** Azure records or authenticate their origin. Caller-supplied fields are untrusted until independently retrieved and verified; its SHA-256 is a locally generated integrity checksum, not an Azure signature. The 11 new Vitest scenarios are synthetic fixtures (not proof that `aegisomega` has any Azure pipeline or free parallel jobs). The root Azure YAML remains manual-only; neither Azure pipelines nor production observations have been created or triggered. Separate operator, cost, and Automaton-3 gates still apply. Azure org invitation `https://dev.azure.com/aegisomega` is the only independently confirmed Azure DevOps organization fact here; project/pipeline IDs and entitlements remain **UNKNOWN**.
