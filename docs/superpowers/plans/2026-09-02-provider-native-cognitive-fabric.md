# Provider-Native Cognitive Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic provider-native deep-cognition policy layer that maximizes provider reasoning quality per work class while preserving AEGIS authority conservation and exact execution provenance.

**Architecture:** Add a pure TypeScript profile selector beside the existing swarm router, test it independently, then wire only provenance-safe profile selection into provider execution surfaces. This slice does not change quorum or admission semantics and does not perform live provider calls.

**Tech Stack:** TypeScript 5.x, Vitest, existing AEGIS hashing/immutability primitives, provider REST/SDK adapters in later slices.

**Spec:** `docs/superpowers/specs/2026-09-02-provider-native-cognitive-fabric-design.md`

## Global Constraints

- Raw provider output authority is always `NONE`.
- No provider framework replaces AEGIS admission/effect verification.
- Model slugs are defaults/overrides, never permanent constitutional identities.
- Exact effective model and reasoning controls must be recordable in provenance.
- Physical quantum execution remains a separately authorized capability.

---

### Task 1: Provider cognitive profile contract

**Files:**
- Create: `sovereign-omega-v2/src/agents/coordination/provider-cognition.ts`
- Test: `sovereign-omega-v2/test/agents/provider-cognition.test.ts`

**Interfaces:**
- Produces: `ProviderName`, `CognitiveWorkClass`, `ProviderCognitiveProfile`, `selectProviderCognitiveProfile(provider, workClass, overrides?)`.
- Guarantees: deterministic output; frontier/formal OpenAI uses max reasoning; Anthropic adaptive/high; Gemini high thinking; all raw authority `NONE`.

- [ ] Write tests for deep provider-native profiles and authority conservation.
- [ ] Run the focused test and verify RED because the module does not exist.
- [ ] Implement the minimal pure selector.
- [ ] Re-run focused tests and verify GREEN.
- [ ] Run TypeScript typecheck for the new module/test surface.

### Task 2: Execution receipt contract

**Files:**
- Create: `sovereign-omega-v2/src/agents/coordination/provider-execution-receipt.ts`
- Test: `sovereign-omega-v2/test/agents/provider-execution-receipt.test.ts`

**Interfaces:**
- Consumes: `ProviderCognitiveProfile`.
- Produces: `ProviderExecutionReceiptV1` and `buildProviderExecutionReceiptV1` binding provider, model, reasoning profile, task digest, output digest, tool-policy digest and `authority_class: "NONE"`.

- [ ] Write deterministic-receipt and anti-authority-escalation tests.
- [ ] Verify RED before implementation.
- [ ] Implement minimal frozen/hash-linked receipt construction using existing AEGIS hashing primitives.
- [ ] Verify focused GREEN and typecheck.

### Task 3: Remove stale OpenAI constitutional model identity

**Files:**
- Modify: `sovereign-omega-v2/src/constitutional/coordinator.ts`
- Test: existing coordinator tests plus a new assertion if needed.

**Interfaces:**
- Consumes: provider cognitive profile/configured model rather than a permanent `gpt-4o` constitutional identity.
- Preserves: provider role and replay contract; no authority increase.

- [ ] Add failing test proving OpenAI member identity is configuration-bound rather than hard-coded to `gpt-4o`.
- [ ] Verify RED.
- [ ] Replace stale fixed model with a policy/configured model identifier while keeping deterministic defaults.
- [ ] Verify coordinator tests and typecheck.

### Task 4: OpenAI Responses request builder

**Files:**
- Create: `sovereign-omega-v2/src/agents/providers/openai-responses.ts`
- Test: `sovereign-omega-v2/test/agents/openai-responses.test.ts`

**Interfaces:**
- Consumes: `ProviderCognitiveProfile`, task input, optional privacy-preserving safety identifier and allowed tools.
- Produces: a pure serializable Responses API request object; no network call in this slice.
- For frontier/formal work, binds configured flagship model and maximum reasoning effort; records stateless/storage policy explicitly.

- [ ] Write failing request-shape tests.
- [ ] Verify RED.
- [ ] Implement pure builder.
- [ ] Verify GREEN/typecheck.

### Task 5: Documentation and integration proof

**Files:**
- Modify: `docs/PROOF.md` or nearest provider architecture documentation if present.
- Create/update focused README section only if the repo already documents model routing there.

- [ ] Document `information amplification != authority amplification` and provider-native configuration semantics.
- [ ] Run focused tests and full available typecheck/test subset.
- [ ] Inspect exact branch diff for accidental constitutional/security changes.
- [ ] Open a DRAFT PR; hosted CI becomes the exact-head authority.
