#!/usr/bin/env python3
"""Tests for the composite Tameion evidence bundle."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.arc_erc20_call import build_unsigned_transfer_call  # noqa: E402
from harness.sdk.arc_treasury_execution import ARC_USDC_INTERFACE, ArcTransferPlan  # noqa: E402
from harness.sdk.arc_treasury_witness import (  # noqa: E402
    ARC_TESTNET_CHAIN_ID,
    ArcTreasuryWitness,
)
from harness.sdk.notebook_evidence import summarize_notebook_bytes  # noqa: E402
from harness.sdk.sovereign_execution import SCHEMA_VERSION, SovereignExecutionError, ZERO_HASH  # noqa: E402
from harness.sdk.tameion_evidence_chain import build_confirmed_tameion_bundle  # noqa: E402

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
SENDER = "0x" + "11" * 20
DEST = "0x" + "22" * 20
TX = "0x" + "33" * 32


class TameionEvidenceBundleTests(TestCase):
    def plan(self, **changes) -> ArcTransferPlan:
        values = dict(
            schema_version=SCHEMA_VERSION,
            chain_id=ARC_TESTNET_CHAIN_ID,
            network="ARC-TESTNET",
            asset="USDC",
            token_interface=ARC_USDC_INTERFACE,
            sender=SENDER,
            destination=DEST,
            amount_microunits=1_000_000,
            idempotency_key="tameion-bundle-001",
            purpose="verified-milestone-payment",
            authority_decision_root=H1,
            treasury_intent_root=H2,
        )
        values.update(changes)
        return ArcTransferPlan(**values)

    def witness(self, **changes) -> ArcTreasuryWitness:
        values = dict(
            schema_version=SCHEMA_VERSION,
            intent_root=H2,
            settlement_root=H3,
            tx_hash=TX,
            chain_id=ARC_TESTNET_CHAIN_ID,
        )
        values.update(changes)
        return ArcTreasuryWitness(**values)

    def notebook(self):
        raw = json.dumps({
            "nbformat": 4,
            "nbformat_minor": 5,
            "cells": [{"cell_type": "code", "source": ["def calculate_hd(a,b): return abs(a-b)\n"]}],
        }).encode("utf-8")
        return summarize_notebook_bytes(
            raw,
            source_label="demo.ipynb",
            source_locator="private://demo",
        )

    def test_bundle_connects_notebook_plan_call_witness_and_hd(self) -> None:
        plan = self.plan()
        call = build_unsigned_transfer_call(plan)
        bundle, calibration = build_confirmed_tameion_bundle(
            plan=plan,
            unsigned_call=call,
            witness=self.witness(),
            claimed_correctness_micros=900_000,
            notebook=self.notebook(),
        )
        self.assertEqual(calibration.hd_micros, 100_000)
        self.assertNotEqual(bundle.notebook_evidence_root, ZERO_HASH)
        self.assertEqual(bundle.authority_effect, "NONE")
        self.assertEqual(len(bundle.root), 64)

    def test_notebook_is_optional(self) -> None:
        plan = self.plan()
        call = build_unsigned_transfer_call(plan)
        bundle, _ = build_confirmed_tameion_bundle(
            plan=plan,
            unsigned_call=call,
            witness=self.witness(),
            claimed_correctness_micros=1_000_000,
        )
        self.assertEqual(bundle.notebook_evidence_root, ZERO_HASH)

    def test_call_must_bind_exact_plan(self) -> None:
        plan = self.plan()
        other_plan = self.plan(amount_microunits=2_000_000)
        call = build_unsigned_transfer_call(other_plan)
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_BUNDLE_TRANSFER_CALL_MISMATCH"):
            build_confirmed_tameion_bundle(
                plan=plan,
                unsigned_call=call,
                witness=self.witness(),
                claimed_correctness_micros=900_000,
            )

    def test_witness_must_bind_exact_intent(self) -> None:
        plan = self.plan()
        call = build_unsigned_transfer_call(plan)
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_BUNDLE_INTENT_MISMATCH"):
            build_confirmed_tameion_bundle(
                plan=plan,
                unsigned_call=call,
                witness=self.witness(intent_root="4" * 64),
                claimed_correctness_micros=900_000,
            )


if __name__ == "__main__":
    main()
