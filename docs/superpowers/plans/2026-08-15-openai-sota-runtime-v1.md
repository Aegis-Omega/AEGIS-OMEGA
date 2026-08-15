# AEGIS Ω OpenAI SOTA Runtime v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-wired, fail-closed OpenAI Agents SDK / Responses runtime to the deployed Python spine, governed by AEGIS capability and evidence rules.

**Architecture:** Keep `bridge.py` as the HTTP boundary, but move OpenAI cognition into a focused `python/openai_runtime/` package. A manager agent owns final output and invokes bounded specialists as tools. AEGIS performs authority admission before any model spend, wraps custom tools with pre/post evidence checks, and binds trace/model provenance to stable run results and mutation receipts.

**Tech Stack:** Python 3.11, `openai-agents`, Pydantic v2, stdlib HTTP bridge, pytest/unittest-compatible offline tests, existing AEGIS receipt schema.

## Global Constraints

- Base branch is `main@0bdffe75b56e5cd27c0632e1ba166620da327494`.
- Implement only on `feat/openai-sota-runtime-v1` until explicit admission.
- Production runtime remains disabled unless `AEGIS_OPENAI_RUNTIME_ENABLED=true`.
- No guessed OpenAI model id; `OPENAI_PRIMARY_MODEL` is required.
- No browser-side OpenAI secret and no new `VITE_*` secret.
- Policy denial must occur before any model call.
- Hosted/built-in OpenAI tools are out of scope for v1; only AEGIS-wrapped local function tools are admitted.
- No live API spend is required for offline verification.
- TDD is mandatory for production-code changes.

---

### Task 1: Dependency and typed runtime contract

**Files:**
- Modify: `sovereign-omega-v2/python/requirements.txt`
- Create: `sovereign-omega-v2/python/openai_runtime/__init__.py`
- Create: `sovereign-omega-v2/python/openai_runtime/config.py`
- Create: `sovereign-omega-v2/python/openai_runtime/types.py`
- Create: `sovereign-omega-v2/python/tests/test_openai_runtime_config.py`
- Create: `sovereign-omega-v2/python/tests/test_openai_runtime_types.py`

**Interfaces:**
- Produces: `OpenAIRuntimeConfig.from_env(env: Mapping[str, str]) -> OpenAIRuntimeConfig`
- Produces: `OmegaRunRequest`, `OmegaRunContext`, `AuthorityDecision`, `ToolEvidence`, `OmegaRunResult`, `RuntimeErrorCode`

- [ ] Write failing config tests for disabled runtime, missing key, missing model, invalid max-turns/concurrency, and sensitive tracing default false.
- [ ] Run focused tests and confirm RED because package/types do not exist.
- [ ] Implement minimal config/types; pin `openai-agents>=0.19.0,<0.20.0` and `pydantic>=2.12.2,<3`.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Fail-closed AEGIS authority adapter

**Files:**
- Create: `sovereign-omega-v2/python/openai_runtime/authority.py`
- Create: `sovereign-omega-v2/python/tests/test_openai_runtime_authority.py`

**Interfaces:**
- Consumes: `OmegaRunRequest`, `AuthorityDecision`
- Produces: `AuthorityGate.evaluate(request, registered_capabilities, active_grants, registered_tools, approvals) -> AuthorityDecision`

- [ ] Write failing tests proving unknown capability, ungranted capability, unregistered tool, and missing approval are denied.
- [ ] Add a test proving a D0 read-only request with known granted capability is admitted.
- [ ] Run tests and confirm RED.
- [ ] Implement the minimal pure authority evaluator with stable denial codes.
- [ ] Run tests and confirm GREEN.

### Task 3: Governed tool evidence and receipt adapter

**Files:**
- Create: `sovereign-omega-v2/python/openai_runtime/tools.py`
- Create: `sovereign-omega-v2/python/openai_runtime/receipts.py`
- Create: `sovereign-omega-v2/python/tests/test_openai_runtime_tools.py`
- Create: `sovereign-omega-v2/python/tests/test_openai_runtime_receipts.py`

**Interfaces:**
- Produces: `validate_tool_input(...) -> AuthorityDecision`
- Produces: `validate_tool_output(evidence: ToolEvidence) -> ToolEvidence`
- Produces: `build_mutation_receipt(...) -> dict[str, object]`

- [ ] Write failing tests that missing evidence rejects a claimed successful tool result.
- [ ] Write failing tests that incomplete mutation evidence cannot produce a receipt.
- [ ] Run tests and confirm RED.
- [ ] Implement deterministic validators and receipt-schema construction without inventing unavailable fields.
- [ ] Run tests and confirm GREEN.

### Task 4: OpenAI Agents SDK manager and specialists

**Files:**
- Create: `sovereign-omega-v2/python/openai_runtime/agents.py`
- Create: `sovereign-omega-v2/python/tests/test_openai_runtime_agents.py`

**Interfaces:**
- Produces: `build_specialists(model: str, context) -> SpecialistSet`
- Produces: `build_omega_manager(model: str, specialists: SpecialistSet) -> Agent`

- [ ] Write failing contract tests for manager ownership, explicit model identity, structured output type, and three bounded specialists.
- [ ] Run tests and confirm RED.
- [ ] Implement `ResearchAgent`, `VerificationAgent`, and `ImplementationAgent` using `Agent` and manager composition via `Agent.as_tool()`; no handoffs.
- [ ] Run tests and confirm GREEN.

### Task 5: Runtime lifecycle, tracing, and runner boundary

**Files:**
- Create: `sovereign-omega-v2/python/openai_runtime/runtime.py`
- Create: `sovereign-omega-v2/python/tests/test_openai_runtime_runtime.py`

**Interfaces:**
- Produces: `OpenAIRuntime.run(request, auth_state, runner=None) -> OmegaRunResult`

- [ ] Write failing tests proving authority denial never invokes the runner.
- [ ] Write failing tests for stable SDK-error mapping, explicit model provenance, bounded max turns, and AEGIS execution id in trace metadata.
- [ ] Run tests and confirm RED.
- [ ] Implement the runner adapter using the Agents SDK `Runner`/`RunConfig` path and structured output conversion.
- [ ] Run tests and confirm GREEN.

### Task 6: Production bridge endpoint

**Files:**
- Modify: `sovereign-omega-v2/python/bridge.py`
- Create: `sovereign-omega-v2/python/tests/test_openai_runtime_bridge.py`

**Interfaces:**
- Produces HTTP: `POST /v1/omega/run`

- [ ] Write failing bridge tests for malformed request, unauthorized caller, disabled runtime, policy denial, and mocked structured success.
- [ ] Run tests and confirm RED.
- [ ] Add the smallest route integration that authenticates first, normalizes the request, performs authority admission, and invokes `OpenAIRuntime` only when admitted.
- [ ] Run focused bridge tests and confirm GREEN.

### Task 7: Regression, security, and draft PR

**Files:**
- Modify only if needed for test discovery/documentation: existing Python test config/docs.

- [ ] Run all new OpenAI runtime tests offline with no network/API call.
- [ ] Run existing Python bridge/runtime regression tests relevant to modified code.
- [ ] Run syntax/import checks for all new modules.
- [ ] Verify `OPENAI_API_KEY` is referenced only server-side and no secret value is committed.
- [ ] Verify diff contains no production deployment or main-branch mutation.
- [ ] Open a draft PR describing exact verified results, remaining live-smoke blocker, and epistemic status.

## Admission Gate

A live D0 smoke test is a separate operator-approved step after the offline suite is green and an API credential is securely available. Passing one live call establishes only transport/runtime viability; it does not establish AGI/ASI or production admission.
