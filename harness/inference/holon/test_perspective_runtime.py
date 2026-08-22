import json
import unittest

import torch

import holon_llm_inference as h
import perspective as p


class PerspectiveRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = h.ByteTokenizer()
        torch.manual_seed(11)
        self.cfg = h.ModelConfig(
            vocab_size=self.tokenizer.vocab_size,
            d_model=32,
            n_layers=2,
            n_heads=4,
            d_ff=64,
            max_seq_len=32,
        )
        self.model = h.HolonLLM(self.cfg).eval()
        self.probe = p.PerspectiveProbeV1(
            d_model=self.cfg.d_model,
            projection_dim=8,
            perspective_id="MYTHOS_PERSPECTIVE_V1",
            tolerance=1e-8,
        )

    def test_forward_with_perspective_observes_embedding_and_every_layer(self):
        ids = torch.tensor([[self.tokenizer.BOS, ord("x")]], dtype=torch.long)
        logits, cache, layer_trace, perspective_trace = self.model.forward_with_perspective(
            ids,
            perspective_probe=self.probe,
            past_kv=None,
            use_cache=True,
            return_trace=True,
        )

        self.assertEqual(tuple(logits.shape), (1, 2, self.cfg.vocab_size))
        self.assertEqual(len(cache), self.cfg.n_layers)
        self.assertEqual(len(layer_trace), self.cfg.n_layers)
        self.assertEqual(
            [frame.label for frame in perspective_trace.frames],
            ["embedding", "layer:0", "layer:1"],
        )
        self.assertEqual(len(perspective_trace.transitions), self.cfg.n_layers)
        self.assertTrue(all(t.transition_preserved for t in perspective_trace.transitions))

    def test_perspective_is_observation_only_and_does_not_change_logits(self):
        ids = torch.tensor([[self.tokenizer.BOS, ord("x")]], dtype=torch.long)
        baseline_logits, _, _ = self.model(
            ids,
            past_kv=None,
            use_cache=False,
            return_trace=True,
        )
        observed_logits, _, _, _ = self.model.forward_with_perspective(
            ids,
            perspective_probe=self.probe,
            past_kv=None,
            use_cache=False,
            return_trace=True,
        )

        self.assertTrue(torch.equal(baseline_logits, observed_logits))

    def test_runtime_receipts_perspective_trace_for_each_sampling_step(self):
        runtime = h.HolonInferenceRuntime(
            self.model,
            self.tokenizer,
            device="cpu",
            perspective_probe=self.probe,
        )
        _, receipt = runtime.generate(
            "x",
            h.InferencePolicy(
                max_new_tokens=2,
                temperature=0.8,
                top_k=8,
                max_context=32,
                seed=17,
            ),
        )

        self.assertTrue(receipt.perspective_enabled)
        self.assertEqual(len(receipt.trajectory), receipt.generated_tokens)
        for step in receipt.trajectory:
            self.assertIsNotNone(step.perspective_trace)
            self.assertEqual(step.perspective_trace.mode, "OBSERVATION_ONLY")
            self.assertEqual(
                step.perspective_trace.epistemic_status,
                "EVIDENCE_ONLY_NOT_AUTHORITY",
            )
            self.assertEqual(len(step.perspective_trace.frames), self.cfg.n_layers + 1)

        body = json.loads(receipt.to_json())
        rendered = receipt.to_json()
        self.assertTrue(body["perspective_enabled"])
        self.assertNotIn("raw_vector", rendered)
        self.assertNotIn("hidden_state", rendered)

    def test_enabling_perspective_does_not_change_generated_output(self):
        policy = h.InferencePolicy(
            max_new_tokens=3,
            temperature=0.8,
            top_k=8,
            max_context=32,
            seed=19,
        )
        baseline_runtime = h.HolonInferenceRuntime(
            self.model,
            self.tokenizer,
            device="cpu",
        )
        observed_runtime = h.HolonInferenceRuntime(
            self.model,
            self.tokenizer,
            device="cpu",
            perspective_probe=self.probe,
        )

        baseline_output, baseline_receipt = baseline_runtime.generate("x", policy)
        observed_output, observed_receipt = observed_runtime.generate("x", policy)

        self.assertEqual(baseline_output, observed_output)
        self.assertEqual(baseline_receipt.output_sha256, observed_receipt.output_sha256)
        self.assertFalse(baseline_receipt.perspective_enabled)
        self.assertTrue(observed_receipt.perspective_enabled)

    def test_perspective_trace_is_replay_stable_for_same_model_prompt_and_seed(self):
        runtime = h.HolonInferenceRuntime(
            self.model,
            self.tokenizer,
            device="cpu",
            perspective_probe=self.probe,
        )
        policy = h.InferencePolicy(
            max_new_tokens=1,
            top_k=8,
            max_context=32,
            seed=23,
        )

        _, first = runtime.generate("x", policy)
        _, second = runtime.generate("x", policy)

        self.assertEqual(
            first.trajectory[0].perspective_trace.trace_digest,
            second.trajectory[0].perspective_trace.trace_digest,
        )


if __name__ == "__main__":
    unittest.main()
