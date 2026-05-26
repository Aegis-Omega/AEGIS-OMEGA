//! Gate 208: Geometric Variance Engine
//! Replaces flawed scalar sums with true tensor-alignment metrics.
//! Computes Mean Squared Error (MSE) between P, G, and E weight vectors.

use std::fmt::Debug;

/// Represents the operational weight of a specific triadic function.
/// In a production system, these would be high-dimensional tensor matrices.
#[derive(Debug, Clone)]
pub struct TensorWeights {
    pub planner: Vec<f64>,
    pub generator: Vec<f64>,
    pub evaluator: Vec<f64>,
}

impl TensorWeights {
    /// Creates new tensor weights with uniform initialization.
    pub fn new(size: usize, initial_value: f64) -> Self {
        Self {
            planner: vec![initial_value; size],
            generator: vec![initial_value; size],
            evaluator: vec![initial_value; size],
        }
    }

    /// Calculates the true geometric divergence using the mean squared error (MSE) 
    /// between the P, G, and E subspaces.
    /// 
    /// This exposes the scalar flaw: P=[1,0], G=[0,1], E=[0.5,0.5] has scalar sum=1.0 
    /// for all three, but geometric variance > 0 due to orthogonal misalignment.
    pub fn compute_geometric_variance(&self) -> f64 {
        let len = self.planner.len();
        if len == 0 { return 0.0; }
        if len != self.generator.len() || len != self.evaluator.len() {
            panic!("Tensor dimension mismatch");
        }

        let mut mse_pg = 0.0;
        let mut mse_pe = 0.0;
        let mut mse_ge = 0.0;

        for i in 0..len {
            mse_pg += (self.planner[i] - self.generator[i]).powi(2);
            mse_pe += (self.planner[i] - self.evaluator[i]).powi(2);
            mse_ge += (self.generator[i] - self.evaluator[i]).powi(2);
        }

        // Average MSE across all three pairwise comparisons
        (mse_pg + mse_pe + mse_ge) / (3.0 * len as f64)
    }

    /// Returns the scalar sums (flawed metric for comparison).
    pub fn compute_scalar_sums(&self) -> (f64, f64, f64) {
        let p_sum: f64 = self.planner.iter().sum();
        let g_sum: f64 = self.generator.iter().sum();
        let e_sum: f64 = self.evaluator.iter().sum();
        (p_sum, g_sum, e_sum)
    }

    /// Computes scalar variance (the flawed metric).
    pub fn compute_scalar_variance(&self) -> f64 {
        let (p, g, e) = self.compute_scalar_sums();
        let mean = (p + g + e) / 3.0;
        ((p - mean).powi(2) + (g - mean).powi(2) + (e - mean).powi(2)) / 3.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scalar_flaw_exposed() {
        // P=[1,0], G=[0,1], E=[0.5, 0.5]
        // Scalar sums are all 1.0. Scalar variance = 0.0.
        // But geometric variance (MSE) is > 0.
        let weights = TensorWeights {
            planner: vec![1.0, 0.0],
            generator: vec![0.0, 1.0],
            evaluator: vec![0.5, 0.5],
        };
        
        let scalar_var = weights.compute_scalar_variance();
        let geometric_var = weights.compute_geometric_variance();
        
        assert!((scalar_var - 0.0).abs() < 1e-9, "Scalar variance should be 0 (the flaw)");
        assert!(geometric_var > 0.1, "Geometric variance must detect orthogonal misalignment");
    }

    #[test]
    fn test_perfect_alignment() {
        // All vectors identical - both metrics should be 0
        let weights = TensorWeights {
            planner: vec![1.0, 2.0, 3.0],
            generator: vec![1.0, 2.0, 3.0],
            evaluator: vec![1.0, 2.0, 3.0],
        };
        
        let scalar_var = weights.compute_scalar_variance();
        let geometric_var = weights.compute_geometric_variance();
        
        assert!((scalar_var - 0.0).abs() < 1e-9);
        assert!((geometric_var - 0.0).abs() < 1e-9);
    }

    #[test]
    fn test_severe_misalignment() {
        // Extreme divergence
        let weights = TensorWeights {
            planner: vec![10.0, 0.0],
            generator: vec![0.0, 10.0],
            evaluator: vec![0.0, 0.0],
        };
        
        let geometric_var = weights.compute_geometric_variance();
        // Expected: MSE_pg = (100+100)/2=100, MSE_pe = (100+0)/2=50, MSE_ge = (0+100)/2=50
        // Average = (100+50+50)/3 = 66.67
        assert!((geometric_var - 66.666666).abs() < 0.001);
    }

    #[test]
    fn test_empty_tensor() {
        let weights = TensorWeights::new(0, 1.0);
        assert_eq!(weights.compute_geometric_variance(), 0.0);
    }
}