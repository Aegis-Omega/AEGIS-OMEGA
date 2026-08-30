// ============================================================
// AEGIS Ω — Binary Merkle Tree (byte-concat-arity-2-v1)
// EPISTEMIC TIER: T0
// Byte-identical to TypeScript computeMerkleRoot in src/core/hashing.ts.
// Leaf buffer layout: [u32_le: len, u8*len: data, ...]
// Duplicate-right padding for odd leaf counts.
// ============================================================

use crate::hash;

/// Compute Merkle root from length-prefixed leaf byte arrays.
///
/// Memory layout at `leaves_ptr`:
///   for each leaf: [len: u32 LE] [data: u8 * len]
///
/// Returns 32-byte SHA-256 Merkle root.
/// For 0 leaves: SHA-256 of empty bytes (matches TypeScript).
pub fn compute_merkle_root(leaves_ptr: *const u8, leaf_count: usize) -> [u8; 32] {
    if leaf_count == 0 {
        return hash::sha256(b"");
    }

    // Parse leaves from length-prefixed buffer and hash each leaf
    let mut layer: Vec<[u8; 32]> = Vec::with_capacity(leaf_count);
    let mut ptr = leaves_ptr;

    for _ in 0..leaf_count {
        unsafe {
            // Read 4-byte little-endian length prefix
            let len_bytes = [*ptr, *ptr.add(1), *ptr.add(2), *ptr.add(3)];
            let len = u32::from_le_bytes(len_bytes) as usize;
            ptr = ptr.add(4);

            // Hash the raw leaf bytes (matches TypeScript: sha256Bytes(leaf))
            let leaf_data = core::slice::from_raw_parts(ptr, len);
            layer.push(hash::sha256(leaf_data));
            ptr = ptr.add(len);
        }
    }

    // Build tree bottom-up — matches TypeScript while (layer.length > 1) loop
    while layer.len() > 1 {
        let mut next: Vec<[u8; 32]> = Vec::new();
        let mut i = 0;
        while i < layer.len() {
            let left = layer[i];
            // Duplicate last node if count is odd (matches TypeScript: layer[i+1] ?? layer[i])
            let right = if i + 1 < layer.len() { layer[i + 1] } else { layer[i] };

            // Byte-concatenate left || right, then hash (matches merkleConcat)
            let mut combined = [0u8; 64];
            combined[..32].copy_from_slice(&left);
            combined[32..].copy_from_slice(&right);
            next.push(hash::sha256(&combined));

            i += 2;
        }
        layer = next;
    }

    layer[0]
}
