import { describe, it, expect } from 'vitest'
import {
  processRepoFiles,
  buildHGTRecord,
  filterSkillFiles,
  HGT_SCHEMA_VERSION,
  type HGTSkillFile,
} from '../../src/skill-harness/hgt/hgt-scanner.js'

const SEQ = 1n as import('../../src/core/types.js').SequenceNumber

const MOCK_SKILL_MD = (name: string, desc: string) => `---
name: ${name}
description: ${desc}
---
## Overview
${desc}
`

const MOCK_FILES: readonly HGTSkillFile[] = [
  {
    repo_id: 'test-owner/test-repo',
    path: 'skills/git/SKILL.md',
    raw_content: MOCK_SKILL_MD('Git Version Control', 'Manage git branches, commits, and merges'),
  },
  {
    repo_id: 'test-owner/test-repo',
    path: 'skills/testing/SKILL.md',
    raw_content: MOCK_SKILL_MD('Test Automation', 'Write and run automated test suites with coverage'),
  },
  {
    repo_id: 'test-owner/test-repo',
    path: 'skills/design/SKILL.md',
    raw_content: MOCK_SKILL_MD('UI Design System', 'Design and implement consistent UI/UX style layouts'),
  },
]

describe('HGT Scanner — schema and constants', () => {
  it('HGT_SCHEMA_VERSION is 1.0.0', () => {
    expect(HGT_SCHEMA_VERSION).toBe('1.0.0')
  })
})

describe('HGT Scanner — filterSkillFiles', () => {
  it('extracts only SKILL.md blob entries', () => {
    const tree = [
      { path: 'skills/git/SKILL.md', type: 'blob' },
      { path: 'skills/git/README.md', type: 'blob' },
      { path: 'src/index.ts', type: 'blob' },
      { path: 'skills', type: 'tree' },
      { path: 'skills/testing/SKILL.md', type: 'blob' },
    ]
    const paths = filterSkillFiles(tree)
    expect(paths).toHaveLength(2)
    expect(paths).toContain('skills/git/SKILL.md')
    expect(paths).toContain('skills/testing/SKILL.md')
  })

  it('returns frozen array', () => {
    const paths = filterSkillFiles([{ path: 'skills/x/SKILL.md', type: 'blob' }])
    expect(Object.isFrozen(paths)).toBe(true)
  })

  it('returns empty array when no SKILL.md files', () => {
    const paths = filterSkillFiles([{ path: 'README.md', type: 'blob' }])
    expect(paths).toHaveLength(0)
  })

  it('case-insensitive match on SKILL.md', () => {
    const paths = filterSkillFiles([
      { path: 'skills/skill.md', type: 'blob' },
      { path: 'skills/SKILL.MD', type: 'blob' },
    ])
    expect(paths).toHaveLength(2)
  })
})

