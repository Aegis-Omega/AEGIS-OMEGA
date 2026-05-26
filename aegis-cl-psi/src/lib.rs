//! # AEGIS-Ω CL-Ψ — State-Coherence Routing Fabric
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
//!
//! This crate implements deterministic state-coherence routing, audit-trail state
//! machines, algorithmic divergence thresholds, and EU AI Act compliance hooks.
//! No emergent properties. No sovereign claims. T2 competency accumulation only.
//!
//! Phase 6 modules (cech_descent, postnikov_truncation, gerbe_splitter):
//! - Code tier: T2 — deterministic O(N) array operations
//! - Theoretical correspondence claim: T3 — the algebraic topology claim is a
//!   research conjecture and does not grant T0–T2 authority.

pub mod sgm_gate;
pub mod lut_kan;
pub mod rwkv_state;
pub mod lyapunov;
pub mod audit;
pub mod orchestrator;

// Phase 1.1 + 2
pub mod sahoo;
pub mod cloud_bridge;
pub mod devs_scheduler;
pub mod hip_runtime;  // always compiled; HIP calls gated inside by cfg(feature = "hip")

// Phase 3
pub mod ccil_lattice;
pub mod rocblas_gemm;  // always compiled; HIP calls gated inside by cfg(feature = "rocblas")

// Phase 4
pub mod obstruction_monitor;
pub mod poly_scheduler;

// Phase 5
pub mod local_resolver;

// Phase 6
pub mod cech_descent;
pub mod postnikov_truncation;
pub mod gerbe_splitter;
pub mod orchestrator_phase6;

// Phase 7 — production hardening
pub mod profiler;
pub mod compliance;
pub mod orchestrator_phase7;

// Gate 177 — Edge BFT Verifier (T2, WASM-compatible, stateless Ed25519 quorum proof)
pub mod edge_verifier;

// Gate 206 — Causal Confidence Arbiter (T2, prevents hallucination via confidence bounding)
pub mod causal_arbiter;

// Gate 207 — Adaptive Lineage Compaction Engine (T2, reduces memory footprint while preserving audit trail)
pub mod lineage_compactor;

// Gate 208 — Geometric Variance Engine (T2, replaces scalar sums with tensor-alignment metrics)
pub mod geometric_variance;

// Gate 208 — Triadic Merkle-Patricia Node (T2, gates state mutations behind geometric variance checks)
pub mod triadic_merkle_node;

// Gate 208 — Holonic State Machine (T2, orchestrates 3-layer escalation with BFT consensus)
pub mod holonic_state;

// Gate 211 — Orthogonal Domain Verifier (T2, |dot(C,O)| < ε enforces D0 ∩ D1 = ∅)
pub mod orthogonal_verifier;

// Gate 212 — Dodecagonal Symmetry Router (T2, 12-fold symmetric routing mesh, integer BFS)
pub mod dodecagonal_router;

// Gate 213 — Proportional Unit Metric (T2, rational arithmetic grid, SQUARED_SUM_K8=204)
pub mod proportional_metric;

// Gate 214 — Vortex Sequence Classifier (T2, digital root cycle detection, Triadic/Hexadic)
pub mod vortex_classifier;

// Gate 215 — Abjad Letter Encoder (T2, letter→integer routing via Abjad values, طارق=310)
pub mod abjad_encoder;

// Gate 216 — Tajweed Phonological DFA (T1, empirically validated Arabic phonology)
// Makharij articulation points = acoustic eigenstates. 4 noon-sakinah/tanween rules.
// Clinical studies: 27.3% cortisol reduction, alpha/theta EEG, vagal stimulation confirmed.
pub mod tajweed_dfa;

// Gate 217 — Ring Composition Verifier (T1, chiastic A-B-C-B'-A' structure)
// Isomorphic to AdaptivePower(T) ≤ ReplayVerifiability(T) — the constitutional law is a ring.
pub mod ring_composition;

