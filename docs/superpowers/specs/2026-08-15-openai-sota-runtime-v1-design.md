# AEGIS Ω OpenAI SOTA Runtime v1 — Design

**Date:** 2026-08-15  
**Base:** `main@0bdffe75b56e5cd27c0632e1ba166620da327494`  
**Status:** implementation-ready design  
**Epistemic stance:** evidence-first, fail-closed, model-agnostic. This design does **not** claim that AEGIS Ω is already AGI or ASI; it creates a runtime in which such capability claims can be measured, replayed, and admitted only with evidence.

## 1. Goal

Create one production OpenAI runtime layer that:

1. replaces the current OpenAI Chat Completions transport with the OpenAI Responses path;
2. adds OpenAI Agents SDK orchestration to the *production Python spine* rather than to the dormant TypeScript governance tree;
3. keeps AEGIS Ω — not the model provider — as the authority for capabilities, tool admission, approvals, provenance, replay, and mutation receipts;
4. supports manager-style specialist agents without allowing delegation to bypass AEGIS authority;
5. emits structured, typed results and evidence metadata suitable for deterministic admission and later evals;
6. preserves the existing multi-provider architecture and graceful fallback contract where explicitly allowed by policy.

The long-term target is a model-agnostic collective-intelligence/superintelligence control plane. The first implementation slice is deliberately narrower: a secure, testable, production-wired OpenAI cognition adapter with bounded agentic execution.

## 2. Why the production Python spine

`REPO_MAP.md` identifies `sovereign-omega-v2/python/bridge.py` and its Python modules as the deployed governance/swarm/inference HTTP service shipped by `sovereign-omega-v2/Dockerfile`. It also records that most of `sovereign-omega-v2/src/` is tested-only/dormant.

Therefore this feature MUST be implemented in the Python production path first. TypeScript may expose client adapters later, but it is not the authoritative execution surface for v1.

Current relevant anchors:

- `sovereign-omega-v2/python/bridge.py` — production HTTP service.
- `sovereign-omega-v2/python/requirements.txt` — production Python dependency set.
- `sovereign-omega-v2/Dockerfile` — Cloud Run packaging of only the Python layer.
- `supabase/functions/chat/index.ts` — existing OpenAI Chat Completions proxy; retained for compatibility during migration, but not the new authority path.
- `packages/shared/lib/inference-router.ts` — client-side multi-backend router; it must not contain OpenAI secrets or become the authority source.
- `docs/CAPABILITY_GOVERNANCE.md` — least-privilege capability semantics.
- `schemas/mutation-receipt.v1.schema.json` — mutation receipt contract.

## 3. OpenAI SOTA mapping

The runtime follows current OpenAI primary guidance:

- OpenAI Agents SDK uses the Responses API by default for OpenAI models.
- Use the Agents SDK when turns, tool execution, guardrails, sessions, tracing, or multi-agent orchestration are needed.
- Use manager-style `Agent.as_tool()` composition when one orchestrator must retain final ownership.
- Use strict schemas/structured outputs for machine-consumable agent results.
- Use tool input/output guardrails for every custom function-tool invocation; agent-level input/output guardrails alone are insufficient for nested agent workflows.
- Use explicit tracing metadata and workflow names so execution provenance can be correlated with AEGIS receipts.

Primary references:

- https://openai.github.io/openai-agents-python/
- https://openai.github.io/openai-agents-python/models/
- https://openai.github.io/openai-agents-python/multi_agent/
- https://openai.github.io/openai-agents-python/guardrails/
- https://openai.github.io/openai-agents-python/running_agents/
- https://platform.openai.com/docs/quickstart/make-your-first-api-request

## 4. Architecture

```text
Operator / caller
      |
      v
AEGIS bridge HTTP boundary
      |
      v
Request normalization + execution identity
      |
      v
AEGIS AuthorityGate
  - capability registration
  - explicit grant
  - action class
  - tool allowlist
  - optional human approval requirement
      |
      +-------------------------- DENY -> denial receipt
      |
      v
OpenAIRuntime
  - required model configuration
  - Agents SDK / Responses transport
  - no guessed model IDs
  - bounded turns / bounded tool concurrency
      |
      v
Omega Manager Agent
  |          |           |
  v          v           v
Research   Verification  Implementation
Agent      Agent         Agent
(as tool)  (as tool)     (as tool)
      \       |        /
       \      |       /
        v     v      v
AEGIS-governed function tools
  - pre-tool authority guardrail
  - optional approval interruption
  - execution
  - post-tool evidence guardrail
      |
      v
Structured OmegaRunResult
      |
      v
Evidence / policy admission
      |
      +---------- reject -> FAILED/DENIED receipt
      |
      v
MutationReceipt / trace binding
      |
      v
Caller response
```

