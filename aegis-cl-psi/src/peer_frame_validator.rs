//! Gate 326 — Peer Frame Validator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Validates a received StateFrame (Gate 325) against the local node's
//! constitutional expectations. Detects divergence between remote claims
//! and local T0 state, classifying each received frame as:
//!
//!   Accepted      — frame valid, remote T0 matches local T0
//!   Degraded      — frame valid, remote T0=true but local=false (or vice versa)
//!   Diverged      — frame valid, remote T0 fundamentally contradicts quorum state
//!   Rejected      — frame checksum invalid (tampered or corrupted wire packet)
//!   EpochStale    — frame epoch older than local epoch by more than MAX_EPOCH_LAG
//!
//! ValidationRecord: hash-chained log entry per validated frame.
//! PeerValidationLog: per-peer append-only chain.
//! ValidationRegistry: BTreeMap<peer_id, PeerValidationLog> — deterministic.
//!   validate(), diverged_peer_count(), quorum_converged(), verify_all().
//!
//! divergence_score: u8 — 0=Accepted, 1=Degraded, 2=Diverged, 3=Rejected, 4=EpochStale
//! Quorum convergence: fraction of peers with latest verdict=Accepted ≥ 1/φ.

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;
use crate::state_broadcaster::StateFrame;

pub const VALIDATION_GENESIS_HASH:   [u8; 32] = [0u8; 32];
pub const MAX_EPOCH_LAG:             u64       = 5;

// ─── ValidationVerdict ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ValidationVerdict {
    Accepted   = 0, // frame valid, T0 consistent with local state
    Degraded   = 1, // frame valid, T0 mismatch but below divergence threshold
    Diverged   = 2, // frame valid, T0 contradicts quorum
    Rejected   = 3, // checksum invalid
    EpochStale = 4, // epoch too old
}

impl ValidationVerdict {
    pub fn score(self) -> u8 { self as u8 }
    pub fn is_healthy(self) -> bool { self == ValidationVerdict::Accepted }
}

// ─── ValidationRecord ─────────────────────────────────────────────────────────

/// One hash-chained validation record for one received frame from one peer.
#[derive(Debug, Clone, PartialEq)]
pub struct ValidationRecord {
    pub peer_id:       u64,
    pub epoch:         u64,
    pub verdict:       ValidationVerdict,
    pub remote_t0:     bool,
    pub local_t0:      bool,
    pub record_hash:   [u8; 32],
    pub prev_hash:     [u8; 32],
}

// ─── Local context ────────────────────────────────────────────────────────────

/// The local node's current constitutional state for comparison.
#[derive(Debug, Clone, Copy)]
pub struct LocalContext {
    pub local_epoch:  u64,
    pub local_t0:     bool,
    pub local_quorum: bool,
}

// ─── Hash ─────────────────────────────────────────────────────────────────────

fn compute_record_hash(
    prev:      &[u8; 32],
    peer_id:   u64,
    epoch:     u64,
    verdict:   ValidationVerdict,
    remote_t0: bool,
    local_t0:  bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([verdict.score()]);
    h.update([remote_t0 as u8]);
    h.update([local_t0 as u8]);
    h.finalize().into()
}

// ─── Classify ─────────────────────────────────────────────────────────────────

/// Classify one received frame against local context.
///
/// Decision tree (first match wins):
///   1. Checksum invalid                         → Rejected
///   2. frame.epoch + MAX_EPOCH_LAG < local_epoch → EpochStale
///   3. remote T0 == local T0                     → Accepted
///   4. local_quorum == true AND remote T0 == false → Diverged (remote disagrees with quorum)
///   5. Otherwise                                 → Degraded
pub fn classify_frame(frame: &StateFrame, ctx: &LocalContext) -> ValidationVerdict {
    if !frame.verify_checksum() {
        return ValidationVerdict::Rejected;
    }
    if frame.epoch.saturating_add(MAX_EPOCH_LAG) < ctx.local_epoch {
        return ValidationVerdict::EpochStale;
    }
    let remote_t0 = frame.t0_consensus();
    if remote_t0 == ctx.local_t0 {
        return ValidationVerdict::Accepted;
    }
    // T0 mismatch
    if ctx.local_quorum && !remote_t0 {
        ValidationVerdict::Diverged   // local quorum disagrees with remote
    } else {
        ValidationVerdict::Degraded   // informational mismatch, below quorum certainty
    }
}