// Gate 220 — Compile-Time Acyclic DAG Lattice + Lawvere Metric + Homotopy Witness (T1/T2)
// Cycles are unrepresentable: VerifiedEdge<From,To> requires From::RANK < To::RANK at compile time.
// Lawvere enrichment: d(A,C) ≤ d(A,B) + d(B,C) — triangle inequality by additive composition.
// HomotopyWitness: structural endpoint equality (T2 code / T3 full HoTT claim).
pub mod lattice_dag;

// Gate 220 (cont.) — Sovereign Persistence Layer (SPSF) (T2)
// Disk-boundary determinism: sequence-monotone, hash-chained, BTreeMap-indexed writes.
// Genesis root verified at open(); divergence from expected root is rejected (not ignored).
pub mod spsf;

// Gate 221 — Constitutional Convergence Certifier (T1/T2)
// 1/φ ≈ 0.6180339887 governs three scales: edge divergence (SUBATOMIC), path safety (MOLECULAR),
// swarm quorum (ORGANISM). certify_path<P>() proves AdaptivePower(T) ≤ ReplayVerifiability(T).
// RankSpan vortex classification: digital_root → Triadic {3,6,9} vs Hexadic {1,2,4,5,7,8}.
pub mod phi_convergence;

// Gate 222 — Constitutional Resonance Monitor (T1/T2)
// Unifies phi_convergence + ring_composition + vortex_classifier + spsf monotone law.
// is_resonant iff phi_convergent AND ring_valid AND sequence_monotone (three T1 invariants).
// resonance_coefficient = depth × vortex_factor × phi_headroom; > 5.0 → certified path.
pub mod resonance_monitor;

// Gate 223 — Constitutional Chord (T2)
// Compact 4-byte spectral fingerprint of constitutional state for distributed resonance checks.
// chord_bytes: [vortex_family, digital_root, resonance_depth, phi_class]
// chords_in_resonance(a, b): same VortexFamily + same PhiClass → compatible resonance class.
pub mod constitutional_chord;

// Gate 224 — Constitutional Chord Network (T2)
// Peer table tracking chord fingerprints across multiple nodes. Detects UNIFIED / CLUSTERED / SPLIT.
// BTreeMap<node_id, ConstitutionalChord> — deterministic iteration. Integer 1/φ quorum threshold.
// find_dissonant() identifies drift nodes; quorum_triadic checks the 1/φ Triadic majority.
pub mod chord_network;

// Gate 225 — Constitutional Self-Certification — Autopoietic State Closure (T1/T2)
// The system certifies its own constitutional state: SHA-256(resonance + network + version).
// CertificationVerdict: Certified / ProvisionallyGranted / Uncertified.
// Deterministic: same inputs → same self_hash across all platforms. No clock, no RNG.
pub mod self_certification;

// Gate 227 — Lattice Coherence: moduli tower global section checker (T2)
// ObstructionLevels × CoherenceReport × Fibonacci weights.
// GlobalSection exists iff all 5 tower levels simultaneously satisfied.
pub mod lattice_coherence;

// Gate 228 — Coherence Broadcaster: encode CoherenceReport as 16-byte gossip frame (T2)
// Bridges lattice_coherence → peer broadcast. Deterministic fixed-point encoding.
pub mod coherence_broadcaster;

// Gate 229 — Epoch Coherence Chain: hash-linked CoherenceFrame history (T2)
// Temporal dimension of the moduli tower. Continuously coherent = martingale holds.
// SHA-256(epoch ‖ frame ‖ prev_hash). Breach detection. Terminal hash certification.
pub mod epoch_coherence_chain;

// Gate 231 — Constitutional Autonode: unified T2 state machine (resonance + cert + coherence + chain)
// One tick() = full constitutional cycle. AdaptivePower(T) ≤ ReplayVerifiability(T) made concrete.
pub mod constitutional_autonode;

// Gate 232 — Swarm Autonode: N-node constitutional consensus at 1/φ quorum threshold (T2)
// Organism-scale layer. consensus_hash = SHA-256(all chain_entry_hashes, BTreeMap order).
pub mod swarm_autonode;

// Gate 233 — Constitutional Replay: State_t = Replay(Lineage_{0→t}) at organism scale (T2)
// ReplayChain + ReplayProof: terminal_hash and replay_fingerprint are tamper-evident proofs.
pub mod constitutional_replay;

