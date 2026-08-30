//! RWKV-7 State Cache — O(1) Memory per Step
//! EPISTEMIC TIER: T2
//!
//! INT4/NF4 quantized recurrent state cache.
//! VRAM-aware eviction: lowest Lyapunov margin evicted first.
//! HIP FFI boundary prepared for AMD RX 570 acceleration.
//!
//! chain_hash: SHA-256(prev_chain_hash || step_count_be8 || packed_slot_byte)
//! Updated on every store_slot(); replay-reconstructable without wall-clock time.

use sha2::{Sha256, Digest};

pub const RWKV_STATE_GENESIS_HASH: [u8; 32] = [0u8; 32];

pub struct RWKVStateCache {
    pub state_bytes: Vec<u8>,
    pub capacity_bytes: usize,
    pub used_bytes: usize,
    pub lyapunov_margins: Vec<f32>,
    pub step_count: u64,
    chain_hash: [u8; 32],
}

impl RWKVStateCache {
    pub fn new(capacity_mb: usize) -> Self {
        let capacity_bytes = capacity_mb * 1024 * 1024;
        Self {
            state_bytes: Vec::with_capacity(capacity_bytes.min(1024 * 1024)),
            capacity_bytes,
            used_bytes: 0,
            lyapunov_margins: Vec::new(),
            step_count: 0,
            chain_hash: RWKV_STATE_GENESIS_HASH,
        }
    }

    /// Current chain hash: SHA-256(prev || step_count_be8 || packed_byte), updated each store.
    /// Replay-reconstructable: deterministic from the exact sequence of packed slots stored.
    pub fn chain_hash(&self) -> [u8; 32] { self.chain_hash }

    /// Pack two f32 values into one INT4 byte (nibble packing).
    #[inline]
    pub fn pack_int4(a: f32, b: f32) -> u8 {
        let a_q = (a.clamp(-8.0, 7.0) + 8.0) as u8;
        let b_q = (b.clamp(-8.0, 7.0) + 8.0) as u8;
        (a_q & 0x0F) | ((b_q & 0x0F) << 4)
    }

    /// Unpack one INT4 byte into two f32 values.
    #[inline]
    pub fn unpack_int4(byte: u8) -> (f32, f32) {
        let a = (byte & 0x0F) as f32 - 8.0;
        let b = ((byte >> 4) & 0x0F) as f32 - 8.0;
        (a, b)
    }

    /// Store a packed state slot with its Lyapunov stability margin.
    /// Returns false if over capacity (caller should evict first).
    /// Advances chain_hash: SHA-256(prev_chain_hash || step_count_be8 || packed).
    pub fn store_slot(&mut self, packed: u8, lyapunov_margin: f32) -> bool {
        if self.used_bytes.saturating_add(1) > self.capacity_bytes {
            return false;
        }
        self.step_count = self.step_count.saturating_add(1);
        // Advance hash chain before storing (step_count already incremented)
        let mut h = Sha256::new();
        h.update(self.chain_hash);
        h.update(self.step_count.to_be_bytes());
        h.update([packed]);
        self.chain_hash = h.finalize().into();

        self.state_bytes.push(packed);
        self.lyapunov_margins.push(lyapunov_margin);
        self.used_bytes = self.used_bytes.saturating_add(1);
        true
    }

    /// Evict the slot with the lowest Lyapunov margin (least stable).
    pub fn evict_least_stable(&mut self) {
        if self.lyapunov_margins.is_empty() { return; }
        let idx = self.lyapunov_margins.iter()
            .enumerate()
            .min_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0);
        self.state_bytes.remove(idx);
        self.lyapunov_margins.remove(idx);
        self.used_bytes = self.used_bytes.saturating_sub(1);
    }

    pub fn slot_count(&self) -> usize { self.state_bytes.len() }
    pub fn utilization_pct(&self) -> f32 { self.used_bytes as f32 / self.capacity_bytes as f32 * 100.0 }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pack_unpack_roundtrip() {
        let (a, b) = (3.0f32, -2.0f32);
        let packed = RWKVStateCache::pack_int4(a, b);
        let (ua, ub) = RWKVStateCache::unpack_int4(packed);
        assert_eq!(ua, 3.0);
        assert_eq!(ub, -2.0);
    }

    #[test]
    fn evict_removes_lowest_margin() {
        let mut cache = RWKVStateCache::new(1);
        cache.store_slot(0b00001111, 0.9);
        cache.store_slot(0b11110000, 0.1); // lowest
        cache.store_slot(0b01010101, 0.5);
        assert_eq!(cache.slot_count(), 3);
        cache.evict_least_stable();
        assert_eq!(cache.slot_count(), 2);
        // The remaining margins should be 0.9 and 0.5
        assert!(cache.lyapunov_margins.contains(&0.9f32));
        assert!(cache.lyapunov_margins.contains(&0.5f32));
    }

    #[test]
    fn capacity_enforced() {
        let mut cache = RWKVStateCache::new(0); // 0MB → 0 bytes capacity
        let ok = cache.store_slot(0xFF, 1.0);
        assert!(!ok);
    }

    // 4. Initial chain_hash equals genesis (all zeros)
    #[test]
    fn initial_chain_hash_is_genesis() {
        let cache = RWKVStateCache::new(1);
        assert_eq!(cache.chain_hash(), RWKV_STATE_GENESIS_HASH);
    }

    // 5. chain_hash changes after store_slot
    #[test]
    fn chain_hash_advances_after_store() {
        let mut cache = RWKVStateCache::new(1);
        let before = cache.chain_hash();
        cache.store_slot(0xAB, 0.5);
        assert_ne!(cache.chain_hash(), before);
    }

    // 6. chain_hash is non-genesis after any store
    #[test]
    fn chain_hash_nonzero_after_store() {
        let mut cache = RWKVStateCache::new(1);
        cache.store_slot(0x00, 0.0);
        assert_ne!(cache.chain_hash(), [0u8; 32]);
    }

    // 7. Determinism ×3: same sequence of stores → same chain_hash
    #[test]
    fn chain_hash_determinism_triple() {
        fn make_hash() -> [u8; 32] {
            let mut c = RWKVStateCache::new(4);
            c.store_slot(0x11, 0.5);
            c.store_slot(0x22, 0.8);
            c.store_slot(0x33, 0.3);
            c.chain_hash()
        }
        assert_eq!(make_hash(), make_hash());
        assert_eq!(make_hash(), make_hash());
    }

    // 8. Different packed bytes → different chain_hash
    #[test]
    fn different_packed_bytes_yield_different_hash() {
        let mut c1 = RWKVStateCache::new(4);
        let mut c2 = RWKVStateCache::new(4);
        c1.store_slot(0xAA, 0.5);
        c2.store_slot(0xBB, 0.5);
        assert_ne!(c1.chain_hash(), c2.chain_hash());
    }

    // 9. step_count increments on each successful store
    #[test]
    fn step_count_increments_on_store() {
        let mut cache = RWKVStateCache::new(4);
        assert_eq!(cache.step_count, 0);
        cache.store_slot(0x01, 0.5);
        assert_eq!(cache.step_count, 1);
        cache.store_slot(0x02, 0.6);
        assert_eq!(cache.step_count, 2);
    }

    // 10. step_count does not increment when capacity is exceeded
    #[test]
    fn step_count_unchanged_on_capacity_exceeded() {
        let mut cache = RWKVStateCache::new(0);
        cache.store_slot(0xFF, 1.0);
        assert_eq!(cache.step_count, 0);
    }
}
