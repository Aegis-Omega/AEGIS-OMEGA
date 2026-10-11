/**
 * AEGIS Ω / Sovereign Field — deterministic spatial lens over actual source registry.
 * Connections denote membership in the curated index, never theorem/proof dependencies.
 */
export type FieldSource = Readonly<{
  id: string; index: string; title: string; area: string; kind: string;
  status: string; description: string; question: string;
  boundaries: readonly string[]; href?: string; action: string;
}>
export type FieldPoint = Readonly<{
  id: string; index: string; x: number; y: number;
  scale: number; depth: number; active: boolean;
}>
export type FieldLink = Readonly<{ from: 'atlas'; to: string; meaning: 'indexed_source' }>

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

export function fieldProjection(
  sources: readonly FieldSource[], selectedId: string | null, yaw = 0,
): { points: FieldPoint[]; links: FieldLink[]; selection: FieldSource | null } {
  const safeYaw = Number.isFinite(yaw) ? clamp(yaw, -3.14, 3.14) : 0
  const selection = sources.find(s => s.id === selectedId) ?? sources[0] ?? null
  const count = sources.length
  const points = sources.map((source, i) => {
    // Intentionally deterministic: stable identity and order, never invented weights.
    const angle = Math.PI / 2 - i * 2 * Math.PI / Math.max(1, count)
    const radius = count === 1 ? 0 : 1.45
    const xx = Math.cos(angle) * radius
    const zz = Math.sin(angle * 2) * radius * .29
    const yy = Math.sin(angle) * 1.13
    const projectedX = xx * Math.cos(safeYaw) + zz * Math.sin(safeYaw)
    const projectedZ = zz * Math.cos(safeYaw) - xx * Math.sin(safeYaw)
    const perspective = 4.3 / (4.3 - projectedZ)
    return {
      id: source.id, index: source.index,
      x: clamp(50 + projectedX * perspective * 20.5, 13, 87),
      y: clamp(50 - yy * perspective * 29 - projectedZ * 2.2, 17, 83),
      depth: projectedZ,
      scale: clamp(perspective, .73, 1.44),
      active: selection?.id === source.id,
    }
  })
  return {
    selection,
    points: points.sort((a, b) => a.depth - b.depth),
    links: sources.map(source => ({ from: 'atlas' as const, to: source.id, meaning: 'indexed_source' as const })),
  }
}

export function sourceSnapshot(source: FieldSource): string {
  // Local text export: neither signed evidence nor verification of the source.
  return [
    'AEGIS Ω / CURATED SOURCE RECORD — UNSIGNED',
    `ID: ${source.id}`,
    `Title: ${source.title}`,
    `Kind: ${source.kind}`,
    `Reported scope: ${source.status}`,
    `Question: ${source.question}`,
    'Declared limits:',
    ...source.boundaries.map((item, index) => `${index + 1}. ${item}`),
    `Reference: ${source.href ?? 'NOT PUBLIC'}`,
    'NOT A VERIFIED RUN OR SCIENTIFIC CERTIFICATE',
  ].join('\n')
}
