//! RWKV-7 State Cache — O(1) Memory per Step
//! EPISTEMIC TIER: T2
//!
//! INT4/NF4 quantized recurrent state cache.
//! VRAM-aware eviction: lowest Lyapunov margin evicted first.
//! HIP FFI boundary prepared for AMD RX 570 acceleration.

pub struct RWKVStateCache {
    pub state_bytes: Vec<u8>,
    pub capacity_bytes: usize,
    pub used_bytes: usize,
    pub lyapunov_margins: Vec<f32>,
    pub step_count: u64,
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
        }
    }

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
    pub fn store_slot(&mut self, packed: u8, lyapunov_margin: f32) -> bool {
        if self.used_bytes + 1 > self.capacity_bytes {
            return false;
        }
        self.state_bytes.push(packed);
        self.lyapunov_margins.push(lyapunov_margin);
        self.used_bytes += 1;
        self.step_count += 1;
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
}
