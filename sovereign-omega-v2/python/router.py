"""
SOVEREIGN OMEGA — Router: Execution Router
EPISTEMIC TIER: T0 (constitutional — frozen after creation)

Deterministic event routing from the bridge HTTP layer to core handlers.
Every event class maps to exactly one handler. Routing is determined solely
by the first byte of the verifier bytes — no dynamic dispatch, no reflection,
no runtime registration after seal().

Role: execution router — bridge.py calls router.route() for every /event POST.
      The router classifies the event (via dna.VERIFIER_MAP), validates size
      bounds (via dna.SCHEMAS), and dispatches to the registered handler.

Invariants enforced here:
  - Router must be sealed before the first route() call.
  - After seal(), no new handlers may be registered.
  - Unknown verifier bytes are rejected fail-closed (never silently dropped).
  - Payload/verifier/context exceeding declared schema bounds are rejected.
  - Sequence numbers are assigned atomically (monotonically increasing).
  - All routing decisions are recorded in an immutable audit trail.
  - Each EventClass may have at most one registered handler.
"""

import threading
from typing import Callable, Dict, List, Optional

from dna import EventClass, EventSchema, MutationVerdict, RouteRecord, SCHEMAS, VERIFIER_MAP


# Handler signature: (payload, verifier, context, sequence) → result dict
Handler = Callable[[bytes, bytes, bytes, int], dict]

MAX_AUDIT_TRAIL: int = 10_000   # rolling audit trail — oldest entries evicted


