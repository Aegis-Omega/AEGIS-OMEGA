// CorpusEngine — 5-phase RALPH pipeline · T2 · fibonacci_depths [1,1,2,3,5]

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import { fibonacciInterval } from '../agents/scheduler/fibonacci.js'
import type {
  CorpusDocument, RalphPhaseRecord, CorpusLineageRecord, RalphPhase, DocumentTier,
} from './types.js'
import { visitSections, sectionText } from './section-visitor.js'

const PHASES: readonly RalphPhase[] = [
  'OBSERVATION', 'INTERPRETATION', 'ARBITRATION', 'MUTATION', 'PROPAGATION',
]

// Keywords that suggest T4/T5 speculative content → ARBITRATION blocks
const T4_T5_SIGNALS = [
  /sovereign consciousness/i, /civilizational/i, /planetary coordination/i,
  /omnipotent/i, /omniscient/i, /transcendent superintelligence/i,
  /self-modifying beyond/i, /unrestricted agi/i,
]

// Domain signal keywords → domain tag
const DOMAIN_SIGNALS: Array<[RegExp, string]> = [
  [/governance|constitutional|replay|invariant/i, 'governance'],
  [/research|analysis|synthesis/i, 'research'],
  [/deploy|ci|pipeline|build/i, 'deployment'],
  [/design|ux|ui/i, 'design'],
  [/security|audit|threat/i, 'security'],
  [/telemetry|monitor|observ/i, 'monitoring'],
  [/agent|swarm|orchestrat/i, 'orchestration'],
  [/test|verify|assert/i, 'quality'],
]

function extractDomainSignals(content: string): readonly string[] {
  const found: string[] = []
  for (const section of visitSections(content)) {
    const text = sectionText(section)
    for (const [pattern, domain] of DOMAIN_SIGNALS) {
      if (pattern.test(text) && !found.includes(domain)) found.push(domain)
    }
  }
  return found.length > 0 ? found : ['general']
}

function classifyTier(content: string): { tier: DocumentTier | 'DOWNGRADED'; reason?: string } {
  for (const pattern of T4_T5_SIGNALS) {
    if (pattern.test(content)) {
      return { tier: 'DOWNGRADED', reason: `T4/T5 signal detected: ${String(pattern)}` }
    }
  }
  if (/mechanically proven|formally verified|sha256|hash chain/i.test(content)) return { tier: 'T0' }
  if (/empirically validated|benchmark|measurement/i.test(content)) return { tier: 'T1' }
  if (/engineering hypothesis|proposed|stub|seam/i.test(content)) return { tier: 'T2' }
  return { tier: 'T3' }
}

function assignPrimitive(domains: readonly string[]): string {
  if (domains.includes('governance') || domains.includes('security')) return 'VERIFY'
  if (domains.includes('quality')) return 'FREEZE'
  if (domains.includes('orchestration') || domains.includes('deployment')) return 'SEQUENCE'
  if (domains.includes('monitoring')) return 'HASH'
  return 'CANONICALIZE'
}

export async function processDocument(
  doc: CorpusDocument,
  rawContent: string,
): Promise<CorpusLineageRecord> {
  const phaseRecords: RalphPhaseRecord[] = []
  let prevOutputHash = doc.content_hash
  let admitted = true
  let downgradeReason: string | undefined

  for (let i = 0; i < PHASES.length; i++) {
    const phase = PHASES[i]!
    const phaseIndex = i + 1
    const fibonacci_depth = fibonacciInterval(phaseIndex)
    const phase_input_hash = prevOutputHash

    let outputPayload: unknown
    if (phase === 'OBSERVATION') {
      outputPayload = { document_id: doc.document_id, byte_length: doc.byte_length, content_hash: doc.content_hash }
    } else if (phase === 'INTERPRETATION') {
      outputPayload = { domain_signals: extractDomainSignals(rawContent) }
    } else if (phase === 'ARBITRATION') {
      const classification = classifyTier(rawContent)
      admitted = classification.tier !== 'DOWNGRADED'
      downgradeReason = classification.reason
      outputPayload = { tier: classification.tier, admitted }
    } else if (phase === 'MUTATION') {
      const domains = extractDomainSignals(rawContent)
      outputPayload = { primitive_mapping: assignPrimitive(domains), domains }
    } else {
      // PROPAGATION — only admitted docs emit canonical abstractions
      outputPayload = { admitted, document_id: doc.document_id }
    }

    const phase_output_hash = await hashValue(outputPayload)
    const phase_hash = await hashValue({
      document_id: doc.document_id, phase, phase_input_hash, phase_output_hash,
    })

    phaseRecords.push(deepFreeze<RalphPhaseRecord>({
      document_id: doc.document_id,
      phase,
      fibonacci_depth,
      phase_input_hash,
      phase_output_hash,
      phase_hash,
      admitted,
      ...(downgradeReason !== undefined && !admitted ? { downgrade_reason: downgradeReason } : {}),
      is_replay_reconstructable: true,
    }))

    prevOutputHash = phase_output_hash
  }

  const corpus_lineage_hash = await hashValue(
    phaseRecords.map(r => r.phase_hash)
  ) as SHA256Hex

  const { tier: final_tier } = classifyTier(rawContent)

  return deepFreeze<CorpusLineageRecord>({
    document_id: doc.document_id,
    phases: Object.freeze(phaseRecords),
    corpus_lineage_hash,
    final_tier,
    is_replay_reconstructable: true,
  })
}

export async function buildCorpusDocument(
  document_id: string,
  source: string,
  rawContent: string,
): Promise<CorpusDocument> {
  const content_hash = await hashValue({ content: rawContent }) as SHA256Hex
  return deepFreeze<CorpusDocument>({
    document_id,
    source,
    content_hash,
    byte_length: new TextEncoder().encode(rawContent).length,
    schema_version: '1.0.0' as const,
    is_replay_reconstructable: true,
  })
}
