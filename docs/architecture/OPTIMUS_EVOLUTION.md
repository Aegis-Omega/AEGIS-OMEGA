# AEGIS Ω / Aegis Omega Labs: Optimus Evolution architecture

**Architecture contract v1 · 2026-11-06 · source-bound, not a deployment certificate**

## Decision

**One repository, one canonical Git tree, one epistemic contract, many products.**
Do not manufacture a second AEGIS runtime, a second authorization root, or a second repo census. Preserve the existing Source Plane and Repository Knowledge Cartographer; this layout is a **logical ownership overlay** until safe moves are proven.

The canonical source map is computed from `git ls-tree -r HEAD` by `scripts/aegis_topology.py`. The document `REPO_MAP.md` is the human entry point, not an independent ground-truth database. A `reports/inventory.json` generated against a different commit is **historical evidence**, never current inventory.

## Logical topology (no physical moves yet)

```text
Aegis Omega Labs / AEGIS Ω
├─ apps                 hub, tactical, cockpit, studio, platform-picker,
│                      hook-generator, content-calendar, enterprise,
│                      aegisomega-webgpu
├─ runtime              sovereign-omega-v2 (Python bridge + TS runtime),
│                      aegis-cl-psi, aegis-runtime, agents, harness, vertex,
│                      root src, core, crates, backend
├─ packages             packages/*, clients/*, aegis-ccil-verifier
├─ integrations         supabase, worker-src
├─ research             genomics, verifiable, sovereign-mesh,
│                      paperclip, alignment
├─ security             security
├─ infrastructure       terraform (deployment definitions; read-only by default)
├─ automation           .github, .claude, .agent
├─ evidence             reports
├─ documentation        docs, .sovereign_context
└─ tooling              scripts, .devcontainer, .vscode
```

The names above are **owners**, not assertions that every module is deployed or even reachable. `sovereign-omega-v2/src` is different from `sovereign-omega-v2/python` even though both share one top-level directory. `agents/` may be bundled into the Vertex image but is not proof that each managed agent is functioning. The external RH repository `Aegis-Omega/formal-conjectures` is **not** to be copied into this tree.

## Truth matrix

| Plane | Authority source | Verified here | Not inferred |
|---|---|---|---|
| Presence | Exact Git tree | File/path exists on the commit | Tests or deploy succeeded |
| Ownership | `aegis_topology.py` logical map | Known root classified | Import graph is correct |
| Build/test | Native exact-head CI + artifact hashes | Only with run/job receipt | Source-line and test-declaration counts |
| Runtime | Deploy provider live state + pinned digest | Only with provider observation | GitHub green preview |
| Agent execution | Automaton-3 / identity / admission | Only with authority and independent receipt | A running container or MCP connectivity |
| Commercial | PayPal / Supabase / client purchase evidence | Only with end-to-end receipts | UI pricing or Vercel success |
| Partnership | OpenAI Partner Network account records | Onboarding complete per provider | Co-sell approval, resale permissions, tier |

## Source-bound findings (2026-11-06 inspection)

- `main`: `c6f4f2131ab06c5b20cfd3d0eafd99e3ca246bc8` observed from GitHub commit search/compare. **Not guaranteed to remain HEAD.**
- `hub/src/components/PricingPage.tsx` `TIER_PRICE` is **49.00 / 499.00 USD** for Operator/Sovereign at the inspected SHA. The server-side `supabase/functions/verify-paypal/index.ts` shows **$49 / $499**. Older `REPO_MAP.md` and `ASSETS.md` say $48/$498; those entries are stale, not alternative pricing.
- `REPO_MAP.md` incorrectly includes `agents/` in a blanket dormant/manual-only paragraph despite also describing agent-image bundling. Treat `agents/` as **mixed**, pending per-submodule import/deploy/runtime tracing.
- Tactical's Vercel deployment config is present on an **unmerged branch** `docs/tactical-deploy-state-v1`, not on inspected `main`. Therefore no claim of current main deployment readiness is justified.
- `docs/OPERATIONS.md` and `infrastructure/production.json` exist on candidate `codex/unify-aegis-operations` (related PR #775). They are candidate-only, **not current main production truth**.
- `reports/inventory.json` declares `generated_from=a0a74ac6f1c98dd72d4dde8837d2ec0efe4c7849` dated 2026-07-12, so must not be treated as live evidence for the inspected commit.
- `docs/PROOF.md` records measured declarations/lines from 2026-06-30; declaration counts are not current-pass receipts.
- The existing read-only `harness/sdk/repository_knowledge.py` and Source Plane PR #795 are reusable. Do not introduce a replacement cartographer or new write authority.

## Folder cleanup protocol

**Phase 0: Audit (this package).** Run the deterministic, read-only topology tool from the exact checkout. Track every root, every critical anchor, new roots and historical documents. `UNKNOWN` must remain visible. Nothing is removed.

**Phase 1: Ownership.** Review each root and record explicit `production`, `tested-only`, `dormant`, or `historical` status **per component**, based on exact-head CI and import/endpoint/build evidence. The top-level ownership map alone cannot prove lifecycle status.

**Phase 2: Dependency graph.** Before any move, enumerate references from Python imports, TS path aliases, Cargo workspaces, build contexts, Docker COPY, GitHub Actions paths, Vercel root directories, Supabase function paths and published external links. Record unresolved dynamic imports as `UNKNOWN` rather than zero references.

**Phase 3: Safe moves.** A move may occur only on an existing authorized development branch and only after expected-head check, full path-reference inventory, import/build repair, local green gates, native exact-head checks and independent review. Preserve commit history and add compatibility adapters where published paths exist. Do **not** bulk `mv` `sovereign-omega-v2`, `hub`, `supabase`, `agents`, `.github`, `harness` or `packages` in this stage.

**Phase 4: Consolidation.** Eliminate only proven duplicates with a deprecation inventory, consumer check, migration test and rollback. Archived research and historical PR evidence are never silently deleted. Cross-repository formal proof lineage remains independent.

**Phase 5: Admission.** The exact final HEAD must pass existing signed provenance and repo-enforcement gates. Deployment, billing, protected main, security settings and branch promotion require distinct authority. A documentation update is not a production repair.

## Minimal runbook

```sh
python3 scripts/aegis_topology.py --repo . --summary
python3 scripts/aegis_topology.py --repo . --strict > /tmp/aegis-topology.json
python3 -m unittest discover -s scripts -p 'test_aegis_topology.py' -v
# Existing canonical repository-knowledge proof (do not replace):
python3 scripts/test-repository-cartographer.py
```

**Open validation obligations:** run the new tool within the *real* repository, capture exact HEAD/tree; inspect all unclassified roots; native CI for that head; compare every published product and deployment path; ensure no unauthorized spend. Local fixture tests prove only the tool's behavior, not real repository completeness.
