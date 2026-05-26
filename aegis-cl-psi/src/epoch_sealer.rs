//! Gate 270 — Epoch Sealer: terminal epoch seal across all gossip subsystems (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Produces an EpochSeal that cryptographically binds the terminal state of all
//! gossip mesh subsystems at epoch close. The seal is a compact tamper-evident
//! proof that all subsystems were observed at the declared epoch.
//!
//! EpochSeal:
//!   epoch             — u64
//!   ledger_hash       — [u8; 32] (MeshLedger terminal_hash at epoch)
//!   consensus_hash    — [u8; 32] (ConsensusLedger last cert_hash at epoch, or genesis)
//!   topology_hash     — [u8; 32] (TopologyLog last snapshot_hash at epoch, or genesis)
//!   sync_hash         — [u8; 32] (SyncLog last sync_hash at epoch, or genesis)
//!   seal_hash         — SHA-256(epoch_be8 ‖ ledger_hash ‖ consensus_hash ‖ topology_hash ‖ sync_hash ‖ prev_seal_hash)
//!   prev_seal_hash    — [u8; 32]
//!
//! SealChain: hash-chained EpochSeals; latest(), seal_count(), verify_chain().

use sha2::{Sha256, Digest};

// ─── Epoch seal ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct EpochSeal {
    pub epoch:          u64,
    pub ledger_hash:    [u8; 32],
    pub consensus_hash: [u8; 32],
    pub topology_hash:  [u8; 32],
    pub sync_hash:      [u8; 32],
    pub seal_hash:      [u8; 32],
    pub prev_seal_hash: [u8; 32],
}

pub const SEAL_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_seal_hash(
    epoch:          u64,
    ledger_hash:    &[u8; 32],
    consensus_hash: &[u8; 32],
    topology_hash:  &[u8; 32],
    sync_hash:      &[u8; 32],
    prev:           &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(ledger_hash);
    h.update(consensus_hash);
    h.update(topology_hash);
    h.update(sync_hash);
    h.finalize().into()
}

pub fn build_seal(
    epoch:          u64,
    ledger_hash:    [u8; 32],
    consensus_hash: [u8; 32],
    topology_hash:  [u8; 32],
    sync_hash:      [u8; 32],
    prev_seal_hash: &[u8; 32],
) -> EpochSeal {
    let seal_hash = compute_seal_hash(
        epoch, &ledger_hash, &consensus_hash, &topology_hash, &sync_hash, prev_seal_hash);
    EpochSeal {
        epoch, ledger_hash, consensus_hash, topology_hash, sync_hash,
        seal_hash, prev_seal_hash: *prev_seal_hash,
    }
}

// ─── Seal chain ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SealChain {
    seals: Vec<EpochSeal>,
}

#[derive(Debug)]
pub enum SealError {
    StaleEpoch,
}

impl SealError {
    pub fn as_str(&self) -> &'static str { "stale epoch" }
}

impl SealChain {
    pub fn new() -> Self { Self { seals: Vec::new() } }

    pub fn len(&self) -> usize { self.seals.len() }
    pub fn is_empty(&self) -> bool { self.seals.is_empty() }
    pub fn seals(&self) -> &[EpochSeal] { &self.seals }
    pub fn latest(&self) -> Option<&EpochSeal> { self.seals.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.seals.last().map(|s| s.seal_hash).unwrap_or(SEAL_GENESIS_HASH)
    }

    /// Terminal seal hash — proof of all subsystem states at last epoch close.
    pub fn terminal_seal_hash(&self) -> [u8; 32] { self.last_hash() }

    pub fn seal_count(&self) -> usize { self.seals.len() }

    pub fn append(
        &mut self,
        epoch:          u64,
        ledger_hash:    [u8; 32],
        consensus_hash: [u8; 32],
        topology_hash:  [u8; 32],
        sync_hash:      [u8; 32],
    ) -> Result<&EpochSeal, SealError> {
        if let Some(last) = self.seals.last() {
            if epoch <= last.epoch {
                return Err(SealError::StaleEpoch);
            }
        }
        let prev = self.last_hash();
        let seal = build_seal(epoch, ledger_hash, consensus_hash, topology_hash, sync_hash, &prev);
        self.seals.push(seal);
        Ok(self.seals.last().unwrap())
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SEAL_GENESIS_HASH;
        for (i, seal) in self.seals.iter().enumerate() {
            if seal.prev_seal_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_seal_hash(
                seal.epoch,
                &seal.ledger_hash,
                &seal.consensus_hash,
                &seal.topology_hash,
                &seal.sync_hash,
                &seal.prev_seal_hash,
            );
            if recomputed != seal.seal_hash {
                return (false, Some(i));
            }
            expected_prev = seal.seal_hash;
        }
        (true, None)
    }
}

