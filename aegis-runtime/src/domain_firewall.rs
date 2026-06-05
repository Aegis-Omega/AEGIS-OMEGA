//! Pillar 2 — Strict Domain-Isolated Memory Sandbox
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Separates Domain 0 (immutable substrate — verified core state) from
//! Domain 1 (mutable overlay — agent-supplied metadata). Access across
//! domains is mediated by `OpaqueSegmentKey` lookup tokens only.
//! No direct reference manipulation across the execution boundary is permitted.
//!
//! Constitutional invariants:
//! - BTreeMap<OpaqueSegmentKey, Domain0Record> — deterministic lookup
//! - Domain 1 write path has no reference to Domain 0 internal bytes
//! - verify_all_domain0() must return 0 for T0 pass

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

/// Opaque lookup token mediating all cross-domain access.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct OpaqueSegmentKey {
    pub domain_id: u32,
    pub segment_id: u32,
}

/// Domain 0 — immutable substrate record. Verified on every read.
#[derive(Clone, Debug)]
pub struct Domain0Record {
    pub key: OpaqueSegmentKey,
    pub payload: Vec<u8>,
    pub integrity_hash: [u8; 32],
}

impl Domain0Record {
    pub fn new(key: OpaqueSegmentKey, payload: Vec<u8>) -> Self {
        let integrity_hash = Self::hash(key, &payload);
        Self { key, payload, integrity_hash }
    }
    pub fn verify(&self) -> bool { Self::hash(self.key, &self.payload) == self.integrity_hash }
    fn hash(key: OpaqueSegmentKey, bytes: &[u8]) -> [u8; 32] {
        let mut h = Sha256::new();
        h.update(key.domain_id.to_le_bytes());
        h.update(key.segment_id.to_le_bytes());
        h.update(bytes);
        h.finalize().into()
    }
}

/// Domain 1 — mutable metadata overlay. Keyed by OpaqueSegmentKey.
#[derive(Default)]
pub struct Domain1Overlay {
    entries: BTreeMap<OpaqueSegmentKey, Vec<u8>>,
}

impl Domain1Overlay {
    pub fn set(&mut self, key: OpaqueSegmentKey, data: Vec<u8>) { self.entries.insert(key, data); }
    pub fn get(&self, key: OpaqueSegmentKey) -> Option<&[u8]> { self.entries.get(&key).map(|v| v.as_slice()) }
    pub fn len(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }
}

#[derive(Debug)]
pub enum FirewallError {
    IntegrityViolation(OpaqueSegmentKey),
    NotFound(OpaqueSegmentKey),
}
impl std::fmt::Display for FirewallError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FirewallError::IntegrityViolation(k) => write!(f, "integrity violation: {}:{}", k.domain_id, k.segment_id),
            FirewallError::NotFound(k) => write!(f, "not found: {}:{}", k.domain_id, k.segment_id),
        }
    }
}
impl std::error::Error for FirewallError {}

/// Composes Domain 0 and Domain 1 with strict write isolation.
pub struct DomainFirewall {
    domain0: BTreeMap<OpaqueSegmentKey, Domain0Record>,
    domain1: Domain1Overlay,
}

impl DomainFirewall {
    pub fn new() -> Self { Self { domain0: BTreeMap::new(), domain1: Domain1Overlay::default() } }

    pub fn register(&mut self, record: Domain0Record) -> Result<(), FirewallError> {
        if !record.verify() { return Err(FirewallError::IntegrityViolation(record.key)); }
        self.domain0.entry(record.key).or_insert(record);
        Ok(())
    }

    pub fn read_domain0(&self, key: OpaqueSegmentKey) -> Result<&Domain0Record, FirewallError> {
        match self.domain0.get(&key) {
            None => Err(FirewallError::NotFound(key)),
            Some(r) => if r.verify() { Ok(r) } else { Err(FirewallError::IntegrityViolation(key)) },
        }
    }

    pub fn write_domain1(&mut self, key: OpaqueSegmentKey, data: Vec<u8>) {
        self.domain1.set(key, data);
    }

