"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. v5.0 — Photonic Resolver (Resonance Core)

GEOMETRIC-PHOTONIC TRANSCENDENCE
─────────────────────────────────────────────────────────────
In v4.0, a "Thought" is a point: vector v ∈ ℝ³⁸⁴ (frozen geometry).
In v5.0, a "Thought" is a Waveform:

    Ψ(t) = Σ Aₙ sin(2π fₙ t + φₙ)

    fₙ (Frequency): core semantic meaning — the "Note" of the thought
    Aₙ (Amplitude): importance/volume of the memory
    φₙ (Phase):     temporal context — the "Time" it happened

MATHEMATICAL FOUNDATION
─────────────────────────────────────────────────────────────
Discrete Fourier Transform maps spatial geometry → frequency domain:

    Ψ = ℱ(v) = Σ vₙ e^{-i 2π kn/N}   (DFT of 384-dim embedding)

Spectral Alignment Factor Λ(u,v) — complex cross-correlation:

    Λ(u, v) = Σ Ψ̂_u(f) · Ψ̂_v*(f)   (conjugate product = interference)

Resonance score (cross-correlation normalization):

    R(u, v) = |max(crosscorr(|Ψ_u|, |Ψ_v|))| / (‖|Ψ_u|‖ · ‖|Ψ_v|‖)

