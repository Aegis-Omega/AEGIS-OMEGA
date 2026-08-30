//! AEGIS-Ω Distributed Agent Swarm Runtime
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
//!
//! # Technical Pillars
//!
//! 1. `genesis_ledger`    — T0 immutable ledger with continuous integrity verification
//! 2. `domain_boundary`   — Epistemic firewall enforcing D₀ → D₁ unidirectional access
//! 3. `semantic_algebra`  — Zero-allocation fractal arena for semantic graphs
//! 4. `acoustic_dfa`      — Deterministic finite automaton for phonetic states
//! 5. `telemetry_emitter` — Zero-allocation UDP telemetry for swarm observability
//! 6. `state_anchor`      — Root cryptographic state anchor (SHA-256 hash-chained ledger)
//! 7. `domain_firewall`   — Strict domain-isolated memory sandbox (OpaqueSegmentKey)
//! 8. `affine_canvas`     — Deterministic affine multi-agent coordinate space
//! 9. `semantic_graph`    — Hierarchical sparse-matrix semantic knowledge graph
//! 10. `validation_dfa`   — Syntactic validation DFA (compile-time state table)
//! 11. `gossip_emitter`   — Zero-copy UDP scatter-gather gossip protocol
//! 12. `hysteresis`       — Non-linear hysteresis peer reputation filter
//!
//! # Constitutional Invariants
//! - BTreeMap throughout — no HashMap; deterministic iteration order enforced
//! - No tokio — std::thread + std::net::UdpSocket only
//! - No wall-clock time in determinism-critical paths — sequence numbers drive cadence
//! - active_violations == 0 required for T0 pass (mirrors corruption_count)

pub mod acoustic_dfa;
pub mod domain_boundary;
pub mod genesis_ledger;
pub mod semantic_algebra;
pub mod telemetry_emitter;
pub mod affine_canvas;
pub mod domain_firewall;
pub mod gossip_emitter;
pub mod hysteresis;
pub mod semantic_graph;
pub mod state_anchor;
pub mod validation_dfa;
// Full External and Internal Autonode — T0 verdict gate + all 7 pillars + GossipEmitter beacon
pub mod autonode;

pub const AEGIS_PROTOCOL_MAGIC: u16 = 0xE0E0;
pub const MAXIMUM_SWARM_NODES: usize = 1024;
pub const SCHEMA_VERSION: u16 = 0x0001;
