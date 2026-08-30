//! Gate 307 — Gossip Peer Blocklist: temporary and permanent peer banning (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains a blocklist of peers that should not receive or send gossip messages.
//! Bans may be temporary (expire after N epochs) or permanent. Each ban/unban is
//! recorded as a hash-chained BanRecord.
//!
//! Constants:
//!   DEFAULT_BAN_DURATION_EPOCHS: u64 = 10  (default temporary ban duration)
//!   MAX_BLOCKLIST_SIZE: usize = 256
//!
//! BanReason: ManualBan | ExcessiveMisses | ReplayAttack | RateLimitViolation | PermanentBan
//!
//! BanEntry:
//!   peer_id, banned_at_epoch, expires_at_epoch: Option<u64> (None = permanent)
//!   reason: BanReason
//!
//! BanRecord:
//!   peer_id, epoch, reason, action: BanAction (Ban | Unban | Expire),
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ reason_byte ‖ action_byte)
//!   prev_hash
//!
//! BanLog: hash-chained BanRecords.
//!   push(), ban_count(), unban_count(), verify_chain().
//!
//! PeerBlocklist:
//!   ban(peer_id, epoch, reason, duration_epochs: Option<u64>) → Result<(), BlocklistError>
//!     Some(n) = temporary ban for n epochs; None = permanent
//!   unban(peer_id, epoch) → bool
//!   is_banned(peer_id, current_epoch) → bool  (checks expiry)
//!   expire_bans(current_epoch)  — removes all expired bans, records Expire events
//!   banned_peers(current_epoch) → Vec<u32>
//!   get_log() → &BanLog

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const DEFAULT_BAN_DURATION_EPOCHS: u64   = 10;
pub const MAX_BLOCKLIST_SIZE:          usize = 256;

// ─── Ban reason ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BanReason {
    ManualBan          = 0,
    ExcessiveMisses    = 1,
    ReplayAttack       = 2,
    RateLimitViolation = 3,
    PermanentBan       = 4,
}

impl BanReason {
    pub fn reason_byte(self) -> u8 { self as u8 }
}

// ─── Ban action ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BanAction {
    Ban    = 0,
    Unban  = 1,
    Expire = 2,
}

impl BanAction {
    pub fn action_byte(self) -> u8 { self as u8 }
}

// ─── Ban record ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct BanRecord {
    pub peer_id:     u32,
    pub epoch:       u64,
    pub reason:      BanReason,
    pub action:      BanAction,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const BAN_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_ban_hash(
    peer_id: u32,
    epoch:   u64,
    reason:  BanReason,
    action:  BanAction,
    prev:    &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([reason.reason_byte(), action.action_byte()]);
    h.finalize().into()
}

pub fn build_ban_record(
    peer_id:   u32,
    epoch:     u64,
    reason:    BanReason,
    action:    BanAction,
    prev_hash: &[u8; 32],
) -> BanRecord {
    let record_hash = compute_ban_hash(peer_id, epoch, reason, action, prev_hash);
    BanRecord { peer_id, epoch, reason, action, record_hash, prev_hash: *prev_hash }
}

// ─── Ban log ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BanLog {
    records: Vec<BanRecord>,
}

