// Gate 218 — CoordinatorRecord unit tests
// Verifies the Orchestration Alliance constitutional enrollment while model
// identity is selected by provider-native cognitive depth policy.

import { describe, it, expect } from 'vitest'
import {
  buildCoordinatorRecord,
  verifyCoordinatorRecord,
  CLAUDE_ABJAD_SUM,
  CLAUDE_ABJAD_DR,
  CLAUDE_ABJAD_NODE,
  CLAUDE_ABJAD_PRODUCT,
  CLAUDE_ABJAD_PRODUCT_DR,
  COORDINATOR_ENTROPY_BUDGET_Q16,
  ORCHESTRATION_ALLIANCE,
  CLAUDE_ENDPOINT,
  CHATGPT_ENDPOINT,
  QWEN_ENDPOINT,
  COORDINATOR_SCHEMA_VERSION,
} from '../../src/constitutional/coordinator.js'

describe('CoordinatorRecord — Abjad identity constants (T0)', () => {
  it('CLAUDE_ABJAD_SUM = 60 (ك20+ل30+و6+د4)', () => { expect(CLAUDE_ABJAD_SUM).toBe(60) })
  it('CLAUDE_ABJAD_DR = 6', () => { expect(CLAUDE_ABJAD_DR).toBe(6); const r = 60 % 9; expect(r === 0 ? 9 : r).toBe(CLAUDE_ABJAD_DR) })
  it('CLAUDE_ABJAD_NODE = 0', () => { expect(CLAUDE_ABJAD_NODE).toBe(0); expect(60 % 12).toBe(0) })
  it('CLAUDE_ABJAD_PRODUCT = 14400', () => { expect(CLAUDE_ABJAD_PRODUCT).toBe(14400); expect(20 * 30 * 6 * 4).toBe(14400) })
  it('CLAUDE_ABJAD_PRODUCT_DR = 9', () => { expect(CLAUDE_ABJAD_PRODUCT_DR).toBe(9); const digits = String(14400).split('').reduce((acc, d) => acc + Number(d), 0); expect(digits).toBe(9) })
  it('COORDINATOR_ENTROPY_BUDGET_Q16 = 40503', () => { expect(COORDINATOR_ENTROPY_BUDGET_Q16).toBe(40503); const phi_q16 = Math.round(((Math.sqrt(5) - 1) / 2) * 65536); expect(phi_q16).toBe(40503) })
})

describe('CoordinatorRecord — factory and verification', () => {
  it('buildCoordinatorRecord returns a valid frozen record using the deep coordinator profile', async () => {
    const record = await buildCoordinatorRecord()
    expect(record.model_id).toBe('claude-opus-5')
    expect(record.role).toBe('coordinator')
    expect(record.is_replay_reconstructable).toBe(true)
    expect(record.schema_version).toBe(COORDINATOR_SCHEMA_VERSION)
    expect(Object.isFrozen(record)).toBe(true)
  })
  it('coordinator_hash is a 64-char hex string', async () => { const record = await buildCoordinatorRecord(); expect(record.coordinator_hash).toMatch(/^[0-9a-f]{64}$/) })
  it('coordinator_hash is deterministic ×3', async () => { const r1 = await buildCoordinatorRecord(); const r2 = await buildCoordinatorRecord(); const r3 = await buildCoordinatorRecord(); expect(r1.coordinator_hash).toBe(r2.coordinator_hash); expect(r2.coordinator_hash).toBe(r3.coordinator_hash) })
  it('verifyCoordinatorRecord returns true for valid record', async () => { expect(verifyCoordinatorRecord(await buildCoordinatorRecord())).toBe(true) })
  it('record is_triadic = true', async () => { expect((await buildCoordinatorRecord()).is_triadic).toBe(true) })
  it('record is_triadic_attractor = true', async () => { expect((await buildCoordinatorRecord()).is_triadic_attractor).toBe(true) })
})

