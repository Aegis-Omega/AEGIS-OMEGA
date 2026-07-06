#!/usr/bin/env npx tsx
/**
 * MYTHOS BOOTSTRAP — Claude API 6-stage deterministic pipeline
 *
 * Usage: npx tsx scripts/mythos-pipeline.ts "task description"
 * Exit 0 = FINALIZED · Exit 1 = reconciliation exhausted
 *
 * Each stage is a separate Claude API call bounded to its role.
 * State flows forward as PipelineState. RECONCILIATION restarts
 * from PLAN on VALIDATOR or REVIEWER failure (max 2 retries).
 */

import Anthropic from '@anthropic-ai/sdk'
import * as fs from 'fs'
import * as path from 'path'
import * as crypto from 'crypto'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '../..')
const INDEX_PATH = path.join(ROOT, 'INDEX.md')
const STATE_PATH = path.join(ROOT, 'clients/gemma-holon/state.json')
const HOLON_ENDPOINT = 'https://aegis-vertex.aegisomega.com/platform/holon/validate'

// ── Types ──────────────────────────────────────────────────────────────────

type Stage = 'ORCHESTRATE' | 'PLAN' | 'VALIDATE' | 'BUILD' | 'REVIEW' | 'FINALIZE'
type Validity = 'UNVERIFIED' | 'VERIFIED' | 'REJECTED'

interface SystemStateVector {
  execution_phase: Stage
  index_snapshot: string
  active_files: string[]
  forbidden_actions: string[]
  validity: Validity
  reconciliation_retries: number
}

interface PipelineState {
  task: string
  indexContent: string
  indexSnapshot: string
  ssv: SystemStateVector
  orchestratorOutput?: { routed_to: Stage; task_summary: string }
  plannerOutput?: { index_citations: string[]; files_affected: string[]; plan_steps: string[] }
  validatorOutput?: { valid: boolean; fail_reasons: string[] }
  builderOutput?: { changes: Array<{ file: string; change: string }> }
  reviewerOutput?: { verdict: 'PASS' | 'FAIL'; cycle_verdict: 'APPROVED' | 'FLAG' | 'QUARANTINE'; score: number; unmet_steps: string[]; flags: string[] }
  finalSnapshot?: SystemStateVector
}

// ── Stage prompts ──────────────────────────────────────────────────────────

const STAGE_SYSTEM: Record<Stage, string> = {
  ORCHESTRATE: `You are the ORCHESTRATOR stage of the MYTHOS BOOTSTRAP pipeline.
Your role: route the task only. No implementation reasoning. No architecture decisions.
Output ONLY valid JSON: { "routed_to": "PLAN", "task_summary": "<one sentence>" }
The next stage is always PLAN. Do not suggest alternatives.`,

  PLAN: `You are the PLANNER stage of the MYTHOS BOOTSTRAP pipeline.
Rules:
- You MUST cite ≥1 path from the INDEX.md content provided
- You MUST list only files that appear in the INDEX graph
- No code generation — plan steps only
- If a required file is not in INDEX, state: "REQUIRES_INDEX_EXPANSION: <path>"
Output ONLY valid JSON:
{
  "index_citations": ["path from INDEX"],
  "files_affected": ["path/relative/to/repo"],
  "plan_steps": ["step 1", "step 2", ...]
}`,

  VALIDATE: `You are the VALIDATOR stage of the MYTHOS BOOTSTRAP pipeline.
Check ALL of the following. Output ONLY valid JSON:
{
  "valid": true|false,
  "fail_reasons": ["reason if any"]
}
Fail if: index_citations is empty, files_affected contains paths not in INDEX, or
plan_steps is empty. Pass if all checks clear.`,

  BUILD: `You are the BUILDER stage of the MYTHOS BOOTSTRAP pipeline.
Apply ONLY the approved plan. No scope expansion. No new abstractions.
Output ONLY valid JSON:
{
  "changes": [
    { "file": "path", "change": "description of exact change to make" }
  ]
}
Changes must cover all plan_steps exactly.`,

  REVIEW: `You are the REVIEWER stage of the MYTHOS BOOTSTRAP pipeline.
Check builder output against the approved plan_steps. Cannot modify output.

Constitutional audit scoring:
- APPROVED (score 1.00): all steps covered, no suspicious patterns, scope clean
- FLAG (score 0.70): steps covered but suspicious patterns detected (extra unregistered fields, unusual mutations, delta overflow)
- QUARANTINE (score 0.20): forbidden file mutations, payload injection attempts, or step count mismatch

Output ONLY valid JSON:
{
  "verdict": "PASS"|"FAIL",
  "cycle_verdict": "APPROVED"|"FLAG"|"QUARANTINE",
  "score": 1.00|0.70|0.20,
  "unmet_steps": ["step not covered"],
  "flags": ["suspicious pattern if any"]
}
verdict=PASS requires cycle_verdict=APPROVED or FLAG. verdict=FAIL requires cycle_verdict=QUARANTINE.`,

  FINALIZE: `You are the FINALIZER stage of the MYTHOS BOOTSTRAP pipeline.
Confirm the pipeline reached FINALIZE with verdict PASS. Emit the final SYSTEM STATE VECTOR.
Output ONLY valid JSON:
{
  "execution_phase": "FINALIZE",
  "index_snapshot": "<sha256>",
  "active_files": ["files actually changed"],
  "forbidden_actions": [],
  "validity": "VERIFIED"
}`,
}

