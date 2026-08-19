# Frontier Provider Mesh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the interrupted Copenhagen Work session hardening and extend AEGIS-Ω SOL into a provider-neutral frontier interoperability mesh without allowing any provider, model, stream, or paid invocation to bypass Automaton-3 authority.

**Architecture:** Continue from `feat/sol-cross-platform-control-plane@12e2c88473a7017378dab31e078b25f991ece397`. Keep the existing invariant `provider proposes/computes -> AEGIS authorizes -> provider executes within granted capability -> AEGIS records evidence/receipt`. Add evidence-bound cognitive admission, proof-carrying work orders, fenced SSE ownership, provider/protocol descriptors, MCP/A2A bridge contracts, and a fail-closed provider router. Provider adapters remain server-side and injected; this wave makes no live provider calls and provisions no credentials.

**Tech Stack:** Python 3.11 stdlib (`dataclasses`, `hashlib`, `json`, `unittest`), existing SOL JSON contracts, existing Automaton-3 consequence classes D0-D4.

## Global Constraints

- Automaton-3 remains the sole authority root.
- Provider/model output is evidence/advice, never authority.
- D0 read-only work may execute automatically only inside declared capability envelopes.
- D2 requires admission + idempotency; D3 requires explicit operator approval + admission; D4 remains denied.
- Any cost-incurring invocation requires a valid proof-carrying work order before transport invocation.
- SSE ownership is fenced by execution identity + owner + generation + monotone event sequence.
- T0/T1 status cannot be obtained from claim wording; external evidence binding is mandatory.
- Offline cognitive mode must emit no fabricated claims/results.
- KAN/hash-chain output proves only local scoring-log integrity, not the truth of a claim.
- Secrets/tokens are references only; no inline secret material in contracts or receipts.
- No production deployment, DNS, IAM, OAuth provisioning, paid API call, merge to `main`, or secret creation in this wave.

---

### Task 1: Recover Copenhagen evidence semantics

**Files:**
- Modify: `agents/cognitive_pipeline.py`
- Create: `agents/tests/test_cognitive_evidence_binding.py`

**Interfaces:**
- Consumes: existing `arbitrate`, `run_pipeline`, KAN score/log primitives.
- Produces: `EvidenceBinding`, evidence-aware `arbitrate(..., evidence=...)`, offline empty discovery behavior, explicit `scoring_integrity_only` metadata.

- [ ] Write failing tests showing (a) T0/T1 wording without external evidence is demoted to T3/unverified, (b) valid bound evidence permits the requested tier subject to score, (c) offline mode with no supplied claims fabricates nothing, and (d) KAN hash metadata does not claim truth/proof.
- [ ] Run the focused unittest file and confirm the failures are due to missing evidence binding behavior.
- [ ] Implement the minimum evidence-binding model and remove synthetic fallback claims.
- [ ] Run focused tests to green.
- [ ] Run existing `agents/tests/test_lut_kan_parity.py` plus the new tests.
- [ ] Commit as `fix(cognition): bind epistemic tiers to external evidence`.

### Task 2: Proof-carrying work orders and fenced SSE ownership

**Files:**
- Create: `platform/sol/frontier/work_order.py`
- Create: `platform/sol/frontier/stream_lease.py`
- Create: `platform/sol/frontier/__init__.py`
- Create: `platform/sol/tests/test_frontier_execution_guards.py`

**Interfaces:**
- Produces `ProofCarryingWorkOrder`, `verify_work_order`, `SSEStreamLease`, `verify_stream_event`.
- Work order binds request/provider/capability/consequence class/arguments digest/expected parent/idempotency/budget/token ceiling/evidence refs/operator approval.
- Stream lease binds execution id/owner identity/generation/fencing token/last sequence.

- [ ] Write failing tests for missing work order on cost work, provider/capability mismatch, missing evidence, missing D3 approval, inline-secret rejection, stale stream generation, wrong stream owner, and non-monotone SSE sequence.
- [ ] Run tests and confirm expected failures.
- [ ] Implement canonical deterministic digesting and fail-closed validators.
- [ ] Re-run tests to green.
- [ ] Commit as `feat(sol): add proof-carrying work orders and stream fencing`.

