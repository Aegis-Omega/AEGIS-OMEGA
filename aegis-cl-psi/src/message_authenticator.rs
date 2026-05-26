//! Gate 289 — Gossip Message Authenticator: epoch-keyed message integrity tagging (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Each gossip message is tagged with a 16-byte authentication token derived from
//! SHA-256(peer_id_be4 ‖ epoch_be8 ‖ session_key[16] ‖ message_id_be8 ‖ payload_hash[32]).
//! The first 16 bytes of the digest are used as the token. Verification recomputes
//! and compares. Forgery attempts are counted and hash-linked per peer.
//!
//! AuthTag: [u8; 16] — first 16 bytes of the SHA-256 digest
//!
//! MessageAuthRecord:
//!   peer_id        — u32
//!   epoch          — u64
//!   message_id     — u64
//!   payload_hash   — [u8; 32] (SHA-256 of the raw message bytes)
//!   auth_tag       — [u8; 16]
//!   is_valid       — bool (verification result)
//!   record_hash    — SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ msg_id_be8 ‖ valid_byte)
//!   prev_hash      — [u8; 32]
//!
//! AuthLog: hash-chained MessageAuthRecords per peer.
//!   verify(), valid_count(), forgery_count(), verify_chain().
//!
//! MessageAuthenticator: BTreeMap<peer_id, AuthLog>.
//!   tag_message(peer_id, epoch, message_id, payload_hash) → AuthTag
//!   verify_message(peer_id, epoch, message_id, payload_hash, tag) → bool (+ records result)
//!   total_forgeries(), peer_forgery_count().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const AUTH_TAG_LEN: usize = 16;
pub type AuthTag = [u8; AUTH_TAG_LEN];

// ─── Tag computation ──────────────────────────────────────────────────────────

/// Compute the 16-byte auth tag for a message.
/// session_key is a 16-byte shared secret per (peer, epoch).
pub fn compute_auth_tag(
    peer_id:      u32,
    epoch:        u64,
    session_key:  &[u8; 16],
    message_id:   u64,
    payload_hash: &[u8; 32],
) -> AuthTag {
    let mut h = Sha256::new();
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(session_key);
    h.update(message_id.to_be_bytes());
    h.update(payload_hash);
    let digest: [u8; 32] = h.finalize().into();
    let mut tag = [0u8; AUTH_TAG_LEN];
    tag.copy_from_slice(&digest[..AUTH_TAG_LEN]);
    tag
}

/// Compute SHA-256 of raw message bytes (the payload_hash input to tag computation).
pub fn hash_payload(message_bytes: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(message_bytes);
    h.finalize().into()
}

// ─── Auth record ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct MessageAuthRecord {
    pub peer_id:      u32,
    pub epoch:        u64,
    pub message_id:   u64,
    pub payload_hash: [u8; 32],
    pub auth_tag:     AuthTag,
    pub is_valid:     bool,
    pub record_hash:  [u8; 32],
    pub prev_hash:    [u8; 32],
}

pub const AUTH_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_record_hash(
    peer_id:    u32,
    epoch:      u64,
    message_id: u64,
    is_valid:   bool,
    prev:       &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(message_id.to_be_bytes());
    h.update([if is_valid { 1u8 } else { 0u8 }]);
    h.finalize().into()
}

pub fn build_auth_record(
    peer_id:      u32,
    epoch:        u64,
    message_id:   u64,
    payload_hash: [u8; 32],
    auth_tag:     AuthTag,
    is_valid:     bool,
    prev_hash:    &[u8; 32],
) -> MessageAuthRecord {
    let record_hash = compute_record_hash(peer_id, epoch, message_id, is_valid, prev_hash);
    MessageAuthRecord {
        peer_id, epoch, message_id, payload_hash, auth_tag,
        is_valid, record_hash, prev_hash: *prev_hash,
    }
}

// ─── Auth log ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AuthLog {
    peer_id: u32,
    records: Vec<MessageAuthRecord>,
}

