# Provider-Native Cognitive Fabric Implementation Plan

> **For agentic workers:** Use TDD and exact-head verification. Hosted CI remains the final repository authority.

**Goal:** Add a deterministic provider-native deep-cognition layer that maximizes reasoning quality per work class while preserving AEGIS authority conservation and exact execution provenance.

**Architecture:** Pure TypeScript provider profiles + pure provider request builders + deterministic execution receipts. This slice does not change quorum, admission, or effect-verification semantics and performs no live provider calls.

**Spec:** `docs/superpowers/specs/2026-09-02-provider-native-cognitive-fabric-design.md`

## Global Constraints

- Raw provider output authority is always `NONE`.
- No provider framework replaces AEGIS admission/effect verification.
- Model slugs are refreshable defaults/overrides, never permanent constitutional identities.
- Exact effective model and reasoning controls are receipt-bound provenance.
- Physical quantum execution remains a separately authorized capability.

### Task 1: Provider cognitive profile contract — IMPLEMENTED

**Files:**
- `sovereign-omega-v2/src/agents/coordination/provider-cognition.ts`
- `sovereign-omega-v2/test/agents/provider-cognition.test.ts`

- [x] RED-first provider-depth tests.
- [x] OpenAI frontier/formal: `gpt-5.6-sol`, max/pro.
- [x] Anthropic frontier/formal: `claude-opus-5`, adaptive/max; implementation xhigh.
- [x] Gemini non-routine: `gemini-3.1-pro-preview`, high thinking.
- [x] Qwen non-routine: `qwen3.8-max`, xhigh reasoning.
- [x] All raw output authority = `NONE`.

### Task 2: Execution receipt contract — IMPLEMENTED

**Files:**
- `sovereign-omega-v2/src/agents/coordination/provider-execution-receipt.ts`
- `sovereign-omega-v2/test/agents/provider-execution-receipt.test.ts`

- [x] Deterministic receipt test.
- [x] Bind provider/model/work class/reasoning/task/output/tool-policy digests.
- [x] Hard-bind `authority_class = "NONE"`.

### Task 3: Constitutional model identity decoupling — IMPLEMENTED

**Files:**
- `sovereign-omega-v2/src/constitutional/coordinator.ts`
- `sovereign-omega-v2/test/unit/coordinator.test.ts`

- [x] Remove stale fixed `gpt-4o`/old provider model identity from alliance endpoints.
- [x] Derive endpoint models from provider cognition policy.
- [x] Preserve alliance roles, weights, replay contract and authority semantics.

### Task 4: Provider-native execution request builders — IMPLEMENTED

**OpenAI**
- `sovereign-omega-v2/src/agents/providers/openai-responses.ts`
- `sovereign-omega-v2/test/agents/openai-responses.test.ts`
- [x] Responses API request, `store=false`, encrypted reasoning continuity, max/pro for frontier/formal, safety identifier support.

**Anthropic**
- `sovereign-omega-v2/src/agents/providers/anthropic-messages.ts`
- `sovereign-omega-v2/test/agents/anthropic-messages.test.ts`
- [x] Messages API request, adaptive thinking, max/xhigh effort by work class, omitted thinking display, AEGIS-authorized tools only.

**Gemini**
- `sovereign-omega-v2/src/agents/providers/gemini-interactions.ts`
- `sovereign-omega-v2/test/agents/gemini-interactions.test.ts`
- [x] Interactions API request, `store=false`, high thinking for non-routine work, no thought summaries, AEGIS-authorized tools only.

**DashScope/Qwen**
- `sovereign-omega-v2/src/agents/providers/qwen-responses.ts`
- `sovereign-omega-v2/test/agents/qwen-responses.test.ts`
- [x] Model Studio Responses request, `store=false`, xhigh maximum-intensity reasoning for non-routine work, AEGIS-authorized tools only.

### Task 5: Verification and documentation — IN PROGRESS

- [x] Ratified design updated to current vendor APIs/defaults.
- [x] RED compile failure observed for missing provider request builders.
- [x] Isolated TypeScript smoke GREEN for Anthropic/Gemini/Qwen request builders.
- [x] DRAFT PR #365 opened.
- [ ] Re-resolve current exact PR head after all documentation/provider commits.
- [ ] Require terminal hosted CI for current exact head; older-head GREEN is stale.
- [ ] Inspect any exact-head failure by job/step and classify code vs infrastructure/auth boundary.
- [ ] Keep DRAFT / NOT_ADMITTED until terminal exact-head verification.

### Follow-up slice after this PR is exact-head GREEN

- Wire pure request builders into authenticated network adapters/Agents SDK runtime behind capability manifests.
- Add provider-specific response parsers that produce `ProviderExecutionReceiptV1` from observed effective execution metadata.
- Add cross-provider UCR ablation/eval harness: quality gain, false-promotion rate, verified progress per compute, authority violations.
- Add SandboxAgent/compute-plane integration without granting sandbox authority.
