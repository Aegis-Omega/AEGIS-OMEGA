//! Gate 287 — Gossip Epoch Auditor: cross-module epoch consistency verification (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! At each epoch close, audits the consistency of gossip subsystem states.
//! Checks that multiple subsystem epoch values agree and detects anomalies.
//!
//! AuditInput:
//!   epoch              — u64 (the epoch being audited)
//!   supervisor_epoch   — u64 (last sealed by MeshSupervisionLog)
//!   finalizer_epoch    — u64 (last sealed by GossipEpochChain)
//!   scheduler_epoch    — u64 (last interval in GossipSchedule)
//!   prober_max_epoch   — u64 (highest epoch in ProbeMatrix)
//!   bandwidth_epoch    — u64 (last sealed by BandwidthRegistry)
//!
//! AuditFinding:
//!   Consistent         — all subsystem epochs == audit epoch
//!   Lagging { subsystem: &'static str, by: u64 } — one subsystem is behind
//!   Leading { subsystem: &'static str, by: u64 } — one subsystem is ahead
//!   Diverged { subsystem: &'static str }          — epoch mismatch > MAX_LAG_ALLOWED (3)
//!
//! EpochAuditRecord:
//!   epoch            — u64
//!   finding          — AuditFinding
//!   consistent_count — u8 (number of subsystems that match audit epoch)
//!   total_checked    — u8 (total subsystems checked)
//!   audit_hash       — SHA-256(prev ‖ epoch_be8 ‖ finding_byte ‖ consistent ‖ total)
//!   prev_hash        — [u8; 32]
//!
//! EpochAuditLog: hash-chained EpochAuditRecords.
//!   record(), consistent_epoch_count(), diverged_epoch_count(), verify_chain().

use sha2::{Sha256, Digest};

pub const MAX_LAG_ALLOWED: u64 = 3;
pub const SUBSYSTEM_COUNT: u8  = 5;  // supervisor, finalizer, scheduler, prober, bandwidth

// ─── Audit input ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy)]
pub struct AuditInput {
    pub epoch:            u64,
    pub supervisor_epoch: u64,
    pub finalizer_epoch:  u64,
    pub scheduler_epoch:  u64,
    pub prober_max_epoch: u64,
    pub bandwidth_epoch:  u64,
}

