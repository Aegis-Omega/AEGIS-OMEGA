# HOLONNGRAM / AEGIS Ω inference prototype

Status: `EXECUTABLE_PROTOTYPE / EVIDENCE_ONLY / NOT_ADMISSION_AUTHORITY`.

This harness translates the Holon/Space-Intelligence geometry into an executable decoder-only PyTorch inference path:

`Input → Tokenize/Embed → RoPE/Attend → SwiGLU/Transform → Project → Decode → Output`.

The runtime exposes AEGIS plane mappings rather than claiming a new pretrained language model:

- Experience Plane: byte tokenizer + embeddings.
- Control Plane: bounded inference policy.
- Knowledge Plane: incremental KV cache.
- Execution Plane: decoder-only Transformer forward pass.
- Space Intelligence Plane: per-token probability/entropy plus per-layer hidden-state summary trajectory.
- Receipt Plane: input/model/config/output SHA-256 bindings and the inference trajectory.

## Epistemic boundary

The default model weights are randomly initialized. A successful run proves that this tensor/inference pipeline executed and produced the bound receipt. It does **not** establish useful language competence, proposition truth, pretrained-model provenance, or external effect.

Receipts therefore serialize:

- `receipt_kind = INFERENCE_EVIDENCE_RECEIPT_V1`
- `epistemic_status = EVIDENCE_ONLY_NOT_AUTHORITY`

The model digest is domain-separated and binds each state entry's name, dtype, shape, and bytes. Checkpoint loading uses `torch.load(..., weights_only=True)` to avoid generic pickle object deserialization at the ingestion boundary.

## Run

```bash
python -m pip install -r harness/inference/holon/requirements_holon.txt
python harness/inference/holon/holon_llm_inference.py \
  --prompt "Objasni geometriju inteligencije" \
  --max-new-tokens 128 \
  --temperature 0.7 \
  --top-k 40 \
  --receipt inference_receipt.json
```

## Verify

```bash
cd harness/inference/holon
python -m unittest -v test_holon_llm_inference.py
python -m py_compile holon_llm_inference.py
python holon_llm_inference.py \
  --prompt "Objasni geometriju inteligencije" \
  --max-new-tokens 8 \
  --temperature 0.7 \
  --top-k 40 \
  --receipt /tmp/holon-inference-receipt.json
```

The tests specifically falsify three dangerous upgrades: tensor shape cannot be omitted from model identity, checkpoint loading cannot silently fall back to unrestricted pickle loading, and an inference receipt cannot present itself as authority.

## Pretrained-model next step

Direct loading of Llama, Qwen, or Gemma checkpoints into `HolonLLM` is **NOT_ESTABLISHED**. Those families differ in tokenizer vocabulary, tensor names/shapes, attention topology (including GQA/MQA variants), normalization details, RoPE variants/scaling, embedding/head tying, and configuration semantics.

The next implementation slice should therefore add explicit provider/model adapters and conformance tests instead of pretending that a raw `state_dict` is architecture-compatible. Space Intelligence should then be evaluated as an operator over observed hidden-state geometry, attention/KV trajectories, and uncertainty—not as a semantic metaphor and not as an authority source.

## Stack boundary

This experiment is intentionally downstream of PR #290 exact head `052135fe79b58cb49ec026865dc8d8997a343799`. It does not repair, bypass, or satisfy PR #290's unresolved CodeQL admission gate, and it provides no authority to promote or restack PR #291.
