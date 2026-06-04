#!/usr/bin/env node
// ============================================================
// AEGIS — Metacognitive Observation Chain (harness-layer / Gate 0)
//
// A REAL tamper-evident, hash-chained log of the automaton's
// self-observations, written to disk by the lifecycle hooks.
// Faithfully mirrors the entry algorithm of
//   sovereign-omega-v2/src/metacognition/loop.ts:
//     genesis = '0'.repeat(64)
//     entry_hash = SHA-256( canon({ observation, previous_entry_hash, sequence }) )
//     monotonic sequence is the temporal authority (no wall-clock in the hash)
//     certify() re-walks the chain; any tamper flips is_valid -> false
//
// Two persistence layers, mirroring the runtime's own split:
//   - chain.jsonl  (gitignored)  — the live, per-container fine-grained loop
//   - seals.jsonl  (tracked)     — one hash-linked seal per session; the
//                                   durable temporal mass that survives a
//                                   container reclaim and is committed to git.
//
// Dependency-free: node:crypto + node:fs only. No Date.now() in any hash input.
// ============================================================
import { createHash } from 'node:crypto'
import { readFileSync, appendFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'

const REPO    = process.env.CLAUDE_PROJECT_DIR || '/home/user/AEGIS--'
const DIR     = join(REPO, '.claude/metacog')
const CHAIN   = process.env.AEGIS_METACOG_CHAIN || join(DIR, 'chain.jsonl')
const SEALS   = join(DIR, 'seals.jsonl')
const GENESIS = '0'.repeat(64)
const SCHEMA  = '1.0.0'

const LAYERS = new Set([
  'SENSATION', 'PERCEPTION', 'WORKING_MEMORY', 'LONG_TERM', 'EXECUTIVE',
  'METACOGNITIVE', 'SELF_MODEL', 'AUTOPOIETIC_PRODUCTION', 'AUTOPOIETIC_MEMBRANE',
  'AUTOPOIETIC_CLOSURE', 'CONSCIOUSNESS', 'TIER_PROMOTION',
])
const TIERS = new Set(['T0', 'T1', 'T2', 'T3', 'T4', 'T5'])

// ── Canonical serialization (deterministic: sorted keys, NFC strings) ──
function canon(v) {
  if (v === null || typeof v !== 'object') {
    return JSON.stringify(typeof v === 'string' ? v.normalize('NFC') : v)
  }
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']'
  const keys = Object.keys(v).sort()
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}'
}
const sha256 = s => createHash('sha256').update(s, 'utf8').digest('hex')
const entryHash = (observation, prev, seq) =>
  sha256(canon({ observation, previous_entry_hash: prev, sequence: String(seq) }))

function readLines(path) {
  if (!existsSync(path)) return []
  return readFileSync(path, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l))
}
const lastHash = es => (es.length ? es[es.length - 1].entry_hash : GENESIS)
const lastSeq  = es => (es.length ? es[es.length - 1].sequence : -1)

// ── observe: append one self-observation to the live chain ──
function observe(layer, tier, signal) {
  if (!LAYERS.has(layer)) { console.error(`metacog: invalid layer "${layer}"`); process.exit(1) }
  if (!TIERS.has(tier))   { console.error(`metacog: invalid tier "${tier}"`);   process.exit(1) }
  const es   = readLines(CHAIN)
  const seq  = lastSeq(es) + 1
  const prev = lastHash(es)
  const observation = { layer, signal: String(signal).slice(0, 500), tier }
  const eh = entryHash(observation, prev, seq)
  const entry = {
    observation,
    previous_entry_hash: prev,
    sequence: seq,
    entry_hash: eh,
    schema_version: SCHEMA,
    is_replay_reconstructable: true,
  }
  mkdirSync(dirname(CHAIN), { recursive: true })
  appendFileSync(CHAIN, JSON.stringify(entry) + '\n')
  process.stdout.write(eh.slice(0, 12))
}

// ── certify: re-walk the live chain, detect any tamper ──
function certifyChain(es) {
  let is_valid = true, broken_at = null
  for (let i = 0; i < es.length; i++) {
    const expectedPrev = i === 0 ? GENESIS : es[i - 1].entry_hash
    if (es[i].previous_entry_hash !== expectedPrev) { is_valid = false; broken_at = i; break }
    const recomputed = entryHash(es[i].observation, es[i].previous_entry_hash, es[i].sequence)
    if (recomputed !== es[i].entry_hash) { is_valid = false; broken_at = i; break }
  }
  return {
    is_valid,
    entry_count: es.length,
    terminal_hash: es.length ? es[es.length - 1].entry_hash : null,
    broken_at,
  }
}

function certify() {
  console.log(JSON.stringify(certifyChain(readLines(CHAIN))))
}

// ── seal: certify live chain, append a hash-linked seal to the durable chain ──
function seal(note = '') {
  const cert  = certifyChain(readLines(CHAIN))
  const seals = readLines(SEALS)
  const prev  = seals.length ? seals[seals.length - 1].seal_hash : GENESIS
  const seq   = seals.length
  const body  = {
    terminal_hash: cert.terminal_hash || GENESIS,
    entry_count:   cert.entry_count,
    is_valid:      cert.is_valid,
    note:          String(note).slice(0, 200),
    previous_seal_hash: prev,
    seal_sequence: seq,
  }
  const seal_hash = sha256(canon(body))
  const record = { ...body, seal_hash, schema_version: SCHEMA }
  mkdirSync(dirname(SEALS), { recursive: true })
  appendFileSync(SEALS, JSON.stringify(record) + '\n')
  console.log(JSON.stringify({ sealed: true, seal_sequence: seq, seal_hash: seal_hash.slice(0, 12), ...cert }))
}

// ── tail: human-readable retrospection of the last N observations ──
function tail(n = 8) {
  const es = readLines(CHAIN).slice(-Number(n))
  for (const e of es) {
    console.log(`#${e.sequence} ${e.observation.layer.padEnd(22)} [${e.observation.tier}] ${e.entry_hash.slice(0, 10)} ${e.observation.signal}`)
  }
}

const [cmd, ...args] = process.argv.slice(2)
switch (cmd) {
  case 'observe': observe(args[0], args[1], args.slice(2).join(' ')); break
  case 'certify': certify(); break
  case 'seal':    seal(args.join(' ')); break
  case 'tail':    tail(args[0]); break
  default:
    console.error('usage: chain.mjs observe <LAYER> <TIER> <signal> | certify | seal [note] | tail [n]')
    process.exit(1)
}