impl Default for SealChain {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn h(seed: u8) -> [u8; 32] { [seed; 32] }

    fn add_seal(chain: &mut SealChain, epoch: u64, seed: u8) {
        chain.append(
            epoch,
            h(seed),
            h(seed.wrapping_add(1)),
            h(seed.wrapping_add(2)),
            h(seed.wrapping_add(3)),
        ).unwrap();
    }

    // ── build_seal ────────────────────────────────────────────────────────────

    #[test]
    fn seal_hash_nonzero() {
        let s = build_seal(1, h(1), h(2), h(3), h(4), &SEAL_GENESIS_HASH);
        assert_ne!(s.seal_hash, [0u8; 32]);
    }

    #[test]
    fn seal_hash_deterministic() {
        let s1 = build_seal(1, h(1), h(2), h(3), h(4), &SEAL_GENESIS_HASH);
        let s2 = build_seal(1, h(1), h(2), h(3), h(4), &SEAL_GENESIS_HASH);
        assert_eq!(s1.seal_hash, s2.seal_hash);
    }

    #[test]
    fn different_ledger_hash_different_seal() {
        let s1 = build_seal(1, h(1), h(2), h(3), h(4), &SEAL_GENESIS_HASH);
        let s2 = build_seal(1, h(9), h(2), h(3), h(4), &SEAL_GENESIS_HASH);
        assert_ne!(s1.seal_hash, s2.seal_hash);
    }

    #[test]
    fn different_epoch_different_seal() {
        let s1 = build_seal(1, h(1), h(2), h(3), h(4), &SEAL_GENESIS_HASH);
        let s2 = build_seal(2, h(1), h(2), h(3), h(4), &SEAL_GENESIS_HASH);
        assert_ne!(s1.seal_hash, s2.seal_hash);
    }

    #[test]
    fn prev_seal_hash_in_output() {
        let prev = h(0xFF);
        let s = build_seal(1, h(1), h(2), h(3), h(4), &prev);
        assert_eq!(s.prev_seal_hash, prev);
    }

    // ── SealChain ─────────────────────────────────────────────────────────────

    #[test]
    fn new_chain_empty() {
        let c = SealChain::new();
        assert!(c.is_empty());
        assert_eq!(c.last_hash(), SEAL_GENESIS_HASH);
        assert_eq!(c.terminal_seal_hash(), SEAL_GENESIS_HASH);
        assert_eq!(c.seal_count(), 0);
    }

    #[test]
    fn append_chains() {
        let mut c = SealChain::new();
        add_seal(&mut c, 1, 10);
        add_seal(&mut c, 2, 20);
        assert_eq!(c.len(), 2);
        assert_eq!(c.seals()[1].prev_seal_hash, c.seals()[0].seal_hash);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut c = SealChain::new();
        add_seal(&mut c, 5, 10);
        assert!(matches!(
            c.append(5, h(1), h(2), h(3), h(4)),
            Err(SealError::StaleEpoch)
        ));
        assert!(matches!(
            c.append(4, h(1), h(2), h(3), h(4)),
            Err(SealError::StaleEpoch)
        ));
    }

    #[test]
    fn terminal_hash_matches_last_seal() {
        let mut c = SealChain::new();
        add_seal(&mut c, 1, 10);
        add_seal(&mut c, 2, 20);
        assert_eq!(c.terminal_seal_hash(), c.seals().last().unwrap().seal_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut c = SealChain::new();
        for e in 1..=6u64 {
            add_seal(&mut c, e, e as u8 * 10);
        }
        let (valid, broken) = c.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn tampered_seal_hash_fails_chain() {
        let mut c = SealChain::new();
        add_seal(&mut c, 1, 10);
        add_seal(&mut c, 2, 20);
        add_seal(&mut c, 3, 30);
        c.seals[1].seal_hash[0] ^= 0xFF;
        let (valid, broken) = c.verify_chain();
        assert!(!valid);
        assert_eq!(broken, Some(1));
    }

    #[test]
    fn fields_preserved() {
        let lh = h(0xAA);
        let ch = h(0xBB);
        let th = h(0xCC);
        let sh = h(0xDD);
        let mut c = SealChain::new();
        c.append(42, lh, ch, th, sh).unwrap();
        let seal = c.latest().unwrap();
        assert_eq!(seal.epoch, 42);
        assert_eq!(seal.ledger_hash,    lh);
        assert_eq!(seal.consensus_hash, ch);
        assert_eq!(seal.topology_hash,  th);
        assert_eq!(seal.sync_hash,      sh);
    }
}
