"""AEGIS Ω — Epistemic Authority Conservation V1.

Derived from the MHP-1 invariant:
authority(derived) <= min(authority(source), verified_transform, applicable_policy).

Authority levels are ordered by increasing operational power.
The meet/min operation ensures every verified transition is non-amplifying.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class AuthorityLevel(IntEnum):
    NONE = 0
    EPISTEMIC = 1
    EXECUTION = 2
    PRODUCTION = 3


@dataclass(frozen=True)
class TransitionGateV1:
    transform_cap: AuthorityLevel
    policy_cap: AuthorityLevel


def step_authority(
    source: AuthorityLevel,
    gate: TransitionGateV1,
) -> AuthorityLevel:
    return AuthorityLevel(
        min(int(source), int(gate.transform_cap), int(gate.policy_cap))
    )


def chain_authority(
    initial: AuthorityLevel,
    gates: tuple[TransitionGateV1, ...],
) -> AuthorityLevel:
    current = initial
    for gate in gates:
        current = step_authority(current, gate)
    return current


def conservation_certificate(
    initial: AuthorityLevel,
    gates: tuple[TransitionGateV1, ...],
) -> dict[str, object]:
    final = chain_authority(initial, gates)
    all_caps = [int(initial)]
    for gate in gates:
        all_caps.extend([int(gate.transform_cap), int(gate.policy_cap)])
    global_meet = min(all_caps) if all_caps else int(initial)
    return {
        "schema": "AEGIS_EPISTEMIC_AUTHORITY_CONSERVATION_V1",
        "initial": initial.name,
        "final": final.name,
        "global_meet": AuthorityLevel(global_meet).name,
        "equals_global_meet": int(final) == global_meet,
        "non_amplifying": int(final) <= int(initial),
        "authority_effect": "NONE",
    }
