"""AEGIS Ω Weil convergence bridge proof kernel v1.

This module is deliberately narrower than a Riemann-Hypothesis proof.
It verifies exact algebraic implications around finite/truncated Weil-form
bounds, rejects target-circular assumptions, records the independent-premise
gap, and refuses to promote finite-family evidence into global Weil positivity.

The bridge is proof-carrying software evidence only:

    WeilBridgeReceipt != RH proof
    ProofTrace != mathematical truth
    finite family != universal quantification
    hash integrity != theorem validity

A future version may close the globalization gap only by re-running an
independent fixed-kernel theorem checker for density, continuity, and complete
coverage of the admissible test-function space.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Iterable

from harness.sdk.proof_trace import (
    DENIED,
    NO_AUTHORITY,
    OK,
    T2,
    VERIFIER,
    ProofTrace,
    TraceSpanV1,
    digest_payload,
)
from harness.sdk.sovereign_execution import canonical_hash

WEIL_INSTANCE_KIND = "AEGIS_WEIL_INSTANCE_EVIDENCE_V1"
WEIL_INSTANCE_RECEIPT_KIND = "AEGIS_WEIL_INSTANCE_PROOF_RECEIPT_V1"
WEIL_FAMILY_KIND = "AEGIS_WEIL_FAMILY_EVIDENCE_V1"
WEIL_FAMILY_RECEIPT_KIND = "AEGIS_WEIL_FAMILY_PROOF_RECEIPT_V1"
GLOBAL_GATE_KIND = "AEGIS_GLOBAL_WEIL_CLAIM_GATE_V1"
PROOF_SEMANTICS = "EVIDENCE_ONLY_NOT_RH_PROOF"

ASSUME_RH = "ASSUME_RH"
ASSUME_GLOBAL_WEIL_POSITIVITY = "ASSUME_GLOBAL_WEIL_POSITIVITY"
ASSUME_ALL_ZETA_ZEROS_ON_CRITICAL_LINE = "ASSUME_ALL_ZETA_ZEROS_ON_CRITICAL_LINE"
ASSUME_TARGET_CLAIM = "ASSUME_TARGET_CLAIM"
FORBIDDEN_CIRCULAR_ASSUMPTIONS = frozenset(
    {
        ASSUME_RH,
        ASSUME_GLOBAL_WEIL_POSITIVITY,
        ASSUME_ALL_ZETA_ZEROS_ON_CRITICAL_LINE,
        ASSUME_TARGET_CLAIM,
    }
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")


class WeilBridgeError(ValueError):
    """Fail-closed input/contract error with a stable machine code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise WeilBridgeError(f"{name}:INVALID_SHA256")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise WeilBridgeError(f"{name}:INVALID_ID")