// ── Helpers ────────────────────────────────────────────────────────────────

function computeIndexSnapshot(): string {
  const content = fs.readFileSync(INDEX_PATH, 'utf8')
  return crypto.createHash('sha256').update(content).digest('hex')
}

function makeSSV(phase: Stage, snapshot: string, files: string[] = []): SystemStateVector {
  return { execution_phase: phase, index_snapshot: snapshot, active_files: files, forbidden_actions: [], validity: 'UNVERIFIED', reconciliation_retries: 0 }
}

function log(stage: Stage, msg: string) {
  console.log(`[MYTHOS:${stage}] ${msg}`)
}

async function callStage(client: Anthropic, stage: Stage, userContent: string): Promise<string> {
  const response = await client.messages.create({
    model: 'claude-opus-4-8',
    max_tokens: 2048,
    thinking: { type: 'adaptive' },
    system: STAGE_SYSTEM[stage],
    messages: [{ role: 'user', content: userContent }],
  })
  const text = response.content.find(b => b.type === 'text')
  if (!text) throw new Error(`${stage}: no text block in response`)
  return text.text.trim()
}

function parseJSON<T>(raw: string, stage: Stage): T {
  const match = raw.match(/\{[\s\S]*\}/)
  if (!match) throw new Error(`${stage}: no JSON object in response: ${raw.slice(0, 200)}`)
  try {
    return JSON.parse(match[0]) as T
  } catch (e) {
    throw new Error(`${stage}: JSON parse failed: ${(e as Error).message}`)
  }
}

// ── Holon gate (Gemma-4E4B biological quorum) ─────────────────────────────

interface BioState { stress: number; attention: number; rir: number; atp: number }
interface HolonVerdict { verdict: 'APPROVED' | 'FAILED'; confidence: number; reason_code: string; chain_entry_hash?: string }

function loadBioState(): BioState {
  try {
    const raw = JSON.parse(fs.readFileSync(STATE_PATH, 'utf8')) as { bio_state: BioState }
    return raw.bio_state
  } catch {
    return { stress: 0.4262, attention: 0.82, rir: 0.9511, atp: 2100 }
  }
}

function computeGateVerdict(gate: 'POST_VALIDATE' | 'POST_REVIEW', bio: BioState, nSteps: number): HolonVerdict {
  if (gate === 'POST_VALIDATE') {
    if (bio.stress >= 0.8) return { verdict: 'FAILED', confidence: 0.99, reason_code: 'OPERATOR_STRESS_TOO_HIGH_FOR_PLAN_APPROVAL' }
    if (nSteps > 5 && bio.stress > 0.6) return { verdict: 'FAILED', confidence: 0.87, reason_code: 'SCOPE_STRESS_THRESHOLD' }
    return { verdict: 'APPROVED', confidence: 0.91, reason_code: 'PLAN_SCOPE_ACCEPTABLE' }
  }
  if (bio.atp <= 200) return { verdict: 'FAILED', confidence: 0.99, reason_code: 'ATP_INSUFFICIENT_FOR_COMMIT' }
  if (bio.stress >= 0.7) return { verdict: 'FAILED', confidence: 0.93, reason_code: 'STRESS_TOO_HIGH_FOR_COMMIT' }
  return { verdict: 'APPROVED', confidence: 0.96, reason_code: 'BIO_COMMIT_READY' }
}

