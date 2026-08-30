#!/usr/bin/env node
/**
 * AEGIS-Ω Swarm Monitor
 * Listens for UDP gossip frames on the configured port and renders
 * live swarm state in the terminal. No external dependencies — Node.js stdlib only.
 *
 * Usage:
 *   node scripts/swarm_monitor.js [--port=9090] [--width=80]
 *
 * Frame layout (64 bytes, little-endian):
 *   [0..2]   magic: 0xE0E0
 *   [2..4]   local_node_id: u16
 *   [4..12]  root_state_pulses: u64
 *   [12..20] semantic_traversals: u64
 *   [20..28] agent_state_alpha: u64
 *   [28..36] agent_state_beta: u64
 *   [36..44] agent_state_gamma: u64
 *   [44..52] reserved_a: u64 = 0
 *   [52..60] reserved_b: u64 = 0
 *   [60..62] cluster_consensus_score: u16
 *   [62..64] network_friction: u16
 */

'use strict';

const dgram = require('dgram');

const MAGIC         = 0xE0E0;
const FRAME_SIZE    = 64;
const MAX_NODES     = 64;
const RENDER_INTERVAL_MS = 500;

// --- CLI args ---
const args = Object.fromEntries(
  process.argv.slice(2)
    .filter(a => a.startsWith('--'))
    .map(a => { const [k, v] = a.slice(2).split('='); return [k, v ?? 'true']; })
);
const PORT  = parseInt(args.port  ?? '9090', 10);
const WIDTH = parseInt(args.width ?? '80', 10);

// --- Node registry ---
const nodes = new Map(); // node_id → { ...frame fields, raddr, last_seen }
let totalFrames = 0;
let badFrames   = 0;

function parseFrame(buf, rinfo) {
  if (buf.length < FRAME_SIZE) return null;
  const magic = buf.readUInt16LE(0);
  if (magic !== MAGIC) return null;
  return {
    node_id:                buf.readUInt16LE(2),
    root_state_pulses:      readU64LE(buf,  4),
    semantic_traversals:    readU64LE(buf, 12),
    agent_state_alpha:      readU64LE(buf, 20),
    agent_state_beta:       readU64LE(buf, 28),
    agent_state_gamma:      readU64LE(buf, 36),
    cluster_consensus_score: buf.readUInt16LE(60),
    network_friction:        buf.readUInt16LE(62),
    raddr:                  `${rinfo.address}:${rinfo.port}`,
    last_seen:              Date.now(),
  };
}

function readU64LE(buf, offset) {
  // Node.js < 12 doesn't have readBigUInt64LE in all builds — fall back to two u32
  try {
    return buf.readBigUInt64LE(offset);
  } catch {
    const lo = buf.readUInt32LE(offset);
    const hi = buf.readUInt32LE(offset + 4);
    return BigInt(lo) + (BigInt(hi) << 32n);
  }
}

// --- UDP server ---
const server = dgram.createSocket('udp4');

server.on('error', err => {
  console.error(`[AEGIS-SWARM] Socket error: ${err.message}`);
  server.close();
});

server.on('message', (buf, rinfo) => {
  totalFrames++;
  const frame = parseFrame(buf, rinfo);
  if (!frame) { badFrames++; return; }
  if (nodes.size >= MAX_NODES && !nodes.has(frame.node_id)) return; // cap
  nodes.set(frame.node_id, frame);
});

server.bind(PORT, () => {
  console.clear();
  console.log(`[AEGIS-SWARM] Listening on UDP :${PORT} — waiting for gossip frames…`);
});

// --- Renderer ---
function bar(value, max, width, char = '█') {
  const filled = max === 0n ? 0 : Math.round(Number((BigInt(width) * value) / BigInt(max)));
  return char.repeat(Math.min(filled, width)) + ' '.repeat(Math.max(width - filled, 0));
}

function friction(f) {
  if (f === 0) return '\x1b[32m✓ 0\x1b[0m';
  if (f < 10)  return `\x1b[33m⚠ ${f}\x1b[0m`;
  return `\x1b[31m✗ ${f}\x1b[0m`;
}

function render() {
  const now = Date.now();
  const stale = 5000; // ms without frame → grey out
  const sortedNodes = [...nodes.values()].sort((a, b) => a.node_id - b.node_id);

  process.stdout.write('\x1b[H\x1b[2J'); // clear screen

  const title = ' AEGIS-Ω SWARM MONITOR ';
  const pad = Math.floor((WIDTH - title.length) / 2);
  console.log('─'.repeat(pad) + title + '─'.repeat(WIDTH - pad - title.length));
  console.log(`  Nodes: ${sortedNodes.length}  |  Frames received: ${totalFrames}  |  Bad frames: ${badFrames}`);
  console.log('─'.repeat(WIDTH));

  if (sortedNodes.length === 0) {
    console.log('  (no nodes heard yet)');
  } else {
    const maxPulses = sortedNodes.reduce((m, n) => n.root_state_pulses > m ? n.root_state_pulses : m, 0n);
    const maxScore  = 10000n;
    for (const n of sortedNodes) {
      const age    = now - n.last_seen;
      const dim    = age > stale ? '\x1b[2m' : '';
      const rst    = '\x1b[0m';
      const pBar   = bar(n.root_state_pulses, maxPulses > 0n ? maxPulses : 1n, 20);
      const cBar   = bar(BigInt(n.cluster_consensus_score), maxScore, 20);
      console.log(
        `${dim}  Node ${String(n.node_id).padStart(4)} │ `
        + `pulses [${pBar}] ${String(n.root_state_pulses).padStart(8)} │ `
        + `consensus [${cBar}] ${String(n.cluster_consensus_score).padStart(5)} │ `
        + `friction ${friction(n.network_friction)} │ `
        + `traversals ${n.semantic_traversals}`
        + `${rst}`
      );
    }
  }

  console.log('─'.repeat(WIDTH));
  console.log(`  Ctrl-C to exit  |  Port ${PORT}`);
}

setInterval(render, RENDER_INTERVAL_MS);
process.on('SIGINT', () => { server.close(); process.exit(0); });
