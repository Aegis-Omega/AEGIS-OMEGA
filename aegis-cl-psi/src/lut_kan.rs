//! LUT-KAN Router — Precomputed INT8 Spline Tables
//! EPISTEMIC TIER: T2
//!
//! Nonlinear pathway mapping via 256-point INT8 spline tables.
//! Replaces dense FFNs with O(1) lookup + linear interpolation.
//! Quantized storage, dequantized on read for precision.

use crate::sgm_gate::RoutingMask;

pub struct LUTKANRouter {
    pub tables: Vec<[i8; 256]>,
    pub scale: f32,
    pub zero_point: i8,
}

impl LUTKANRouter {
    pub fn new(num_paths: usize, scale: f32, zero_point: i8) -> Self {
        // Identity spline stub — replace with precomputed KAN splines in production.
        let tables = vec![[0i8; 256]; num_paths];
        Self { tables, scale, zero_point }
    }

    #[inline]
    fn dequant(&self, val: i8) -> f32 {
        (val as f32 - self.zero_point as f32) * self.scale
    }

    /// Transform sparse activations via LUT linear interpolation.
    pub fn transform(&self, input: &[f32], mask: &RoutingMask) -> Vec<f32> {
        let mut output = vec![0.0f32; input.len()];
        for &idx in &mask.active_indices {
            if idx >= input.len() || idx >= self.tables.len() { continue; }
            let x = input[idx];
            let x_clamped = x.max(0.0).min(1.0);
            let pos = x_clamped * 255.0;
            let i = pos.floor() as usize;
            let frac = pos - i as f32;
            let i_next = (i + 1).min(255);

            let y0 = self.dequant(self.tables[idx][i]);
            let y1 = self.dequant(self.tables[idx][i_next]);
            output[idx] = y0 + frac * (y1 - y0);
        }
        output
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sgm_gate::RoutingMask;

    fn all_active(len: usize) -> RoutingMask {
        RoutingMask { active_indices: (0..len).collect(), entropy: 0.0, threshold_exceeded: false }
    }

    #[test]
    fn zero_table_yields_zero_output() {
        let router = LUTKANRouter::new(4, 1.0, 0);
        let input = vec![0.5f32; 4];
        let mask = all_active(4);
        let out = router.transform(&input, &mask);
        assert!(out.iter().all(|&v| v == 0.0));
    }

    #[test]
    fn out_of_bounds_index_ignored() {
        let router = LUTKANRouter::new(2, 1.0, 0);
        let input = vec![0.5f32; 4];
        let mask = RoutingMask {
            active_indices: vec![0, 1, 99],
            entropy: 0.0,
            threshold_exceeded: false,
        };
        let out = router.transform(&input, &mask);
        assert_eq!(out.len(), 4);
    }
}