## 5. Module boundaries

Create a focused package inside the production Python layer:

### `python/openai_runtime/config.py`

Loads runtime configuration. Required fields fail closed.

- `OPENAI_API_KEY` — required for live OpenAI execution.
- `OPENAI_PRIMARY_MODEL` — required; no guessed fallback.
- `AEGIS_OPENAI_RUNTIME_ENABLED` — must equal `true` for live execution.
- `AEGIS_OPENAI_MAX_TURNS` — positive bounded integer; default 12.
- `AEGIS_OPENAI_MAX_TOOL_CONCURRENCY` — positive bounded integer; default 2.
- `AEGIS_OPENAI_TRACE_SENSITIVE_DATA` — default false.

Config validation MUST NOT perform network I/O.

### `python/openai_runtime/types.py`

Pydantic/dataclass types for stable execution contracts:

- `OmegaRunRequest`
- `OmegaRunContext`
- `AuthorityDecision`
- `ToolEvidence`
- `OmegaRunResult`
- `RuntimeErrorCode`

`OmegaRunResult` includes at least:

- `execution_id`
- `status`
- `model`
- `final_output`
- `specialists_used`
- `tool_calls`
- `evidence_digests`
- `trace_id` when available
- `receipt_digest` when a receipt is emitted
- `is_replay_reconstructable`

### `python/openai_runtime/authority.py`

Adapter from AEGIS capability/authority semantics to agent/tool execution.

It MUST:

- deny unknown capabilities;
- deny ungranted capabilities;
- deny tools outside the execution allowlist;
- distinguish read-only actions from external/mutating actions;
- require approval for configured high-impact actions;
- return a typed `AuthorityDecision` rather than booleans with implicit meaning.

No OpenAI SDK object may be treated as an authority source.

### `python/openai_runtime/tools.py`

Defines only AEGIS-wrapped function tools. Every mutating or external-effect function tool MUST have both input and output guardrails.

Pre-tool guardrail verifies:

- execution identity;
- active capability grant;
- tool allowlist membership;
- target scope;
- approval state when required.

Post-tool guardrail verifies:

- result shape;
- evidence/provenance presence;
- digestability;
- no success claim if the underlying operation failed.

Hosted/built-in OpenAI tools are NOT admitted in v1 because their execution does not pass through the same custom function-tool guardrail pipeline. They may be added later only with an explicit AEGIS wrapper or equivalent enforceable control.

### `python/openai_runtime/agents.py`

Defines the first specialist set and the manager.

Initial specialists:

1. `ResearchAgent` — evidence gathering/synthesis; no mutation authority.
2. `VerificationAgent` — adversarial verification, contradiction detection, evidence grading; no mutation authority.
3. `ImplementationAgent` — proposes code/action plans and may call only explicitly granted implementation tools.

`OmegaManager` remains the single owner of the final output and invokes specialists as tools. Handoffs are not used in v1 for authority-sensitive workflows because manager ownership provides one governance boundary for the final result.

All agents use structured outputs where machine consumption is required.

### `python/openai_runtime/runtime.py`

Owns `Runner` configuration and execution lifecycle.

Responsibilities:

- build `OmegaRunContext`;
- instantiate/reuse the governed runner;
- set workflow name and trace metadata;
- enforce max turns;
- enforce local tool concurrency;
- set pre-approval tool guardrails;
- convert SDK exceptions into stable AEGIS error codes;
- never convert a failed/denied run into an apparent successful result.

### `python/openai_runtime/receipts.py`

Binds OpenAI execution evidence to the existing AEGIS mutation-receipt model.

The adapter MUST NOT invent unavailable receipt fields. For actions that do not mutate external state, it may emit a non-mutation execution evidence record instead of misusing `MutationReceipt`.

For real mutations, it must provide or derive every required field in `mutation-receipt.v1.schema.json`, including pre/post state digests and parent receipt linkage.

### `python/openai_runtime/__init__.py`

Exports only stable public runtime interfaces.

## 6. Bridge integration

Add a new versioned bridge endpoint rather than silently changing unrelated endpoints:

`POST /v1/omega/run`

Request:

```json
{
  "input": "operator task",
  "allowed_capabilities": ["research-synthesis"],
  "allowed_tools": [],
  "action_class": "D0",
  "metadata": {}
}
```

Behavior:

1. authenticate using the bridge's normal production auth path;
2. create an execution ID and normalized request digest;
3. run the AEGIS authority preflight;
4. reject before OpenAI spend if policy fails;
5. invoke `OpenAIRuntime` only when explicitly enabled and configured;
6. return a structured `OmegaRunResult`;
7. include model and trace provenance actually observed, never client guesses.