// ─── Audit finding ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuditFinding {
    Consistent,
    Lagging   { subsystem: &'static str, by: u64 },
    Leading   { subsystem: &'static str, by: u64 },
    Diverged  { subsystem: &'static str },
}

impl AuditFinding {
    pub fn finding_byte(self) -> u8 {
        match self {
            Self::Consistent     => 0,
            Self::Lagging  { .. } => 1,
            Self::Leading  { .. } => 2,
            Self::Diverged { .. } => 3,
        }
    }

    pub fn is_healthy(self) -> bool { matches!(self, Self::Consistent) }
}

/// Audit a set of subsystem epochs against the expected audit epoch.
/// Returns the finding for the first anomaly found, or Consistent.
/// Subsystems checked in order: supervisor, finalizer, scheduler, prober, bandwidth.
pub fn audit_epoch(input: AuditInput) -> (AuditFinding, u8) {
    let epoch = input.epoch;
    let subsystems: &[(&'static str, u64)] = &[
        ("supervisor", input.supervisor_epoch),
        ("finalizer",  input.finalizer_epoch),
        ("scheduler",  input.scheduler_epoch),
        ("prober",     input.prober_max_epoch),
        ("bandwidth",  input.bandwidth_epoch),
    ];

    let mut consistent = 0u8;
    let mut first_anomaly: Option<AuditFinding> = None;

    for &(name, subsys_epoch) in subsystems {
        if subsys_epoch == epoch {
            consistent += 1;
        } else if first_anomaly.is_none() {
            first_anomaly = Some(if subsys_epoch < epoch {
                let lag = epoch - subsys_epoch;
                if lag > MAX_LAG_ALLOWED {
                    AuditFinding::Diverged { subsystem: name }
                } else {
                    AuditFinding::Lagging { subsystem: name, by: lag }
                }
            } else {
                let lead = subsys_epoch - epoch;
                AuditFinding::Leading { subsystem: name, by: lead }
            });
        }
    }

    let finding = first_anomaly.unwrap_or(AuditFinding::Consistent);
    (finding, consistent)
}

// ─── Epoch audit record ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct EpochAuditRecord {
    pub epoch:            u64,
    pub finding:          AuditFinding,
    pub consistent_count: u8,
    pub total_checked:    u8,
    pub audit_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

pub const AUDIT_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_audit_hash(
    epoch:            u64,
    finding:          AuditFinding,
    consistent_count: u8,
    total_checked:    u8,
    prev:             &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([finding.finding_byte(), consistent_count, total_checked]);
    h.finalize().into()
}

pub fn build_audit_record(
    epoch:            u64,
    finding:          AuditFinding,
    consistent_count: u8,
    total_checked:    u8,
    prev_hash:        &[u8; 32],
) -> EpochAuditRecord {
    let audit_hash = compute_audit_hash(
        epoch, finding, consistent_count, total_checked, prev_hash,
    );
    EpochAuditRecord {
        epoch, finding, consistent_count, total_checked,
        audit_hash, prev_hash: *prev_hash,
    }
}

// ─── Epoch audit log ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct EpochAuditLog {
    records: Vec<EpochAuditRecord>,
}

#[derive(Debug)]
pub enum AuditError {
    StaleEpoch,
}

impl EpochAuditLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[EpochAuditRecord] { &self.records }
    pub fn latest(&self)   -> Option<&EpochAuditRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.audit_hash).unwrap_or(AUDIT_GENESIS_HASH)
    }

    pub fn record(&mut self, input: AuditInput) -> Result<&EpochAuditRecord, AuditError> {
        if let Some(last) = self.records.last() {
            if input.epoch <= last.epoch {
                return Err(AuditError::StaleEpoch);
            }
        }
        let (finding, consistent_count) = audit_epoch(input);
        let prev = self.last_hash();
        let r = build_audit_record(
            input.epoch, finding, consistent_count, SUBSYSTEM_COUNT, &prev,
        );
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn consistent_epoch_count(&self) -> usize {
        self.records.iter().filter(|r| r.finding.is_healthy()).count()
    }

    pub fn diverged_epoch_count(&self) -> usize {
        self.records.iter().filter(|r| matches!(r.finding, AuditFinding::Diverged { .. })).count()
    }

    pub fn anomaly_epoch_count(&self) -> usize {
        self.records.iter().filter(|r| !r.finding.is_healthy()).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = AUDIT_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_audit_hash(
                r.epoch, r.finding, r.consistent_count, r.total_checked, &r.prev_hash,
            );
            if recomputed != r.audit_hash { return (false, Some(i)); }
            expected_prev = r.audit_hash;
        }
        (true, None)
    }
}

