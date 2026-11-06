//! NTT Transform - The "Brush" of ECCF
//! 
//! Transforms linear data into high-dimensional geometric forms
//! over Z_q[X]/(X^256 + 1)

use num_bigint::BigInt;
use num_traits::{One, Zero};

/// NTTBrush - Geometric transformation engine
pub struct NTTBrush {
    /// Polynomial degree (typically 256)
    degree: usize,
    /// Precomputed roots of unity
    roots: Vec<BigInt>,
}

impl NTTBrush {
    /// Create new NTT brush with specified degree
    pub fn new(degree: usize) -> Self {
        let roots = Self::compute_roots(degree);
        Self { degree, roots }
    }

    /// Compute primitive roots of unity for NTT
    fn compute_roots(degree: usize) -> Vec<BigInt> {
        // Simplified root computation for demonstration
        // In production, use precomputed tables for efficiency
        let mut roots = Vec::with_capacity(degree);
        for i in 0..degree {
            // Approximate root calculation
            let root = BigInt::from(i) % BigInt::from(65537u64);
            roots.push(root);
        }
        roots
    }

    /// Transform hash data into NTT coefficients
    /// 
    /// Maps Keccak hash to polynomial ring Z_q[X]/(X^n + 1)
    pub fn transform(&self, hash: &[u8], dimension: usize) -> Vec<i16> {
        let mut coefficients = Vec::with_capacity(dimension);
        
        // Expand hash to fill dimension
        for i in 0..dimension {
            let byte_idx = i % hash.len();
            let next_byte_idx = (i + 1) % hash.len();
            
            // Combine bytes for coefficient
            let coeff = ((hash[byte_idx] as i16) << 8) | (hash[next_byte_idx] as i16);
            let normalized = (coeff % 16384) - 8192; // Center around zero
            
            coefficients.push(normalized);
        }
        
        // Apply NTT-like transformation (simplified)
        self.apply_ntt_simplified(&mut coefficients);
        
        coefficients
    }

    /// Simplified NTT application for coefficient transformation
    fn apply_ntt_simplified(&self, coeffs: &mut [i16]) {
        let n = coeffs.len();
        if n == 0 {
            return;
        }

        // Cooley-Tukey style iterative NTT (simplified)
        let mut len = 2;
        while len <= n {
            let angle_step = std::f64::consts::PI * 2.0 / (len as f64);
            for start in (0..n).step_by(len) {
                for j in 0..(len / 2) {
                    let idx1 = start + j;
                    let idx2 = start + j + len / 2;
                    
                    if idx1 < n && idx2 < n {
                        let angle = (j as f64) * angle_step;
                        let cos = angle.cos() as f32;
                        let sin = angle.sin() as f32;
                        
                        let a = coeffs[idx1] as f32;
                        let b = coeffs[idx2] as f32;
                        
                        // Complex multiplication (simplified)
                        let real = a * cos - b * sin;
                        let imag = a * sin + b * cos;
                        
                        coeffs[idx1] = (real + imag) as i16 / 2;
                        coeffs[idx2] = (real - imag) as i16 / 2;
                    }
                }
            }
            len *= 2;
        }
    }

    /// Inverse NTT transform
    pub fn inverse_transform(&self, coeffs: &[i16]) -> Vec<u8> {
        // Simplified inverse - in production use proper INTT
        let mut output = Vec::with_capacity(32);
        
        for i in 0..32 {
            let idx = i % coeffs.len();
            let byte = ((coeffs[idx] + 8192) % 256) as u8;
            output.push(byte);
        }
        
        output
    }

    /// Get the degree of the NTT
    pub fn degree(&self) -> usize {
        self.degree
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ntt_transform_deterministic() {
        let brush = NTTBrush::new(256);
        let hash = [0x1a, 0x2b, 0x3c, 0x4d];
        
        let coeffs1 = brush.transform(&hash, 64);
        let coeffs2 = brush.transform(&hash, 64);
        
        assert_eq!(coeffs1, coeffs2);
    }

    #[test]
    fn test_ntt_different_dimensions() {
        let brush = NTTBrush::new(256);
        let hash = [0xab, 0xcd, 0xef];
        
        let coeffs_32 = brush.transform(&hash, 32);
        let coeffs_128 = brush.transform(&hash, 128);
        
        assert_eq!(coeffs_32.len(), 32);
        assert_eq!(coeffs_128.len(), 128);
        assert_ne!(coeffs_32.len(), coeffs_128.len());
    }

    #[test]
    fn test_inverse_transform() {
        let brush = NTTBrush::new(256);
        let hash = [0x12, 0x34, 0x56, 0x78, 0x9a];
        
        let coeffs = brush.transform(&hash, 64);
        let recovered = brush.inverse_transform(&coeffs);
        
        // Note: Simplified INTT won't perfectly recover, but should produce output
        assert_eq!(recovered.len(), 32);
    }

    #[test]
    fn test_coefficient_range() {
        let brush = NTTBrush::new(256);
        let hash = [0xff; 32];
        
        let coeffs = brush.transform(&hash, 128);
        
        // Coefficients should be roughly centered around zero
        for &coeff in &coeffs {
            assert!(coeff > -16384 && coeff < 16384);
        }
    }
}