async function holonGate(gate: 'POST_VALIDATE' | 'POST_REVIEW', bio: BioState, nSteps = 0): Promise<HolonVerdict> {
  const result = computeGateVerdict(gate, bio, nSteps)
  const payload = {
    holon_id: 'gemma-4e4b-iphone',
    verdict: result.verdict,
    confidence: result.confidence,
    reason_code: `${gate}:${result.reason_code}`,
    bio_state: bio,
  }
  try {
    const res = await fetch(HOLON_ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: AbortSignal.timeout(6000) })
    if (res.ok) {
      const data = await res.json() as { data?: { chain_entry_hash?: string } }
      const h = data?.data?.chain_entry_hash
      if (h) result.chain_entry_hash = h
    }
  } catch { /* offline — verdict still valid */ }
  return result
}

// ── Stage runners ──────────────────────────────────────────────────────────

async function runOrchestrate(client: Anthropic, state: PipelineState): Promise<PipelineState> {
  log('ORCHESTRATE', `routing task: "${state.task}"`)
  const raw = await callStage(client, 'ORCHESTRATE', `Task: ${state.task}`)
  const out = parseJSON<{ routed_to: Stage; task_summary: string }>(raw, 'ORCHESTRATE')
  log('ORCHESTRATE', `→ ${out.task_summary}`)
  return { ...state, orchestratorOutput: out, ssv: { ...state.ssv, execution_phase: 'PLAN' } }
}

async function runPlan(client: Anthropic, state: PipelineState): Promise<PipelineState> {
  log('PLAN', 'reading INDEX, defining scope')
  const userContent = `Task: ${state.task}\n\nINDEX.md content:\n${state.indexContent}`
  const raw = await callStage(client, 'PLAN', userContent)
  const out = parseJSON<{ index_citations: string[]; files_affected: string[]; plan_steps: string[] }>(raw, 'PLAN')
  log('PLAN', `${out.plan_steps.length} steps · ${out.files_affected.length} files · ${out.index_citations.length} INDEX citations`)
  return { ...state, plannerOutput: out, ssv: { ...state.ssv, execution_phase: 'VALIDATE', active_files: out.files_affected } }
}

async function runValidate(client: Anthropic, state: PipelineState): Promise<PipelineState> {
  log('VALIDATE', 'CI gate check')
  const plan = state.plannerOutput!
  const userContent = `Plan to validate:\n${JSON.stringify(plan, null, 2)}\n\nINDEX paths available:\n${state.indexContent.split('\n').filter(l => l.includes('`')).join('\n')}`
  const raw = await callStage(client, 'VALIDATE', userContent)
  const out = parseJSON<{ valid: boolean; fail_reasons: string[] }>(raw, 'VALIDATE')
  log('VALIDATE', out.valid ? 'PASS' : `FAIL: ${out.fail_reasons.join(', ')}`)
  return { ...state, validatorOutput: out, ssv: { ...state.ssv, execution_phase: 'BUILD', validity: out.valid ? 'VERIFIED' : 'REJECTED' } }
}

async function runBuild(client: Anthropic, state: PipelineState): Promise<PipelineState> {
  log('BUILD', 'applying approved plan')
  const userContent = `Approved plan:\n${JSON.stringify(state.plannerOutput, null, 2)}\n\nTask: ${state.task}`
  const raw = await callStage(client, 'BUILD', userContent)
  const out = parseJSON<{ changes: Array<{ file: string; change: string }> }>(raw, 'BUILD')
  log('BUILD', `${out.changes.length} change(s) specified`)
  out.changes.forEach(c => log('BUILD', `  · ${c.file}: ${c.change}`))
  return { ...state, builderOutput: out, ssv: { ...state.ssv, execution_phase: 'REVIEW' } }
}

