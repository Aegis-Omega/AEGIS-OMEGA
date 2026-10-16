"""Operator-key-sealed offline checkpoint for the existing AEGIS issue token lifecycle.

No wallet, blockchain, network, time oracle, deployment, authority or promotion.
A checkpoint proves consistency with an independently provisioned *local* MAC key;
it only resists deletion/rollback when its ID is retained outside the journal.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Mapping

from agents.evolution_token_lifecycle import canonical, digest, evaluate_lifecycle

SCHEMA = "AEGIS_EVOLUTION_JOURNAL_OPERATOR_CHECKPOINT_V1"
DOMAIN = b"AEGIS:EVOLUTION:OPERATOR_CHECKPOINT:V1\x00"
GENESIS = "0" * 64
FIELDS = frozenset({
    "schema", "spine_receipt", "journal_digest", "observations_digest",
    "event_count", "checkpoint_sequence", "previous_checkpoint_id",
    "as_of", "state_receipt", "checkpoint_key_id", "authority_effect",
    "execution_effect", "signature", "checkpoint_id",
})


def _key(key: bytes) -> None:
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("CHECKPOINT_KEY_INVALID")


def _event_keys_separate(key: bytes, event_keys: Mapping[str, Mapping[str, Any]]) -> None:
    for principal in event_keys.values():
        if isinstance(principal, Mapping) and type(principal.get("secret")) is bytes:
            if hmac.compare_digest(key, principal["secret"]):
                raise ValueError("CHECKPOINT_KEY_REUSES_EVENT_SECRET")


def _observations_digest(events: list[Mapping[str, Any]], observations: list[int]) -> str:
    return digest({"journal_digest": digest(events), "observed_at": observations})


def _unsigned_body(cp: Mapping[str, Any]) -> dict[str, Any]:
    return {k: cp[k] for k in FIELDS - {"checkpoint_id", "signature"}}


def _signature(body: Mapping[str, Any], key: bytes) -> str:
    return hmac.new(key, DOMAIN + canonical(body), hashlib.sha256).hexdigest()


def verify_checkpoint(spine: Mapping[str, Any], events: list[Mapping[str, Any]],
                      observed_at: list[int], checkpoint: Mapping[str, Any], *,
                      trusted_spine_hash: str,
                      trusted_event_keys: Mapping[str, Mapping[str, Any]],
                      trusted_checkpoint_keys: Mapping[str, bytes],
                      trusted_checkpoint_id: str,
                      expected_previous_id: str | None = None) -> dict[str, Any]:
    """Fail closed on any altered journal, observation time, signer or state."""
    if not isinstance(checkpoint, Mapping) or set(checkpoint) != FIELDS:
        raise ValueError("CHECKPOINT_SCHEMA_INVALID")
    cp = checkpoint
    if (cp["schema"] != SCHEMA or cp["authority_effect"] != "NONE"
            or cp["execution_effect"] != "NONE"
            or type(cp["as_of"]) is not int or cp["as_of"] < 0
            or type(cp["event_count"]) is not int or cp["event_count"] < 0
            or type(cp["checkpoint_sequence"]) is not int
            or cp["checkpoint_sequence"] < 0
            or not isinstance(cp["checkpoint_key_id"], str)
            or not isinstance(cp["previous_checkpoint_id"], str)
            or len(cp["previous_checkpoint_id"]) != 64):
        raise ValueError("CHECKPOINT_CONTRACT_INVALID")
    if (not isinstance(trusted_checkpoint_id, str)
            or len(trusted_checkpoint_id) != 64
            or cp["checkpoint_id"] != trusted_checkpoint_id):
        raise ValueError("CHECKPOINT_TRUSTED_ID_MISMATCH")
    if expected_previous_id is not None and cp["previous_checkpoint_id"] != expected_previous_id:
        raise ValueError("CHECKPOINT_PREDECESSOR_MISMATCH")
    key = trusted_checkpoint_keys.get(cp["checkpoint_key_id"])
    if key is None:
        raise ValueError("CHECKPOINT_SIGNER_NOT_TRUSTED")
    _key(key)
    _event_keys_separate(key, trusted_event_keys)
    body = _unsigned_body(cp)
    sig = cp["signature"]
    if (not isinstance(sig, str) or len(sig) != 64
            or not hmac.compare_digest(sig, _signature(body, key))):
        raise ValueError("CHECKPOINT_MAC_INVALID")
    if cp["checkpoint_id"] != digest({**body, "signature": sig}):
        raise ValueError("CHECKPOINT_ID_INVALID")
    if (cp["spine_receipt"] != trusted_spine_hash
            or cp["event_count"] != len(events)
            or cp["journal_digest"] != digest(events)
            or cp["observations_digest"] != _observations_digest(events, observed_at)):
        raise ValueError("CHECKPOINT_DATA_BINDING_INVALID")
    state = evaluate_lifecycle(
        spine, events, trusted_spine_hash=trusted_spine_hash,
        trusted_keys=trusted_event_keys, now=cp["as_of"],
        trusted_journal_digest=cp["journal_digest"],
        trusted_observation_times=observed_at,
        trusted_observations_digest=cp["observations_digest"],
    )
    if state["receipt_hash"] != cp["state_receipt"]:
        raise ValueError("CHECKPOINT_STATE_REPLAY_MISMATCH")
    return {
        "schema": "AEGIS_EVOLUTION_CHECKPOINT_VERDICT_V1",
        "status": "LOCAL_OPERATOR_CHECKPOINT_MAC_VERIFIED",
        "checkpoint_id": cp["checkpoint_id"],
        "event_count": cp["event_count"],
        "revoked_count": sum(bool(x["revoked"]) for x in state["tokens"]),
        "source_publisher_authenticated": False,
        "independent_reviewer_authenticated": False,
        "external_checkpoint_storage_verified": False,
        "authority_effect": "NONE", "execution_effect": "NONE",
        "production_admission": "DENIED", "skill_promotion": "DENIED",
    }


def seal_checkpoint(spine: Mapping[str, Any], events: list[Mapping[str, Any]],
                    observed_at: list[int], *, trusted_spine_hash: str,
                    trusted_event_keys: Mapping[str, Mapping[str, Any]],
                    checkpoint_key_id: str, checkpoint_secret: bytes,
                    as_of: int, prior_checkpoint: Mapping[str, Any] | None = None,
                    prior_events: list[Mapping[str, Any]] | None = None,
                    prior_observed_at: list[int] | None = None,
                    trusted_prior_checkpoint_id: str | None = None) -> dict[str, Any]:
    """Sign an append-only snapshot. Caller must pin checkpoint_id separately."""
    _key(checkpoint_secret)
    _event_keys_separate(checkpoint_secret, trusted_event_keys)
    if not isinstance(checkpoint_key_id, str) or not checkpoint_key_id.isidentifier():
        raise ValueError("CHECKPOINT_KEY_ID_INVALID")
    if type(as_of) is not int or as_of < 0:
        raise ValueError("CHECKPOINT_TIME_INVALID")
    if prior_checkpoint is None:
        if (prior_events is not None or prior_observed_at is not None
                or trusted_prior_checkpoint_id not in (None, GENESIS)):
            raise ValueError("CHECKPOINT_PRIOR_INCOMPLETE")
        previous_id, seq = GENESIS, 0
    else:
        if (not isinstance(prior_events, list) or not isinstance(prior_observed_at, list)
                or not isinstance(trusted_prior_checkpoint_id, str)):
            raise ValueError("CHECKPOINT_PRIOR_UNANCHORED")
        verify_checkpoint(
            spine, prior_events, prior_observed_at, prior_checkpoint,
            trusted_spine_hash=trusted_spine_hash,
            trusted_event_keys=trusted_event_keys,
            trusted_checkpoint_keys={checkpoint_key_id: checkpoint_secret},
            trusted_checkpoint_id=trusted_prior_checkpoint_id,
        )
        if (events[:len(prior_events)] != prior_events
                or observed_at[:len(prior_observed_at)] != prior_observed_at
                or len(events) <= len(prior_events)
                or as_of < prior_checkpoint["as_of"]
                or any(t < prior_checkpoint["as_of"] for t in observed_at[len(prior_observed_at):])):
            raise ValueError("CHECKPOINT_APPEND_ONLY_VIOLATION")
        previous_id = trusted_prior_checkpoint_id
        seq = prior_checkpoint["checkpoint_sequence"] + 1
    jd = digest(events)
    od = _observations_digest(events, observed_at)
    state = evaluate_lifecycle(
        spine, events, trusted_spine_hash=trusted_spine_hash,
        trusted_keys=trusted_event_keys, now=as_of,
        trusted_journal_digest=jd, trusted_observation_times=observed_at,
        trusted_observations_digest=od,
    )
    body = {
        "schema": SCHEMA, "spine_receipt": trusted_spine_hash,
        "journal_digest": jd, "observations_digest": od,
        "event_count": len(events), "checkpoint_sequence": seq,
        "previous_checkpoint_id": previous_id, "as_of": as_of,
        "state_receipt": state["receipt_hash"],
        "checkpoint_key_id": checkpoint_key_id,
        "authority_effect": "NONE", "execution_effect": "NONE",
    }
    sig = _signature(body, checkpoint_secret)
    return {**body, "signature": sig, "checkpoint_id": digest({**body, "signature": sig})}
