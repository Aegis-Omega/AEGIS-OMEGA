//! Gate 322 — Constitutional Synthesis Monitor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Synthesises the gossip health verdict (Gate 320) and resonance certification
//! (Gate 321) into a single T0 constitutional verdict with a SHA-256 hash chain.
//!
//! T0 verdict rules (top-to-bottom, first match):
//!   false — gossip_health_class == Red  (dead peers / exceeded epochs / sequence flood)
//!   false — resonance_certified == false (phi breach, ring broken, or non-monotone)
//!   true  — gossip_health_class != Red AND resonance_certified == true
//!
//! Yellow gossip is constitutionally degraded but not violated:
//!   the organism can still certify if resonance holds.
//!
//! report_hash = SHA-256(
//!   prev_hash[32]
//!   ‖ epoch_be8
//!   ‖ health_class_byte          (Green=0, Yellow=1, Red=2)
//!   ‖ resonance_certified_byte   (0 or 1)
//!   ‖ t0_verdict_byte            (0 or 1)
//! )
//!
//! ConstitutionalSynthesisMonitor:
//!   record(), latest(), t0_verdict(), health_class(), verify_chain()
//! verify_chain() → (bool, Option<usize>) — index of first invalid record.

use sha2::{Sha256, Digest};
use crate::gossip_health_report::NetworkHealthClass;

pub const SYNTHESIS_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── T0 verdict ──────────────────────────────────────────────────────────────

/// Compute the T0 constitutional verdict from its two inputs.
///
/// Red gossip health overrides a certified resonance score — the gossip layer
/// has detected a hard network violation (dead peer / sequence flood / epoch
/// excess) that cannot be resolved by mathematical coherence alone.
#[inline]
pub fn compute_t0_verdict(
    gossip_health_class:  NetworkHealthClass,
    resonance_certified:  bool,
) -> bool {
    gossip_health_class != NetworkHealthClass::Red && resonance_certified
}

// ─── Synthesis record ─────────────────────────────────────────────────────────

/// A single hash-chained constitutional synthesis record.
#[derive(Debug, Clone, PartialEq)]
pub struct ConstitutionalSynthesisRecord {
    pub epoch:                u64,
    pub gossip_health_class:  NetworkHealthClass,
    pub resonance_certified:  bool,
    pub t0_verdict:           bool,
    pub report_hash:          [u8; 32],
    pub prev_hash:            [u8; 32],
}

// ─── Input ────────────────────────────────────────────────────────────────────

/// Inputs for one synthesis record.
#[derive(Debug, Clone, Copy)]
pub struct SynthesisInput {
    pub epoch:               u64,
    pub gossip_health_class: NetworkHealthClass,
    pub resonance_certified: bool,
}

// ─── Hash computation ─────────────────────────────────────────────────────────

fn compute_synthesis_hash(
    prev:      &[u8; 32],
    epoch:     u64,
    health:    NetworkHealthClass,
    certified: bool,
    t0:        bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([health.class_byte()]);
    h.update([certified as u8]);
    h.update([t0 as u8]);
    h.finalize().into()
}

// ─── Monitor ──────────────────────────────────────────────────────────────────

/// Append-only hash-chained ledger of constitutional synthesis verdicts.
pub struct ConstitutionalSynthesisMonitor {
    records: Vec<ConstitutionalSynthesisRecord>,
}

impl ConstitutionalSynthesisMonitor {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[ConstitutionalSynthesisRecord] { &self.records }

    /// Record a synthesis verdict, chaining from the last report (or genesis).
    pub fn record(&mut self, inp: SynthesisInput) -> ConstitutionalSynthesisRecord {
        let prev = self.records.last()
            .map(|r| r.report_hash)
            .unwrap_or(SYNTHESIS_GENESIS_HASH);

        let t0 = compute_t0_verdict(inp.gossip_health_class, inp.resonance_certified);

        let report_hash = compute_synthesis_hash(
            &prev,
            inp.epoch,
            inp.gossip_health_class,
            inp.resonance_certified,
            t0,
        );

        let rec = ConstitutionalSynthesisRecord {
            epoch:               inp.epoch,
            gossip_health_class: inp.gossip_health_class,
            resonance_certified: inp.resonance_certified,
            t0_verdict:          t0,
            report_hash,
            prev_hash:           prev,
        };
        self.records.push(rec.clone());
        rec
    }

