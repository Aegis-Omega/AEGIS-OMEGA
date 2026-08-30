# GATE 219 — Constitutional Claude API Layer
## Epistemic Tier: T2 · Sovereign Omega v2

This document describes the four client modules that form the constitutional AI
integration layer in `sovereign-omega-v2/src/api/`. Every AI call made through
this layer is hash-certified, tier-stamped, and replay-reconstructable.

---

## Architecture Overview

```
caller
  │
  ├─► ConstitutionalClaudeClient  (claude-client.ts)
  │     └─ hashValue(prompt) → request_hash
  │     └─ inject AEGIS constitutional system prompt
  │     └─ Anthropic SDK messages.create()
  │     └─ hashValue(response_text) → response_hash
  │     └─ hashValue(request_hash + response_hash) → chain_hash
  │     └─ deepFreeze(ConstitutionalResponse)
  │
  ├─► ConstitutionalPipeline  (constitutional-pipeline.ts)
  │     └─ Stage 1: hash-certify input
  │     └─ Stage 2: TajweedDFA phonological analysis
  │     └─ Stage 3: Abjad routing (Arabic text only)
  │     └─ Stage 4: enrich prompt with phonological context
  │     └─ Stage 5: ConstitutionalClaudeClient.send() or .think()
  │     └─ Stage 6: pipeline_hash = hash(input_hash + chain_hash + model)
  │
  ├─► ManagedAgentClient  (managed-agent-client.ts)
  │     └─ agents.create() → persistent AEGIS constitutional agent
  │     └─ sessions.create() → per-task container
  │     └─ sessions.stream() → SSE event stream
  │
  └─► AdminClient  (admin-client.ts)
        └─ raw fetch to /v1/organizations/* (requires ANTHROPIC_ADMIN_API_KEY)
```

**Constitutional invariant:** `AdaptivePower(T) ≤ ReplayVerifiability(T)` — every
AI inference is hash-bounded and can be replayed identically from its inputs.

---

## ConstitutionalClaudeClient

**File:** `src/api/claude-client.ts`  
**Schema version:** `1.0.0`  
**Tier:** T2 (engineering hypothesis — correct, not yet formally proven optimal)

### Constitutional System Prompt

Every call injects four directives unless `use_constitutional_prompt: false`:

| Directive | Enforces |
|-----------|---------|
| EPISTEMIC SOVEREIGNTY | Every claim must carry T0/T1/T2/T3 tier marking |
| CAUSAL ARCHITECTURE | No groundless claims — traceable causal chains only |
| OPERATIONAL REALISM | AdaptivePower ≤ ReplayVerifiability in every response |
| ADVERSARIAL SELF-CORRECTION | Flag the weakest point in every argument |

Additional system context is appended *after* the constitutional prompt with `---`
as separator so the model sees governance constraints first.

### Types

```typescript
// Immutable, deepFrozen after construction
interface ConstitutionalResponse {
  response_text: string
  model_id: string
  request_hash: SHA256Hex       // SHA-256 of {messages, model}
  response_hash: SHA256Hex      // SHA-256 of {response_text, model_id}
  chain_hash: SHA256Hex         // SHA-256 of {request_hash, response_hash}
  input_tokens: number
  output_tokens: number
  stop_reason: string
  epistemic_tier: EpistemicTier
  schema_version: '1.0.0'
  is_replay_reconstructable: true
}
```

### Methods

| Method | Description | Model default |
|--------|-------------|---------------|
| `send(request)` | Single-turn constitutional call | as specified |
| `stream(request)` | Streaming — yields `StreamChunk` deltas | as specified |
| `quickAsk(question)` | One-shot, no conversation history | `claude-haiku-4-5-20251001` |
| `think(messages)` | Extended thinking with `budget_tokens` | `claude-sonnet-4-6` |

### Epistemic tier assignment

| Condition | Tier assigned |
|-----------|--------------|
| `stop_reason === 'max_tokens'` (truncated) | T3 — conjecture |
| Normal response | T2 — engineering hypothesis |
| Via `.think()` (extended thinking) | T1 — empirically validated |

### Usage

```typescript
import { ConstitutionalClaudeClient } from './src/api/claude-client.js'

const client = new ConstitutionalClaudeClient()  // reads ANTHROPIC_API_KEY

// Single-turn call
const response = await client.send({
  messages: [{ role: 'user', content: 'Assess the latency invariant T2→T1 promotion criteria.' }],
  model: 'claude-opus-4-8',
  max_tokens: 2048,
})

console.log(response.chain_hash)       // replay anchor
console.log(response.epistemic_tier)   // EpistemicTier.T2
console.log(response.is_replay_reconstructable)  // true

// Streaming
for await (const chunk of client.stream({ messages, model, max_tokens: 1024 })) {
  if (!chunk.is_final) process.stdout.write(chunk.delta)
}

// Extended thinking (T1 output)
const thoughtResponse = await client.think(
  [{ role: 'user', content: 'Root-cause the martingale drift anomaly.' }],
  'claude-sonnet-4-6',
  8000,   // budget_tokens
  16000,  // max_tokens
)
```

