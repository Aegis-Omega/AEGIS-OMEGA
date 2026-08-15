from __future__ import annotations

import dataclasses
import hashlib
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel

from .types import ChainLayer, ChainStageReceipt, RuntimeErrorCode


class ChainOrderError(RuntimeError):
    pass


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_jsonable(v) for v in value), key=lambda x: json.dumps(x, sort_keys=True))
    return value


def stable_local_digest(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class OmegaChain:
    """Fail-closed staged extension ledger inspired by a Postnikov tower.

    This is an engineering dependency tower, not a claim of mathematical
    equivalence to a topological Postnikov system. Each stage may extend only an
    admitted predecessor and commits typed inputs/outputs by a deterministic local JSON digest.
    This digest profile is not claimed to be RFC 8785/JCS.
    """

    ORDER = tuple(ChainLayer)

    def __init__(self) -> None:
        self._receipts: list[ChainStageReceipt] = []
        self._terminal = False

    @property
    def receipts(self) -> tuple[ChainStageReceipt, ...]:
        return tuple(self._receipts)

    def root_digest(self) -> str | None:
        if not self._receipts:
            return None
        return stable_local_digest([receipt.model_dump(mode="json") for receipt in self._receipts])

    def _require_next(self, layer: ChainLayer) -> None:
        if self._terminal:
            raise ChainOrderError("chain is terminal after a denied stage")
        index = len(self._receipts)
        if index >= len(self.ORDER):
            raise ChainOrderError("chain is already complete")
        expected = self.ORDER[index]
        if layer != expected:
            raise ChainOrderError(f"expected {expected.value}, got {layer.value}")

    def admit(
        self,
        layer: ChainLayer,
        *,
        input_artifact: Any,
        output_artifact: Any,
        evidence_digests: list[str] | None = None,
    ) -> ChainStageReceipt:
        self._require_next(layer)
        receipt = ChainStageReceipt(
            layer=layer,
            admitted=True,
            input_digest=stable_local_digest(input_artifact),
            output_digest=stable_local_digest(output_artifact),
            evidence_digests=list(evidence_digests or []),
        )
        self._receipts.append(receipt)
        return receipt

    def deny(
        self,
        layer: ChainLayer,
        *,
        input_artifact: Any,
        obstruction_code: RuntimeErrorCode | str,
        evidence_digests: list[str] | None = None,
    ) -> ChainStageReceipt:
        self._require_next(layer)
        code = obstruction_code.value if isinstance(obstruction_code, RuntimeErrorCode) else str(obstruction_code)
        receipt = ChainStageReceipt(
            layer=layer,
            admitted=False,
            input_digest=stable_local_digest(input_artifact),
            obstruction_code=code,
            evidence_digests=list(evidence_digests or []),
        )
        self._receipts.append(receipt)
        self._terminal = True
        return receipt
