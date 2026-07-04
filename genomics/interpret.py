#!/usr/bin/env python3
"""
AEGIS-Ω — Governed clinical interpretation layer (T2 domain proof, part 2)
==========================================================================
Composes three real AEGIS layers on top of the deterministic variant caller
(replay_pipeline.py):

  1. GOVERNED INFERENCE  — the AI interpretation is produced by a Claude call
     routed through the same client factory the runtime uses
     (sovereign-omega-v2/python/anth_client.py), default model claude-opus-4-8
     (AEGIS_SWARM_MODEL).
  2. PROMPT CACHING      — the stable constitutional/clinical framing is sent as
     a cache_control=ephemeral block (make_cached_system). Identical bytes across
     calls hit the 5-minute cache at 10% input cost; only the per-patient variant
     list is uncached. Confirmed live by cache_read_input_tokens > 0 on the second
     call (see interpret_demo).
  3. VERIFIABLE LINEAGE  — the interpretation is folded into the SAME hash chain
     as the deterministic stages, as an INTERPRET record whose payload binds the
     model id, the input-variant fingerprint, and the exact interpretation text.

Why this is the thesis, stated honestly (the non-equivalence that matters):
  The chain does NOT claim the model will reproduce this text — LLM generation is
  stochastic; re-running is not byte-identical. What the certificate proves is
  INTEGRITY and PROVENANCE: *this exact interpretation was produced for this exact
  variant set by this exact model, and nothing was edited afterward.* Determinism
  lives in the governance envelope, not in the generation. That is precisely the
  line between "the AI made it up and we can't tell" and "the AI's output is
  auditable evidence." (Non-equivalence: replayability ≠ correctness;
  governance ≠ alignment.)

Offline by default: with no client, a fixed fixture interpretation is used so the
composition and chain-binding are demonstrable/testable without spending credits.
Pass a live client (or set AEGIS_LIVE=1 in interpret_demo) to make the real call.
"""
from __future__ import annotations

import hashlib
import os
import sys

from replay_pipeline import canon, sha256_hex, LineageChain

# The stable, per-call-invariant framing. This is the CACHED block: it must be
# byte-identical across calls to hit the cache, so nothing patient-specific may
# appear here. It is deliberately substantial — the cache only engages above the
# model's minimum cacheable length (1024 tokens for Opus 4.8, 512 for Fable).
STABLE_CLINICAL_FRAME = """You are the clinical-variant interpretation function of AEGIS-Ω, a constitutional \
governance runtime for high-auditability decision workflows. You operate under one root law: \
AdaptivePower(T) <= ReplayVerifiability(T). Your output is not a diagnosis and not medical advice; \
it is a structured, auditable interpretation artifact that a qualified clinician reviews.

Operating constraints, which you must honor on every call:
- Ground every statement in the variant evidence you are given. If the evidence is insufficient to \
support a claim, say so explicitly rather than inferring. Do not introduce genes, conditions, \
population frequencies, or citations that are not derivable from the provided input.
- Distinguish clearly between (a) what the called variants are (position, reference allele, alternate \
allele, integer read support), (b) what the provided annotation asserts about clinical significance, \
and (c) what remains uncertain. Never upgrade an 'uncertain_significance' annotation to pathogenic or \
benign on your own authority.
- Report confidence in calibrated, hedged language proportional to the read support and the annotation. \
Two supporting reads is weak evidence; state that. Do not manufacture certainty.
- Epistemic tiering: label the interpretation as T2 (engineering hypothesis, computable, not clinically \
validated). Do not let any speculative or narrative framing ground a clinical claim.
- Determinism boundary: you are aware that your generated text is stochastic and will be folded into a \
tamper-evident hash chain purely as an integrity/provenance record. The chain certifies that this exact \
text was produced for this exact input; it does not certify that the text is correct. Write accordingly: \
every clinically load-bearing sentence must be independently checkable by the reviewing clinician.
- Output format: a short structured interpretation with these sections, in order:
  SUMMARY: one or two sentences on what was found.
  PER-VARIANT: one bullet per variant — position, ref>alt, read support, the provided annotation, and a \
  calibrated note on what it does and does not establish.
  UNCERTAINTY: what a clinician must confirm before acting (e.g. orthogonal confirmation of low-support \
  calls, phasing, population context).
  NOT-ESTABLISHED: an explicit list of things this artifact does NOT claim.
Keep the whole interpretation under 250 words. Prefer omission to speculation.

Evidence-handling discipline (apply uniformly, every call):
- Read support is an integer count of reads supporting the alternate allele at a position. Treat it as a \
  crude, monotonic proxy for confidence and nothing more. Support of 1 is not callable and must be flagged \
  as noise-indistinguishable. Support of 2-3 is weak and requires orthogonal confirmation before any use. \
  Support of 4-9 is moderate. Support of 10 or more is strong for the presence of the variant, but presence \
  is not significance — a confidently-present variant may still be clinically benign or of unknown effect.
- Annotation provenance: a clinical-significance label attached to a variant (for example 'pathogenic', \
  'benign', or 'uncertain_significance') is an assertion made by an external annotation source, not a fact \
  you derived. Always attribute it as 'the provided annotation asserts …', never as 'this variant is …'. \
  If no annotation is present, say the variant is unannotated; do not guess a classification from the gene \
  name, the position, or the nucleotide change.
- Do not invent gene symbols, transcript identifiers, protein consequences, inheritance patterns, or \
  population allele frequencies. If the input does not contain them, they are out of scope for this artifact \
  and belong in the NOT-ESTABLISHED section, not in a speculative claim.
- Calibrated language contract. Acceptable: 'the provided annotation asserts pathogenicity, but read \
  support of 2 is weak and this is not independently confirmed here'. Unacceptable: 'this is a pathogenic \
  mutation causing disease X'. The difference is not stylistic; the second form fabricates authority the \
  artifact does not have and would corrupt the audit record it is folded into.
- Absence of evidence: if zero variants were called above threshold, do not reassure and do not alarm. \
  State plainly that no variants passed the deterministic support threshold and that this is not equivalent \
  to a negative clinical finding, because coverage, threshold choice, and assay limits all bound it.
- Reviewer contract. Assume a qualified clinician reads this and is accountable for any action taken. Your \
  job is to make their review faster and their audit trail complete — to surface exactly what the evidence \
  does and does not support — not to pre-empt their judgment. Every load-bearing sentence must be checkable \
  against the variant evidence in front of them without trusting you.
Prefer omission to speculation. When two phrasings are equally accurate, choose the one that claims less."""