### Singleton

```typescript
import { claudeClient } from './src/api/claude-client.js'
await claudeClient.quickAsk('Is the gossip epoch sealed?')
```

---

## ConstitutionalPipeline

**File:** `src/api/constitutional-pipeline.ts`  
**Schema version:** `1.0.0`  
**Tier:** T2

### Pipeline stages

```
InputText
  Stage 1: input_hash = SHA-256({text})
  Stage 2: TajweedDFA analysis → {activeRules, ruleCount, hasArabic}
  Stage 3: if hasArabic → AbjadEncoder → {sum, node, dr, isTriadic}
  Stage 4: enrich prompt with phonological context annotations
  Stage 5: claude_response = client.send() or client.think()
  Stage 6: pipeline_hash = SHA-256({input_hash, request_hash, response_hash, model})
  → PipelineResult (deepFrozen, is_replay_reconstructable: true)
```

### Tajweed DFA

Pure TypeScript mirror of the Rust `tajweed_dfa.rs` module (Gate 216). Classifies
Arabic codepoints into tajweed phoneme classes and applies transition rules:

| Rule | Trigger |
|------|---------|
| IdghamWithGhunnah | NoonSakinah/Tanween before ي م و ن |
| IdghamWithoutGhunnah | NoonSakinah/Tanween before ل ر |
| Iqlab | NoonSakinah/Tanween before ب |
| Ikhfa | NoonSakinah/Tanween before 15 specified codepoints |
| Idhar | NoonSakinah/Tanween before six halqi letters |

### Abjad routing

Maps Arabic characters to their Abjad numerical values (ا=1 … غ=1000), computes
`sum % 12` for the dodecagonal node, and `digitalRoot(sum)` for triadic detection
(DR ∈ {3, 6, 9}).

### Types

```typescript
interface PipelineResult {
  input_text: string
  input_hash: SHA256Hex
  analysis: {
    tajweed: { hasArabic, activeRuleCount, ruleBreakdown, dominantRule }
    abjad: { sum, node, dr, isTriadic } | null
  }
  claude_response: ConstitutionalResponse
  pipeline_hash: SHA256Hex          // all-stage chain hash
  epistemic_tier: EpistemicTier
  schema_version: '1.0.0'
  is_replay_reconstructable: true
}
```

### Usage

```typescript
import { ConstitutionalPipeline } from './src/api/constitutional-pipeline.js'

const pipeline = new ConstitutionalPipeline()

// Single input
const result = await pipeline.run('بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ', {
  model: 'claude-opus-4-8',
  maxTokens: 2048,
  useThinking: false,
})

console.log(result.analysis.tajweed.hasArabic)    // true
console.log(result.analysis.abjad?.node)          // 0–11
console.log(result.pipeline_hash)                 // full stage chain

// Batch
const results = await pipeline.runBatch(['text1', 'نص عربي'], { model: 'claude-sonnet-4-6' })
```

### Singleton

```typescript
import { constitutionalPipeline } from './src/api/constitutional-pipeline.js'
const result = await constitutionalPipeline.run(inputText)
```

---

## ManagedAgentClient

**File:** `src/api/managed-agent-client.ts`  
**Schema version:** `1.0.0`  
**Tier:** T2  
**Beta header:** `managed-agents-2026-04-01`

### Agent definition

The AEGIS constitutional agent is created once and reused across sessions:

```
Name:   AEGIS-Ω Constitutional Agent
Model:  claude-sonnet-4-6
Tools:  bash_20250124, text_editor_20250429, web_search_20250305
Prompt: AEGIS constitutional system prompt + RALPH loop instructions
```

**Critical:** Call `ensureAgent()` at startup, not in the request path. Store
`agentId` and pass it to subsequent sessions. Do not call `agents.create()` on
every request.

### Session lifecycle

```
ensureAgent()           → string (agentId, cached after first call)
startSession(task)      → AgentSession {session_id, agent_id, status, created_at}
streamSession(id)       → AsyncGenerator<SessionEvent>
sendEvent(id, message)  → void
getSession(id)          → AgentSession
interrupt(id)           → void
```

### Usage

```typescript
import { ManagedAgentClient } from './src/api/managed-agent-client.js'

const client = new ManagedAgentClient()

// Create agent once at app startup
const agentId = await client.ensureAgent()

// Start a task session
const session = await client.startSession(
  'Verify the martingale boundedness invariant by running the stress test suite.'
)

// Stream events
for await (const event of client.streamSession(session.session_id)) {
  console.log(`[${event.type}] ${event.content}`)
  if (event.type === 'status' && event.content.includes('completed')) break
}
```

### Error handling

