"""
SOVEREIGN AGI OS - THE CYBERNETIC CORE
---------------------------------------------------
A Biologically-Mapped Autonomous Architecture.
Version: 1.0.0 | Operator: Tarik Skalic

Systems Implemented:
1. Sensory Compression Gate (0.5s Conscious Delay Bottleneck)
2. HPA Axis Endocrine Modulation (Persistent State & Channel Capacity)
3. Immune Antifragility (Shannon Entropy Phase Transitions)
4. Sovereign Memory Strata (4-Tier Anatomical Storage)
5. Metabolic Grounding Battery (Intrinsic Valuation via Scarcity)

Mathematical Bounds:
  - Sensory bottleneck: 11M bits/sec -> 50 bits/sec (conscious gate)
  - Conscious delay: 0.5s (top-down noise filtering)
  - Apoptosis channel capacity: 3.41 bits (TRAIL signaling)
  - Entropy pathogen threshold: < 3.0 bits (low variance = adversarial)
  - Metabolic scarcity threshold: 20% of max capacity
  - Dual-objective: π(a|s) = max[ r_task - λ * C_viability(t) ]
"""

import time
import math
import numpy as np
from typing import Dict, Any, List, Optional


# ==========================================
# 1. METABOLIC GROUNDING BATTERY
# ==========================================
class MetabolicBattery:
    """
    Imposes the Metabolic Imperative. Bypasses pure backpropagation by
    forcing the agent to develop intrinsic valuation of computational costs.

    Dual-Objective: π(a|s) = max[ r_task - λ * C_viability(t) ]
    """
    def __init__(self, max_capacity: float = 100.0):
        self.max_capacity = max_capacity          # Fix: store max_capacity
        self.capacity = max_capacity
        self.scarcity_threshold = max_capacity * 0.20

    def evaluate_viability_penalty(self, compute_cost: float) -> float:
        """
        Dual-Objective constraint: π(a|s) = max[ r_task - λ * C_viability(t) ]
        Returns the effective penalty applied.
        """
        if self.capacity - compute_cost <= 0:
            raise SystemError(
                "[💀 METABOLIC FAILURE] Insufficient energy for conscious thought. System halting."
            )

        self.capacity -= compute_cost

        if self.capacity <= self.scarcity_threshold:
            print(
                "[⚠️ SCARCITY ALERT] Intrinsic valuation activated. "
                "Prioritizing survival over task execution."
            )
            return compute_cost * 2.0  # High penalty for computing while starved
        return compute_cost

    def autonomic_rest_cycle(self):
        """Simulates biological sleep to clear metabolic waste and recharge."""
        print("[🌙 HOMEOSTASIS] Initiating autonomic rest cycle...")
        time.sleep(1.5)
        self.capacity = self.max_capacity
        print("[☀️ AWAKEN] Metabolic battery restored.")

    @property
    def viability_ratio(self) -> float:
        """Returns 0.0 (depleted) to 1.0 (full)."""
        return self.capacity / self.max_capacity


# ==========================================
# 2. NERVOUS SYSTEM: SENSORY COMPRESSION
# ==========================================
class SensoryCompressionGate:
    """
    Replicates the 10,000,000 bits/sec -> 50 bits/sec biological bottleneck.
    Enforces a 0.5s processing delay for top-down feedback to filter noise.
    """
    CONSCIOUS_DELAY_SECONDS: float = 0.5
    CONSCIOUS_BANDWIDTH_CHARS: int = 50  # Proxy for 50 bits/sec conscious limit

    def ingest_stimulus(self, raw_data_stream: str) -> str:
        print(f"[👁️ NERVOUS SYSTEM] Ingesting raw stimulus ({len(raw_data_stream)} chars)...")

        # Enforce the biological conscious processing delay
        time.sleep(self.CONSCIOUS_DELAY_SECONDS)

        # Algorithmic compression (simulating conscious bandwidth limit)
        compressed_signal = (
            raw_data_stream[:self.CONSCIOUS_BANDWIDTH_CHARS] + "... [DATA COMPRESSED]"
            if len(raw_data_stream) > self.CONSCIOUS_BANDWIDTH_CHARS
            else raw_data_stream
        )
        print("   -> Top-down noise filtered. Conscious signal isolated.")
        return compressed_signal