The existing Supabase `/chat` OpenAI path remains temporarily available for existing product callers. It is not upgraded in place until the new governed runtime has passing tests and an admission decision.

## 7. Fail-closed rules

The v1 runtime MUST reject rather than guess when any of these is true:

- runtime disabled;
- API key missing;
- model missing;
- unknown capability;
- no active grant;
- unregistered tool;
- action exceeds declared action class;
- approval required but absent;
- structured result validation fails;
- required evidence is absent;
- receipt construction for a claimed mutation is incomplete;
- model/tool runtime raises an unclassified exception.

Fallback to another model/provider is allowed only when the caller/policy explicitly permits fallback. A policy denial is never a fallback condition.

## 8. Security and sovereignty constraints

1. `OPENAI_API_KEY` remains server-side only.
2. No `VITE_*` secret is introduced.
3. Model names are configuration, not authority.
4. Agent instructions cannot expand capabilities.
5. Tool descriptions cannot expand capabilities.
6. Specialist agents cannot grant themselves tools.
7. Provider tracing is supplementary evidence, not the canonical AEGIS ledger.
8. Sensitive trace payload export defaults off.
9. External-effect tools require bounded target scope and explicit authority.
10. Existing known bridge security issues are not silently broadened by this feature; the new endpoint must not rely on a client-controlled provider flag as authorization.

## 9. Cost controls

The first live proof must be cheap and bounded:

- no automatic background loops;
- max turns <= 12 by default;
- local tool concurrency <= 2 by default;
- no hosted web/file/code tools in v1;
- no automatic retries that can multiply cost without a configured cap;
- one explicit configured model per run;
- token/usage metadata captured when available.

These controls make the runtime testable with a small Platform balance without conflating API balance with ChatGPT Work credits.

## 10. Testing strategy

TDD is mandatory.

### Unit tests

- config fails closed on missing model/key/enabled flag;
- unknown capability rejected;
- ungranted capability rejected;
- tool outside allowlist rejected;
- mutating tool requires approval;
- tool output without evidence rejected;
- SDK exception maps to stable error code;
- policy denial happens before the model runner is invoked;
- sensitive tracing defaults false;
- mutation receipt adapter refuses incomplete mutation evidence.

### Contract tests

Mock the OpenAI runner. Tests MUST NOT require network or spend.

Verify:

- exact `OmegaRunRequest -> OmegaRunResult` shape;
- manager owns final output;
- specialist outputs are captured as provenance;
- trace metadata contains AEGIS execution identity;
- explicit model identity is returned;
- denial result cannot serialize as success.

### Bridge tests

- `POST /v1/omega/run` rejects malformed body;
- rejects unauthorized caller;
- rejects disabled runtime before invoking SDK;
- returns structured success from mocked runtime;
- returns stable denial/failure codes.

### Live smoke test

Only after offline suite passes:

- one D0 read-only task;
- no external/mutating tools;
- one configured OpenAI model;
- capture actual model, trace/run identifiers and usage;
- no claim of production admission from a single smoke test.

## 11. Rollout / admission

Phase 1 — offline: dependency pin, types, authority adapter, mocked Runner tests.  
Phase 2 — bridge wiring behind `AEGIS_OPENAI_RUNTIME_ENABLED=false` default.  
Phase 3 — one bounded API smoke test with explicit operator activation.  
Phase 4 — compare trace/receipt evidence and run security review.  
Phase 5 — only then consider routing real AEGIS tasks through the new runtime.

No existing provider path is removed in v1.

## 12. Explicit non-goals for v1

- proving AGI or ASI;
- self-modifying authority policy;
- autonomous credential creation;
- unrestricted shell/computer use;
- hosted OpenAI tool use without equivalent AEGIS enforcement;
- recursive unbounded subagent spawning;
- replacing the whole multi-provider router;
- silently merging or deploying to production.

## 13. Success criteria

The slice is complete only when all are true:

1. OpenAI execution in the production Python spine uses Agents SDK / Responses path.
2. Runtime is disabled by default and fails closed when configuration is absent.
3. Manager + specialists produce structured outputs.
4. Every admitted local tool call is authority-checked before execution and evidence-checked after execution.
5. Policy rejection incurs no model call.
6. Trace metadata is bound to AEGIS execution identity.
7. Mutation claims cannot be emitted without complete receipt evidence.
8. Offline tests pass without network/API spend.
9. One optional bounded live smoke test can be run independently.
10. Existing production paths remain intact until explicit admission.
