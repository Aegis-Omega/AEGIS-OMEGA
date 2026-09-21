import { useEffect, useState } from 'react'

const BRIDGE = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'

export interface OperationsSourceFinding {
  id: string
  priority: 'P0' | 'P1' | 'P2'
  component: string
  path_count: number
  individually_catalogued_paths: number
  uncatalogued_paths: number
  authority_effect: 'NONE'
}

export interface OperationsSourceCard {
  id: 'catalogued_sources' | 'archive_project_files' | 'coverage_groups' | 'unsurfaced_no_counterpart'
  label: string
  value: number
  status: string
  note: string
}

export interface OperationsSourcesPayload {
  schema: 'AEGIS_OPERATIONS_CENTER_SOURCES_V1'
  source: {
    archive_coverage_path: string
    archive_coverage_root: string
    evidence_package_sha256: string
    observed_main_head: string
    observed_at_utc: string
  }
  cards: OperationsSourceCard[]
  findings: readonly OperationsSourceFinding[]
  unsurfaced_paths: readonly string[]
  warnings: readonly string[]
  consumer_contract: {
    preferred_path: string
    legacy_label_to_replace: string
    primary_card_id: string
    invalid_source_behavior: string
  }
  authority_effect: 'NONE'
  projection_root: string
}

export type OperationsSourcesState =
  | { state: 'LOADING'; payload: null; error: null }
  | { state: 'READY'; payload: OperationsSourcesPayload; error: null }
  | { state: 'INVALID_OR_STALE'; payload: null; error: string }
  | { state: 'OFFLINE'; payload: null; error: string }

function validatePayload(value: unknown): OperationsSourcesPayload {
  if (typeof value !== 'object' || value === null) throw new Error('SOURCE_PAYLOAD_NOT_OBJECT')
  const payload = value as Partial<OperationsSourcesPayload>
  if (payload.schema !== 'AEGIS_OPERATIONS_CENTER_SOURCES_V1') throw new Error('SOURCE_SCHEMA_MISMATCH')
  if (payload.authority_effect !== 'NONE') throw new Error('SOURCE_AUTHORITY_ESCALATION')
  if (!Array.isArray(payload.cards) || payload.cards.length !== 4) throw new Error('SOURCE_CARDS_INVALID')
  const ids = payload.cards.map(card => card.id)
  const expected = ['catalogued_sources', 'archive_project_files', 'coverage_groups', 'unsurfaced_no_counterpart']
  if (ids.join('|') !== expected.join('|')) throw new Error('SOURCE_CARD_SET_MISMATCH')
  if (payload.cards[0]?.status !== 'INCOMPLETE_SELECTED_SAMPLE') {
    throw new Error('SOURCE_CATALOGUE_COMPLETENESS_INVALID')
  }
  if (!Array.isArray(payload.findings) || !Array.isArray(payload.unsurfaced_paths)) {
    throw new Error('SOURCE_DETAILS_INVALID')
  }
  for (const finding of payload.findings) {
    if (
      typeof finding !== 'object' ||
      finding === null ||
      typeof finding.id !== 'string' ||
      !['P0', 'P1', 'P2'].includes(finding.priority) ||
      typeof finding.component !== 'string' ||
      typeof finding.path_count !== 'number' ||
      typeof finding.individually_catalogued_paths !== 'number' ||
      typeof finding.uncatalogued_paths !== 'number' ||
      finding.authority_effect !== 'NONE'
    ) {
      throw new Error('SOURCE_FINDING_INVALID')
    }
  }
  if (payload.cards[2]?.value !== payload.findings.length) throw new Error('SOURCE_FINDING_COUNT_MISMATCH')
  if (payload.cards[3]?.value !== payload.unsurfaced_paths.length) throw new Error('SOURCE_PATH_COUNT_MISMATCH')
  if (payload.consumer_contract?.legacy_label_to_replace !== '38 arhiva + Git') {
    throw new Error('SOURCE_LEGACY_LABEL_CONTRACT_MISMATCH')
  }
  if (payload.consumer_contract?.primary_card_id !== 'catalogued_sources') {
    throw new Error('SOURCE_PRIMARY_CARD_CONTRACT_MISMATCH')
  }
  if (
    payload.consumer_contract?.invalid_source_behavior !==
    'SHOW_INVALID_OR_STALE; DO_NOT_FALL_BACK_TO_COMPLETE_INVENTORY_CLAIM'
  ) {
    throw new Error('SOURCE_FAIL_CLOSED_CONTRACT_MISMATCH')
  }
  if (
    typeof payload.projection_root !== 'string' ||
    !/^[0-9a-f]{64}$/.test(payload.projection_root)
  ) {
    throw new Error('SOURCE_PROJECTION_ROOT_INVALID')
  }
  return payload as OperationsSourcesPayload
}

export function useOperationsSources(): OperationsSourcesState {
  const [snapshot, setSnapshot] = useState<OperationsSourcesState>({
    state: 'LOADING',
    payload: null,
    error: null,
  })

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const response = await fetch(`${BRIDGE}/platform/operations/sources`, {
          method: 'GET',
          cache: 'no-store',
          signal: controller.signal,
        })
        const body = await response.json().catch(() => null)
        if (!response.ok) {
          const errorCode =
            typeof body === 'object' && body !== null && 'error_code' in body
              ? String((body as { error_code?: unknown }).error_code)
              : `HTTP_${response.status}`
          setSnapshot({ state: 'INVALID_OR_STALE', payload: null, error: errorCode })
          return
        }
        const payload = validatePayload(body)
        setSnapshot({ state: 'READY', payload, error: null })
      } catch (error) {
        if (controller.signal.aborted) return
        const message = error instanceof Error ? error.message : String(error)
        const semanticFailure = message.startsWith('SOURCE_')
        setSnapshot({
          state: semanticFailure ? 'INVALID_OR_STALE' : 'OFFLINE',
          payload: null,
          error: message,
        })
      }
    }

    void load()
    return () => controller.abort()
  }, [])

  return snapshot
}
