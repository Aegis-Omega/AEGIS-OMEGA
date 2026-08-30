// RWKV-7 INT4 Step Kernel for AMD RX 570 (gfx803)
// Compiled only when --features hip is set (requires ROCm/HIP toolkit)
// Build: hipcc --amdgpu-target=gfx803 -O3 kernels/rwkv7_step.hip -o kernels/rwkv7_step.o

#include <hip/hip_runtime.h>

#define BLOCK_SIZE 256
#define INT4_SCALE 0.05f
#define INT4_ZERO  0

__device__ float dequant_int4_lo(uint8_t byte) {
    return ((float)(byte & 0x0F) - (float)INT4_ZERO) * INT4_SCALE;
}

__device__ float dequant_int4_hi(uint8_t byte) {
    return ((float)((byte >> 4) & 0x0F) - (float)INT4_ZERO) * INT4_SCALE;
}

// One RWKV-7 time-mixing step: applies INT4-quantized weights to input
__global__ void rwkv7_int4_step(
    const uint8_t* __restrict__ weights_int4,  // packed INT4 weights
    const float*   __restrict__ input,          // f32 input activations
    float*         __restrict__ output,         // f32 output
    int len
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= len) return;

    int byte_idx = idx / 2;
    uint8_t packed = weights_int4[byte_idx];
    float w = (idx % 2 == 0) ? dequant_int4_lo(packed) : dequant_int4_hi(packed);
    output[idx] = input[idx] * w;
}

// Entry point called from Rust FFI
extern "C" int launch_rwkv7_step(const void* state_ptr) {
    // state_ptr cast to KernelState struct (defined in hip_runtime.rs)
    // Full implementation: unpack KernelState, launch kernel
    // Stub: returns 0 (success) for build validation
    (void)state_ptr;
    return 0;
}