### Task 3: Frontier provider and protocol registry

**Files:**
- Create: `platform/sol/frontier/providers.py`
- Create: `platform/sol/tests/test_frontier_provider_registry.py`

**Interfaces:**
- Produces immutable `ProviderDescriptor`, `get_provider`, and `FRONTIER_PROVIDERS`.
- Initial provider set: OpenAI, Anthropic, Google Vertex/Gemini, Microsoft Foundry, AWS Bedrock/AgentCore, Vercel AI Gateway, xAI, Mistral, DeepSeek, Alibaba/Qwen-DashScope, NVIDIA NIM, Hugging Face.
- Protocol capabilities describe native inference surface plus MCP/A2A/OpenResponses/OpenAI-compatible support where applicable; descriptors do not contain credentials.

- [ ] Write failing tests for registry completeness, unique provider IDs, server-side auth references, unknown-provider denial, and absence of inline credentials.
- [ ] Run tests and confirm failures.
- [ ] Implement descriptors with explicit protocol/auth/streaming/tool-interoperability metadata.
- [ ] Run tests to green.
- [ ] Commit as `feat(sol): register frontier inference providers`.

### Task 4: MCP/A2A bridges and governed provider router

**Files:**
- Create: `platform/sol/frontier/mcp.py`
- Create: `platform/sol/frontier/a2a.py`
- Create: `platform/sol/frontier/router.py`
- Create: `platform/sol/tests/test_frontier_router.py`

**Interfaces:**
- MCP: normalized remote-server reference, allowlisted tools, approval policy, auth-reference only.
- A2A: normalized agent-card/task envelope and stream-owner binding.
- Router: `ProviderInvocation`, injected `ProviderTransport`, `GovernedProviderRouter.invoke()` returning non-authoritative provider evidence.

- [ ] Write failing tests proving unknown provider denial, undeclared capability denial, cost work denial without work order, D3 denial without operator approval, MCP all-tools default rejection, A2A stream owner mismatch rejection, idempotent duplicate collapsing, and provider result `grants_authority=False`.
- [ ] Run tests and confirm expected failures.
- [ ] Implement minimal bridge contracts and router.
- [ ] Run tests to green.
- [ ] Commit as `feat(sol): add governed MCP A2A provider router`.

### Task 5: Canonical SOL contract expansion and verification

**Files:**
- Modify: `platform/sol/contracts/platform-registry.v1.json`
- Modify: `platform/sol/contracts/execution-request.v1.schema.json`
- Modify: `platform/sol/README.md`
- Create: `platform/sol/frontier/README.md`

**Interfaces:**
- Add provider IDs introduced in Task 3.
- Add optional cost/token/work-order/stream-ownership fields while keeping D3/D4 explicit approval requirements.
- Document native transport vs MCP vs A2A roles and authority non-equivalence.

- [ ] Add static tests or JSON-load assertions covering registry/schema validity and provider parity with `FRONTIER_PROVIDERS`.
- [ ] Update canonical contract documents only after tests fail for the missing provider entries/fields.
- [ ] Run all `platform/sol/tests` plus the cognitive evidence tests.
- [ ] Record exact test command/output and branch head in the PR body; do not claim unrun suites.
- [ ] Open a draft PR targeting `feat/sol-cross-platform-control-plane`, not `main`.

## Verification Target

The wave is complete only when the branch demonstrates these machine-checkable properties:

1. `T0/T1 wording != T0/T1 authority` without evidence.
2. `offline != fabricated research result`.
3. `scoring hash != truth proof`.
4. `cost-incurring provider call -> valid work order`.
5. `SSE event -> current fenced owner + monotone sequence`.
6. `MCP/A2A/provider output -> evidence only, grants_authority=false`.
7. `unknown provider/capability -> deny`.
8. `D3 -> explicit operator approval + admission`.
9. Frontier provider/protocol coverage is explicit and credential-free.
10. No live spend, deployment, secret provisioning, or merge occurs in this implementation wave.
