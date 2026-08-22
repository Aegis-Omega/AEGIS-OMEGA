import json
import unittest
from unittest import mock

import torch
import torch.nn as nn

import holon_llm_inference as h


class _ShapeModule(nn.Module):
    def __init__(self, shape):
        super().__init__()
        self.register_buffer("x", torch.arange(4, dtype=torch.float32).reshape(shape))


class HolonInferenceEvidenceTests(unittest.TestCase):
    def test_model_hash_binds_tensor_shape(self):
        self.assertNotEqual(
            h.model_hash(_ShapeModule((4,))),
            h.model_hash(_ShapeModule((2, 2))),
        )

    def test_checkpoint_load_is_weights_only(self):
        model = h.HolonLLM(h.ModelConfig())
        with mock.patch.object(h.torch, "load", return_value=model.state_dict()) as load:
            h.load_checkpoint(model, "/tmp/fake.pt")
        load.assert_called_once_with(
            "/tmp/fake.pt", map_location="cpu", weights_only=True
        )

    def test_receipt_declares_evidence_boundary(self):
        tokenizer = h.ByteTokenizer()
        torch.manual_seed(1)
        cfg = h.ModelConfig(
            vocab_size=tokenizer.vocab_size,
            d_model=32,
            n_layers=1,
            n_heads=4,
            d_ff=64,
            max_seq_len=32,
        )
        runtime = h.HolonInferenceRuntime(h.HolonLLM(cfg), tokenizer, device="cpu")
        _, receipt = runtime.generate(
            "x", h.InferencePolicy(max_new_tokens=1, max_context=32, seed=3)
        )
        body = json.loads(receipt.to_json())
        self.assertEqual(body["receipt_kind"], "INFERENCE_EVIDENCE_RECEIPT_V1")
        self.assertEqual(body["epistemic_status"], "EVIDENCE_ONLY_NOT_AUTHORITY")


if __name__ == "__main__":
    unittest.main()