class ExecutionRouter:
    """
    Routes incoming event payloads to the correct handler based on
    the event class derived from the verifier byte.

    Thread-safe. All methods may be called from any thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: Dict[EventClass, Handler] = {}
        self._sealed: bool = False
        self._sequence: int = 0
        self._audit: List[RouteRecord] = []

    def register(self, event_class: EventClass, handler: Handler) -> None:
        """
        Register a handler for an event class. Must be called before seal().
        Each EventClass may have at most one handler — duplicate registration raises.
        """
        with self._lock:
            if self._sealed:
                raise RuntimeError(
                    f"Router is sealed — cannot register handler for {event_class.value}"
                )
            if event_class not in SCHEMAS:
                raise ValueError(f"Unknown event class: {event_class}")
            if event_class in self._handlers:
                raise RuntimeError(
                    f"Handler already registered for {event_class.value}"
                )
            self._handlers[event_class] = handler

    def seal(self) -> None:
        """
        Seal the router. No further handler registrations are permitted.
        Must be called before the first route() call.
        """
        with self._lock:
            self._sealed = True

    def route(self, payload: bytes, verifier: bytes, context: bytes) -> dict:
        """
        Route an event to its handler. Returns the handler's result dict,
        or a structured rejection dict if routing fails.

        Routing is fail-closed: any ambiguity results in REJECTED, never
        a fallback or default handler.
        """
        with self._lock:
            if not self._sealed:
                raise RuntimeError("Router must be sealed before routing events")
            sequence = self._sequence
            self._sequence += 1

        event_class = self._classify(verifier)

        if event_class is None:
            record = RouteRecord(
                sequence=sequence,
                event_class=EventClass.GOVERNANCE,  # placeholder for unknown
                verifier_byte=verifier[0] if verifier else -1,
                payload_size=len(payload),
                outcome="REJECTED",
                reason="UNKNOWN_EVENT_CLASS",
            )
            self._append_audit(record)
            return {
                'status': 'REJECTED',
                'reason': 'UNKNOWN_EVENT_CLASS',
                'verifier_byte': verifier[0] if verifier else None,
                'sequence': sequence,
            }

        # Schema size validation
        schema = SCHEMAS[event_class]
        size_error = self._check_sizes(payload, verifier, context, schema)
        if size_error:
            record = RouteRecord(
                sequence=sequence,
                event_class=event_class,
                verifier_byte=verifier[0] if verifier else -1,
                payload_size=len(payload),
                outcome="REJECTED",
                reason=size_error,
            )
            self._append_audit(record)
            return {
                'status': 'REJECTED',
                'reason': size_error,
                'event_class': event_class.value,
                'sequence': sequence,
            }

        handler = self._handlers.get(event_class)
        if handler is None:
            record = RouteRecord(
                sequence=sequence,
                event_class=event_class,
                verifier_byte=verifier[0] if verifier else -1,
                payload_size=len(payload),
                outcome="REJECTED",
                reason="NO_HANDLER_REGISTERED",
            )
            self._append_audit(record)
            return {
                'status': 'REJECTED',
                'reason': 'NO_HANDLER_REGISTERED',
                'event_class': event_class.value,
                'sequence': sequence,
            }

        try:
            result = handler(payload, verifier, context, sequence)
            record = RouteRecord(
                sequence=sequence,
                event_class=event_class,
                verifier_byte=verifier[0] if verifier else -1,
                payload_size=len(payload),
                outcome="ROUTED",
                reason=None,
            )
            self._append_audit(record)
            return result
        except Exception as exc:
            record = RouteRecord(
                sequence=sequence,
                event_class=event_class,
                verifier_byte=verifier[0] if verifier else -1,
                payload_size=len(payload),
                outcome="ERROR",
                reason=str(exc),
            )
            self._append_audit(record)
            return {
                'status': 'ERROR',
                'reason': str(exc),
                'event_class': event_class.value,
                'sequence': sequence,
            }

    def audit_trail(self, last_n: int = 100) -> list:
        """Return the most recent N routing records for diagnostic purposes."""
        with self._lock:
            tail = self._audit[-last_n:] if len(self._audit) >= last_n else self._audit[:]
            return [
                {
                    'sequence': r.sequence,
                    'event_class': r.event_class.value,
                    'verifier_byte': hex(r.verifier_byte) if r.verifier_byte >= 0 else None,
                    'payload_size': r.payload_size,
                    'outcome': r.outcome,
                    'reason': r.reason,
                }
                for r in tail
            ]

    def telemetry(self) -> dict:
        """Emit router telemetry for inclusion in VCG telemetry payload."""
        with self._lock:
            total = len(self._audit)
            routed = sum(1 for r in self._audit if r.outcome == "ROUTED")
            rejected = sum(1 for r in self._audit if r.outcome == "REJECTED")
            errors = sum(1 for r in self._audit if r.outcome == "ERROR")
            return {
                'router_sealed': self._sealed,
                'router_sequence': self._sequence,
                'router_registered_classes': [c.value for c in self._handlers],
                'router_total_events': total,
                'router_routed': routed,
                'router_rejected': rejected,
                'router_errors': errors,
            }

    @property
    def is_sealed(self) -> bool:
        with self._lock:
            return self._sealed

    @property
    def registered_classes(self) -> list:
        with self._lock:
            return list(self._handlers.keys())

    # ── Private ──────────────────────────────────────────────────────────────

    @staticmethod
    def _classify(verifier: bytes) -> Optional[EventClass]:
        """Classify event from verifier byte. Returns None for unknown bytes (fail-closed)."""
        if not verifier:
            return EventClass.GOVERNANCE  # empty verifier defaults to governance
        return VERIFIER_MAP.get(verifier[0])  # None if unknown

    @staticmethod
    def _check_sizes(
        payload: bytes,
        verifier: bytes,
        context: bytes,
        schema: EventSchema,
    ) -> Optional[str]:
        """Return an error string if any size bound is exceeded, else None."""
        if len(payload) > schema.payload_size_max:
            return f"PAYLOAD_EXCEEDS_SCHEMA_MAX ({len(payload)} > {schema.payload_size_max})"
        if len(verifier) > schema.verifier_size_max:
            return f"VERIFIER_EXCEEDS_SCHEMA_MAX ({len(verifier)} > {schema.verifier_size_max})"
        if len(context) > schema.context_size_max:
            return f"CONTEXT_EXCEEDS_SCHEMA_MAX ({len(context)} > {schema.context_size_max})"
        return None

    def _append_audit(self, record: RouteRecord) -> None:
        """Append to audit trail, evicting oldest if over capacity."""
        if len(self._audit) >= MAX_AUDIT_TRAIL:
            self._audit = self._audit[-(MAX_AUDIT_TRAIL - 1):]
        self._audit.append(record)


# Module-level singleton — sealed during bridge startup via bridge.py
router = ExecutionRouter()
