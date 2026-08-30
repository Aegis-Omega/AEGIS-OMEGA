//! Gate 315 — Gossip Peer Address Book: peer endpoint registry (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maps peer_id (u32) to a network address string (e.g. "192.168.1.1:7890").
//! Updates are accepted only if the supplied epoch strictly exceeds the last
//! registered epoch for that peer (monotone). Removals are unconditional.
//! All mutations are hash-chained for audit.
//!
//! Constants:
//!   MAX_ADDRESS_LEN: usize = 128
//!   MAX_BOOK_SIZE:   usize = 256
//!
//! AddressOp: Register | Update | Remove
//!
//! AddressRecord:
//!   peer_id, epoch, address_hash: [u8;32], op
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ address_hash[32] ‖ op_byte)
//!   prev_hash
//!
//! AddressLog: hash-chained AddressRecords (global).
//!   push(), register_count(), update_count(), remove_count(), verify_chain().
//!
//! PeerAddressBook:
//!   register(peer_id, address, epoch) → Result<AddressOp, AddressError>
//!     Returns Ok(Register) for new peer, Ok(Update) for existing peer with new address.
//!     Returns Err(StaleEpoch) if epoch not strictly advancing.
//!     Returns Err(AddressTooLong) if address > MAX_ADDRESS_LEN bytes.
//!     Returns Err(BookFull) if book at MAX_BOOK_SIZE and peer is new.
//!   remove(peer_id, epoch) → bool
//!   lookup(peer_id) → Option<&str>
//!   all_peers() → Vec<u32>   (sorted)
//!   book_size() → usize

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MAX_ADDRESS_LEN: usize = 128;
pub const MAX_BOOK_SIZE:   usize = 256;

// ─── Address operation ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AddressOp {
    Register = 0,
    Update   = 1,
    Remove   = 2,
}

impl AddressOp {
    pub fn op_byte(self) -> u8 { self as u8 }
}

// ─── Address record ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct AddressRecord {
    pub peer_id:      u32,
    pub epoch:        u64,
    pub address_hash: [u8; 32],
    pub op:           AddressOp,
    pub record_hash:  [u8; 32],
    pub prev_hash:    [u8; 32],
}

pub const ADDRESS_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_address_hash(
    peer_id:      u32,
    epoch:        u64,
    address_hash: &[u8; 32],
    op:           AddressOp,
    prev:         &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(address_hash);
    h.update([op.op_byte()]);
    h.finalize().into()
}

pub fn build_address_record(
    peer_id:      u32,
    epoch:        u64,
    address_hash: [u8; 32],
    op:           AddressOp,
    prev_hash:    &[u8; 32],
) -> AddressRecord {
    let record_hash = compute_address_hash(peer_id, epoch, &address_hash, op, prev_hash);
    AddressRecord { peer_id, epoch, address_hash, op, record_hash, prev_hash: *prev_hash }
}

// ─── Address log ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AddressLog {
    records: Vec<AddressRecord>,
}