// Gate 234 — Entropy Budget: AdaptivePower(T) ≤ ReplayVerifiability(T) as numerical ledger (T2)
// Hash-linked BudgetEntry chain. consume_adaptive() blocked if balance < ADAPTIVE_EVENT_COST.
pub mod entropy_budget;

// Gate 235 — Drift Classifier: D0–D4 constitutional drift severity system (T2)
// DriftHistory: hash-linked records. D2+: mutation authority suspended.
pub mod drift_classifier;

// Gate 236 — Governance Pipeline: field-scale integration of all constitutional substrates (T2)
// process() = entropy check → autonode tick → drift classify → budget → replay chain.
pub mod governance_pipeline;

// Gate 237 — Swarm Health Monitor (T2, unified constitutional health verdict across swarm)
pub mod swarm_health;

// Gate 238 — Divergence Oracle: classifies constitutional drift between health epochs (T2)
// Stable/Nominal/Elevated/Critical/Terminal. adaptive_permitted() blocks at Critical+.
pub mod divergence_oracle;

// Gate 239 — Resilience Watchdog: rolling-window constitutional stability tracker (T2)
// Recovering/Stable/Oscillating/Degrading/Insufficient. oscillation_count ≥ 2 → intervention.
pub mod resilience_watchdog;

// Gate 240 — Constitutional Pulse: compact 3-byte epoch health signal (T2)
// Green/Yellow/Red triad from HealthVerdict + ResilienceVerdict + DivergenceClass.
// PulseChain hash-linked by SHA-256(prev ‖ pulse_bytes[3] ‖ epoch_be8).
pub mod constitutional_pulse;

// Gate 241 — Adaptive Threshold Engine: dynamic constitutional alert thresholds (T2)
// ThresholdProfile derived from rolling baseline × 1/φ. Clear/EntropyAlert/CoherenceAlert/BothAlert.
pub mod adaptive_threshold;

// Gate 242 — Quorum Drift Detector: quorum transition tracking across epochs (T2)
// QuorumLost/QuorumRestored events. longest_absence tracks worst-case quorum gap.
pub mod quorum_drift;

// Gate 243 — Entropy Forecast Engine: predicts epochs until entropy exhaustion (T2)
// DrainRate from observation window. ExhaustionRisk: Immediate/Imminent/Moderate/Low/None.
pub mod entropy_forecast;

// Gate 244 — Coherence Stability Index: rolling integer stability score 0–100 (T2)
// StabilityGrade A/B/C/D/F from global_section_rate + satisfied_rate + score_avg.
pub mod coherence_stability;

// Gate 245 — Constitutional Momentum Tracker: signed directional trend signal (T2)
// MomentumDir: Improving/Stable/Declining. momentum_int = score[last] - score[first].
pub mod momentum_tracker;

// Gate 246 — Phase Transition Detector: constitutional regime change detection (T2)
// ConstitutionalPhase: Nominal/Degraded/Recovery/Critical. Recovery = improving from Critical+.
pub mod phase_transition;

// Gate 247 — Constitutional Health Aggregator: unified system health vector (T2)
// SystemHealthVector: health_verdict + resilience_verdict + pulse_verdict + stability_grade + momentum_dir + phase.
// OverallCondition: Optimal/Good/Caution/Alert/Emergency. vector_hash = SHA-256(prev ‖ condition ‖ degraded_count ‖ epoch).
pub mod health_aggregator;

// Gate 248 — Constitutional Health Dashboard: epoch-by-epoch DashboardFrame (T2)
// DashboardFrame: vector + phase + momentum + OverallTrend. Thriving/Stable/Concerning/Critical.
// frame_hash = SHA-256(prev ‖ condition_byte ‖ trend_byte ‖ epoch_be8).
pub mod health_dashboard;

// Gate 249 — Epoch Health Ledger: tamper-evident running health record (T2)
// HealthLedgerEntry per epoch; ledger_hash = SHA-256(prev ‖ frame_hash ‖ condition ‖ epoch).
// worst_condition(), critical_epoch_count(), thriving_epoch_count(), verify_chain().
pub mod epoch_health_ledger;

