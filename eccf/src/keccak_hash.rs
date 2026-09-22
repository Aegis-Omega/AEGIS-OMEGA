//! Keccak Hash - The "Ink" of ECCF
//! 
//! Fixes cognitive state into immutable cryptographic seal.

use sha3::{Keccak256, Digest};

/// KeccakInk - Cryptographic fixation process
pub struct KeccakInk {
    hasher: Keccak256,
}

impl KeccakInk {
    /// Create new Keccak hasher
    pub fn new() -> Self {
        Self {
            hasher: Keccak256::new(),
        }
    }

    /// Fixate input data into cryptographic seal
    /// 
    /// Returns 32-byte Keccak256 hash
    pub fn fixate(&self, input: &[u8]) -> [u8; 32] {
        let mut hasher = Keccak256::new();
        hasher.update(input);
        let result = hasher.finalize();
        let mut output = [0u8; 32];
        output.copy_from_slice(&result);
        output
    }

    /// Fixate with domain separation prefix
    pub fn fixate_with_domain(&self, domain: &[u8], input: &[u8]) -> [u8; 32] {
        let mut hasher = Keccak256::new();
        hasher.update(domain);
        hasher.update(input);
        let result = hasher.finalize();
        let mut output = [0u8; 32];
        output.copy_from_slice(&result);
        output
    }

    /// Verify hash matches expected
    pub fn verify(&self, input: &[u8], expected: &[u8; 32]) -> bool {
        self.fixate(input) == *expected
    }
}

impl Default for KeccakInk {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fixate_deterministic() {
        let ink = KeccakInk::new();
        let input = b"Test input";
        
        let hash1 = ink.fixate(input);
        let hash2 = ink.fixate(input);
        
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_fixate_different_inputs() {
        let ink = KeccakInk::new();
        
        let hash1 = ink.fixate(b"Input 1");
        let hash2 = ink.fixate(b"Input 2");
        
        assert_ne!(hash1, hash2);
    }

    #[test]
    fn test_domain_separation() {
        let ink = KeccakInk::new();
        let input = b"Same input";
        
        let hash1 = ink.fixate_with_domain(b"Domain A", input);
        let hash2 = ink.fixate_with_domain(b"Domain B", input);
        
        assert_ne!(hash1, hash2);
    }

    #[test]
    fn test_verification() {
        let ink = KeccakInk::new();
        let input = b"Verify this";
        let expected = ink.fixate(input);
        
        assert!(ink.verify(input, &expected));
        assert!(!ink.verify(b"Different", &expected));
    }
}
