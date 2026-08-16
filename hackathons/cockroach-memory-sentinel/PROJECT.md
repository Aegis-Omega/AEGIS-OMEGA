# AEGIS Memory Sentinel

A hackathon-specific agentic-memory application for the CockroachDB × AWS challenge.

## What it does

Memory Sentinel treats persistent memory as a safety boundary rather than chat history. Before a consequential action, the agent compares current state, policy, authority epoch, and action identity with the admitted memory tuple. Stale or replayed context fails closed.

Above that sits **MCM — Mycorrhizal Collective Metacognition**: a sparse collective meta-layer that propagates evidence quality, contradiction, reliability, load, and verification demand across heterogeneous nodes. MCM is permanently `OBSERVATION_ONLY/T2`; it cannot grant or expand authority.

## Current verified local slice

Dependency-free Node modules implement:

- deterministic stale-state / stale-policy / stale-authority / replay denial;
- MCM observation records with `authorityWeight = 0`;
- independent-witness demand under contradiction or stale evidence;
- routing priority changes without authority mutation.

Local TDD witnesses produced:

- memory authority contract: RED observed before implementation; GREEN `6/6`;
- MCM contract: RED `0/4`; GREEN `4/4`;
- deterministic demo: stale state -> `DENY`, MCM -> independent witness demand, authority mutation forbidden.

These are local component witnesses, not a CockroachDB Cloud/AWS integration claim.

## Run locally

```bash
cd hackathons/cockroach-memory-sentinel
npm test
npm run demo
```

No package installation is required for the current local contract slice.

## CockroachDB design

`db/schema.sql` defines three persistent surfaces:

1. `mcm_node_state` — sparse operational meta-state;
2. `mcm_evidence_memory` — evidence text + VECTOR embeddings + distributed vector index;
3. `mcm_action_receipt` — request/action/state/policy/authority-bound admission receipts.

Planned required sponsor-tool use:

- **Distributed Vector Indexing** — semantic retrieval over evidence memories while preserving transactional state in the same database;
- **CockroachDB Agent Skills Repo** — agent-visible CockroachDB operational/schema/security skills used during setup and diagnostics;
- **Cloud Managed MCP Server** — optional third Cockroach tool when Cloud credentials are available.

These remain `NOT_ESTABLISHED_AS_EXECUTED` until runtime evidence is captured.

## AWS design

Target deployment is a small AWS Lambda HTTP/API execution surface with CockroachDB as the external persistent memory system and optional S3 artifact storage. AWS use remains `NOT_ESTABLISHED_AS_EXECUTED` until a deployed endpoint and cloud receipt exist.

## OpenAI orchestration alignment

The intended agent host follows current OpenAI Agents SDK patterns:

- one narrow agent first;
- explicit function tools;
- structured state;
- traces and behavior evals;
- trusted host orchestration;
- deterministic AEGIS authority gate separate from model judgment and guardrails.

See `docs/OPENAI_COOKBOOK_ALIGNMENT.md`.

## Pre-existing work disclosure

AEGIS Omega is a pre-existing open-source project with metacognitive, replay, receipt, and governance experiments. This hackathon submission does not present that pre-existing corpus as new work.

The new submission work is the Memory Sentinel application slice created during the hackathon period: the MCM collective layer, memory-authority contract, CockroachDB schema/integration, AWS deployment path, demo, tests, and submission artifacts.

## Evidence boundary

Current status:

```text
LOCAL_CONTRACT_IMPLEMENTATION: ESTABLISHED
LOCAL_COMPONENT_TESTS: ESTABLISHED (reported local TDD runs)
COCKROACHDB_SCHEMA: IMPLEMENTED
COCKROACHDB_RUNTIME_INTEGRATION: NOT_ESTABLISHED
COCKROACHDB_REQUIRED_TOOL_1_EXECUTION: NOT_ESTABLISHED
COCKROACHDB_REQUIRED_TOOL_2_EXECUTION: NOT_ESTABLISHED
AWS_DEPLOYMENT: NOT_ESTABLISHED
FUNCTIONAL_PUBLIC_DEMO: NOT_ESTABLISHED
HACKATHON_ELIGIBLE_SUBMISSION: NOT_YET_ESTABLISHED
```