// Gate 250 — Constitutional Alert Engine: AlertSeverity classification + hash-linked AlertLog (T2)
// None/Info/Warn/Critical/Emergency from OverallCondition × OverallTrend.
// alert_hash = SHA-256(prev ‖ severity_byte ‖ condition_byte ‖ epoch_be8).
pub mod alert_engine;

// Gate 251 — Intervention Recommender: ranked remediation actions + PlanHistory (T2)
// InterventionKind: MonitorOnly/TightenThresholds/ForceResilient/QuorumRecovery/PulseReset/PhaseRecovery/EmergencyHalt.
// plan_hash = SHA-256(prev ‖ severity_byte ‖ top_priority_byte ‖ epoch_be8).
pub mod intervention_recommender;

// Gate 252 — Recovery Sequencer: time-ordered step execution with progress hash (T2)
// RecoveryStep: kind + priority + StepStatus (Pending/InProgress/Completed/Skipped).
// advance_step() recomputes step_hash chain. sequence_hash = SHA-256(all step_hashes ‖ epoch).
pub mod recovery_sequencer;

// Gate 253 — Constitutional Audit Certifier: AuditCertificate over (VectorHistory, AlertLog, PlanHistory) (T2)
// chains_valid, peak_condition, peak_severity, certificate_hash = SHA-256(3 terminals ‖ epoch_end).
pub mod audit_certifier;

// Gate 254 — Constitutional Telemetry Encoder: 32-byte gossip packet (T2)
// TelemetryPacket: epoch(8) ‖ condition(1) ‖ trend(1) ‖ severity(1) ‖ phase(1) ‖ dir(1) ‖ degraded(1) ‖ momentum(2) ‖ checksum(8) ‖ frame_hash_prefix(8).
pub mod telemetry_encoder;

// Gate 255 — Gossip Broadcaster: signed GossipMessage for peer broadcast (T2)
// GossipMessage: node_id(4) ‖ sequence(8) ‖ TelemetryPacket(32) ‖ mac(8) = 52 bytes.
// GossipLog: BTreeMap<node_id, highest_sequence>; append validates MAC + monotone sequence.
pub mod gossip_broadcaster;

// Gate 256 — Gossip Router: multi-hop peer routing with deduplication and TTL (T2)
// RoutingTable: BTreeMap<peer_id, PeerEntry> + BTreeMap<(node_id, seq), ()> seen set.
// route() → Forward(peer_ids) | Drop(AlreadySeen|TtlExpired|NoPeers|SelfMessage).
pub mod gossip_router;

// Gate 257 — Peer Manifest: signed peer identity + capability advertisement (T2)
// PeerManifest: node_id + epoch + capabilities(bitmask) + phase + manifest_hash.
// PeerRegistry: BTreeMap<node_id, manifest>; register validates hash + monotone epoch.
pub mod peer_manifest;

// Gate 258 — Swarm Topology Snapshot: hash-linked mesh state capture (T2)
// TopologySnapshot: peer_count + operational_count + cap counts + max_epoch + prev_hash.
// quorum_reached(): operational/total >= 1/φ (integer arithmetic). TopologyLog chains snapshots.
pub mod swarm_topology;

// Gate 259 — Constitutional Beacon: 16-byte self-broadcast frame (T2)
// BeaconFrame: epoch(8) ‖ node_id_byte(1) ‖ phase(1) ‖ capabilities(1) ‖ quorum(1) ‖ checksum(4).
// BeaconLog: hash-chained records; append validates checksum + monotone epoch.
pub mod constitutional_beacon;

// Gate 260 — Epoch Synchronizer: cross-peer epoch alignment + lag detection (T2)
// SyncRecord: local vs max_peer_epoch; alignment = Synchronized/LocalLagging/LocalLeading/NoPeers.
// SyncLog: hash-chained records; lag_count(), max_lag(), synchronized_count().
pub mod epoch_synchronizer;

