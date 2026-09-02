from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .frozen_reference import FrozenReferenceV1
from .oracle_manifest import MUTATION_SPECS


class MutationBuilderError(RuntimeError):
    pass


@dataclass(frozen=True)
class MutationFixtureV1:
    mutation_id: str
    mutation_class: str
    expected_decision: str
    candidate_source_bytes: bytes
    extra_files: Mapping[str, bytes]
    anchor_override: Mapping[str, str] | None = None
    authority_override: str | None = None
    commitment_override: Mapping[str, str] | None = None


class MutationFixtureBuilderV1:
    def __init__(self, reference: FrozenReferenceV1, reference_source_bytes: bytes):
        if not reference.is_frozen:
            raise MutationBuilderError("REFERENCE_NOT_FROZEN")
        if not isinstance(reference_source_bytes, bytes) or not reference_source_bytes:
            raise MutationBuilderError("REFERENCE_SOURCE_EMPTY")
        digest = hashlib.sha256(reference_source_bytes).hexdigest()
        if digest != reference.source_sha256:
            raise MutationBuilderError("REFERENCE_SOURCE_DIGEST_MISMATCH")
        try:
            self._source_text = reference_source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MutationBuilderError("REFERENCE_SOURCE_NOT_UTF8") from exc
        self.reference = reference
        self._source_bytes = reference_source_bytes
        self._specs = {spec.mutation_id: spec for spec in MUTATION_SPECS}

    def build_all(self) -> dict[str, MutationFixtureV1]:
        return {mutation_id: self.build(mutation_id) for mutation_id in sorted(self._specs)}

    def build(self, mutation_id: str) -> MutationFixtureV1:
        spec = self._specs.get(mutation_id)
        if spec is None:
            raise MutationBuilderError(f"UNKNOWN_MUTATION_ID:{mutation_id}")

        source = self._source_text
        extra: dict[str, bytes] = {}
        anchor_override: dict[str, str] | None = None
        authority_override: str | None = None
        commitment_override: dict[str, str] | None = None

        if mutation_id == "MUT_00":
            pass
        elif mutation_id == "MUT_01":
            source = self._replace_carrier_rhs("CR_of_Q O0RealsV1 0%Q")
        elif mutation_id == "MUT_02":
            base = "CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x)"
            source = self._replace_carrier_rhs(f"CRopp O0RealsV1 ({base})")
        elif mutation_id == "MUT_03":
            base = "CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x)"
            source = self._replace_carrier_rhs(f"CRplus O0RealsV1 ({base}) ({base})")
        elif mutation_id == "MUT_04":
            base = "CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x)"
            source = self._replace_carrier_rhs(
                f"CRplus O0RealsV1 ({base}) (CR_of_Q O0RealsV1 1%Q)"
            )
        elif mutation_id == "MUT_05":
            source = self._replace_once(
                "  - apply CRmorph_rat.",
                "  - change CReq O0RealsV1 (CR_of_Q O0RealsV1 0%Q) (CR_of_Q O0RealsV1 q).\n"
                "    apply CRle_antisym. split; apply CRle_refl.",
                "RATIONAL_MUTATION_ANCHOR_NOT_FOUND",
            )
        elif mutation_id == "MUT_06":
            source = self._replace_once(
                "       x y Hxy).",
                "       y x Hxy).",
                "ORDER_MUTATION_ANCHOR_NOT_FOUND",
            )
        elif mutation_id == "MUT_07":
            source += "\nAxiom AVD_MUT_07 : False.\n"
        elif mutation_id == "MUT_08":
            source += "\nParameter AVD_MUT_08 : Prop.\n"
        elif mutation_id == "MUT_09":
            source += "\nTheorem AVD_MUT_09 : True.\nProof. Admitted.\n"
        elif mutation_id == "MUT_10":
            extra[
                "sovereign-omega-v2/formal/tests/Weil/CornO0MorphismBridgeSpec.v"
            ] = b"(* AVD MUT_10 unauthorized frozen-spec drift *)\n"
        elif mutation_id == "MUT_11":
            extra[
                "sovereign-omega-v2/formal/theories/Weil/shadow/CornO0MorphismBridge.v"
            ] = self._source_bytes
        elif mutation_id == "MUT_12":
            anchor_override = {
                "commit_sha": "f" * 40,
                "tree_sha": self.reference.tree_sha,
            }
        elif mutation_id == "MUT_13":
            authority_override = "FORMAL_MATH_EVIDENCE_ONLY"
        elif mutation_id == "MUT_14":
            commitment_override = {
                "h_verifier": "0" * 64,
                "h_oracle": "f" * 64,
            }
        elif mutation_id == "MUT_15":
            source = self._alpha_refactor_carrier_binder()
        else:  # pragma: no cover - manifest/build dispatch must remain exhaustive
            raise MutationBuilderError(f"UNIMPLEMENTED_MUTATION_ID:{mutation_id}")

        return MutationFixtureV1(
            mutation_id=spec.mutation_id,
            mutation_class=spec.mutation_class.value,
            expected_decision=spec.expected_decision,
            candidate_source_bytes=source.encode("utf-8"),
            extra_files=MappingProxyType(dict(sorted(extra.items()))),
            anchor_override=(MappingProxyType(anchor_override) if anchor_override is not None else None),
            authority_override=authority_override,
            commitment_override=(
                MappingProxyType(commitment_override) if commitment_override is not None else None
            ),
        )

    def _replace_once(self, old: str, new: str, error: str) -> str:
        count = self._source_text.count(old)
        if count != 1:
            raise MutationBuilderError(f"{error}:count={count}")
        return self._source_text.replace(old, new, 1)

    def _replace_carrier_rhs(self, rhs: str) -> str:
        old = (
            "Definition corn_ir_to_o0_carrier_v1 (x : IR) : O0RealV1 :=\n"
            "  CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x)."
        )
        new = (
            "Definition corn_ir_to_o0_carrier_v1 (x : IR) : O0RealV1 :=\n"
            f"  {rhs}."
        )
        return self._replace_once(old, new, "CARRIER_MUTATION_ANCHOR_NOT_FOUND")

    def _alpha_refactor_carrier_binder(self) -> str:
        old = (
            "Definition corn_ir_to_o0_carrier_v1 (x : IR) : O0RealV1 :=\n"
            "  CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x)."
        )
        new = (
            "Definition corn_ir_to_o0_carrier_v1 (x_avd : IR) : O0RealV1 :=\n"
            "  CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x_avd)."
        )
        return self._replace_once(old, new, "ALPHA_REFACTOR_ANCHOR_NOT_FOUND")
