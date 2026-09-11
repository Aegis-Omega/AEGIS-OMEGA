#!/usr/bin/env python3
"""
AEGIS-Ω — the domain-agnostic verifiable envelope (T2)
======================================================
Constitutional law: AdaptivePower(T) <= ReplayVerifiability(T)

This is the reusable core the genomics proof (genomics/replay_pipeline.py) inlines
for zero-dependency portability. Promoted here to shared infra so a SECOND domain
can consume the *same* primitive by import — making "the envelope is stage-agnostic"
a fact you can test (see verifiable/test_generality.py, which cross-checks that this
implementation is byte-identical to the genomics inline one), not a claim.

Any pipeline whose intermediate state can be canonicalized — genomics, regulated
decision-audit, materials screening, financial model runs — folds into this chain and
gets: reproducible terminal hash, tamper-evidence with stage localization, and
cross-stage lineage binding. The stages are the only domain-specific part.

Dependency-free: Python standard library only. Canonical profile: aegis-integer-json-v2.
"""
from __future__ import annotations

import hashlib
import json
import copy
from dataclasses import dataclass, field

GENESIS = "0" * 64
CANONICAL_PROFILE = "aegis-integer-json-v2"


# ── Explicit integer-only canonical profile; not a full RFC 8785 implementation ──
def canon(value) -> bytes:
    """Sorted string keys, exact strings, compact UTF-8 and no floats.

    Unicode is not normalized: changing the recorded text must change its hash.
    This local profile does not claim full cross-language RFC 8785 conformance.
    """
    def check(v):
        if v is None or type(v) in (bool, int, str):
            return
        if type(v) is dict:
            for k, item in v.items():
                if type(k) is not str:
                    raise TypeError("hashed object keys must be strings")
                check(item)
        elif type(v) in (list, tuple):
            for x in v:
                check(x)
        else:
            raise TypeError("unsupported type in hashed state")
    check(value)
    s = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
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
            "canonicalization": CANONICAL_PROFILE,
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
        if not isinstance(stage, str) or not stage or not isinstance(output, dict):
            raise ValueError("a stage requires a name and an output object")
        prev = self.records[-1].stage_hash if self.records else GENESIS
        rec = StageRecord(stage=stage, output=copy.deepcopy(output),
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
            if not isinstance(rec, StageRecord):
                return {"is_valid": False, "broken_at": "INVALID_RECORD", "sequence": i}
            expect_prev = prev
            recomputed = StageRecord(rec.stage, rec.output, expect_prev, rec.sequence)
            try:
                recomputed.compute()
            except (TypeError, ValueError, RecursionError):
                return {"is_valid": False, "broken_at": rec.stage, "sequence": i}
            if (type(rec.sequence) is not int or rec.sequence != i or
                    recomputed.stage_hash != rec.stage_hash or rec.previous_hash != expect_prev):
                return {"is_valid": False, "broken_at": rec.stage, "sequence": i}
            prev = rec.stage_hash
        return {"is_valid": True, "broken_at": None, "terminal_hash": self.terminal_hash()}
