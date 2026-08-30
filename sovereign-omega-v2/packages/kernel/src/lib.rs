// ============================================================
// AEGIS Ω — Deterministic WASM Kernel
// EPISTEMIC TIER: T0 · Gate 16
//
// Implements the 5 determinism-critical functions declared in
// src/core/wasm-interface.ts. Each function is a drop-in
// replacement for the TypeScript JS fallback, verified by
// byte-identical output in test/determinism/wasm-kernel.test.ts.
//
// Memory interface:
//   get_input_ptr()  → pointer to 32KB shared input buffer
//   get_output_ptr() → pointer to 32KB shared output buffer
//   All other functions take explicit ptr+len parameters.
//
// No external dependencies — zero non-deterministic code paths.
// ============================================================

mod bernstein;
mod canonical;
mod hash;
mod merkle;

// 32KB shared buffers — callers use get_input_ptr/get_output_ptr
// for convenient access without managing their own memory offsets.
static mut INPUT:  [u8; 32768] = [0u8; 32768];
static mut OUTPUT: [u8; 32768] = [0u8; 32768];

/// Returns the address of the 32KB shared input buffer.
/// Write your input bytes here before calling a memory-based function.
#[no_mangle]
pub extern "C" fn get_input_ptr() -> i32 {
    core::ptr::addr_of!(INPUT) as i32
}

/// Returns the address of the 32KB shared output buffer.
/// Read your output bytes from here after calling a memory-based function.
#[no_mangle]
pub extern "C" fn get_output_ptr() -> i32 {
    core::ptr::addr_of!(OUTPUT) as i32
}

/// SHA-256 over raw bytes.
/// input_ptr/input_len: source data in WASM linear memory.
/// out_ptr: destination for 32-byte digest.
/// Matches TypeScript sha256Bytes (src/core/hashing.ts) byte-for-byte.
#[no_mangle]
pub unsafe extern "C" fn sha256(input_ptr: i32, input_len: i32, out_ptr: i32) {
    let input = core::slice::from_raw_parts(input_ptr as *const u8, input_len as usize);
    let digest = hash::sha256(input);
    let out = core::slice::from_raw_parts_mut(out_ptr as *mut u8, 32);
    out.copy_from_slice(&digest);
}

/// Binary Merkle root from length-prefixed raw leaf arrays.
///
/// Buffer layout at leaves_ptr:
///   for each leaf: [len: u32 LE] [raw_data: u8 * len]
///
/// Each leaf is SHA-256 hashed before tree construction.
/// Odd counts: last leaf is duplicated (matches TypeScript).
/// Writes 32-byte root digest to out_ptr.
#[no_mangle]
pub unsafe extern "C" fn merkle_root(leaves_ptr: i32, leaf_count: i32, out_ptr: i32) {
    let root = merkle::compute_merkle_root(leaves_ptr as *const u8, leaf_count as usize);
    let out = core::slice::from_raw_parts_mut(out_ptr as *mut u8, 32);
    out.copy_from_slice(&root);
}

/// Empirical Bernstein LCB in Q32.32 fixed-point.
///
/// All Q32.32 parameters are i64, which WebAssembly passes as JavaScript BigInt.
/// n: sample count (i32 in WASM, treated as i64 internally).
///
/// Ports bernsteinLCBQ32 from src/core/fixedpoint.ts exactly.
/// Same f64 transcendentals (ln, sqrt) — byte-identical on same platform.
#[no_mangle]
pub extern "C" fn bernstein_lcb(
    sum_q32: i64,
    sum_sq_q32: i64,
    n: i32,
    alpha_q32: i64,
) -> i64 {
    bernstein::bernstein_lcb_q32(sum_q32, sum_sq_q32, n as i64, alpha_q32)
}

/// RFC 8785 JSON canonicalization.
/// Parses JSON at input_ptr, sorts object keys by Unicode code point order,
/// writes canonical UTF-8 bytes to out_ptr.
/// Returns output byte length.
/// Ports canonicalizeJCS from src/core/canonicalize.ts.
#[no_mangle]
pub unsafe extern "C" fn canonicalize(
    input_ptr: i32,
    input_len: i32,
    out_ptr: i32,
) -> i32 {
    let input = core::slice::from_raw_parts(input_ptr as *const u8, input_len as usize);
    let result = canonical::canonicalize_json(input);
    let out = core::slice::from_raw_parts_mut(out_ptr as *mut u8, result.len());
    out.copy_from_slice(&result);
    result.len() as i32
}

/// Pure deterministic state reduction: SHA-256(state_bytes || event_bytes).
/// Provides a replay-verifiable hash of the combined state+event boundary.
/// Returns 32 (output length); writes digest to out_ptr.
#[no_mangle]
pub unsafe extern "C" fn reduce_state(
    state_ptr: i32,
    state_len: i32,
    event_ptr: i32,
    event_len: i32,
    out_ptr: i32,
) -> i32 {
    let state = core::slice::from_raw_parts(state_ptr as *const u8, state_len as usize);
    let event = core::slice::from_raw_parts(event_ptr as *const u8, event_len as usize);

    let mut combined = Vec::with_capacity(state.len() + event.len());
    combined.extend_from_slice(state);
    combined.extend_from_slice(event);

    let digest = hash::sha256(&combined);
    let out = core::slice::from_raw_parts_mut(out_ptr as *mut u8, 32);
    out.copy_from_slice(&digest);
    32
}
