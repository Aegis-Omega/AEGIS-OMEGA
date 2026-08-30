//! Gate 260 — Epoch Synchronizer: cross-peer epoch alignment + lag detection (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Compares the local epoch against peer epochs from beacon data to detect lag.
//! Produces a SyncRecord describing alignment status and recommending action.
//!
//! SyncRecord:
//!   local_epoch      — u64 (this node's current epoch)
//!   max_peer_epoch   — u64 (highest epoch seen in peer set)
//!   min_peer_epoch   — u64 (lowest epoch seen in peer set)
//!   peer_count       — usize
//!   lag              — u64 = max_peer_epoch.saturating_sub(local_epoch)
//!   lead             — u64 = local_epoch.saturating_sub(max_peer_epoch)
//!   alignment        — EpochAlignment
//!   sync_hash        — SHA-256(local_epoch_be8 ‖ max_peer_be8 ‖ peer_count_be8 ‖ prev_hash)
//!
//! EpochAlignment:
//!   Synchronized     — lag == 0 && lead == 0
//!   LocalLagging     — lag > 0 (peers ahead)
//!   LocalLeading     — lead > 0 (local ahead of all peers)
//!   NoPeers          — peer_count == 0
//!
//! SyncLog: hash-chained SyncRecords; one per epoch check cycle.

use sha2::{Sha256, Digest};

// ─── Epoch alignment ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EpochAlignment {
    Synchronized = 0,
    LocalLagging = 1,
    LocalLeading = 2,
    NoPeers      = 3,
}

impl EpochAlignment {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Synchronized => "synchronized",
            Self::LocalLagging => "local lagging",
            Self::LocalLeading => "local leading",
            Self::NoPeers      => "no peers",
        }
    }

    pub fn is_synchronized(self) -> bool { self == Self::Synchronized }
    pub fn needs_catchup(self) -> bool   { self == Self::LocalLagging }
}

// ─── Sync record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SyncRecord {
    pub local_epoch:    u64,
    pub max_peer_epoch: u64,
    pub min_peer_epoch: u64,
    pub peer_count:     usize,
    pub lag:            u64,
    pub lead:           u64,
    pub alignment:      EpochAlignment,
    pub sync_hash:      [u8; 32],
    pub prev_hash:      [u8; 32],
}

impl SyncRecord {
    /// Epoch spread across peers (max - min). 0 if fewer than 2 peers.
    pub fn peer_spread(&self) -> u64 {
        self.max_peer_epoch.saturating_sub(self.min_peer_epoch)
    }
}

pub const SYNC_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_sync_hash(
    local_epoch:    u64,
    max_peer_epoch: u64,
    peer_count:     usize,
    prev_hash:      &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev_hash);
    h.update(local_epoch.to_be_bytes());
    h.update(max_peer_epoch.to_be_bytes());
    h.update((peer_count as u64).to_be_bytes());
    h.finalize().into()
}

fn classify_alignment(
    local_epoch:    u64,
    max_peer_epoch: u64,
    peer_count:     usize,
) -> (EpochAlignment, u64, u64) {
    if peer_count == 0 {
        return (EpochAlignment::NoPeers, 0, 0);
    }
    let lag  = max_peer_epoch.saturating_sub(local_epoch);
    let lead = local_epoch.saturating_sub(max_peer_epoch);
    let alignment = if lag > 0 {
        EpochAlignment::LocalLagging
    } else if lead > 0 {
        EpochAlignment::LocalLeading
    } else {
        EpochAlignment::Synchronized
    };
    (alignment, lag, lead)
}

// ─── Build sync record ────────────────────────────────────────────────────────