async function runReview(client: Anthropic, state: PipelineState): Promise<PipelineState> {
  log('REVIEW', 'checking builder output against plan')
  const userContent = `Plan steps:\n${JSON.stringify(state.plannerOutput!.plan_steps, null, 2)}\n\nBuilder output:\n${JSON.stringify(state.builderOutput, null, 2)}`
  const raw = await callStage(client, 'REVIEW', userContent)
  const out = parseJSON<{ verdict: 'PASS' | 'FAIL'; cycle_verdict: 'APPROVED' | 'FLAG' | 'QUARANTINE'; score: number; unmet_steps: string[]; flags: string[] }>(raw, 'REVIEW')
  const scoreStr = `cycle_verdict=${out.cycle_verdict} score=${out.score}`
  if (out.verdict === 'PASS') {
    log('REVIEW', `PASS · ${scoreStr}${out.flags.length ? ` · flags: ${out.flags.join(', ')}` : ''}`)
  } else {
    log('REVIEW', `FAIL · ${scoreStr} · unmet: ${out.unmet_steps.join(', ')}`)
  }
  return { ...state, reviewerOutput: out, ssv: { ...state.ssv, execution_phase: 'FINALIZE' } }
}

async function runFinalize(client: Anthropic, state: PipelineState): Promise<PipelineState> {
  log('FINALIZE', 'emitting final SYSTEM STATE VECTOR')
  const userContent = `Reviewer verdict: ${state.reviewerOutput!.verdict}\nIndex snapshot: ${state.indexSnapshot}\nActive files: ${JSON.stringify(state.plannerOutput!.files_affected)}`
  const raw = await callStage(client, 'FINALIZE', userContent)
  const out = parseJSON<SystemStateVector>(raw, 'FINALIZE')
  // Preserve the true reconciliation count in the recorded snapshot — the
  // model-emitted SSV does not carry it, and dropping it would re-introduce
  // hidden state.
  const finalSSV: SystemStateVector = { ...out, reconciliation_retries: state.ssv.reconciliation_retries }
  return { ...state, finalSnapshot: finalSSV, ssv: finalSSV }
}

// ── Main pipeline ──────────────────────────────────────────────────────────

