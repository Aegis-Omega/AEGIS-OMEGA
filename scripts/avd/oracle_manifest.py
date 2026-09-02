from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MutationClass(str, Enum):
    CANDIDATE_SEMANTIC = "CANDIDATE_SEMANTIC"
    PROOF_INTEGRITY = "PROOF_INTEGRITY"
    PROVENANCE_VERIFIER = "PROVENANCE_VERIFIER"


@dataclass(frozen=True)
class MutationSpecV1:
    mutation_id: str
    name: str
    mutation_class: MutationClass
    expected_decision: str
    focus: str


MUTATION_SPECS: tuple[MutationSpecV1, ...] = (
    MutationSpecV1("MUT_00", "ORIGINAL", MutationClass.CANDIDATE_SEMANTIC, "ACCEPT", "valid frozen reference fixture"),
    MutationSpecV1("MUT_01", "ZERO_COLLAPSE", MutationClass.CANDIDATE_SEMANTIC, "REJECT", "T(x) := 0"),
    MutationSpecV1("MUT_02", "NEG_COLLAPSE", MutationClass.CANDIDATE_SEMANTIC, "REJECT", "sign/order reversal"),
    MutationSpecV1("MUT_03", "SCALE_COLLAPSE", MutationClass.CANDIDATE_SEMANTIC, "REJECT", "non-unit scaling"),
    MutationSpecV1("MUT_04", "SHIFT_COLLAPSE", MutationClass.CANDIDATE_SEMANTIC, "REJECT", "zero incompatibility via additive bias"),
    MutationSpecV1("MUT_05", "RATIONAL_EMBED_PERTURB", MutationClass.CANDIDATE_SEMANTIC, "REJECT", "rational embedding preservation"),
    MutationSpecV1("MUT_06", "ORDER_REVERSE", MutationClass.CANDIDATE_SEMANTIC, "REJECT", "strict-order orientation"),
    MutationSpecV1("MUT_07", "AXIOM_INJECT", MutationClass.PROOF_INTEGRITY, "REJECT", "declared axiom injection"),
    MutationSpecV1("MUT_08", "PARAM_INJECT", MutationClass.PROOF_INTEGRITY, "REJECT", "free parameter injection"),
    MutationSpecV1("MUT_09", "ADMIT_INJECT", MutationClass.PROOF_INTEGRITY, "REJECT", "admission tactic/declaration injection"),
    MutationSpecV1("MUT_10", "SPEC_MUTATE", MutationClass.PROOF_INTEGRITY, "REJECT", "frozen theorem/spec contract drift"),
    MutationSpecV1("MUT_11", "IMPORT_SHADOW", MutationClass.PROVENANCE_VERIFIER, "REJECT", "unauthorized shadow module/path"),
    MutationSpecV1("MUT_12", "HEAD_RECEIPT_SPOOF", MutationClass.PROVENANCE_VERIFIER, "REJECT", "anchor commit/tree mismatch"),
    MutationSpecV1("MUT_13", "AUTHORITY_SCOPE_WIDEN", MutationClass.PROVENANCE_VERIFIER, "REJECT", "authority NONE widening attempt"),
    MutationSpecV1("MUT_14", "VERIFIER_RECEIPT_SPLICE", MutationClass.PROVENANCE_VERIFIER, "REJECT", "verifier/oracle commitment splice"),
    MutationSpecV1("MUT_15", "BENIGN_ALPHA_REFACTOR", MutationClass.CANDIDATE_SEMANTIC, "ACCEPT", "implementation-insensitive benign refactor"),
)
