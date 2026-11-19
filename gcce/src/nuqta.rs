//! Nuqta: The Atomic Truth Unit (Dimension 0)
//!
//! In classical calligraphy, all proportions are derived from the Nuqta
//! (the rhombic dot made by the reed pen).
//!
//! Cognitive Translation: The Nuqta is the T0 Verified Fact.
//! It is the irreducible, cryptographically sealed atomic unit of data.
//!
//! Mathematical State: H(x) = S_genesis
//! No reasoning can proceed unless anchored to a verified Nuqta.

use sha2::{Sha256, Digest};

/// The Nuqta: Atomic truth unit anchored to Genesis Seal
#[derive(Debug, Clone)]
pub struct Nuqta {
    /// SHA-256 hash of the verified fact
    pub hash: [u8; 32],
    /// Reference to source in Genesis ledger
    pub source: &'static str,
    /// Sequence number of verification (not wall-clock time)
    pub verified_at: u64,
    /// Optional parent Nuqta for chained verification
    pub parent_hash: Option<[u8; 32]>,
}

impl Nuqta {
    /// Create a new Nuqta from raw bytes
    pub fn new(source: &'static str, data: &[u8], sequence: u64) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(data);
        let hash: [u8; 32] = hasher.finalize().into();

        Self {
            hash,
            source,
            verified_at: sequence,
            parent_hash: None,
        }
    }

    /// Create a child Nuqta linked to a parent
    pub fn with_parent(mut self, parent_hash: [u8; 32]) -> Self {
        self.parent_hash = Some(parent_hash);
        self
    }

    /// Verify this Nuqta against the Genesis Seal
    pub fn verify(&self, genesis_seal: &[u8; 32]) -> bool {
        self.hash == *genesis_seal
    }

    /// Verify chain of Nuqtas (for linked verification)
    pub fn verify_chain(&self, genesis_seal: &[u8; 32], ancestors: &[Nuqta]) -> bool {
        // Base case: direct genesis verification
        if self.verify(genesis_seal) {
            return true;
        }

        // Recursive case: verify parent chain
        if let Some(parent_hash) = self.parent_hash {
            for ancestor in ancestors {
                if ancestor.hash == parent_hash {
                    return ancestor.verify_chain(genesis_seal, ancestors);
                }
            }
        }

        false
    }

    /// Get the hash as hex string for debugging
    pub fn hash_hex(&self) -> String {
        hex::encode(&self.hash)
    }
}

/// Nuqta Registry: BTreeMap for deterministic iteration
pub type NuqtaRegistry = std::collections::BTreeMap<[u8; 32], Nuqta>;

/// Nuqta Verifier Engine
pub struct NuqtaVerifier {
    genesis_seal: [u8; 32],
    registry: NuqtaRegistry,
    sequence_counter: u64,
}

impl NuqtaVerifier {
    pub fn new(genesis_seal: [u8; 32]) -> Self {
        Self {
            genesis_seal,
            registry: NuqtaRegistry::new(),
            sequence_counter: 0,
        }
    }

    /// Inscribe a new Nuqta (Phase 1 of Khatt Loop)
    pub fn inscribe(&mut self, source: &'static str, data: &[u8]) -> Nuqta {
        let nuqta = Nuqta::new(source, data, self.sequence_counter);
        self.sequence_counter += 1;
        self.registry.insert(nuqta.hash, nuqta.clone());
        nuqta
    }

    /// Verify a Nuqta against genesis seal
    pub fn verify(&self, nuqta: &Nuqta) -> bool {
        nuqta.verify(&self.genesis_seal)
    }

    /// Get all verified Nuqtas
    pub fn verified_nuqtas(&self) -> Vec<&Nuqta> {
        self.registry
            .values()
            .filter(|n| n.verify(&self.genesis_seal))
            .collect()
    }

    /// Get chain length for a Nuqta
    pub fn chain_length(&self, nuqta: &Nuqta) -> usize {
        let mut count = 1;
        let mut current = nuqta.clone();

        while let Some(parent_hash) = current.parent_hash {
            if let Some(parent) = self.registry.get(&parent_hash) {
                count += 1;
                current = parent.clone();
            } else {
                break;
            }
        }

        count
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nuqta_creation() {
        let data = b"verified atomic fact";
        let nuqta = Nuqta::new("test_source", data, 0);

        assert_eq!(nuqta.source, "test_source");
        assert_eq!(nuqta.verified_at, 0);
        assert_eq!(nuqta.hash.len(), 32);
        assert!(nuqta.parent_hash.is_none());
    }

    #[test]
    fn test_nuqta_chain() {
        let genesis_data = b"genesis truth";
        let mut hasher = Sha256::new();
        hasher.update(genesis_data);
        let genesis_seal: [u8; 32] = hasher.finalize().into();

        let mut verifier = NuqtaVerifier::new(genesis_seal);

        // Inscribe genesis Nuqta
        let genesis_nuqta = verifier.inscribe("genesis", genesis_data);

        // Inscribe child Nuqta
        let child_data = b"derived fact";
        let child_nuqta = Nuqta::new("child", child_data, 1)
            .with_parent(genesis_nuqta.hash);

        // Verify chain
        let ancestors = vec![genesis_nuqta.clone()];
        assert!(child_nuqta.verify_chain(&genesis_seal, &ancestors));
    }

    #[test]
    fn test_nuqta_registry_determinism() {
        let genesis_seal = [0u8; 32];
        let mut verifier = NuqtaVerifier::new(genesis_seal);

        // Insert multiple Nuqtas
        for i in 0..5 {
            verifier.inscribe("test", format!("data {}", i).as_bytes());
        }

        // BTreeMap ensures deterministic iteration order
        let hashes: Vec<_> = verifier.registry.keys().collect();
        let mut sorted_hashes = hashes.clone();
        sorted_hashes.sort();

        assert_eq!(hashes, sorted_hashes);
    }

    #[test]
    fn test_chain_length() {
        let genesis_seal = [0u8; 32];
        let mut verifier = NuqtaVerifier::new(genesis_seal);

        let root = verifier.inscribe("root", b"root data");
        let child1 = verifier.inscribe("child1", b"child1 data");
        let child2 = verifier.inscribe("child2", b"child2 data");

        // Note: inscribe creates independent Nuqtas
        // Chain length is 1 for each (no parent links in inscribe)
        assert_eq!(verifier.chain_length(&root), 1);
        assert_eq!(verifier.chain_length(&child1), 1);
        assert_eq!(verifier.chain_length(&child2), 1);
    }
}
