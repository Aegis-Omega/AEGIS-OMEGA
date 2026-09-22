//! Tanasub: Proportional Scaling (Dimension 4+)
//!
//! Calligraphy relies on Tanasub (harmony/proportion), often utilizing
//! the Golden Ratio (φ) to balance negative and positive space.
//!
//! Cognitive Translation: The Tanasub is Resource Allocation and Scalability.
//! As the system scales from local components to global ecosystems,
//! the computational load must scale proportionally, not exponentially.
//!
//! Fractal Architecture: Just as an arabesque pattern repeats infinitely
//! at different scales, the Sovereign Protocol must be fractal.
//! The rules governing a single line of code must be identical to the
//! rules governing the entire distributed system.

/// The Golden Ratio φ ≈ 1.618033988749895
pub const GOLDEN_RATIO: f64 = 1.618033988749895;

/// Inverse golden ratio for downscaling
pub const INV_GOLDEN_RATIO: f64 = 0.6180339887498949;

/// Base computational unit
#[derive(Debug, Clone)]
pub struct ComputationalUnit {
    /// CPU cycles (normalized)
    pub compute: f64,
    /// Memory bytes (normalized)
    pub memory: f64,
    /// Network bandwidth (normalized)
    pub network: f64,
}

impl ComputationalUnit {
    pub fn new(compute: f64, memory: f64, network: f64) -> Self {
        Self { compute, memory, network }
    }

    /// Scale all resources by a factor
    pub fn scale(&self, factor: f64) -> Self {
        Self {
            compute: self.compute * factor,
            memory: self.memory * factor,
            network: self.network * factor,
        }
    }
}

impl Default for ComputationalUnit {
    fn default() -> Self {
        Self {
            compute: 1.0,
            memory: 1.0,
            network: 1.0,
        }
    }
}

/// Resource allocation result
#[derive(Debug, Clone)]
pub struct ResourceAllocation {
    pub compute: f64,
    pub memory: f64,
    pub network: f64,
    pub scale_factor: f64,
    pub user_count: u64,
}

impl ResourceAllocation {
    pub fn new(compute: f64, memory: f64, network: f64, scale_factor: f64, users: u64) -> Self {
        Self {
            compute,
            memory,
            network,
            scale_factor,
            user_count: users,
        }
    }

    /// Check if allocation is proportional (not exponential)
    pub fn is_proportional(&self, base: &ComputationalUnit) -> bool {
        let compute_ratio = self.compute / base.compute;
        let memory_ratio = self.memory / base.memory;
        let network_ratio = self.network / base.network;

        // All ratios should be within 10% of each other
        let max_ratio = compute_ratio.max(memory_ratio).max(network_ratio);
        let min_ratio = compute_ratio.min(memory_ratio).min(network_ratio);

        (max_ratio - min_ratio) / min_ratio < 0.1
    }
}

/// FractalScaler: Ensures proportional scaling with Golden Ratio
pub struct FractalScaler {
    pub base_unit: ComputationalUnit,
    pub scale_factor: f64,
}

impl FractalScaler {
    /// Create a new FractalScaler with default base unit
    pub fn new() -> Self {
        Self {
            base_unit: ComputationalUnit::default(),
            scale_factor: 1.0,
        }
    }

    /// Create with custom base unit
    pub fn with_base(base: ComputationalUnit) -> Self {
        Self {
            base_unit: base,
            scale_factor: 1.0,
        }
    }

    /// Scale resources for given user count using Golden Ratio
    /// Ensures computational load scales proportionally, not exponentially
    pub fn scale(&self, users: u64) -> ResourceAllocation {
        // Use logarithmic scaling with Golden Ratio base
        // This ensures proportional growth: O(log_φ(n)) instead of O(n)
        let n = if users <= 1 {
            1.0
        } else {
            (users as f64).ln() / GOLDEN_RATIO.ln()
        };

        let scaled = self.base_unit.scale(n);

        ResourceAllocation::new(
            scaled.compute,
            scaled.memory,
            scaled.network,
            n,
            users,
        )
    }

    /// Scale with custom exponent (for different growth patterns)
    pub fn scale_with_exponent(&self, users: u64, exponent: f64) -> ResourceAllocation {
        let n = if users <= 1 {
            1.0
        } else {
            (users as f64).powf(exponent)
        };

        let scaled = self.base_unit.scale(n);

        ResourceAllocation::new(
            scaled.compute,
            scaled.memory,
            scaled.network,
            n,
            users,
        )
    }

    /// Verify fractal property: rules at scale s₁ ≡ rules at scale s₂
    pub fn verify_fractal_property(&self, users_small: u64, users_large: u64) -> bool {
        let alloc_small = self.scale(users_small);
        let alloc_large = self.scale(users_large);

        // Both allocations should maintain same proportions
        alloc_small.is_proportional(&self.base_unit) && 
        alloc_large.is_proportional(&self.base_unit)
    }

