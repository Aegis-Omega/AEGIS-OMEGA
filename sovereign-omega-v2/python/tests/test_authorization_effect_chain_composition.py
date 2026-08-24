#!/usr/bin/env python3
"""Composition boundary for current authorization -> verified external effect.

RED-first contract: the effect chain already exists on this branch, but the
current-transition authorization bridge from PR #297 has not yet been transplanted.
The final GREEN test must consume the *same nominal DecisionReceipt* verified by
current authorization-time evidence; no replacement receipt type is permitted.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.authorization_transition_bridge import CurrentTransitionAuthorization  # noqa: E402
from harness.sdk.complete_verifier import CompleteVerifier  # noqa: E402
from harness.sdk.transition_receipts import (  # noqa: E402
    DecisionReceipt,
    pr1_verifier_policy_commitment,
    verifier_policy_commitment,
)


class AuthorizationEffectChainCompositionBoundaryTests(TestCase):
    def test_current_authorization_uses_the_same_nominal_decision_receipt_type(self) -> None:
        annotations = CurrentTransitionAuthorization.__annotations__
        self.assertIs(annotations["decision_receipt"], DecisionReceipt)
        self.assertNotIn("replacement_decision_receipt", annotations)

    def test_effect_chain_policy_is_not_the_legacy_pr1_authorization_policy(self) -> None:
        # A pre-composition PR1-bound authorization must not survive the active
        # PR3 VerifyEffect policy transition. A fresh current authorization is
        # required because verifier-policy commitment is part of tau.
        self.assertNotEqual(pr1_verifier_policy_commitment(), verifier_policy_commitment())

    def test_complete_verifier_remains_the_existing_effect_bundle_verifier(self) -> None:
        self.assertTrue(callable(CompleteVerifier().verify_complete))


if __name__ == "__main__":
    main()
