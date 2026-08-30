//! Gate 304 — Gossip Message Fragmenter: split/reassemble large messages into fixed-size fragments (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Splits a large message payload (byte slice) into fixed-size fragments for gossip
//! transmission. Each fragment carries a sequence number and fragment index. A reassembly
//! buffer collects received fragments and reconstructs the original message when all
//! fragments arrive.
//!
//! Constants:
//!   FRAGMENT_SIZE: usize = 256   (bytes per fragment body)
//!   MAX_FRAGMENTS: usize = 64    (max fragments per message → max message = 16 KB)
//!
//! Fragment:
//!   message_id: u64, fragment_index: u16, total_fragments: u16,
//!   payload: Vec<u8> (≤ FRAGMENT_SIZE bytes), payload_hash: [u8; 32]
//!   payload_hash = SHA-256(message_id_be8 ‖ fragment_index_be2 ‖ total_be2 ‖ payload)
//!
//! FragmentError: MessageTooLarge | EmptyPayload | InconsistentHeader | DuplicateFragment
//!
//! fragment_message(message_id, data) → Result<Vec<Fragment>, FragmentError>
//!   Splits data into ≤FRAGMENT_SIZE chunks. Errors if data is empty or requires > MAX_FRAGMENTS.
//!
//! ReassemblyBuffer:
//!   new(message_id, total_fragments)
//!   insert(fragment) → Result<Option<Vec<u8>>, FragmentError>
//!     Returns Ok(Some(data)) when all fragments received and reassembled.
//!     Returns Ok(None) when still waiting for more fragments.
//!     Returns Err(DuplicateFragment) if index already received.
//!     Returns Err(InconsistentHeader) if total_fragments doesn't match.
//!   is_complete() → bool
//!   received_count() → usize
//!   missing_indices() → Vec<u16>

use sha2::{Sha256, Digest};

pub const FRAGMENT_SIZE: usize = 256;
pub const MAX_FRAGMENTS: usize = 64;

// ─── Fragment ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct Fragment {
    pub message_id:       u64,
    pub fragment_index:   u16,
    pub total_fragments:  u16,
    pub payload:          Vec<u8>,
    pub payload_hash:     [u8; 32],
}

fn compute_fragment_hash(
    message_id:      u64,
    fragment_index:  u16,
    total_fragments: u16,
    payload:         &[u8],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(message_id.to_be_bytes());
    h.update(fragment_index.to_be_bytes());
    h.update(total_fragments.to_be_bytes());
    h.update(payload);
    h.finalize().into()
}

pub fn build_fragment(
    message_id:      u64,
    fragment_index:  u16,
    total_fragments: u16,
    payload:         Vec<u8>,
) -> Fragment {
    let payload_hash = compute_fragment_hash(message_id, fragment_index, total_fragments, &payload);
    Fragment { message_id, fragment_index, total_fragments, payload, payload_hash }
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug, PartialEq)]
pub enum FragmentError {
    MessageTooLarge,     // requires > MAX_FRAGMENTS fragments
    EmptyPayload,        // zero-byte input
    InconsistentHeader,  // total_fragments doesn't match buffer's expected
    DuplicateFragment,   // fragment_index already received
}

// ─── Fragment a message ───────────────────────────────────────────────────────

/// Split `data` into ≤FRAGMENT_SIZE-byte fragments for message `message_id`.
pub fn fragment_message(message_id: u64, data: &[u8]) -> Result<Vec<Fragment>, FragmentError> {
    if data.is_empty() { return Err(FragmentError::EmptyPayload); }
    let total = (data.len() + FRAGMENT_SIZE - 1) / FRAGMENT_SIZE;
    if total > MAX_FRAGMENTS { return Err(FragmentError::MessageTooLarge); }
    let total_u16 = total as u16;
    let fragments: Vec<Fragment> = data
        .chunks(FRAGMENT_SIZE)
        .enumerate()
        .map(|(i, chunk)| build_fragment(message_id, i as u16, total_u16, chunk.to_vec()))
        .collect();
    Ok(fragments)
}

// ─── Reassembly buffer ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ReassemblyBuffer {
    message_id:       u64,
    total_fragments:  u16,
    slots:            Vec<Option<Vec<u8>>>,  // indexed by fragment_index
    received:         usize,
}

impl ReassemblyBuffer {
    pub fn new(message_id: u64, total_fragments: u16) -> Self {
        Self {
            message_id,
            total_fragments,
            slots: vec![None; total_fragments as usize],
            received: 0,
        }
    }

    pub fn is_complete(&self) -> bool { self.received == self.total_fragments as usize }
    pub fn received_count(&self) -> usize { self.received }

    /// Indices of fragments not yet received.
    pub fn missing_indices(&self) -> Vec<u16> {
        self.slots.iter().enumerate()
            .filter(|(_, s)| s.is_none())
            .map(|(i, _)| i as u16)
            .collect()
    }