    /// Get optimal batch size for given user count (Golden Ratio optimized)
    pub fn optimal_batch_size(&self, users: u64) -> u64 {
        // Batch size grows with Golden Ratio
        let base = 10.0; // Minimum batch size
        let scale = (users as f64).ln() / GOLDEN_RATIO.ln();
        (base * scale).ceil() as u64
    }

    /// Calculate harmony index (how well-proportioned the scaling is)
    pub fn harmony_index(&self, actual: &ResourceAllocation) -> f64 {
        let expected = self.scale(actual.user_count);

        let compute_diff = (actual.compute - expected.compute).abs() / expected.compute.max(1.0);
        let memory_diff = (actual.memory - expected.memory).abs() / expected.memory.max(1.0);
        let network_diff = (actual.network - expected.network).abs() / expected.network.max(1.0);

        let avg_diff = (compute_diff + memory_diff + network_diff) / 3.0;

        // Convert to harmony score (1.0 = perfect, 0.0 = disharmonious)
        (1.0 - avg_diff).max(0.0)
    }
}

impl Default for FractalScaler {
    fn default() -> Self {
        Self::new()
    }
}

/// Tanasub Balance State for Khatt Loop Phase 5
pub struct TanasubState {
    pub current_scale: f64,
    pub target_users: u64,
    pub harmony_index: f64,
    pub is_balanced: bool,
}

impl TanasubState {
    pub fn new(target_users: u64) -> Self {
        Self {
            current_scale: 1.0,
            target_users,
            harmony_index: 1.0,
            is_balanced: false,
        }
    }

    pub fn evaluate(&mut self, scaler: &FractalScaler, actual: &ResourceAllocation) {
        self.harmony_index = scaler.harmony_index(actual);
        self.is_balanced = self.harmony_index > 0.9;
        self.current_scale = actual.scale_factor;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_golden_ratio_constant() {
        // Verify golden ratio precision
        assert!((GOLDEN_RATIO - 1.618033988749895).abs() < 1e-15);
        // Golden ratio property: φ² = φ + 1
        assert!((GOLDEN_RATIO * GOLDEN_RATIO - (GOLDEN_RATIO + 1.0)).abs() < 1e-14);
    }

    #[test]
    fn test_computational_unit_scaling() {
        let unit = ComputationalUnit::new(100.0, 200.0, 50.0);
        let scaled = unit.scale(2.0);

        assert!((scaled.compute - 200.0).abs() < 0.001);
        assert!((scaled.memory - 400.0).abs() < 0.001);
        assert!((scaled.network - 100.0).abs() < 0.001);
    }

    #[test]
    fn test_fractal_scaler_basic() {
        let scaler = FractalScaler::new();
        let alloc = scaler.scale(100);

        assert!(alloc.user_count == 100);
        assert!(alloc.scale_factor > 1.0);
        assert!(alloc.is_proportional(&scaler.base_unit));
    }

    #[test]
    fn test_fractal_scaler_single_user() {
        let scaler = FractalScaler::new();
        let alloc = scaler.scale(1);

        assert!(alloc.user_count == 1);
        assert!((alloc.scale_factor - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_fractal_property() {
        let scaler = FractalScaler::new();

        assert!(scaler.verify_fractal_property(10, 1000));
        assert!(scaler.verify_fractal_property(100, 10000));
    }

    #[test]
    fn test_optimal_batch_size() {
        let scaler = FractalScaler::new();

        let batch_10 = scaler.optimal_batch_size(10);
        let batch_100 = scaler.optimal_batch_size(100);
        let batch_1000 = scaler.optimal_batch_size(1000);

        assert!(batch_10 > 0);
        assert!(batch_100 >= batch_10);
        assert!(batch_1000 >= batch_100);
    }

    #[test]
    fn test_harmony_index_perfect() {
        let scaler = FractalScaler::new();
        let expected = scaler.scale(100);

        let harmony = scaler.harmony_index(&expected);
        assert!(harmony > 0.99); // Should be nearly perfect
    }

    #[test]
    fn test_harmony_index_imperfect() {
        let scaler = FractalScaler::new();
        let mut actual = scaler.scale(100);

        // Introduce imbalance
        actual.compute *= 2.0;

        let harmony = scaler.harmony_index(&actual);
        assert!(harmony < 1.0);
        assert!(harmony > 0.0);
    }

    #[test]
    fn test_tanasub_state() {
        let scaler = FractalScaler::new();
        let mut state = TanasubState::new(100);
        let alloc = scaler.scale(100);

        state.evaluate(&scaler, &alloc);

        assert!(state.harmony_index > 0.9);
        assert!(state.is_balanced);
    }

    #[test]
    fn test_resource_allocation_proportionality() {
        let base = ComputationalUnit::new(10.0, 10.0, 10.0);
        let alloc = ResourceAllocation::new(20.0, 20.0, 20.0, 2.0, 100);

        assert!(alloc.is_proportional(&base));

        // Non-proportional allocation
        let bad_alloc = ResourceAllocation::new(50.0, 20.0, 20.0, 2.0, 100);
        assert!(!bad_alloc.is_proportional(&base));
    }
}