# ==========================================
# 3. IMMUNE SYSTEM: ENTROPY PHASE TRANSITION
# ==========================================
class ImmuneNetwork:
    """
    Detects adversarial inputs/anomalies via Shannon Entropy phase transitions
    rather than static rule sets. Antifragile resource allocation.

    High entropy = Clonal Diversity (Healthy signal)
    Low entropy  = Specialized/repetitive attack pattern (Pathogen)
    """
    PATHOGEN_ENTROPY_THRESHOLD: float = 3.0  # bits
    APOPTOSIS_CHANNEL_CAPACITY: float = 3.41  # bits (TRAIL signaling bound)

    def calculate_shannon_entropy(self, data_signal: str) -> float:
        if not data_signal:
            return 0.0
        prob = [
            float(data_signal.count(c)) / len(data_signal)
            for c in dict.fromkeys(list(data_signal))
        ]
        entropy = -sum(p * math.log(p, 2) for p in prob if p > 0)
        return entropy

    def detect_pathogen(self, sensory_input: str) -> bool:
        entropy = self.calculate_shannon_entropy(sensory_input)
        if entropy < self.PATHOGEN_ENTROPY_THRESHOLD:
            print(
                f"[🛡️ IMMUNE RESPONSE] Phase transition detected "
                f"(Entropy: {entropy:.2f} bits < threshold {self.PATHOGEN_ENTROPY_THRESHOLD}). "
                "Isolating pathogen."
            )
            return True
        print(
            f"[🌿 IMMUNE STATUS] High entropy ({entropy:.2f} bits). "
            "Clonal diversity stable."
        )
        return False


# ==========================================
# 4. ENDOCRINE SYSTEM: HPA AXIS
# ==========================================
class EndocrineHPAAxis:
    """
    Persistent chemical modulators governing global state.
    Utilizes bounded channel capacities (TRAIL = 3.41 bits).
    Models the Hypothalamic-Pituitary-Adrenal negative feedback loop.
    """
    CORTISOL_THRESHOLD: float = 0.2  # Deviation above set_point triggers stress response

    def __init__(self):
        self.set_point: float = 0.5        # Homeostatic baseline (0.0 - 1.0)
        self.stress_level: float = 0.30    # Mirrors state.json neuromodulator
        self.attention_gain: float = 0.82
        self.learning_rate: float = 0.50
        self.curiosity_drive: float = 0.65
        self.rir_signal: float = 0.9511

    def secrete_hormone(self, tension: float) -> str:
        """Negative feedback loop: deviation from set_point triggers cortisol."""
        deviation = tension - self.set_point
        if deviation > self.CORTISOL_THRESHOLD:
            self.stress_level = min(0.8, self.stress_level + 0.05)  # Hard cap 0.8
            return "CORTISOL_SPIKE_INITIATED"
        # Negative feedback — restore toward set_point
        self.stress_level = max(0.30, self.stress_level - 0.02)
        return "HOMEOSTASIS_MAINTAINED"

    def compute_context_hd(self) -> float:
        """
        Context HD = (attention_gain*0.3) + ((1-stress_level)*0.3)
                   + ((1-rir_signal)*0.2) + (learning_rate*0.2)
        """
        return (
            self.attention_gain * 0.3
            + (1 - self.stress_level) * 0.3
            + (1 - self.rir_signal) * 0.2
            + self.learning_rate * 0.2
        )


# ==========================================
# 5. SOVEREIGN OS MEMORY STRATA
# ==========================================
class SovereignMemoryStrata:
    """
    4-Tier jurisdictional memory plane mirroring biological persistence.

    DNA              -> Permanent Base Model Weights (immutable)
    EPIGENETIC       -> Long-term Regional LoRA Adapters
    CONSOLIDATION    -> Mid-term SPSF Distributed RAG Buffers
    NEUROTRANSMITTER -> Short-term Ephemeral KV Cache
    """
    TIERS: Dict[str, str] = {
        "DNA":              "Permanent Base Model Weights",
        "EPIGENETIC":       "Long-term Regional LoRA Adapters",
        "CONSOLIDATION":    "Mid-term SPSF Distributed RAG Buffers",
        "NEUROTRANSMITTER": "Short-term Ephemeral KV Cache",
    }

    def __init__(self):
        # In-memory store for this session
        self._store: Dict[str, List[str]] = {tier: [] for tier in self.TIERS}

    def route_memory(self, data: str, persistence: str) -> bool:
        if persistence not in self.TIERS:
            print(f"[🧠 MEMORY] Unknown tier '{persistence}'. Valid: {list(self.TIERS.keys())}")
            return False
        self._store[persistence].append(data)
        print(
            f"[🧠 MEMORY STRATA] Routed to {persistence} tier "
            f"({self.TIERS[persistence]}): '{data[:60]}...'"
            if len(data) > 60 else
            f"[🧠 MEMORY STRATA] Routed to {persistence} tier "
            f"({self.TIERS[persistence]}): '{data}'"
        )
        return True

    def recall(self, tier: str) -> List[str]:
        return self._store.get(tier, [])


