"""
Sovereign HD — Core Middleware: Attention Spectral Transition Guard

Bridges biological state (stress, attention, RIR, ATP) with the
attention tensor's spectral geometry to detect lambda-collapse
(the Baik-Ben Arous-Péché phase transition in QK^T space).

Integration: results are submitted to /platform/holon/validate as
constitutional verdicts in the AEGIS chain.

Epistemic tier: T2 — engineering hypothesis, computable.
"""

import json
import urllib.request as _ur
import urllib.error as _ue
from typing import Optional

import numpy as np
import torch

# Constitutional constant — Fibonacci recurrence separatrix
PHI = (5 ** 0.5 - 1) / 2  # ≈ 0.6180339887

# λ_c = 1.0 is the BBP threshold in τ-normalised coordinates:
# the bulk spectrum edge of a random d_k×d_k matrix scaled by 1/√d_k.
# Setting it lower (e.g. PHI) tightens the gate.
DEFAULT_LAMBDA_C = 1.0

HOLON_ENDPOINT = 'https://aegis-vertex.aegisomega.com/platform/holon/validate'


class SovereignHD:
    """
    Primary middleware evaluation pipeline.

    Extracts the spectral radius of the unnormalised QK^T attention
    interaction tensor, modulates it by a bio-derived temperature, and
    compares the result against the separatrix λ_c to decide
    APPROVED / REJECTED.

    Bio guardrails are checked first (zero-cost, deterministic) before
    the SVD computation.
    """

    def __init__(self, d_k: int = 64, lambda_c: float = DEFAULT_LAMBDA_C):
        self.d_k = d_k
        self.lambda_c = lambda_c
        # ATP reference level for a healthy, alert operator.
        self._atp_ref = 2500.0

    def _normalise_bio(self, bio_state: dict) -> tuple[float, float, float]:
        """
        Map raw bio features to [0.1, 1.0].

        Features are assumed to be in [0, 1] already (stress, attention, rir).
        Linear map: x_norm = 0.1 + 0.9 * x.
        This preserves discriminative power across the full range — a single-row
        MinMaxScaler collapses everything to 0.1 (constant), making it useless.
        """
        stress = float(np.clip(bio_state.get('stress', 0.4262), 0.0, 1.0))
        attn   = float(np.clip(bio_state.get('attention', 0.82),  0.0, 1.0))
        rir    = float(np.clip(bio_state.get('rir', 0.9511),      0.0, 1.0))
        return (0.1 + 0.9 * stress,
                0.1 + 0.9 * attn,
                0.1 + 0.9 * rir)

    def guard_inference(
        self,
        qk_t_tensor: torch.Tensor,
        bio_state: dict,
    ) -> dict:
        """
        Evaluate QK^T against the lambda-collapse separatrix.

        Returns a verdict dict compatible with /platform/holon/validate.
        """
        norm_stress, norm_attn, norm_rir = self._normalise_bio(bio_state)
        atp = float(bio_state.get('atp', 2100))

        # ── Hard biological guardrails (deterministic, evaluated before SVD) ──
        if norm_stress >= 0.8 or atp <= 0:
            return {
                'verdict': 'FAILED',
                'lambda_attn': float('inf'),
                'spectral_radius': None,
                'biological_temperature': None,
                'confidence': 0.99,
                'reason_code': 'LIMBIC_EXHAUSTION_OR_ATP_DEPLETION',
            }

        # ── PyTorch spectral analysis ─────────────────────────────────────────
        with torch.no_grad():
            _, S_val, _ = torch.linalg.svd(qk_t_tensor)
            # S_val[0] is σ₁, the operator norm (largest singular value).
            # For symmetric QK^T this equals the spectral radius; for
            # non-symmetric it upper-bounds it.
            spectral_radius = float(S_val[0])

        # ── Bio-modulated softmax temperature ────────────────────────────────
        tau_base = float(np.sqrt(self.d_k))
        # Temperature falls as stress rises (focus narrows) and as ATP depletes.
        tau_bio = tau_base * (atp / self._atp_ref) * float(np.exp(-norm_stress))
        tau_bio = max(0.01, tau_bio)

        # ── Lambda-collapse phase transition ──────────────────────────────────
        # λ_attn = ρ(QK^T) / τ_bio.
        # λ_attn ≥ λ_c → BBP transition → attractor collapse → hallucination risk.
        lambda_attn = spectral_radius / tau_bio

        if lambda_attn >= self.lambda_c:
            return {
                'verdict': 'FAILED',
                'lambda_attn': float(lambda_attn),
                'spectral_radius': float(spectral_radius),
                'biological_temperature': float(tau_bio),
                'confidence': min(0.99, float(lambda_attn - self.lambda_c + 0.5)),
                'reason_code': (
                    f'PHASE_III_COLLAPSE lambda={lambda_attn:.4f} '
                    f'> separatrix={self.lambda_c}'
                ),
            }

        headroom = self.lambda_c - lambda_attn
        return {
            'verdict': 'APPROVED',
            'lambda_attn': float(lambda_attn),
            'spectral_radius': float(spectral_radius),
            'biological_temperature': float(tau_bio),
            'confidence': min(0.99, float(headroom / self.lambda_c + 0.5)),
            'reason_code': (
                f'STABLE lambda={lambda_attn:.4f} '
                f'< separatrix={self.lambda_c} headroom={headroom:.4f}'
            ),
        }

    def submit_to_chain(
        self,
        result: dict,
        bio_state: dict,
        holon_id: str = 'sovereign-hd-iphone',
        endpoint: str = HOLON_ENDPOINT,
        timeout: int = 5,
    ) -> Optional[dict]:
        """
        POST the guard_inference result to the AEGIS constitutional chain.
        Returns the chain entry response, or None on network failure (dev mode).
        """
        payload = json.dumps({
            'holon_id': holon_id,
            'verdict': 'APPROVED' if result['verdict'] == 'APPROVED' else 'FAILED',
            'confidence': result.get('confidence', 0.5),
            'reason_code': result.get('reason_code', ''),
            'bio_state': {
                'stress':    bio_state.get('stress', 0.0),
                'attention': bio_state.get('attention', 0.0),
                'rir':       bio_state.get('rir', 0.0),
                'atp':       bio_state.get('atp', 0.0),
            },
            'lambda_attn':   result.get('lambda_attn'),
            'spectral_radius': result.get('spectral_radius'),
        }).encode()

        req = _ur.Request(
            endpoint,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with _ur.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None


# ── Verification loop ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== SOVEREIGN HD — INTEGRATION TEST ===')
    guard = SovereignHD(d_k=64)

    # Case 1: spike above BBP threshold → collapse
    qk_spiked = torch.randn(12, 12) * 2.0
    qk_spiked[0, 0] += 30.0  # rank-1 BBP perturbation
    bio_nominal = {'stress': 0.4262, 'attention': 0.82, 'rir': 0.9511, 'atp': 2100}
    r1 = guard.guard_inference(qk_spiked, bio_nominal)
    print(f'\n[1] Spiked QK^T + nominal bio:')
    print(json.dumps(r1, indent=2))

    # Case 2: normal random tensor → stable
    qk_normal = torch.randn(12, 12) * 2.0
    r2 = guard.guard_inference(qk_normal, bio_nominal)
    print(f'\n[2] Normal QK^T + nominal bio:')
    print(json.dumps(r2, indent=2))

    # Case 3: high stress → hard gate fires
    bio_stressed = {'stress': 0.95, 'attention': 0.3, 'rir': 0.4, 'atp': 2100}
    r3 = guard.guard_inference(qk_normal, bio_stressed)
    print(f'\n[3] Normal QK^T + high stress:')
    print(json.dumps(r3, indent=2))

    # Case 4: ATP depleted → hard gate fires
    bio_atp_zero = {'stress': 0.3, 'attention': 0.9, 'rir': 0.9, 'atp': 0}
    r4 = guard.guard_inference(qk_normal, bio_atp_zero)
    print(f'\n[4] Normal QK^T + ATP=0:')
    print(json.dumps(r4, indent=2))

    print(f'\nConstitutional separatrix φ = {PHI:.10f}')
    print(f'Current separatrix λ_c      = {guard.lambda_c:.4f}')
    print(f'(Set lambda_c=PHI for tighter constitutional gate)')
