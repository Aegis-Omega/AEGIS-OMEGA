"""AEGIS always-on witness representation fabric v1.

Observational only: no gate, router, execution, deployment, or admission authority.
The fabric binds coding, sequence, structural, and declared-meaning projections
to one hash-chained receipt while keeping compact carriers non-authoritative.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import queue
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

SCHEMA = "AEGIS_WITNESS_FABRIC_RECEIPT_V1"
AUTHORITY_EFFECT = "NONE"
FIELD_MODULUS = 101
ZERO_HASH = "0" * 64
ABJAD_ALPHABET = "ابجدهوزحطيكلمنسعفصقرشتثخذضظغ"
CLASSICAL_ABJAD_WEIGHTS = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50,
    60, 70, 80, 90, 100, 200, 300, 400, 500, 600,
    700, 800, 900, 1000,
)
MASHRIQI = dict(zip(ABJAD_ALPHABET, CLASSICAL_ABJAD_WEIGHTS))
_PROFILE_CYCLE = {60: 300, 300: 1000, 1000: 900, 900: 800, 800: 90, 90: 60}
MAGHRIBI = {letter: _PROFILE_CYCLE.get(weight, weight) for letter, weight in MASHRIQI.items()}
AFFINE_POINTS = (0, 1, 35, 100)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_payload_bytes(payload: Any) -> tuple[bytes, str]:
    if isinstance(payload, bytes):
        return payload, "AEGIS_WITNESS_RAW_BYTES_V1"
    if isinstance(payload, (bytearray, memoryview)):
        return bytes(payload), "AEGIS_WITNESS_RAW_BYTES_V1"
    if isinstance(payload, str):
        return payload.encode("utf-8"), "AEGIS_WITNESS_UTF8_V1"
    return _canonical_json_bytes(payload), "AEGIS_WITNESS_JSON_V1"


def encode_bytes_field101(data: bytes) -> list[int]:
    """Lossless base-101 pair encoding: byte b -> (b//101, b%101)."""
    out: list[int] = []
    for b in data:
        out.extend((b // FIELD_MODULUS, b % FIELD_MODULUS))
    return out


def decode_bytes_field101(coeffs: list[int] | tuple[int, ...]) -> bytes:
    if len(coeffs) % 2:
        raise ValueError("field101 byte encoding requires an even coefficient count")
    out = bytearray()
    for i in range(0, len(coeffs), 2):
        q = int(coeffs[i])
        r = int(coeffs[i + 1])
        if not (0 <= q < FIELD_MODULUS and 0 <= r < FIELD_MODULUS):
            raise ValueError("coefficient outside F_101")
        value = q * FIELD_MODULUS + r
        if q > 2 or value > 255:
            raise ValueError("coefficient pair is not a canonical byte encoding")
        out.append(value)
    return bytes(out)


def field101_eval(coeffs: list[int] | tuple[int, ...], point: int) -> int:
    if not (0 <= point < FIELD_MODULUS):
        raise ValueError("evaluation point outside F_101")
    acc = 0
    for coeff in reversed(coeffs):
        c = int(coeff)
        if not (0 <= c < FIELD_MODULUS):
            raise ValueError("coefficient outside F_101")
        acc = (acc * point + c) % FIELD_MODULUS
    return acc


def affine_state(coeffs: list[int] | tuple[int, ...], point: int) -> tuple[int, int, int]:
    return (
        field101_eval(coeffs, point),
        pow(point, len(coeffs), FIELD_MODULUS),
        len(coeffs),
    )


def affine_combine(
    left: tuple[int, int, int],
    right: tuple[int, int, int],
) -> tuple[int, int, int]:
    le, lu, ln = left
    re, ru, rn = right
    return ((le + lu * re) % FIELD_MODULUS, (lu * ru) % FIELD_MODULUS, ln + rn)


def _field101_compact_fingerprint(coeffs: list[int]) -> str:
    """Small algebraic fingerprint. Diagnostic only; collisions are expected."""
    e1 = field101_eval(coeffs, 1)
    e35 = field101_eval(coeffs, 35)
    e100 = field101_eval(coeffs, 100)
    n = len(coeffs) % FIELD_MODULUS
    return base64.urlsafe_b64encode(bytes((e1, e35, e100, n))).decode("ascii").rstrip("=")


def _cryptographic_short_carrier(payload_sha256: str) -> str:
    """72-bit locator derived from the payload digest; still not an authority proof."""
    digest = bytes.fromhex(payload_sha256)
    return base64.urlsafe_b64encode(digest[:9]).decode("ascii").rstrip("=")


def _field101_projection(data: bytes) -> dict[str, Any]:
    coeffs = encode_bytes_field101(data)
    affine = {}
    for point in AFFINE_POINTS:
        e, shift, length = affine_state(coeffs, point)
        affine[str(point)] = {"evaluation": e, "shift": shift, "length": length}
    return {
        "field": "F_101",
        "encoding": "BYTE_QR_PAIR_V1",
        "source_encoding_lossless": True,
        "receipt_projection_reconstructs_source": False,
        "coefficient_count": len(coeffs),
        "affine_points": affine,
        "compact_fingerprint": _field101_compact_fingerprint(coeffs),
        "fingerprint_role": "ALGEBRAIC_DIAGNOSTIC_NOT_LOCATOR",
    }


def abjad_projection(text: str) -> dict[str, Any] | None:
    if not isinstance(text, str):
        return None
    letters = [ch for ch in text if not ch.isspace()]
    if not letters or any(ch not in MASHRIQI for ch in letters):
        return None

    mash_weights = [MASHRIQI[ch] for ch in letters]
    magh_weights = [MAGHRIBI[ch] for ch in letters]
    mash_sum = sum(mash_weights)
    magh_sum = sum(magh_weights)
    common_z10 = mash_sum % 10
    if common_z10 != magh_sum % 10:
        raise AssertionError("cross-profile Z/10 invariant violated")

    coeffs = [weight % FIELD_MODULUS for weight in mash_weights]
    field = {
        "profile": "CLASSICAL_MASHRIQI_WEIGHT_SYMBOL_V1",
        "coefficients": coeffs,
        "evaluation_at_1": field101_eval(coeffs, 1),
        "affine": {},
    }
    for point in AFFINE_POINTS:
        e, shift, length = affine_state(coeffs, point)
        field["affine"][str(point)] = {
            "evaluation": e,
            "shift": shift,
            "length": length,
        }

    canonical_text = "".join(letters)
    return {
        "profile": "ABJAD_CROSS_PROFILE_V1",
        "canonical_letters": letters,
        "canonical_sequence_sha256": _sha256(canonical_text.encode("utf-8")),
        "mashriqi_sum": mash_sum,
        "maghribi_sum": magh_sum,
        "common_z10": common_z10,
        "mashriqi_residues": {
            "mod9": mash_sum % 9,
            "mod12": mash_sum % 12,
            "mod36": mash_sum % 36,
        },
        "maghribi_residues": {
            "mod9": magh_sum % 9,
            "mod12": magh_sum % 12,
            "mod36": magh_sum % 36,
        },
        "field101": field,
        "profile_switch_period": 6,
        "authority_effect": AUTHORITY_EFFECT,
    }


def structure_commitment(
    value: Any,
    *,
    max_nodes: int = 8192,
    max_depth: int = 64,
) -> dict[str, Any]:
    h = hashlib.sha256()
    node_count = 0
    complete = True

    def token(s: str) -> None:
        h.update(s.encode("utf-8"))
        h.update(b"\x00")

    def walk(item: Any, depth: int) -> None:
        nonlocal node_count, complete
        if node_count >= max_nodes:
            complete = False
            token("!NODE_LIMIT")
            return
        if depth > max_depth:
            complete = False
            token("!DEPTH_LIMIT")
            return
        node_count += 1

        if item is None:
            token("null")
        elif isinstance(item, bool):
            token("bool")
        elif isinstance(item, int) and not isinstance(item, bool):
            token("int")
        elif isinstance(item, float):
            token("float")
        elif isinstance(item, str):
            token("str")
        elif isinstance(item, (bytes, bytearray, memoryview)):
            token("bytes")
        elif isinstance(item, list):
            token(f"list:{len(item)}")
            for child in item:
                walk(child, depth + 1)
        elif isinstance(item, tuple):
            token(f"tuple:{len(item)}")
            for child in item:
                walk(child, depth + 1)
        elif isinstance(item, dict):
            entries = sorted(item.items(), key=lambda kv: (type(kv[0]).__name__, str(kv[0])))
            token(f"dict:{len(entries)}")
            for raw_key, child in entries:
                token("key_type:" + type(raw_key).__name__)
                token("key:" + str(raw_key))
                walk(child, depth + 1)
        else:
            token("type:" + type(item).__name__)

    walk(value, 0)
    return {
        "profile": "AEGIS_STRUCTURAL_SHAPE_V1",
        "sha256": h.hexdigest(),
        "node_count": node_count,
        "complete": complete,
        "max_nodes": max_nodes,
        "max_depth": max_depth,
    }


def _meaning_commitment(
    *,
    kind: str,
    payload_sha256: str,
    meaning: dict[str, Any] | None,
    provenance: dict[str, Any] | None,
) -> dict[str, Any]:
    declared = dict(meaning or {})
    prov = dict(provenance or {})
    context_refs = list(declared.get("context_refs", [])) if isinstance(declared.get("context_refs", []), list) else []
    history_refs = list(declared.get("history_refs", [])) if isinstance(declared.get("history_refs", []), list) else []
    ontology = declared.get("ontology")
    claim = declared.get("claim")

    envelope = {
        "kind": kind,
        "payload_sha256": payload_sha256,
        "meaning": declared,
        "provenance": prov,
    }
    return {
        "status": "DECLARED_MEANING_COMMITTED" if meaning else "TYPE_ONLY",
        "ontology": ontology if isinstance(ontology, str) else None,
        "context_refs": [str(x) for x in context_refs],
        "history_refs": [str(x) for x in history_refs],
        "claim_sha256": _sha256(str(claim).encode("utf-8")) if claim is not None else None,
        "provenance_sha256": _sha256(_canonical_json_bytes(prov)),
        "commitment_sha256": _sha256(_canonical_json_bytes(envelope)),
        "truth_status": "NOT_ESTABLISHED_BY_COMMITMENT",
        "authority_effect": AUTHORITY_EFFECT,
    }


def build_receipt(
    *,
    kind: str,
    payload: Any,
    sequence: int,
    prev_receipt_hash: str,
    timestamp_ns: int | None = None,
    meaning: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    if not isinstance(prev_receipt_hash, str) or len(prev_receipt_hash) != 64:
        raise ValueError("prev_receipt_hash must be 64 hex characters")

    payload_bytes, payload_profile = canonical_payload_bytes(payload)
    payload_sha = _sha256(payload_bytes)
    field = _field101_projection(payload_bytes)

    abjad = None
    if isinstance(payload, str):
        abjad = abjad_projection(payload)
    elif isinstance(payload, dict) and isinstance(payload.get("canonical_abjad"), str):
        abjad = abjad_projection(payload["canonical_abjad"])

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "sequence": sequence,
        "timestamp_ns": time.time_ns() if timestamp_ns is None else int(timestamp_ns),
        "kind": str(kind),
        "authority_effect": AUTHORITY_EFFECT,
        "prev_receipt_hash": prev_receipt_hash,
        "payload": {
            "canonicalization": payload_profile,
            "byte_length": len(payload_bytes),
            "sha256": payload_sha,
        },
        "coding": {
            "short_carrier": _cryptographic_short_carrier(payload_sha),
            "carrier_role": "LOOKUP_ONLY_NOT_PROOF",
            "collision_policy": "AMBIGUOUS_FAIL_CLOSED",
            "field101": field,
            "abjad": abjad,
        },
        "structure": structure_commitment(payload),
        "meaning": _meaning_commitment(
            kind=str(kind),
            payload_sha256=payload_sha,
            meaning=meaning,
            provenance=provenance,
        ),
    }
    receipt["receipt_sha256"] = _sha256(_canonical_json_bytes(receipt))
    return receipt


def _validate_receipt_hash(receipt: dict[str, Any]) -> bool:
    actual = receipt.get("receipt_sha256")
    if not isinstance(actual, str) or len(actual) != 64:
        return False
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    return _sha256(_canonical_json_bytes(body)) == actual


class WitnessFabric:
    """Bounded one-writer background receipt fabric."""

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        max_queue: int = 1024,
        recent_limit: int = 256,
    ) -> None:
        if max_queue <= 0 or recent_limit <= 0:
            raise ValueError("queue and recent limits must be positive")
        if path is None:
            env_path = os.environ.get("AEGIS_WITNESS_PATH")
            if env_path:
                path = Path(env_path)
            else:
                checkpoint = os.environ.get("AEGIS_CHECKPOINT_PATH")
                if checkpoint:
                    path = Path(checkpoint).with_name("aegis_witness_v1.jsonl")
                else:
                    path = Path("/tmp/aegis_witness_v1.jsonl")
        self.path = Path(path)
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_queue)
        self._recent: deque[dict[str, Any]] = deque(maxlen=recent_limit)
        self._index_order: deque[tuple[str, str]] = deque()
        self._carrier_index: dict[str, list[str]] = {}
        self._recent_limit = recent_limit
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._next_sequence = 0
        self._terminal_hash = ZERO_HASH
        self._processed = 0
        self._dropped = 0
        self._continuity_intact = True
        self._blocked_reason: str | None = None
        self._last_error: str | None = None
        self._tail_recovered = False
        self._history_replay_verified = False
        self._recovered_receipts = 0

    def _recover_tail(self) -> None:
        """Replay and verify the complete persisted chain before accepting new work."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            self._history_replay_verified = True
            return

        expected_sequence = 0
        expected_prev = ZERO_HASH
        recovered_recent: deque[dict[str, Any]] = deque(maxlen=self._recent_limit)
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line_number, raw_line in enumerate(fh, start=1):
                    if not raw_line.strip():
                        continue
                    receipt = json.loads(raw_line)
                    if receipt.get("schema") != SCHEMA:
                        raise ValueError(f"line {line_number}: unexpected schema")
                    if not _validate_receipt_hash(receipt):
                        raise ValueError(f"line {line_number}: receipt hash mismatch")

                    sequence = int(receipt.get("sequence", -1))
                    if sequence != expected_sequence:
                        raise ValueError(
                            f"line {line_number}: sequence {sequence} != {expected_sequence}"
                        )
                    if receipt.get("prev_receipt_hash") != expected_prev:
                        raise ValueError(
                            f"line {line_number}: prev_receipt_hash mismatch"
                        )

                    expected_prev = str(receipt["receipt_sha256"])
                    expected_sequence += 1
                    recovered_recent.append(receipt)

            self._next_sequence = expected_sequence
            self._terminal_hash = expected_prev
            self._tail_recovered = expected_sequence > 0
            self._history_replay_verified = True
            self._recovered_receipts = expected_sequence

            for receipt in recovered_recent:
                self._recent.append(receipt)
                self._index(receipt)
        except Exception as exc:
            self._continuity_intact = False
            self._history_replay_verified = False
            self._blocked_reason = "PERSISTED_CHAIN_INVALID"
            self._last_error = f"{type(exc).__name__}: {exc}"

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._recover_tail()
            self._running = True
            self._thread = threading.Thread(
                target=self._run,
                name="aegis-witness-fabric-v1",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        with self._lock:
            if not self._running:
                return
            thread = self._thread
        try:
            self._queue.put(None, timeout=max(0.01, timeout))
        except queue.Full:
            with self._lock:
                self._continuity_intact = False
                self._blocked_reason = self._blocked_reason or "STOP_QUEUE_FULL"
            return
        if thread is not None:
            thread.join(timeout=timeout)
        with self._lock:
            self._running = False

    def submit(
        self,
        kind: str,
        payload: Any,
        *,
        meaning: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> bool:
        with self._lock:
            if not self._running or self._blocked_reason is not None:
                return False
        item = (str(kind), payload, meaning, provenance, time.time_ns())
        try:
            self._queue.put_nowait(item)
            return True
        except queue.Full:
            with self._lock:
                self._dropped += 1
                self._continuity_intact = False
                self._blocked_reason = "QUEUE_OVERFLOW"
            return False

    def _persist(self, receipt: dict[str, Any]) -> None:
        line = json.dumps(
            receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
            fh.flush()

    def _index(self, receipt: dict[str, Any]) -> None:
        carrier = receipt["coding"]["short_carrier"]
        digest = receipt["receipt_sha256"]
        bucket = self._carrier_index.setdefault(carrier, [])
        if digest not in bucket:
            bucket.append(digest)
        self._index_order.append((carrier, digest))
        while len(self._index_order) > self._recent_limit:
            old_carrier, old_digest = self._index_order.popleft()
            old_bucket = self._carrier_index.get(old_carrier, [])
            if old_digest in old_bucket:
                old_bucket.remove(old_digest)
            if not old_bucket:
                self._carrier_index.pop(old_carrier, None)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                kind, payload, meaning, provenance, ts = item
                with self._lock:
                    if self._blocked_reason is not None:
                        continue
                    sequence = self._next_sequence
                    prev = self._terminal_hash
                receipt = build_receipt(
                    kind=kind,
                    payload=payload,
                    sequence=sequence,
                    prev_receipt_hash=prev,
                    timestamp_ns=ts,
                    meaning=meaning,
                    provenance=provenance,
                )
                self._persist(receipt)
                with self._lock:
                    self._terminal_hash = receipt["receipt_sha256"]
                    self._next_sequence += 1
                    self._processed += 1
                    self._recent.append(receipt)
                    self._index(receipt)
            except Exception as exc:
                with self._lock:
                    self._continuity_intact = False
                    self._blocked_reason = "WORKER_FAILURE"
                    self._last_error = f"{type(exc).__name__}: {exc}"
            finally:
                self._queue.task_done()

    def wait_idle(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return self._queue.unfinished_tasks == 0

    def resolve_carrier(self, carrier: str) -> dict[str, Any]:
        with self._lock:
            hashes = list(self._carrier_index.get(str(carrier), []))
        if not hashes:
            status = "NOT_FOUND"
        elif len(hashes) == 1:
            status = "RESOLVED"
        else:
            status = "AMBIGUOUS"
        return {
            "status": status,
            "carrier": str(carrier),
            "receipt_hashes": hashes,
            "authority_effect": AUTHORITY_EFFECT,
        }

    def recent(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._lock:
            if limit <= 0:
                return []
            return list(self._recent)[-limit:]

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": "AEGIS_WITNESS_FABRIC_STATUS_V1",
                "running": bool(self._thread and self._thread.is_alive()),
                "path": str(self.path),
                "queue_depth": self._queue.qsize(),
                "processed": self._processed,
                "dropped": self._dropped,
                "next_sequence": self._next_sequence,
                "terminal_hash": self._terminal_hash,
                "continuity_intact": self._continuity_intact,
                "blocked_reason": self._blocked_reason,
                "last_error": self._last_error,
                "tail_recovered": self._tail_recovered,
                "history_replay_verified": self._history_replay_verified,
                "recovered_receipts": self._recovered_receipts,
                "authority_effect": AUTHORITY_EFFECT,
            }