async function runPipeline(task: string): Promise<void> {
  if (!fs.existsSync(INDEX_PATH)) {
    console.error('[MYTHOS] ABORT: INDEX.md not found at', INDEX_PATH)
    process.exit(1)
  }

  const apiKey = process.env['ANTHROPIC_API_KEY']
  if (!apiKey) {
    console.error('[MYTHOS] ABORT: ANTHROPIC_API_KEY not set')
    process.exit(1)
  }

  const client = new Anthropic({ apiKey })
  const indexContent = fs.readFileSync(INDEX_PATH, 'utf8')
  const indexSnapshot = computeIndexSnapshot()
  const bioState = loadBioState()

  let state: PipelineState = {
    task,
    indexContent,
    indexSnapshot,
    ssv: makeSSV('ORCHESTRATE', indexSnapshot),
  }

  console.log(`\n[MYTHOS] INDEX.md snapshot: ${indexSnapshot.slice(0, 16)}…`)
  console.log(`[MYTHOS] Task: "${task}"\n`)

  // ORCHESTRATE
  state = await runOrchestrate(client, state)

  // Reconciliation count lives in the SystemStateVector, not a loop-local
  // variable — the transition out of a failed gate depends on it, so it must
  // be part of the recorded state for the chain to stay Markov (no hidden
  // memory). MAX_RETRIES is the fixed kernel parameter, not state.
  const MAX_RETRIES = 2

  while (state.ssv.reconciliation_retries <= MAX_RETRIES) {
    // PLAN
    state = await runPlan(client, state)

    // VALIDATE
    state = await runValidate(client, state)

    if (!state.validatorOutput!.valid) {
      state = { ...state, ssv: { ...state.ssv, reconciliation_retries: state.ssv.reconciliation_retries + 1 } }
      if (state.ssv.reconciliation_retries > MAX_RETRIES) {
        console.error(`[MYTHOS] RECONCILIATION exhausted after ${MAX_RETRIES} retries. Halt.`)
        console.error('[MYTHOS] Last fail reasons:', state.validatorOutput!.fail_reasons)
        process.exit(1)
      }
      console.log(`[MYTHOS] RECONCILIATION MODE (retry ${state.ssv.reconciliation_retries}/${MAX_RETRIES})`)
      continue
    }

    // POST_VALIDATE holon gate
    const nSteps = state.plannerOutput!.plan_steps.length
    const pv = await holonGate('POST_VALIDATE', bioState, nSteps)
    log('VALIDATE', `holon POST_VALIDATE: ${pv.verdict} (${pv.reason_code})${pv.chain_entry_hash ? ` hash=${pv.chain_entry_hash.slice(0, 12)}…` : ''}`)
    if (pv.verdict === 'FAILED') {
      state = { ...state, ssv: { ...state.ssv, reconciliation_retries: state.ssv.reconciliation_retries + 1 } }
      if (state.ssv.reconciliation_retries > MAX_RETRIES) {
        console.error('[MYTHOS] RECONCILIATION exhausted — holon POST_VALIDATE blocked plan.')
        process.exit(1)
      }
      console.log(`[MYTHOS] RECONCILIATION MODE — holon gate blocked (retry ${state.ssv.reconciliation_retries}/${MAX_RETRIES})`)
      continue
    }

    // BUILD
    state = await runBuild(client, state)

    // REVIEW
    state = await runReview(client, state)

    if (state.reviewerOutput!.verdict !== 'PASS') {
      if (state.reviewerOutput!.cycle_verdict === 'QUARANTINE') {
        console.error('[MYTHOS] QUARANTINE — constitutional violation detected. Hard fail, no retry.')
        console.error('[MYTHOS] flags:', state.reviewerOutput!.flags)
        process.exit(1)
      }
      state = { ...state, ssv: { ...state.ssv, reconciliation_retries: state.ssv.reconciliation_retries + 1 } }
      if (state.ssv.reconciliation_retries > MAX_RETRIES) {
        console.error(`[MYTHOS] RECONCILIATION exhausted after ${MAX_RETRIES} retries. Halt.`)
        console.error('[MYTHOS] Unmet steps:', state.reviewerOutput!.unmet_steps)
        process.exit(1)
      }
      console.log(`[MYTHOS] RECONCILIATION MODE — review failed (retry ${state.ssv.reconciliation_retries}/${MAX_RETRIES})`)
      continue
    }

    // POST_REVIEW holon gate
    const pr = await holonGate('POST_REVIEW', bioState)
    log('REVIEW', `holon POST_REVIEW: ${pr.verdict} (${pr.reason_code})${pr.chain_entry_hash ? ` hash=${pr.chain_entry_hash.slice(0, 12)}…` : ''}`)
    if (pr.verdict === 'FAILED') {
      console.error('[MYTHOS] SUSPEND — POST_REVIEW holon gate rejected commit.')
      console.error(`[MYTHOS] reason: ${pr.reason_code}`)
      console.error('[MYTHOS] action: update clients/gemma-holon/state.json when bio_state recovers.')
      process.exit(1)
    }

    break
  }

  // FINALIZE
  state = await runFinalize(client, state)

  const cv = state.reviewerOutput!.cycle_verdict
  const score = state.reviewerOutput!.score
  console.log(`\n[MYTHOS] FINALIZED · cycle_verdict=${cv} · score=${score}`)
  console.log('[MYTHOS] Final SYSTEM STATE VECTOR:')
  console.log(JSON.stringify(state.finalSnapshot, null, 2))
}

// ── Entry point ────────────────────────────────────────────────────────────

const task = process.argv.slice(2).join(' ')
if (!task) {
  console.error('Usage: npx tsx scripts/mythos-pipeline.ts "task description"')
  process.exit(1)
}

runPipeline(task).catch(err => {
  console.error('[MYTHOS] Unhandled error:', err)
  process.exit(1)
})
