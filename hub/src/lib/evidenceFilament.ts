/**
 * Evidence Filament data model. Every edge describes a relationship present
 * in the ResearchOS source register, NOT a proven dependency or live result.
 */
export type FilamentSource = Readonly<{
  id: string
  index: string
  title: string
  kind: string
  status: string
  question: string
  boundaries: readonly string[]
}>

export type FilamentLink = Readonly<{
  from: string
  to: string
  relationship: 'recorded_open_question' | 'declared_boundary'
  label: string
}>

export function selectEvidenceFilament(
  sources: readonly FilamentSource[],
  selectedId: string | null,
): { source: FilamentSource; links: FilamentLink[] } | null {
  const source = sources.find(item => item.id === selectedId) ?? sources[0]
  if (!source) return null
  return {
    source,
    links: [
      {
        from: 'source:' + source.id,
        to: 'question:' + source.id,
        relationship: 'recorded_open_question',
        label: source.question,
      },
      ...source.boundaries.map((label, index) => ({
        from: 'question:' + source.id,
        to: 'boundary:' + source.id + ':' + index,
        relationship: 'declared_boundary' as const,
        label,
      })),
    ],
  }
}
