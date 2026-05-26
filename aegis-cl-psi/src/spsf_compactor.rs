//! Gate 328 — SPSF Epoch Compactor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Truncates SPSF entries older than a configurable retention window while
//! preserving the terminal hash as a cryptographic anchor. Enables long-running
//! epoch sequences without unbounded disk growth.
//!
//! Constitutional invariant: compaction never destroys the proof-of-history.
//! After compaction, the surviving entries must still form a valid hash chain
//! from the compaction anchor forward. The anchor carries the terminal hash
//! of all pruned entries — a future verifier who holds the anchor can still
//! certify the post-compaction chain.
//!
//! CompactionInput:
//!   entries:          Vec<(sequence_id, state_hash)> — ordered by sequence_id
//!   retain_count:     usize — how many MOST RECENT entries to keep
//!   compaction_epoch: u64
//!
//! CompactionResult:
//!   pruned_count:     usize — entries removed
//!   retained_count:   usize
//!   anchor:           CompactionAnchor — terminal hash of pruned prefix
//!   certificate_hash: SHA-256(compaction_epoch‖pruned_count_be8‖retained_count_be8
//!                             ‖anchor.terminal_hash[32]‖anchor.anchor_seq_be8)
//!
//! CompactionAnchor:
//!   anchor_sequence:  u64  — highest sequence_id in the pruned set
//!   terminal_hash:    [u8;32] — SHA-256 hash of the last pruned entry's state_hash
//!                               chained over all pruned entries in sequence order
//!   entry_count:      u64  — number of pruned entries sealed into anchor
//!
//! CompactionLog: hash-chained CompactionRecords — audit trail for all compactions.
//!   compact(), latest(), total_pruned(), verify_chain().

use sha2::{Sha256, Digest};

pub const COMPACTOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── CompactionAnchor ─────────────────────────────────────────────────────────

/// Cryptographic anchor sealing the pruned entry prefix.
///
/// The `terminal_hash` is computed as:
///   SHA-256( SHA-256(…SHA-256(prev_hash ‖ state_hash[0])…) ‖ state_hash[N-1] )
/// i.e., a sequential hash chain over the pruned entries in ascending sequence order.
#[derive(Debug, Clone, PartialEq)]
pub struct CompactionAnchor {
    pub anchor_sequence: u64,
    pub terminal_hash:   [u8; 32],
    pub entry_count:     u64,
}

impl CompactionAnchor {
    /// Construct an anchor from the pruned entry set.
    /// `pruned`: slices of `(sequence_id, state_hash)` in ascending sequence order.
    pub fn from_pruned(pruned: &[(u64, [u8; 32])]) -> Self {
        if pruned.is_empty() {
            return CompactionAnchor {
                anchor_sequence: 0,
                terminal_hash:   COMPACTOR_GENESIS_HASH,
                entry_count:     0,
            };
        }
        let mut acc = COMPACTOR_GENESIS_HASH;
        for (seq, state_hash) in pruned {
            let mut h = Sha256::new();
            h.update(acc);
            h.update(seq.to_be_bytes());
            h.update(state_hash);
            acc = h.finalize().into();
        }
        CompactionAnchor {
            anchor_sequence: pruned.last().unwrap().0,
            terminal_hash:   acc,
            entry_count:     pruned.len() as u64,
        }
    }
}

// ─── CompactionInput ──────────────────────────────────────────────────────────

/// Input for one compaction operation.
#[derive(Debug, Clone)]
pub struct CompactionInput {
    /// Full set of current entries, sorted ascending by sequence_id.
    pub entries:          Vec<(u64, [u8; 32])>,
    /// How many most-recent entries to retain.
    pub retain_count:     usize,
    pub compaction_epoch: u64,
}

// ─── CompactionResult ─────────────────────────────────────────────────────────

/// Result of one compaction operation.
#[derive(Debug, Clone, PartialEq)]
pub struct CompactionResult {
    pub compaction_epoch: u64,
    pub pruned_count:     usize,
    pub retained_count:   usize,
    pub anchor:           CompactionAnchor,
    pub certificate_hash: [u8; 32],
}

fn compute_certificate_hash(
    epoch:          u64,
    pruned_count:   usize,
    retained_count: usize,
    anchor:         &CompactionAnchor,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(epoch.to_be_bytes());
    h.update((pruned_count as u64).to_be_bytes());
    h.update((retained_count as u64).to_be_bytes());
    h.update(anchor.terminal_hash);
    h.update(anchor.anchor_sequence.to_be_bytes());
    h.update(anchor.entry_count.to_be_bytes());
    h.finalize().into()
}

