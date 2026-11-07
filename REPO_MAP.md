<!-- AEGIS_OPTIMUS_EVOLUTION_DOC_BOUNDARY_V1 -->
# AEGIS Ω | Canonical repository map entry point

**Current-source rule:** this file contains historical observations; run `python3 scripts/aegis_topology.py --repo . --summary` on the exact current commit for the actual folder census. `docs/architecture/OPTIMUS_EVOLUTION.md` defines ownership and migration gates. Source presence is not live deployment, test success, revenue or admission.

**2026-11-06 reconciliation:** `hub/src/components/PricingPage.tsx` and `supabase/functions/verify-paypal/index.ts` in inspected `main@c6f4f2131ab06c5b20cfd3d0eafd99e3ca246bc8` specify $49/$499 (not historical $48/$498). `agents/` is a mixed-function directory, not globally dormant. Tactical Vercel config and `infrastructure/production.json` live in unmerged candidate branches, not automatically in main.

## Generate the current folder table

On the exact checkout, generate a complete, source-bound table without updating a static inventory:

```bash
python3 scripts/aegis_topology.py --strict --markdown
```

The table includes every tracked root and its logical owner. It does **not** assert production readiness or connectivity. Unknown roots fail the strict gate and require inspection.

## Navigate the architecture

- `docs/architecture/OPTIMUS_EVOLUTION.md`: logical ownership, evidence boundaries and migration constraints.
- `scripts/aegis_topology.py`: deterministic exact-HEAD folder map, unknown roots and critical missing files.
- `harness/sdk/repository_knowledge.py`: existing source-bound repository cartographer, preserved.
- `docs/archive/REPO_MAP_2026-07.md`: entire previous map, including historical deployment and pricing assertions, unchanged.

## Cross-PR Compose dependency (OPEN)

Source check at `main@c6f4f2131ab06c5b20cfd3d0eafd99e3ca246bc8`: `docker-compose.yml` selects bridge target `runtime`, but `sovereign-omega-v2/Dockerfile` has no matching named stage. This **build dependency is broken**, even if `docker compose config` reports valid YAML. PR #775, source `977523d7761c25264a4c0156e6a3f76bf8bfa16c`, already contains the candidate fix (removes the target); the fix is not part of this PR or protected main.

The existing deployment preflight now invokes `scripts/validate_compose_targets.py` under `--docker-config`. Missing stage or missing Dockerfile is `FAILED`, unparseable/dynamic configuration is `UNKNOWN`, and a literal valid stage is `PASS`. This validates **source build targets only**, not image build, deployment, authorization, or provider status. The preflight is expected to fail on the current source until the existing #775 correction is admitted. Do not duplicate its Compose change here.

## Deployment classes

`SOURCE_PRESENT` only establishes a path exists. Never conflate it with `CI_PASS`, `DEPLOYED`, `AUTHORIZED`, `COMMERCIAL_VERIFIED`, or `OPENAI_QUALIFIED`. Confirm each property independently from exact-source receipts. Repo presence is not a functional integration.
