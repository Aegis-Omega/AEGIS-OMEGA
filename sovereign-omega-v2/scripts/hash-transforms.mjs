#!/usr/bin/env node
// ============================================================
// SOVEREIGN OMEGA — Hash Transform Manifest Generator
// ChatGPT synthesis v2.1-Ω (Ω.D.1 Manifest Closure)
// Hashes all migration transform files and writes transform-manifest.json.
// Run at build time. Referenced by RuntimeExecutionPin.
// ============================================================

import { createHash } from 'crypto'
import { writeFileSync, readFileSync, readdirSync, statSync, realpathSync, existsSync } from 'fs'
import { join, extname, sep } from 'path'

const migrationsDir = join(process.cwd(), 'src', 'gate', 'migrations')
const outPath = join(process.cwd(), 'src', 'core', 'transform-manifest.json')

const hashFile = (p) =>
  createHash('sha256')
    .update(readFileSync(p, 'utf8').replace(/\r\n/g, '\n'))
    .digest('hex')

// Hash core determinism-critical source files
const coreFiles = [
  'src/core/canonicalize.ts',
  'src/core/hashing.ts',
  'src/core/ordering.ts',
  'src/core/fixedpoint.ts',
  'src/core/immutable.ts',
  'src/projection/reducer.ts',
  'src/gate/hoeffding.ts',
]
const reducer_hashes = {}
for (const f of coreFiles) {
  const fp = join(process.cwd(), f)
  if (existsSync(fp)) {
    reducer_hashes[f] = hashFile(fp)
  }
}

// Hash migration transform files
const migrationFiles = existsSync(migrationsDir) && statSync(migrationsDir).isDirectory()
  ? readdirSync(migrationsDir)
      .filter(f => ['.ts', '.js'].includes(extname(f)))
      .sort()
  : []

const migration_hashes = {}
for (const f of migrationFiles) {
  const fp = realpathSync(join(migrationsDir, f))
  // Path traversal guard
  if (!fp.startsWith(realpathSync(migrationsDir) + sep)) {
    throw new Error(`PATH_ESCAPE: ${f}`)
  }
  migration_hashes[f.replace(extname(f), '').toUpperCase()] = hashFile(fp)
}

const manifest = {
  _spec_ref: 'v2.1-Ω §5.4 Ω.D.1',
  build_id: process.env.SO_BUILD_ID ?? null,
  source_date_epoch: process.env.SOURCE_DATE_EPOCH ?? null,
  reducer_hashes,
  migration_hashes,
  sealed: true,
}

writeFileSync(outPath, JSON.stringify(manifest, null, 2))
console.log(`[hash-transforms] Manifest written to ${outPath}`)
console.log(`[hash-transforms] ${Object.keys(reducer_hashes).length} core files + ${Object.keys(migration_hashes).length} migrations hashed`)