    /// Most recently recorded synthesis record, or `None` if empty.
    pub fn latest(&self) -> Option<&ConstitutionalSynthesisRecord> {
        self.records.last()
    }

    /// T0 verdict of the most recent record, or `None` if empty.
    pub fn t0_verdict(&self) -> Option<bool> {
        self.latest().map(|r| r.t0_verdict)
    }

    /// Gossip health class of the most recent record, or `None` if empty.
    pub fn health_class(&self) -> Option<NetworkHealthClass> {
        self.latest().map(|r| r.gossip_health_class)
    }

    /// Verify hash-chain integrity.
    ///
    /// Returns `(true, None)` when all links are valid.
    /// Returns `(false, Some(idx))` where `idx` is the first broken record.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = SYNTHESIS_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_synthesis_hash(
                &prev,
                r.epoch,
                r.gossip_health_class,
                r.resonance_certified,
                r.t0_verdict,
            );
            if r.report_hash != expected {
                return (false, Some(i));
            }
            prev = r.report_hash;
        }
        (true, None)
    }
}

impl Default for ConstitutionalSynthesisMonitor {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gossip_health_report::NetworkHealthClass;

    fn green_certified(epoch: u64) -> SynthesisInput {
        SynthesisInput {
            epoch,
            gossip_health_class: NetworkHealthClass::Green,
            resonance_certified: true,
        }
    }

    // ── Genesis ────────────────────────────────────────────────────────────────

    #[test]
    fn genesis_hash_is_zero() {
        assert_eq!(SYNTHESIS_GENESIS_HASH, [0u8; 32]);
    }

    #[test]
    fn fresh_monitor_empty() {
        let m = ConstitutionalSynthesisMonitor::new();
        assert!(m.is_empty());
        assert!(m.latest().is_none());
        assert!(m.t0_verdict().is_none());
        assert!(m.health_class().is_none());
    }

    // ── T0 verdict rules ───────────────────────────────────────────────────────

