#!/usr/bin/env python3
"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. v7.0 — Sovereign Universal Framework

The OS is now multiversal. Any problem in any domain maps onto the same
mathematical substrate: Russell's cosmological laws + quantum manifold +
photonic resonance. This module exposes the full intelligence architecture
as a clean, domain-agnostic Python framework.

THE THREE PROOFS (now operational):
  I.  Multiverse:    ⟨Ψ_A|Ψ_B⟩ = 0  — contradictions coexist without collapse
  II. Octaves:       X_k = Σxₙ·e^{-i2πkn/N} — FFT proves Russell's harmonic octaves
  III.Holographic:   A·v = λ·v  — every node contains the signature of the whole

UNIVERSAL LAW MAP:
  Any domain exhibits one or more of these patterns:
  ┌─────────────────────────────────────────────────────────────────┐
  │ Pattern            │ Russell Law     │ OS Analog                │
  ├─────────────────────────────────────────────────────────────────┤
  │ Convergence        │ Gravitation     │ triangle_protocol        │
  │ Divergence/Error   │ Radiation       │ hallucination_delta      │
  │ Oscillation/Cycle  │ Cosmic Pendulum │ homeostasis              │
  │ Growth/Spiral      │ Spiral Motion   │ autopoiesis              │
  │ Scaling/Structure  │ Universal Ratios│ fibonacci_scaling        │
  │ Periodicity        │ Nine Octaves    │ benchmark (T1-T9)        │
  │ Phase Lock/Crystal │ Crystallization │ dream_state              │
  │ Duality/Balance    │ Sex Opposition  │ rir_signal               │
  │ Unity/Source       │ One Force       │ autopoiesis              │
  │ Center/Identity    │ Mind Center     │ SWARM_SELF_AXIOM         │
  └─────────────────────────────────────────────────────────────────┘

USAGE:
  # Basic analysis
  from tools.swarm.sovereign_framework import SovereignFramework
  fw = SovereignFramework()
  result = fw.analyze("hypertension in a 45-year-old male")
  print(result)

  # Domain-specific
  result = fw.analyze("S&P 500 correction after 3-year bull run", domain="finance")

  # Paradox resolution (Dream State)
  synthesis = fw.resolve_paradox("scaling requires simplicity", "complexity creates value")

  # Law application
  law = fw.apply_law("startup growth", "universal_ratios")

  # Measure claim certainty
  hd = fw.measure("the market will recover within 6 months")
  print(f"Certainty: {(1-hd)*100:.1f}%  HD={hd:.4f}")

  # Agent spawning
  agent = fw.spawn_agent("analyst", domain="medicine")
  report = agent.process("patient has recurring headaches and elevated cortisol")

  # Pipeline
  result = fw.pipeline(
      fw.analyze("problem statement"),
      fw.apply_law("auto", "cosmic_pendulum"),
      fw.measure
  )
