//! HIP Runtime FFI Bridge — AMD RX 570 (gfx803)
//! EPISTEMIC TIER: T2
//! Feature-gated: compiled only with --features hip (requires ROCm toolkit).
//!
//! Provides the Rust FFI boundary for HIP kernel calls.
//! Without ROCm: this module is excluded from compilation.

#[repr(C)]
pub struct KernelState {
    pub input_ptr: *const f32,
    pub output_ptr: *mut f32,
    pub len: u32,
    pub int4_scale: f32,
    pub int4_zero: i32,
}

#[cfg(feature = "hip")]
extern "C" {
    fn launch_rwkv7_step(state: *const KernelState) -> i32;
}

/// Invoke the RWKV-7 HIP kernel for one state step.
/// Returns 0 on success, non-zero on error.
#[cfg(feature = "hip")]
pub fn hip_rwkv7_step(state: &KernelState) -> i32 {
    unsafe { launch_rwkv7_step(state as *const KernelState) }
}

/// Stub for non-HIP builds — returns error code indicating unavailable.
#[cfg(not(feature = "hip"))]
pub fn hip_rwkv7_step(_state: &KernelState) -> i32 {
    // HIP not available — caller should fall back to CPU path
    -1
}