/// Execute compaction on the given input.
///
/// If `retain_count >= entries.len()`, no pruning occurs — returns
/// `CompactionResult` with `pruned_count = 0` and genesis anchor.
pub fn compact(inp: CompactionInput) -> CompactionResult {
    let total = inp.entries.len();
    let pruned_count = if inp.retain_count >= total {
        0
    } else {
        total - inp.retain_count
    };
    let retained_count = total - pruned_count;

    let pruned: Vec<(u64, [u8; 32])> = inp.entries[..pruned_count].to_vec();
    let anchor = CompactionAnchor::from_pruned(&pruned);

    let certificate_hash = compute_certificate_hash(
        inp.compaction_epoch,
        pruned_count,
        retained_count,
        &anchor,
    );

    CompactionResult {
        compaction_epoch: inp.compaction_epoch,
        pruned_count,
        retained_count,
        anchor,
        certificate_hash,
    }
}

// ─── CompactionRecord ─────────────────────────────────────────────────────────

/// One hash-chained audit record for one compaction event.
#[derive(Debug, Clone, PartialEq)]
pub struct CompactionRecord {
    pub compaction_epoch:    u64,
    pub pruned_count:        u64,
    pub retained_count:      u64,
    pub anchor_sequence:     u64,
    pub anchor_terminal_hash: [u8; 32],
    pub record_hash:         [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_record_hash(
    prev:                  &[u8; 32],
    compaction_epoch:      u64,
    pruned_count:          u64,
    retained_count:        u64,
    anchor_sequence:       u64,
    anchor_terminal_hash:  &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(compaction_epoch.to_be_bytes());
    h.update(pruned_count.to_be_bytes());
    h.update(retained_count.to_be_bytes());
    h.update(anchor_sequence.to_be_bytes());
    h.update(anchor_terminal_hash);
    h.finalize().into()
}

// ─── CompactionLog ────────────────────────────────────────────────────────────

/// Append-only hash-chained audit log of all compaction operations.
pub struct CompactionLog {
    records: Vec<CompactionRecord>,
}

impl CompactionLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[CompactionRecord] { &self.records }

    /// Record a completed compaction in the audit log.
    pub fn record(&mut self, result: &CompactionResult) -> CompactionRecord {
        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(COMPACTOR_GENESIS_HASH);

        let record_hash = compute_record_hash(
            &prev,
            result.compaction_epoch,
            result.pruned_count as u64,
            result.retained_count as u64,
            result.anchor.anchor_sequence,
            &result.anchor.terminal_hash,
        );

        let rec = CompactionRecord {
            compaction_epoch:     result.compaction_epoch,
            pruned_count:         result.pruned_count as u64,
            retained_count:       result.retained_count as u64,
            anchor_sequence:      result.anchor.anchor_sequence,
            anchor_terminal_hash: result.anchor.terminal_hash,
            record_hash,
            prev_hash:            prev,
        };
        self.records.push(rec.clone());
        rec
    }

    /// Total entries pruned across all compactions.
    pub fn total_pruned(&self) -> u64 {
        self.records.iter().map(|r| r.pruned_count).sum()
    }

    /// Latest record, or `None` if empty.
    pub fn latest(&self) -> Option<&CompactionRecord> {
        self.records.last()
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = COMPACTOR_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(
                &prev,
                r.compaction_epoch,
                r.pruned_count,
                r.retained_count,
                r.anchor_sequence,
                &r.anchor_terminal_hash,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for CompactionLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn state_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = seed; h[31] = seed.wrapping_mul(11);
        h
    }

    fn entries(n: u64) -> Vec<(u64, [u8; 32])> {
        (1..=n).map(|i| (i, state_hash(i as u8))).collect()
    }

    // ── CompactionAnchor ──────────────────────────────────────────────────────

    #[test]
    fn anchor_empty_is_genesis() {
        let a = CompactionAnchor::from_pruned(&[]);
        assert_eq!(a.terminal_hash, COMPACTOR_GENESIS_HASH);
        assert_eq!(a.entry_count, 0);
        assert_eq!(a.anchor_sequence, 0);
    }

    #[test]
    fn anchor_single_entry() {
        let e = vec![(1u64, state_hash(1))];
        let a = CompactionAnchor::from_pruned(&e);
        assert_eq!(a.anchor_sequence, 1);
        assert_eq!(a.entry_count, 1);
        assert_ne!(a.terminal_hash, COMPACTOR_GENESIS_HASH);
    }

    #[test]
    fn anchor_deterministic_three_times() {
        let e = entries(5);
        let a1 = CompactionAnchor::from_pruned(&e);
        let a2 = CompactionAnchor::from_pruned(&e);
        let a3 = CompactionAnchor::from_pruned(&e);
        assert_eq!(a1.terminal_hash, a2.terminal_hash);
        assert_eq!(a2.terminal_hash, a3.terminal_hash);
    }

    #[test]
    fn anchor_order_matters() {
        let fwd: Vec<(u64, [u8; 32])> = vec![(1, state_hash(1)), (2, state_hash(2))];
        let rev: Vec<(u64, [u8; 32])> = vec![(2, state_hash(2)), (1, state_hash(1))];
        let a1 = CompactionAnchor::from_pruned(&fwd);
        let a2 = CompactionAnchor::from_pruned(&rev);
        assert_ne!(a1.terminal_hash, a2.terminal_hash);
    }

    // ── compact() ─────────────────────────────────────────────────────────────

    #[test]
    fn compact_prunes_prefix() {
        // 10 entries, retain 4 → prune 6
        let result = compact(CompactionInput {
            entries:          entries(10),
            retain_count:     4,
            compaction_epoch: 5,
        });
        assert_eq!(result.pruned_count, 6);
        assert_eq!(result.retained_count, 4);
        assert_eq!(result.anchor.anchor_sequence, 6); // entries 1..6 pruned
        assert_eq!(result.anchor.entry_count, 6);
    }

    #[test]
    fn compact_retain_all_no_pruning() {
        let result = compact(CompactionInput {
            entries:          entries(5),
            retain_count:     10, // more than total
            compaction_epoch: 1,
        });
        assert_eq!(result.pruned_count, 0);
        assert_eq!(result.retained_count, 5);
        assert_eq!(result.anchor.terminal_hash, COMPACTOR_GENESIS_HASH);
    }

    #[test]
    fn compact_retain_zero_prunes_all() {
        let result = compact(CompactionInput {
            entries:          entries(8),
            retain_count:     0,
            compaction_epoch: 3,
        });
        assert_eq!(result.pruned_count, 8);
        assert_eq!(result.retained_count, 0);
        assert_eq!(result.anchor.anchor_sequence, 8);
    }

    #[test]
    fn certificate_hash_nonzero() {
        let result = compact(CompactionInput {
            entries:          entries(5),
            retain_count:     2,
            compaction_epoch: 10,
        });
        assert_ne!(result.certificate_hash, [0u8; 32]);
    }

    #[test]
    fn certificate_hash_deterministic() {
        let inp = CompactionInput {
            entries:          entries(6),
            retain_count:     3,
            compaction_epoch: 7,
        };
        let r1 = compact(inp.clone());
        let r2 = compact(inp.clone());
        let r3 = compact(inp);
        assert_eq!(r1.certificate_hash, r2.certificate_hash);
        assert_eq!(r2.certificate_hash, r3.certificate_hash);
    }

    #[test]
    fn different_retain_count_different_certificate() {
        let e = entries(8);
        let r1 = compact(CompactionInput { entries: e.clone(), retain_count: 2, compaction_epoch: 1 });
        let r2 = compact(CompactionInput { entries: e,         retain_count: 4, compaction_epoch: 1 });
        assert_ne!(r1.certificate_hash, r2.certificate_hash);
    }

    // ── CompactionLog ─────────────────────────────────────────────────────────

    #[test]
    fn fresh_log_empty() {
        let l = CompactionLog::new();
        assert!(l.is_empty());
        assert_eq!(l.total_pruned(), 0);
    }

    #[test]
    fn record_chains_correctly() {
        let mut l = CompactionLog::new();
        let r1 = compact(CompactionInput { entries: entries(10), retain_count: 7, compaction_epoch: 1 });
        let r2 = compact(CompactionInput { entries: entries(15), retain_count: 5, compaction_epoch: 2 });
        let rec1 = l.record(&r1);
        let rec2 = l.record(&r2);
        assert_eq!(rec2.prev_hash, rec1.record_hash);
        assert_eq!(l.total_pruned(), 3 + 10);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let l = CompactionLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut l = CompactionLog::new();
        for epoch in 1..=3u64 {
            let r = compact(CompactionInput { entries: entries(10), retain_count: 7, compaction_epoch: epoch });
            l.record(&r);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered_pruned_count() {
        let mut l = CompactionLog::new();
        let r = compact(CompactionInput { entries: entries(10), retain_count: 7, compaction_epoch: 1 });
        l.record(&r);
        l.records[0].pruned_count = 99;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_tampered_anchor_hash() {
        let mut l = CompactionLog::new();
        let r = compact(CompactionInput { entries: entries(10), retain_count: 7, compaction_epoch: 1 });
        l.record(&r);
        l.records[0].anchor_terminal_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }
}
