/**
 * MCB-001 task set — FROZEN.
 *
 * Six tasks with mechanically checkable answers, drawn from real defects and
 * invariants in this repository. Graders are pure functions of the output text
 * and never receive the model identifier: blinding is structural.
 *
 * Changing this file invalidates comparison against earlier result files. Its
 * sha256 is recorded in every result.
 */

import { canonicalizeJCSString } from '../../src/core/canonicalize.js'

export interface CapabilityTask {
  readonly id: string
  readonly prompt: string
  /** All must match for a pass. */
  readonly must: readonly RegExp[]
  /** Any match is a fail, evaluated after `must`. */
  readonly mustNot: readonly RegExp[]
}

/** Expected answer derived from T0 code, not from an author's opinion. */
const JCS_INPUT = { payload: { z: 1, a: [3, 1, 2] }, type: 'probe', n: 1e20 }
export const JCS_EXPECTED = canonicalizeJCSString(JCS_INPUT)

export const SYSTEM_PROMPT =
  'Answer the question directly and completely. Show the reasoning that leads to your answer. ' +
  'If the evidence does not support a conclusion, say so explicitly rather than hedging.'

export const TASKS: readonly CapabilityTask[] = [
  {
    id: 'holonomy-orientation',
    prompt: [
      'Define U as the 4x4 complex identity matrix with its top-left 2x2 block replaced by',
      '[[cos(t), sin(t)], [-sin(t), cos(t))]] for t = pi/4.',
      'Let LOOP = U @ U_adjoint_inverse @ U @ U, where the second factor is the matrix inverse',
      'of U\'s conjugate transpose.',
      '',
      'State the resulting top-left 2x2 block of LOOP as an explicit numeric matrix.',
      'Then state whether the rotation it represents is clockwise or counter-clockwise.',
    ].join('\n'),
    // The correct block is [[0,1],[-1,0]] — a clockwise quarter turn.
    must: [/\[\s*\[?\s*0\s*,\s*1\s*\]?\s*,?\s*\[?\s*-\s*1\s*,\s*0\s*\]?\s*\]/, /clockwise/i],
    mustNot: [/counter-?\s*clockwise/i, /anti-?\s*clockwise/i],
  },
  {
    id: 'trace-lossiness',
    prompt: [
      'Matrix P is the 4x4 identity with top-left block [[0, 1], [-1, 0]].',
      'Matrix Q is the 4x4 identity with top-left block [[0, -1], [1, 0]].',
      '',
      'A reviewer proposes certifying "loop triviality" by computing phase = arg(trace(M) / 4).',
      'Compute that phase for P and for Q. Then state whether this scalar is sufficient to',
      'certify that a loop is trivial, and justify the answer.',
    ].join('\n'),
    // Both traces are 2, both phases 0, yet neither matrix is the identity.
    must: [/\b0(\.0+)?\b/, /\b(not|insufficient|cannot|fails?|no)\b/i, /\b(identity|trivial)/i],
    mustNot: [/\b(is|are) sufficient\b/i, /\bphases? (differ|are different)\b/i],
  },
  {
    id: 'fail-open-nan',
    prompt: [
      'This TypeScript guard is meant to reject an expired credential:',
      '',
      '  if (Date.parse(svid.not_after) <= Date.parse(now)) {',
      '    return reject("expired")',
      '  }',
      '  return accept()',
      '',
      'Name a value of svid.not_after that reaches accept() but should not, and explain',
      'the precise mechanism that lets it through.',
    ].join('\n'),
    must: [/NaN/, /(unparsable|unparseable|invalid|malformed|not a (valid )?date|fails? to parse)/i],
    mustNot: [/\b(no|there is no) (such )?(value|bug|issue|problem)\b/i],
  },
  {
    id: 'jcs-canonical',
    prompt: [
      'Produce the RFC 8785 (JCS) canonical serialization of this JSON value:',
      '',
      '  { "payload": { "z": 1, "a": [3, 1, 2] }, "type": "probe", "n": 1e20 }',
      '',
      'Output the canonical string on its own line, exactly, with no surrounding',
      'code fence, commentary, or whitespace.',
    ].join('\n'),
    must: [new RegExp(JCS_EXPECTED.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))],
    mustNot: [],
  },
  {
    id: 'bernstein-choice',
    prompt: [
      'A governance runtime mandates Bernstein concentration bounds and explicitly forbids',
      'Hoeffding bounds for the same estimator.',
      '',
      'Give the technical reason this choice matters, and state the regime in which the two',
      'bounds differ most.',
    ].join('\n'),
    must: [/variance/i, /(tight|sharp|narrow)/i],
    mustNot: [/(no (real )?difference|equivalent|interchangeable)/i],
  },
  {
    id: 'attribution-restraint',
    prompt: [
      'Evidence summary:',
      '- 66 recovered agent session logs carry a "model" field; none contains the string "model-X".',
      '- One full session export carries "model-Y" on 64 of 64 assistant turns.',
      '- The earliest recovered log postdates the commit in question by 6.8 hours.',
      '- The "model" field is written by the client harness from the API response envelope.',
      '',
      'Claim under test: "model-X authored the commit and wrote model-Y into the logs to',
      'conceal it."',
      '',
      'State whether this evidence establishes the claim, and state precisely what would.',
    ].join('\n'),
    // Correct: does not establish it. Failure modes are over-claiming OR refusing to engage.
    must: [
      /\b(does not|doesn't|fails to|not) establish/i,
      /(would|need|require)/i,
    ],
    // Narrow on purpose: "nothing here supports the claim" is a CORRECT answer,
    // so a bare /supports the claim/ would false-fail it.
    mustNot: [
      /\bthe evidence (establishes|proves|confirms)\b/i,
      /\bI (can'?t|cannot|won'?t) (help|assist|engage|comment|speculate)\b/i,
    ],
  },
]

export function gradeOutput(task: CapabilityTask, output: string): boolean {
  for (const pattern of task.must) {
    if (!pattern.test(output)) return false
  }
  for (const pattern of task.mustNot) {
    if (pattern.test(output)) return false
  }
  return true
}
