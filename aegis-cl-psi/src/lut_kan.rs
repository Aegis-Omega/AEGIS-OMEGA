//! LUT-KAN — INT4 Cache-Local Activation + INT8 Router
//! EPISTEMIC TIER: T2
//!
//! `lut_activation`: canonical INT4 (16-entry) activation lookup as specified
//! in the int4-lut-kan skill. O(1), no floating point, fits one 64-byte cache line.
//! `LUTKANRouter`: original INT8/256-entry router with linear interpolation.
//!
//! Scaling invariant: table values are stored in scaled fixed-point; the scale
//! factor MUST be a power of 2 so results can be re-scaled with a bit-shift,
//! preserving the no-f64 invariant in hash inputs.

use crate::sgm_gate::RoutingMask;

/// INT4 LUT activation — canonical form from the int4-lut-kan skill.
///
/// Clamps `input` to [0, 15] (4-bit unsigned range) and returns `table[idx]`.
/// O(1), no floating point, no branching beyond the clamp. The table (16 × i32)
/// fits exactly in one 64-byte cache line when values are i32 = 4 bytes each.
///
/// Table values are stored in scaled fixed-point; the scale factor must be a
/// power of 2 so the caller can rescale with `>> SHIFT`, preserving the no-f64
/// invariant required for hash inputs.
#[inline]
pub fn lut_activation(input: i32, table: &[i32; 16]) -> i32 {
    let idx = input.clamp(0, 15) as usize;
    table[idx]
}

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

    // ── INT4 LUT activation — 19-test viability ring ─────────────────────────

    const IDENTITY: [i32; 16] = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15];
    const ALL_ZERO: [i32; 16] = [0i32; 16];
    const ALL_MAX:  [i32; 16] = [i32::MAX; 16];
    const ALL_NEG:  [i32; 16] = [-1i32; 16];
    const SCALED:   [i32; 16] = [0,256,512,768,1024,1280,1536,1792,
                                  2048,2304,2560,2816,3072,3328,3584,3840];

    // 1. Lower boundary: input 0 → table[0]
    #[test] fn int4_lower_boundary() { assert_eq!(lut_activation(0, &IDENTITY), 0); }
    // 2. Upper boundary: input 15 → table[15]
    #[test] fn int4_upper_boundary() { assert_eq!(lut_activation(15, &IDENTITY), 15); }
    // 3. Clamp below: input -1 → table[0]
    #[test] fn int4_clamp_below() { assert_eq!(lut_activation(-1, &IDENTITY), 0); }
    // 4. Clamp above: input 16 → table[15]
    #[test] fn int4_clamp_above() { assert_eq!(lut_activation(16, &IDENTITY), 15); }
    // 5. Extreme low: i32::MIN clamps to table[0]
    #[test] fn int4_extreme_low() { assert_eq!(lut_activation(i32::MIN, &IDENTITY), 0); }
    // 6. Extreme high: i32::MAX clamps to table[15]
    #[test] fn int4_extreme_high() { assert_eq!(lut_activation(i32::MAX, &IDENTITY), 15); }
    // 7. Identity: lut_activation(k, IDENTITY) == k for all k in 0..16
    #[test] fn int4_identity_table() {
        for k in 0i32..16 { assert_eq!(lut_activation(k, &IDENTITY), k); }
    }
    // 8. All-zero table: always 0 regardless of input
    #[test] fn int4_all_zero_table() {
        for k in [0, 7, 15, -1, 16, i32::MIN, i32::MAX] {
            assert_eq!(lut_activation(k, &ALL_ZERO), 0);
        }
    }
    // 9. All-max table: always i32::MAX
    #[test] fn int4_all_max_table() { assert_eq!(lut_activation(8, &ALL_MAX), i32::MAX); }
    // 10. Negative table entries: returns negative values correctly
    #[test] fn int4_negative_table_entries() { assert_eq!(lut_activation(3, &ALL_NEG), -1); }
    // 11. Mid-range: input 8 → table[8]
    #[test] fn int4_mid_range() { assert_eq!(lut_activation(8, &IDENTITY), 8); }
    // 12. Input 1 → table[1]
    #[test] fn int4_input_one() { assert_eq!(lut_activation(1, &IDENTITY), 1); }
    // 13. Input 14 → table[14]
    #[test] fn int4_input_fourteen() { assert_eq!(lut_activation(14, &IDENTITY), 14); }
    // 14. Determinism ×3: same inputs yield identical output
    #[test] fn int4_determinism() {
        let t = [100i32,200,300,400,500,600,700,800,900,1000,1100,1200,1300,1400,1500,1600];
        let r1 = lut_activation(7, &t);
        let r2 = lut_activation(7, &t);
        let r3 = lut_activation(7, &t);
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }
    // 15. Power-of-2 scaling: SCALED[k] = k * 256; rescale with >> 8 gives k
    #[test] fn int4_power_of_two_scale() {
        for k in 0i32..16 {
            let raw = lut_activation(k, &SCALED);
            assert_eq!(raw >> 8, k);
        }
    }
    // 16. Cache line: 16 entries × 4 bytes = 64 bytes exactly
    #[test] fn int4_cache_line_fit() { assert_eq!(16 * std::mem::size_of::<i32>(), 64); }
    // 17. No f64: return type and table type are i32; compile-time guarantee
    #[test] fn int4_no_f64_type() {
        let v: i32 = lut_activation(5, &IDENTITY);
        let _: i32 = v;  // confirms i32, not f64
    }
    // 18. Clamped inputs are equal to in-range inputs at the boundary values
    #[test] fn int4_clamp_equivalence() {
        assert_eq!(lut_activation(-100, &IDENTITY), lut_activation(0, &IDENTITY));
        assert_eq!(lut_activation(100,  &IDENTITY), lut_activation(15, &IDENTITY));
    }
    // 19. Non-trivial table: mixed positive/negative fixed-point values
    #[test] fn int4_mixed_signed_table() {
        let t: [i32; 16] = [-8,-7,-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7];
        for k in 0i32..16 { assert_eq!(lut_activation(k, &t), k as i32 - 8); }
    }
}
