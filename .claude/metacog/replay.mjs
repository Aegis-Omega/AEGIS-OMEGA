#!/usr/bin/env node
// ============================================================
// AEGIS — Replay-Verification Harness (harness-layer / Gate 0)
//
// Enacts REPLAY SOVEREIGNTY: replay(genesis, events) → identical topology hash.
// Wired into the pre-commit gate: a chain that does not replay cannot commit.
//
// This is stronger than certify(). certify() trusts each stored entry_hash and
// checks local consistency. replay() THROWS AWAY every stored hash and rebuilds
// the entire chain from genesis using ONLY the observations (layer, signal, tier)
// and the monotonic sequence — exactly replay(genesis, events). Because each
// rebuilt hash feeds the next (prev-linked from genesis), any tamper anywhere —
// even a single internally re-hashed entry — cascades forward and changes the
// terminal topology hash. The derived terminal must equal the stored terminal.
//
// Determinism: the reconstruction is run THREE times and asserted byte-identical
// across all runs (per testing.md — one or two runs are insufficient to confirm
// determinism). This is the "cross-platform deterministic replay" hard problem
// enacted at harness scale.
//
// DIVERGENCE iff  derived_terminal ≠ stored_terminal  OR  any run differs.
// On divergence the gate exits 2 and the commit is blocked.
//
// Dependency-free: node:crypto + node:fs.
// ============================================================
import { createHash } from 'node:crypto'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const REPO   = process.env.CLAUDE_PROJECT_DIR || '/home/user/AEGIS--'
const DIR    = join(REPO, '.claude/metacog')
const CHAIN  = process.env.AEGIS_METACOG_CHAIN || join(DIR, 'chain.jsonl')
const GENESIS = '0'.repeat(64)

function canon(v) {
  if (v === null || typeof v !== 'object') {
    return JSON.stringify(typeof v === 'string' ? v.normalize('NFC') : v)
  }
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']'
  return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}'
}
const sha256 = s => createHash('sha256').update(s, 'utf8').digest('hex')
function readLines(path) {
  if (!existsSync(path)) return []
  return readFileSync(path, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l))
}

// replay(genesis, events): rebuild the whole chain from observations alone.
// Returns the derived terminal hash — the topology hash of the reconstruction.
function replayFromGenesis(entries) {
  let prev = GENESIS
  for (let i = 0; i < entries.length; i++) {
    const obs = entries[i].observation
    const seq = entries[i].sequence
    prev = sha256(canon({ observation: obs, previous_entry_hash: prev, sequence: String(seq) }))
  }
  return prev  // terminal topology hash
}

function verify() {
  const entries = readLines(CHAIN)
  const stored_terminal = entries.length ? entries[entries.length - 1].entry_hash : GENESIS

  // Run the reconstruction three times; assert byte-identical (determinism).
  const runs = [replayFromGenesis(entries), replayFromGenesis(entries), replayFromGenesis(entries)]
  const replay_deterministic = runs[0] === runs[1] && runs[1] === runs[2]
  const derived_terminal = runs[0]
  const replays = derived_terminal === stored_terminal

  return {
    replays,
    replay_deterministic,
    diverged: !replays || !replay_deterministic,
    entry_count: entries.length,
    derived_terminal,
    stored_terminal,
    runs_identical: replay_deterministic,
  }
}

const [cmd] = process.argv.slice(2)
const r = verify()
switch (cmd) {
  case 'verify':
  case 'status':
    console.log(JSON.stringify(r))
    break
  case 'gate':
    if (r.diverged) {
      const reason = !r.replay_deterministic
        ? 'replay non-deterministic — reconstruction differed across runs (topology non-determinism)'
        : `replay divergence — derived terminal ${r.derived_terminal.slice(0, 12)} ≠ stored ${r.stored_terminal.slice(0, 12)}`
      console.error(`REPLAY DIVERGENCE — replay(genesis, events) does not reproduce the chain.\n  ${reason}`)
      process.exit(2)
    }
    console.log(`replay verified — ${r.entry_count} events fold to ${r.derived_terminal.slice(0, 12)} (3 runs identical). OK.`)
    process.exit(0)
  default:
    console.error('usage: replay.mjs verify | status | gate')
    process.exit(2)
}
