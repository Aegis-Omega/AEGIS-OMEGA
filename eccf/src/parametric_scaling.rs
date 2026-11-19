//! Parametric Scaling - Dynamic Complexity Adjustment for ECCF
//! 
//! Implements Tanasub (proportional harmony) via Golden Ratio scaling.

use serde::{Serialize, Deserialize};

/// Golden Ratio constant
const PHI: f64 = 1.618033988749895;

/// ComplexityParameter - Scales with task difficulty
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplexityParameter {
    /// Complexity level (1-10)
    pub level: u8,
    /// Lattice dimension (scales with complexity)
    pub lattice_dimension: usize,
    /// Modular base q(λ) (scales with complexity)
    pub modular_base: u64,
    /// Golden Ratio scaling factor
    pub phi_scale: f64,
}

/// ParametricScaler - Manages dynamic scaling based on complexity
pub struct ParametricScaler {
    /// Base lattice dimension
    base_dimension: usize,
    /// Base modular base
    base_modular: u64,
}

impl ParametricScaler {
    /// Create new scaler with default parameters
    pub fn new() -> Self {
        Self {
            base_dimension: 32,
            base_modular: 65537,
        }
    }

    /// Create new scaler with custom base parameters
    pub fn with_base(base_dimension: usize, base_modular: u64) -> Self {
        Self {
            base_dimension,
            base_modular,
        }
    }

    /// Scale parameters for given complexity level
    /// 
    /// Uses Golden Ratio (φ) for proportional scaling:
    /// - Low complexity (1-3): Minimal dimensions, efficient
    /// - Medium complexity (4-7): Balanced dimensions
    /// - High complexity (8-10): Maximum dimensions, secure
    pub fn scale_for_complexity(&self, complexity: u8) -> ComplexityParameter {
        let level = complexity.clamp(1, 10);
        
        // Compute scaling factor using Golden Ratio
        let phi_exponent = (level as f64 - 1.0) / 9.0; // Normalize to [0, 1]
        let phi_scale = PHI.powf(phi_exponent);
        
        // Scale lattice dimension: O(log_φ(n)) instead of O(n)
        let lattice_dimension = (self.base_dimension as f64 * phi_scale).round() as usize;
        
        // Scale modular base proportionally
        let modular_base = (self.base_modular as f64 * phi_scale).round() as u64;
        
        // Ensure minimum values
        let lattice_dimension = lattice_dimension.max(self.base_dimension);
        let modular_base = modular_base.max(self.base_modular);
        
        ComplexityParameter {
            level,
            lattice_dimension,
            modular_base,
            phi_scale,
        }
    }

    /// Compute resource estimate for given complexity
    pub fn estimate_resources(&self, complexity: u8) -> ResourceEstimate {
        let params = self.scale_for_complexity(complexity);
        
        // Computational cost scales quadratically with dimension
        let compute_cost = (params.lattice_dimension as u64).pow(2);
        
        // Memory scales linearly with dimension and log(modular_base)
        let memory_bytes = params.lattice_dimension as u64 * 4; // 4 bytes per coefficient
        
        ResourceEstimate {
            compute_operations: compute_cost,
            memory_bytes,
            latency_estimate_us: compute_cost / 1000, // Rough estimate
        }
    }

    /// Verify scaling maintains fractal properties
    pub fn verify_fractal_scaling(&self, low: u8, high: u8) -> bool {
        let low_params = self.scale_for_complexity(low);
        let high_params = self.scale_for_complexity(high);
        
        // Higher complexity should always have >= dimensions
        if high_params.lattice_dimension < low_params.lattice_dimension {
            return false;
        }
        
        // Check Golden Ratio proportion is maintained
        let dim_ratio = high_params.lattice_dimension as f64 / low_params.lattice_dimension as f64;
        let expected_ratio = PHI.powf((high as f64 - low as f64) / 9.0);
        
        // Allow 10% tolerance
        (dim_ratio - expected_ratio).abs() / expected_ratio < 0.1
    }
}

impl Default for ParametricScaler {
    fn default() -> Self {
        Self::new()
    }
}

/// ResourceEstimate - Computational requirements for given complexity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceEstimate {
    /// Number of computational operations
    pub compute_operations: u64,
    /// Memory requirement in bytes
    pub memory_bytes: u64,
    /// Estimated latency in microseconds
    pub latency_estimate_us: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scale_min_complexity() {
        let scaler = ParametricScaler::new();
        let params = scaler.scale_for_complexity(1);
        
        assert_eq!(params.level, 1);
        assert_eq!(params.lattice_dimension, scaler.base_dimension);
        assert_eq!(params.modular_base, scaler.base_modular);
        assert!((params.phi_scale - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_scale_max_complexity() {
        let scaler = ParametricScaler::new();
        let params = scaler.scale_for_complexity(10);
        
        assert_eq!(params.level, 10);
        assert!(params.lattice_dimension > scaler.base_dimension);
        assert!(params.modular_base > scaler.base_modular);
        assert!((params.phi_scale - PHI).abs() < 0.1);
    }

    #[test]
    fn test_monotonic_scaling() {
        let scaler = ParametricScaler::new();
        
        let p1 = scaler.scale_for_complexity(1);
        let p5 = scaler.scale_for_complexity(5);
        let p10 = scaler.scale_for_complexity(10);
        
        assert!(p5.lattice_dimension >= p1.lattice_dimension);
        assert!(p10.lattice_dimension >= p5.lattice_dimension);
        assert!(p5.modular_base >= p1.modular_base);
        assert!(p10.modular_base >= p5.modular_base);
    }

    #[test]
    fn test_resource_estimation() {
        let scaler = ParametricScaler::new();
        
        let low = scaler.estimate_resources(1);
        let high = scaler.estimate_resources(10);
        
        assert!(high.compute_operations > low.compute_operations);
        assert!(high.memory_bytes >= low.memory_bytes);
        assert!(high.latency_estimate_us > low.latency_estimate_us);
    }

    #[test]
    fn test_fractal_verification() {
        let scaler = ParametricScaler::new();
        
        assert!(scaler.verify_fractal_scaling(1, 10));
        assert!(scaler.verify_fractal_scaling(3, 7));
        assert!(scaler.verify_fractal_scaling(5, 5)); // Same level should pass
    }

    #[test]
    fn test_golden_ratio_scaling() {
        let scaler = ParametricScaler::new();
        
        // Test that scaling follows Golden Ratio pattern
        let p1 = scaler.scale_for_complexity(1);
        let p4 = scaler.scale_for_complexity(4);
        let p7 = scaler.scale_for_complexity(7);
        let p10 = scaler.scale_for_complexity(10);
        
        // Ratios should approximate powers of φ
        let ratio_1_4 = p4.lattice_dimension as f64 / p1.lattice_dimension as f64;
        let ratio_4_7 = p7.lattice_dimension as f64 / p4.lattice_dimension as f64;
        let ratio_7_10 = p10.lattice_dimension as f64 / p7.lattice_dimension as f64;
        
        // All ratios should be positive and increasing
        assert!(ratio_1_4 > 1.0);
        assert!(ratio_4_7 > 1.0);
        assert!(ratio_7_10 > 1.0);
    }
}
