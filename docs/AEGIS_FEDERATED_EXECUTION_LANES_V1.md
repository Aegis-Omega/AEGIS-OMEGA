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
