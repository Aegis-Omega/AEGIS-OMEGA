import dataclasses
import unittest

import torch

import perspective as p


class PerspectiveProbeTests(unittest.TestCase):
    def setUp(self):
        self.probe = p.PerspectiveProbeV1(
            d_model=4,
            projection_dim=3,
            perspective_id="MYTHOS_PERSPECTIVE_V1",
            tolerance=1e-6,
        )
        self.states = [
            ("embedding", torch.tensor([[[1.0, 2.0, 3.0, 4.0]]])),
            ("layer:0", torch.tensor([[[1.5, 1.0, 4.0, 3.0]]])),
            ("layer:1", torch.tensor([[[2.0, 0.5, 5.0, 2.0]]])),
        ]

    def test_four_readings_and_commutative_transition_preservation(self):
        trace = self.probe.observe(self.states)

        self.assertEqual(trace.trace_kind, "PERSPECTIVE_TRACE_V1")
        self.assertEqual(trace.epistemic_status, "EVIDENCE_ONLY_NOT_AUTHORITY")
        self.assertEqual(trace.mode, "OBSERVATION_ONLY")
        self.assertEqual(
            trace.readings,
            (
                "CATEGORICAL_ALGEBRAIC",
                "FORMAL_TRANSITION_PRESERVATION",
                "FORENSIC_AUDITABILITY",
                "INFORMATION_THEORETIC",
            ),
        )
        self.assertEqual(len(trace.frames), 3)
        self.assertEqual(len(trace.transitions), 2)
        for transition in trace.transitions:
            self.assertLessEqual(transition.commutative_residual_l2, 1e-6)
            self.assertTrue(transition.transition_preserved)
            self.assertGreaterEqual(transition.angle_radians, 0.0)
            self.assertGreaterEqual(transition.delta_l2, 0.0)

    def test_trace_is_deterministic_hash_chained_and_state_sensitive(self):
        first = self.probe.observe(self.states)
        second = self.probe.observe(self.states)
        changed = list(self.states)
        changed[-1] = (
            "layer:1",
            torch.tensor([[[2.0, 0.5, 5.0, 2.25]]]),
        )
        third = self.probe.observe(changed)

        self.assertEqual(first.trace_digest, second.trace_digest)
        self.assertEqual(first.frames[-1].chain_digest, second.frames[-1].chain_digest)
        self.assertNotEqual(first.trace_digest, third.trace_digest)
        self.assertNotEqual(first.frames[-1].state_digest, third.frames[-1].state_digest)

    def test_probe_is_observation_only_and_never_mutates_hidden_state(self):
        originals = [(label, tensor.clone()) for label, tensor in self.states]
        self.probe.observe(self.states)

        for (_, before), (_, after) in zip(originals, self.states):
            self.assertTrue(torch.equal(before, after))

    def test_non_finite_hidden_state_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "NON_FINITE_HIDDEN_STATE"):
            self.probe.observe(
                [
                    ("embedding", torch.tensor([[[1.0, 2.0, 3.0, 4.0]]])),
                    ("layer:0", torch.tensor([[[1.0, float("nan"), 3.0, 4.0]]])),
                ]
            )

    def test_wrong_hidden_dimension_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "HIDDEN_DIMENSION_MISMATCH"):
            self.probe.observe(
                [("embedding", torch.tensor([[[1.0, 2.0, 3.0]]]))]
            )

    def test_receipt_contains_summaries_and_digests_not_raw_hidden_vectors(self):
        trace = self.probe.observe(self.states)
        rendered = repr(dataclasses.asdict(trace))

        self.assertNotIn("hidden_state", rendered)
        self.assertNotIn("raw_vector", rendered)
        self.assertTrue(all(frame.state_digest for frame in trace.frames))
        self.assertTrue(all(frame.projection_digest for frame in trace.frames))
        self.assertTrue(all(frame.energy_entropy_bits >= 0.0 for frame in trace.frames))


if __name__ == "__main__":
    unittest.main()
