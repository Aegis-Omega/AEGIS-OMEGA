//! Edge BFT Verifier — Stateless quorum proof verification
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! WASM-compatible: no disk access, no network sockets, no mmap
//!
//! Quorum threshold: valid_count * 1_000_000 >= total_count * 618_034
//!   Integer approximation of 1/φ ≈ 0.6180339887 — same governing constant as
//!   DEFAULT_QUORUM_THRESHOLD in swarm.ts and MUTATION_RATE_LIMIT in martingale.ts.
//!   Integer arithmetic avoids floating-point cross-platform determinism issues.
//!
//! Determinism: BTreeMap iteration is always sorted by key — identical byte order
//!   across all platforms and Rust versions. No HashMap permitted here.
//!
//! Serialization: Vec<u8> for signatures (serde supports Vec, not [u8; 64]).
//!   In practice always 64 bytes; validated by Signature::try_from at verify time.

use std::collections::BTreeMap;
use std::convert::TryFrom;

use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::audit::AuditLogger;

/// A validator entry in the active registry.
/// BTreeMap key = node_id string; sorted iteration is deterministic.
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ValidatorEntry {
    pub node_id: String,
    pub public_key: [u8; 32],
}

/// One node's Ed25519 signature over the topology_hash.
/// signature is Vec<u8> (always 64 bytes) — serde does not support [u8; 64] natively.
/// Fields in alphabetical order → serde_json output matches JCS key ordering.
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct NodeSignature {
    pub node_id: String,
    pub signature: Vec<u8>,
}

/// Stateless quorum proof.
/// Fields declared alphabetically → serde_json serialization is JCS-compatible.
/// topology_hash is the signed message (SHA-256 of the canonical governance state).
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct QuorumProof {
    pub sequence: u64,
    pub signatures: Vec<NodeSignature>,
    pub topology_hash: [u8; 32],
}

/// Result of edge verification.
#[derive(Debug, Serialize)]
pub struct EdgeVerificationResult {
    pub is_quorum_verified: bool,
    pub sequence: u64,
    pub total_count: usize,
    pub valid_count: usize,
}

