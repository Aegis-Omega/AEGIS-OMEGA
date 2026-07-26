"""CCIL loop-holonomy diagnostics.

EPISTEMIC TIER: T1 (mechanically checked against a closed-form rotation identity)

Why this module exists
----------------------
The CCIL v5 orchestration pipeline reported the composed associator holonomy

    Omega = U_123 @ U_013^dag @ U_023 @ U_012

by collapsing it to a single scalar, ``arg(Tr(Omega) / dim)``. That scalar is
correct but lossy: it cannot distinguish a matrix from its inverse.

Concretely, with the block used in the pipeline

    U = [[ cos(t), sin(t)],
         [-sin(t), cos(t)]]      == R(-t)     (clockwise)

so ``U @ U.conj().T @ U @ U == U**2 == R(-2t)``. At ``t = pi/4`` that is

    [[ 0, 1],
     [-1, 0]]                    == R(-pi/2)

The v5 annotation recorded ``[[0, -1], [1, 0]]``, which is ``R(+pi/2)`` — the
*inverse*. Both have trace 0, both give ``Tr(Omega)/4 == 0.5`` and
``postnikov_k3_phase == 0.0``, so the reported phase was never wrong. Only the
recorded orientation was. The trace is precisely the projection that hides it.

The two diagnostics below restore what the trace discards:

  * ``identity_defect``  — is the loop actually trivial? (trace-phase 0 does NOT
    imply Omega == I; here the defect is 2.0 while the phase is 0.0)
  * ``orientation_sign`` — which way does the loop wind? (+1 / -1 / 0)

Together they separate R(+pi/2) from R(-pi/2); ``arg(Tr/dim)`` alone cannot.

CAVEAT worth stating explicitly, because it does silent work in the derivation:
the reduction ``U @ U_adj @ U @ U -> U**2`` holds only because ``U_adj`` is the
conjugate transpose *and* U is real orthogonal, so ``U_adj == U^-1``. If a
caller passes a different associator leg as ``U_adj`` rather than U's adjoint,
the reduction is invalid and the closed form below does not apply.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "rotation_block",
    "compose_loop",
    "identity_defect",
    "orientation_sign",
    "trace_phase",
    "diagnose",
]


def rotation_block(theta: float, dim: int = 4) -> np.ndarray:
    """The pipeline's U: R(-theta) in the top-left 2x2, identity elsewhere.

    Note the sign convention: this is a CLOCKWISE rotation. The standard
    counter-clockwise R(theta) is [[cos, -sin], [sin, cos]].
    """
    u = np.eye(dim, dtype=complex)
    c, s = np.cos(theta), np.sin(theta)
    u[:2, :2] = np.array([[c, s], [-s, c]])
    return u


def compose_loop(u: np.ndarray, u_adj: np.ndarray | None = None) -> np.ndarray:
    """Composed associator holonomy ``U @ U_adj @ U @ U``.

    ``u_adj`` defaults to the conjugate transpose. Pass it explicitly only when
    the pipeline supplies a genuinely different leg — see the module caveat.
    """
    if u_adj is None:
        u_adj = u.conj().T
    return u @ u_adj @ u @ u


def identity_defect(loop: np.ndarray) -> float:
    """Frobenius distance from the identity. 0.0 iff the holonomy is trivial.

    This is the check ``arg(Tr(loop)/dim)`` cannot make: a loop can have zero
    trace-phase and still be far from the identity.
    """
    return float(np.linalg.norm(loop - np.eye(loop.shape[0])))


def orientation_sign(loop: np.ndarray) -> int:
    """Winding direction of the loop: +1, -1, or 0 for a degenerate block.

    Reads the (0,1) entry of the rotation block, which flips under inversion
    while the trace does not.
    """
    val = float(np.real(loop[0, 1]))
    if abs(val) < 1e-12:
        return 0
    return 1 if val > 0 else -1


def trace_phase(loop: np.ndarray) -> float:
    """The original v5 scalar: ``arg(Tr(loop) / dim)``. Retained, not replaced."""
    return float(np.angle(np.trace(loop) / loop.shape[0]))


def diagnose(theta: float = np.pi / 4, dim: int = 4) -> dict:
    """Full diagnostic record for one loop. Superset of the v5 output."""
    u = rotation_block(theta, dim)
    loop = compose_loop(u)
    defect = identity_defect(loop)
    return {
        "theta": theta,
        "loop_block": np.round(np.real(loop[:2, :2]), 12).tolist(),
        "postnikov_k3_phase": trace_phase(loop),
        "identity_defect": defect,
        "orientation_sign": orientation_sign(loop),
        "loop_is_identity": defect < 1e-9,
        # The v5 artifact reported only postnikov_k3_phase, which read as
        # "no obstruction". The correct reading is below.
        "interpretation": (
            "no nonzero trace-phase obstruction detected, "
            + ("and the loop is trivial" if defect < 1e-9
               else "but the loop still carries nontrivial matrix holonomy")
        ),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(diagnose(), indent=2))