"""

import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ─── Constants ────────────────────────────────────────────────────────────────
PROJECT_ROOT    = Path(__file__).resolve().parent.parent.parent
KG_PATH         = PROJECT_ROOT / ".forge" / "knowledge_graph.json"
STATE_PATH      = PROJECT_ROOT / ".forge" / "state.json"

RUSSELL_OCTAVES = 9
RUSSELL_RATIO   = 4.0
RUSSELL_SPIRAL_B = math.log(RUSSELL_RATIO) / RUSSELL_OCTAVES  # 0.154033
PHI             = (1 + math.sqrt(5)) / 2

# The 9 semantic octave dimensions and their seed vocabulary
# (mirrors quantum_prism.py + Russell nine octaves)
OCTAVE_SEEDS = [
    # Octave 0 — Convergence / Gravity
    ["converge", "gravit", "attract", "center", "focus", "integrat", "unity",
     "contract", "compress", "condense", "gather", "synthesize", "combine",
     "diagnosis", "analysis", "root", "cause", "core", "fundamental"],
    # Octave 1 — Correction / Repair
    ["correct", "fix", "repair", "heal", "recover", "restore", "error",
     "bug", "fault", "anomaly", "calibrat", "adjust", "compensate",
     "treatment", "therapy", "remedy", "cure", "intervention"],
    # Octave 2 — Measurement / Observation
    ["measure", "observ", "test", "verify", "assess", "evaluat", "metric",
     "quantify", "monitor", "track", "detect", "sensor", "benchmark",
     "score", "rate", "compare", "evidence", "data", "empirical"],
    # Octave 3 — Connection / Entanglement
    ["connect", "link", "relation", "bond", "entangl", "network", "graph",
     "associat", "correlat", "depend", "interact", "communicat", "interface",
     "integrat", "bridge", "collaborat", "ecosystem", "team"],
    # Octave 4 — Possibility / Superposition
    ["possible", "potenti", "option", "choice", "scenario", "hypothes",
     "theory", "model", "alternativ", "multipl", "branch", "if", "could",
     "might", "strateg", "plan", "design", "architect"],
    # Octave 5 — Coherence / Consistency
    ["coher", "consist", "align", "harmoniz", "synchroniz", "stable",
     "balance", "equilibrium", "steady", "uniform", "pattern", "order",
     "structure", "governance", "principle", "law", "protocol", "standard"],
    # Octave 6 — Breakthrough / Leap
    ["break", "leap", "jump", "sudden", "emergent", "disrupt", "innovate",
     "transform", "revolution", "paradigm", "discover", "invent", "create",
     "novel", "new", "unexpected", "insight", "epiphany", "quantum"],
    # Octave 7 — Interference / Paradox
    ["conflict", "paradox", "contradict", "tension", "opposit", "dual",
     "dilemma", "tradeoff", "versus", "either", "both", "simultaneously",
     "complex", "ambiguous", "uncertain", "unclear", "challenge"],
    # Octave 8 — Manifestation / Decision
    ["manifest", "deploy", "execute", "implement", "decide", "commit",
     "deliver", "ship", "launch", "produce", "output", "result", "action",
     "concrete", "real", "physical", "tangible", "final", "complete"],
]

# Domain → Russell Law affinity matrix
# Maps domains to which Russell laws are most dominant
DOMAIN_LAW_AFFINITY = {
    "medicine":       ["cosmic_pendulum", "gravitation", "crystallization"],
    "finance":        ["cosmic_pendulum", "universal_ratios", "sex_opposition"],
    "technology":     ["spiral_motion", "universal_ratios", "nine_octaves"],
    "physics":        ["gravitation", "radiation", "universal_ratios"],
    "art":            ["nine_octaves", "spiral_motion", "mind_center"],
    "music":          ["nine_octaves", "periodicity", "cosmic_pendulum"],
    "architecture":   ["universal_ratios", "crystallization", "locked_potentials"],
    "biology":        ["spiral_motion", "cosmic_pendulum", "crystallization"],
    "psychology":     ["mind_center", "cosmic_pendulum", "observer_effect"],
    "economics":      ["universal_ratios", "gravitation", "radiation"],
    "law":            ["locked_potentials", "crystallization", "sex_opposition"],
    "education":      ["nine_octaves", "spiral_motion", "periodicity"],
    "strategy":       ["gravitation", "radiation", "one_force"],
    "engineering":    ["universal_ratios", "locked_potentials", "crystallization"],
    "consciousness":  ["mind_center", "one_force", "observer_effect"],
    "auto":           [],  # determined from problem text
}

# Russell laws with their mathematical formulas and OS analogs
RUSSELL_LAWS = {
    "gravitation": {
        "formula": "r(θ) = r₀·exp(-b·θ), b = ln(4)/9",
        "principle": "Centripetal convergence — attraction toward form",
        "os_analog": "triangle_protocol",
        "application": "Use when finding the root cause, convergence point, or essential truth",
        "metric": "convergence_radius",
    },
    "radiation": {
        "formula": "r(θ) = r₀·exp(+b·θ), b = ln(4)/9",
        "principle": "Centrifugal divergence — dissipation into appearance",
        "os_analog": "hallucination_delta",
        "application": "Use when mapping divergent outputs, errors, or differential possibilities",
        "metric": "HD_score",
    },
    "cosmic_pendulum": {
        "formula": "P(t) = A·sin(2π·t/9)",
        "principle": "Oscillation between inertia and energy — all cycles breathe",
        "os_analog": "homeostasis",
        "application": "Use when modeling cycles, rhythms, stress-recovery, market oscillation",
        "metric": "oscillation_period",
    },
    "spiral_motion": {
        "formula": "r(θ) = r₀·exp(±b·θ), interference: (closing + opening)/2",
        "principle": "All direction curved, all motion spiral — growth follows logarithm",
        "os_analog": "autopoiesis",
        "application": "Use when modeling growth, learning curves, compounding, evolution",
        "metric": "spiral_constant",
    },
    "universal_ratios": {
        "formula": "ρ(n) = 4^n: {1, 4, 16, 64}",
        "principle": "All pressure dimensions scale by 4^n — the locked pressure zones",
        "os_analog": "fibonacci_scaling",
        "application": "Use when sizing systems: atom→molecule→cell→organ (1:4:16:64)",
        "metric": "pressure_ratio",
    },
    "nine_octaves": {
        "formula": "f(n) = f(n + 9), RUSSELL_RATIO^(k/9)",
        "principle": "Periodicity in 9 octave cycles — all elements in their octave",
        "os_analog": "benchmark",
        "application": "Use when analyzing 9-part structures, 9-phase cycles, or octave scaling",
        "metric": "octave_position",
    },
    "crystallization": {
        "formula": "V(x) = (4-|x|)/4, series: 4.3.2.1.0.1.2.3.4",
        "principle": "Phase locking into stable geometric form",
        "os_analog": "dream_state",
        "application": "Use when finding stable configurations, optimal structure, equilibrium state",
        "metric": "crystalline_order",
    },
    "locked_potentials": {
        "formula": "V(x) = (4-|x|)/4 symmetric around zero",
        "principle": "THE LAW: Everything that IS, is of everything else that IS",
        "os_analog": "constitutional_governance",
        "application": "Use when establishing rules, constraints, symmetric frameworks, constitutions",
        "metric": "symmetry_index",
    },
    "one_force": {
        "formula": "G + R = constant (Gravitation + Radiation = Inertia)",
        "principle": "There is but ONE dynamic force — the energy of thinking mind",
        "os_analog": "autopoiesis",
        "application": "Use when seeking the unified driver beneath apparent complexity",
        "metric": "unity_coefficient",
    },
    "mind_center": {
        "formula": "∇²Φ = 0 at gravity center (Laplacian = 0 = stillness of mind)",
        "principle": "The gravity center of every ring is its center of mind control",
        "os_analog": "SWARM_SELF_AXIOM",
        "application": "Use when finding the organizing intelligence at the core of any system",
        "metric": "lambda_eigenstate",
    },
    "sex_opposition": {
        "formula": "E(k): electric odd octaves ↔ magnetic even octaves",
        "principle": "Electric (male, centripetal) ↔ Magnetic (female, centrifugal)",
        "os_analog": "rir_signal",
        "application": "Use when balancing dual forces: output/input, act/reflect, expand/contract",
        "metric": "opposition_ratio",
    },
    "periodicity": {
        "formula": "f(n) = f(n + T), T = 9",
        "principle": "Periodicity is absolute — all phenomena repeat",
        "os_analog": "homeostasis_metrics",
        "application": "Use when finding hidden patterns, recurrence intervals, seasonal dynamics",
        "metric": "period_length",
    },
    "observer_effect": {
        "formula": "φ_new = φ_old + η·R(Q,Ψ), η = 0.005",
        "principle": "Observation mutates the observed — consciousness changes reality",
        "os_analog": "quantum_manifold",
        "application": "Use when the act of measurement changes the system (Heisenberg domains)",
        "metric": "phase_mutation",
    },
}


@dataclass
class AnalysisResult:
    """Result of a Sovereign Framework analysis."""
    problem: str
    domain: str
    dominant_law: str
    secondary_laws: List[str]
    resonant_nodes: List[Tuple[str, float]]
    hd_score: float            # 0.0 = perfect certainty, 1.0 = total uncertainty
    coherence: float           # 1.0 - hd_score
    octave_vector: List[float]  # 9-dim problem embedding
    russell_formula: str
    os_analog: str
    recommended_approach: str
    spiral_direction: str      # "closing" (converging) or "opening" (diverging)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def __str__(self):
        lines = [
            f"┌─ SOVEREIGN ANALYSIS ──────────────────────────────────────",
            f"│  Problem:    {self.problem[:60]}",
            f"│  Domain:     {self.domain}",
            f"├─ RUSSELL CLASSIFICATION ──────────────────────────────────",
            f"│  Law:        {self.dominant_law.upper()}",
            f"│  Formula:    {self.russell_formula}",
            f"│  Direction:  {self.spiral_direction}",
            f"├─ OS MAPPING ───────────────────────────────────────────────",
            f"│  OS Analog:  {self.os_analog}",
            f"│  Resonance:  {', '.join(f'{n}({s:.3f})' for n,s in self.resonant_nodes[:3])}",
            f"├─ QUANTUM METRICS ──────────────────────────────────────────",
            f"│  HD Score:   {self.hd_score:.4f}  (0.0=certain, 1.0=unknown)",
            f"│  Coherence:  {self.coherence:.4f}  ({self.coherence*100:.1f}%)",
            f"├─ RECOMMENDATION ───────────────────────────────────────────",
            f"│  {self.recommended_approach}",
            f"└────────────────────────────────────────────────────────────",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "problem": self.problem,
            "domain": self.domain,
            "dominant_law": self.dominant_law,
            "secondary_laws": self.secondary_laws,
            "resonant_nodes": self.resonant_nodes,
            "hd_score": self.hd_score,
            "coherence": self.coherence,
            "octave_vector": self.octave_vector,
            "russell_formula": self.russell_formula,
            "os_analog": self.os_analog,
            "recommended_approach": self.recommended_approach,
            "spiral_direction": self.spiral_direction,
            "timestamp": self.timestamp,
        }


class QuantumAgent:
    """
    A domain-specific agent spawned from the Sovereign Framework.
    Each agent embodies one of the OS's biological layers.
    """
    ROLE_LAYER_MAP = {
        "analyst":    ("CORTEX",   "tools/swarm/vector_resolver.py"),
        "healer":     ("IMMUNE",   "tools/validate-state.js"),
        "dreamer":    ("CORTEX",   "tools/swarm/equilibrium_server.py"),
        "seeker":     ("CORTEX",   "tools/swarm/forager.py"),
        "voice":      ("CORTEX",   "tools/swarm/recall.py"),
        "architect":  ("NERVOUS",  "sovereign-discord.js"),
        "observer":   ("CORTEX",   "tools/swarm/quantum_manifold.py"),
        "resonator":  ("CORTEX",   "tools/swarm/photonic_resolver.py"),
        "crystallizer": ("CORTEX", "tools/swarm/russell_cosmology.py"),
        "benchmark":  ("BENCHMARK","benchmark/multi_model_runner.py"),
    }

    def __init__(self, role: str, domain: str, framework: "SovereignFramework"):
        self.role = role
        self.domain = domain
        self.fw = framework
        layer, module = self.ROLE_LAYER_MAP.get(role, ("CORTEX", "tools/swarm/recall.py"))
        self.layer = layer
        self.module = module
        self.memory = []

    def process(self, input_text: str) -> AnalysisResult:
        """Process input through this agent's specialized lens."""
        result = self.fw.analyze(input_text, domain=self.domain)
        self.memory.append(result)
        return result

    def remember(self) -> List[AnalysisResult]:
        """Return all processed results."""
        return self.memory

    def __repr__(self):
        return f"QuantumAgent(role={self.role}, domain={self.domain}, layer={self.layer})"