`ensureAgent()` throws `Error('[MANAGED_AGENT] Failed to create agent: ...')` if
Managed Agents are not available on the API key. Handle this at startup and fall
back to `ConstitutionalClaudeClient` for regions/tiers without Managed Agents.

---

## AdminClient

**File:** `src/api/admin-client.ts`  
**Schema version:** `1.0.0`  
**Tier:** T2  
**Required env:** `ANTHROPIC_ADMIN_API_KEY` (organization-level key, not workspace key)

### Methods

| Method | API endpoint | Returns |
|--------|-------------|---------|
| `getOrg()` | `GET /v1/organizations/me` | `OrgInfo` |
| `listApiKeys(limit?)` | `GET /v1/organizations/api_keys` | `ApiKeyInfo[]` |
| `listWorkspaces(limit?)` | `GET /v1/organizations/workspaces` | `WorkspaceInfo[]` |
| `createWorkspace(name)` | `POST /v1/organizations/workspaces` | `WorkspaceInfo` |
| `summary()` | all three in parallel | `{org, activeKeyCount, workspaceCount}` |

### Usage

```typescript
import { AdminClient } from './src/api/admin-client.js'

// Requires ANTHROPIC_ADMIN_API_KEY
const admin = new AdminClient()
const { org, activeKeyCount, workspaceCount } = await admin.summary()
console.log(`Org: ${org.name} — ${activeKeyCount} active keys, ${workspaceCount} workspaces`)
```

---

## Environment Variables

| Variable | Used by | Required |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | `ConstitutionalClaudeClient`, `ManagedAgentClient` | Yes (for AI calls) |
| `ANTHROPIC_ADMIN_API_KEY` | `AdminClient` | Yes (for admin operations) |

---

## Hash Chain Integrity

Every `ConstitutionalResponse` carries three hashes that form a tamper-evident chain:

```
request_hash  = SHA-256(canonicalizeJCS({messages, model}))
response_hash = SHA-256(canonicalizeJCS({response_text, model_id}))
chain_hash    = SHA-256(canonicalizeJCS({request_hash, response_hash}))
```

The `pipeline_hash` in `PipelineResult` extends this chain:

```
pipeline_hash = SHA-256(canonicalizeJCS({
  input_hash,       ← input certification
  request_hash,     ← prompt hash from claude_response
  response_hash,    ← output hash from claude_response
  model,            ← model pinning
}))
```

To verify replay integrity, re-run the same inputs through the pipeline and compare
`chain_hash` values. Determinism is guaranteed by `canonicalizeJCS` (RFC 8785 JCS)
and `deepFreeze` on all response objects.

---

## Tier Constraints

| What | Tier | Why |
|------|------|-----|
| `hashValue()` output | T0 | SHA-256 over RFC 8785 — deterministic, formally specified |
| `deepFreeze()` enforcement | T0 | JavaScript `Object.freeze()` — mechanically enforced |
| Constitutional system prompt | T2 | Model compliance is a hypothesis, not a proof |
| `epistemic_tier` inference | T2 | Heuristic (stop_reason, length) — not formally validated |
| Tajweed DFA | T2 | Mirrors Rust implementation — correctness not formally proven |
| Abjad routing | T2 | Numerical computation is T0; phonological significance is T3 |
| Managed agent session isolation | T2 | Anthropic cloud guarantee — not independently verified |

---

## Test Coverage Gaps (T2 — as of Gate 219)

The following scenarios have no test coverage and should be addressed in Gates 220+:

| Gap | Risk |
|-----|------|
| `send()` with `ANTHROPIC_API_KEY` unset | Unhandled rejection at `Anthropic()` constructor |
| `send()` API timeout / 5xx | No retry or error surfacing |
| `stream()` SSE disconnection mid-stream | Generator may throw; not caught by callers |
| `think()` with `budget_tokens > max_tokens` | SDK will return 400; not validated pre-flight |
| `ConstitutionalPipeline.runBatch()` partial failure | `Promise.all` short-circuits; no partial result |
| `ensureAgent()` with invalid API key | Error message may leak key prefix in logs |
| `AdminClient` missing admin key | Constructor throws; not documented for callers |
| Hash chain determinism across Node.js versions | `hashValue` uses SubtleCrypto — not cross-platform verified |

---

## Related Documents

- `docs/GATE_202_HARNESS_SDK.md` — SDK harness design
- `docs/GATE_204_ECCF_SECURITY_ALIGNMENT.md` — EU AI Act compliance context
- `docs/SKILL_HARNESS_SPECIFICATION.md` — skill catalog that invokes this API layer
- `sovereign-omega-v2/CLAUDE.md` — frozen constitutional files and build gate sequence
- `sovereign-omega-v2/src/core/canonicalize.ts` — RFC 8785 JCS implementation (T0)
- `sovereign-omega-v2/src/core/hashing.ts` — `hashValue()` — the only permitted hash path