    /// Insert a fragment. Returns Ok(Some(data)) when complete, Ok(None) if more needed.
    pub fn insert(&mut self, frag: Fragment) -> Result<Option<Vec<u8>>, FragmentError> {
        if frag.total_fragments != self.total_fragments {
            return Err(FragmentError::InconsistentHeader);
        }
        let idx = frag.fragment_index as usize;
        if self.slots[idx].is_some() {
            return Err(FragmentError::DuplicateFragment);
        }
        self.slots[idx] = Some(frag.payload);
        self.received += 1;
        if self.is_complete() {
            let data: Vec<u8> = self.slots.iter()
                .map(|s| s.as_ref().unwrap().as_slice())
                .flat_map(|s| s.iter().copied())
                .collect();
            Ok(Some(data))
        } else {
            Ok(None)
        }
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── build_fragment ────────────────────────────────────────────────────────

    #[test]
    fn fragment_hash_nonzero() {
        let f = build_fragment(1, 0, 1, vec![0xAB; 10]);
        assert_ne!(f.payload_hash, [0u8; 32]);
    }

    #[test]
    fn fragment_hash_deterministic() {
        let f1 = build_fragment(1, 0, 1, vec![0xAB; 10]);
        let f2 = build_fragment(1, 0, 1, vec![0xAB; 10]);
        assert_eq!(f1.payload_hash, f2.payload_hash);
    }

    // ── fragment_message ──────────────────────────────────────────────────────

    #[test]
    fn empty_payload_errors() {
        assert_eq!(fragment_message(1, &[]), Err(FragmentError::EmptyPayload));
    }

    #[test]
    fn too_large_errors() {
        let data = vec![0u8; FRAGMENT_SIZE * MAX_FRAGMENTS + 1];
        assert_eq!(fragment_message(1, &data), Err(FragmentError::MessageTooLarge));
    }

    #[test]
    fn single_small_fragment() {
        let data: Vec<u8> = (0..100).map(|i| i as u8).collect();
        let frags = fragment_message(42, &data).unwrap();
        assert_eq!(frags.len(), 1);
        assert_eq!(frags[0].total_fragments, 1);
        assert_eq!(frags[0].fragment_index, 0);
        assert_eq!(frags[0].payload, data);
    }

    #[test]
    fn splits_exactly_on_boundary() {
        let data = vec![0xBB; FRAGMENT_SIZE * 3];
        let frags = fragment_message(1, &data).unwrap();
        assert_eq!(frags.len(), 3);
        assert!(frags.iter().all(|f| f.total_fragments == 3));
        assert!(frags.iter().all(|f| f.payload.len() == FRAGMENT_SIZE));
    }

    #[test]
    fn last_fragment_shorter() {
        let data = vec![0xCC; FRAGMENT_SIZE * 2 + 50];
        let frags = fragment_message(1, &data).unwrap();
        assert_eq!(frags.len(), 3);
        assert_eq!(frags[2].payload.len(), 50);
    }

    #[test]
    fn indices_sequential() {
        let data = vec![0xDD; FRAGMENT_SIZE * 4];
        let frags = fragment_message(1, &data).unwrap();
        for (i, f) in frags.iter().enumerate() {
            assert_eq!(f.fragment_index, i as u16);
        }
    }

    // ── ReassemblyBuffer ──────────────────────────────────────────────────────

    #[test]
    fn single_fragment_reassembles() {
        let data: Vec<u8> = (0..100).map(|i| i as u8).collect();
        let frags = fragment_message(1, &data).unwrap();
        let mut buf = ReassemblyBuffer::new(1, 1);
        let result = buf.insert(frags.into_iter().next().unwrap()).unwrap();
        assert_eq!(result, Some(data));
        assert!(buf.is_complete());
    }

    #[test]
    fn multi_fragment_reassembles_in_order() {
        let data: Vec<u8> = (0..=255u8).cycle().take(FRAGMENT_SIZE * 3).collect();
        let frags = fragment_message(2, &data).unwrap();
        let mut buf = ReassemblyBuffer::new(2, 3);
        for (i, f) in frags.into_iter().enumerate() {
            let res = buf.insert(f).unwrap();
            if i < 2 { assert!(res.is_none()); }
            else      { assert_eq!(res, Some(data.clone())); }
        }
    }

    #[test]
    fn out_of_order_reassembly() {
        let data: Vec<u8> = (0..200).map(|i| (i % 256) as u8).collect();
        let frags = fragment_message(3, &data).unwrap();
        let mut buf = ReassemblyBuffer::new(3, frags[0].total_fragments);
        // Insert in reverse order
        let mut frag_iter: Vec<Fragment> = frags.into_iter().rev().collect();
        for _ in 0..frag_iter.len() - 1 {
            assert!(buf.insert(frag_iter.pop().unwrap()).unwrap().is_none());
        }
        let result = buf.insert(frag_iter.pop().unwrap()).unwrap();
        assert_eq!(result, Some(data));
    }

    #[test]
    fn duplicate_fragment_errors() {
        let data = vec![1u8; 10];
        let frags = fragment_message(4, &data).unwrap();
        let mut buf = ReassemblyBuffer::new(4, 1);
        buf.insert(frags[0].clone()).unwrap();
        assert_eq!(buf.insert(frags[0].clone()), Err(FragmentError::DuplicateFragment));
    }

    #[test]
    fn inconsistent_total_errors() {
        let mut f = build_fragment(1, 0, 2, vec![1u8; 10]);
        f.total_fragments = 3; // mismatch
        let mut buf = ReassemblyBuffer::new(1, 2);
        assert_eq!(buf.insert(f), Err(FragmentError::InconsistentHeader));
    }

    #[test]
    fn missing_indices_correct() {
        let data: Vec<u8> = vec![0u8; FRAGMENT_SIZE * 3];
        let frags = fragment_message(5, &data).unwrap();
        let mut buf = ReassemblyBuffer::new(5, 3);
        buf.insert(frags[0].clone()).unwrap();
        let missing = buf.missing_indices();
        assert_eq!(missing, vec![1, 2]);
    }
}
