#!/usr/bin/env python3
"""The notation is bound to the kernel, and plausibility cannot reach authority."""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk import thread_manifold_contract as tmc  # noqa: E402
from harness.sdk.quantummanifold_scheduler import (  # noqa: E402
    DispatchProposalV1,
    QuantumManifoldError,
    canonical_proposal_bytes,
)

SHA = "a" * 40
DIGEST = "b" * 64


def proposal(**overrides) -> DispatchProposalV1:
    base = dict(
        receipt_kind="AEGIS_QUANTUMMANIFOLD_DISPATCH_PROPOSAL_V1",
        baseline_digest=DIGEST,
        source_head_sha=SHA,
        reality_snapshot_digest=DIGEST,
        obligation_set_digest=DIGEST,
        candidate_set_digest=DIGEST,
        scheduler_policy_digest=DIGEST,
        selected_action_digest=DIGEST,
        information_gain_ppm=0,
        closure_leverage_ppm=0,
        falsification_value_ppm=0,
        cost_ppm=0,
        ranking_score_ppm=0,
        recommended_role="BUILDER",
    )
    base.update(overrides)
    return DispatchProposalV1(**base)


class BindingResolutionTests(TestCase):
    def test_every_source_bound_symbol_resolves_against_the_live_kernel(self) -> None:
        # The contract claims each symbol denotes a real type or field. Naming is
        # cheap; this is the part that costs something.
        self.assertEqual(tmc.unresolved_bindings(), [])

    def test_a_binding_that_names_a_missing_field_is_reported(self) -> None:
        # Positive control: without this, the test above would also pass against
        # a resolver that never reports anything.
        contract = tmc.load_contract()
        contract["bindings"].append(
            {
                "symbol": "invented",
                "status": tmc.SOURCE_BOUND,
                "module": "harness.sdk.quantummanifold_scheduler",
                "type": "RealityThreadV1",
                "field": "no_such_field",
                "plane": "plausibility",
            }
        )
        self.assertEqual(tmc.unresolved_bindings(contract), ["invented"])

    def test_derived_notation_is_declared_derived_and_is_really_absent(self) -> None:
        # The contract says these strings do not appear in the sources of record.
        # Check that rather than take its word: a DERIVED row that quietly became
        # source-bound, or a claim of absence that was never true, is the defect.
        contract = tmc.load_contract()
        sources = [
            REPO_ROOT / "harness" / "sdk" / "quantummanifold_scheduler.py",
            REPO_ROOT / "docs" / "specs" / "QUANTUMMANIFOLD_SCHEDULER_SPEC_V1.md",
            REPO_ROOT / "docs" / "specs" / "QUANTUMMANIFOLD_SCHEDULER_PHASE1_DELTA_V1.md",
        ]
        corpus = "\n".join(p.read_text(encoding="utf-8") for p in sources if p.is_file())
        self.assertTrue(corpus, "no source of record was readable")
        for row in contract["derived_formalizations"]:
            with self.subTest(symbol=row["symbol"]):
                self.assertEqual(row["status"], tmc.DERIVED_FORMALIZATION)
                self.assertFalse(row["found_in_source"])
        # The name is source-bound; the geometry is not. Asserting the presence
        # of one is what keeps the absence of the others from passing against an
        # empty or unread corpus.
        self.assertIn("QuantumManifold", corpus)
        for needle in (
            "\U0001d514",
            "|Ψ⟩",
            "g_P",
            "g_A",
            "Ê_k",
            "P̂",
            "Hilbert",
            "superposition",
        ):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, corpus)

    def test_a_symbol_is_never_both_bound_and_derived(self) -> None:
        contract = tmc.load_contract()
        bound = {b["symbol"] for b in contract["bindings"]}
        self.assertEqual(bound & tmc.derived_symbols(contract), set())


class AuthoritySeparationTests(TestCase):
    """RED: nothing the scheduler optimises may move the authority plane."""

    def test_authority_fields_are_not_constructor_parameters(self) -> None:
        by_name = {f.name: f for f in dataclasses.fields(DispatchProposalV1)}
        for field in tmc.load_contract()["authority_plane"]["fields"]:
            with self.subTest(field=field):
                self.assertIn(field, by_name)
                self.assertFalse(by_name[field].init)

    def test_extreme_plausibility_never_moves_the_authority_plane(self) -> None:
        # Sweep the plane the scheduler is allowed to maximise, including the
        # values an optimiser would drift toward, and assert the other plane
        # does not follow.
        extremes = (0, 1, 1_000_000, 9_007_199_254_740_991)
        for value in extremes:
            for field in (
                "information_gain_ppm",
                "closure_leverage_ppm",
                "falsification_value_ppm",
                "ranking_score_ppm",
                "cost_ppm",
            ):
                with self.subTest(field=field, value=value):
                    candidate = proposal(**{field: value})
                    self.assertEqual(tmc.authority_plane_violations(candidate), [])
                    self.assertEqual(candidate.authority_effect, "NONE")
                    self.assertFalse(candidate.can_admit_claim)
                    self.assertFalse(candidate.can_advance_authority)
                    # An intact proposal still serialises: the guard refuses
                    # tunneling, not ordinary ranking.
                    self.assertTrue(canonical_proposal_bytes(candidate))

    def test_forcing_the_authority_plane_is_refused_not_ranked(self) -> None:
        # The adversarial case. init=False stops a caller; it does not stop
        # object.__setattr__ on a frozen dataclass. What must hold is that the
        # canonical path refuses such a proposal instead of scoring it.
        for field, forced in (
            ("authority_effect", "ADMIT"),
            ("can_admit_claim", True),
            ("can_advance_authority", True),
        ):
            with self.subTest(field=field):
                tunneled = proposal()
                object.__setattr__(tunneled, field, forced)
                self.assertEqual(tmc.authority_plane_violations(tunneled), [field])
                with self.assertRaises(tmc.ThreadManifoldContractError) as raised:
                    tmc.refuse_if_tunneled(tunneled)
                self.assertEqual(raised.exception.reason_code, tmc.TUNNELING)
                with self.assertRaises(QuantumManifoldError) as kernel_raised:
                    canonical_proposal_bytes(tunneled)
                self.assertEqual(kernel_raised.exception.reason_code, tmc.TUNNELING)

    def test_no_plausibility_symbol_is_filed_under_authority(self) -> None:
        for symbol in ("gamma", "alpha", "plausibility", "falsification", "information_gain"):
            with self.subTest(symbol=symbol):
                self.assertEqual(tmc.plane_of(symbol), "plausibility")
        for symbol in ("authority", "lineage", "exact_head"):
            with self.subTest(symbol=symbol):
                self.assertEqual(tmc.plane_of(symbol), "authority")

    def test_contract_itself_declares_zero_authority(self) -> None:
        contract = tmc.load_contract()
        self.assertEqual(contract["authority_effect"], "NONE")
        self.assertEqual(contract["separation_invariant"], "PLAUSIBILITY_IS_NOT_AUTHORITY")
        self.assertIn("admits no claim", " ".join(contract["non_claims"]))


if __name__ == "__main__":
    main()