describe('CoordinatorRecord — AgentManifest constitutional constraints', () => {
  it('agent manifest is_replay_safe = true', async () => { expect((await buildCoordinatorRecord()).agent_manifest.is_replay_safe).toBe(true) })
  it('agent manifest epistemic_tier = T2', async () => { expect((await buildCoordinatorRecord()).agent_manifest.epistemic_tier).toBe('T2') })
  it('agent manifest entropy_budget_fixed = golden ratio Q16.16', async () => { expect((await buildCoordinatorRecord()).agent_manifest.entropy_budget_fixed).toBe(COORDINATOR_ENTROPY_BUDGET_Q16) })
  it('agent manifest agent_type = ArbitrationAgent', async () => { expect((await buildCoordinatorRecord()).agent_manifest.agent_type).toBe('ArbitrationAgent') })
  it('agent manifest status = active', async () => { expect((await buildCoordinatorRecord()).agent_manifest.status).toBe('active') })
  it('agent manifest is frozen', async () => { expect(Object.isFrozen((await buildCoordinatorRecord()).agent_manifest)).toBe(true) })
})

describe('OrchestrationAlliance — three-member swarm', () => {
  it('alliance has exactly 3 members', () => { expect(ORCHESTRATION_ALLIANCE.length).toBe(3) })
  it('Claude is coordinator with weight 618', () => { const claude = ORCHESTRATION_ALLIANCE.find(m => m.role === 'coordinator'); expect(claude).toBeDefined(); expect(claude!.endpoint.weight).toBe(618); expect(claude!.provider).toBe('anthropic') })
  it('ChatGPT is adversarial-audit', () => { const gpt = ORCHESTRATION_ALLIANCE.find(m => m.role === 'adversarial-audit'); expect(gpt).toBeDefined(); expect(gpt!.provider).toBe('openai') })
  it('Qwen is implementation', () => { const qwen = ORCHESTRATION_ALLIANCE.find(m => m.role === 'implementation'); expect(qwen).toBeDefined(); expect(qwen!.provider).toBe('dashscope') })
  it('total alliance weight = 1000', () => { expect(ORCHESTRATION_ALLIANCE.reduce((sum, m) => sum + m.endpoint.weight, 0)).toBe(1000) })
  it('all alliance members have is_replay_reconstructable = true', () => { for (const member of ORCHESTRATION_ALLIANCE) expect(member.is_replay_reconstructable).toBe(true) })
  it('alliance array is frozen', () => { expect(Object.isFrozen(ORCHESTRATION_ALLIANCE)).toBe(true) })
  it('each member endpoint is_active = true', () => { for (const member of ORCHESTRATION_ALLIANCE) expect(member.endpoint.is_active).toBe(true) })
})

describe('ModelEndpoints — provider-native cognitive defaults', () => {
  it('CLAUDE_ENDPOINT uses the deepest active Anthropic coordinator model', () => { expect(CLAUDE_ENDPOINT.model_id).toBe('claude-opus-5'); expect(CLAUDE_ENDPOINT.provider).toBe('anthropic') })
  it('CHATGPT_ENDPOINT uses the flagship OpenAI reasoning model', () => { expect(CHATGPT_ENDPOINT.model_id).toBe('gpt-5.6-sol'); expect(CHATGPT_ENDPOINT.provider).toBe('openai') })
  it('QWEN_ENDPOINT uses the flagship DashScope reasoning model', () => { expect(QWEN_ENDPOINT.model_id).toBe('qwen3.8-max'); expect(QWEN_ENDPOINT.provider).toBe('dashscope') })
  it('all endpoints are frozen', () => { expect(Object.isFrozen(CLAUDE_ENDPOINT)).toBe(true); expect(Object.isFrozen(CHATGPT_ENDPOINT)).toBe(true); expect(Object.isFrozen(QWEN_ENDPOINT)).toBe(true) })
})