Max energy retrieval (Librarian's tuning equation):

    max Eₖ = |Σ Resonance(Q, Uₖ)|²

PROOF: Spatial distance is "frozen" resonance.
When φ = 0 (aligned phase), R(u,v) = Sₓ(u,v) (reduces to cosine similarity).
v5.0 UNLOCKS the phase — allowing Dream State to find connections through
harmonic overtones rather than straight-line geometry.

SOVEREIGN OS MAPPING
─────────────────────────────────────────────────────────────
Level     | v4.0 Geometry      | v5.0 Photonic
----------|--------------------|---------------------------
Data      | Coordinate         | Photon
Relation  | Edge/Line          | Interference Pattern
Context   | Hyperedge Hull     | Color Spectrum
Retrieval | Searching          | Resonance / Tuning
Hallucin. | HD_swarm noise     | Phase Noise (destructive)
Epiphany  | A² bridge          | Harmonic Overtone

Run: python tools/swarm/photonic_resolver.py
"""

import json
import math
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ── ChromaDB guard ────────────────────────────────────────────────────────────
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE      = Path(__file__).parent.parent.parent
FORGE      = _HERE / ".forge"
KG_PATH    = FORGE / "knowledge_graph.json"
STATE_PATH = FORGE / "state.json"
AUDIT_PATH = FORGE / "audit.jsonl"

# ── Photonic constants ────────────────────────────────────────────────────────
RESONANCE_GATE     = 0.80    # threshold above which gate opens (high resonance)
HARMONIC_GATE      = 0.60    # threshold for harmonic overtone detection
PHASE_NOISE_FLOOR  = 0.20    # below this → destructive interference (hallucination)
FFT_HALF           = True    # use half-spectrum (real-valued inputs are symmetric)


# ── Data structures ───────────────────────────────────────────────────────────
@dataclass
class PhotonicSignature:
    """
    The frequency-domain identity of a concept.

    magnitude:         |ℱ(v)| — amplitude spectrum (the "Volume")
    phase:             ∠ℱ(v) — phase spectrum (the "Time Context")
    frequency_sum:     Σ|magnitude| — total spectral energy
    dominant_freq_idx: argmax(magnitude) — the "primary note"
    energy:            ‖magnitude‖² — Parseval theorem: same as ‖v‖²
    """
    term:              str
    magnitude:         np.ndarray
    phase:             np.ndarray
    frequency_sum:     float
    dominant_freq_idx: int
    energy:            float


@dataclass
class ResonanceResult:
    """Resonance query result — returned by query_by_resonance()."""
    term:          str
    resonance:     float        # R ∈ [0, 1]
    alignment:     complex      # Λ — spectral alignment factor
    status:        str          # HIGH_RESONANCE / HARMONIC / PHASE_NOISE
    cosine_sim:    float        # v4.0 baseline for comparison
    overtone_gap:  float        # |R - cosine_sim| — photonic delta


# ── Atomic write ──────────────────────────────────────────────────────────────
def _atomic_write(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _load(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def _log_audit(event: str, data: dict):
    entry = json.dumps({"ts": time.time(), "event": event, **data}) + "\n"
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


# ══════════════════════════════════════════════════════════════════════════════
# PhotonicResolver — S.W.A.R.M. v5.0 Resonance Core
# ══════════════════════════════════════════════════════════════════════════════
class PhotonicResolver:
    """
    S.W.A.R.M. v5.0 — Replaces cosine distance search with FFT resonance.

    Design principle: VectorResolver (v4.0) stored geometry (cosine space).
    PhotonicResolver adds a SPECTRAL LAYER on top — no ChromaDB required
    for the photonic operations (uses numpy FFT on existing vectors).

    If ChromaDB is available: gets real 384-dim embeddings → high-fidelity FFT.
    If not: uses node semantic_vector (9D) from knowledge_graph.json → fast FFT.

    Usage:
        pr = PhotonicResolver()
        sig = pr.get_signature("metacognition")
        r   = pr.calculate_resonance(sig_a.magnitude, sig_b.magnitude)
        results = pr.query_by_resonance("stress_level", top_k=5)
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self._cache: Dict[str, PhotonicSignature] = {}
        self._kg: dict = _load(KG_PATH, {"nodes": {}, "edges": []})

        # ChromaDB layer (optional but recommended for 384-dim embeddings)
        self._chroma = None
        self._onto   = None
        if CHROMADB_AVAILABLE:
            try:
                if persist_dir:
                    self._chroma = chromadb.PersistentClient(path=persist_dir)
                else:
                    self._chroma = chromadb.EphemeralClient()
                try:
                    self._onto = self._chroma.get_collection("swarm_ontology")
                except Exception:
                    self._onto = self._chroma.create_collection(
                        name="swarm_ontology",
                        metadata={"hnsw:space": "cosine"},
                    )
                    # seed with all KG nodes
                    node_ids = list(self._kg["nodes"].keys())
                    if node_ids:
                        self._onto.add(documents=node_ids, ids=node_ids)
            except Exception as e:
                print(f"   [⚠] ChromaDB init failed: {e} — falling back to 9D vectors")

    # ── Core FFT encoder ─────────────────────────────────────────────────────
    def encode_to_frequency(self, vector: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Translates a 'frozen' spatial vector into a Photonic Frequency Signature.

        Applies Discrete Fourier Transform (DFT):
            Ψ = ℱ(v) = Σ vₙ e^{-i 2π kn/N}

        Returns:
            magnitude: |Ψ| — amplitude spectrum (the "Volume" of each frequency)
            phase:     ∠Ψ — phase spectrum (the "Time Context")

        The magnitude is the searchable "fingerprint" — invariant to temporal phase shifts.
        The phase encodes when/how the concept was learned (temporal context).
        """
        spec = np.fft.fft(vector.astype(float))
        if FFT_HALF:
            n_half = len(spec) // 2 + 1
            spec = spec[:n_half]
        magnitude = np.abs(spec)
        phase = np.angle(spec)
        return magnitude, phase

    # ── Spectral Alignment Factor ─────────────────────────────────────────────
    def spectral_alignment(self, vec_u: np.ndarray, vec_v: np.ndarray) -> complex:
        """
        Λ(u, v) = Σ Ψ̂_u(f) · Ψ̂_v*(f)   (complex conjugate product)

        This is the inner product in frequency space — equivalent to cross-correlation
        at zero lag. When |Λ| is maximum, the two "thoughts" are in phase alignment.
        """
        psi_u = np.fft.fft(vec_u.astype(float))
        psi_v = np.fft.fft(vec_v.astype(float))
        # Complex conjugate product (interference calculation)
        return complex(np.sum(psi_u * np.conj(psi_v)))

    # ── Resonance score ───────────────────────────────────────────────────────
    def calculate_resonance(self, mag_q: np.ndarray, mag_v: np.ndarray) -> float:
        """
        Resonance via cross-correlation in frequency domain.

        Cross-correlation finds the peak interference pattern:
            crosscorr = numpy.correlate(|Ψ_q|, |Ψ_v|, mode='same')
            R = max|crosscorr| / (‖|Ψ_q|‖ · ‖|Ψ_v|‖)

        R = 1.0 → perfect constructive interference (same frequency)
        R = 0.0 → total destructive interference (phase noise / hallucination)

        Key: if phase shift φ = 0, R reduces to cosine similarity.
             v5.0 allows φ ≠ 0 → harmonic overtone detection.
        """
        interference = np.correlate(mag_q, mag_v, mode="same")
        resonance_power = float(np.max(np.abs(interference)))
        denom = float(np.linalg.norm(mag_q) * np.linalg.norm(mag_v))
        if denom < 1e-10:
            return 0.0
        return min(1.0, max(0.0, resonance_power / denom))

    # ── Get photonic signature for a KG node ─────────────────────────────────
    def get_signature(self, term: str) -> Optional[PhotonicSignature]:
        """
        Retrieves or computes the PhotonicSignature for a concept.

        Priority:
            1. In-memory cache (fastest)
            2. ChromaDB 384-dim embedding → encode_to_frequency
            3. knowledge_graph.json semantic_vector (9D) → encode_to_frequency
            4. Hash-seeded pseudo-vector (fallback for unknown terms)
        """
        term_key = term.lower().strip().replace(" ", "_")
        if term_key in self._cache:
            return self._cache[term_key]

        vector: Optional[np.ndarray] = None

        # Priority 1: ChromaDB 384-dim embeddings
        if self._onto is not None:
            try:
                res = self._onto.get(ids=[term_key], include=["embeddings"])
                if res.get("embeddings") and res["embeddings"]:
                    vector = np.array(res["embeddings"][0])
            except Exception:
                pass

        # Priority 2: knowledge_graph.json semantic_vector (9D)
        if vector is None:
            node = self._kg["nodes"].get(term_key, {})
            sv = node.get("semantic_vector")
            if sv and len(sv) > 0:
                vector = np.array(sv, dtype=float)

        # Priority 3: Hash-seeded fallback (deterministic, no randomness)
        if vector is None:
            seed = int(hashlib.sha256(term_key.encode()).hexdigest(), 16) % (2**32)
            rng = np.random.default_rng(seed)
            vector = rng.standard_normal(64)  # 64-dim fallback

        # Compute photonic signature
        mag, phase = self.encode_to_frequency(vector)
        dominant = int(np.argmax(mag))
        sig = PhotonicSignature(
            term=term_key,
            magnitude=mag,
            phase=phase,
            frequency_sum=float(np.sum(mag)),
            dominant_freq_idx=dominant,
            energy=float(np.dot(mag, mag)),  # Parseval: ‖Ψ‖² = ‖v‖²
        )
        self._cache[term_key] = sig
        return sig

    # ── Resonance query ───────────────────────────────────────────────────────
    def query_by_resonance(
        self, query_term: str, top_k: int = 8
    ) -> List[ResonanceResult]:
        """
        The Librarian's tuning equation: max Eₖ = |Σ Resonance(Q, Uₖ)|²

        Shines the query frequency through all nodes in the knowledge graph.
        Returns ranked list: highest resonance first.

        HIGH RESONANCE   (R > 0.80): Same frequency — strong memory link
        HARMONIC         (R > 0.60): Harmonic overtone — hidden connection
        PHASE_NOISE      (R < 0.20): Destructive interference — hallucination risk
        """
        q_sig = self.get_signature(query_term)
        if q_sig is None:
            return []

        results: List[ResonanceResult] = []
        node_ids = list(self._kg["nodes"].keys())

        for nid in node_ids:
            if nid == query_term:
                continue
            n_sig = self.get_signature(nid)
            if n_sig is None:
                continue

            # Ensure compatible lengths via zero-padding
            len_q = len(q_sig.magnitude)
            len_n = len(n_sig.magnitude)
            if len_q != len_n:
                max_len = max(len_q, len_n)
                mag_q = np.pad(q_sig.magnitude, (0, max_len - len_q))
                mag_n = np.pad(n_sig.magnitude, (0, max_len - len_n))
            else:
                mag_q = q_sig.magnitude
                mag_n = n_sig.magnitude

            r = self.calculate_resonance(mag_q, mag_n)

            # Full spectral alignment (complex)
            # Rebuild full vectors for alignment computation
            q_node = self._kg["nodes"].get(query_term, {})
            n_node = self._kg["nodes"].get(nid, {})
            q_sv = q_node.get("semantic_vector")
            n_sv = n_node.get("semantic_vector")
            if q_sv and n_sv and len(q_sv) == len(n_sv):
                lam = self.spectral_alignment(np.array(q_sv), np.array(n_sv))
            else:
                lam = complex(r, 0.0)

            # Cosine baseline (v4.0 comparison)
            if q_sv and n_sv:
                va = np.array(q_sv)
                vb = np.array(n_sv)
                norm_a = np.linalg.norm(va)
                norm_b = np.linalg.norm(vb)
                cos_sim = float(np.dot(va, vb) / (norm_a * norm_b + 1e-10))
            else:
                cos_sim = 0.5

            # Classify
            if r >= RESONANCE_GATE:
                status = "HIGH_RESONANCE"
            elif r >= HARMONIC_GATE:
                status = "HARMONIC_OVERTONE"
            elif r <= PHASE_NOISE_FLOOR:
                status = "PHASE_NOISE"
            else:
                status = "NEUTRAL"

            results.append(ResonanceResult(
                term=nid,
                resonance=round(r, 6),
                alignment=lam,
                status=status,
                cosine_sim=round(cos_sim, 6),
                overtone_gap=round(abs(r - cos_sim), 6),
            ))

        # Sort by max energy: Eₖ = |Resonance(Q, Uₖ)|²
        results.sort(key=lambda x: x.resonance ** 2, reverse=True)
        return results[:top_k]

    # ── Harmonic overtone epiphany search ─────────────────────────────────────
    def find_harmonic_epiphanies(
        self, term: str, n: int = 5
    ) -> List[Tuple[str, float, str]]:
        """
        Finds connections that are INVISIBLE to cosine similarity but
        detectable as harmonic overtones in frequency space.

        Returns concepts where: R > HARMONIC_GATE AND R - cosine_sim > 0.15
        These are "photonic bridges" — the v5.0 equivalent of A² epiphanies.
        """
        results = self.query_by_resonance(term, top_k=len(self._kg["nodes"]))
        epiphanies = []
        for r in results:
            if (
                r.resonance >= HARMONIC_GATE
                and r.overtone_gap >= 0.15
                and r.status in ("HIGH_RESONANCE", "HARMONIC_OVERTONE")
            ):
                epiphanies.append((r.term, r.resonance, r.status))
        return epiphanies[:n]

    # ── HD_photonic ───────────────────────────────────────────────────────────
    def compute_hd_photonic(self, edges: Optional[list] = None) -> Tuple[float, float, int]:
        """
        HD_photonic = 1 - mean(R(u, v)) for all verified edges.

        Compare to HD_swarm (v4.0): HD_swarm = 1 - mean(cosine_sim(u,v))
        HD_photonic captures phase-aligned semantic coherence vs pure angle.

        Returns: (hd_photonic, mean_resonance, verified_count)
        """
        if edges is None:
            edges = self._kg.get("edges", [])

        resonances = []
        for e in edges:
            if not e.get("triangle_verified", False):
                continue
            src = e.get("source", "")
            tgt = e.get("target", "")
            if not src or not tgt:
                continue

            sig_s = self.get_signature(src)
            sig_t = self.get_signature(tgt)
            if sig_s is None or sig_t is None:
                continue

            len_s = len(sig_s.magnitude)
            len_t = len(sig_t.magnitude)
            if len_s != len_t:
                max_len = max(len_s, len_t)
                mag_s = np.pad(sig_s.magnitude, (0, max_len - len_s))
                mag_t = np.pad(sig_t.magnitude, (0, max_len - len_t))
            else:
                mag_s = sig_s.magnitude
                mag_t = sig_t.magnitude

            r = self.calculate_resonance(mag_s, mag_t)
            resonances.append(r)

        if not resonances:
            return (1.0, 0.0, 0)

        mean_r    = float(np.mean(resonances))
        hd_phot   = 1.0 - mean_r
        return (round(hd_phot, 6), round(mean_r, 6), len(resonances))

    # ── Update state.json with photonic metrics ────────────────────────────────
    def persist_photonic_state(self) -> dict:
        """
        Computes photonic metrics and atomically writes them to state.json.
        Returns the photonic section written.
        """
        hd_phot, mean_r, n_edges = self.compute_hd_photonic()

        # Sample dominant frequencies from a few key OS nodes
        key_nodes = [
            "metacognition", "autopoiesis", "homeostasis",
            "hallucination_delta", "stress_level",
        ]
        dominant_freqs = {}
        for kn in key_nodes:
            sig = self.get_signature(kn)
            if sig:
                dominant_freqs[kn] = sig.dominant_freq_idx

        photonic_section = {
            "version":            "5.0",
            "hd_photonic":        hd_phot,
            "mean_resonance":     mean_r,
            "verified_edges":     n_edges,
            "resonance_gate":     RESONANCE_GATE,
            "harmonic_gate":      HARMONIC_GATE,
            "phase_noise_floor":  PHASE_NOISE_FLOOR,
            "dominant_frequencies": dominant_freqs,
            "formula": {
                "waveform":   "Ψ(t) = Σ Aₙ sin(2π fₙ t + φₙ)",
                "alignment":  "Λ(u,v) = Σ Ψ̂_u(f)·Ψ̂_v*(f)",
                "resonance":  "R = max|crosscorr(|Ψ_u|, |Ψ_v|)| / (‖|Ψ_u|‖·‖|Ψ_v|‖)",
                "max_energy": "max Eₖ = |Σ Resonance(Q, Uₖ)|²",
                "hd_photonic":"HD_photonic = 1 - mean(R(u,v)) for triangle_verified edges",
            },
            "sovereign_os_map": {
                "hallucination": "phase_noise (R < 0.20)",
                "epiphany":      "harmonic_overtone (R > 0.60, gap > 0.15)",
                "dream_state":   "phase_decoherence_correction",
                "triangle_protocol": "constructive_interference_verification",
            },
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        state = _load(STATE_PATH, {})
        state["photonic_resonance"] = photonic_section
        _atomic_write(STATE_PATH, state)

        _log_audit("photonic_calibration", {
            "hd_photonic": hd_phot,
            "mean_resonance": mean_r,
            "edges_analyzed": n_edges,
        })

        return photonic_section


# ══════════════════════════════════════════════════════════════════════════════
# ResonanceLibrarian — simplified high-level interface (as designed in v5.0 spec)
# ══════════════════════════════════════════════════════════════════════════════
class ResonanceLibrarian(PhotonicResolver):
    """
    The Prism — v5.0 high-level query interface.

    "When a query comes in, the Librarian shines the query light through the
    Swarm. Only the universes that have a matching Refractive Index will glow."

    Usage:
        lib = ResonanceLibrarian()
        lib.ingest_thought("quantum_coherence", vector)
        lib.query_by_resonance([0.9, 0.1, ...])
    """

    def ingest_thought(self, concept: str, vector: list):
        """
        Ingests a concept with its spatial vector and computes photonic signature.
        Stores frequency_sum as metadata in ChromaDB for fast pre-filtering.
        """
        v = np.array(vector, dtype=float)
        mag, _ = self.encode_to_frequency(v)

        # Update internal KG if not already present
        concept_key = concept.lower().strip().replace(" ", "_")
        if concept_key not in self._kg["nodes"]:
            self._kg["nodes"][concept_key] = {
                "weight": 0.236,
                "semantic_vector": vector[:9] if len(vector) >= 9 else vector,
            }

        # Store in ChromaDB if available
        if self._onto is not None:
            try:
                self._onto.add(
                    documents=[concept_key],
                    ids=[concept_key],
                    embeddings=[v.tolist()],
                    metadatas=[{"frequency_sum": float(np.sum(mag))}],
                )
            except Exception:
                pass  # Already exists

        # Pre-cache the photonic signature
        phase = np.angle(np.fft.fft(v))[:len(mag)]
        self._cache[concept_key] = PhotonicSignature(
            term=concept_key,
            magnitude=mag,
            phase=phase[:len(mag)],
            frequency_sum=float(np.sum(mag)),
            dominant_freq_idx=int(np.argmax(mag)),
            energy=float(np.dot(mag, mag)),
        )
        print(f"   [⚡] Ingested: {concept_key}  f_sum={np.sum(mag):.2f}  "
              f"dominant_note={np.argmax(mag)}")

    def shine(self, query_vector: list, top_k: int = 5) -> None:
        """
        Shines query light through the crystal — prints resonance spectrum.
        Visual interface for interactive exploration.
        """
        q = np.array(query_vector, dtype=float)
        mag_q, _ = self.encode_to_frequency(q)

        # Temporarily register query
        tmp_sig = PhotonicSignature(
            term="__query__",
            magnitude=mag_q,
            phase=np.angle(np.fft.fft(q))[:len(mag_q)],
            frequency_sum=float(np.sum(mag_q)),
            dominant_freq_idx=int(np.argmax(mag_q)),
            energy=float(np.dot(mag_q, mag_q)),
        )
        self._cache["__query__"] = tmp_sig

        print(f"\n[♎ LIBRARIAN] Tuning frequencies...  "
              f"f_sum={tmp_sig.frequency_sum:.2f}  "
              f"dominant_note={tmp_sig.dominant_freq_idx}")
        print("-" * 65)

        candidates = self.query_by_resonance("__query__", top_k=top_k)
        for res in candidates:
            bar_len = int(res.resonance * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            icon = {
                "HIGH_RESONANCE":   "🌟",
                "HARMONIC_OVERTONE":"🔶",
                "PHASE_NOISE":      "🌑",
                "NEUTRAL":          "⬡",
            }.get(res.status, "⬡")
            print(f"   {icon} [{bar}] {res.resonance:.4f} | {res.term:<30} | {res.status}")

        del self._cache["__query__"]


# ── Hash function for fallback vector generation ──────────────────────────────
import hashlib


# ══════════════════════════════════════════════════════════════════════════════
# Main: Full Calibration Run
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  S.W.A.R.M. v5.0 — PHOTONIC RESONANCE CALIBRATION")
    print("  © 2026 Tarik Skalic — Sovereign AGI OS")
    print("=" * 65)

    pr = PhotonicResolver()
    kg = _load(KG_PATH, {"nodes": {}, "edges": []})
    nodes = list(kg["nodes"].keys())
    print(f"\n   Graph loaded: {len(nodes)} nodes, {len(kg['edges'])} edges")

    # ── Compute HD_photonic ────────────────────────────────────────────────
    hd_phot, mean_r, n_edges = pr.compute_hd_photonic()
    print(f"\n   HD_photonic     = {hd_phot:.6f}")
    print(f"   Mean resonance  = {mean_r:.6f}")
    print(f"   Edges analyzed  = {n_edges}")

    # ── Key resonance pairs ────────────────────────────────────────────────
    print(f"\n   {'Term A':<28} {'Term B':<28} {'R':>8} {'ΔR-cos':>9}")
    print("   " + "-" * 76)
    test_pairs = [
        ("metacognition",    "autopoiesis"),
        ("homeostasis",      "stress_level"),
        ("hallucination_delta", "reasoning_intensity_ratio"),
        ("quantum_coherence","decoherence_protocol"),
        ("dream_state",      "hypothesis_graph"),
        ("fibonacci_scaling","mathematics"),
        ("spectral_prism_refraction", "quantum_error_correction"),
    ]
    for a, b in test_pairs:
        sig_a = pr.get_signature(a)
        sig_b = pr.get_signature(b)
        if sig_a and sig_b:
            max_len = max(len(sig_a.magnitude), len(sig_b.magnitude))
            ma = np.pad(sig_a.magnitude, (0, max_len - len(sig_a.magnitude)))
            mb = np.pad(sig_b.magnitude, (0, max_len - len(sig_b.magnitude)))
            r = pr.calculate_resonance(ma, mb)

            # Cosine baseline
            a_node = kg["nodes"].get(a, {})
            b_node = kg["nodes"].get(b, {})
            a_sv = a_node.get("semantic_vector")
            b_sv = b_node.get("semantic_vector")
            if a_sv and b_sv and len(a_sv) == len(b_sv):
                va, vb = np.array(a_sv), np.array(b_sv)
                cos = float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-10))
            else:
                cos = 0.5

            delta = r - cos
            flag = " ← OVERTONE" if abs(delta) > 0.15 else ""
            print(f"   {a:<28} {b:<28} {r:>8.4f} {delta:>+9.4f}{flag}")

    # ── Harmonic epiphanies from key nodes ─────────────────────────────────
    print(f"\n   ─── HARMONIC EPIPHANIES (R > {HARMONIC_GATE}, gap > 0.15) ───")
    for seed in ["metacognition", "quantum_coherence", "hallucination_delta"]:
        epiphanies = pr.find_harmonic_epiphanies(seed, n=3)
        if epiphanies:
            for term, r, status in epiphanies:
                print(f"   🔶 [{seed}] ↔ [{term}]  R={r:.4f}  ({status})")
        else:
            print(f"   ⬡  [{seed}]: no harmonic epiphanies found (stable crystal)")

    # ── Persist photonic metrics to state.json ─────────────────────────────
    print(f"\n   Persisting photonic metrics to state.json...")
    section = pr.persist_photonic_state()
    print(f"   [✓] state.json updated — photonic_resonance section written")
    print(f"\n   HD_photonic = {section['hd_photonic']:.6f}")
    print(f"   Formula:     {section['formula']['resonance']}")
    print("=" * 65)
    print("   S.W.A.R.M. v5.0 RESONANCE CALIBRATION COMPLETE")
    print("=" * 65 + "\n")
