import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, copyFileSync, writeFileSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

const ROOT = resolve(import.meta.dirname, '..')
const HOOK = resolve(ROOT, '.claude/hooks/post-write.sh')
const CHAIN = resolve(ROOT, '.claude/metacog/chain.mjs')
function fixture({ chain = true } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'aegis-post-write-'))
  const meta = join(dir, '.claude/metacog')
  mkdirSync(meta, { recursive: true })
  if (chain) copyFileSync(CHAIN, join(meta, 'chain.mjs'))
  return { dir, meta, chainFile: join(meta, 'chain.jsonl'), lock: join(meta, 'chain.jsonl.lock') }
}
function trigger(f, body = { tool_input: { file_path: 'docs/created.md' } }) {
  return spawnSync('bash', [HOOK], {
    cwd: f.dir, encoding: 'utf8', input: JSON.stringify(body),
    env: { ...process.env, CLAUDE_PROJECT_DIR: f.dir, AEGIS_METACOG_CHAIN: f.chainFile },
  })
}
function entries(f) { return readFileSync(f.chainFile, 'utf8').trim().split('\n').map(JSON.parse) }

test('post-write success creates real AUTOPOIETIC_PRODUCTION entry', () => {
  const f = fixture()
  const r = trigger(f)
  assert.equal(r.status, 0, r.stderr)
  const e = entries(f)
  assert.equal(e.length, 1)
  assert.equal(e[0].observation.layer, 'AUTOPOIETIC_PRODUCTION')
  assert.equal(e[0].observation.tier, 'T2')
})

test('post-write absent chain engine fails closed instead of silent success', () => {
  const f = fixture({ chain: false })
  const r = trigger(f)
  assert.equal(r.status, 2)
  assert.match(r.stderr, /AEGIS_POST_WRITE_HOLD/)
})

test('post-write existing lock fails closed and never deletes other writer lock', () => {
  const f = fixture()
  writeFileSync(f.lock, 'other-owner')
  const r = trigger(f)
  assert.equal(r.status, 2)
  assert.match(r.stderr, /HOLD/)
  assert.equal(readFileSync(f.lock, 'utf8'), 'other-owner')
})

test('post-write corrupted history fails closed without appending', () => {
  const f = fixture()
  let r = trigger(f)
  assert.equal(r.status, 0, r.stderr)
  const before = entries(f)
  before[0].observation.signal = 'tampered without rehash'
  writeFileSync(f.chainFile, JSON.stringify(before[0])+'\n')
  r = trigger(f)
  assert.equal(r.status, 2)
  assert.deepEqual(entries(f), before)
})

test('post-write missing tool path is a no-op', () => {
  const f = fixture({ chain: false })
  const r = trigger(f, { tool_input: {} })
  assert.equal(r.status, 0, r.stderr)
})

test('post-write 2 sequential writes maintain monotonic chain and cert', () => {
  const f = fixture()
  assert.equal(trigger(f).status, 0)
  assert.equal(trigger(f, { tool_input: { file_path: 'a.ts' } }).status, 0)
  const e=entries(f)
  assert.equal(e.length, 2)
  assert.equal(e[0].sequence, 0)
  assert.equal(e[1].sequence, 1)
  assert.equal(e[1].previous_entry_hash, e[0].entry_hash)
  const check = spawnSync('node', [join(f.meta,'chain.mjs'),'certify'], { encoding:'utf8', env: { ...process.env, CLAUDE_PROJECT_DIR:f.dir, AEGIS_METACOG_CHAIN:f.chainFile } })
  assert.equal(check.status, 0)
  assert.equal(JSON.parse(check.stdout).is_valid, true)
})
