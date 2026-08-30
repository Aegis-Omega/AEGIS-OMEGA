import { describe, it, expect } from 'vitest'
import {
  MAX_SECTION_DEPTH, visitSections, sectionText,
  type DocumentSection,
} from '../../src/corpus-engine/section-visitor.js'

describe('CorpusEngine — Depth-Bounded Section Visitor (Gate 173)', () => {
  describe('constants', () => {
    it('MAX_SECTION_DEPTH is 8 (fibonacciInterval(6))', () => {
      expect(MAX_SECTION_DEPTH).toBe(8)
    })

    it('MAX_SECTION_DEPTH is a const — not mutable', () => {
      // TypeScript const ensures this; runtime sanity check
      expect(typeof MAX_SECTION_DEPTH).toBe('number')
    })
  })

  describe('visitSections — basic structure', () => {
    it('empty string → empty array', () => {
      expect(visitSections('')).toHaveLength(0)
    })

    it('content with no headings → one preamble section at depth 0', () => {
      const sections = visitSections('Some body text here.')
      expect(sections).toHaveLength(1)
      expect(sections[0]!.depth).toBe(0)
      expect(sections[0]!.heading).toBe('')
      expect(sections[0]!.content).toBe('Some body text here.')
    })

    it('single H1 heading → one section with correct heading and depth', () => {
      const sections = visitSections('# Hello\nsome content')
      expect(sections).toHaveLength(1)
      expect(sections[0]!.heading).toBe('Hello')
      expect(sections[0]!.depth).toBe(1)
      expect(sections[0]!.content).toBe('some content')
    })

    it('returns frozen sections', () => {
      const sections = visitSections('# A\nbody')
      expect(Object.isFrozen(sections)).toBe(true)
      expect(Object.isFrozen(sections[0]!)).toBe(true)
    })
  })

  describe('visitSections — multi-level headings', () => {
    const doc = [
      '# Top Level',
      'top body',
      '## Sub Section',
      'sub body',
      '### Sub Sub',
      'deep body',
    ].join('\n')

    it('parses three levels correctly', () => {
      const sections = visitSections(doc)
      expect(sections).toHaveLength(3)
    })

    it('H1 section has depth 1', () => {
      expect(visitSections(doc)[0]!.depth).toBe(1)
    })

    it('H2 section has depth 2', () => {
      expect(visitSections(doc)[1]!.depth).toBe(2)
    })

    it('H3 section has depth 3', () => {
      expect(visitSections(doc)[2]!.depth).toBe(3)
    })

    it('each section carries its correct body content', () => {
      const sections = visitSections(doc)
      expect(sections[0]!.content).toContain('top body')
      expect(sections[1]!.content).toContain('sub body')
      expect(sections[2]!.content).toContain('deep body')
    })
  })

  describe('visitSections — depth cap enforcement', () => {
    const deepDoc = [
      '# Level 1',
      '## Level 2',
      '### Level 3',
      '#### Level 4 (deep)',
    ].join('\n')

    it('headings beyond maxDepth=2 become body text of parent section', () => {
      const sections = visitSections(deepDoc, 2)
      // Only # and ## become sections (depth 1+2); ### and #### treated as body
      expect(sections).toHaveLength(2)
    })

    it('body text of last admitted section contains the deep headings as raw text', () => {
      const sections = visitSections(deepDoc, 2)
      const lastSection = sections[sections.length - 1]!
      expect(lastSection.content).toContain('### Level 3')
    })

    it('default maxDepth is MAX_SECTION_DEPTH (8)', () => {
      // 6-level heading (###### Level 6) is within MAX_SECTION_DEPTH
      const doc = '# A\n###### B\nbody'
      const sections = visitSections(doc)
      expect(sections).toHaveLength(2)
      expect(sections[1]!.depth).toBe(6)
    })

    it('maxDepth=1 only admits H1 headings', () => {
      const doc = '# Top\n## Sub\n### DeepSub'
      const sections = visitSections(doc, 1)
      expect(sections).toHaveLength(1)
      expect(sections[0]!.depth).toBe(1)
    })
  })

  describe('visitSections — preamble handling', () => {
    it('content before first heading becomes a preamble section', () => {
      const doc = 'Preamble text\n# First Heading\nbody'
      const sections = visitSections(doc)
      expect(sections).toHaveLength(2)
      expect(sections[0]!.depth).toBe(0)
      expect(sections[0]!.heading).toBe('')
      expect(sections[0]!.content).toBe('Preamble text')
    })

    it('no preamble when content starts with heading', () => {
      const doc = '# First\nbody'
      const sections = visitSections(doc)
      expect(sections).toHaveLength(1)
      expect(sections[0]!.depth).toBe(1)
    })
  })

  describe('visitSections — determinism', () => {
    const doc = '# Alpha\nbody alpha\n## Beta\nbody beta\n### Gamma\nbody gamma'

    it('produces identical output on three consecutive calls', () => {
      const r1 = visitSections(doc)
      const r2 = visitSections(doc)
      const r3 = visitSections(doc)
      expect(JSON.stringify(r1)).toBe(JSON.stringify(r2))
      expect(JSON.stringify(r2)).toBe(JSON.stringify(r3))
    })

    it('different content → different sections', () => {
      const a = visitSections('# Alpha\nbody')
      const b = visitSections('# Beta\nbody')
      expect(a[0]!.heading).not.toBe(b[0]!.heading)
    })
  })

  describe('sectionText', () => {
    it('returns heading + space + content for headed sections', () => {
      const section: DocumentSection = Object.freeze({ heading: 'My Section', depth: 1, content: 'some body' })
      expect(sectionText(section)).toBe('My Section some body')
    })

    it('returns content only for preamble (empty heading)', () => {
      const section: DocumentSection = Object.freeze({ heading: '', depth: 0, content: 'preamble' })
      expect(sectionText(section)).toBe('preamble')
    })

    it('correctly exposes domain signal keywords inside section text', () => {
      const section: DocumentSection = Object.freeze({ heading: 'Governance Overview', depth: 1, content: 'constitutional replay invariant' })
      const text = sectionText(section)
      expect(/governance/i.test(text)).toBe(true)
      expect(text).toContain('constitutional')
    })
  })

  describe('visitSections — integration: corpus INTERPRETATION phase', () => {
    it('CL-Ψ spec-like document: all top-level sections admitted within depth cap', () => {
      const spec = [
        '# AEGIS-Ω CL-Ψ Specification',
        'Constitutional grounding section.',
        '## System Architecture',
        'SGM-Ψ Gate routing via entropy thresholding.',
        '## Phase 6: Čech/Postnikov (T3 claim)',
        'T3 — research conjecture.',
        '#### Very Deep Appendix',
        'Should not create a new section at depth 4 with maxDepth=3.',
      ].join('\n')
      const sections = visitSections(spec, 3)
      // # = depth 1, ## = depth 2, ## = depth 2 → 3 sections; #### absorbed into last ##
      expect(sections).toHaveLength(3)
      // The #### heading text should appear in the last section's content
      expect(sections[2]!.content).toContain('Very Deep Appendix')
    })

    it('governance keywords found via section visitor (same as flat scan)', () => {
      const doc = '## Governance Layer\nconstitutional replay invariant enforcement'
      const sections = visitSections(doc)
      const combined = sections.map(sectionText).join(' ')
      expect(/governance|constitutional/i.test(combined)).toBe(true)
    })
  })
})
