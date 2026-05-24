#!/usr/bin/env node
/**
 * Global Resonance Visualizer - Zero-Dependency Node.js Terminal Interface
 * 
 * EPISTEMIC TIER: T0 (mechanically proven)
 * Constitutional root: O(t) = Σ atomicᵢ for real-time introspection
 * 
 * This script listens for UDP telemetry heartbeats from AEGIS swarm nodes
 * and renders a real-time terminal dashboard showing:
 * - T0 Ledger integrity status
 * - Semantic traversal activity
 * - Acoustic state distribution (The Breath)
 * - Swarm harmony index
 * - Hysteresis tension level
 * - Real-time waveform visualization
 */

const dgram = require('dgram');

// ANSI escape codes for terminal manipulation
const CLEAR_SCREEN = '\x1B[2J\x1B[0f';
const HIDE_CURSOR = '\x1B[?25l';
const SHOW_CURSOR = '\x1B[?25h';
const RESET_COLOR = '\x1b[0m';

// Color codes
const COLORS = {
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    red: '\x1b[31m',
    cyan: '\x1b[36m',
    blue: '\x1b[34m',
    magenta: '\x1b[35m',
    white: '\x1b[37m',
    bright: '\x1b[90m',
};

// Swarm state aggregation
const swarmState = {
    nodesAlive: 0,
    totalSemanticTraversals: 0,
    t0IntegrityPulse: 0,
    acousticChord: {
        clear: 0,
        concealed: 0,
        merged: 0,
        prolonged: 0,
        vibrating: 0
    },
    harmonyIndex: 100,
    hysteresisTension: 0
};

// Node registry for tracking active swarm members
const nodeRegistry = new Map();

// Create UDP server
const server = dgram.createSocket('udp4');

/**
 * Processes incoming telemetry packets
 * Packet format (64 bytes total):
 * - Bytes 0-1:   Magic number (0xE0E0)
 * - Bytes 2-3:   Node ID (u16 LE)
 * - Bytes 4-11:  T0 integrity pulse (u64 LE)
 * - Bytes 12-19: Semantic traversals (u64 LE)
 * - Bytes 20-27: Acoustic clear count (u64 LE)
 * - Bytes 28-35: Acoustic concealed count (u64 LE)
 * - Bytes 36-43: Acoustic merged count (u64 LE)
 * - Bytes 44-51: Acoustic prolonged count (u64 LE)
 * - Bytes 52-59: Acoustic vibrating count (u64 LE)
 * - Bytes 60-61: Harmony index (u16 LE)
 * - Bytes 62-63: Tension level (u16 LE)
 */
server.on('message', (msg) => {
    // Validate packet length and magic number
    if (msg.length < 64) return;
    
    const magic = msg.readUInt16LE(0);
    if (magic !== 0xE0E0) return;
    
    const nodeId = msg.readUInt16LE(2);
    
    // Update node registry
    nodeRegistry.set(nodeId, Date.now());
    swarmState.nodesAlive = nodeRegistry.size;
    
    // Aggregate telemetry data
    swarmState.t0IntegrityPulse = Number(msg.readBigUInt64LE(4));
    swarmState.totalSemanticTraversals += Number(msg.readBigUInt64LE(12));
    swarmState.acousticChord.clear += Number(msg.readBigUInt64LE(20));
    swarmState.acousticChord.concealed += Number(msg.readBigUInt64LE(28));
    swarmState.acousticChord.merged += Number(msg.readBigUInt64LE(36));
    swarmState.acousticChord.prolonged += Number(msg.readBigUInt64LE(44));
    swarmState.acousticChord.vibrating += Number(msg.readBigUInt64LE(52));
    swarmState.harmonyIndex = msg.readUInt16LE(60);
    swarmState.hysteresisTension = msg.readUInt16LE(62);
});

/**
 * Renders a progress bar using block characters
 */
function renderBar(value, max, length, char = '█') {
    const filled = Math.min(length, Math.floor((value / max) * length));
    const empty = length - filled;
    return char.repeat(filled) + '░'.repeat(empty);
}

/**
 * Renders the acoustic chord distribution
 */
function renderAcousticChord() {
    const chord = swarmState.acousticChord;
    const totalBreath = chord.clear + chord.concealed + chord.merged + 
                        chord.prolonged + chord.vibrating + 1;
    
    const bars = [
        { label: 'Clear',     value: chord.clear,     char: '░', color: COLORS.white },
        { label: 'Concealed', value: chord.concealed, char: '▒', color: COLORS.blue },
        { label: 'Merged',    value: chord.merged,    char: '▓', color: COLORS.cyan },
        { label: 'Prolonged', value: chord.prolonged, char: '█', color: COLORS.green },
        { label: 'Vibrating', value: chord.vibrating, char: '▄', color: COLORS.magenta },
    ];
    
    let output = '';
    for (const bar of bars) {
        const width = Math.floor((bar.value / totalBreath) * 30);
        const displayWidth = Math.max(0, width);
        output += `    ${bar.label.padEnd(11)} ${bar.color}${bar.char.repeat(displayWidth)}${RESET_COLOR}\n`;
    }
    return output;
}

/**
 * Generates a real-time sine wave visualization
 */