    pub fn read_domain1(&self, key: OpaqueSegmentKey) -> Option<&[u8]> { self.domain1.get(key) }

    pub fn verify_all_domain0(&self) -> usize { self.domain0.values().filter(|r| !r.verify()).count() }
    pub fn domain0_len(&self) -> usize { self.domain0.len() }
    pub fn domain1_len(&self) -> usize { self.domain1.len() }
}

impl Default for DomainFirewall { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    fn k(d: u32, s: u32) -> OpaqueSegmentKey { OpaqueSegmentKey { domain_id: d, segment_id: s } }

    #[test] fn register_and_read_domain0() {
        let mut fw = DomainFirewall::new();
        fw.register(Domain0Record::new(k(0,1), b"core".to_vec())).unwrap();
        assert!(fw.read_domain0(k(0,1)).is_ok());
    }
    #[test] fn tampered_record_rejected_on_register() {
        let mut fw = DomainFirewall::new();
        let mut r = Domain0Record::new(k(0,1), b"x".to_vec());
        r.payload.push(0xFF);
        assert!(fw.register(r).is_err());
    }
    #[test] fn domain1_write_independent_of_domain0() {
        let mut fw = DomainFirewall::new();
        fw.register(Domain0Record::new(k(0,1), b"base".to_vec())).unwrap();
        fw.write_domain1(k(0,1), b"overlay".to_vec());
        assert_eq!(fw.verify_all_domain0(), 0);
        assert_eq!(fw.read_domain1(k(0,1)), Some(b"overlay".as_slice()));
    }
    #[test] fn verify_all_domain0_passes() {
        let mut fw = DomainFirewall::new();
        for i in 0..5u32 { fw.register(Domain0Record::new(k(0,i), vec![i as u8])).unwrap(); }
        assert_eq!(fw.verify_all_domain0(), 0);
    }
    #[test] fn btreemap_iteration_ordered() {
        let mut fw = DomainFirewall::new();
        fw.register(Domain0Record::new(k(2,0), b"b".to_vec())).unwrap();
        fw.register(Domain0Record::new(k(1,0), b"a".to_vec())).unwrap();
        let first = fw.domain0.keys().next().unwrap();
        assert_eq!(*first, k(1,0));
    }

    // 6. read_domain0 on unregistered key returns NotFound
    #[test] fn read_domain0_unregistered_returns_not_found() {
        let fw = DomainFirewall::new();
        let result = fw.read_domain0(k(9, 9));
        assert!(matches!(result, Err(FirewallError::NotFound(_))));
    }

    // 7. domain1_len increments with each write
    #[test] fn domain1_len_increments() {
        let mut fw = DomainFirewall::new();
        assert_eq!(fw.domain1_len(), 0);
        fw.write_domain1(k(0,1), b"a".to_vec());
        assert_eq!(fw.domain1_len(), 1);
        fw.write_domain1(k(0,2), b"b".to_vec());
        assert_eq!(fw.domain1_len(), 2);
    }

    // 8. domain0_len increments with each successful register
    #[test] fn domain0_len_increments() {
        let mut fw = DomainFirewall::new();
        assert_eq!(fw.domain0_len(), 0);
        fw.register(Domain0Record::new(k(0,1), b"x".to_vec())).unwrap();
        assert_eq!(fw.domain0_len(), 1);
    }

    // 9. read_domain1 on unregistered key returns None
    #[test] fn domain1_unregistered_returns_none() {
        let fw = DomainFirewall::new();
        assert_eq!(fw.read_domain1(k(99, 99)), None);
    }

    // 10. register is idempotent (or_insert semantics — second call doesn't overwrite)
    #[test] fn register_idempotent_for_same_key() {
        let mut fw = DomainFirewall::new();
        fw.register(Domain0Record::new(k(0,1), b"first".to_vec())).unwrap();
        fw.register(Domain0Record::new(k(0,1), b"second".to_vec())).unwrap();
        // domain0_len stays at 1 (or_insert doesn't replace)
        assert_eq!(fw.domain0_len(), 1);
        let rec = fw.read_domain0(k(0,1)).unwrap();
        assert_eq!(rec.payload, b"first");
    }
}
