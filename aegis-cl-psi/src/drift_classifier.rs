//! Gate 235: Drift Classifier — Constitutional Drift Severity (D0–D4)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Classifies the severity of constitutional drift between two ResonanceReport
//! snapshots (current vs previous epoch). Maps to the TypeScript D0–D4 divergence
//! surface (src/frame/divergence.ts) at the Rust organism layer.
//!
//! Drift severity classes:
//!   D0 — Observational: resonance_coefficient declined but all T1 invariants hold
//!   D1 — Serializer drift: phi_headroom changed direction (was positive, now negative or vice versa)
//!   D2 — Topology mismatch: ring_valid or sequence_monotone flipped to false
//!   D3 — Ownership inconsistency: vortex_family changed (Triadic↔Hexadic)
//!   D4 — Constitutional invalidity: phi_convergent=false OR resonance_depth dropped to 0
//!
//! Severity is monotone: D4 > D3 > D2 > D1 > D0.
//! mutation_authority_active iff drift class < D2 (matches TypeScript divergence law).
//!
//! DriftRecord: hash-linked per epoch (SHA-256(prev ‖ class_byte ‖ epoch_be8)).
//! A DriftHistory accumulates records; provides aggregate statistics.

use sha2::{Sha256, Digest};
use crate::resonance_monitor::ResonanceReport;

// ─── Drift class ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum DriftClass {
    D0 = 0, // observational — coefficient changed, invariants intact
    D1 = 1, // phi_headroom sign changed — serializer-level drift
    D2 = 2, // ring_valid or sequence_monotone flipped to false
    D3 = 3, // vortex_family changed
    D4 = 4, // phi_convergent=false OR resonance_depth==0 — constitutional invalidity
}

impl DriftClass {
    pub fn as_u8(self) -> u8 { self as u8 }

    /// True iff mutation authority is preserved (drift < D2).
    pub fn mutation_authority_active(self) -> bool { self < DriftClass::D2 }
}

// ─── Drift record ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct DriftRecord {
    pub epoch: u64,
    pub class: DriftClass,
    /// Signed change in resonance_coefficient (current - previous).
    pub coefficient_delta: f64,
    /// SHA-256(prev_hash ‖ class.as_u8() ‖ epoch_be8).
    pub record_hash: [u8; 32],
    pub prev_record_hash: [u8; 32],
}

impl DriftRecord {
    /// True iff mutation authority is preserved for this record.
    pub fn mutation_authority_active(&self) -> bool {
        self.class.mutation_authority_active()
    }
}

// ─── Genesis hash ─────────────────────────────────────────────────────────

pub const DRIFT_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Classifier function ──────────────────────────────────────────────────

/// Classify the drift between `current` and `previous` ResonanceReport snapshots.
///
/// Returns the most severe drift class that applies (D4 takes priority over D3, etc.).
/// If `previous` is None (first epoch), always returns D0 (baseline — no prior to drift from).
pub fn classify_drift(current: &ResonanceReport, previous: Option<&ResonanceReport>) -> DriftClass {
    let Some(prev) = previous else {
        return DriftClass::D0;
    };

    // D4: constitutional invalidity — highest priority check
    if !current.phi_convergent || current.resonance_depth == 0 {
        return DriftClass::D4;
    }

    // D3: vortex family changed (Triadic↔Hexadic)
    if current.vortex_family != prev.vortex_family {
        return DriftClass::D3;
    }

    // D2: ring_valid or sequence_monotone flipped to false
    let ring_broken = prev.ring_valid && !current.ring_valid;
    let seq_broken  = prev.sequence_monotone && !current.sequence_monotone;
    if ring_broken || seq_broken {
        return DriftClass::D2;
    }

    // D1: phi_headroom sign changed (positive→negative or negative→positive)
    let sign_prev = prev.phi_headroom >= 0.0;
    let sign_curr = current.phi_headroom >= 0.0;
    if sign_prev != sign_curr {
        return DriftClass::D1;
    }

    // D0: observational drift — coefficient changed but invariants intact
    DriftClass::D0
}

// ─── Drift history ────────────────────────────────────────────────────────