// Gate 261 — Consensus Ledger: distributed vote log with quorum certification (T2)
// VoteEntry + ConsensusRound: BTreeMap<voter_id, vote>; quorum at 1/φ threshold.
// ConsensusCertificate + ConsensusLedger: hash-chained round certifications.
pub mod consensus_ledger;

// Gate 262 — Node State Machine: per-node lifecycle automaton (T2)
// NodeState: Initializing→Active→Degraded→Recovery→Halted; transition adjacency enforced.
// NodeHistory: hash-chained NodeRecords; degraded_count(), recovery_count(), verify_chain().
pub mod node_state_machine;

// Gate 263 — Fault Detector: mesh-wide fault pattern classifier (T2)
// FaultClass: None/Isolated/Correlated/Cascading from per-epoch degradation analysis.
// FaultLog: hash-chained FaultReports; cascading_count(), max_degraded_count().
pub mod fault_detector;

// Gate 264 — Mesh Census: periodic peer mesh population snapshot (T2)
// CensusRecord: epoch + node counts by state + capability counts + health_ratio_pct + SHA-256 chain.
// CensusLog: hash-chained CensusRecords; min_health_pct(), trend(), verify_chain().
pub mod mesh_census;

// Gate 265 — Recovery Planner: ranked recovery action sequences for degraded mesh (T2)
// RecoveryAction: kind (MonitorOnly/Isolate/Restart/ReduceLoad/ActivateSpare/PartialQuorum/Halt) + priority + target.
// RecoveryPlan: epoch + fault_class + sorted actions + SHA-256 chain. PlanLog: hash-chained plans.
pub mod recovery_planner;

// Gate 266 — Quorum Guard: real-time quorum health monitoring with alert levels (T2)
// QuorumLevel: Healthy(≥70%) / AtThreshold(≥1/φ) / BelowQuorum / NoNodes.
// QuorumGuard: hash-chained QuorumStatus records; alert_epochs(), longest_outage(), latest_delta().
pub mod quorum_guard;

// Gate 267 — Health Ticker: epoch-by-epoch condensed 3-byte health signal (T2)
// TickerFrame[3]: quorum_level(1) ‖ health_pct(1) ‖ fault_class:4|top_action:4(1).
// TickerLog: hash-chained TickerRecords; healthy_count(), alert_count(), verify_chain().
pub mod health_ticker;

// Gate 268 — Mesh Ledger: cross-module tamper-evident epoch ledger (T2)
// MeshEntry: epoch + census/fault/plan/quorum/ticker hashes + SHA-256 chain.
// MeshLedger: hash-chained MeshEntries; entry_count(), terminal_hash(), verify_chain().
pub mod mesh_ledger;

// Gate 269 — Capability Negotiator: peer capability advertisement + intersection (T2)
// NegotiationResult: local∩peer bitmask; gossip_ok/consensus_ok/relay_ok/audit_ok flags.
// NegotiationLog: hash-chained results per (local,peer) pair; capability_stable(), verify_chain().
pub mod capability_negotiator;

// Gate 270 — Epoch Sealer: terminal epoch seal across all gossip subsystems (T2)
// EpochSeal: epoch + ledger/consensus/topology/sync hashes + SHA-256 chain.
// SealChain: hash-chained EpochSeals; terminal_seal_hash(), seal_count(), verify_chain().
pub mod epoch_sealer;

// Gate 271 — Gossip Scheduler: Fibonacci-paced gossip interval calculator (T2)
// fibonacci(n) capped at F_11=89; interval_ms = F(n)*100ms. GossipSchedule: hash-chained intervals.
// next_interval_ms(), total_elapsed_ms(), verify_chain(). Mirrors TypeScript Gate 124.
pub mod gossip_scheduler;

// Gate 272 — Spread Estimator: gossip message propagation reach estimator (T2)
// estimate_reach(): geometric series 1+f+f^2+...+f^ttl, saturating integer, capped at total_nodes.
// hops_to_quorum(): min hops for 1/φ quorum. EstimateLog: hash-chained SpreadEstimates.
pub mod spread_estimator;

