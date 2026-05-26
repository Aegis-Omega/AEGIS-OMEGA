//! Gate 291 — Gossip Peer Selector: topology-aware peer selection for gossip forwarding (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Selects which peers to forward a gossip message to, based on:
//! - Reputation score (higher = preferred)
//! - Latency tier (lower = preferred)
//! - Exclusion of the sending peer (no echo back)
//! - Fanout limit (how many peers to select)
//!
//! SelectionCriteria:
//!   sender_id     — u32 (exclude from candidates)
//!   max_fanout    — u8 (maximum peers to select)
//!   min_score     — u8 (minimum reputation score required)
//!   max_latency_tier — u8 (0=Fast, 1=Normal, 2=Slow, 3=Timeout; peers ≤ tier accepted)
//!
//! SelectionRecord:
//!   epoch         — u64
//!   sender_id     — u32
//!   candidate_count — u8 (total eligible peers before selection)
//!   selected_count  — u8 (peers chosen)
//!   selected_ids    — Vec<u32> (sorted, deterministic)
//!   record_hash   — SHA-256(prev ‖ epoch_be8 ‖ sender_be4 ‖ cand ‖ sel ‖ selected_hash)
//!   prev_hash     — [u8; 32]
//!
//! SelectionLog: hash-chained SelectionRecords.
//!   record(), avg_selected_count(), zero_selection_count(), verify_chain().
//!
//! PeerSelector:
//!   select(epoch, criteria, peer_scores, peer_latency_tiers) → Vec<u32>
//!   record_and_select(…) → (Vec<u32>, &SelectionRecord)

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

// ─── Selection criteria ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy)]
pub struct SelectionCriteria {
    pub sender_id:        u32,
    pub max_fanout:       u8,
    pub min_score:        u8,
    pub max_latency_tier: u8,
}

// ─── Selection record ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SelectionRecord {
    pub epoch:            u64,
    pub sender_id:        u32,
    pub candidate_count:  u8,
    pub selected_count:   u8,
    pub selected_ids:     Vec<u32>,
    pub record_hash:      [u8; 32],
    pub prev_hash:        [u8; 32],
}

pub const SELECTOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_selection_hash(
    epoch:           u64,
    sender_id:       u32,
    candidate_count: u8,
    selected_count:  u8,
    selected_ids:    &[u32],
    prev:            &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(sender_id.to_be_bytes());
    h.update([candidate_count, selected_count]);
    // Hash the selected IDs in order for deterministic digest
    for &id in selected_ids {
        h.update(id.to_be_bytes());
    }
    h.finalize().into()
}

pub fn build_selection_record(
    epoch:           u64,
    sender_id:       u32,
    candidate_count: u8,
    selected_ids:    Vec<u32>,
    prev_hash:       &[u8; 32],
) -> SelectionRecord {
    let selected_count = selected_ids.len() as u8;
    let record_hash = compute_selection_hash(
        epoch, sender_id, candidate_count, selected_count, &selected_ids, prev_hash,
    );
    SelectionRecord {
        epoch, sender_id, candidate_count, selected_count,
        selected_ids, record_hash, prev_hash: *prev_hash,
    }
}

// ─── Selection log ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SelectionLog {
    records: Vec<SelectionRecord>,
}

#[derive(Debug)]
pub enum SelectionError {
    StaleEpoch,
}

