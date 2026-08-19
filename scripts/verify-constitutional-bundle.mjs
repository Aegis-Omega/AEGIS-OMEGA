import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

const witnessPath = '.aegis/evidence/constitutional-bundle-v1-local-witness.json'
const witness = JSON.parse(readFileSync(witnessPath, 'utf8'))
const required = [
  'spec.md',
  'plan.md',
  'state.md',
  'src/core/constitutional_invariants.mjs',
  'tests/unit/constitutional_invariants.test.mjs',
]

for (const path of required) {
  const bytes = readFileSync(path)
  const actual = createHash('sha256').update(bytes).digest('hex')
  const expected = witness.files[path]?.sha256
  if (actual !== expected) {
    console.error(JSON.stringify({ status: 'FAIL', code: 'WITNESS_HASH_MISMATCH', path, expected, actual }))
    process.exit(1)
  }
}

const spec = readFileSync('spec.md', 'utf8')
const implementation = readFileSync('src/core/constitutional_invariants.mjs', 'utf8')
for (const marker of ['Ω1', 'Ω2', 'Ω3', 'OBSERVATION_ONLY', 'observationTier', 'authorityWeight', 'mayGroundStateTransition']) {
  if (!spec.includes(marker) && !implementation.includes(marker)) {
    console.error(JSON.stringify({ status: 'FAIL', code: 'CONSTITUTIONAL_MARKER_MISSING', marker }))
    process.exit(1)
  }
}

const run = spawnSync(process.execPath, ['--test', 'tests/unit/constitutional_invariants.test.mjs'], { encoding: 'utf8' })
process.stdout.write(run.stdout)
process.stderr.write(run.stderr)
if (run.status !== 0 || !run.stdout.includes('# pass 35') || !run.stdout.includes('# fail 0')) {
  console.error(JSON.stringify({ status: 'FAIL', code: 'FALSIFICATION_WITNESS_FAILED', exitCode: run.status }))
  process.exit(1)
}
console.log(JSON.stringify({ status: 'PASS', witness: witnessPath, tests: 35, fail: 0 }))
