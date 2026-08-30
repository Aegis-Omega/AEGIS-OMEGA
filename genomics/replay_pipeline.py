#!/usr/bin/env python3
"""
AEGIS-Ω — Replay-Verifiable Genomics Pipeline (T2 domain proof)
================================================================
Constitutional law: AdaptivePower(T) <= ReplayVerifiability(T)

The clinical problem this addresses: a variant call that cannot be reproduced
byte-for-byte, and whose provenance cannot be proven un-tampered, is not
admissible as a medical-grade result. Standard bioinformatics pipelines are
reproducible only "in spirit" — thread races, hash-map iteration order, and
float non-determinism perturb outputs across runs and machines.

This pipeline applies the SAME primitive the AEGIS runtime uses for governance
(RFC 8785 canonical JSON -> SHA-256, hash-chained lineage) to a genomics
workflow: reference load -> align -> pileup -> variant-call -> annotate.
Every stage output is canonicalized and folded into a tamper-evident chain.

Proven invariants (asserted in tests):
  1. DETERMINISM: replay(same inputs) -> byte-identical terminal hash, 3x.
  2. TAMPER-EVIDENCE: flip one base in one read -> terminal hash changes, and
     certify() localizes the first divergent stage.
  3. CROSS-STAGE LINEAGE: each stage hash binds the previous (a real chain,
     not independent digests) — mirrors src/frame/adaptive-lineage.ts.

Determinism discipline (why this reproduces where others don't):
  - No dict/set iteration in hashed state — sorted keys via RFC 8785.
  - Integer/fixed arithmetic only in the call decision (no float thresholds).
  - Deterministic tie-breaking by (position, ref, alt) lexicographic order.
  - No wall-clock, no RNG, no thread-order dependence.

Dependency-free: Python stdlib only (hashlib, json, unicodedata).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field

GENESIS = "0" * 64


# ── RFC 8785-style canonical serialization (mirrors src/core/canonicalize.ts) ──
def canon(value) -> bytes:
    """Deterministic bytes: sorted keys, NFC strings, no whitespace, UTF-8.
    Rejects float (non-determinism source) — integers and strings only in
    hashed state, exactly as the runtime forbids float in hash inputs."""
    def check(v):
        if isinstance(v, float):
            raise TypeError("float in hashed state is forbidden (non-deterministic)")
        if isinstance(v, dict):
            for k in v:
                check(v[k])
        elif isinstance(v, (list, tuple)):
            for x in v:
                check(x)
    check(value)
    s = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    s = unicodedata.normalize("NFC", s)
    return s.encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@dataclass
class StageRecord:
    stage: str
    output: dict
    previous_hash: str
    sequence: int
    stage_hash: str = ""

    def compute(self) -> str:
        # The chain: this stage's hash binds its output AND the prior hash.
        payload = {
            "stage": self.stage,
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "output": self.output,
        }
        self.stage_hash = sha256_hex(canon(payload))
        return self.stage_hash


@dataclass
class LineageChain:
    records: list = field(default_factory=list)

    def append(self, stage: str, output: dict) -> str:
        prev = self.records[-1].stage_hash if self.records else GENESIS
        rec = StageRecord(stage=stage, output=output,
                          previous_hash=prev, sequence=len(self.records))
        rec.compute()
        self.records.append(rec)
        return rec.stage_hash

    def terminal_hash(self) -> str:
        return self.records[-1].stage_hash if self.records else GENESIS

    def certify(self) -> dict:
        """Re-walk the chain; any tamper flips is_valid False and localizes it."""
        prev = GENESIS
        for i, rec in enumerate(self.records):
            expect_prev = prev
            recomputed = StageRecord(rec.stage, rec.output, expect_prev, rec.sequence)
            recomputed.compute()
            if recomputed.stage_hash != rec.stage_hash or rec.previous_hash != expect_prev:
                return {"is_valid": False, "broken_at": rec.stage, "sequence": i}
            prev = rec.stage_hash
        return {"is_valid": True, "broken_at": None, "terminal_hash": self.terminal_hash()}


# ── The genomics workflow (deterministic by construction) ──
# Toy but structurally faithful: reads are (pos, bases); reference is a string.
# Variant call = positions where >=CALL_MIN_ALT reads disagree with reference,
# decided by integer counts only (no float allele-frequency threshold).

CALL_MIN_ALT = 2  # integer support threshold — deterministic, no float AF


def load_reference(ref: str) -> dict:
    return {"reference": ref, "length": len(ref)}


def align(reads: list) -> dict:
    # Deterministic sort: by (pos, bases). No hashmap order, no thread race.
    aligned = sorted(([r["pos"], r["bases"]] for r in reads),
                     key=lambda x: (x[0], x[1]))
    return {"aligned_reads": aligned, "count": len(aligned)}


def pileup(ref: str, aligned: list) -> dict:
    # Per-position base counts as SORTED lists of [base, count] — never a dict
    # in hashed state (dict iteration order is not guaranteed cross-impl).
    columns = {}
    for pos, bases in aligned:
        for i, b in enumerate(bases):
            p = pos + i
            if p >= len(ref):
                continue
            columns.setdefault(p, {}).setdefault(b, 0)
            columns[p][b] += 1
    piled = []
    for p in sorted(columns):
        counts = sorted([[b, c] for b, c in columns[p].items()], key=lambda x: x[0])
        piled.append([p, ref[p], counts])
    return {"pileup": piled}


def call_variants(ref: str, piled: list) -> dict:
    variants = []
    for p, ref_base, counts in piled:
        for base, count in counts:
            if base != ref_base and count >= CALL_MIN_ALT:
                variants.append([p, ref_base, base, count])
    # Deterministic order: (pos, ref, alt).
    variants.sort(key=lambda v: (v[0], v[1], v[2]))
    return {"variants": variants, "n_variants": len(variants)}


CLINVAR_TOY = {  # (pos, ref, alt) -> significance. Sorted-key canon handles it.
    "5|A|T": "pathogenic",
    "11|C|G": "benign",
}


def annotate(variants: list) -> dict:
    annotated = []
    for pos, ref_b, alt_b, support in variants:
        key = f"{pos}|{ref_b}|{alt_b}"
        annotated.append([pos, ref_b, alt_b, support,
                          CLINVAR_TOY.get(key, "uncertain_significance")])
    return {"annotated_variants": annotated}


def run_pipeline(reference: str, reads: list) -> LineageChain:
    """Full governed pipeline. Returns the hash-chained lineage."""
    chain = LineageChain()
    ref_out = load_reference(reference)
    chain.append("REFERENCE_LOAD", ref_out)

    aln = align(reads)
    chain.append("ALIGN", aln)

    pil = pileup(reference, aln["aligned_reads"])
    chain.append("PILEUP", pil)

    vc = call_variants(reference, pil["pileup"])
    chain.append("VARIANT_CALL", vc)

    ann = annotate(vc["variants"])
    chain.append("ANNOTATE", ann)
    return chain


# A fixed, deterministic sample (a clinician's re-runnable input).
SAMPLE_REFERENCE = "ACGTACGTACGTACGT"
SAMPLE_READS = [
    {"pos": 3, "bases": "TACGT"},
    {"pos": 0, "bases": "ACGTT"},
    {"pos": 5, "bases": "CGTAC"},
    {"pos": 5, "bases": "TGTAC"},   # supports a T at pos 5 (ref A)
    {"pos": 4, "bases": "ATGTA"},   # supports a T at pos 5 again -> >=2
    {"pos": 9, "bases": "CGTAC"},
    {"pos": 2, "bases": "GTACG"},
]


if __name__ == "__main__":
    chain = run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS)
    for rec in chain.records:
        print(f"  {rec.sequence} {rec.stage:16s} {rec.stage_hash[:16]}…")
    print("terminal:", chain.terminal_hash())
    print("certify :", chain.certify()["is_valid"])
