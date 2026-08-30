//! Gate 392 — Gossip Delivery Ratio Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks the ratio of successfully delivered frames to total dispatched frames
//! per epoch. delivery_ratio_pct = floor(delivered * 100 / max(dispatched, 1)).
//! Classifies each epoch as: Full (100%), Partial (≥50%), Poor (<50%).
//!
//! GossipDeliveryRatioEntry (hash-chained):
//!   epoch_end:          u64
//!   dispatched:         u32
//!   delivered:          u32
//!   delivery_ratio_pct: u32  — floor(delivered*100/max(dispatched,1))
//!   class:              DeliveryClass
//!   entry_hash:         [u8;32]
//!   prev_hash:          [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ dispatched_be4
//!                       ‖ delivered_be4 ‖ delivery_ratio_pct_be4 ‖ class_byte)
//!
//! GossipDeliveryRatioLog: record(epoch_end, dispatched, delivered),
//!   full_count(), partial_count(), poor_count(), average_ratio_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_DELIVERY_RATIO_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── DeliveryClass ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum DeliveryClass {
    Full    = 0, // delivery_ratio_pct == 100
    Partial = 1, // delivery_ratio_pct >= 50
    Poor    = 2, // delivery_ratio_pct < 50
}

impl DeliveryClass {
    fn as_u8(self) -> u8 { self as u8 }

    fn classify(ratio_pct: u32) -> Self {
        if ratio_pct == 100 {
            DeliveryClass::Full
        } else if ratio_pct >= 50 {
            DeliveryClass::Partial
        } else {
            DeliveryClass::Poor
        }
    }
}

// ─── GossipDeliveryRatioEntry ─────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDeliveryRatioEntry {
    pub epoch_end:          u64,
    pub dispatched:         u32,
    pub delivered:          u32,
    pub delivery_ratio_pct: u32,
    pub class:              DeliveryClass,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_delivery_ratio_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    dispatched:         u32,
    delivered:          u32,
    delivery_ratio_pct: u32,
    class:              DeliveryClass,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(dispatched.to_be_bytes());
    h.update(delivered.to_be_bytes());
    h.update(delivery_ratio_pct.to_be_bytes());
    h.update([class.as_u8()]);
    h.finalize().into()
}

// ─── GossipDeliveryRatioLog ───────────────────────────────────────────────────

pub struct GossipDeliveryRatioLog {
    entries: Vec<GossipDeliveryRatioEntry>,
}

