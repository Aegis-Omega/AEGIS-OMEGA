# GitHub Substrate Census v1 Implementation Plan

> **For agentic workers:** use TDD and exact-head verification. This plan extends PR #296; every commit moves the evidence subject.

**Goal:** Make AEGIS enumerate and distinguish the GitHub execution surfaces it actually has: current-tree workflows, declared runner requirements, action dependencies, workflow permissions/triggers, model/provider integration points, and separately supplied executed/historical observations.

**Architecture:** A pure stdlib Python parser scans `.github/workflows/*.yml|*.yaml` from the exact checked-out candidate and emits a deterministic `GITHUB_SUBSTRATE_MANIFEST_V1`. It never infers live runner registration from `runs-on`, and it never infers current-tree existence from historical workflow-run UI. A validator fails closed on deprecated GitHub Models integration, authority-sensitive mutable action pins, and malformed subject binding. Historical run observations and runner observations are a separate optional input class.

**Tech Stack:** Python 3.12 stdlib, GitHub Actions, JSON.

**Parent slice:** `docs/superpowers/specs/2026-08-22-epistemic-admission-kernel-v1-design.md`

## Global constraints

- Current-tree enumeration and historical workflow/run enumeration are separate universes.
- `runs-on` is a declared runner requirement, not proof that a runner is registered, online, idle, or used.
- An executed job log is an observation of the runner used for that run, not a complete registered-runner inventory.
- GitHub Models service status and GitHub Copilot model availability are distinct products.
- As of the implementation date, primary GitHub documentation says GitHub Models was fully retired on 2026-07-30; a current workflow using `actions/ai-inference` / `models: read` is therefore a deprecated integration candidate, not a working model surface.
- Model/provider outputs remain evidence only.
- New CI dependencies must use immutable action commit SHAs.
- The census gate gets `contents: read` only.

---

### Task 1 — RED falsifiers for universe separation

**Files**
- Create: `harness/tests/test_github_substrate.py`

**Tests**
1. A workflow fixture with `runs-on: [self-hosted, linux, gpu]` is reported under `declared_runner_requirements`; no `live_runners` field is synthesized.
2. A fixture with `uses: actions/checkout@v4` is classified `MUTABLE_REF`; a 40-hex action ref is `IMMUTABLE_COMMIT`.
3. A fixture with `permissions: models: read` and/or `uses: actions/ai-inference@v1` is flagged `RETIRED_GITHUB_MODELS_SURFACE`.
4. A historical observation naming a workflow absent from the scanned directory remains under `historical_workflow_observations` and does not enter `current_tree_workflows`.
5. Workflow name, trigger keys, permissions, `runs-on`, reusable/action uses, OIDC, attestations and artifact usage are deterministically extracted.
6. Manifest subject SHA is explicit and required.

Run before implementation:
`python -m unittest harness.tests.test_github_substrate -v`
Expected: RED because `harness.sdk.github_substrate` does not exist.

---

### Task 2 — Minimal deterministic census implementation

**Files**
- Create: `harness/sdk/github_substrate.py`
- Create: `scripts/inventory-github-substrate.py`
- Create: `scripts/validate-github-substrate.py`

**Interfaces**
- `scan_workflow_text(path: str, text: str) -> WorkflowSurfaceV1`
- `build_manifest(repo_root: Path, candidate_sha: str, historical_observations: list[dict] | None = None) -> dict`
- Manifest authority: `EVIDENCE_ONLY_NOT_RUNNER_REGISTRATION_AUTHORITY`

**Required manifest separation**
- `current_tree_workflows`
- `declared_runner_requirements`
- `action_dependencies`
- `provider_model_surfaces`
- `historical_workflow_observations`
- `registered_runner_inventory_status: NOT_CHECKED` unless separately supplied by an authorized runner-inventory source.

**Validation**
- exact candidate SHA must be non-empty;
- current workflow paths must be unique and sorted;
- no historical-only workflow may be promoted into current-tree set;
- retired GitHub Models integration is a blocking violation for current-tree workflow use;
- mutable third-party/action refs in authority-sensitive workflows are reported as supply-chain debt; v1 blocks only the dedicated census workflow from being mutable, while inherited debt is surfaced explicitly.

Run:
`python -m unittest harness.tests.test_github_substrate -v`
`python scripts/inventory-github-substrate.py --repo-root . --candidate-sha TEST > /tmp/github-substrate.json`
`python scripts/validate-github-substrate.py --manifest /tmp/github-substrate.json`

---

### Task 3 — Exact-head census workflow

**Files**
- Create: `.github/workflows/github-substrate-census.yml`
- Create: `harness/tests/test_github_substrate_workflow.py`

**Contract**
- PR, merge_group, push(main).
- `CANDIDATE_SHA` from event.
- immutable `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`.
- `permissions: contents: read` only.
- generate + validate exact-head manifest.
- no model call, no repository write, no OIDC mint, no attestation write.

Run workflow contract test locally before commit.

---

### Task 4 — Reconcile with actual GitHub observations

Use GitHub connector/API evidence separately from the tree manifest:
- workflow-run history from GitHub UI/API is historical/executed observation;
- current run logs can bind observed runner image/version to a specific run;
- if the available connector cannot list registered runners, record `REGISTERED_RUNNER_INVENTORY=NOT_CHECKED`; do not infer absence.

Known starting observation from operator screenshot: historical workflow UI includes `.github/workflows/smoke-test-provider-agnostic.yml`; exact canonical-main tree search does not currently find that path. This is a required regression example for universe separation, not proof the workflow never existed.

After implementation, update PR #296 body with the new exact head and only current-head CI conclusions. Do not promote prior GREEN runs to current applicability.