impl SelectionLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self)-> bool  { self.records.is_empty() }
    pub fn records(&self) -> &[SelectionRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(SELECTOR_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:           u64,
        sender_id:       u32,
        candidate_count: u8,
        selected_ids:    Vec<u32>,
    ) -> Result<&SelectionRecord, SelectionError> {
        if let Some(last) = self.records.last() {
            if epoch < last.epoch { return Err(SelectionError::StaleEpoch); }
        }
        let prev = self.last_hash();
        let r = build_selection_record(epoch, sender_id, candidate_count, selected_ids, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn avg_selected_count(&self) -> u8 {
        if self.records.is_empty() { return 0; }
        let sum: u32 = self.records.iter().map(|r| r.selected_count as u32).sum();
        (sum / self.records.len() as u32) as u8
    }

    pub fn zero_selection_count(&self) -> usize {
        self.records.iter().filter(|r| r.selected_count == 0).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SELECTOR_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_selection_hash(
                r.epoch, r.sender_id, r.candidate_count,
                r.selected_count, &r.selected_ids, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for SelectionLog {
    fn default() -> Self { Self::new() }
}

// ─── Peer selector ────────────────────────────────────────────────────────────

/// Core selection algorithm: deterministic, no RNG.
/// peer_scores: BTreeMap<peer_id, score(0–100)>
/// peer_latency_tiers: BTreeMap<peer_id, tier(0–3)>
///
/// Selection order: higher score first; ties broken by lower peer_id (BTreeMap ordering).
/// Returns sorted Vec<u32> of selected peer IDs.
pub fn select_peers(
    criteria:            &SelectionCriteria,
    peer_scores:         &BTreeMap<u32, u8>,
    peer_latency_tiers:  &BTreeMap<u32, u8>,
) -> (Vec<u32>, u8) {
    // Build eligible list: exclude sender, min_score, max_latency_tier
    // BTreeMap iteration is deterministic (sorted by key = peer_id)
    let mut eligible: Vec<(u32, u8)> = peer_scores.iter()
        .filter(|(&pid, &score)| {
            pid != criteria.sender_id
                && score >= criteria.min_score
                && peer_latency_tiers.get(&pid).copied().unwrap_or(3) <= criteria.max_latency_tier
        })
        .map(|(&pid, &score)| (pid, score))
        .collect();

    let candidate_count = eligible.len() as u8;

    // Sort by score descending, then by peer_id ascending for ties (deterministic)
    eligible.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));

    // Select up to max_fanout
    let take = (criteria.max_fanout as usize).min(eligible.len());
    let mut selected: Vec<u32> = eligible[..take].iter().map(|&(pid, _)| pid).collect();
    selected.sort_unstable(); // return in sorted order for determinism
    (selected, candidate_count)
}

/// Stateful selector with selection logging.
#[derive(Debug, Clone)]
pub struct PeerSelector {
    pub log: SelectionLog,
}

impl PeerSelector {
    pub fn new() -> Self { Self { log: SelectionLog::new() } }

    /// Select peers and record the selection.
    pub fn record_and_select(
        &mut self,
        epoch:               u64,
        criteria:            &SelectionCriteria,
        peer_scores:         &BTreeMap<u32, u8>,
        peer_latency_tiers:  &BTreeMap<u32, u8>,
    ) -> Result<(Vec<u32>, &SelectionRecord), SelectionError> {
        let (selected, candidate_count) = select_peers(criteria, peer_scores, peer_latency_tiers);
        let rec = self.log.record(epoch, criteria.sender_id, candidate_count, selected.clone())?;
        Ok((selected, rec))
    }
}

impl Default for PeerSelector {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn scores_3() -> BTreeMap<u32, u8> {
        let mut m = BTreeMap::new();
        m.insert(10, 80u8);
        m.insert(20, 60u8);
        m.insert(30, 40u8);
        m
    }

    fn latency_all_fast() -> BTreeMap<u32, u8> {
        let mut m = BTreeMap::new();
        m.insert(10, 0u8);
        m.insert(20, 0u8);
        m.insert(30, 0u8);
        m
    }

    fn criteria(sender: u32, fanout: u8, min_score: u8, max_lat: u8) -> SelectionCriteria {
        SelectionCriteria { sender_id: sender, max_fanout: fanout, min_score, max_latency_tier: max_lat }
    }

    // ── select_peers ──────────────────────────────────────────────────────────

    #[test]
    fn selects_up_to_fanout() {
        let (sel, _) = select_peers(&criteria(0, 2, 0, 3), &scores_3(), &latency_all_fast());
        assert_eq!(sel.len(), 2);
    }

    #[test]
    fn excludes_sender() {
        let (sel, _) = select_peers(&criteria(10, 10, 0, 3), &scores_3(), &latency_all_fast());
        assert!(!sel.contains(&10));
    }

    #[test]
    fn min_score_filters() {
        let (sel, cands) = select_peers(&criteria(0, 10, 70, 3), &scores_3(), &latency_all_fast());
        assert_eq!(sel, vec![10]); // only peer 10 has score ≥ 70
        assert_eq!(cands, 1);
    }

    #[test]
    fn latency_tier_filters() {
        let mut lat = latency_all_fast();
        lat.insert(10, 3u8); // peer 10 has Timeout tier
        let (sel, _) = select_peers(&criteria(0, 10, 0, 1), &scores_3(), &lat);
        assert!(!sel.contains(&10));
    }

    #[test]
    fn selection_is_sorted() {
        let (sel, _) = select_peers(&criteria(0, 3, 0, 3), &scores_3(), &latency_all_fast());
        let mut sorted = sel.clone();
        sorted.sort();
        assert_eq!(sel, sorted);
    }

    #[test]
    fn higher_score_preferred() {
        // fanout=1: should select peer with highest score (10 → score 80)
        let (sel, _) = select_peers(&criteria(0, 1, 0, 3), &scores_3(), &latency_all_fast());
        assert_eq!(sel, vec![10]);
    }

    #[test]
    fn no_eligible_peers() {
        let (sel, cands) = select_peers(&criteria(0, 5, 100, 3), &scores_3(), &latency_all_fast());
        assert!(sel.is_empty());
        assert_eq!(cands, 0);
    }

    #[test]
    fn all_excluded_by_sender() {
        let mut scores = BTreeMap::new();
        scores.insert(1u32, 99u8);
        let lat = BTreeMap::new();
        let (sel, _) = select_peers(&criteria(1, 5, 0, 3), &scores, &lat);
        assert!(sel.is_empty());
    }

    // ── SelectionRecord ───────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_selection_record(1, 0, 3, vec![10, 20], &SELECTOR_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_selection_record(1, 0, 3, vec![10, 20], &SELECTOR_GENESIS_HASH);
        let r2 = build_selection_record(1, 0, 3, vec![10, 20], &SELECTOR_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn different_selected_different_hash() {
        let r1 = build_selection_record(1, 0, 3, vec![10, 20], &SELECTOR_GENESIS_HASH);
        let r2 = build_selection_record(1, 0, 3, vec![10, 30], &SELECTOR_GENESIS_HASH);
        assert_ne!(r1.record_hash, r2.record_hash);
    }

    // ── SelectionLog ──────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = SelectionLog::new();
        assert!(l.is_empty());
        assert_eq!(l.avg_selected_count(), 0);
        assert_eq!(l.zero_selection_count(), 0);
    }

    #[test]
    fn log_records_and_stats() {
        let mut l = SelectionLog::new();
        l.record(1, 0, 5, vec![10, 20, 30]).unwrap();
        l.record(2, 0, 2, vec![]).unwrap(); // zero selection
        l.record(3, 0, 4, vec![10]).unwrap();
        assert_eq!(l.avg_selected_count(), 1); // (3+0+1)/3=1
        assert_eq!(l.zero_selection_count(), 1);
    }

    #[test]
    fn chain_links() {
        let mut l = SelectionLog::new();
        l.record(1, 0, 3, vec![10]).unwrap();
        l.record(2, 0, 3, vec![20]).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = SelectionLog::new();
        for e in 1..=5u64 {
            l.record(e, 0, 3, vec![10, 20]).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── PeerSelector ──────────────────────────────────────────────────────────

    #[test]
    fn record_and_select_works() {
        let mut ps = PeerSelector::new();
        let (sel, rec) = ps.record_and_select(
            1, &criteria(0, 2, 0, 3), &scores_3(), &latency_all_fast(),
        ).unwrap();
        assert_eq!(sel.len(), 2);
        assert_eq!(rec.selected_count, 2);
        assert_eq!(ps.log.len(), 1);
    }
}
