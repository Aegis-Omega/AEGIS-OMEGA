//! Gate 224: Constitutional Chord Network
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! A peer table that tracks ConstitutionalChord values from multiple nodes.
//! Detects when the network splits into incompatible resonance classes and
//! produces a NetworkResonanceReport summarizing the cluster structure.
//!
//! NetworkResonanceReport classifies the network into:
//!   - UNIFIED:    all nodes share the same chord (same VortexFamily + PhiClass)
//!   - CLUSTERED:  multiple compatible groups (≥2 chord classes, each internally resonant)
//!   - SPLIT:      some nodes are AbovePhi (drift detected) while others are BelowPhi
//!
//! Peer table is BTreeMap<node_id: String, ConstitutionalChord> — deterministic iteration.
//! No HashMap. No mutable global state. All f64 arithmetic is bounded and reproducible.
//!
//! Use case: the bridge can aggregate chord_bytes from multiple /node polls
//! (simulated peers, cloud replicas, CI nodes) and detect constitutional drift
//! before it causes replay divergence.
//!
//! Copyright (C) 2025 Tarik Skalić — AGPL-3.0-or-later

use std::collections::BTreeMap;
use crate::constitutional_chord::{ConstitutionalChord, PhiClass, chords_in_resonance};
use crate::vortex_classifier::VortexFamily;

// ─── Network verdict ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum NetworkVerdict {
    Unified   = 0, // all peers share the same resonance chord
    Clustered = 1, // multiple distinct chords, none AbovePhi
    Split     = 2, // at least one AbovePhi peer alongside BelowPhi peers
}

// ─── Network report ───────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct NetworkResonanceReport {
    pub verdict: NetworkVerdict,
    pub peer_count: usize,
    pub below_phi_count: usize,     // peers with PhiClass::BelowPhi
    pub at_phi_count: usize,        // peers with PhiClass::AtPhi
    pub above_phi_count: usize,     // peers with PhiClass::AbovePhi
    pub triadic_count: usize,
    pub hexadic_count: usize,
    pub distinct_chord_classes: usize, // number of (VortexFamily, PhiClass) pairs present
    pub all_below_phi: bool,        // every peer is constitutionally convergent
    pub quorum_triadic: bool,       // > 61.8% of peers are Triadic (1/φ threshold)
}

impl NetworkResonanceReport {
    pub fn is_constitutionally_sound(&self) -> bool {
        self.all_below_phi && self.verdict != NetworkVerdict::Split
    }
}

#[derive(Debug)]
pub struct NetworkError(pub &'static str);

impl std::fmt::Display for NetworkError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "NetworkError: {}", self.0)
    }
}

// ─── Peer table ───────────────────────────────────────────────────────────

/// Immutable peer chord table (BTreeMap for deterministic iteration).
#[derive(Debug, Clone, Default)]
pub struct ChordNetwork {
    peers: BTreeMap<String, ConstitutionalChord>,
}

impl ChordNetwork {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    /// Register or update a peer's chord. Returns a new ChordNetwork (immutable pattern).
    pub fn register(&self, node_id: &str, chord: ConstitutionalChord) -> Self {
        let mut peers = self.peers.clone();
        peers.insert(node_id.to_owned(), chord);
        Self { peers }
    }

    /// Remove a peer from the network. Returns a new ChordNetwork.
    pub fn deregister(&self, node_id: &str) -> Self {
        let mut peers = self.peers.clone();
        peers.remove(node_id);
        Self { peers }
    }

    /// Look up a peer's chord. O(log n).
    pub fn get(&self, node_id: &str) -> Option<&ConstitutionalChord> {
        self.peers.get(node_id)
    }

    /// Produce a full network resonance report. O(n log n) — BTreeMap iteration.
    /// Returns Err if peer table is empty.
    pub fn analyze(&self) -> Result<NetworkResonanceReport, NetworkError> {
        if self.peers.is_empty() {
            return Err(NetworkError("empty peer table — at least one peer required"));
        }

        let mut below_phi = 0usize;
        let mut at_phi = 0usize;
        let mut above_phi = 0usize;
        let mut triadic = 0usize;
        let mut hexadic = 0usize;

        // BTreeMap iteration is sorted by node_id — fully deterministic
        for chord in self.peers.values() {
            match chord.phi_class {
                PhiClass::BelowPhi => below_phi += 1,
                PhiClass::AtPhi    => at_phi    += 1,
                PhiClass::AbovePhi => above_phi += 1,
            }
            match chord.vortex_family {
                VortexFamily::Triadic => triadic += 1,
                VortexFamily::Hexadic => hexadic += 1,
            }
        }

        let peer_count = self.peers.len();

        // Count distinct (VortexFamily, PhiClass) pairs — BTreeMap over Ord types
        let mut class_counts: BTreeMap<(u8, u8), usize> = BTreeMap::new();
        for chord in self.peers.values() {
            *class_counts
                .entry((chord.vortex_family as u8, chord.phi_class as u8))
                .or_insert(0) += 1;
        }
        let distinct_chord_classes = class_counts.len();

        // Verdict classification
        let verdict = if above_phi > 0 && below_phi > 0 {
            NetworkVerdict::Split
        } else if distinct_chord_classes == 1 {
            NetworkVerdict::Unified
        } else {
            NetworkVerdict::Clustered
        };

        let all_below_phi = below_phi == peer_count;

        // 1/φ quorum for Triadic: triadic/peer_count >= 618034/1_000_000
        let quorum_triadic = triadic * 1_000_000 >= peer_count * 618_034;

        Ok(NetworkResonanceReport {
            verdict,
            peer_count,
            below_phi_count: below_phi,
            at_phi_count: at_phi,
            above_phi_count: above_phi,
            triadic_count: triadic,
            hexadic_count: hexadic,
            distinct_chord_classes,
            all_below_phi,
            quorum_triadic,
        })
    }