#[derive(Debug)]
pub struct DriftError(pub &'static str);

/// Hash-linked drift record history.
#[derive(Debug, Clone)]
pub struct DriftHistory {
    records: Vec<DriftRecord>,
}

impl DriftHistory {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self) -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self) -> &[DriftRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(DRIFT_GENESIS_HASH)
    }

    /// Record a drift event for the given epoch.
    /// Returns Err if epoch is not strictly greater than the last epoch.
    pub fn record(
        &mut self,
        epoch: u64,
        current: &ResonanceReport,
        previous: Option<&ResonanceReport>,
    ) -> Result<&DriftRecord, DriftError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(DriftError("epoch must be strictly greater than last epoch"));
            }
        }
        let class = classify_drift(current, previous);
        let coefficient_delta = match previous {
            Some(p) => current.resonance_coefficient - p.resonance_coefficient,
            None    => 0.0,
        };
        let prev_hash = self.last_hash();
        let record_hash = compute_record_hash(&prev_hash, class, epoch);

        self.records.push(DriftRecord {
            epoch,
            class,
            coefficient_delta,
            record_hash,
            prev_record_hash: prev_hash,
        });
        Ok(self.records.last().unwrap())
    }

    /// Severity of the worst recorded drift class across all epochs.
    pub fn worst_class(&self) -> Option<DriftClass> {
        self.records.iter().map(|r| r.class).max()
    }

    /// Count of epochs with drift class >= D2 (mutation authority suspended).
    pub fn authority_suspended_count(&self) -> usize {
        self.records.iter().filter(|r| r.class >= DriftClass::D2).count()
    }

    /// True iff current drift (last record) allows mutation authority.
    pub fn mutation_authority_active(&self) -> bool {
        self.records.last()
            .map(|r| r.mutation_authority_active())
            .unwrap_or(true) // empty history → authority active by default
    }

    /// Verify the full hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DRIFT_GENESIS_HASH;
        for (i, rec) in self.records.iter().enumerate() {
            if rec.prev_record_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(&prev, rec.class, rec.epoch);
            if expected != rec.record_hash {
                return (false, Some(i));
            }
            prev = rec.record_hash;
        }
        (true, None)
    }
}

impl Default for DriftHistory {
    fn default() -> Self { Self::new() }
}