impl AuthLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self)-> bool  { self.records.is_empty() }
    pub fn records(&self) -> &[MessageAuthRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(AUTH_GENESIS_HASH)
    }

    pub fn append(
        &mut self,
        epoch:        u64,
        message_id:   u64,
        payload_hash: [u8; 32],
        auth_tag:     AuthTag,
        is_valid:     bool,
    ) {
        let prev = self.last_hash();
        let r = build_auth_record(
            self.peer_id, epoch, message_id, payload_hash, auth_tag, is_valid, &prev,
        );
        self.records.push(r);
    }

    pub fn valid_count(&self) -> usize {
        self.records.iter().filter(|r| r.is_valid).count()
    }

    pub fn forgery_count(&self) -> usize {
        self.records.iter().filter(|r| !r.is_valid).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = AUTH_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_record_hash(
                r.peer_id, r.epoch, r.message_id, r.is_valid, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Message authenticator ───────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MessageAuthenticator {
    session_key: [u8; 16],
    peers:       BTreeMap<u32, AuthLog>,
}

impl MessageAuthenticator {
    pub fn new(session_key: [u8; 16]) -> Self {
        Self { session_key, peers: BTreeMap::new() }
    }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    /// Compute the auth tag for a message (does NOT record the operation).
    pub fn tag_message(
        &self,
        peer_id:      u32,
        epoch:        u64,
        message_id:   u64,
        payload_hash: &[u8; 32],
    ) -> AuthTag {
        compute_auth_tag(peer_id, epoch, &self.session_key, message_id, payload_hash)
    }

    /// Verify a received auth tag and record the result.
    pub fn verify_message(
        &mut self,
        peer_id:      u32,
        epoch:        u64,
        message_id:   u64,
        payload_hash: [u8; 32],
        claimed_tag:  AuthTag,
    ) -> bool {
        let expected = compute_auth_tag(peer_id, epoch, &self.session_key, message_id, &payload_hash);
        let is_valid = claimed_tag == expected;
        let log = self.peers.entry(peer_id).or_insert_with(|| AuthLog::new(peer_id));
        log.append(epoch, message_id, payload_hash, claimed_tag, is_valid);
        is_valid
    }

    pub fn total_forgeries(&self) -> usize {
        self.peers.values().map(|l| l.forgery_count()).sum()
    }

    pub fn peer_forgery_count(&self, peer_id: u32) -> usize {
        self.peers.get(&peer_id).map(|l| l.forgery_count()).unwrap_or(0)
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&AuthLog> {
        self.peers.get(&peer_id)
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn key() -> [u8; 16] { [0x42u8; 16] }
    fn payload() -> [u8; 32] { hash_payload(b"hello gossip world") }

    // ── compute_auth_tag ──────────────────────────────────────────────────────

    #[test]
    fn tag_nonzero() {
        let t = compute_auth_tag(1, 10, &key(), 99, &payload());
        assert_ne!(t, [0u8; 16]);
    }

    #[test]
    fn tag_deterministic() {
        let t1 = compute_auth_tag(1, 10, &key(), 99, &payload());
        let t2 = compute_auth_tag(1, 10, &key(), 99, &payload());
        assert_eq!(t1, t2);
    }

    #[test]
    fn different_peer_different_tag() {
        let t1 = compute_auth_tag(1, 10, &key(), 99, &payload());
        let t2 = compute_auth_tag(2, 10, &key(), 99, &payload());
        assert_ne!(t1, t2);
    }

    #[test]
    fn different_epoch_different_tag() {
        let t1 = compute_auth_tag(1, 10, &key(), 99, &payload());
        let t2 = compute_auth_tag(1, 11, &key(), 99, &payload());
        assert_ne!(t1, t2);
    }

    #[test]
    fn different_message_different_tag() {
        let t1 = compute_auth_tag(1, 10, &key(), 99, &payload());
        let t2 = compute_auth_tag(1, 10, &key(), 100, &payload());
        assert_ne!(t1, t2);
    }

    #[test]
    fn different_key_different_tag() {
        let k2 = [0xFFu8; 16];
        let t1 = compute_auth_tag(1, 10, &key(), 99, &payload());
        let t2 = compute_auth_tag(1, 10, &k2,  99, &payload());
        assert_ne!(t1, t2);
    }

    // ── hash_payload ──────────────────────────────────────────────────────────

    #[test]
    fn hash_payload_nonzero() {
        let h = hash_payload(b"data");
        assert_ne!(h, [0u8; 32]);
    }

    #[test]
    fn hash_payload_deterministic() {
        assert_eq!(hash_payload(b"data"), hash_payload(b"data"));
    }

    // ── AuthLog ───────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = AuthLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.valid_count(), 0);
        assert_eq!(l.forgery_count(), 0);
    }

    #[test]
    fn log_counts_correctly() {
        let mut l = AuthLog::new(1);
        l.append(1, 1, payload(), [0u8; 16], true);
        l.append(1, 2, payload(), [0u8; 16], false);
        l.append(1, 3, payload(), [0u8; 16], true);
        assert_eq!(l.valid_count(), 2);
        assert_eq!(l.forgery_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = AuthLog::new(1);
        l.append(1, 1, payload(), [0u8; 16], true);
        l.append(1, 2, payload(), [0u8; 16], true);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = AuthLog::new(1);
        for i in 0..5u64 {
            l.append(i + 1, i, payload(), [0u8; 16], i % 2 == 0);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── MessageAuthenticator ──────────────────────────────────────────────────

    #[test]
    fn valid_tag_verifies() {
        let mut auth = MessageAuthenticator::new(key());
        let ph = payload();
        let tag = auth.tag_message(1, 10, 99, &ph);
        assert!(auth.verify_message(1, 10, 99, ph, tag));
        assert_eq!(auth.total_forgeries(), 0);
    }

    #[test]
    fn tampered_tag_detected() {
        let mut auth = MessageAuthenticator::new(key());
        let ph = payload();
        let mut tag = auth.tag_message(1, 10, 99, &ph);
        tag[0] ^= 0xFF; // corrupt first byte
        assert!(!auth.verify_message(1, 10, 99, ph, tag));
        assert_eq!(auth.total_forgeries(), 1);
        assert_eq!(auth.peer_forgery_count(1), 1);
    }

    #[test]
    fn wrong_peer_detected() {
        let mut auth = MessageAuthenticator::new(key());
        let ph = payload();
        let tag = auth.tag_message(1, 10, 99, &ph);
        // verify with peer_id=2 — tag was computed for peer_id=1
        assert!(!auth.verify_message(2, 10, 99, ph, tag));
    }

    #[test]
    fn multiple_peers_tracked() {
        let mut auth = MessageAuthenticator::new(key());
        let ph = payload();
        auth.verify_message(1, 1, 1, ph, [0xFF; 16]); // forgery
        auth.verify_message(2, 1, 1, ph, [0xFF; 16]); // forgery
        assert_eq!(auth.peer_count(), 2);
        assert_eq!(auth.total_forgeries(), 2);
    }

    #[test]
    fn record_hash_nonzero() {
        let r = build_auth_record(1, 1, 1, payload(), [0u8; 16], true, &AUTH_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_auth_record(1, 1, 1, payload(), [0u8; 16], true, &AUTH_GENESIS_HASH);
        let r2 = build_auth_record(1, 1, 1, payload(), [0u8; 16], true, &AUTH_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }
}