/// Returned on verification failure.
#[derive(Debug)]
pub struct EdgeVerifierError(pub &'static str);

/// Verify BFT quorum at the edge — stateless, no disk, no sockets, WASM-compatible.
///
/// Each validator in `registry` is looked up against the proof's signature list.
/// A signature is valid iff Ed25519 check passes against topology_hash.
///
/// Threshold (integer, no f64): valid_count * 1_000_000 >= total_count * 618_034
/// 618_034 / 1_000_000 ≈ 0.618034 — holonic 1/φ constant (shared with swarm.ts).
///
/// BTreeMap iteration is sorted → identical evaluation order on all platforms.
pub fn verify_quorum_at_edge(
    proof: &QuorumProof,
    registry: &BTreeMap<String, ValidatorEntry>,
) -> Result<EdgeVerificationResult, EdgeVerifierError> {
    if proof.signatures.is_empty() {
        return Err(EdgeVerifierError("[EDGE_REJECT] No signatures in proof"));
    }
    if registry.is_empty() {
        return Err(EdgeVerifierError("[EDGE_REJECT] Empty validator registry"));
    }

    let message = &proof.topology_hash;
    let mut valid_count: usize = 0;
    let total_count: usize = registry.len();

    // BTreeMap iterates in sorted key order — deterministic across all platforms.
    for (node_id, entry) in registry {
        if let Some(node_sig) = proof.signatures.iter().find(|s| &s.node_id == node_id) {
            if let Ok(key) = VerifyingKey::from_bytes(&entry.public_key) {
                if let Ok(sig) = Signature::try_from(node_sig.signature.as_slice()) {
                    if key.verify(message, &sig).is_ok() {
                        valid_count += 1;
                    }
                }
            }
        }
    }

    // Integer 1/φ threshold — avoids f64 cross-platform floating-point issues.
    // 618_034 / 1_000_000 ≈ 0.618034 (within 1e-6 of (√5−1)/2)
    let is_quorum_verified = valid_count * 1_000_000 >= total_count * 618_034;

    Ok(EdgeVerificationResult {
        is_quorum_verified,
        sequence: proof.sequence,
        total_count,
        valid_count,
    })
}

/// Immutable validator registry with SHA-256 content hash.
/// Immutable builder pattern: `.register()` returns a new registry, leaving the original unchanged.
/// BTreeMap internally ensures deterministic key iteration (sorted by node_id).
#[derive(Clone, Debug)]
pub struct ValidatorRegistry {
    map: BTreeMap<String, ValidatorEntry>,
    /// SHA-256 of serde_json serialization of all ValidatorEntry values in sorted node_id order.
    registry_hash: [u8; 32],
}

impl ValidatorRegistry {
    /// Create an empty registry. registry_hash = SHA-256 of empty bytes.
    pub fn empty() -> Self {
        let registry_hash = Sha256::digest(b"").into();
        ValidatorRegistry { map: BTreeMap::new(), registry_hash }
    }

    /// Register a new validator. Returns a new registry with the entry added.
    /// Rejects duplicate node_id.
    pub fn register(mut self, entry: ValidatorEntry) -> Result<ValidatorRegistry, EdgeVerifierError> {
        if self.map.contains_key(&entry.node_id) {
            return Err(EdgeVerifierError("[REGISTRY_REJECT] Duplicate node_id"));
        }
        self.map.insert(entry.node_id.clone(), entry);
        let hash = Self::compute_hash(&self.map);
        Ok(ValidatorRegistry { map: self.map, registry_hash: hash })
    }

    pub fn size(&self) -> usize {
        self.map.len()
    }

    pub fn registry_hash(&self) -> &[u8; 32] {
        &self.registry_hash
    }

    pub fn registry_hash_hex(&self) -> String {
        self.registry_hash.iter().map(|b| format!("{:02x}", b)).collect()
    }

    pub fn as_map(&self) -> &BTreeMap<String, ValidatorEntry> {
        &self.map
    }

    /// Minimum valid_count for quorum: ceiling of size * 618_034 / 1_000_000.
    pub fn quorum_size(&self) -> usize {
        let n = self.map.len();
        (n * 618_034 + 999_999) / 1_000_000
    }

    fn compute_hash(map: &BTreeMap<String, ValidatorEntry>) -> [u8; 32] {
        // Serialize all entries in sorted key order to produce a stable content hash.
        let entries: Vec<&ValidatorEntry> = map.values().collect();
        let json = serde_json::to_vec(&entries).unwrap_or_default();
        Sha256::digest(&json).into()
    }
}

/// Log a quorum verification result to the audit chain.
/// Returns the entry_hash produced by the logger.
pub fn log_verification_result(logger: &mut AuditLogger, result: &EdgeVerificationResult) -> String {
    logger.log("EDGE_BFT_QUORUM_VERIFY", result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Signer, SigningKey};

    fn make_registry_and_keys(n: usize) -> (BTreeMap<String, ValidatorEntry>, Vec<SigningKey>) {
        let mut registry = BTreeMap::new();
        let mut signing_keys = Vec::new();
        for i in 0..n {
            let seed = [i as u8 + 1; 32];
            let sk = SigningKey::from_bytes(&seed);
            let pk: [u8; 32] = sk.verifying_key().to_bytes();
            let node_id = format!("node-{:03}", i);
            registry.insert(node_id.clone(), ValidatorEntry { node_id, public_key: pk });
            signing_keys.push(sk);
        }
        (registry, signing_keys)
    }

    fn make_proof(
        sequence: u64,
        topology_hash: [u8; 32],
        signing_keys: &[SigningKey],
        registry: &BTreeMap<String, ValidatorEntry>,
        sign_count: usize,
    ) -> QuorumProof {
        let mut signatures = Vec::new();
        for (i, (node_id, _)) in registry.iter().enumerate().take(sign_count) {
            let sig_bytes: Vec<u8> = signing_keys[i].sign(&topology_hash).to_bytes().to_vec();
            signatures.push(NodeSignature { node_id: node_id.clone(), signature: sig_bytes });
        }
        QuorumProof { sequence, signatures, topology_hash }
    }

    #[test]
    fn empty_signatures_returns_err() {
        let (registry, _) = make_registry_and_keys(3);
        let proof = QuorumProof { sequence: 1, signatures: vec![], topology_hash: [0u8; 32] };
        assert!(verify_quorum_at_edge(&proof, &registry).is_err());
    }

    #[test]
    fn empty_registry_returns_err() {
        let registry: BTreeMap<String, ValidatorEntry> = BTreeMap::new();
        let proof = QuorumProof {
            sequence: 1,
            signatures: vec![NodeSignature { node_id: "x".into(), signature: vec![0u8; 64] }],
            topology_hash: [0u8; 32],
        };
        assert!(verify_quorum_at_edge(&proof, &registry).is_err());
    }

    #[test]
    fn all_valid_signatures_quorum_verified() {
        let (registry, keys) = make_registry_and_keys(5);
        let hash = [42u8; 32];
        let proof = make_proof(1, hash, &keys, &registry, 5);
        let result = verify_quorum_at_edge(&proof, &registry).unwrap();
        assert!(result.is_quorum_verified);
        assert_eq!(result.valid_count, 5);
        assert_eq!(result.total_count, 5);
    }

    #[test]
    fn five_of_eight_meets_phi_threshold() {
        // 5/8 = 0.625 >= 0.618034 → quorum reached
        let (registry, keys) = make_registry_and_keys(8);
        let hash = [7u8; 32];
        let proof = make_proof(2, hash, &keys, &registry, 5);
        let result = verify_quorum_at_edge(&proof, &registry).unwrap();
        assert!(result.is_quorum_verified);
        assert_eq!(result.valid_count, 5);
    }

    #[test]
    fn four_of_eight_fails_phi_threshold() {
        // 4/8 = 0.500 < 0.618034 → quorum NOT reached
        let (registry, keys) = make_registry_and_keys(8);
        let hash = [8u8; 32];
        let proof = make_proof(3, hash, &keys, &registry, 4);
        let result = verify_quorum_at_edge(&proof, &registry).unwrap();
        assert!(!result.is_quorum_verified);
        assert_eq!(result.valid_count, 4);
    }

    #[test]
    fn no_valid_signatures_quorum_not_verified() {
        let (registry, _) = make_registry_and_keys(3);
        let hash = [1u8; 32];
        let mut signatures = Vec::new();
        for node_id in registry.keys() {
            signatures.push(NodeSignature { node_id: node_id.clone(), signature: vec![0u8; 64] });
        }
        let proof = QuorumProof { sequence: 4, signatures, topology_hash: hash };
        let result = verify_quorum_at_edge(&proof, &registry).unwrap();
        assert!(!result.is_quorum_verified);
        assert_eq!(result.valid_count, 0);
    }

    #[test]
    fn tampered_topology_hash_invalidates_signatures() {
        let (registry, keys) = make_registry_and_keys(5);
        let original_hash = [10u8; 32];
        let tampered_hash = [11u8; 32];
        let mut proof = make_proof(5, original_hash, &keys, &registry, 5);
        // Replace topology_hash with tampered version; signatures still over original_hash
        proof = QuorumProof { topology_hash: tampered_hash, ..proof };
        let result = verify_quorum_at_edge(&proof, &registry).unwrap();
        assert!(!result.is_quorum_verified);
        assert_eq!(result.valid_count, 0);
    }

    #[test]
    fn deterministic_three_times() {
        let (registry, keys) = make_registry_and_keys(7);
        let hash = [99u8; 32];
        let proof = make_proof(6, hash, &keys, &registry, 5);
        let r1 = verify_quorum_at_edge(&proof, &registry).unwrap();
        let r2 = verify_quorum_at_edge(&proof, &registry).unwrap();
        let r3 = verify_quorum_at_edge(&proof, &registry).unwrap();
        assert_eq!(r1.is_quorum_verified, r2.is_quorum_verified);
        assert_eq!(r2.is_quorum_verified, r3.is_quorum_verified);
        assert_eq!(r1.valid_count, r2.valid_count);
        assert_eq!(r2.valid_count, r3.valid_count);
    }

    #[test]
    fn integer_threshold_approximates_phi() {
        // 618_034 / 1_000_000 should approximate 1/φ = (√5-1)/2 to within 1e-6
        let phi_recip = (5.0_f64.sqrt() - 1.0) / 2.0;
        let integer_approx = 618_034.0_f64 / 1_000_000.0;
        assert!((phi_recip - integer_approx).abs() < 1e-6);
    }

    #[test]
    fn sequence_propagated_to_result() {
        let (registry, keys) = make_registry_and_keys(3);
        let hash = [5u8; 32];
        let proof = make_proof(42, hash, &keys, &registry, 3);
        let result = verify_quorum_at_edge(&proof, &registry).unwrap();
        assert_eq!(result.sequence, 42);
    }

    #[test]
    fn total_count_is_registry_size_not_proof_signature_count() {
        // total_count = registry size; valid_count = matching valid signatures
        let (registry, keys) = make_registry_and_keys(10);
        let hash = [3u8; 32];
        // Only sign 7 of 10
        let proof = make_proof(7, hash, &keys, &registry, 7);
        let result = verify_quorum_at_edge(&proof, &registry).unwrap();
        assert_eq!(result.total_count, 10);
        assert_eq!(result.valid_count, 7);
        // 7/10 = 0.7 >= 0.618034 → quorum
        assert!(result.is_quorum_verified);
    }

    // ValidatorRegistry tests

    fn make_entry(node_id: &str, seed_byte: u8) -> ValidatorEntry {
        let seed = [seed_byte; 32];
        let sk = SigningKey::from_bytes(&seed);
        ValidatorEntry { node_id: node_id.to_string(), public_key: sk.verifying_key().to_bytes() }
    }

    #[test]
    fn registry_empty_has_size_zero() {
        let r = ValidatorRegistry::empty();
        assert_eq!(r.size(), 0);
    }

    #[test]
    fn registry_empty_hash_is_sha256_of_empty() {
        use sha2::{Digest, Sha256};
        let r = ValidatorRegistry::empty();
        let expected: [u8; 32] = Sha256::digest(b"").into();
        assert_eq!(r.registry_hash(), &expected);
    }

    #[test]
    fn registry_register_adds_entry() {
        let r = ValidatorRegistry::empty()
            .register(make_entry("node-001", 1)).unwrap();
        assert_eq!(r.size(), 1);
        assert!(r.as_map().contains_key("node-001"));
    }

    #[test]
    fn registry_duplicate_node_id_rejected() {
        let r = ValidatorRegistry::empty()
            .register(make_entry("node-001", 1)).unwrap();
        let result = r.register(make_entry("node-001", 2));
        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(err.0.contains("Duplicate"));
    }

    #[test]
    fn registry_hash_changes_after_registration() {
        let r0 = ValidatorRegistry::empty();
        let r1 = r0.clone().register(make_entry("node-001", 1)).unwrap();
        assert_ne!(r0.registry_hash(), r1.registry_hash());
    }

    #[test]
    fn registry_hash_is_deterministic() {
        let r1 = ValidatorRegistry::empty()
            .register(make_entry("node-a", 1)).unwrap()
            .register(make_entry("node-b", 2)).unwrap();
        let r2 = ValidatorRegistry::empty()
            .register(make_entry("node-a", 1)).unwrap()
            .register(make_entry("node-b", 2)).unwrap();
        assert_eq!(r1.registry_hash(), r2.registry_hash());
    }

    #[test]
    fn registry_hash_hex_is_64_chars() {
        let r = ValidatorRegistry::empty()
            .register(make_entry("node-001", 1)).unwrap();
        assert_eq!(r.registry_hash_hex().len(), 64);
    }

    #[test]
    fn registry_quorum_size_ceiling() {
        // n=10: ceiling(10 * 618_034 / 1_000_000) = ceiling(6.18034) = 7
        let r = (0..10u8).fold(ValidatorRegistry::empty(), |acc, i| {
            acc.register(make_entry(&format!("node-{:03}", i), i + 1)).unwrap()
        });
        assert_eq!(r.quorum_size(), 7);
    }

    #[test]
    fn registry_quorum_size_empty_is_zero() {
        let r = ValidatorRegistry::empty();
        assert_eq!(r.quorum_size(), 0);
    }

    #[test]
    fn registry_as_map_usable_with_verify_quorum() {
        let seed_sk = SigningKey::from_bytes(&[1u8; 32]);
        let pk = seed_sk.verifying_key().to_bytes();
        let r = ValidatorRegistry::empty()
            .register(ValidatorEntry { node_id: "node-000".to_string(), public_key: pk })
            .unwrap();
        let hash = [9u8; 32];
        let sig_bytes: Vec<u8> = seed_sk.sign(&hash).to_bytes().to_vec();
        let proof = QuorumProof {
            sequence: 1,
            signatures: vec![NodeSignature { node_id: "node-000".to_string(), signature: sig_bytes }],
            topology_hash: hash,
        };
        let result = verify_quorum_at_edge(&proof, r.as_map()).unwrap();
        assert!(result.is_quorum_verified);
    }

    // log_verification_result tests

    #[test]
    fn log_verification_result_returns_64_char_hex() {
        let mut logger = AuditLogger::new();
        let result = EdgeVerificationResult {
            is_quorum_verified: true,
            sequence: 42,
            total_count: 10,
            valid_count: 7,
        };
        let hash = log_verification_result(&mut logger, &result);
        assert_eq!(hash.len(), 64);
    }

    #[test]
    fn log_verification_result_appends_to_chain() {
        let mut logger = AuditLogger::new();
        assert_eq!(logger.len(), 0);
        let result = EdgeVerificationResult {
            is_quorum_verified: false,
            sequence: 1,
            total_count: 5,
            valid_count: 2,
        };
        log_verification_result(&mut logger, &result);
        assert_eq!(logger.len(), 1);
        let (valid, _) = logger.verify_chain();
        assert!(valid);
    }

    #[test]
    fn log_verification_result_chain_verifies_after_two_entries() {
        let mut logger = AuditLogger::new();
        for i in 0..2u64 {
            let r = EdgeVerificationResult {
                is_quorum_verified: i % 2 == 0,
                sequence: i,
                total_count: 8,
                valid_count: 5,
            };
            log_verification_result(&mut logger, &r);
        }
        let (valid, first_bad) = logger.verify_chain();
        assert!(valid);
        assert!(first_bad.is_none());
    }
}