    /// Returns all peers that are NOT in resonance with the given chord.
    /// BTreeMap iteration → deterministic order of returned node_ids.
    pub fn find_dissonant(&self, reference: &ConstitutionalChord) -> Vec<String> {
        self.peers
            .iter()
            .filter(|(_, chord)| !chords_in_resonance(chord, reference))
            .map(|(id, _)| id.clone())
            .collect()
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::constitutional_chord::{compute_chord, PhiClass};
    use crate::resonance_monitor::check_resonance;
    use crate::ring_composition::build_ring;

    fn h(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[7] = seed; // leading u64 big-endian = seed
        h
    }

    // span = 3 → digital_root(3) = 3 → Triadic; drift_risk=0.1 < 0.618 → BelowPhi
    fn good_triadic_report() -> crate::resonance_monitor::ResonanceReport {
        let ring = build_ring(&[h(9), h(3)], None);
        check_resonance(0.1, 1, 4, &ring, 10, Some(9))
    }

    // span = 1 → digital_root(1) = 1 → Hexadic; drift_risk=0.1 < 0.618 → BelowPhi
    fn good_hexadic_report() -> crate::resonance_monitor::ResonanceReport {
        let ring = build_ring(&[h(9), h(3)], None);
        check_resonance(0.1, 0, 1, &ring, 10, Some(9))
    }

    // span = 3 → Triadic; drift_risk=0.9 > 0.618 → AbovePhi
    fn drift_report() -> crate::resonance_monitor::ResonanceReport {
        let ring = build_ring(&[h(9), h(3)], None);
        check_resonance(0.9, 1, 4, &ring, 10, Some(9))
    }

    fn good_report() -> crate::resonance_monitor::ResonanceReport { good_triadic_report() }

    #[test]
    fn empty_network_returns_err() {
        let net = ChordNetwork::new();
        assert!(net.analyze().is_err());
    }

    #[test]
    fn single_peer_unified() {
        let chord = compute_chord(&h(9), &good_report());
        let net = ChordNetwork::new().register("node-a", chord);
        let report = net.analyze().unwrap();
        assert_eq!(report.verdict, NetworkVerdict::Unified);
        assert_eq!(report.peer_count, 1);
        assert!(report.all_below_phi);
    }

    #[test]
    fn all_identical_chords_unified() {
        let chord = compute_chord(&h(9), &good_report());
        let net = ChordNetwork::new()
            .register("a", chord)
            .register("b", chord)
            .register("c", chord);
        let report = net.analyze().unwrap();
        assert_eq!(report.verdict, NetworkVerdict::Unified);
        assert_eq!(report.distinct_chord_classes, 1);
        assert_eq!(report.peer_count, 3);
    }

    #[test]
    fn below_and_above_phi_is_split() {
        let good = compute_chord(&h(9), &good_report());
        let drift = compute_chord(&h(9), &drift_report());
        let net = ChordNetwork::new()
            .register("good", good)
            .register("drift", drift);
        let report = net.analyze().unwrap();
        assert_eq!(report.verdict, NetworkVerdict::Split);
        assert!(!report.is_constitutionally_sound());
    }

    #[test]
    fn all_below_phi_unified_is_sound() {
        let chord = compute_chord(&h(9), &good_report());
        let net = ChordNetwork::new()
            .register("x", chord)
            .register("y", chord);
        let report = net.analyze().unwrap();
        assert!(report.is_constitutionally_sound());
    }

    #[test]
    fn counts_phi_classes_correctly() {
        let good = compute_chord(&h(9), &good_report());
        let drift = compute_chord(&h(9), &drift_report());
        let net = ChordNetwork::new()
            .register("a", good)
            .register("b", good)
            .register("c", drift);
        let report = net.analyze().unwrap();
        assert_eq!(report.below_phi_count, 2);
        assert_eq!(report.above_phi_count, 1);
        assert!(!report.all_below_phi);
    }

    #[test]
    fn quorum_triadic_five_of_eight_passes() {
        // 5/8 = 0.625 >= 0.618034 → quorum_triadic=true
        let triadic = compute_chord(&h(9), &good_triadic_report()); // Triadic
        let hexadic = compute_chord(&h(1), &good_hexadic_report()); // Hexadic
        let net = ChordNetwork::new()
            .register("t1", triadic).register("t2", triadic)
            .register("t3", triadic).register("t4", triadic)
            .register("t5", triadic)
            .register("h1", hexadic).register("h2", hexadic)
            .register("h3", hexadic);
        let report = net.analyze().unwrap();
        assert_eq!(report.triadic_count, 5);
        assert_eq!(report.hexadic_count, 3);
        assert!(report.quorum_triadic);
    }

    #[test]
    fn quorum_triadic_four_of_eight_fails() {
        // 4/8 = 0.5 < 0.618034 → quorum_triadic=false
        let triadic = compute_chord(&h(9), &good_triadic_report());
        let hexadic = compute_chord(&h(1), &good_hexadic_report());
        let net = ChordNetwork::new()
            .register("t1", triadic).register("t2", triadic)
            .register("t3", triadic).register("t4", triadic)
            .register("h1", hexadic).register("h2", hexadic)
            .register("h3", hexadic).register("h4", hexadic);
        let report = net.analyze().unwrap();
        assert!(!report.quorum_triadic);
    }

    #[test]
    fn register_deregister_immutable_pattern() {
        let chord = compute_chord(&h(9), &good_report());
        let net0 = ChordNetwork::new();
        let net1 = net0.register("a", chord);
        assert_eq!(net0.peer_count(), 0); // original unchanged
        assert_eq!(net1.peer_count(), 1);
        let net2 = net1.deregister("a");
        assert_eq!(net1.peer_count(), 1); // net1 unchanged
        assert_eq!(net2.peer_count(), 0);
    }

    #[test]
    fn find_dissonant_empty_for_unified_network() {
        let chord = compute_chord(&h(9), &good_report());
        let net = ChordNetwork::new()
            .register("a", chord)
            .register("b", chord);
        let dissonant = net.find_dissonant(&chord);
        assert!(dissonant.is_empty());
    }

    #[test]
    fn find_dissonant_identifies_drift_node() {
        let good = compute_chord(&h(9), &good_report());
        let drift = compute_chord(&h(9), &drift_report());
        let net = ChordNetwork::new()
            .register("good1", good)
            .register("good2", good)
            .register("drifter", drift);
        let dissonant = net.find_dissonant(&good);
        assert_eq!(dissonant, vec!["drifter"]);
    }

    #[test]
    fn find_dissonant_sorted_by_node_id() {
        let good = compute_chord(&h(9), &good_report());
        let drift = compute_chord(&h(9), &drift_report());
        let net = ChordNetwork::new()
            .register("zebra", drift)
            .register("alpha", drift)
            .register("middle", good);
        let dissonant = net.find_dissonant(&good);
        // BTreeMap iteration → alphabetical order
        assert_eq!(dissonant, vec!["alpha", "zebra"]);
    }

    #[test]
    fn determinism_x3() {
        let chord = compute_chord(&h(9), &good_report());
        let net = ChordNetwork::new()
            .register("n1", chord)
            .register("n2", chord)
            .register("n3", chord);
        let r1 = net.analyze().unwrap();
        let r2 = net.analyze().unwrap();
        let r3 = net.analyze().unwrap();
        assert_eq!(r1.verdict, r2.verdict);
        assert_eq!(r2.verdict, r3.verdict);
        assert_eq!(r1.peer_count, r3.peer_count);
        assert_eq!(r1.triadic_count, r3.triadic_count);
    }

    #[test]
    fn clustered_verdict_two_below_phi_different_vortex() {
        // Two nodes: different VortexFamily, both BelowPhi → Clustered (not Unified, not Split)
        let triadic = compute_chord(&h(9), &good_triadic_report()); // Triadic, BelowPhi
        let hexadic = compute_chord(&h(1), &good_hexadic_report()); // Hexadic, BelowPhi
        let net = ChordNetwork::new()
            .register("t", triadic)
            .register("h", hexadic);
        let report = net.analyze().unwrap();
        assert_eq!(report.verdict, NetworkVerdict::Clustered);
        assert!(report.all_below_phi); // both are convergent despite different families
    }

    #[test]
    fn network_verdict_ordering() {
        assert!(NetworkVerdict::Unified < NetworkVerdict::Clustered);
        assert!(NetworkVerdict::Clustered < NetworkVerdict::Split);
    }
}