impl GossipDeliveryRatioLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipDeliveryRatioEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipDeliveryRatioEntry> { self.entries.last() }

    /// Count of epochs with DeliveryClass::Full (100% delivery).
    pub fn full_count(&self) -> usize {
        self.entries.iter().filter(|e| e.class == DeliveryClass::Full).count()
    }

    /// Count of epochs with DeliveryClass::Partial (50–99% delivery).
    pub fn partial_count(&self) -> usize {
        self.entries.iter().filter(|e| e.class == DeliveryClass::Partial).count()
    }

    /// Count of epochs with DeliveryClass::Poor (<50% delivery).
    pub fn poor_count(&self) -> usize {
        self.entries.iter().filter(|e| e.class == DeliveryClass::Poor).count()
    }

    /// Average delivery_ratio_pct across all entries (floor division). Returns 0 if empty.
    pub fn average_ratio_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u32 = self.entries.iter().map(|e| e.delivery_ratio_pct).sum();
        sum / self.entries.len() as u32
    }

    /// Record delivery ratio for one epoch.
    /// delivered is clamped to dispatched (cannot deliver more than dispatched).
    pub fn record(
        &mut self,
        epoch_end:  u64,
        dispatched: u32,
        delivered:  u32,
    ) -> &GossipDeliveryRatioEntry {
        // Clamp delivered to dispatched
        let delivered = delivered.min(dispatched);
        let delivery_ratio_pct = (delivered as u64 * 100 / dispatched.max(1) as u64) as u32;
        let class = DeliveryClass::classify(delivery_ratio_pct);

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_DELIVERY_RATIO_GENESIS_HASH);

        let entry_hash = compute_delivery_ratio_hash(
            &prev, epoch_end, dispatched, delivered, delivery_ratio_pct, class,
        );

        self.entries.push(GossipDeliveryRatioEntry {
            epoch_end,
            dispatched,
            delivered,
            delivery_ratio_pct,
            class,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_DELIVERY_RATIO_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_delivery_ratio_hash(
                &prev, e.epoch_end, e.dispatched, e.delivered,
                e.delivery_ratio_pct, e.class,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipDeliveryRatioLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── class classification ──────────────────────────────────────────────────

    #[test]
    fn full_delivery_class() {
        let mut log = GossipDeliveryRatioLog::new();
        let e = log.record(1, 100, 100);
        assert_eq!(e.delivery_ratio_pct, 100);
        assert_eq!(e.class, DeliveryClass::Full);
    }

    #[test]
    fn partial_delivery_class_at_boundary() {
        let mut log = GossipDeliveryRatioLog::new();
        let e = log.record(1, 100, 50);
        assert_eq!(e.delivery_ratio_pct, 50);
        assert_eq!(e.class, DeliveryClass::Partial);
    }

    #[test]
    fn partial_delivery_class_mid_range() {
        let mut log = GossipDeliveryRatioLog::new();
        let e = log.record(1, 100, 75);
        assert_eq!(e.delivery_ratio_pct, 75);
        assert_eq!(e.class, DeliveryClass::Partial);
    }

    #[test]
    fn poor_delivery_class() {
        let mut log = GossipDeliveryRatioLog::new();
        let e = log.record(1, 100, 30);
        assert_eq!(e.delivery_ratio_pct, 30);
        assert_eq!(e.class, DeliveryClass::Poor);
    }

    #[test]
    fn zero_dispatched_gives_zero_ratio() {
        let mut log = GossipDeliveryRatioLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.delivery_ratio_pct, 0);
        assert_eq!(e.class, DeliveryClass::Poor);
    }

    #[test]
    fn delivered_clamped_to_dispatched() {
        let mut log = GossipDeliveryRatioLog::new();
        // delivered > dispatched → clamped
        let e = log.record(1, 50, 200);
        assert_eq!(e.delivered, 50);
        assert_eq!(e.delivery_ratio_pct, 100);
        assert_eq!(e.class, DeliveryClass::Full);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn counts_correct() {
        let mut log = GossipDeliveryRatioLog::new();
        log.record(1, 100, 100); // Full
        log.record(2, 100, 75);  // Partial
        log.record(3, 100, 50);  // Partial
        log.record(4, 100, 30);  // Poor
        assert_eq!(log.full_count(), 1);
        assert_eq!(log.partial_count(), 2);
        assert_eq!(log.poor_count(), 1);
    }

    #[test]
    fn average_ratio_pct_correct() {
        let mut log = GossipDeliveryRatioLog::new();
        log.record(1, 100, 100); // 100%
        log.record(2, 100, 60);  // 60%
        log.record(3, 100, 80);  // 80%
        // avg = (100+60+80)/3 = 80
        assert_eq!(log.average_ratio_pct(), 80);
    }

    #[test]
    fn average_ratio_pct_empty_zero() {
        let log = GossipDeliveryRatioLog::new();
        assert_eq!(log.average_ratio_pct(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipDeliveryRatioLog::new();
        let e = log.record(1, 100, 80);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipDeliveryRatioLog::new();
        let e = log.record(1, 100, 80);
        assert_eq!(e.prev_hash, GOSSIP_DELIVERY_RATIO_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipDeliveryRatioLog::new();
        log.record(1, 100, 80);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 100, 60);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipDeliveryRatioLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipDeliveryRatioLog::new();
        for i in 1u64..=5 { log.record(i, 100, (i * 20) as u32); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipDeliveryRatioLog::new();
        log.record(1, 100, 80);
        log.record(2, 100, 60);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipDeliveryRatioLog::new();
        let mut l2 = GossipDeliveryRatioLog::new();
        let h1 = l1.record(5, 100, 75).entry_hash;
        let h2 = l2.record(5, 100, 75).entry_hash;
        assert_eq!(h1, h2);
    }
}