// ─── PeerValidationLog ────────────────────────────────────────────────────────

/// Append-only hash-chained validation log for one peer.
pub struct PeerValidationLog {
    peer_id: u64,
    records: Vec<ValidationRecord>,
}

impl PeerValidationLog {
    pub fn new(peer_id: u64) -> Self {
        Self { peer_id, records: Vec::new() }
    }

    pub fn peer_id(&self)   -> u64   { self.peer_id }
    pub fn len(&self)       -> usize { self.records.len() }
    pub fn is_empty(&self)  -> bool  { self.records.is_empty() }
    pub fn records(&self)   -> &[ValidationRecord] { &self.records }

    /// Append a validation result, chaining from the previous record.
    pub fn append(
        &mut self,
        frame:   &StateFrame,
        ctx:     &LocalContext,
        verdict: ValidationVerdict,
    ) -> ValidationRecord {
        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(VALIDATION_GENESIS_HASH);

        let remote_t0 = frame.t0_consensus();
        let record_hash = compute_record_hash(
            &prev, self.peer_id, frame.epoch, verdict, remote_t0, ctx.local_t0,
        );

        let rec = ValidationRecord {
            peer_id:   self.peer_id,
            epoch:     frame.epoch,
            verdict,
            remote_t0,
            local_t0:  ctx.local_t0,
            record_hash,
            prev_hash: prev,
        };
        self.records.push(rec.clone());
        rec
    }

    /// Latest validation verdict for this peer, or `None` if empty.
    pub fn latest_verdict(&self) -> Option<ValidationVerdict> {
        self.records.last().map(|r| r.verdict)
    }

