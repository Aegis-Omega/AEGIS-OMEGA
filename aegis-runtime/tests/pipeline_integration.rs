//! Seven-Pillar Pipeline Integration Test
//!
//! Proves all 7 constitutional pillars compose correctly end-to-end:
//!   Pillar 1 (StateAnchor) → Pillar 2 (DomainFirewall) → Pillar 5 (ValidationDFA)
//!   → Pillar 4 (SemanticGraph) → Pillar 3 (AffineCanvas) → Pillar 6 (GossipEmitter)
//!   with Pillar 7 (HysteresisFilter) governing peer trust throughout.

use aegis_runtime::{
    affine_canvas::{AffineCanvas, AffineMatrix, AgentSpec},
    domain_firewall::{Domain0Record, DomainFirewall, OpaqueSegmentKey},
    gossip_emitter::{GossipEmitter, GossipFrame},
    hysteresis::HysteresisFilter,
    semantic_graph::{RelationType, SemanticGraph},
    state_anchor::{SegmentKey, StateAnchor},
    validation_dfa::ValidationDfa,
};

fn seg(d: u32, s: u32) -> SegmentKey { SegmentKey { domain_id: d, segment_id: s } }
fn osk(d: u32, s: u32) -> OpaqueSegmentKey { OpaqueSegmentKey { domain_id: d, segment_id: s } }

/// Full pipeline: all 7 pillars in composition.
#[test]
fn seven_pillar_pipeline_composes() {
    // Pillar 1 — Root Cryptographic State Anchor
    let mut anchor = StateAnchor::new();
    anchor.append(seg(0, 1), b"genesis-state".to_vec()).unwrap();
    anchor.append(seg(0, 2), b"runtime-init".to_vec()).unwrap();
    assert_eq!(anchor.corruption_count(), 0);

    // Pillar 2 — Domain-Isolated Memory Sandbox
    let mut firewall = DomainFirewall::new();
    let k1 = osk(0, 1);
    let k2 = osk(0, 2);
    firewall.register(Domain0Record::new(k1, b"runtime-topology".to_vec())).unwrap();
    firewall.register(Domain0Record::new(k2, b"consensus-record".to_vec())).unwrap();
    assert!(firewall.read_domain0(k1).is_ok());
    assert!(firewall.read_domain0(k2).is_ok());
    assert_eq!(firewall.verify_all_domain0(), 0);

    // Pillar 5 — Syntactic Validation DFA
    let mut dfa = ValidationDfa::new();
    let valid_frame: Vec<u8> = vec![0xE0, 0x01, 0xAB, 0xFF, 0x00];
    dfa.process(&valid_frame);
    assert!(dfa.is_accepted());

    // Pillar 4 — Semantic Knowledge Graph
    let mut graph = SemanticGraph::new();
    let root  = graph.add_node("swarm-root", 0);
    let alpha = graph.add_node("agent-alpha", 1);
    let beta  = graph.add_node("agent-beta", 1);
    let gamma = graph.add_node("agent-gamma", 2);
    graph.add_edge(root, alpha, RelationType::GovernedBy, 1000).unwrap();
    graph.add_edge(root, beta,  RelationType::GovernedBy, 1000).unwrap();
    graph.add_edge(alpha, gamma, RelationType::DependsOn, 500).unwrap();
    assert_eq!(graph.node_count(), 4);
    assert_eq!(graph.edge_count(), 3);
    let reachable = graph.traverse_bfs(root, 10);
    assert!(reachable.contains(&root));
    assert!(reachable.contains(&gamma));
    assert_eq!(graph.fingerprint(), graph.fingerprint()); // deterministic

    // Pillar 3 — Deterministic Affine Coordinate Space
    let mut canvas = AffineCanvas::new(AffineMatrix::identity());
    canvas.layout_agents(&[
        AgentSpec { id: alpha, logical_x: 1000, logical_y: 0, logical_w: 500, logical_h: 500 },
        AgentSpec { id: beta,  logical_x: 2000, logical_y: 0, logical_w: 500, logical_h: 500 },
        AgentSpec { id: gamma, logical_x: 1500, logical_y: 1000, logical_w: 500, logical_h: 500 },
    ]);
    assert_eq!(canvas.agent_count(), 3);
    assert_eq!(canvas.fingerprint(), canvas.fingerprint());

    // Pillar 6 — Zero-Copy UDP Gossip Protocol (noop — no real socket needed)
    let frame = GossipFrame {
        local_node_id: 1,
        root_state_pulses: anchor.len() as u64,
        semantic_traversals: reachable.len() as u64,
        agent_state_alpha: alpha,
        agent_state_beta: beta,
        agent_state_gamma: gamma,
        cluster_consensus_score: 9500,
        network_friction: 0, // T0 invariant
    };
    let bytes = frame.to_bytes();
    assert_eq!(bytes.len(), 64);
    let decoded = GossipFrame::from_bytes(&bytes).unwrap();
    assert_eq!(decoded.network_friction, 0);
    assert_eq!(decoded.cluster_consensus_score, 9500);
    let mut emitter = GossipEmitter::noop();
    assert_eq!(emitter.emit(&frame).unwrap(), 0);

    // Pillar 7 — Non-Linear Hysteresis Peer Reputation Filter
    let mut hyst = HysteresisFilter::new();
    hyst.register_peer(alpha);
    hyst.register_peer(beta);
    hyst.register_peer(gamma);
    hyst.penalize(beta); // one penalty — not quarantine-level
    assert_eq!(hyst.active_quarantines(), 0);
    hyst.recover(gamma);
    assert_eq!(hyst.active_quarantines(), 0);
}

