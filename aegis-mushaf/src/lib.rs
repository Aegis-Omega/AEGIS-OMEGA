//! AEGIS Digital Mushaf — Constitutional Quranic Integrity Runtime
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
//!
//! # Domain Architecture
//!
//! Domain 0 — T0Core: immutable Quranic text (rasm, ayah bytes, SHA-256 chain)
//! Domain 1 — TafsirOverlay: mutable commentary (never modifies Domain 0)
//! Epistemic firewall: BTreeMap<AyahKey, T0Core> — BTreeMap for deterministic iteration
//!
//! # Constitutional Invariants
//! - No HashMap (BTreeMap only — deterministic key ordering)
//! - No tokio (std::net::UdpSocket for telemetry)
//! - TANZIL_GENESIS_SEAL is T2 placeholder — migration to T0 requires SHA-256
//!   verification against the actual Tanzil XML corpus at ingest time
//! - Domain 0 bytes are append-only; no mutation path exists
//! - Tajweed DFA transitions are deterministic — no floating-point

pub mod epistemic_firewall;
pub mod nuqta_canvas;
pub mod semantic_algebra;
pub mod tajweed_dfa;
pub mod tanzil_ledger;
pub mod telemetry_emitter;