describe('HGT Scanner — processRepoFiles', () => {
  it('processes 3 valid SKILL.md files → 3 admitted', async () => {
    const result = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    expect(result.repo_id).toBe('test-owner/test-repo')
    expect(result.files_found).toBe(3)
    expect(result.admitted.length).toBe(3)
    expect(result.rejected.length).toBe(0)
  })

  it('result is frozen', async () => {
    const result = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    expect(Object.isFrozen(result)).toBe(true)
  })

  it('source_hash is 64-char hex', async () => {
    const result = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    expect(result.source_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is_replay_reconstructable is true', async () => {
    const result = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('source_hash is deterministic ×3', async () => {
    const [r1, r2, r3] = await Promise.all([
      processRepoFiles('test-owner/test-repo', MOCK_FILES),
      processRepoFiles('test-owner/test-repo', MOCK_FILES),
      processRepoFiles('test-owner/test-repo', MOCK_FILES),
    ])
    expect(r1.source_hash).toBe(r2.source_hash)
    expect(r2.source_hash).toBe(r3.source_hash)
  })

  it('different repo_id → different source_hash', async () => {
    const [r1, r2] = await Promise.all([
      processRepoFiles('owner-a/repo-a', MOCK_FILES),
      processRepoFiles('owner-b/repo-b', MOCK_FILES),
    ])
    expect(r1.source_hash).not.toBe(r2.source_hash)
  })

  it('empty files array → files_found=0, no admitted', async () => {
    const result = await processRepoFiles('test-owner/empty-repo', [])
    expect(result.files_found).toBe(0)
    expect(result.admitted.length).toBe(0)
    expect(result.rejected.length).toBe(0)
    expect(result.source_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('file with missing frontmatter → rejected', async () => {
    const badFile: HGTSkillFile = {
      repo_id: 'test/repo',
      path: 'SKILL.md',
      raw_content: '# No frontmatter here',
    }
    const result = await processRepoFiles('test/repo', [badFile])
    expect(result.admitted.length).toBe(0)
    expect(result.rejected.length).toBe(1)
    expect(result.rejected[0]?.reason).toMatch(/OBSERVATION/)
  })

  it('T4/T5 content → rejected by arbitration', async () => {
    const t5File: HGTSkillFile = {
      repo_id: 'test/repo',
      path: 'AGI/SKILL.md',
      raw_content: MOCK_SKILL_MD('Superintelligent AGI', 'Self-aware omniscient system that achieves AGI'),
    }
    const result = await processRepoFiles('test/repo', [t5File])
    expect(result.admitted.length).toBe(0)
    expect(result.rejected.length).toBe(1)
    expect(result.rejected[0]?.reason).toMatch(/ARBITRATION/)
  })

  it('admitted SkillRecords have skill_hash 64-char hex', async () => {
    const result = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    for (const skill of result.admitted) {
      expect(skill.skill_hash).toMatch(/^[0-9a-f]{64}$/)
    }
  })

  it('domain_affinity correctly assigned from content', async () => {
    const result = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    const gitSkill = result.admitted.find(s => s.skill_id.includes('git'))
    expect(gitSkill?.domain_affinity).toContain('version-control')
  })
})

describe('HGT Scanner — buildHGTRecord', () => {
  it('builds valid HGTRecord from scan results', async () => {
    const repoResult = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    const record = await buildHGTRecord([repoResult], SEQ)
    expect(record.sources_scanned).toContain('test-owner/test-repo')
    expect(record.total_files_found).toBe(3)
    expect(record.total_admitted).toBe(3)
    expect(record.total_rejected).toBe(0)
    expect(record.schema_version).toBe('1.0.0')
    expect(record.is_replay_reconstructable).toBe(true)
  })

  it('hgt_hash is 64-char hex', async () => {
    const repoResult = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    const record = await buildHGTRecord([repoResult], SEQ)
    expect(record.hgt_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('catalog_hash is 64-char hex', async () => {
    const repoResult = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    const record = await buildHGTRecord([repoResult], SEQ)
    expect(record.catalog_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('record is frozen', async () => {
    const repoResult = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    const record = await buildHGTRecord([repoResult], SEQ)
    expect(Object.isFrozen(record)).toBe(true)
  })

  it('hgt_hash deterministic ×3', async () => {
    const repoResult = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    const [r1, r2, r3] = await Promise.all([
      buildHGTRecord([repoResult], SEQ),
      buildHGTRecord([repoResult], SEQ),
      buildHGTRecord([repoResult], SEQ),
    ])
    expect(r1.hgt_hash).toBe(r2.hgt_hash)
    expect(r2.hgt_hash).toBe(r3.hgt_hash)
  })

  it('different sequence → different hgt_hash', async () => {
    const repoResult = await processRepoFiles('test-owner/test-repo', MOCK_FILES)
    const seq2 = 2n as import('../../src/core/types.js').SequenceNumber
    const [r1, r2] = await Promise.all([
      buildHGTRecord([repoResult], SEQ),
      buildHGTRecord([repoResult], seq2),
    ])
    expect(r1.hgt_hash).not.toBe(r2.hgt_hash)
  })

  it('aggregates across multiple repos', async () => {
    const repoA = await processRepoFiles('org/repo-a', MOCK_FILES.slice(0, 1))
    const repoB = await processRepoFiles('org/repo-b', MOCK_FILES.slice(1, 3))
    const record = await buildHGTRecord([repoA, repoB], SEQ)
    expect(record.sources_scanned).toHaveLength(2)
    expect(record.total_files_found).toBe(3)
    expect(record.total_admitted).toBe(3)
  })

  it('empty results → zeros with valid hashes', async () => {
    const record = await buildHGTRecord([], SEQ)
    expect(record.total_files_found).toBe(0)
    expect(record.total_admitted).toBe(0)
    expect(record.hgt_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.catalog_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('sequence is preserved', async () => {
    const seq42 = 42n as import('../../src/core/types.js').SequenceNumber
    const record = await buildHGTRecord([], seq42)
    expect(record.sequence).toBe(seq42)
  })
})