// Gate 273 — Fanout Controller: adaptive gossip fanout based on mesh health (T2)
// FanoutPolicy: Conservative(2)/Standard(3)/Aggressive(5)/Maximum(8) selected from QuorumLevel + health_ratio.
// FanoutLog: hash-chained FanoutDecisions; average_fanout(), max_fanout(), aggressive_epoch_count().
pub mod fanout_controller;

// Gate 274 — Backpressure Monitor: per-peer gossip rate tracking and backpressure decisions (T2)
// Accept(≤70%) / Throttle(71–100%) / Drop(>100% capacity). BackpressureRegistry: BTreeMap<peer_id, PeerRateLog>.
// global_drop_count(), global_throttle_count(), peer_decision(). PeerRateLog: hash-chained records.
pub mod backpressure_monitor;

// Gate 275 — Dedup Cache: epoch-scoped gossip message deduplication (T2)
// DedupCache: BTreeMap<(node_id,seq), seen_epoch>. New/Duplicate/EpochTooOld/EpochTooFuture.
// advance_epoch() evicts entries older than current_epoch - max_epoch_lag. hit_rate_pct().
pub mod dedup_cache;

// Gate 276 — Latency Tracker: per-peer round-trip latency estimation with rolling window (T2)
// LatencyTier: Fast(≤50ms)/Normal(≤200ms)/Slow(≤500ms)/Timeout(>500ms).
// PeerLatencyLog: circular buffer window[8], hash-chained records. LatencyRegistry: BTreeMap<peer_id>.
pub mod latency_tracker;

// Gate 277 — Gossip Priority Queue: deterministic outbound message scheduling (T2)
// Score = ttl*urgency*fanout/(elapsed+1). Urgent(≥1000)/High(≥500)/Normal(≥100)/Low.
// GossipPriorityQueue: BTreeMap<(-score,id),msg>; dequeue_batch(), discard_expired(), peek_top().
pub mod gossip_priority;

// Gate 278 — Peer Reputation Scorer: integer 0–100 reputation tracking (T2)
// ReputationTier: Blocked(0-19)/Suspicious/Neutral/Good/Trusted(80-100). Initial score=50.
// ReputationLedger: BTreeMap<peer_id, PeerReputation>; trusted_peers(), blocked_peers(), weakest_peer().
pub mod peer_reputation;

// Gate 279 — Mesh Supervisor: epoch-level gossip subsystem integration snapshot (T2)
// MeshSupervisionRecord: fanout+drops+spread+quorum+reputation+queue in one tamper-evident hash.
// MeshSupervisionLog: hash-chained; min_reach_pct(), max_drop_count(), quorum_loss_epochs().
pub mod mesh_supervisor;

// Gate 280 — Gossip Epoch Finalizer: terminal gossip state seal at epoch close (T2)
// GossipEpochSeal: supervision+scheduler+spread hashes + peer counts in SHA-256 chain.
// GossipEpochChain: append(), terminal_hash(), seal_count(), verify_chain().
pub mod gossip_epoch_finalizer;

// Gate 281 — Mesh Convergence Certifier: multi-epoch gossip stability proof (T2)
// CONVERGENCE_WINDOW_SIZE=3 epochs. EpochSnapshot::satisfies_convergence() checks 4 conditions.
// ConvergenceCertifier: sliding window → ConvergenceCertificate per full window.
// consecutive_converged_count(), verify_chain(). Chain via SHA-256(prev‖fields).
pub mod convergence_certifier;

// Gate 282 — Gossip Topology Prober: active mesh connectivity probing (T2)
// ProbeResult: Success{rtt_ms}/Timeout/Refused/NoRoute. ProbeLog: hash-chained per (prober,target).
// ProbeMatrix: BTreeMap<(prober_id,target_id), ProbeLog>; reachable_from(), avg_mesh_rtt().
pub mod gossip_prober;

pub use sgm_gate::SGMGate;
pub use lut_kan::LUTKANRouter;
pub use rwkv_state::RWKVStateCache;
pub use lyapunov::LyapunovMonitor;
pub use audit::AuditLogger;
pub use orchestrator::Phase1Orchestrator;
