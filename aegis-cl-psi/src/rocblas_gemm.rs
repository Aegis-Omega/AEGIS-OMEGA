//! rocBLAS GEMM Integration Stub
//! EPISTEMIC TIER: T2
//! Feature-gated: only compiled with --features rocblas (requires ROCm)
//!
//! In production: calls hipblasSgemm for accelerated matrix multiply on RX 570.
//! Without feature: naive row-major GEMM in pure Rust (fallback).

/// Naive O(M*N*K) row-major GEMM: C = A * B
/// A: M×K, B: K×N, C: M×N (all row-major, zeroed before call)
pub fn gemm_naive(
    a: &[f32], b: &[f32], c: &mut [f32],
    m: usize, n: usize, k: usize,
) {
    for i in 0..m {
        for j in 0..n {
            let mut sum = 0.0f32;
            for l in 0..k {
                sum += a[i * k + l] * b[l * n + j];
            }
            c[i * n + j] = sum;
        }
    }
}

#[cfg(feature = "rocblas")]
pub mod hip {
    // rocBLAS FFI boundary — compiled only with ROCm toolkit present.
    extern "C" {
        fn hipblasSgemm(
            handle: *mut std::ffi::c_void,
            transa: i32, transb: i32,
            m: i32, n: i32, k: i32,
            alpha: *const f32,
            a: *const f32, lda: i32,
            b: *const f32, ldb: i32,
            beta: *const f32,
            c: *mut f32, ldc: i32,
        ) -> i32;
    }
    // Wrapper called from orchestrator when feature enabled.
    pub fn sgemm(
        a: *const f32, b: *const f32, c: *mut f32,
        m: i32, n: i32, k: i32,
        handle: *mut std::ffi::c_void,
    ) -> i32 {
        let alpha = 1.0f32;
        let beta = 0.0f32;
        unsafe {
            hipblasSgemm(handle, 111, 111, m, n, k,
                         &alpha, a, k, b, n, &beta, c, n)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identity_matrix_multiply() {
        // A = [[1,0],[0,1]], B = [[2,3],[4,5]], C = B
        let a = [1.0f32, 0.0, 0.0, 1.0];
        let b = [2.0f32, 3.0, 4.0, 5.0];
        let mut c = [0.0f32; 4];
        gemm_naive(&a, &b, &mut c, 2, 2, 2);
        assert_eq!(c, [2.0, 3.0, 4.0, 5.0]);
    }

    #[test]
    fn gemm_1x1() {
        let a = [3.0f32];
        let b = [4.0f32];
        let mut c = [0.0f32];
        gemm_naive(&a, &b, &mut c, 1, 1, 1);
        assert_eq!(c[0], 12.0);
    }

    // 3. Zero A matrix produces zero C
    #[test]
    fn zero_a_produces_zero_c() {
        let a = [0.0f32; 4];
        let b = [1.0f32, 2.0, 3.0, 4.0];
        let mut c = [0.0f32; 4];
        gemm_naive(&a, &b, &mut c, 2, 2, 2);
        assert_eq!(c, [0.0, 0.0, 0.0, 0.0]);
    }

    // 4. 2×1 times 1×2 outer product
    #[test]
    fn gemm_2x1_times_1x2() {
        // A (2×1) = [2, 3]^T, B (1×2) = [4, 5], C (2×2) = [8,10, 12,15]
        let a = [2.0f32, 3.0];
        let b = [4.0f32, 5.0];
        let mut c = [0.0f32; 4];
        gemm_naive(&a, &b, &mut c, 2, 2, 1);
        assert_eq!(c, [8.0, 10.0, 12.0, 15.0]);
    }

    // 5. Dot product (1×n times n×1 = scalar)
    #[test]
    fn gemm_dot_product() {
        // A (1×3) = [1,2,3], B (3×1) = [4,5,6], C = [32]
        let a = [1.0f32, 2.0, 3.0];
        let b = [4.0f32, 5.0, 6.0];
        let mut c = [0.0f32];
        gemm_naive(&a, &b, &mut c, 1, 1, 3);
        assert_eq!(c[0], 32.0);
    }

    // 6. C is overwritten, not accumulated
    #[test]
    fn c_overwritten_not_accumulated() {
        let a = [1.0f32, 0.0, 0.0, 1.0]; // identity
        let b = [5.0f32, 6.0, 7.0, 8.0];
        let mut c = [999.0f32; 4]; // pre-fill with garbage
        gemm_naive(&a, &b, &mut c, 2, 2, 2);
        assert_eq!(c, [5.0, 6.0, 7.0, 8.0]);
    }

    // 7. Non-square: M=1, N=3, K=2
    #[test]
    fn gemm_non_square_1x2_times_2x3() {
        // A (1×2) = [1,2], B (2×3) = [1,2,3, 4,5,6]
        // C (1×3) = [1+8, 2+10, 3+12] = [9, 12, 15]
        let a = [1.0f32, 2.0];
        let b = [1.0f32, 2.0, 3.0, 4.0, 5.0, 6.0];
        let mut c = [0.0f32; 3];
        gemm_naive(&a, &b, &mut c, 1, 3, 2);
        assert_eq!(c, [9.0, 12.0, 15.0]);
    }

    // 8. Scalar multiplication via 1×1 GEMM
    #[test]
    fn gemm_scalar_multiply_pi() {
        let a = [std::f32::consts::PI];
        let b = [2.0f32];
        let mut c = [0.0f32];
        gemm_naive(&a, &b, &mut c, 1, 1, 1);
        assert!((c[0] - std::f32::consts::TAU).abs() < 1e-5);
    }

    // 9. All-ones M×K times K×N — each output = K
    #[test]
    fn all_ones_matrices() {
        // A (2×3) all 1s, B (3×4) all 1s → C (2×4) all 3s
        let a = [1.0f32; 6];
        let b = [1.0f32; 12];
        let mut c = [0.0f32; 8];
        gemm_naive(&a, &b, &mut c, 2, 4, 3);
        assert!(c.iter().all(|&v| (v - 3.0).abs() < 1e-6));
    }

    // 10. Result dimensions M×N filled correctly
    #[test]
    fn gemm_fills_exactly_m_n_outputs() {
        // A (3×2), B (2×3) → C (3×3)
        let a = [1.0f32, 0.0,  0.0, 1.0,  1.0, 1.0]; // row-major 3×2
        let b = [1.0f32, 2.0, 3.0,  4.0, 5.0, 6.0];  // row-major 2×3
        let mut c = [0.0f32; 9];
        gemm_naive(&a, &b, &mut c, 3, 3, 2);
        // Row 0: [1,2,3], Row 1: [4,5,6], Row 2: [5,7,9]
        assert_eq!(c[0], 1.0); assert_eq!(c[1], 2.0); assert_eq!(c[2], 3.0);
        assert_eq!(c[3], 4.0); assert_eq!(c[4], 5.0); assert_eq!(c[5], 6.0);
        assert_eq!(c[6], 5.0); assert_eq!(c[7], 7.0); assert_eq!(c[8], 9.0);
    }
}
