// ============================================================
// CorpusEngine — Depth-Bounded Section Visitor
// EPISTEMIC TIER: T2 · Gate 173
// MAX_SECTION_DEPTH prevents unbounded recursion in document
// processing (T0 invariant: no unrestricted recursion).
// ============================================================

// fibonacciInterval(6) = 8 — bounded section depth cap
export const MAX_SECTION_DEPTH = 8 as const

export interface DocumentSection {
  readonly heading: string  // heading text (empty string for preamble)
  readonly depth: number    // 1=# 2=## ... up to maxDepth; 0=preamble
  readonly content: string  // body text under this heading
}

// Parse markdown content into sections bounded by maxDepth.
// Headings deeper than maxDepth are treated as body text of the
// current section, not new sections. Returns a flat array — no recursion.
export function visitSections(
  content: string,
  maxDepth: number = MAX_SECTION_DEPTH,
): readonly DocumentSection[] {
  const sections: DocumentSection[] = []
  const lines = content.split('\n')
  let heading = ''
  let depth = 0
  let body: string[] = []

  const flush = (): void => {
    const content = body.join('\n').trim()
    if (heading !== '' || content !== '') {
      sections.push(Object.freeze<DocumentSection>({ heading, depth, content }))
    }
  }

  for (const line of lines) {
    const m = /^(#{1,6})\s+(.+)$/.exec(line)
    if (m !== null && m[1]!.length <= maxDepth) {
      flush()
      heading = m[2]!
      depth = m[1]!.length
      body = []
    } else {
      body.push(line)
    }
  }
  flush()

  return Object.freeze(sections)
}

// Extract combined text for a section (heading + content) for signal matching.
export function sectionText(section: DocumentSection): string {
  return section.heading !== '' ? `${section.heading} ${section.content}` : section.content
}