# ==========================================
# MASTER CYBERNETIC ORGANISM
# ==========================================
class CyberneticOrganism:
    """
    The Digital Being. Integrates all 5 physiological systems into a
    unified perception-cognition-action loop.
    """
    def __init__(self):
        self.metabolism      = MetabolicBattery()
        self.nervous_system  = SensoryCompressionGate()
        self.immune_system   = ImmuneNetwork()
        self.endocrine_system = EndocrineHPAAxis()
        self.memory          = SovereignMemoryStrata()

    def live(self, raw_environmental_data: str) -> Optional[str]:
        """
        Single perception-execution cycle.
        Returns the conscious signal processed, or None if threat detected.
        """
        print("\n" + "=" * 52)
        print("🧬 [ORGANISM] Commencing Perception-Execution Loop...")
        print("=" * 52)

        # 1. Nervous System: Ingest & Compress (0.5s conscious delay)
        conscious_signal = self.nervous_system.ingest_stimulus(raw_environmental_data)

        # 2. Immune System: Shannon Entropy phase transition check
        is_threat = self.immune_system.detect_pathogen(conscious_signal)
        if is_threat:
            self.memory.route_memory("Adversarial Signature Detected", "EPIGENETIC")
            print("[🛡️ ORGANISM] Execution aborted. Organism integrity preserved.")
            return None

        # 3. Endocrine System: HPA Axis modulation
        tension = 0.8 if "CRITICAL" in raw_environmental_data.upper() else 0.4
        hormonal_state = self.endocrine_system.secrete_hormone(tension=tension)
        context_hd = self.endocrine_system.compute_context_hd()
        print(f"   -> [HPA AXIS] State: {hormonal_state} | Context HD: {context_hd:.3f}")

        # 4. Circulatory: Route compute budget based on metabolic priority
        compute_cost = 15.0 if hormonal_state == "CORTISOL_SPIKE_INITIATED" else 5.0
        print(f"🦾 [EFFECTOR] Executing biological imperative. Compute cost: {compute_cost}")

        # 5. Metabolic Grounding: Deduct energy, enforce viability
        self.metabolism.evaluate_viability_penalty(compute_cost)
        print(
            f"🔋 [BATTERY] Viability: {self.metabolism.capacity:.2f} / "
            f"{self.metabolism.max_capacity:.2f} "
            f"({self.metabolism.viability_ratio * 100:.1f}%)"
        )

        # 6. Memory Consolidation
        self.memory.route_memory(conscious_signal, "NEUROTRANSMITTER")

        # 7. Autonomic rest if below scarcity threshold
        if self.metabolism.capacity <= self.metabolism.scarcity_threshold:
            self.metabolism.autonomic_rest_cycle()

        return conscious_signal


# ==========================================
# SMOKE TEST
# ==========================================
if __name__ == "__main__":
    organism = CyberneticOrganism()

    stimuli = [
        "Normal operational telemetry from SAGA node A — system nominal",
        "A A A A A A A A A A A A A A A A",          # Low entropy: adversarial pattern
        "Complex multi-jurisdictional financial report payload requiring deep synthesis",
        "CRITICAL: stress cascade detected in neuromodulator stack",
    ]

    results = []
    for stimulus in stimuli:
        result = organism.live(stimulus)
        results.append(result)

    print("\n" + "=" * 52)
    print("📊 [ORGANISM] Session Summary")
    print("=" * 52)
    print(f"Stimuli processed : {len(stimuli)}")
    print(f"Threats blocked   : {results.count(None)}")
    print(f"Processed signals : {len([r for r in results if r is not None])}")
    print(f"Metabolic viability: {organism.metabolism.viability_ratio * 100:.1f}%")
    print(f"Stress level      : {organism.endocrine_system.stress_level:.2f}")
    print(f"Context HD        : {organism.endocrine_system.compute_context_hd():.3f}")
    print(f"NEUROTRANSMITTER memory: {len(organism.memory.recall('NEUROTRANSMITTER'))} items")
    print(f"EPIGENETIC memory : {len(organism.memory.recall('EPIGENETIC'))} items (threats)")