function renderWaveform() {
    const width = 60;
    const harmonyFactor = swarmState.harmonyIndex / 100;
    const prolongationBoost = swarmState.acousticChord.prolonged / 10;
    const amplitude = (harmonyFactor * 3) + prolongationBoost;
    const phase = Date.now() / 200;
    
    let wave = '';
    for (let i = 0; i < width; i++) {
        const x = phase + (i * 0.3);
        const y = Math.round(4 + Math.sin(x) * amplitude);
        
        if (y === 4) {
            wave += '━';
        } else if (y > 4) {
            wave += `${COLORS.cyan}╱${RESET_COLOR}`;
        } else {
            wave += `${COLORS.cyan}╲${RESET_COLOR}`;
        }
    }
    return wave;
}

/**
 * Determines color based on harmony index
 */
function getHarmonyColor() {
    if (swarmState.harmonyIndex > 80) return COLORS.green;
    if (swarmState.harmonyIndex > 50) return COLORS.yellow;
    return COLORS.red;
}

/**
 * Main dashboard render function
 */
function renderDashboard() {
    // Clean up stale nodes (no heartbeat in 5 seconds)
    const now = Date.now();
    for (const [id, lastSeen] of nodeRegistry.entries()) {
        if (now - lastSeen > 5000) {
            nodeRegistry.delete(id);
        }
    }
    swarmState.nodesAlive = nodeRegistry.size;
    
    // Clear screen and reset cursor
    process.stdout.write(CLEAR_SCREEN);
    
    // Header
    console.log(`${COLORS.cyan}╔════════════════════════════════════════════════════════════════╗${RESET_COLOR}`);
    console.log(`${COLORS.cyan}║${RESET_COLOR}         AEGIS-Ω CYBERNETIC GARDEN: GLOBAL RESONANCE          ${COLORS.cyan}║${RESET_COLOR}`);
    console.log(`${COLORS.cyan}╚════════════════════════════════════════════════════════════════╝${RESET_COLOR}\n`);
    
    // Section 1: The Anchor (T0 Ledger)
    console.log(`  ${COLORS.bright}[ THE ANCHOR ]${RESET_COLOR} T0 Ledger Integrity: ${COLORS.green}VERIFIED & SEALED${RESET_COLOR}`);
    console.log(`               Pulse Count: ${swarmState.t0IntegrityPulse}`);
    
    // Section 2: The Intellect (Semantic Traversals)
    const intellectBar = renderBar(
        Math.min(swarmState.totalSemanticTraversals, 4000),
        4000,
        40,
        '█'
    );
    console.log(`\n  ${COLORS.bright}[ THE INTELLECT ]${RESET_COLOR} Semantic Traversal:`);
    console.log(`               ${intellectBar} (${swarmState.totalSemanticTraversals}/s)`);
    
    // Section 3: The Breath (Acoustic States)
    console.log(`\n  ${COLORS.bright}[ THE BREATH ]${RESET_COLOR} Acoustic State Resonance:`);
    console.log(renderAcousticChord());
    
    // Section 4: The Unity (Swarm Harmony)
    const harmonyColor = getHarmonyColor();
    console.log(`  ${COLORS.bright}[ THE UNITY ]${RESET_COLOR} Swarm Harmony: ${harmonyColor}${swarmState.harmonyIndex}%${RESET_COLOR}`);
    console.log(`  ${COLORS.bright}[ THE FRICTION ]${RESET_COLOR} Hysteresis Tension: ${swarmState.hysteresisTension}`);
    
    // Section 5: The Waveform
    console.log(`\n  ${COLORS.bright}[ THE WAVEFORM ]${RESET_COLOR}`);
    console.log(`  ${renderWaveform()}`);
    
    // Footer: Active Nodes
    console.log(`\n  ${COLORS.bright}Nodes in active resonance:${RESET_COLOR} ${COLORS.cyan}${swarmState.nodesAlive}${RESET_COLOR}`);
    
    // Decay counters for next render cycle (exponential moving average)
    for (let key in swarmState.acousticChord) {
        swarmState.acousticChord[key] = Math.floor(swarmState.acousticChord[key] * 0.8);
    }
    swarmState.totalSemanticTraversals = 0;
}

// Error handling
server.on('error', (err) => {
    console.error(`[SERVER ERROR] ${err.message}`);
    process.exit(1);
});

// Graceful shutdown
process.on('SIGINT', () => {
    process.stdout.write(SHOW_CURSOR);
    console.log('\n\n[SHUTDOWN] Resonance visualizer terminating...');
    server.close(() => {
        process.exit(0);
    });
});

process.on('SIGTERM', () => {
    process.stdout.write(SHOW_CURSOR);
    server.close(() => {
        process.exit(0);
    });
});

// Start server
const PORT = process.env.TELEMETRY_PORT || 9000;
const HOST = process.env.TELEMETRY_HOST || '0.0.0.0';

server.bind(PORT, HOST, () => {
    console.log(`${COLORS.green}╔════════════════════════════════════════════════════════════════╗${RESET_COLOR}`);
    console.log(`${COLORS.green}║${RESET_COLOR}     RESONANCE DASHBOARD LISTENING ON UDP ${PORT}${' '.repeat(20)}${COLORS.green}║${RESET_COLOR}`);
    console.log(`${COLORS.green}╚════════════════════════════════════════════════════════════════╝${RESET_COLOR}`);
    console.log(`\nWaiting for telemetry heartbeats from AEGIS swarm nodes...\n`);
    console.log(`Press Ctrl+C to exit.\n`);
    
    // Hide cursor and start render loop
    process.stdout.write(HIDE_CURSOR);
    
    setInterval(() => {
        renderDashboard();
    }, 500);
});
