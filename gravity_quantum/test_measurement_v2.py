#!/usr/bin/env python3
import unittest

from gravity_quantum.measurement_v2 import (
    ARXIV_V4_SOURCE,
    build_measurement_receipt,
    cubic_prefactor_identity,
    discriminate_published_models,
    validate_scaled_measurement,
)


def contains_float(value):
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(contains_float(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_float(v) for v in value)
    return False


class TestScaledMeasurementV2(unittest.TestCase):
    def test_receipt_binds_arxiv_v4_and_scaled_integer_observables(self):
        r = build_measurement_receipt()
        self.assertEqual(r["source"]["source_id"], ARXIV_V4_SOURCE)
        self.assertEqual(r["measurements"]["phase_span_millirad"], 80000)
        self.assertEqual(r["measurements"]["blind_residual_basis_points"], 250)
        self.assertEqual(r["measurements"]["relative_phase_noise_basis_points"], 130)
        self.assertEqual(r["apparatus"]["kick_duration_us"], 80)
        self.assertEqual(r["apparatus"]["effective_delay_us"], 77)
        self.assertEqual(r["apparatus"]["effective_g_micrometre_per_s2"], 9910000)
        self.assertEqual(r["apparatus"]["maximum_separation_nm"], 7500)
        self.assertEqual(r["apparatus"]["kick_current_uncertainty_ppm"], 5000)
        self.assertEqual(r["acquisition"]["experimental_cycles"], 633)
        self.assertFalse(contains_float(r))

    def test_float_in_hashed_measurement_is_rejected(self):
        bad = build_measurement_receipt()
        bad["measurements"]["phase_span_rad"] = 80.0
        with self.assertRaises(ValueError):
            validate_scaled_measurement(bad)

    def test_published_cubic_prefactors_are_degenerate_under_levitation(self):
        identity = cubic_prefactor_identity()
        self.assertTrue(identity["degenerate_under_levitation_and_mass_equivalence"])
        self.assertEqual(identity["qgi_normalized_prefactor"], {"numerator": -1, "denominator": 3})
        self.assertEqual(identity["comment_normalized_prefactor"], {"numerator": -1, "denominator": 3})

    def test_model_discrimination_fails_closed_without_point_level_data(self):
        d = discriminate_published_models(build_measurement_receipt())
        self.assertEqual(d["decision"], "NO_UNIQUE_MODEL_SELECTION")
        self.assertEqual(d["authority_effect"], "NONE")
        self.assertIn("NO_POINT_LEVEL_PHASE_DATA", d["reason_codes"])
        self.assertIn("PUBLISHED_MODEL_DEGENERACY", d["reason_codes"])
        self.assertEqual(d["models"]["QGI_GRAVITY_EP"]["status"], "REQUIRES_POINT_LEVEL_REPLAY")
        self.assertEqual(d["models"]["MAGNETIC_RECOIL"]["status"], "REQUIRES_POINT_LEVEL_REPLAY")

    def test_discrimination_declares_minimal_falsification_experiment(self):
        d = discriminate_published_models(build_measurement_receipt())
        interventions = d["next_falsifiers"]
        self.assertIn("BREAK_LEVITATION_DEGENERACY", interventions)
        self.assertIn("INDEPENDENTLY_BIND_MAGNETIC_GRADIENT", interventions)
        self.assertIn("REPLAY_RAW_PHASE_VS_TIME", interventions)
        self.assertIn("PROPAGATE_APPARATUS_SYSTEMATICS", interventions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