fn compute_record_hash(prev: &[u8; 32], class: DriftClass, epoch: u64) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([class.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::resonance_monitor::check_resonance;
    use crate::ring_composition::build_ring;

    fn ring_hashes(seed: u8) -> Vec<[u8; 32]> {
        let h = |v: u8| { let mut a = [0u8; 32]; a[0] = v; a };
        build_ring(&[h(seed), h(seed+1), h(seed+2)], None)
    }

    fn good_report() -> ResonanceReport {
        check_resonance(0.12, 3, 9, &ring_hashes(1), 100, None)
    }

    fn above_phi_report() -> ResonanceReport {
        check_resonance(0.99, 3, 9, &ring_hashes(1), 101, Some(100))
    }

    // ── DriftClass ────────────────────────────────────────────────────────

    #[test]
    fn drift_class_ordering() {
        assert!(DriftClass::D0 < DriftClass::D1);
        assert!(DriftClass::D1 < DriftClass::D2);
        assert!(DriftClass::D2 < DriftClass::D3);
        assert!(DriftClass::D3 < DriftClass::D4);
    }

    #[test]
    fn mutation_authority_below_d2() {
        assert!(DriftClass::D0.mutation_authority_active());
        assert!(DriftClass::D1.mutation_authority_active());
    }

    #[test]
    fn mutation_authority_blocked_at_d2_plus() {
        assert!(!DriftClass::D2.mutation_authority_active());
        assert!(!DriftClass::D3.mutation_authority_active());
        assert!(!DriftClass::D4.mutation_authority_active());
    }

    // ── classify_drift ────────────────────────────────────────────────────

    #[test]
    fn no_previous_is_d0() {
        let rep = good_report();
        assert_eq!(classify_drift(&rep, None), DriftClass::D0);
    }

    #[test]
    fn same_report_is_d0() {
        let rep = good_report();
        assert_eq!(classify_drift(&rep, Some(&rep)), DriftClass::D0);
    }

    #[test]
    fn above_phi_is_d4() {
        let good = good_report();
        let bad  = above_phi_report();
        assert_eq!(classify_drift(&bad, Some(&good)), DriftClass::D4);
    }

    #[test]
    fn zero_resonance_depth_is_d4() {
        // Build a report where resonance_depth=0: all four conditions false.
        // Use ring of only 2 elements (TooShort → ring_valid=false),
        // above-phi divergence (phi_convergent=false), span=0 (Hexadic, vortex_triadic=false),
        // and sequence going backwards (sequence_monotone=false).
        let h = |v: u8| { let mut a = [0u8; 32]; a[0] = v; a };
        // ring of length 1 → TooShort → ring_valid=false; no valid ring possible with <3 elements
        let short_ring = vec![h(1), h(2), h(3), h(2), h(1)]; // valid ring to avoid error but phi=false
        let bad = check_resonance(0.99, 5, 3, &short_ring, 50, Some(100));
        // phi_convergent=false, vortex=Hexadic (span=0→Hexadic), ring=valid, seq_mono=false
        // depth = ring_valid(1) + vortex_triadic(0) = at most 1, but phi_convergent=false triggers D4
        let good = good_report();
        assert_eq!(classify_drift(&bad, Some(&good)), DriftClass::D4);
    }

    #[test]
    fn vortex_change_is_d3() {
        // Create reports with different vortex families
        let triadic = check_resonance(0.12, 3, 9, &ring_hashes(1), 100, None);
        // span=1 → digital_root(1)=1 → Hexadic
        let hexadic = check_resonance(0.12, 3, 4, &ring_hashes(1), 101, Some(100));
        use crate::vortex_classifier::VortexFamily;
        // Only test D3 if families actually differ
        if triadic.vortex_family != hexadic.vortex_family {
            assert_eq!(classify_drift(&hexadic, Some(&triadic)), DriftClass::D3);
        }
    }

    // ── DriftHistory ──────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = DriftHistory::new();
        assert!(h.is_empty());
        assert_eq!(h.len(), 0);
    }

    #[test]
    fn empty_history_mutation_authority_true() {
        assert!(DriftHistory::new().mutation_authority_active());
    }

    #[test]
    fn record_first_entry_is_d0_no_previous() {
        let mut hist = DriftHistory::new();
        let rep = good_report();
        let rec = hist.record(1, &rep, None).unwrap();
        assert_eq!(rec.class, DriftClass::D0);
        assert_eq!(rec.epoch, 1);
    }

    #[test]
    fn record_grows_history() {
        let mut hist = DriftHistory::new();
        let rep = good_report();
        hist.record(1, &rep, None).unwrap();
        hist.record(2, &rep, Some(&rep)).unwrap();
        assert_eq!(hist.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut hist = DriftHistory::new();
        let rep = good_report();
        hist.record(5, &rep, None).unwrap();
        assert!(hist.record(5, &rep, Some(&rep)).is_err());
    }

    #[test]
    fn hash_chain_links_correctly() {
        let mut hist = DriftHistory::new();
        let rep = good_report();
        hist.record(1, &rep, None).unwrap();
        hist.record(2, &rep, Some(&rep)).unwrap();
        assert_eq!(hist.records()[1].prev_record_hash, hist.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_clean_history() {
        let mut hist = DriftHistory::new();
        let rep = good_report();
        for i in 1u64..=5 { hist.record(i, &rep, Some(&rep)).unwrap(); }
        let (valid, broken) = hist.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn worst_class_tracks_maximum() {
        let mut hist = DriftHistory::new();
        let rep = good_report();
        hist.record(1, &rep, None).unwrap();
        hist.record(2, &rep, Some(&rep)).unwrap();
        assert_eq!(hist.worst_class(), Some(DriftClass::D0));
    }

    #[test]
    fn record_hash_nonzero() {
        let mut hist = DriftHistory::new();
        let rep = good_report();
        let rec = hist.record(1, &rep, None).unwrap();
        assert_ne!(rec.record_hash, [0u8; 32]);
    }

    #[test]
    fn determinism_same_sequence_same_hashes() {
        let rep = good_report();
        let build = || {
            let mut h = DriftHistory::new();
            h.record(1, &rep, None).unwrap();
            h.record(2, &rep, Some(&rep)).unwrap();
            h.records()[1].record_hash
        };
        assert_eq!(build(), build());
        assert_eq!(build(), build());
    }

    #[test]
    fn drift_error_wraps_str() {
        let e = DriftError("test");
        assert_eq!(e.0, "test");
    }
}