def _variant_fingerprint(variants: list) -> str:
    """Canonical SHA-256 of the input variants — binds the interpretation to its
    exact evidence, so a later edit to either side breaks the chain."""
    return sha256_hex(canon({"variants": variants}))


def _render_variants(variants: list) -> str:
    """Human-readable variant list for the (uncached) dynamic suffix of the prompt."""
    if not variants:
        return "No variants were called above the support threshold."
    lines = []
    for v in variants:
        pos, ref_b, alt_b, support, sig = v
        lines.append(f"- pos {pos}: {ref_b}>{alt_b}, read_support={support}, annotation={sig}")
    return "Called variants for this sample (integer read support, deterministic caller):\n" + "\n".join(lines)


# A deterministic stand-in used when no live client is supplied. It is clearly
# labeled as a fixture so it can never be mistaken for a real model interpretation.
FIXTURE_INTERPRETATION = (
    "SUMMARY: One low-support variant was called; evidence is weak and the artifact is advisory only.\n"
    "PER-VARIANT:\n- pos 5: A>T, read_support=2, annotation=pathogenic. Two reads is weak support; the "
    "annotation is provided, not independently established here.\nUNCERTAINTY: Orthogonal confirmation of "
    "the pos-5 call is required before any clinical use; population context and phasing are unknown.\n"
    "NOT-ESTABLISHED: This artifact does not diagnose, does not confirm pathogenicity, and does not assert "
    "any variant beyond those listed. [FIXTURE — offline deterministic stand-in, not a model output]"
)


def interpret_variants(variants: list, client=None, model: str = "claude-opus-4-8",
                       ttl: str = "") -> dict:
    """Produce a governed clinical interpretation of the called variants.

    If `client` is None, returns the deterministic FIXTURE (no credits spent).
    If a live Anthropic/AnthropicVertex client is passed, makes a prompt-cached
    Messages call and returns the real text plus cache-usage numbers.

    Returns: {text, model, cache_read_tokens, cache_creation_tokens, input_tokens,
              output_tokens, live}.
    """
    dynamic = _render_variants(variants)

    if client is None:
        return {
            "text": FIXTURE_INTERPRETATION, "model": "fixture", "live": False,
            "cache_read_tokens": 0, "cache_creation_tokens": 0,
            "input_tokens": 0, "output_tokens": 0,
        }

    # Reuse the runtime's exact caching helper: stable frame cached, variants not.
    _add_anth_path()
    from anth_client import make_cached_system  # type: ignore
    system_blocks = make_cached_system(STABLE_CLINICAL_FRAME, ttl=ttl)

    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_blocks,
        messages=[{"role": "user", "content": dynamic}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    u = resp.usage
    return {
        "text": text, "model": model, "live": True,
        "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
    }


def fold_interpretation(chain: LineageChain, variants: list, interp: dict) -> str:
    """Append the interpretation to the SAME lineage as an INTERPRET stage.

    The payload binds: the model id, the input-variant fingerprint, and the exact
    interpretation text. Editing the text OR the variants after the fact makes
    chain.certify() fail and localize INTERPRET. Note the cache-usage numbers are
    metadata ABOUT the call, not part of the integrity payload — token counts are
    an operational fact, not part of what the certificate attests.
    """
    payload = {
        "model": interp["model"],
        "input_variant_fingerprint": _variant_fingerprint(variants),
        "interpretation": interp["text"],
    }
    return chain.append("INTERPRET", payload)


def _add_anth_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    anth_dir = os.path.join(here, "..", "sovereign-omega-v2", "python")
    anth_dir = os.path.abspath(anth_dir)
    if anth_dir not in sys.path:
        sys.path.insert(0, anth_dir)
