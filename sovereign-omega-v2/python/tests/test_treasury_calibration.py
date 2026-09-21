#!/usr/bin/env python3
"""Tests for post-settlement HD treasury calibration."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.treasury_calibration import (  # noqa: E402
    MICROS,
    calibrate_treasury_outcome,
    hallucination_delta_micros,
)
from harness.sdk.sovereign_execution import SovereignExecutionError  # noqa: E402

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64


class TreasuryCalibrationTests(TestCase):
    def record(self, **changes):
        values = dict(
            authority_decision_root=H1,
            transfer_plan_root=H2,
            settlement_reference_root=H3,
            claimed_correctness_micros=900_000,
            actual_correctness_micros=1_000_000,
            outcome_label="CONFIRMED_RECONCILED",
        )
        values.update(changes)
        return calibrate_treasury_outcome(**values)

    def test_hd_matches_historical_absolute_gap_definition(self) -> None:
        self.assertEqual(hallucination_delta_micros(900_000, 1_000_000), 100_000)
        self.assertEqual(hallucination_delta_micros(200_000, 0), 200_000)

    def test_record_is_post_settlement_only_and_non_authoritative(self) -> None:
        record = self.record()
        self.assertEqual(record.hd_micros, 100_000)
        self.assertEqual(record.authority_effect, "NONE")
        self.assertEqual(record.scope, "POST_SETTLEMENT_CALIBRATION_ONLY")
        self.assertEqual(len(record.root), 64)

    def test_probability_range_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "claimed_correctness_micros:OUT_OF_RANGE"):
            self.record(claimed_correctness_micros=MICROS + 1)

    def test_wrong_hd_cannot_be_injected(self) -> None:
        record = self.record()
        with self.assertRaisesRegex(SovereignExecutionError, "TREASURY_CALIBRATION_HD_MISMATCH"):
            replace(record, hd_micros=0).validate()

    def test_calibration_cannot_gain_authority(self) -> None:
        record = self.record()
        with self.assertRaisesRegex(SovereignExecutionError, "TREASURY_CALIBRATION_AUTHORITY_EFFECT_INVALID"):
            replace(record, authority_effect="GRANT").validate()


if __name__ == "__main__":
    main()
