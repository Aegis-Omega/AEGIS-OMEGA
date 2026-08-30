//! Gate 434 — Gossip Broadcast Loss Monitor (T2)
//! Tracks loss rate per gossip broadcast epoch.
//! HIGH_LOSS_THRESHOLD = 3: rate_pct > 3 → high_loss

use sha2::{Sha256, Digest};

pub const LOSS_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_LOSS_THRESHOLD: u32 = 3;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipLossEntry {
    pub epoch_end:    u64,
    pub lost_msgs:    u32,
    pub total_sent:   u32,
    pub lost_rate_pct: u32,
    pub high_loss:    bool,
    pub entry_hash:   [u8; 32],
    pub prev_hash:    [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    lost_msgs: u32,
    total_sent: u32,
    lost_rate_pct: u32,
    high_loss: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(lost_msgs.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(lost_rate_pct.to_be_bytes());
    h.update([high_loss as u8]);
    h.finalize().into()
}

pub struct GossipLossLog {
    pub entries: Vec<GossipLossEntry>,
}

impl GossipLossLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, lost_msgs: u32, total_sent: u32) -> &GossipLossEntry {
        let denom = total_sent.max(1) as u64;
        let lost_rate_pct = ((lost_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_loss = lost_rate_pct > HIGH_LOSS_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(LOSS_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, lost_msgs, total_sent, lost_rate_pct, high_loss);
        self.entries.push(GossipLossEntry {
            epoch_end,
            lost_msgs,
            total_sent,
            lost_rate_pct,
            high_loss,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_loss_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_loss).count()
    }

    pub fn total_lost_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.lost_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.lost_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = LOSS_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.lost_msgs, e.total_sent, e.lost_rate_pct, e.high_loss);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipLossLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_rate_and_flag_true() {
        let mut log = GossipLossLog::new();
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.lost_msgs, 10);
        assert_eq!(e.total_sent, 100);
        assert_eq!(e.lost_rate_pct, 10);
        assert!(e.high_loss);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipLossLog::new();
        // rate_pct == 3 → not > 3 → high_loss = false
        let e = log.record(2000, 3, 100);
        assert_eq!(e.lost_rate_pct, 3);
        assert!(!e.high_loss);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipLossLog::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.lost_rate_pct, 100);
        assert!(e.high_loss);
    }

    #[test]
    fn total_sent_zero_no_div_by_zero() {
        let mut log = GossipLossLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.lost_rate_pct, 0);
        assert!(!e.high_loss);
    }

    #[test]
    fn threshold_constant_value_is_3() {
        assert_eq!(HIGH_LOSS_THRESHOLD, 3);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipLossLog::new();
        let e = log.record(5000, 5, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_is_genesis() {
        let mut log = GossipLossLog::new();
        log.record(6000, 1, 50);
        assert_eq!(log.entries[0].prev_hash, LOSS_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipLossLog::new();
        log.record(7000, 1, 50);
        log.record(8000, 2, 50);
        assert_eq!(log.entries[1].prev_hash, log.entries[0].entry_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipLossLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipLossLog::new();
        log.record(9000, 1, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipLossLog::new();
        log.record(10000, 1, 20);
        log.record(11000, 2, 40);
        log.record(12000, 3, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipLossLog::new();
        log.record(13000, 1, 20);
        log.record(14000, 2, 40);
        log.entries[0].lost_msgs = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipLossLog::new();
        log.record(15000, 1, 20);
        log.record(16000, 2, 40);
        log.entries[1].lost_msgs = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipLossLog::new();
        let mut log2 = GossipLossLog::new();
        let mut log3 = GossipLossLog::new();
        let e1 = log1.record(17000, 4, 80);
        let e2 = log2.record(17000, 4, 80);
        let e3 = log3.record(17000, 4, 80);
        assert_eq!(e1.entry_hash, e2.entry_hash);
        assert_eq!(e2.entry_hash, e3.entry_hash);
    }

    #[test]
    fn high_loss_count_mixed_log() {
        let mut log = GossipLossLog::new();
        log.record(18000, 1, 100);  // 1% → not high
        log.record(19000, 5, 100);  // 5% → high
        log.record(20000, 3, 100);  // 3% → not high (exactly at threshold)
        log.record(21000, 10, 100); // 10% → high
        assert_eq!(log.high_loss_count(), 2);
    }

    #[test]
    fn total_lost_msgs_sums_correctly() {
        let mut log = GossipLossLog::new();
        log.record(22000, 7, 100);
        log.record(23000, 13, 100);
        log.record(24000, 5, 100);
        assert_eq!(log.total_lost_msgs(), 25);
    }

    #[test]
    fn mean_rate_pct_empty_returns_0() {
        let log = GossipLossLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipLossLog::new();
        log.record(25000, 10, 100); // 10%
        log.record(26000, 20, 100); // 20%
        log.record(27000, 30, 100); // 30%
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_has_zero_entries() {
        let log = GossipLossLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}