#!/usr/bin/env python3
"""
HOLONNGRAM / AEGIS Ω — minimal decoder-only LLM inference runtime.

Maps the visual concept into executable components:

Experience Plane  -> tokenization + embeddings
Control Plane     -> inference policy / bounds
Knowledge Plane   -> KV cache
Execution Plane   -> transformer forward pass
Space Intelligence-> per-step trajectory / entropy / layer-state trace
Perspective       -> observation-only hidden-state geometric trace
Receipt Plane     -> hashes + reproducible inference receipt

This is a compact reference runtime, not a pretrained frontier model.
Load trained weights into HolonLLM for useful language generation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from .perspective import PerspectiveProbeV1, PerspectiveTraceV1
except ImportError:
    from perspective import PerspectiveProbeV1, PerspectiveTraceV1


# ---------------------------------------------------------------------
# EXPERIENCE PLANE
# ---------------------------------------------------------------------

class ByteTokenizer:
    """
    Dependency-free tokenizer:
      token ids 0..255 = raw UTF-8 bytes
      BOS = 256
      EOS = 257
    """
    BOS = 256
    EOS = 257
    vocab_size = 258

    def encode(self, text: str, bos: bool = True) -> List[int]:
        ids = list(text.encode("utf-8"))
        return ([self.BOS] if bos else []) + ids

    def decode(self, ids: List[int]) -> str:
        raw = bytes(i for i in ids if 0 <= i <= 255)
        return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------
# CONTROL PLANE
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class InferencePolicy:
    max_new_tokens: int = 64
    temperature: float = 0.8
    top_k: int = 40
    repetition_penalty: float = 1.05
    max_context: int = 512
    seed: int = 7

    def validate(self) -> None:
        if not (1 <= self.max_new_tokens <= 4096):
            raise ValueError("max_new_tokens out of bounds")
        if not (0.0 < self.temperature <= 5.0):
            raise ValueError("temperature out of bounds")
        if not (0 <= self.top_k <= 100000):
            raise ValueError("top_k out of bounds")
        if not (1.0 <= self.repetition_penalty <= 4.0):
            raise ValueError("repetition_penalty out of bounds")
        if self.max_context < 8:
            raise ValueError("max_context too small")


# ---------------------------------------------------------------------
# MODEL CONFIG
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ModelConfig:
    vocab_size: int = 258
    d_model: int = 256
    n_layers: int = 6
    n_heads: int = 8
    d_ff: int = 1024
    max_seq_len: int = 512
    dropout: float = 0.0

    @property
    def head_dim(self) -> int:
        if self.d_model % self.n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")
        return self.d_model // self.n_heads


# ---------------------------------------------------------------------
# ROTARY POSITIONAL EMBEDDING
# ---------------------------------------------------------------------

def rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1, x2 = x[..., ::2], x[..., 1::2]
    return torch.stack((-x2, x1), dim=-1).flatten(-2)


class RotaryEmbedding(nn.Module):
    def __init__(self, dim: int, max_seq_len: int = 4096, base: float = 10000.0):
        super().__init__()
        inv_freq = 1.0 / (
            base ** (torch.arange(0, dim, 2, dtype=torch.float32) / dim)
        )
        t = torch.arange(max_seq_len, dtype=torch.float32)
        freqs = torch.outer(t, inv_freq)
        emb = torch.repeat_interleave(freqs, repeats=2, dim=-1)
        self.register_buffer("cos_cached", emb.cos(), persistent=False)
        self.register_buffer("sin_cached", emb.sin(), persistent=False)

    def forward(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
        positions: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        cos = self.cos_cached[positions].unsqueeze(0).unsqueeze(0)
        sin = self.sin_cached[positions].unsqueeze(0).unsqueeze(0)
        q = q * cos + rotate_half(q) * sin
        k = k * cos + rotate_half(k) * sin
        return q, k


# ---------------------------------------------------------------------
# KNOWLEDGE PLANE: KV CACHE
# ---------------------------------------------------------------------

KV = Tuple[torch.Tensor, torch.Tensor]


# ---------------------------------------------------------------------
# TRANSFORMER LAYER
# ---------------------------------------------------------------------

class CausalSelfAttention(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=False)
        self.proj = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.rope = RotaryEmbedding(cfg.head_dim, cfg.max_seq_len)

    def forward(
        self,
        x: torch.Tensor,
        past_kv: Optional[KV] = None,
        use_cache: bool = True,
    ) -> Tuple[torch.Tensor, Optional[KV]]:
        B, T, C = x.shape
        H, D = self.cfg.n_heads, self.cfg.head_dim

        qkv = self.qkv(x)
        q, k, v = qkv.chunk(3, dim=-1)

        q = q.view(B, T, H, D).transpose(1, 2)
        k = k.view(B, T, H, D).transpose(1, 2)
        v = v.view(B, T, H, D).transpose(1, 2)

        past_len = 0 if past_kv is None else past_kv[0].size(2)
        pos = torch.arange(past_len, past_len + T, device=x.device)
        q, k = self.rope(q, k, pos)

        if past_kv is not None:
            pk, pv = past_kv
            k = torch.cat([pk, k], dim=2)
            v = torch.cat([pv, v], dim=2)

        new_kv = (k, v) if use_cache else None

        q_len = q.size(2)
        k_len = k.size(2)
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(D)

        q_positions = torch.arange(
            k_len - q_len, k_len, device=x.device
        ).unsqueeze(-1)
        k_positions = torch.arange(k_len, device=x.device).unsqueeze(0)
        mask = k_positions > q_positions
        scores = scores.masked_fill(mask.unsqueeze(0).unsqueeze(0), float("-inf"))

        attn = F.softmax(scores, dim=-1)
        y = torch.matmul(attn, v)
        y = y.transpose(1, 2).contiguous().view(B, T, C)

        return self.proj(y), new_kv


class FeedForward(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.w1 = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)
        self.w2 = nn.Linear(cfg.d_ff, cfg.d_model, bias=False)
        self.w3 = nn.Linear(cfg.d_model, cfg.d_ff, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.w2(F.silu(self.w1(x)) * self.w3(x))


class TransformerBlock(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.ln1 = nn.RMSNorm(cfg.d_model)
        self.attn = CausalSelfAttention(cfg)
        self.ln2 = nn.RMSNorm(cfg.d_model)
        self.ffn = FeedForward(cfg)

    def forward(
        self,
        x: torch.Tensor,
        past_kv: Optional[KV] = None,
        use_cache: bool = True,
    ) -> Tuple[torch.Tensor, Optional[KV]]:
        a, kv = self.attn(self.ln1(x), past_kv=past_kv, use_cache=use_cache)
        x = x + a
        x = x + self.ffn(self.ln2(x))
        return x, kv


# ---------------------------------------------------------------------
# EXECUTION PLANE: DECODER-ONLY LLM
# ---------------------------------------------------------------------

class HolonLLM(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.layers = nn.ModuleList([TransformerBlock(cfg) for _ in range(cfg.n_layers)])
        self.norm = nn.RMSNorm(cfg.d_model)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        self.lm_head.weight = self.tok_emb.weight

    def _forward_internal(
        self,
        input_ids: torch.Tensor,
        past_kv: Optional[List[KV]] = None,
        use_cache: bool = True,
        return_trace: bool = False,
        perspective_probe: Optional[PerspectiveProbeV1] = None,
    ):
        x = self.tok_emb(input_ids)
        perspective_states = []
        if perspective_probe is not None:
            perspective_states.append(("embedding", x))

        if past_kv is None:
            past_kv = [None] * len(self.layers)

        new_cache: List[KV] = []
        layer_trace: List[Dict[str, float]] = []

        for i, (layer, cache_i) in enumerate(zip(self.layers, past_kv)):
            x, kv = layer(x, past_kv=cache_i, use_cache=use_cache)
            if use_cache:
                new_cache.append(kv)
            if return_trace:
                layer_trace.append(
                    {
                        "layer": i,
                        "mean": float(x.mean().detach().cpu()),
                        "std": float(x.std().detach().cpu()),
                        "l2": float(x.norm().detach().cpu()),
                    }
                )
            if perspective_probe is not None:
                perspective_states.append((f"layer:{i}", x))

        perspective_trace = None
        if perspective_probe is not None:
            perspective_trace = perspective_probe.observe(perspective_states)

        x = self.norm(x)
        logits = self.lm_head(x)
        return logits, new_cache if use_cache else None, layer_trace, perspective_trace

    def forward(
        self,
        input_ids: torch.Tensor,
        past_kv: Optional[List[KV]] = None,
        use_cache: bool = True,
        return_trace: bool = False,
    ):
        logits, cache, layer_trace, _ = self._forward_internal(
            input_ids,
            past_kv=past_kv,
            use_cache=use_cache,
            return_trace=return_trace,
            perspective_probe=None,
        )
        return logits, cache, layer_trace

    def forward_with_perspective(
        self,
        input_ids: torch.Tensor,
        *,
        perspective_probe: PerspectiveProbeV1,
        past_kv: Optional[List[KV]] = None,
        use_cache: bool = True,
        return_trace: bool = False,
    ):
        if perspective_probe.d_model != self.cfg.d_model:
            raise ValueError("PERSPECTIVE_D_MODEL_MISMATCH")
        return self._forward_internal(
            input_ids,
            past_kv=past_kv,
            use_cache=use_cache,
            return_trace=return_trace,
            perspective_probe=perspective_probe,
        )


# ---------------------------------------------------------------------
# SPACE INTELLIGENCE PLANE
# ---------------------------------------------------------------------

@dataclass
class TrajectoryStep:
    step: int
    token_id: int
    token_text: str
    entropy_bits: float
    max_probability: float
    layer_state: List[Dict[str, float]]
    perspective_trace: Optional[PerspectiveTraceV1] = None


def entropy_bits(probs: torch.Tensor) -> float:
    p = probs.clamp_min(1e-12)
    h = -(p * torch.log2(p)).sum()
    return float(h.detach().cpu())


# ---------------------------------------------------------------------
# RECEIPT / TRACE PLANE
# ---------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def model_hash(model: nn.Module) -> str:
    """Domain-separated hash binding parameter name, dtype, shape, and bytes."""
    h = hashlib.sha256()
    h.update(b"AEGIS_HOLON_MODEL_STATE_V1\x00")
    with torch.no_grad():
        for name, tensor in model.state_dict().items():
            cpu = tensor.detach().cpu().contiguous()
            name_b = name.encode("utf-8")
            dtype_b = str(cpu.dtype).encode("ascii")
            shape_b = json.dumps(list(cpu.shape), separators=(",", ":")).encode("ascii")
            raw = cpu.numpy().tobytes()
            for part in (name_b, dtype_b, shape_b, raw):
                h.update(len(part).to_bytes(8, "big"))
                h.update(part)
    return h.hexdigest()


@dataclass
class InferenceReceipt:
    receipt_kind: str
    epistemic_status: str
    runtime: str
    device: str
    input_sha256: str
    model_sha256: str
    config_sha256: str
    output_sha256: str
    prompt_tokens: int
    generated_tokens: int
    latency_ms: float
    seed: int
    trajectory: List[TrajectoryStep]
    perspective_enabled: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------
# SAMPLING / INFERENCE RUNTIME
# ---------------------------------------------------------------------

class HolonInferenceRuntime:
    def __init__(
        self,
        model: HolonLLM,
        tokenizer: ByteTokenizer,
        device: Optional[str] = None,
        perspective_probe: Optional[PerspectiveProbeV1] = None,
    ):
        self.device = device or (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
        self.model = model.to(self.device).eval()
        self.tokenizer = tokenizer
        if perspective_probe is not None and perspective_probe.d_model != model.cfg.d_model:
            raise ValueError("PERSPECTIVE_D_MODEL_MISMATCH")
        self.perspective_probe = perspective_probe

    def _forward(
        self,
        input_ids: torch.Tensor,
        *,
        past_kv: Optional[List[KV]],
    ):
        if self.perspective_probe is None:
            logits, cache, layer_trace = self.model(
                input_ids,
                past_kv=past_kv,
                use_cache=True,
                return_trace=True,
            )
            return logits, cache, layer_trace, None
        return self.model.forward_with_perspective(
            input_ids,
            perspective_probe=self.perspective_probe,
            past_kv=past_kv,
            use_cache=True,
            return_trace=True,
        )

    @torch.inference_mode()
    def generate(
        self,
        prompt: str,
        policy: InferencePolicy,
    ) -> Tuple[str, InferenceReceipt]:
        policy.validate()
        torch.manual_seed(policy.seed)

        ids = self.tokenizer.encode(prompt, bos=True)
        ids = ids[-min(policy.max_context, self.model.cfg.max_seq_len):]

        input_sha = sha256_bytes(prompt.encode("utf-8"))
        perspective_config = None
        if self.perspective_probe is not None:
            perspective_config = {
                "perspective_id": self.perspective_probe.perspective_id,
                "d_model": self.perspective_probe.d_model,
                "projection_dim": self.perspective_probe.projection_dim,
                "tolerance": self.perspective_probe.tolerance,
                "mode": "OBSERVATION_ONLY",
            }
        cfg_json = json.dumps(
            {
                "model": asdict(self.model.cfg),
                "policy": asdict(policy),
                "perspective": perspective_config,
            },
            sort_keys=True,
        ).encode("utf-8")
        cfg_sha = sha256_bytes(cfg_json)
        mdl_sha = model_hash(self.model)

        input_ids = torch.tensor([ids], dtype=torch.long, device=self.device)

        start = time.perf_counter()
        logits, cache, layer_trace, perspective_trace = self._forward(
            input_ids,
            past_kv=None,
        )

        generated: List[int] = []
        trajectory: List[TrajectoryStep] = []

        for step in range(policy.max_new_tokens):
            next_logits = logits[:, -1, :].clone()

            if generated and policy.repetition_penalty > 1.0:
                seen = torch.tensor(
                    sorted(set(generated)),
                    dtype=torch.long,
                    device=self.device,
                )
                next_logits[:, seen] /= policy.repetition_penalty

            next_logits /= policy.temperature

            if 0 < policy.top_k < next_logits.size(-1):
                topv, _ = torch.topk(next_logits, policy.top_k)
                cutoff = topv[:, -1].unsqueeze(-1)
                next_logits = next_logits.masked_fill(
                    next_logits < cutoff, float("-inf")
                )

            probs = F.softmax(next_logits, dim=-1)
            token = torch.multinomial(probs, num_samples=1)
            token_id = int(token.item())
            generated.append(token_id)

            trajectory.append(
                TrajectoryStep(
                    step=step,
                    token_id=token_id,
                    token_text=self.tokenizer.decode([token_id]),
                    entropy_bits=entropy_bits(probs[0]),
                    max_probability=float(probs.max().detach().cpu()),
                    layer_state=layer_trace,
                    perspective_trace=perspective_trace,
                )
            )

            if token_id == self.tokenizer.EOS:
                break

            logits, cache, layer_trace, perspective_trace = self._forward(
                token,
                past_kv=cache,
            )

            cache_len = cache[0][0].size(2)
            if cache_len >= self.model.cfg.max_seq_len:
                break

        latency_ms = (time.perf_counter() - start) * 1000.0
        output = self.tokenizer.decode(generated)
        output_sha = sha256_bytes(output.encode("utf-8"))

        receipt = InferenceReceipt(
            receipt_kind="INFERENCE_EVIDENCE_RECEIPT_V1",
            epistemic_status="EVIDENCE_ONLY_NOT_AUTHORITY",
            runtime="HOLONNGRAM-AEGIS-INFERENCE-v1",
            device=self.device,
            input_sha256=input_sha,
            model_sha256=mdl_sha,
            config_sha256=cfg_sha,
            output_sha256=output_sha,
            prompt_tokens=len(ids),
            generated_tokens=len(generated),
            latency_ms=latency_ms,
            seed=policy.seed,
            trajectory=trajectory,
            perspective_enabled=self.perspective_probe is not None,
        )
        return output, receipt


# ---------------------------------------------------------------------
# LOADING / CLI
# ---------------------------------------------------------------------

def load_checkpoint(model: HolonLLM, path: Optional[str]) -> None:
    if not path:
        return
    state = torch.load(path, map_location="cpu", weights_only=True)
    if isinstance(state, dict) and "model" in state:
        state = state["model"]
    model.load_state_dict(state, strict=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True)
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--max-new-tokens", type=int, default=64)
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--top-k", type=int, default=40)
    p.add_argument("--receipt", default="inference_receipt.json")
    args = p.parse_args()

    tokenizer = ByteTokenizer()
    cfg = ModelConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=256,
        n_layers=6,
        n_heads=8,
        d_ff=1024,
        max_seq_len=512,
    )

    model = HolonLLM(cfg)
    load_checkpoint(model, args.checkpoint)

    runtime = HolonInferenceRuntime(model, tokenizer)
    policy = InferencePolicy(
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
        max_context=cfg.max_seq_len,
    )

    output, receipt = runtime.generate(args.prompt, policy)

    print(output)
    with open(args.receipt, "w", encoding="utf-8") as f:
        f.write(receipt.to_json())

    print(f"\nreceipt -> {args.receipt}")


if __name__ == "__main__":
    main()