/// Build a SyncRecord from local epoch and a slice of peer epochs.
/// peer_epochs may be empty (produces NoPeers alignment).
pub fn build_sync_record(
    local_epoch:  u64,
    peer_epochs:  &[u64],
    prev_hash:    &[u8; 32],
) -> SyncRecord {
    let peer_count     = peer_epochs.len();
    let max_peer_epoch = peer_epochs.iter().copied().max().unwrap_or(0);
    let min_peer_epoch = peer_epochs.iter().copied().min().unwrap_or(0);

    let (alignment, lag, lead) = classify_alignment(local_epoch, max_peer_epoch, peer_count);
    let sync_hash = compute_sync_hash(local_epoch, max_peer_epoch, peer_count, prev_hash);

    SyncRecord {
        local_epoch,
        max_peer_epoch,
        min_peer_epoch,
        peer_count,
        lag,
        lead,
        alignment,
        sync_hash,
        prev_hash: *prev_hash,
    }
}

// ─── Sync log ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SyncLog {
    records: Vec<SyncRecord>,
}

#[derive(Debug)]
pub enum SyncError {
    StaleEpoch,
}

impl SyncError {
    pub fn as_str(&self) -> &'static str { "stale epoch" }
}

impl SyncLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self) -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self) -> &[SyncRecord] { &self.records }
    pub fn latest(&self) -> Option<&SyncRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last()
            .map(|r| r.sync_hash)
            .unwrap_or(SYNC_GENESIS_HASH)
    }

    /// Record a sync observation. local_epoch must be >= previous local_epoch.
    pub fn record(
        &mut self,
        local_epoch: u64,
        peer_epochs: &[u64],
    ) -> Result<&SyncRecord, SyncError> {
        if let Some(last) = self.records.last() {
            if local_epoch < last.local_epoch {
                return Err(SyncError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let rec = build_sync_record(local_epoch, peer_epochs, &prev_hash);
        self.records.push(rec);
        Ok(self.records.last().unwrap())
    }

    /// Count of records where alignment was LocalLagging.
    pub fn lag_count(&self) -> usize {
        self.records.iter().filter(|r| r.alignment.needs_catchup()).count()
    }

    /// Count of records where alignment was Synchronized.
    pub fn synchronized_count(&self) -> usize {
        self.records.iter().filter(|r| r.alignment.is_synchronized()).count()
    }

    /// Maximum lag observed across all records.
    pub fn max_lag(&self) -> u64 {
        self.records.iter().map(|r| r.lag).max().unwrap_or(0)
    }

    /// Verify hash chain.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SYNC_GENESIS_HASH;
        for (i, rec) in self.records.iter().enumerate() {
            if rec.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_sync_hash(
                rec.local_epoch, rec.max_peer_epoch, rec.peer_count, &rec.prev_hash);
            if recomputed != rec.sync_hash {
                return (false, Some(i));
            }
            expected_prev = rec.sync_hash;
        }
        (true, None)
    }
}

impl Default for SyncLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── EpochAlignment ───────────────────────────────────────────────────────

    #[test]
    fn alignment_as_str() {
        assert_eq!(EpochAlignment::Synchronized.as_str(), "synchronized");
        assert_eq!(EpochAlignment::LocalLagging.as_str(), "local lagging");
        assert_eq!(EpochAlignment::LocalLeading.as_str(), "local leading");
        assert_eq!(EpochAlignment::NoPeers.as_str(),      "no peers");
    }

    #[test]
    fn alignment_flags() {
        assert!(EpochAlignment::Synchronized.is_synchronized());
        assert!(!EpochAlignment::LocalLagging.is_synchronized());
        assert!(EpochAlignment::LocalLagging.needs_catchup());
        assert!(!EpochAlignment::Synchronized.needs_catchup());
    }

    // ── build_sync_record ────────────────────────────────────────────────────

    #[test]
    fn no_peers_gives_no_peers_alignment() {
        let r = build_sync_record(5, &[], &SYNC_GENESIS_HASH);
        assert_eq!(r.alignment, EpochAlignment::NoPeers);
        assert_eq!(r.peer_count, 0);
        assert_eq!(r.lag, 0);
        assert_eq!(r.lead, 0);
    }

    #[test]
    fn synchronized_when_equal() {
        let r = build_sync_record(5, &[5, 5, 5], &SYNC_GENESIS_HASH);
        assert_eq!(r.alignment, EpochAlignment::Synchronized);
        assert_eq!(r.lag, 0);
        assert_eq!(r.lead, 0);
    }

    #[test]
    fn local_lagging_when_behind() {
        let r = build_sync_record(3, &[5, 6, 7], &SYNC_GENESIS_HASH);
        assert_eq!(r.alignment, EpochAlignment::LocalLagging);
        assert_eq!(r.lag, 4); // 7 - 3
        assert_eq!(r.lead, 0);
    }

    #[test]
    fn local_leading_when_ahead() {
        let r = build_sync_record(10, &[7, 8], &SYNC_GENESIS_HASH);
        assert_eq!(r.alignment, EpochAlignment::LocalLeading);
        assert_eq!(r.lead, 2); // 10 - 8
        assert_eq!(r.lag, 0);
    }

    #[test]
    fn max_min_peer_epoch_correct() {
        let r = build_sync_record(5, &[3, 7, 5], &SYNC_GENESIS_HASH);
        assert_eq!(r.max_peer_epoch, 7);
        assert_eq!(r.min_peer_epoch, 3);
        assert_eq!(r.peer_spread(), 4);
    }

    #[test]
    fn sync_hash_nonzero() {
        let r = build_sync_record(1, &[1], &SYNC_GENESIS_HASH);
        assert_ne!(r.sync_hash, [0u8; 32]);
    }

    #[test]
    fn sync_hash_deterministic() {
        let r1 = build_sync_record(5, &[5, 6], &SYNC_GENESIS_HASH);
        let r2 = build_sync_record(5, &[5, 6], &SYNC_GENESIS_HASH);
        let r3 = build_sync_record(5, &[5, 6], &SYNC_GENESIS_HASH);
        assert_eq!(r1.sync_hash, r2.sync_hash);
        assert_eq!(r2.sync_hash, r3.sync_hash);
    }

    // ── SyncLog ──────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = SyncLog::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), SYNC_GENESIS_HASH);
        assert_eq!(l.max_lag(), 0);
    }

    #[test]
    fn record_valid_sync() {
        let mut l = SyncLog::new();
        l.record(1, &[1, 1]).unwrap();
        assert_eq!(l.len(), 1);
        assert_eq!(l.synchronized_count(), 1);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = SyncLog::new();
        l.record(5, &[5]).unwrap();
        assert!(matches!(l.record(4, &[4]), Err(SyncError::StaleEpoch)));
    }

    #[test]
    fn same_epoch_allowed() {
        // local_epoch may stay same between checks
        let mut l = SyncLog::new();
        l.record(5, &[5]).unwrap();
        l.record(5, &[5]).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn lag_count_tracked() {
        let mut l = SyncLog::new();
        l.record(1, &[5]).unwrap(); // lagging
        l.record(5, &[5]).unwrap(); // synced
        l.record(5, &[7]).unwrap(); // lagging
        assert_eq!(l.lag_count(), 2);
        assert_eq!(l.synchronized_count(), 1);
    }

    #[test]
    fn max_lag_tracked() {
        let mut l = SyncLog::new();
        l.record(1, &[5]).unwrap();  // lag=4
        l.record(2, &[10]).unwrap(); // lag=8
        l.record(10, &[10]).unwrap(); // synced
        assert_eq!(l.max_lag(), 8);
    }

    #[test]
    fn chain_links_correctly() {
        let mut l = SyncLog::new();
        l.record(1, &[1]).unwrap();
        l.record(2, &[2]).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].sync_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = SyncLog::new();
        for e in 1..=5u64 {
            l.record(e, &[e]).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn tampered_record_breaks_chain() {
        let mut l = SyncLog::new();
        l.record(1, &[1]).unwrap();
        l.record(2, &[2]).unwrap();
        l.records[0].sync_hash[0] ^= 0xFF;
        let (valid, broken) = l.verify_chain();
        assert!(!valid);
        assert_eq!(broken, Some(0));
    }
}