impl AddressLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[AddressRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(ADDRESS_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        peer_id:      u32,
        epoch:        u64,
        address_hash: [u8; 32],
        op:           AddressOp,
    ) -> &AddressRecord {
        let prev = self.last_hash();
        let r = build_address_record(peer_id, epoch, address_hash, op, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn register_count(&self) -> usize {
        self.records.iter().filter(|r| r.op == AddressOp::Register).count()
    }

    pub fn update_count(&self) -> usize {
        self.records.iter().filter(|r| r.op == AddressOp::Update).count()
    }

    pub fn remove_count(&self) -> usize {
        self.records.iter().filter(|r| r.op == AddressOp::Remove).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = ADDRESS_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_address_hash(r.peer_id, r.epoch, &r.address_hash, r.op, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for AddressLog {
    fn default() -> Self { Self::new() }
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug, PartialEq, Eq)]
pub enum AddressError {
    StaleEpoch,
    AddressTooLong,
    BookFull,
}

// ─── Peer entry (internal) ────────────────────────────────────────────────────

struct PeerEntry {
    address:    String,
    last_epoch: u64,
}

// ─── PeerAddressBook ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerAddressBook {
    entries: BTreeMap<u32, (String, u64)>, // peer_id → (address, last_epoch)
    pub log: AddressLog,
}

fn hash_address(addr: &str) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(addr.as_bytes());
    h.finalize().into()
}

impl PeerAddressBook {
    pub fn new() -> Self {
        Self { entries: BTreeMap::new(), log: AddressLog::new() }
    }

    /// Register or update an address for a peer.
    pub fn register(
        &mut self,
        peer_id: u32,
        address: &str,
        epoch:   u64,
    ) -> Result<AddressOp, AddressError> {
        if address.len() > MAX_ADDRESS_LEN {
            return Err(AddressError::AddressTooLong);
        }
        let is_new = !self.entries.contains_key(&peer_id);
        if is_new && self.entries.len() >= MAX_BOOK_SIZE {
            return Err(AddressError::BookFull);
        }
        if let Some((_, last_epoch)) = self.entries.get(&peer_id) {
            if epoch <= *last_epoch {
                return Err(AddressError::StaleEpoch);
            }
        }

        let op = if is_new { AddressOp::Register } else { AddressOp::Update };
        let addr_hash = hash_address(address);
        self.entries.insert(peer_id, (address.to_string(), epoch));
        self.log.push(peer_id, epoch, addr_hash, op);
        Ok(op)
    }

    /// Remove a peer from the address book. Records Remove operation.
    /// Returns true if the peer existed.
    pub fn remove(&mut self, peer_id: u32, epoch: u64) -> bool {
        if let Some((address, _)) = self.entries.remove(&peer_id) {
            let addr_hash = hash_address(&address);
            self.log.push(peer_id, epoch, addr_hash, AddressOp::Remove);
            true
        } else {
            false
        }
    }

    pub fn lookup(&self, peer_id: u32) -> Option<&str> {
        self.entries.get(&peer_id).map(|(addr, _)| addr.as_str())
    }

    /// All registered peer IDs, sorted.
    pub fn all_peers(&self) -> Vec<u32> {
        self.entries.keys().copied().collect()
    }

    pub fn book_size(&self) -> usize { self.entries.len() }

    pub fn get_log(&self) -> &AddressLog { &self.log }
}

impl Default for PeerAddressBook {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── AddressOp ─────────────────────────────────────────────────────────────

    #[test]
    fn op_bytes() {
        assert_eq!(AddressOp::Register.op_byte(), 0);
        assert_eq!(AddressOp::Update.op_byte(),   1);
        assert_eq!(AddressOp::Remove.op_byte(),   2);
    }

    // ── build_address_record ──────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let ah = [1u8; 32];
        let r = build_address_record(1, 1, ah, AddressOp::Register, &ADDRESS_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let ah = [2u8; 32];
        let r1 = build_address_record(1, 1, ah, AddressOp::Register, &ADDRESS_GENESIS_HASH);
        let r2 = build_address_record(1, 1, ah, AddressOp::Register, &ADDRESS_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── AddressLog ────────────────────────────────────────────────────────────

    #[test]
    fn log_counts() {
        let mut l = AddressLog::new();
        l.push(1, 1, [0u8; 32], AddressOp::Register);
        l.push(1, 2, [1u8; 32], AddressOp::Update);
        l.push(1, 3, [2u8; 32], AddressOp::Remove);
        assert_eq!(l.register_count(), 1);
        assert_eq!(l.update_count(),   1);
        assert_eq!(l.remove_count(),   1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = AddressLog::new();
        l.push(1, 1, [0u8; 32], AddressOp::Register);
        l.push(1, 2, [1u8; 32], AddressOp::Update);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = AddressLog::new();
        for i in 0..5u8 {
            l.push(i as u32, i as u64, [i; 32], AddressOp::Register);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── PeerAddressBook ───────────────────────────────────────────────────────

    #[test]
    fn register_new_peer() {
        let mut b = PeerAddressBook::new();
        let op = b.register(1, "127.0.0.1:7890", 1).unwrap();
        assert_eq!(op, AddressOp::Register);
        assert_eq!(b.lookup(1), Some("127.0.0.1:7890"));
        assert_eq!(b.book_size(), 1);
    }

    #[test]
    fn update_existing_peer() {
        let mut b = PeerAddressBook::new();
        b.register(1, "127.0.0.1:7890", 1).unwrap();
        let op = b.register(1, "10.0.0.1:7890", 2).unwrap();
        assert_eq!(op, AddressOp::Update);
        assert_eq!(b.lookup(1), Some("10.0.0.1:7890"));
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut b = PeerAddressBook::new();
        b.register(1, "127.0.0.1:7890", 5).unwrap();
        assert_eq!(b.register(1, "10.0.0.1:7890", 5), Err(AddressError::StaleEpoch));
        assert_eq!(b.register(1, "10.0.0.1:7890", 3), Err(AddressError::StaleEpoch));
    }

    #[test]
    fn address_too_long_rejected() {
        let long_addr = "x".repeat(MAX_ADDRESS_LEN + 1);
        let mut b = PeerAddressBook::new();
        assert_eq!(b.register(1, &long_addr, 1), Err(AddressError::AddressTooLong));
    }

    #[test]
    fn remove_peer() {
        let mut b = PeerAddressBook::new();
        b.register(1, "127.0.0.1:7890", 1).unwrap();
        assert!(b.remove(1, 2));
        assert_eq!(b.lookup(1), None);
        assert_eq!(b.book_size(), 0);
        assert!(!b.remove(1, 3)); // already removed
    }

    #[test]
    fn all_peers_sorted() {
        let mut b = PeerAddressBook::new();
        b.register(3, "a", 1).unwrap();
        b.register(1, "b", 1).unwrap();
        b.register(2, "c", 1).unwrap();
        assert_eq!(b.all_peers(), vec![1, 2, 3]);
    }

    #[test]
    fn log_records_all_ops() {
        let mut b = PeerAddressBook::new();
        b.register(1, "127.0.0.1", 1).unwrap();
        b.register(1, "10.0.0.1",  2).unwrap(); // update
        b.remove(1, 3);
        let log = b.get_log();
        assert_eq!(log.register_count(), 1);
        assert_eq!(log.update_count(),   1);
        assert_eq!(log.remove_count(),   1);
        let (valid, _) = log.verify_chain();
        assert!(valid);
    }
}
