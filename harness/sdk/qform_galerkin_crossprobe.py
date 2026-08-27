"""Cross-layer receipt binding the Gaussian QForm probe to the finite Arb Galerkin route.

The only promoted bridge in v1 is the *scale identity*

    L = log(c) = log(P_cutoff)

and the rigorously enclosed scalar Gaussian-envelope condition

    L >= C(epsilon) * sigma,
    C(epsilon) = 2*sqrt(log(1/epsilon)).

The receipt also replays the existing cutoff-free Arb Galerkin verifier at the
same integer cutoff ``c``.  It deliberately does **not** identify the Gaussian
quadratic functional with that Galerkin matrix.  That semantic correspondence,
compact-support approximation, and global Weil/RH implications remain false.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Optional

from flint import arb, ctx

from harness.sdk.guinand_weil_arb import ArbGalerkinSpecV1, verify_cutoff_free_galerkin
from harness.sdk.qform_receipt import (
    CERTIFIED_INTERVAL,
    EMPIRICAL_FIXTURE,
    QFormReceiptError,
    gaussian_cutoff_certificate,
)
from harness.sdk.sovereign_execution import canonical_hash

RECEIPT_KIND = "AEGIS_QFORM_GALERKIN_CROSS_RECEIPT_V1"
PROOF_SEMANTICS = "CERTIFIED_SCALE_BINDING_PLUS_FINITE_GALERKIN_REPLAY_NOT_SEMANTIC_IDENTITY"


@dataclass(frozen=True)
class QFormGalerkinCrossSpecV1:
    c: int
    sigma: str
    epsilon: str
    N: int
    prec_bits: int = 256

    def __post_init__(self) -> None:
        # Reuse the Galerkin contract for c/N/precision validation.
        ArbGalerkinSpecV1(c=self.c, N=self.N, prec_bits=self.prec_bits)
        try:
            s = arb(self.sigma)
            eps = arb(self.epsilon)
        except Exception as exc:  # pragma: no cover - backend parse detail
            raise QFormReceiptError("CROSS_SPEC_DECIMAL_INVALID") from exc
        if not bool(s > 0):
            raise QFormReceiptError("SIGMA_NOT_STRICTLY_POSITIVE")
        if not bool(eps > 0 and eps < 1):
            raise QFormReceiptError("EPSILON_OUT_OF_RANGE")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_QFORM_GALERKIN_CROSS_SPEC_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class QFormGalerkinCrossReceiptV1:
    receipt_kind: str
    proof_semantics: str
    subject_root: str
    provenance: dict[str, object]
    scale_binding: dict[str, object]
    galerkin_replay: dict[str, object]
    finite_scale_binding_authority: str
    overall_authority: str
    gaussian_to_galerkin_semantics_verified: bool
    compact_support_bridge_verified: bool
    formula_to_weil_operator_identity_proven: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_QFORM_GALERKIN_CROSS_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


def _git_text(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QFormReceiptError("GIT_PROVENANCE_UNAVAILABLE") from exc


def _resolve_provenance(source_commit: Optional[str], source_tree: Optional[str]) -> tuple[str, str]:
    commit = source_commit or _git_text("rev-parse", "HEAD")
    tree = source_tree or _git_text("rev-parse", f"{commit}^{{tree}}")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise QFormReceiptError("SOURCE_COMMIT_INVALID")
    if len(tree) != 40 or any(ch not in "0123456789abcdef" for ch in tree):
        raise QFormReceiptError("SOURCE_TREE_INVALID")
    return commit, tree


def _ball_from_dict(ball: dict[str, str]) -> arb:
    # Reconstruct only for a conservative relational cross-check.  The source
    # certificate remains authoritative for its own Arb enclosure.
    mid = arb(ball["mid"])
    rad = arb(ball["rad"])
    return mid + arb(0, rad)


def build_qform_galerkin_cross_receipt(
    spec: QFormGalerkinCrossSpecV1,
    *,
    source_commit: Optional[str] = None,
    source_tree: Optional[str] = None,
) -> QFormGalerkinCrossReceiptV1:
    ctx.prec = spec.prec_bits
    cutoff = gaussian_cutoff_certificate(
        sigma=spec.sigma,
        epsilon=spec.epsilon,
        P_cutoff=spec.c,
        prec_bits=spec.prec_bits,
    )
    galerkin = verify_cutoff_free_galerkin(
        ArbGalerkinSpecV1(c=spec.c, N=spec.N, prec_bits=spec.prec_bits)
    )

    u_cut = _ball_from_dict(cutoff["u_cut_ball"])
    required = _ball_from_dict(cutoff["required_u_cut_ball"])
    scale_relation_replayed = bool(u_cut >= required)
    if scale_relation_replayed != cutoff["cutoff_relation_verified"]:
        raise QFormReceiptError("GAUSSIAN_SCALE_REPLAY_MISMATCH")

    commit, tree = _resolve_provenance(source_commit, source_tree)
    implementation_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    parameter_sha256 = hashlib.sha256(
        json.dumps(asdict(spec), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    scale_binding = {
        "status": CERTIFIED_INTERVAL,
        "c_equals_P_cutoff_by_construction": True,
        "L_definition": "L=log(c)=log(P_cutoff)",
        "sigma": spec.sigma,
        "epsilon": spec.epsilon,
        "C_epsilon_ball": cutoff["C_epsilon_ball"],
        "L_ball": cutoff["u_cut_ball"],
        "required_L_ball": cutoff["required_u_cut_ball"],
        "gaussian_envelope_tail_ball": cutoff["envelope_tail_ball"],
        "L_ge_C_sigma_verified": scale_relation_replayed,
        "gaussian_envelope_below_epsilon_verified": cutoff["envelope_below_epsilon_verified"],
        "scope": "SCALAR_SCALE_COORDINATION_ONLY",
    }

    galerkin_replay = {
        "receipt_root": galerkin.receipt_root,
        "status": galerkin.status,
        "c": galerkin.c,
        "N": galerkin.N,
        "dimension": galerkin.dimension,
        "prec_bits": galerkin.prec_bits,
        "cutoff_free_entry_enclosures_verified": galerkin.cutoff_free_entry_enclosures_verified,
        "interval_inertia_verified": galerkin.interval_inertia_verified,
        "n_positive": galerkin.n_positive,
        "n_negative": galerkin.n_negative,
        "undetermined_pivot": galerkin.undetermined_pivot,
        "finite_matrix_positive_definite_verified": galerkin.finite_matrix_positive_definite_verified,
        "finite_matrix_psd_verified": galerkin.finite_matrix_psd_verified,
        "matrix_root": galerkin.matrix_root,
        "pivot_root": galerkin.pivot_root,
        "galerkin_semantics_verified": galerkin.galerkin_semantics_verified,
        "global_weil_positivity_proven": galerkin.global_weil_positivity_proven,
        "rh_proven": galerkin.rh_proven,
        "errors": list(galerkin.errors),
        "open_obligations": list(galerkin.open_obligations),
    }

    obligations = {
        "COMPACT_SUPPORT_GAUSSIAN_CORE_THEOREM_NOT_MACHINE_BOUND",
        "GAUSSIAN_QFORM_TO_GALERKIN_SEMANTIC_IDENTITY_NOT_MACHINE_BOUND",
        "FORMULA_TO_WEIL_OPERATOR_IDENTITY_NOT_MACHINE_BOUND",
        "FINITE_WINDOW_TO_GLOBAL_WEIL_COVERAGE_NOT_MACHINE_BOUND",
        "WEIL_CRITERION_NOT_MACHINE_BOUND",
    }
    obligations.update(galerkin.open_obligations)

    return QFormGalerkinCrossReceiptV1(
        receipt_kind=RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        subject_root=spec.root,
        provenance={
            "repository": "Aegis-Omega/AEGIS-OMEGA",
            "commit_sha": commit,
            "tree_sha": tree,
            "implementation_sha256": implementation_sha256,
            "parameter_sha256": parameter_sha256,
        },
        scale_binding=scale_binding,
        galerkin_replay=galerkin_replay,
        finite_scale_binding_authority=CERTIFIED_INTERVAL,
        overall_authority=EMPIRICAL_FIXTURE,
        gaussian_to_galerkin_semantics_verified=False,
        compact_support_bridge_verified=False,
        formula_to_weil_operator_identity_proven=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        open_obligations=tuple(sorted(obligations)),
    )
