# AEGIS-OMEGA Repository Topology Baseline

Date: 2026-07-31  
Branch inspected: `main`  
Observed head: `f04dc41e1edf06d92956df6a8991bc3b459e43a0`  
Status: forensic baseline; descriptive only; no runtime or authority mutation

## Purpose

Establish the current repository topology before interpreting individual modules. This baseline separates repository structure, deployment surfaces, control-plane code, tested-only libraries, dormant material, and historical documentation.

The existing `REPO_MAP.md` remains useful, but it is not sufficient as the current source of truth. Its original full inspection dates to 2026-06-13. `reports/inventory.json` was generated from commit `a0a74ac6f1c98dd72d4dde8837d2ec0efe4c7849` on 2026-07-12. Current `main` has materially diverged: the compared history is 141 commits ahead and four commits behind that inventory source.

Therefore no repository-wide conclusion may be based solely on the old map, an isolated file, or a documentation claim.

## Top-level topology inherited from the last full inventory

The last machine-readable inventory identified these principal surfaces:

### Runtime and deployment surfaces

- `sovereign-omega-v2/`
- `aegis-cl-psi/`
- `aegis-runtime/`
- `vertex/`
- `agents/`
- `harness/`
- `hub/`
- `packages/`
- `platform-picker/`
- `hook-generator/`
- `content-calendar/`
- `tactical/`
- `cockpit/`
- `studio/`
- `supabase/`
- `worker-src/`
- `.github/`
- `.claude/`
- `verifiable/`
- `genomics/`

### Tested-only, standalone, or incompletely integrated surfaces

- `crates/`
- root `src/`
- `clients/`
- `aegisomega-webgpu/`
- `enterprise/`

### Dormant, manual-run, infrastructure, or documentary surfaces

- `backend/`
- `terraform/`
- `sovereign-mesh/`
- `aegis-ccil-verifier/`
- root `core/`
- `security/`
- `paperclip/`
- `alignment/`
- `.agent/`
- `.sovereign_context/`

## Material topology added or expanded after the last inventory source

The current head adds or materially expands repository-level surfaces that the 2026-07-12 inventory does not classify adequately:

### `.aegis/`

Contains the claims ledger, experiment-plan schema, and exact-head experiment plans for admission and integration work. This is now a first-class governance/evidence surface, not incidental metadata.

### `kernel-one/`

A standalone constitutional execution kernel with SQLite persistence, signed `WitnessEnvelope` records, deterministic validation, a dedicated test ring, and the `aegis / kernel-one` workflow check. Its own README classifies it as T2 and explicitly not deployed production authority.

### `schemas/`

Contains repository-level contracts for cognitive state, event envelopes, execution identity, mutation receipts, and writer leases. These contracts must be mapped against the Python bridge, Automaton-3 evaluator, Supabase schema, MCP server, and any future Node Fabric implementation.

### Expanded `harness/`

Now includes:

- consequence policy;
- capability map;
- environment-bound authority client;
- operator visibility;
- evidence-bound skill authority and routing;
- deterministic sovereign execution reference model.

This is no longer only a small skill-tree harness. It is a principal control-plane implementation surface.

### Replaced coordinator boundary

`agents/coordinator.py` is now a governed compatibility facade over `agents/coordinator_legacy.py`. Dispatch authority is delegated to `harness.sdk.authority_client.authorize_from_environment`; historical local scoring remains available only through the legacy implementation surface.

### Expanded `.github/workflows/`

New workflow families include:

- Automaton-2 and Automaton-3 validation;
- claims ledger;
- cognitive manifest refresh;
- coordinator authority;
- experiment admission;
- integration ledger;
- Kernel One;
- MCP resources;
- Scale OS controls;
- sovereignty contracts.

The workflow graph must be treated as part of the runtime/governance topology, not merely CI decoration.

### Expanded `reports/` and `docs/`

New reports, ADRs, RFCs, evidence packages, threat models, discovery records, and operational documents significantly alter the documentation and evidence topology. They must be classified by authority and freshness; they do not automatically override code or deployed state.

## Current validated control-plane chain

The currently visible local reference chain is:

```text
entry point / coordinator / MCP adapter
    -> harness.sdk.authority_client.authorize_from_environment
    -> ExecutionIdentityEnvelope validation
    -> workspace verification
    -> consequence policy + capability registry loading
    -> AuthorityEvaluator
    -> mutation receipt construction
```

`ADR-0021` explicitly states that this is a deterministic local reference model and does not claim deployed Temporal, LangGraph, Kubernetes, or cloud-worker execution.

This chain is distinct from:

- the Python bridge runtime;
- Kernel One;
- the TypeScript constitutional/test substrate;
- the Rust CL-Ψ and runtime engines;
- Supabase edge functions and migrations;
- GitHub Actions admission workflows;
- future Node Fabric durable execution.

They may share concepts and schemas, but integration must be demonstrated through imports, calls, deployment manifests, durable state, and receipts.

## Immediate forensic rules

1. Map directories and entry points before reviewing a leaf module.
2. Distinguish code presence, test execution, CI execution, deployment, live use, and authority.
3. Treat comments and headings as claims until confirmed by the call graph.
4. Do not classify a component as dead, canonical, superseded, or authoritative without semantic ancestry and current consumers.
5. Treat `main`, open PR overlays, deployed systems, and external operator-local artifacts as separate state layers.
6. No claim of autonomous or durable execution without an actual scheduler/queue, persistent execution state, worker acquisition, verification, and receipts.

## Next audit slices

The next updates to this branch will add:

1. exact top-level directory and manifest inventory at current head;
2. entrypoint and deployment map;
3. Python bridge import/call graph;
4. Automaton-3 authority graph;
5. Kernel One boundary and overlap analysis;
6. TypeScript tested-only versus runtime-reachable graph;
7. Rust workspace and CI membership map;
8. Supabase/Cloudflare/Vercel/Cloud Run deployment contract map;
9. open-PR overlay and semantic ancestry map;
10. corrected replacement for `REPO_MAP.md` only after the above are complete.

## Current conclusion

The repository already contains a map, but that map predates a material control-plane expansion. The correct first action is not to reinterpret `gate.py` or another isolated module. It is to rebuild the repository topology against the present head and then trace each claimed authority or runtime path end to end.