impl Default for EpochAuditLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn consistent_input(epoch: u64) -> AuditInput {
        AuditInput {
            epoch,
            supervisor_epoch: epoch,
            finalizer_epoch:  epoch,
            scheduler_epoch:  epoch,
            prober_max_epoch: epoch,
            bandwidth_epoch:  epoch,
        }
    }

    fn lagging_input(epoch: u64, by: u64) -> AuditInput {
        AuditInput {
            epoch,
            supervisor_epoch: epoch - by,  // supervisor is behind
            finalizer_epoch:  epoch,
            scheduler_epoch:  epoch,
            prober_max_epoch: epoch,
            bandwidth_epoch:  epoch,
        }
    }

    // ── audit_epoch ────────────────────────────────────────────────────────────

    #[test]
    fn all_consistent() {
        let (finding, consistent) = audit_epoch(consistent_input(10));
        assert_eq!(finding, AuditFinding::Consistent);
        assert_eq!(consistent, 5);
    }

    #[test]
    fn lagging_by_1_detected() {
        let (finding, consistent) = audit_epoch(lagging_input(10, 1));
        assert_eq!(finding, AuditFinding::Lagging { subsystem: "supervisor", by: 1 });
        assert_eq!(consistent, 4);
    }

    #[test]
    fn lagging_by_3_still_lagging() {
        let (finding, _) = audit_epoch(lagging_input(10, 3));
        assert_eq!(finding, AuditFinding::Lagging { subsystem: "supervisor", by: 3 });
    }

    #[test]
    fn lagging_by_4_is_diverged() {
        let (finding, _) = audit_epoch(lagging_input(10, 4));
        assert_eq!(finding, AuditFinding::Diverged { subsystem: "supervisor" });
    }

    #[test]
    fn leading_subsystem_detected() {
        let input = AuditInput {
            epoch: 5,
            supervisor_epoch: 7,  // leading by 2
            finalizer_epoch:  5,
            scheduler_epoch:  5,
            prober_max_epoch: 5,
            bandwidth_epoch:  5,
        };
        let (finding, _) = audit_epoch(input);
        assert_eq!(finding, AuditFinding::Leading { subsystem: "supervisor", by: 2 });
    }

    #[test]
    fn finding_health() {
        assert!(AuditFinding::Consistent.is_healthy());
        assert!(!AuditFinding::Lagging { subsystem: "x", by: 1 }.is_healthy());
        assert!(!AuditFinding::Diverged { subsystem: "x" }.is_healthy());
    }

    #[test]
    fn finding_bytes() {
        assert_eq!(AuditFinding::Consistent.finding_byte(), 0);
        assert_eq!(AuditFinding::Lagging { subsystem: "x", by: 1 }.finding_byte(), 1);
        assert_eq!(AuditFinding::Leading { subsystem: "x", by: 1 }.finding_byte(), 2);
        assert_eq!(AuditFinding::Diverged { subsystem: "x" }.finding_byte(), 3);
    }

    // ── build_audit_record ────────────────────────────────────────────────────

    #[test]
    fn audit_hash_nonzero() {
        let r = build_audit_record(1, AuditFinding::Consistent, 5, 5, &AUDIT_GENESIS_HASH);
        assert_ne!(r.audit_hash, [0u8; 32]);
    }

    #[test]
    fn audit_hash_deterministic() {
        let r1 = build_audit_record(1, AuditFinding::Consistent, 5, 5, &AUDIT_GENESIS_HASH);
        let r2 = build_audit_record(1, AuditFinding::Consistent, 5, 5, &AUDIT_GENESIS_HASH);
        assert_eq!(r1.audit_hash, r2.audit_hash);
    }

    // ── EpochAuditLog ─────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = EpochAuditLog::new();
        assert!(l.is_empty());
        assert_eq!(l.consistent_epoch_count(), 0);
        assert_eq!(l.anomaly_epoch_count(), 0);
    }

    #[test]
    fn record_and_count() {
        let mut l = EpochAuditLog::new();
        l.record(consistent_input(1)).unwrap();
        l.record(lagging_input(2, 1)).unwrap();
        l.record(consistent_input(3)).unwrap();
        assert_eq!(l.consistent_epoch_count(), 2);
        assert_eq!(l.anomaly_epoch_count(), 1);
    }

    #[test]
    fn diverged_count() {
        let mut l = EpochAuditLog::new();
        l.record(lagging_input(10, 5)).unwrap(); // diverged
        assert_eq!(l.diverged_epoch_count(), 1);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = EpochAuditLog::new();
        l.record(consistent_input(5)).unwrap();
        assert!(matches!(l.record(consistent_input(4)), Err(AuditError::StaleEpoch)));
    }

    #[test]
    fn hash_chain_links() {
        let mut l = EpochAuditLog::new();
        l.record(consistent_input(1)).unwrap();
        l.record(consistent_input(2)).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].audit_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = EpochAuditLog::new();
        for e in 1..=6u64 {
            l.record(consistent_input(e)).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