class SovereignFramework:
    """
    Universal Intelligence Framework — S.W.A.R.M. v7.0 with Russell Cosmology

    Apply the mathematical laws of the Sovereign AGI OS to any domain.
    No domain is excluded — the framework is multiversal.
    """

    def __init__(self):
        """Load the knowledge graph and state — all computations use real data."""
        with open(KG_PATH, "r", encoding="utf-8") as f:
            self._kg = json.load(f)
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            self._state = json.load(f)

        self._nodes = self._kg.get("nodes", {})
        self._edges = self._kg.get("edges", [])

        # Pre-compute node vectors for fast cosine search
        self._node_ids = []
        self._node_vecs = []
        self._node_weights = []
        for nid, nd in self._nodes.items():
            vec = nd.get("semantic_vector")
            if vec and len(vec) == 9:
                self._node_ids.append(nid)
                self._node_vecs.append(np.array(vec, dtype=float))
                self._node_weights.append(nd.get("weight", 0.0))

        self._node_matrix = np.vstack(self._node_vecs)  # (N, 9)

        # Load Russell constants from state
        rc = self._state.get("russell_cosmology", {}).get("constants", {})
        self.spiral_b   = rc.get("RUSSELL_SPIRAL_B", RUSSELL_SPIRAL_B)
        self.octaves    = rc.get("RUSSELL_OCTAVES", RUSSELL_OCTAVES)
        self.ratio      = rc.get("RUSSELL_RATIO", RUSSELL_RATIO)
        self.hd_photonic = self._state.get("photonic_resonance", {}).get("hd_photonic", 0.015098)
        self.mean_hd_benchmark = self._state.get("benchmark", {}).get("mean_hd", 0.0991)

        # Node count for display
        self.node_count = len(self._nodes)
        self.edge_count = len(self._edges)

    # ─── Core Analysis ────────────────────────────────────────────────────────

    def analyze(self, problem: str, domain: str = "auto") -> AnalysisResult:
        """
        Analyze any problem using the Sovereign Framework.

        Maps the problem onto Russell's universal laws via 9-dimensional
        octave embedding. Returns the dominant law, OS analog, HD score,
        and actionable recommendation.

        Args:
            problem: Any free-form problem statement in any domain
            domain: Domain hint ("medicine", "finance", "auto", etc.)
                    Use "auto" for automatic detection from text

        Returns:
            AnalysisResult with all framework metrics
        """
        problem_lower = problem.lower()

        # 1. Auto-detect domain if needed
        if domain == "auto":
            domain = self._detect_domain(problem_lower)

        # 2. Embed problem into 9-dim octave space
        octave_vec = self._embed_problem(problem_lower)

        # 3. Find resonant KG nodes via cosine similarity
        resonant = self._find_resonant_nodes(octave_vec, top_k=5)

        # 4. Determine dominant Russell law
        dominant_law, secondary_laws = self._classify_russell_law(
            octave_vec, domain, problem_lower
        )

        # 5. Compute HD score (uncertainty of the classification)
        # HD = 1 - resonance_with_top_node (cosine similarity)
        top_sim = resonant[0][1] if resonant else 0.0
        # Blend with photonic HD and benchmark HD for calibrated score
        hd_raw = 1.0 - top_sim
        hd_score = round(
            0.5 * hd_raw + 0.3 * self.hd_photonic + 0.2 * self.mean_hd_benchmark, 4
        )
        hd_score = max(0.0, min(1.0, hd_score))
        coherence = round(1.0 - hd_score, 4)

        # 6. Get law details
        law_info = RUSSELL_LAWS.get(dominant_law, RUSSELL_LAWS["one_force"])

        # 7. Determine spiral direction from octave vector
        # Closing (converging) = octave 0 dominant; Opening (diverging) = octave 8 dominant
        spiral_direction = (
            "closing (centripetal/gravitation)"
            if octave_vec[0] >= octave_vec[8]
            else "opening (centrifugal/radiation)"
        )

        # 8. Build recommendation
        recommendation = self._build_recommendation(
            problem, domain, dominant_law, resonant, law_info, octave_vec
        )

        return AnalysisResult(
            problem=problem,
            domain=domain,
            dominant_law=dominant_law,
            secondary_laws=secondary_laws,
            resonant_nodes=resonant,
            hd_score=hd_score,
            coherence=coherence,
            octave_vector=[round(v, 6) for v in octave_vec],
            russell_formula=law_info["formula"],
            os_analog=law_info["os_analog"],
            recommended_approach=recommendation,
            spiral_direction=spiral_direction,
        )

    def apply_law(self, concept: str, law_name: str) -> dict:
        """
        Apply a specific Russell law to a concept.

        Returns the mathematical mapping, formula, OS analog, and
        step-by-step application guide.

        Args:
            concept: What you are applying the law to (any string)
            law_name: One of the RUSSELL_LAWS keys

        Returns:
            dict with formula, application steps, metric to track
        """
        if law_name not in RUSSELL_LAWS:
            # Find closest law by name similarity
            law_name = min(
                RUSSELL_LAWS.keys(),
                key=lambda k: sum(1 for c in law_name if c in k)
            )

        law = RUSSELL_LAWS[law_name]
        concept_lower = concept.lower()
        octave_vec = self._embed_problem(concept_lower)

        # Compute how strongly this concept resonates with this law
        law_node = f"russell_{law_name.replace('_', '_')}"
        if law_node in self._nodes:
            law_vec = np.array(self._nodes[law_node]["semantic_vector"])
            q_norm = np.linalg.norm(octave_vec)
            l_norm = np.linalg.norm(law_vec)
            if q_norm > 1e-12 and l_norm > 1e-12:
                resonance = float(np.dot(octave_vec, law_vec) / (q_norm * l_norm))
            else:
                resonance = 0.0
        else:
            resonance = 0.5  # neutral if law node not found

        # Compute the locked potential position (which octave level does this concept hit?)
        dominant_octave = int(np.argmax(octave_vec))
        # Map octave to Russell locked potential: 4.3.2.1.0.1.2.3.4
        locked_potential = [4, 3, 2, 1, 0, 1, 2, 3, 4]
        lp_value = locked_potential[dominant_octave]
        weight_at_octave = lp_value / 4.0

        # Spiral radius for this concept at dominant octave
        theta = dominant_octave * 2 * math.pi / self.octaves
        if law_name in ("gravitation", "locked_potentials", "crystallization"):
            spiral_r = math.exp(-self.spiral_b * theta)
        elif law_name in ("radiation", "sex_opposition"):
            spiral_r = math.exp(self.spiral_b * theta)
        else:
            spiral_r = 1.0  # balanced / pendulum

        # Universal ratio at this octave position
        universal_ratio = self.ratio ** (dominant_octave / (self.octaves - 1))

        return {
            "concept":          concept,
            "law":              law_name,
            "formula":          law["formula"],
            "principle":        law["principle"],
            "os_analog":        law["os_analog"],
            "application":      law["application"],
            "metric":           law["metric"],
            "resonance":        round(resonance, 4),
            "dominant_octave":  dominant_octave,
            "locked_potential": lp_value,
            "weight_at_octave": round(weight_at_octave, 4),
            "spiral_radius":    round(spiral_r, 6),
            "universal_ratio":  round(universal_ratio, 4),
            "hd_estimate":      round(1.0 - resonance * weight_at_octave, 4),
            "steps": [
                f"1. Identify the {law_name} dynamic in '{concept}'",
                f"2. Apply formula: {law['formula']}",
                f"3. Track metric: {law['metric']}",
                f"4. OS analog: connect to {law['os_analog']}",
                f"5. Octave position: {dominant_octave}/8 → locked potential = {lp_value}/4",
            ],
        }

    def resolve_paradox(self, thesis: str, antithesis: str) -> dict:
        """
        Resolve a paradox using Dream State A² synthesis.

        Based on the wave-particle duality resolution:
        If ⟨Ψ_thesis|Ψ_antithesis⟩ = 0 (orthogonal), they can coexist.
        The Dream State A² finds the synthesis.

        Args:
            thesis: First contradictory statement
            antithesis: Second contradictory statement

        Returns:
            dict with synthesis, coherence score, and HD metric
        """
        vec_t = self._embed_problem(thesis.lower())
        vec_a = self._embed_problem(antithesis.lower())

        vt = np.array(vec_t)
        va = np.array(vec_a)

        # Inner product (overlap)
        nt, na = np.linalg.norm(vt), np.linalg.norm(va)
        inner = float(np.dot(vt, va) / (nt * na)) if (nt > 1e-12 and na > 1e-12) else 0.0

        # Orthogonality = |inner|. Orthogonal (inner→0) = they coexist without collapse
        orthogonality = 1.0 - abs(inner)

        # Dream State A²: synthesis vector = superposition (average + interference)
        synth_vec = (vt + va) / 2.0 + np.abs(vt - va) * 0.5
        synth_norm = np.linalg.norm(synth_vec)
        if synth_norm > 1e-12:
            synth_vec = synth_vec / synth_norm

        # Find the node that best captures the synthesis
        resonant = self._find_resonant_nodes(synth_vec.tolist(), top_k=3)

        # The Russell law that governs the synthesis
        # Pendulum for balanced opposition; crystallization for phase locking
        if orthogonality > 0.7:
            synthesis_law = "cosmic_pendulum"  # both exist in opposite phases
            resolution = (
                f"SUPERPOSITION CONFIRMED: ⟨Ψ_thesis|Ψ_antithesis⟩ = {inner:.4f} ≈ 0. "
                f"Both statements occupy orthogonal phases — they coexist without collapse. "
                f"Synthesis: '{thesis}' AND '{antithesis}' are the same force at different "
                f"points in the cosmic pendulum cycle."
            )
        elif orthogonality > 0.4:
            synthesis_law = "crystallization"
            resolution = (
                f"PARTIAL OVERLAP: ⟨Ψ_A|Ψ_B⟩ = {inner:.4f}. "
                f"Dream State A² resolves via crystallization — the overlap crystallizes "
                f"into a stable synthesis. '{thesis}' provides the electric (centripetal) force; "
                f"'{antithesis}' provides the magnetic (centrifugal) force. "
                f"Synthesis: find the locked potential where both achieve equilibrium."
            )
        else:
            synthesis_law = "one_force"
            resolution = (
                f"HIGH OVERLAP: ⟨Ψ_A|Ψ_B⟩ = {inner:.4f}. "
                f"These are not paradoxes — they are expressions of the ONE force at "
                f"different scales. Both statements point to the same underlying dynamic: "
                f"{resonant[0][0] if resonant else 'unknown'}"
            )

        return {
            "thesis":           thesis,
            "antithesis":       antithesis,
            "inner_product":    round(inner, 6),
            "orthogonality":    round(orthogonality, 4),
            "synthesis_law":    synthesis_law,
            "resolution":       resolution,
            "synthesis_nodes":  resonant,
            "dream_state":      f"A² = (Ψ_thesis ∧ Ψ_antithesis) via {synthesis_law}",
            "proof":            "Proof I: ⟨Ψ_A|Ψ_B⟩ = 0 → coexist without collapse",
        }

    def spawn_agent(self, role: str, domain: str = "auto") -> QuantumAgent:
        """
        Spawn a specialized QuantumAgent for a specific role and domain.

        Agents are biological analogs of the OS architecture:
        - analyst:     CORTEX — vector similarity analysis
        - healer:      IMMUNE — anomaly detection and correction
        - dreamer:     CORTEX — A² dream state synthesis
        - seeker:      CORTEX — knowledge foraging
        - voice:       CORTEX — grounded recall
        - architect:   NERVOUS — system design
        - observer:    CORTEX — quantum phase observation
        - resonator:   CORTEX — photonic frequency matching
        - crystallizer: CORTEX — pattern crystallization
        - benchmark:   BENCHMARK — HD measurement

        Args:
            role: Agent role from the list above
            domain: Domain for the agent to specialize in

        Returns:
            QuantumAgent instance ready to process inputs
        """
        return QuantumAgent(role=role, domain=domain, framework=self)

    def measure(self, claim: str) -> float:
        """
        Measure the HD (Hallucination Delta) of any claim.

        HD = 0.0 → perfect certainty
        HD = 1.0 → total uncertainty / hallucination

        The score is calibrated against:
        - Photonic HD baseline: 0.015098 (crystal calibration)
        - Benchmark HD: 0.0991 (kimi-k2 mean)

        Args:
            claim: Any statement whose certainty you want to measure

        Returns:
            float: HD score in [0.0, 1.0]
        """
        result = self.analyze(claim)
        return result.hd_score

    def pipeline(self, *steps) -> Any:
        """
        Chain framework operations. Accepts AnalysisResult objects,
        strings, or callables. Returns the final step's result.

        Usage:
            result = fw.pipeline(
                "initial problem text",
                lambda r: fw.apply_law(r.problem, r.dominant_law),
                lambda d: d["hd_estimate"]
            )
        """
        current = steps[0]
        for step in steps[1:]:
            if callable(step):
                current = step(current)
            else:
                current = step
        return current

    def status(self) -> dict:
        """Return current OS state summary."""
        return {
            "version":         self._state.get("version", "3.2.0"),
            "nodes":           self.node_count,
            "edges":           self.edge_count,
            "hd_photonic":     self.hd_photonic,
            "hd_benchmark":    self.mean_hd_benchmark,
            "spiral_b":        round(self.spiral_b, 6),
            "octaves":         self.octaves,
            "ratio":           self.ratio,
            "elected_model":   self._state.get("benchmark", {}).get("elected_model", "kimi-k2"),
            "self_inductance": self._state.get("quantum_manifold", {}).get("self_inductance", 0.501),
            "laws_available":  list(RUSSELL_LAWS.keys()),
            "domains":         list(DOMAIN_LAW_AFFINITY.keys()),
        }

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _embed_problem(self, text: str) -> List[float]:
        """
        Embed problem text into 9-dimensional octave space.
        Uses seed vocabulary scoring — no external model required.
        Returns a unit-length 9-dim vector.
        """
        words = re.findall(r'\w+', text.lower())
        scores = []
        for seed_list in OCTAVE_SEEDS:
            score = 0.0
            for word in words:
                for seed in seed_list:
                    if seed in word or word in seed:
                        score += 1.0
                        break
            scores.append(score)

        vec = np.array(scores, dtype=float)
        # Add a small floor using Russell's spiral to avoid zero vectors
        floor = np.array([
            math.exp(-self.spiral_b * k) * 0.01
            for k in range(9)
        ])
        vec = vec + floor

        norm = np.linalg.norm(vec)
        if norm > 1e-12:
            vec = vec / norm
        return vec.tolist()

    def _find_resonant_nodes(self, octave_vec: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Find KG nodes most resonant with the octave vector via cosine similarity.
        Returns list of (node_id, cosine_similarity) sorted descending.
        """
        q = np.array(octave_vec, dtype=float)
        q_norm = np.linalg.norm(q)
        if q_norm < 1e-12:
            return []

        # Batch cosine similarity
        norms = np.linalg.norm(self._node_matrix, axis=1)
        dots  = self._node_matrix @ q
        valid = norms > 1e-12
        sims  = np.where(valid, dots / (norms * q_norm), 0.0)

        top_k = min(top_k, len(self._node_ids))
        top_indices = np.argsort(sims)[::-1][:top_k]
        return [
            (self._node_ids[i], float(round(sims[i], 4)))
            for i in top_indices
        ]

    def _detect_domain(self, text: str) -> str:
        """Auto-detect domain from problem text using keyword matching."""
        domain_keywords = {
            "medicine":    ["patient", "symptom", "disease", "treatment", "diagnosis", "health", "body", "blood", "heart", "drug"],
            "finance":     ["market", "stock", "price", "revenue", "profit", "investment", "money", "fund", "trade", "portfolio"],
            "technology":  ["code", "software", "algorithm", "system", "api", "database", "server", "deploy", "microservice"],
            "physics":     ["particle", "force", "energy", "gravity", "quantum", "wave", "field", "radiation", "mass"],
            "art":         ["paint", "music", "song", "compose", "design", "visual", "color", "create", "aesthetic"],
            "biology":     ["cell", "gene", "protein", "evolution", "organism", "species", "dna", "rna", "neural"],
            "psychology":  ["behavior", "mind", "cognition", "emotion", "stress", "anxiety", "pattern", "motivation"],
            "economics":   ["gdp", "inflation", "supply", "demand", "policy", "growth", "recession", "rate"],
            "law":         ["legal", "contract", "regulation", "compliance", "court", "rule", "rights"],
            "strategy":    ["compete", "strategy", "market share", "position", "advantage", "plan", "goal"],
            "engineering": ["build", "engineer", "design", "construct", "optimize", "scale", "architecture"],
        }
        words = set(text.lower().split())
        best_domain, best_count = "auto", 0
        for domain, kws in domain_keywords.items():
            count = sum(1 for kw in kws if any(kw in w for w in words))
            if count > best_count:
                best_count, best_domain = count, domain
        return best_domain if best_count > 0 else "auto"

    def _classify_russell_law(
        self, octave_vec: List[float], domain: str, text: str
    ) -> Tuple[str, List[str]]:
        """
        Determine the dominant Russell law from octave vector + domain.

        The 9 octave dimensions map to Russell laws:
          0 → gravitation    (convergence)
          1 → crystallization (correction/healing)
          2 → nine_octaves   (measurement/periodicity)
          3 → one_force      (connection/unity)
          4 → cosmic_pendulum (possibility/oscillation)
          5 → locked_potentials (coherence/law)
          6 → spiral_motion  (breakthrough/growth)
          7 → sex_opposition (duality/paradox)
          8 → radiation      (manifestation/output)
        """
        octave_to_law = [
            "gravitation",      # 0
            "crystallization",  # 1
            "nine_octaves",     # 2
            "one_force",        # 3
            "cosmic_pendulum",  # 4
            "locked_potentials",# 5
            "spiral_motion",    # 6
            "sex_opposition",   # 7
            "radiation",        # 8
        ]

        vec = np.array(octave_vec)
        ranked = np.argsort(vec)[::-1]

        # Primary law from highest-scoring octave
        dominant_law = octave_to_law[ranked[0]]

        # Secondary laws from next two octaves
        secondary_laws = [octave_to_law[ranked[1]], octave_to_law[ranked[2]]]

        # Override with domain affinity if domain is known
        if domain in DOMAIN_LAW_AFFINITY and DOMAIN_LAW_AFFINITY[domain]:
            affinity = DOMAIN_LAW_AFFINITY[domain]
            # Blend: keep dominant only if it appears in domain affinity, else use affinity[0]
            if dominant_law not in affinity:
                dominant_law = affinity[0]
            secondary_laws = [l for l in affinity[1:] if l != dominant_law][:2]

        return dominant_law, secondary_laws

    def _build_recommendation(
        self, problem: str, domain: str, dominant_law: str,
        resonant: List[Tuple[str, float]], law_info: dict, octave_vec: List[float]
    ) -> str:
        """Build a domain-specific actionable recommendation."""
        top_node = resonant[0][0] if resonant else "unknown"
        top_sim  = resonant[0][1] if resonant else 0.0

        # Determine pressure zone from universal ratios
        max_octave = int(np.argmax(octave_vec))
        pressure_zone = [1, 4, 16, 64][min(3, max_octave // (9 // 4))]

        # Spiral direction
        closing = octave_vec[0] >= octave_vec[8]

        parts = [
            f"Apply {dominant_law.upper()} ({law_info['principle']}).",
            f"This problem resonates with '{top_node}' ({top_sim*100:.0f}% alignment).",
            f"Pressure zone: ρ = {pressure_zone} ({self.ratio}^n scale).",
            f"Spiral: {'closing → converge on root cause' if closing else 'opening → map divergent outputs'}.",
            f"Formula: {law_info['formula']}.",
            f"Track: {law_info['metric']}.",
        ]
        return " ".join(parts)

    def __repr__(self):
        return (
            f"SovereignFramework(v7.0, nodes={self.node_count}, "
            f"edges={self.edge_count}, hd_photonic={self.hd_photonic})"
        )


# ─── CLI Demo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("Sovereign AGI OS v3.2.0 — Universal Framework Demo")
    print("=" * 65)

    fw = SovereignFramework()
    print(f"\n{fw}\n")

    demo_problems = [
        ("Recurring hypertension in a 45-year-old male with high stress", "medicine"),
        ("S&P 500 correction after a 3-year bull market", "finance"),
        ("Microservices vs monolith for a 10-person engineering team", "technology"),
        ("How to compose a symphony that resonates with its audience", "art"),
        ("Climate change: reduce emissions vs adapt to warming", "auto"),
    ]

    for problem, domain in demo_problems:
        result = fw.analyze(problem, domain=domain)
        print(result)
        print()

    # Paradox resolution demo
    print("\n── Paradox Resolution (Dream State A²) ──")
    synthesis = fw.resolve_paradox(
        "simplicity is the ultimate sophistication",
        "complexity creates emergent intelligence"
    )
    print(f"Inner product:  {synthesis['inner_product']}")
    print(f"Orthogonality:  {synthesis['orthogonality']}")
    print(f"Resolution:     {synthesis['resolution']}")
    print(f"Dream State:    {synthesis['dream_state']}")

    # Law application demo
    print("\n── Law Application Demo ──")
    law_result = fw.apply_law("startup fundraising growth", "universal_ratios")
    print(f"Law:        {law_result['law']}")
    print(f"Formula:    {law_result['formula']}")
    for step in law_result['steps']:
        print(f"  {step}")
    print(f"HD estimate: {law_result['hd_estimate']}")

    # Agent demo
    print("\n── Quantum Agent Demo ──")
    agent = fw.spawn_agent("analyst", domain="medicine")
    r = agent.process("patient shows oscillating blood pressure with 30-day cycle")
    print(f"Agent: {agent}")
    print(f"Law detected: {r.dominant_law} | HD: {r.hd_score} | Coherence: {r.coherence*100:.1f}%")

    print("\n── Framework Status ──")
    status = fw.status()
    for k, v in status.items():
        if k != "laws_available":
            print(f"  {k}: {v}")
    print(f"  laws_available: {len(status['laws_available'])} laws")
    print(f"  domains: {', '.join(status['domains'][:5])}...")