impl BanLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[BanRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(BAN_GENESIS_HASH)
    }

    pub fn push(&mut self, peer_id: u32, epoch: u64, reason: BanReason, action: BanAction) -> &BanRecord {
        let prev = self.last_hash();
        let r = build_ban_record(peer_id, epoch, reason, action, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn ban_count(&self) -> usize {
        self.records.iter().filter(|r| r.action == BanAction::Ban).count()
    }

    pub fn unban_count(&self) -> usize {
        self.records.iter().filter(|r| r.action == BanAction::Unban).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = BAN_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_ban_hash(r.peer_id, r.epoch, r.reason, r.action, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for BanLog {
    fn default() -> Self { Self::new() }
}

// ─── Ban entry (in-memory state) ──────────────────────────────────────────────

#[derive(Debug, Clone)]
struct BanEntry {
    banned_at_epoch:  u64,
    expires_at_epoch: Option<u64>, // None = permanent
    reason:           BanReason,
}

// ─── Peer blocklist ───────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum BlocklistError {
    AlreadyBanned,
    BlocklistFull,
}

#[derive(Debug, Clone)]
pub struct PeerBlocklist {
    entries: BTreeMap<u32, BanEntry>,
    pub log: BanLog,
}

impl PeerBlocklist {
    pub fn new() -> Self { Self { entries: BTreeMap::new(), log: BanLog::new() } }

    pub fn ban(
        &mut self,
        peer_id:         u32,
        epoch:           u64,
        reason:          BanReason,
        duration_epochs: Option<u64>,
    ) -> Result<(), BlocklistError> {
        if self.entries.contains_key(&peer_id) { return Err(BlocklistError::AlreadyBanned); }
        if self.entries.len() >= MAX_BLOCKLIST_SIZE { return Err(BlocklistError::BlocklistFull); }
        let expires_at = duration_epochs.map(|d| epoch.saturating_add(d));
        self.entries.insert(peer_id, BanEntry { banned_at_epoch: epoch, expires_at_epoch: expires_at, reason });
        self.log.push(peer_id, epoch, reason, BanAction::Ban);
        Ok(())
    }

    /// Manually unban a peer. Returns true if the peer was banned.
    pub fn unban(&mut self, peer_id: u32, epoch: u64) -> bool {
        if let Some(entry) = self.entries.remove(&peer_id) {
            self.log.push(peer_id, epoch, entry.reason, BanAction::Unban);
            true
        } else {
            false
        }
    }

    pub fn is_banned(&self, peer_id: u32, current_epoch: u64) -> bool {
        self.entries.get(&peer_id).map(|e| {
            match e.expires_at_epoch {
                None    => true,                         // permanent
                Some(x) => current_epoch < x,           // temporary: still active?
            }
        }).unwrap_or(false)
    }

    /// Remove all expired bans, recording Expire events.
    pub fn expire_bans(&mut self, current_epoch: u64) {
        let expired: Vec<(u32, BanReason)> = self.entries.iter()
            .filter(|(_, e)| matches!(e.expires_at_epoch, Some(x) if current_epoch >= x))
            .map(|(&pid, e)| (pid, e.reason))
            .collect();
        for (pid, reason) in expired {
            self.entries.remove(&pid);
            self.log.push(pid, current_epoch, reason, BanAction::Expire);
        }
    }

    /// All currently active bans (not yet expired) sorted by peer_id.
    pub fn banned_peers(&self, current_epoch: u64) -> Vec<u32> {
        self.entries.iter()
            .filter(|(_, e)| match e.expires_at_epoch {
                None    => true,
                Some(x) => current_epoch < x,
            })
            .map(|(&pid, _)| pid)
            .collect()
    }

    pub fn blocklist_size(&self) -> usize { self.entries.len() }
}

impl Default for PeerBlocklist {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── BanReason / BanAction ─────────────────────────────────────────────────

    #[test]
    fn reason_and_action_bytes() {
        assert_eq!(BanReason::ManualBan.reason_byte(),          0);
        assert_eq!(BanReason::ReplayAttack.reason_byte(),       2);
        assert_eq!(BanReason::PermanentBan.reason_byte(),       4);
        assert_eq!(BanAction::Ban.action_byte(),    0);
        assert_eq!(BanAction::Unban.action_byte(),  1);
        assert_eq!(BanAction::Expire.action_byte(), 2);
    }

    // ── build_ban_record ──────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_ban_record(1, 1, BanReason::ManualBan, BanAction::Ban, &BAN_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_ban_record(1, 1, BanReason::ManualBan, BanAction::Ban, &BAN_GENESIS_HASH);
        let r2 = build_ban_record(1, 1, BanReason::ManualBan, BanAction::Ban, &BAN_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── BanLog ────────────────────────────────────────────────────────────────

    #[test]
    fn log_counts_actions() {
        let mut l = BanLog::new();
        l.push(1, 1, BanReason::ManualBan, BanAction::Ban);
        l.push(1, 2, BanReason::ManualBan, BanAction::Unban);
        l.push(2, 3, BanReason::ReplayAttack, BanAction::Ban);
        assert_eq!(l.ban_count(), 2);
        assert_eq!(l.unban_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = BanLog::new();
        l.push(1, 1, BanReason::ManualBan, BanAction::Ban);
        l.push(2, 2, BanReason::ReplayAttack, BanAction::Ban);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = BanLog::new();
        for i in 0..5u32 {
            l.push(i, i as u64, BanReason::ManualBan, BanAction::Ban);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── PeerBlocklist ─────────────────────────────────────────────────────────

    #[test]
    fn ban_and_check() {
        let mut bl = PeerBlocklist::new();
        bl.ban(1, 1, BanReason::ManualBan, Some(DEFAULT_BAN_DURATION_EPOCHS)).unwrap();
        assert!(bl.is_banned(1, 1));
        assert!(bl.is_banned(1, 5));
        assert!(!bl.is_banned(2, 1)); // not banned
    }

    #[test]
    fn temporary_ban_expires() {
        let mut bl = PeerBlocklist::new();
        bl.ban(1, 1, BanReason::ManualBan, Some(5)).unwrap(); // expires at epoch 6
        assert!(bl.is_banned(1, 5));   // epoch 5 < 6 → still banned
        assert!(!bl.is_banned(1, 6));  // epoch 6 == 6 → expired
        assert!(!bl.is_banned(1, 10)); // well past expiry
    }

    #[test]
    fn permanent_ban_never_expires() {
        let mut bl = PeerBlocklist::new();
        bl.ban(1, 1, BanReason::PermanentBan, None).unwrap();
        assert!(bl.is_banned(1, 9999));
    }

    #[test]
    fn duplicate_ban_errors() {
        let mut bl = PeerBlocklist::new();
        bl.ban(1, 1, BanReason::ManualBan, Some(5)).unwrap();
        assert!(matches!(bl.ban(1, 2, BanReason::ManualBan, Some(5)), Err(BlocklistError::AlreadyBanned)));
    }

    #[test]
    fn unban_removes_entry() {
        let mut bl = PeerBlocklist::new();
        bl.ban(1, 1, BanReason::ManualBan, Some(10)).unwrap();
        assert!(bl.unban(1, 2));
        assert!(!bl.is_banned(1, 2));
        assert_eq!(bl.log.unban_count(), 1);
    }

    #[test]
    fn expire_bans_removes_expired() {
        let mut bl = PeerBlocklist::new();
        bl.ban(1, 1, BanReason::ManualBan, Some(5)).unwrap();  // expires at 6
        bl.ban(2, 1, BanReason::ManualBan, Some(20)).unwrap(); // expires at 21
        bl.expire_bans(6);
        assert!(!bl.is_banned(1, 6)); // removed
        assert!(bl.is_banned(2, 6));  // still active
        assert_eq!(bl.blocklist_size(), 1);
    }

    #[test]
    fn banned_peers_sorted() {
        let mut bl = PeerBlocklist::new();
        bl.ban(3, 1, BanReason::ManualBan, None).unwrap();
        bl.ban(1, 1, BanReason::ManualBan, None).unwrap();
        bl.ban(2, 1, BanReason::ManualBan, None).unwrap();
        assert_eq!(bl.banned_peers(1), vec![1, 2, 3]);
    }
}
