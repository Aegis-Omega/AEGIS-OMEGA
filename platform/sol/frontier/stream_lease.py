from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


class StreamLeaseError(ValueError):
    pass


@dataclass(frozen=True)
class SSEStreamLease:
    execution_id: str
    owner_identity: str
    generation: int
    fencing_token: str
    last_sequence: int = -1


def _fence(execution_id: str, owner_identity: str, generation: int) -> str:
    if not execution_id or not owner_identity:
        raise StreamLeaseError("execution_id and owner_identity are required")
    if generation < 0:
        raise StreamLeaseError("generation must be non-negative")
    material = f"{execution_id}\x00{owner_identity}\x00{generation}".encode("utf-8")
    return sha256(material).hexdigest()


def open_stream_lease(execution_id: str, owner_identity: str, *, generation: int) -> SSEStreamLease:
    return SSEStreamLease(
        execution_id=execution_id,
        owner_identity=owner_identity,
        generation=generation,
        fencing_token=_fence(execution_id, owner_identity, generation),
        last_sequence=-1,
    )


def verify_stream_event(
    lease: SSEStreamLease,
    *,
    execution_id: str,
    owner_identity: str,
    generation: int,
    fencing_token: str,
    sequence: int,
) -> SSEStreamLease:
    if execution_id != lease.execution_id:
        raise StreamLeaseError("stream event execution_id does not match lease")
    if owner_identity != lease.owner_identity:
        raise StreamLeaseError("stream event owner does not match lease")
    if generation != lease.generation:
        raise StreamLeaseError("stale stream generation")
    if fencing_token != lease.fencing_token:
        raise StreamLeaseError("invalid stream fencing token")
    if sequence != lease.last_sequence + 1:
        raise StreamLeaseError("stream event sequence must advance exactly once")
    return SSEStreamLease(
        execution_id=lease.execution_id,
        owner_identity=lease.owner_identity,
        generation=lease.generation,
        fencing_token=lease.fencing_token,
        last_sequence=sequence,
    )