@dataclass(frozen=True)
class ExactRationalV1:
    """Canonical exact rational. Binary floating point is intentionally absent."""

    numerator: int
    denominator: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.numerator, bool) or not isinstance(self.numerator, int):
            raise WeilBridgeError("NUMERATOR_INVALID")
        if isinstance(self.denominator, bool) or not isinstance(self.denominator, int) or self.denominator == 0:
            raise WeilBridgeError("DENOMINATOR_INVALID")

        n = self.numerator
        d = self.denominator
        if d < 0:
            n = -n
            d = -d
        g = math.gcd(abs(n), d)
        if g == 0:
            g = 1
        object.__setattr__(self, "numerator", n // g)
        object.__setattr__(self, "denominator", d // g)

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @classmethod
    def from_fraction(cls, value: Fraction) -> "ExactRationalV1":
        return cls(value.numerator, value.denominator)


@dataclass(frozen=True)
class WeilInstanceEvidenceV1:
    """One finite/truncated Weil-form proof obligation.

    ``finite_evaluator_root`` and ``approximation_bound_root`` are evidence
    commitments, not self-authenticating mathematical premises. v1 checks the
    exact implication that would follow from them and keeps premise closure
    explicit in the receipt.
    """

    test_function_digest: str
    cutoff: int
    q_r: ExactRationalV1
    norm_sq: ExactRationalV1
    epsilon_r: ExactRationalV1
    approximation_delta: ExactRationalV1
    finite_evaluator_root: str
    approximation_bound_root: str
    assumption_tags: tuple[str, ...] = ()
    evidence_kind: str = WEIL_INSTANCE_KIND
    proof_semantics: str = PROOF_SEMANTICS

    def __post_init__(self) -> None:
        if self.evidence_kind != WEIL_INSTANCE_KIND:
            raise WeilBridgeError("WEIL_INSTANCE_KIND_MISMATCH")
        if self.proof_semantics != PROOF_SEMANTICS:
            raise WeilBridgeError("WEIL_PROOF_SEMANTICS_MISMATCH")
        _require_hash("test_function_digest", self.test_function_digest)
        _require_hash("finite_evaluator_root", self.finite_evaluator_root)
        _require_hash("approximation_bound_root", self.approximation_bound_root)
        if isinstance(self.cutoff, bool) or not isinstance(self.cutoff, int) or self.cutoff < 2:
            raise WeilBridgeError("CUTOFF_INVALID")
        if self.norm_sq.fraction < 0:
            raise WeilBridgeError("NORM_SQ_NEGATIVE")
        if self.epsilon_r.fraction < 0:
            raise WeilBridgeError("EPSILON_NEGATIVE")
        if self.approximation_delta.fraction < 0:
            raise WeilBridgeError("APPROXIMATION_DELTA_NEGATIVE")
        if len(set(self.assumption_tags)) != len(self.assumption_tags):
            raise WeilBridgeError("ASSUMPTION_TAG_DUPLICATE")
        for tag in self.assumption_tags:
            _require_id("assumption_tag", tag)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_WEIL_INSTANCE_EVIDENCE_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class WeilInstanceVerificationV1:
    receipt_kind: str
    proof_semantics: str
    subject_root: str
    valid: bool
    status: str
    circular: bool
    finite_lower_bound_verified: bool
    conditional_target_nonnegative: bool
    premises_independently_verified: bool
    rh_proven: bool
    errors: tuple[str, ...]
    open_obligations: tuple[str, ...]
    conditional_target_lower_bound: ExactRationalV1

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_WEIL_INSTANCE_PROOF_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


def verify_weil_instance(evidence: WeilInstanceEvidenceV1) -> WeilInstanceVerificationV1:
    """Verify the v1 local algebra and expose unclosed premise obligations.

    The checked implications are exact:

        Q_R >= -epsilon_R ||f||^2

    and, conditionally on an externally established approximation theorem,

        |Q_W - Q_R| <= delta_R  and  Q_R - delta_R >= 0
        ------------------------------------------------
                           Q_W >= 0.

    The function verifies the algebra, not the truth of a caller-supplied
    approximation/evaluator commitment. Therefore ``rh_proven`` is always
    false in v1.
    """

    circular = any(tag in FORBIDDEN_CIRCULAR_ASSUMPTIONS for tag in evidence.assumption_tags)
    errors: list[str] = []
    if circular:
        errors.append("CIRCULAR_ASSUMPTION_FORBIDDEN")

    q = evidence.q_r.fraction
    norm_sq = evidence.norm_sq.fraction
    epsilon = evidence.epsilon_r.fraction
    delta = evidence.approximation_delta.fraction

    finite_lower_bound_verified = q + epsilon * norm_sq >= 0
    if not finite_lower_bound_verified:
        errors.append("FINITE_LOWER_BOUND_VIOLATED")

    conditional_lower = q - delta
    conditional_target_nonnegative = (
        not circular and finite_lower_bound_verified and conditional_lower >= 0
    )

    valid = not errors
    status = "LOCAL_ALGEBRAIC_INFERENCE_VERIFIED" if valid else "REJECTED"

    open_obligations: list[str] = [
        "FINITE_EVALUATOR_PREMISE_REQUIRES_INDEPENDENT_VERIFIER",
        "APPROXIMATION_PREMISE_REQUIRES_INDEPENDENT_VERIFIER",
        "FINITE_INSTANCE_DOES_NOT_ESTABLISH_GLOBAL_POSITIVITY",
    ]
    if not conditional_target_nonnegative and valid:
        open_obligations.append("CURRENT_CUTOFF_DOES_NOT_CERTIFY_CONDITIONAL_NONNEGATIVITY")

    return WeilInstanceVerificationV1(
        receipt_kind=WEIL_INSTANCE_RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        subject_root=evidence.root,
        valid=valid,
        status=status,
        circular=circular,
        finite_lower_bound_verified=finite_lower_bound_verified,
        conditional_target_nonnegative=conditional_target_nonnegative,
        premises_independently_verified=False,
        rh_proven=False,
        errors=tuple(sorted(set(errors))),
        open_obligations=tuple(sorted(set(open_obligations))),
        conditional_target_lower_bound=ExactRationalV1.from_fraction(conditional_lower),
    )


@dataclass(frozen=True)
class WeilFamilyEvidenceV1:
    family_id: str
    members: tuple[WeilInstanceEvidenceV1, ...]
    evidence_kind: str = WEIL_FAMILY_KIND
    proof_semantics: str = PROOF_SEMANTICS

    def __post_init__(self) -> None:
        if self.evidence_kind != WEIL_FAMILY_KIND:
            raise WeilBridgeError("WEIL_FAMILY_KIND_MISMATCH")
        if self.proof_semantics != PROOF_SEMANTICS:
            raise WeilBridgeError("WEIL_PROOF_SEMANTICS_MISMATCH")
        _require_id("family_id", self.family_id)
        if not self.members:
            raise WeilBridgeError("WEIL_FAMILY_EMPTY")
        roots = [member.root for member in self.members]
        if len(set(roots)) != len(roots):
            raise WeilBridgeError("WEIL_FAMILY_DUPLICATE_MEMBER")

    @property
    def root(self) -> str:
        return canonical_hash(
            "AEGIS_WEIL_FAMILY_EVIDENCE_ROOT_V1",
            {
                "family_id": self.family_id,
                "proof_semantics": self.proof_semantics,
                "member_roots": sorted(member.root for member in self.members),
            },
        )


@dataclass(frozen=True)
class WeilFamilyVerificationV1:
    receipt_kind: str
    proof_semantics: str
    source_family_root: str
    family_root: str
    member_count: int
    valid: bool
    status: str
    all_conditional_nonnegative: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    member_receipt_roots: tuple[str, ...]
    errors: tuple[str, ...]
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_WEIL_FAMILY_PROOF_RECEIPT_ROOT_V1", asdict(self))


def verify_weil_family(family: WeilFamilyEvidenceV1) -> WeilFamilyVerificationV1:
    verified = [verify_weil_instance(member) for member in family.members]
    receipt_roots = tuple(sorted(item.receipt_root for item in verified))
    family_root = canonical_hash(
        "AEGIS_WEIL_VERIFIED_FAMILY_ROOT_V1",
        {
            "family_id": family.family_id,
            "source_family_root": family.root,
            "member_receipt_roots": receipt_roots,
        },
    )
    errors = tuple(sorted({error for item in verified for error in item.errors}))
    valid = all(item.valid for item in verified)
    all_conditional = valid and all(item.conditional_target_nonnegative for item in verified)
    status = "FINITE_FAMILY_CONDITIONALLY_VERIFIED" if all_conditional else "FINITE_FAMILY_NOT_CLOSED"
    open_obligations = {
        obligation
        for item in verified
        for obligation in item.open_obligations
    }
    open_obligations.update(
        {
            "FINITE_FAMILY_DOES_NOT_ESTABLISH_GLOBAL_POSITIVITY",
            "DENSITY_THEOREM_REQUIRES_MACHINE_VERIFICATION",
            "CONTINUITY_THEOREM_REQUIRES_MACHINE_VERIFICATION",
            "UNIVERSAL_COVERAGE_REQUIRES_MACHINE_VERIFICATION",
        }
    )
    return WeilFamilyVerificationV1(
        receipt_kind=WEIL_FAMILY_RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        source_family_root=family.root,
        family_root=family_root,
        member_count=len(verified),
        valid=valid,
        status=status,
        all_conditional_nonnegative=all_conditional,
        global_weil_positivity_proven=False,
        rh_proven=False,
        member_receipt_roots=receipt_roots,
        errors=errors,
        open_obligations=tuple(sorted(open_obligations)),
    )


@dataclass(frozen=True)
class GlobalWeilClaimGateV1:
    gate_kind: str
    proof_semantics: str
    family_receipt_root: str
    density_proof_root: str
    continuity_proof_root: str
    universal_coverage_proof_root: str
    closed: bool
    status: str
    global_weil_positivity_proven: bool
    rh_proven: bool
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_GLOBAL_WEIL_CLAIM_GATE_ROOT_V1", asdict(self))


def request_global_weil_claim(
    family: WeilFamilyVerificationV1,
    *,
    density_proof_root: str,
    continuity_proof_root: str,
    universal_coverage_proof_root: str,
) -> GlobalWeilClaimGateV1:
    """Fail closed on global promotion in v1.

    Roots are only commitments. Without an integrated checker that replays the
    corresponding theorem artifacts, accepting them would be self-assertion.
    """

    _require_hash("density_proof_root", density_proof_root)
    _require_hash("continuity_proof_root", continuity_proof_root)
    _require_hash("universal_coverage_proof_root", universal_coverage_proof_root)
    return GlobalWeilClaimGateV1(
        gate_kind=GLOBAL_GATE_KIND,
        proof_semantics=PROOF_SEMANTICS,
        family_receipt_root=family.receipt_root,
        density_proof_root=density_proof_root,
        continuity_proof_root=continuity_proof_root,
        universal_coverage_proof_root=universal_coverage_proof_root,
        closed=False,
        status="OPEN_KERNEL_GLOBALIZATION_REQUIRED",
        global_weil_positivity_proven=False,
        rh_proven=False,
        open_obligations=(
            "GLOBALIZATION_THEOREMS_NOT_MACHINE_VERIFIED",
            "WEIL_POSITIVITY_TO_RH_EQUIVALENCE_NOT_EXECUTED_AS_GLOBAL_CLOSURE",
        ),
    )


@dataclass(frozen=True)
class WeilTraceBindingV1:
    verification: WeilInstanceVerificationV1
    span: TraceSpanV1

    @property
    def binding_root(self) -> str:
        return canonical_hash(
            "AEGIS_WEIL_TRACE_BINDING_ROOT_V1",
            {
                "verification_root": self.verification.receipt_root,
                "span_root": self.span.root,
            },
        )


def bind_weil_instance_verification(
    trace: ProofTrace,
    evidence: WeilInstanceEvidenceV1,
    *,
    causal_parent_ids: Iterable[str] = (),
) -> WeilTraceBindingV1:
    """Re-run the local verifier and attach its receipt as T2 evidence only."""

    verification = verify_weil_instance(evidence)
    handle = trace.start_span(
        name="weil-convergence-bridge",
        span_kind=VERIFIER,
        causal_parent_ids=tuple(causal_parent_ids),
        start_context={
            "proof_semantics": PROOF_SEMANTICS,
            "subject_root": evidence.root,
        },
    )
    span = trace.finish_span(
        handle,
        status=OK if verification.valid else DENIED,
        authority_class=NO_AUTHORITY,
        epistemic_tier=T2,
        input_digest=digest_payload(asdict(evidence)),
        output_digest=digest_payload(verification.to_dict()),
        evidence_roots=(verification.receipt_root,),
        error_code=None if verification.valid else "WEIL_BRIDGE_REJECTED",
    )
    return WeilTraceBindingV1(verification=verification, span=span)