    #[test]
    fn green_resonant_t0_true() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(green_certified(1));
        assert!(r.t0_verdict);
        assert_eq!(m.t0_verdict(), Some(true));
    }

    #[test]
    fn yellow_resonant_t0_true() {
        // Yellow = degraded, not violated; resonance still certifies
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(SynthesisInput {
            epoch: 1,
            gossip_health_class: NetworkHealthClass::Yellow,
            resonance_certified: true,
        });
        assert!(r.t0_verdict);
    }

    #[test]
    fn red_resonant_t0_false() {
        // Red overrides resonance — hard network violation
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(SynthesisInput {
            epoch: 1,
            gossip_health_class: NetworkHealthClass::Red,
            resonance_certified: true,
        });
        assert!(!r.t0_verdict);
    }

    #[test]
    fn green_not_certified_t0_false() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(SynthesisInput {
            epoch: 1,
            gossip_health_class: NetworkHealthClass::Green,
            resonance_certified: false,
        });
        assert!(!r.t0_verdict);
    }

    #[test]
    fn yellow_not_certified_t0_false() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(SynthesisInput {
            epoch: 1,
            gossip_health_class: NetworkHealthClass::Yellow,
            resonance_certified: false,
        });
        assert!(!r.t0_verdict);
    }

    #[test]
    fn red_not_certified_t0_false() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(SynthesisInput {
            epoch: 1,
            gossip_health_class: NetworkHealthClass::Red,
            resonance_certified: false,
        });
        assert!(!r.t0_verdict);
    }

    // ── compute_t0_verdict standalone ─────────────────────────────────────────

    #[test]
    fn standalone_t0_all_combinations() {
        assert!( compute_t0_verdict(NetworkHealthClass::Green,  true));
        assert!( compute_t0_verdict(NetworkHealthClass::Yellow, true));
        assert!(!compute_t0_verdict(NetworkHealthClass::Red,    true));
        assert!(!compute_t0_verdict(NetworkHealthClass::Green,  false));
        assert!(!compute_t0_verdict(NetworkHealthClass::Yellow, false));
        assert!(!compute_t0_verdict(NetworkHealthClass::Red,    false));
    }

    // ── Hash chain linking ─────────────────────────────────────────────────────

    #[test]
    fn first_record_prev_is_genesis() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(green_certified(1));
        assert_eq!(r.prev_hash, SYNTHESIS_GENESIS_HASH);
    }

    #[test]
    fn second_record_links_to_first() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r1 = m.record(green_certified(1));
        let r2 = m.record(green_certified(2));
        assert_eq!(r2.prev_hash, r1.report_hash);
    }

    #[test]
    fn chain_links_three_records() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r1 = m.record(green_certified(1));
        let r2 = m.record(green_certified(2));
        let r3 = m.record(green_certified(3));
        assert_eq!(r1.prev_hash, SYNTHESIS_GENESIS_HASH);
        assert_eq!(r2.prev_hash, r1.report_hash);
        assert_eq!(r3.prev_hash, r2.report_hash);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let m = ConstitutionalSynthesisMonitor::new();
        let (ok, idx) = m.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        m.record(green_certified(1));
        m.record(SynthesisInput {
            epoch: 2,
            gossip_health_class: NetworkHealthClass::Yellow,
            resonance_certified: true,
        });
        m.record(SynthesisInput {
            epoch: 3,
            gossip_health_class: NetworkHealthClass::Red,
            resonance_certified: false,
        });
        let (ok, idx) = m.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered_report_hash() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        m.record(green_certified(1));
        m.record(green_certified(2));
        m.records[1].report_hash[0] ^= 0xFF;
        let (ok, idx) = m.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_tampered_prev_hash() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        m.record(green_certified(1));
        m.record(green_certified(2));
        m.records[1].prev_hash[0] ^= 0x01;
        let (ok, idx) = m.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_tampered_t0_field() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        m.record(green_certified(1));
        // Silently flip t0_verdict — chain must catch it
        m.records[0].t0_verdict = false;
        let (ok, idx) = m.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── Determinism ───────────────────────────────────────────────────────────

    #[test]
    fn determinism_same_input_three_times() {
        let inp = green_certified(42);
        let mut m1 = ConstitutionalSynthesisMonitor::new(); let r1 = m1.record(inp);
        let mut m2 = ConstitutionalSynthesisMonitor::new(); let r2 = m2.record(inp);
        let mut m3 = ConstitutionalSynthesisMonitor::new(); let r3 = m3.record(inp);
        assert_eq!(r1.report_hash, r2.report_hash);
        assert_eq!(r2.report_hash, r3.report_hash);
    }

    #[test]
    fn different_epoch_different_hash() {
        let mut m1 = ConstitutionalSynthesisMonitor::new(); let r1 = m1.record(green_certified(1));
        let mut m2 = ConstitutionalSynthesisMonitor::new(); let r2 = m2.record(green_certified(2));
        assert_ne!(r1.report_hash, r2.report_hash);
    }

    #[test]
    fn different_health_class_different_hash() {
        let inp_green = green_certified(1);
        let inp_yellow = SynthesisInput {
            epoch: 1,
            gossip_health_class: NetworkHealthClass::Yellow,
            resonance_certified: true,
        };
        let mut m1 = ConstitutionalSynthesisMonitor::new(); let r1 = m1.record(inp_green);
        let mut m2 = ConstitutionalSynthesisMonitor::new(); let r2 = m2.record(inp_yellow);
        assert_ne!(r1.report_hash, r2.report_hash);
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    #[test]
    fn epoch_preserved() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(green_certified(77));
        assert_eq!(r.epoch, 77);
    }

    #[test]
    fn health_class_accessor() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        m.record(SynthesisInput {
            epoch: 1,
            gossip_health_class: NetworkHealthClass::Yellow,
            resonance_certified: true,
        });
        assert_eq!(m.health_class(), Some(NetworkHealthClass::Yellow));
    }

    #[test]
    fn report_hash_nonzero() {
        let mut m = ConstitutionalSynthesisMonitor::new();
        let r = m.record(green_certified(1));
        assert_ne!(r.report_hash, [0u8; 32]);
    }

    // ── Transition sequences ──────────────────────────────────────────────────

    #[test]
    fn transition_from_t0_true_to_false_and_back() {
        let mut m = ConstitutionalSynthesisMonitor::new();

        // Start healthy
        m.record(green_certified(1));
        assert_eq!(m.t0_verdict(), Some(true));

        // Gossip goes red (network partition)
        m.record(SynthesisInput {
            epoch: 2,
            gossip_health_class: NetworkHealthClass::Red,
            resonance_certified: true,
        });
        assert_eq!(m.t0_verdict(), Some(false));

        // Network recovers, resonance still holds
        m.record(green_certified(3));
        assert_eq!(m.t0_verdict(), Some(true));

        // Chain must be valid throughout
        let (ok, _) = m.verify_chain();
        assert!(ok);
    }
}
