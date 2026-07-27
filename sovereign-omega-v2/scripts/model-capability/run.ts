#!/usr/bin/env npx tsx
/**
 * MCB-001 runner — cross-model capability battery.
 *
 * Usage: ANTHROPIC_API_KEY=... npx tsx scripts/model-capability/run.ts <model-a> <model-b> [...]
 *
 * Protocol is frozen in PREREGISTRATION.md. This file executes it and records
 * results; it does not decide anything the preregistration did not already fix.
 *
 * Exit 0 = battery completed (verdict may be SEPARATED or UNRESOLVED).
 * Exit 1 = harness fault — no verdict.
 */

import Anthropic from '@anthropic-ai/sdk'
import * as crypto from 'crypto'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'
import { canonicalizeJCSString } from '../../src/core/canonicalize.js'
import { SYSTEM_PROMPT, TASKS, gradeOutput, type CapabilityTask } from './tasks.js'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPEATS = 5
const MAX_TOKENS = 1024
const TRANSPORT_RETRIES = 3

// Fixed by the preregistration, §7.
const MARGIN_TOTAL = 6
const MARGIN_PER_TASK = 3
const TASKS_REQUIRED = 2

interface Trial {
  task_id: string
  model_requested: string
  model_reported: string
  repeat: number
  passed: boolean
  output_sha256: string
  output_length: number
}

function sha256(text: string): string {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex')
}

function textOf(message: Anthropic.Message): string {
  const parts: string[] = []
  for (const block of message.content) {
    if (block.type === 'text') parts.push(block.text)
  }
  return parts.join('')
}

async function callWithRetry(
  client: Anthropic,
  model: string,
  task: CapabilityTask,
): Promise<Anthropic.Message> {
  let lastError: unknown = null
  for (let attempt = 0; attempt < TRANSPORT_RETRIES; attempt++) {
    try {
      return await client.messages.create({
        model,
        max_tokens: MAX_TOKENS,
        temperature: 0,
        system: SYSTEM_PROMPT,
        messages: [{ role: 'user', content: task.prompt }],
      })
    } catch (error) {
      lastError = error
      const backoffMs = 2000 * 2 ** attempt
      console.error(`  transport error (attempt ${attempt + 1}/${TRANSPORT_RETRIES}), retrying in ${backoffMs}ms`)
      await new Promise((resolve) => setTimeout(resolve, backoffMs))
    }
  }
  throw lastError
}

function tally(trials: readonly Trial[], model: string, taskId: string): number {
  return trials.filter((t) => t.model_requested === model && t.task_id === taskId && t.passed).length
}

function totalFor(trials: readonly Trial[], model: string): number {
  return trials.filter((t) => t.model_requested === model && t.passed).length
}

/** Preregistration §7. Applied to the first two models only; pairwise by construction. */
function verdict(trials: readonly Trial[], a: string, b: string): string {
  const totalA = totalFor(trials, a)
  const totalB = totalFor(trials, b)
  const [high, low] = totalA >= totalB ? [a, b] : [b, a]

  const trivial = TASKS.filter(
    (t) => tally(trials, a, t.id) === 0 && tally(trials, b, t.id) === 0,
  )
  if (trivial.length > 0) {
    return `INVALID — both models scored 0 on: ${trivial.map((t) => t.id).join(', ')}. Suspect harness or transport fault, not a finding.`
  }

  const margin = Math.abs(totalA - totalB)
  const decisiveTasks = TASKS.filter(
    (t) => tally(trials, high, t.id) - tally(trials, low, t.id) >= MARGIN_PER_TASK,
  )

  if (margin >= MARGIN_TOTAL && decisiveTasks.length >= TASKS_REQUIRED) {
    return `SEPARATED — ${high} over ${low} by ${margin}/30, decisive on ${decisiveTasks.length} tasks: ${decisiveTasks.map((t) => t.id).join(', ')}. NOTE: capability only. This does not license an authorship inference (PREREGISTRATION.md §2).`
  }
  return `UNRESOLVED — margin ${margin}/30 (needs ${MARGIN_TOTAL}), decisive on ${decisiveTasks.length} tasks (needs ${TASKS_REQUIRED}).`
}

async function main(): Promise<number> {
  const models = process.argv.slice(2)
  if (models.length < 2) {
    console.error('usage: run.ts <model-a> <model-b> [...]')
    return 1
  }

  const apiKey = process.env['ANTHROPIC_API_KEY']
  if (!apiKey) {
    console.error('ANTHROPIC_API_KEY is unset. The harness is complete but cannot run without a')
    console.error('credential. This is an absent binding, not absent code — see ADAPTER_MAP.md §3.')
    return 1
  }

  const tasksSha = sha256(fs.readFileSync(path.join(HERE, 'tasks.ts'), 'utf8'))
  console.log(`MCB-001 · tasks.ts sha256=${tasksSha}`)
  console.log(`models: ${models.join(', ')} · ${TASKS.length} tasks × ${REPEATS} repeats\n`)

  const client = new Anthropic({ apiKey })
  const trials: Trial[] = []
  const outputs = new Map<string, string>()

  for (const model of models) {
    for (const task of TASKS) {
      for (let repeat = 0; repeat < REPEATS; repeat++) {
        const message = await callWithRetry(client, model, task)
        const output = textOf(message)
        const digest = sha256(output)
        outputs.set(digest, output)
        const passed = gradeOutput(task, output)
        trials.push({
          task_id: task.id,
          model_requested: model,
          model_reported: message.model,
          repeat,
          passed,
          output_sha256: digest,
          output_length: output.length,
        })
        process.stdout.write(passed ? '.' : 'x')
      }
      console.log(`  ${model} · ${task.id}: ${tally(trials, model, task.id)}/${REPEATS}`)
    }
  }

  const mismatches = trials.filter((t) => !t.model_reported.startsWith(t.model_requested))
  if (mismatches.length > 0) {
    console.log(`\nRequested/reported model mismatch on ${mismatches.length} trials — recorded, not corrected.`)
  }

  const resultsDir = path.join(HERE, 'results')
  fs.mkdirSync(resultsDir, { recursive: true })
  const stamp = new Date().toISOString().replace(/[:.]/g, '-')

  const record = { protocol: 'MCB-001', tasks_sha256: tasksSha, repeats: REPEATS, models, trials }
  const canonical = canonicalizeJCSString(record)
  fs.writeFileSync(path.join(resultsDir, `${stamp}.json`), canonical)
  fs.writeFileSync(
    path.join(resultsDir, `${stamp}.outputs.json`),
    JSON.stringify(Object.fromEntries(outputs), null, 2),
  )

  console.log('\n' + '-'.repeat(72))
  for (const model of models) console.log(`${model}: ${totalFor(trials, model)}/${TASKS.length * REPEATS}`)
  console.log('-'.repeat(72))
  console.log(verdict(trials, models[0] as string, models[1] as string))
  console.log(`\nresult root: ${sha256(canonical)}`)
  return 0
}

main().then(
  (code) => process.exit(code),
  (error) => {
    console.error('harness fault:', error)
    process.exit(1)
  },
)