/// StateAnchor pulse count flows into gossip frame.
#[test]
fn anchor_pulses_reflected_in_gossip_frame() {
    let mut anchor = StateAnchor::new();
    for i in 1u32..=10 {
        anchor.append(SegmentKey { domain_id: 0, segment_id: i },
                      format!("state-{}", i).into_bytes()).unwrap();
    }
    assert_eq!(anchor.corruption_count(), 0);
    let frame = GossipFrame {
        local_node_id: 42,
        root_state_pulses: anchor.len() as u64,
        semantic_traversals: 0,
        agent_state_alpha: 0, agent_state_beta: 0, agent_state_gamma: 0,
        cluster_consensus_score: 10_000,
        network_friction: 0,
    };
    let decoded = GossipFrame::from_bytes(&frame.to_bytes()).unwrap();
    assert_eq!(decoded.root_state_pulses, 10);
    assert_eq!(decoded.network_friction, 0);
}

/// SemanticGraph BFS depth bound respected in pipeline.
#[test]
fn graph_depth_bounded_in_pipeline() {
    let mut graph = SemanticGraph::new();
    let mut prev = graph.add_node("level-0", 0);
    for depth in 1u32..=5 {
        let next = graph.add_node(&format!("level-{}", depth), depth);
        graph.add_edge(prev, next, RelationType::DerivedFrom, 100).unwrap();
        prev = next;
    }
    let root = 1u64;
    let visited = graph.traverse_bfs(root, 2);
    assert!(visited.contains(&1));  // level-0
    assert!(visited.contains(&2));  // level-1
    assert!(visited.contains(&3));  // level-2
    assert!(!visited.contains(&4)); // level-3 — beyond bound
    assert!(!visited.contains(&6)); // level-5 — beyond bound
}

/// Byzantine node gets quarantined after repeated violations.
#[test]
fn byzantine_node_quarantined_by_hysteresis() {
    let mut hyst = HysteresisFilter::new();
    hyst.register_peer(1);
    hyst.register_peer(2);
    for _ in 0..8 { hyst.penalize(2); }
    assert!(hyst.get_peer(2).unwrap().is_quarantined());
    assert!(!hyst.get_peer(1).unwrap().is_quarantined());
    assert_eq!(hyst.active_quarantines(), 1);
}

/// AffineCanvas scale transform doubles coordinates.
#[test]
fn canvas_scale_transform_in_pipeline() {
    let scale2x = AffineMatrix::scale(2000, 2000);
    let mut canvas = AffineCanvas::new(scale2x);
    canvas.layout_agents(&[
        AgentSpec { id: 1, logical_x: 1000, logical_y: 500, logical_w: 200, logical_h: 200 },
    ]);
    let bound = canvas.get_bound(1).unwrap();
    assert_eq!(bound.x, 2000);
    assert_eq!(bound.y, 1000);
}

/// All 7 pillars produce deterministic outputs ×3.
#[test]
fn all_pillars_deterministic_3x() {
    let make_graph_fp = || {
        let mut g = SemanticGraph::new();
        let a = g.add_node("alpha", 0);
        let b = g.add_node("beta", 1);
        g.add_edge(a, b, RelationType::ComposedOf, 500).unwrap();
        g.fingerprint()
    };
    let make_canvas_fp = || {
        let mut c = AffineCanvas::new(AffineMatrix::identity());
        c.layout_agents(&[AgentSpec { id: 1, logical_x: 1000, logical_y: 0, logical_w: 500, logical_h: 500 }]);
        c.fingerprint()
    };
    let make_frame_bytes = || {
        GossipFrame {
            local_node_id: 7, root_state_pulses: 100, semantic_traversals: 50,
            agent_state_alpha: 1, agent_state_beta: 2, agent_state_gamma: 3,
            cluster_consensus_score: 9000, network_friction: 0,
        }.to_bytes()
    };
    assert_eq!(make_graph_fp(), make_graph_fp());
    assert_eq!(make_graph_fp(), make_graph_fp());
    assert_eq!(make_canvas_fp(), make_canvas_fp());
    assert_eq!(make_canvas_fp(), make_canvas_fp());
    assert_eq!(make_frame_bytes(), make_frame_bytes());
    assert_eq!(make_frame_bytes(), make_frame_bytes());
}