    /// Count of records where verdict == Diverged or Rejected.
    pub fn fault_count(&self) -> usize {
        self.records.iter()
            .filter(|r| r.verdict == ValidationVerdict::Diverged || r.verdict == ValidationVerdict::Rejected)
            .count()
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = VALIDATION_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(
                &prev, r.peer_id, r.epoch, r.verdict, r.remote_t0, r.local_t0,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── ValidationRegistry ───────────────────────────────────────────────────────

/// BTreeMap-keyed per-peer validation log registry.
pub struct ValidationRegistry {
    logs: BTreeMap<u64, PeerValidationLog>,
}

impl ValidationRegistry {
    pub fn new() -> Self { Self { logs: BTreeMap::new() } }

    pub fn peer_count(&self) -> usize { self.logs.len() }

    /// Validate a received frame from a specific peer.
    pub fn validate(&mut self, peer_id: u64, frame: &StateFrame, ctx: &LocalContext) -> ValidationRecord {
        let verdict = classify_frame(frame, ctx);
        let log = self.logs
            .entry(peer_id)
            .or_insert_with(|| PeerValidationLog::new(peer_id));
        log.append(frame, ctx, verdict)
    }

    /// Count of peers whose latest verdict is Diverged or Rejected.
    pub fn diverged_peer_count(&self) -> usize {
        self.logs.values()
            .filter(|l| matches!(l.latest_verdict(), Some(v) if v >= ValidationVerdict::Diverged))
            .count()
    }

    /// `true` iff fraction of peers with Accepted latest verdict ≥ 1/φ.
    /// Integer arithmetic: accepted * 1_000_000 >= total * 618_034.
    pub fn quorum_converged(&self) -> bool {
        let total = self.logs.len();
        if total == 0 { return false; }
        let accepted = self.logs.values()
            .filter(|l| l.latest_verdict() == Some(ValidationVerdict::Accepted))
            .count();
        accepted * 1_000_000 >= total * 618_034
    }

    /// Verify chain integrity for all peer logs.
    /// Returns `(true, BTreeMap::new())` when all valid.
    pub fn verify_all(&self) -> (bool, BTreeMap<u64, usize>) {
        let mut failures: BTreeMap<u64, usize> = BTreeMap::new();
        for (&peer_id, log) in &self.logs {
            let (ok, idx) = log.verify_chain();
            if !ok { failures.insert(peer_id, idx.unwrap_or(0)); }
        }
        (failures.is_empty(), failures)
    }

    /// Get the log for a specific peer.
    pub fn log_for(&self, peer_id: u64) -> Option<&PeerValidationLog> {
        self.logs.get(&peer_id)
    }
}

impl Default for ValidationRegistry {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state_broadcaster::StateFrame;

    fn dummy_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = seed; h[31] = seed.wrapping_mul(5);
        h
    }

    fn valid_frame(epoch: u64, t0: bool, quorum: bool) -> StateFrame {
        StateFrame::encode(epoch, &dummy_hash(1), &dummy_hash(2), &dummy_hash(3), t0, quorum)
    }

    fn ctx(epoch: u64, t0: bool, quorum: bool) -> LocalContext {
        LocalContext { local_epoch: epoch, local_t0: t0, local_quorum: quorum }
    }

    // ── classify_frame ────────────────────────────────────────────────────────

    #[test]
    fn accepted_when_t0_matches() {
        let f = valid_frame(5, true, true);
        let v = classify_frame(&f, &ctx(5, true, true));
        assert_eq!(v, ValidationVerdict::Accepted);
    }

    #[test]
    fn accepted_both_false() {
        let f = valid_frame(5, false, false);
        let v = classify_frame(&f, &ctx(5, false, false));
        assert_eq!(v, ValidationVerdict::Accepted);
    }

    #[test]
    fn rejected_on_bad_checksum() {
        let f = valid_frame(5, true, true);
        let mut bytes = f.to_bytes();
        bytes[33] ^= 0xFF; // corrupt checksum
        // Manually build a frame with bad checksum to test classify_frame
        // We can't use from_bytes (it validates), so construct manually:
        // Instead test via a tampered frame struct
        let mut bad = f.clone();
        bad.checksum[0] ^= 0xFF;
        let v = classify_frame(&bad, &ctx(5, true, true));
        assert_eq!(v, ValidationVerdict::Rejected);
    }

    #[test]
    fn epoch_stale_beyond_max_lag() {
        // local_epoch = 10, frame.epoch = 4 → 4 + 5 = 9 < 10 → EpochStale
        let f = valid_frame(4, true, true);
        let v = classify_frame(&f, &ctx(10, true, true));
        assert_eq!(v, ValidationVerdict::EpochStale);
    }

    #[test]
    fn epoch_at_boundary_not_stale() {
        // local_epoch = 10, frame.epoch = 5 → 5 + 5 = 10 = 10 → NOT stale
        let f = valid_frame(5, true, true);
        let v = classify_frame(&f, &ctx(10, true, true));
        assert_eq!(v, ValidationVerdict::Accepted);
    }

    #[test]
    fn diverged_when_local_quorum_remote_false() {
        // local has quorum=true, local_t0=true; remote claims t0=false → Diverged
        let f = valid_frame(5, false, false);
        let v = classify_frame(&f, &ctx(5, true, true));
        assert_eq!(v, ValidationVerdict::Diverged);
    }

    #[test]
    fn degraded_when_no_quorum_t0_mismatch() {
        // local quorum=false, remote T0=true, local T0=false → Degraded
        let f = valid_frame(5, true, true);
        let v = classify_frame(&f, &ctx(5, false, false));
        assert_eq!(v, ValidationVerdict::Degraded);
    }

    // ── ValidationVerdict ordering ────────────────────────────────────────────

    #[test]
    fn verdict_scores_ordered() {
        assert!(ValidationVerdict::Accepted.score()   < ValidationVerdict::Degraded.score());
        assert!(ValidationVerdict::Degraded.score()   < ValidationVerdict::Diverged.score());
        assert!(ValidationVerdict::Diverged.score()   < ValidationVerdict::Rejected.score());
        assert!(ValidationVerdict::Rejected.score()   < ValidationVerdict::EpochStale.score());
    }

    #[test]
    fn only_accepted_is_healthy() {
        assert!(ValidationVerdict::Accepted.is_healthy());
        assert!(!ValidationVerdict::Degraded.is_healthy());
        assert!(!ValidationVerdict::Diverged.is_healthy());
        assert!(!ValidationVerdict::Rejected.is_healthy());
    }

    // ── PeerValidationLog ─────────────────────────────────────────────────────

    #[test]
    fn fresh_log_empty() {
        let l = PeerValidationLog::new(7);
        assert!(l.is_empty());
        assert!(l.latest_verdict().is_none());
    }

    #[test]
    fn append_chains_records() {
        let mut l = PeerValidationLog::new(1);
        let f = valid_frame(1, true, true);
        let c = ctx(1, true, true);
        let r1 = l.append(&f, &c, ValidationVerdict::Accepted);
        let f2 = valid_frame(2, true, true);
        let r2 = l.append(&f2, &c, ValidationVerdict::Accepted);
        assert_eq!(r2.prev_hash, r1.record_hash);
    }

    #[test]
    fn fault_count_only_diverged_and_rejected() {
        let mut l = PeerValidationLog::new(1);
        let f = valid_frame(1, true, true);
        let c = ctx(1, true, true);
        l.append(&f, &c, ValidationVerdict::Accepted);
        l.append(&f, &c, ValidationVerdict::Diverged);
        l.append(&f, &c, ValidationVerdict::Rejected);
        l.append(&f, &c, ValidationVerdict::Degraded);
        assert_eq!(l.fault_count(), 2);
    }

    #[test]
    fn verify_chain_ok() {
        let mut l = PeerValidationLog::new(1);
        let c = ctx(5, true, true);
        for epoch in 1..=4u64 {
            let f = valid_frame(epoch, true, true);
            l.append(&f, &c, ValidationVerdict::Accepted);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered_verdict() {
        let mut l = PeerValidationLog::new(1);
        let f = valid_frame(1, true, true);
        let c = ctx(1, true, true);
        l.append(&f, &c, ValidationVerdict::Accepted);
        l.records[0].verdict = ValidationVerdict::Diverged;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── ValidationRegistry ────────────────────────────────────────────────────

    #[test]
    fn fresh_registry_empty() {
        let r = ValidationRegistry::new();
        assert_eq!(r.peer_count(), 0);
        assert!(!r.quorum_converged());
    }

    #[test]
    fn validate_creates_log() {
        let mut r = ValidationRegistry::new();
        let f = valid_frame(1, true, true);
        let c = ctx(1, true, true);
        r.validate(42, &f, &c);
        assert_eq!(r.peer_count(), 1);
        assert!(r.log_for(42).is_some());
    }

    #[test]
    fn quorum_converged_five_of_eight() {
        let mut r = ValidationRegistry::new();
        let c = ctx(1, true, true);
        for id in 1..=5u64 {
            r.validate(id, &valid_frame(1, true, true), &c); // Accepted
        }
        for id in 6..=8u64 {
            r.validate(id, &valid_frame(1, false, false), &c); // Diverged
        }
        // 5/8 = 0.625 >= 0.618034 → quorum_converged
        assert!(r.quorum_converged());
    }

    #[test]
    fn quorum_not_converged_four_of_eight() {
        let mut r = ValidationRegistry::new();
        let c = ctx(1, true, true);
        for id in 1..=4u64 {
            r.validate(id, &valid_frame(1, true, true), &c); // Accepted
        }
        for id in 5..=8u64 {
            r.validate(id, &valid_frame(1, false, false), &c); // Diverged
        }
        // 4/8 = 0.500 < 0.618034 → not converged
        assert!(!r.quorum_converged());
    }

    #[test]
    fn diverged_peer_count() {
        let mut r = ValidationRegistry::new();
        let c = ctx(1, true, true);
        r.validate(1, &valid_frame(1, true, true), &c);   // Accepted
        r.validate(2, &valid_frame(1, false, false), &c); // Diverged
        r.validate(3, &valid_frame(1, true, true), &c);   // Accepted
        assert_eq!(r.diverged_peer_count(), 1);
    }

    #[test]
    fn verify_all_clean() {
        let mut r = ValidationRegistry::new();
        let c = ctx(5, true, true);
        r.validate(1, &valid_frame(5, true, true), &c);
        r.validate(2, &valid_frame(5, true, true), &c);
        let (ok, failures) = r.verify_all();
        assert!(ok);
        assert!(failures.is_empty());
    }

    #[test]
    fn determinism_same_frame_three_times() {
        let f = valid_frame(7, true, true);
        let c = ctx(7, true, true);
        let mut l1 = PeerValidationLog::new(1); let r1 = l1.append(&f, &c, ValidationVerdict::Accepted);
        let mut l2 = PeerValidationLog::new(1); let r2 = l2.append(&f, &c, ValidationVerdict::Accepted);
        let mut l3 = PeerValidationLog::new(1); let r3 = l3.append(&f, &c, ValidationVerdict::Accepted);
        assert_eq!(r1.record_hash, r2.record_hash);
        assert_eq!(r2.record_hash, r3.record_hash);
    }
}
