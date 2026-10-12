"""AEGIS: bounded offline issue-token lifecycle over the EXISTING evolution spine.

This is a *local HMAC-authenticated contract simulation*, not a blockchain,
public-key identity, authority token, scientific proof, or production admission.
No network, persistence, model calls, money, skill/tree mutations, or dispatch.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, Mapping

SCHEMA = "AEGIS_ISSUE_EVOLUTION_TOKEN_LIFECYCLE_V1"
EVENT_SCHEMA = "AEGIS_EVOLUTION_TOKEN_EVENT_V1"
TOKEN_SCHEMA = "AEGIS_INFORMATIONAL_EVOLUTION_TOKEN_V1"
SPINE_SCHEMA = "AEGIS_SOVEREIGN_EVOLUTION_CONTRACT_SPINE_V1"
DOMAIN = b"AEGIS:INFORMATIONAL:ISSUE_TOKEN_LIFECYCLE:V1\x00"
HEX = re.compile(r"[0-9a-f]{64}\Z")
ACTOR = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
ALLOWED = {
    "REQUEST_REVIEW": "proposer",
    "ATTEST_LOCAL_REVIEW": "verifier",
    "REVOKE": "operator",
}
EVENT_FIELDS = frozenset({
    "schema", "token_id", "issue", "source_head", "sequence", "prev_event_hash",
    "nonce", "action", "actor", "key_id", "evidence_sha256", "issued_at",
    "expires_at", "authority_effect", "execution_effect", "signature",
})
MAX_TOKENS = 2048
MAX_EVENTS = 4096


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _digest(value: Any) -> bool:
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def _principal(p: Any) -> tuple[str, str, bytes]:
    """Trust material is caller-provisioned, NOT read from a candidate receipt."""
    if not isinstance(p, Mapping) or set(p) != {"actor", "role", "secret"}:
        raise ValueError("UNTRUSTED_PRINCIPAL_SCHEMA")
    actor, role, secret = p["actor"], p["role"], p["secret"]
    if not isinstance(actor, str) or not ACTOR.fullmatch(actor):
        raise ValueError("INVALID_ACTOR")
    if role not in {"proposer", "verifier", "operator"}:
        raise ValueError("INVALID_PRINCIPAL_ROLE")
    if type(secret) is not bytes or len(secret) < 32:
        raise ValueError("INVALID_LOCAL_SECRET")
    return actor, role, secret


def _strict_spine(spine: Mapping[str, Any], expected_spine_hash: str) -> dict[str, dict[str, Any]]:
    if not isinstance(spine, Mapping) or spine.get("schema") != SPINE_SCHEMA:
        raise ValueError("SPINE_SCHEMA_INVALID")
    if not _digest(expected_spine_hash):
        raise ValueError("TRUSTED_SPINE_HASH_MISSING")
    if (spine.get("receipt_hash") != expected_spine_hash or
            digest({k: v for k, v in spine.items() if k != "receipt_hash"}) != expected_spine_hash):
        raise ValueError("SPINE_HASH_MISMATCH")
    if (spine.get("token_meaning") != "CONTENT_ADDRESS_ONLY_NOT_A_CAPABILITY" or
            spine.get("improvement_admission") != "DENIED" or
            spine.get("skill_tier_effect") != "NONE" or
            spine.get("authority_effect") != "NONE" or
            spine.get("execution_effect") != "NONE"):
        raise ValueError("SPINE_AUTHORITY_CONTRACT_INVALID")
    tokens = spine.get("issue_contract_tokens")
    if (not isinstance(tokens, list) or len(tokens) > MAX_TOKENS or
            spine.get("issue_count") != len(tokens) or type(spine.get("issue_count")) is not int):
        raise ValueError("SPINE_TOKENS_INVALID")
    keyed = {}
    issue_keys = set()
    for t in tokens:
        if (not isinstance(t, Mapping) or t.get("schema") != TOKEN_SCHEMA or
                not _digest(t.get("token_id")) or
                digest({k: v for k, v in t.items() if k != "token_id"}) != t["token_id"] or
                t.get("authority_effect") != "NONE" or
                t.get("execution_effect") != "NONE" or
                t.get("self_promotion") != "DENIED" or
                t.get("claims_verified") is not False or
                t.get("source_head") != spine.get("source_head") or
                t.get("graph_receipt_hash") != spine.get("issue_graph_root") or
                t.get("evolution_round_hash") != spine.get("evolution_round_root") or
                t.get("workplane_receipt") != spine.get("workplane_receipt") or
                not isinstance(t.get("issue"), str)):
            raise ValueError("TOKEN_CONTENT_BINDING_INVALID")
        if t["token_id"] in keyed or t["issue"] in issue_keys:
            raise ValueError("DUPLICATE_ISSUE_TOKEN")
        keyed[t["token_id"]] = dict(t)
        issue_keys.add(t["issue"])
    return keyed


def sign_local_event(body: Mapping[str, Any], *, secret: bytes) -> dict[str, Any]:
    """Local test/operator helper; possession of secret does NOT prove real-world identity."""
    if type(secret) is not bytes or len(secret) < 32:
        raise ValueError("INVALID_LOCAL_SECRET")
    if not isinstance(body, Mapping) or set(body) != EVENT_FIELDS - {"signature"}:
        raise ValueError("EVENT_SIGNING_FIELDS_INVALID")
    unsigned = dict(body)
    mac = hmac.new(secret, DOMAIN + canonical(unsigned), hashlib.sha256).hexdigest()
    return {**unsigned, "signature": mac}


def _event(e: Any, keyring: Mapping[str, Mapping[str, Any]], now: int) -> None:
    if not isinstance(e, Mapping) or set(e) != EVENT_FIELDS or e.get("schema") != EVENT_SCHEMA:
        raise ValueError("EVENT_SCHEMA_INVALID")
    if e["action"] not in ALLOWED:
        raise ValueError("EVENT_ACTION_FORBIDDEN")
    if e.get("authority_effect") != "NONE" or e.get("execution_effect") != "NONE":
        raise ValueError("EVENT_AUTHORITY_ESCALATION")
    for key in ("token_id", "prev_event_hash", "nonce", "evidence_sha256", "signature"):
        if not _digest(e.get(key)):
            raise ValueError("EVENT_DIGEST_INVALID:" + key)
    for key in ("issued_at", "expires_at", "sequence"):
        if type(e.get(key)) is not int or e[key] < 0:
            raise ValueError("EVENT_TIME_SEQUENCE_INVALID")
    if e["issued_at"] > now or e["expires_at"] < e["issued_at"]:
        raise ValueError("EVENT_CLOCK_INVALID")
    if e["action"] != "REVOKE" and now > e["expires_at"]:
        raise ValueError("EVENT_EXPIRED")
    if (not isinstance(e.get("actor"), str) or not ACTOR.fullmatch(e["actor"]) or
            not isinstance(e.get("key_id"), str) or not ACTOR.fullmatch(e["key_id"])):
        raise ValueError("EVENT_ACTOR_INVALID")
    principal = keyring.get(e["key_id"])
    if principal is None:
        raise ValueError("EVENT_UNKNOWN_KEY")
    actor, role, secret = _principal(principal)
    if actor != e["actor"] or role != ALLOWED[e["action"]]:
        raise ValueError("EVENT_ROLE_BINDING_INVALID")
    unsigned = {k: e[k] for k in EVENT_FIELDS if k != "signature"}
    expected = hmac.new(secret, DOMAIN + canonical(unsigned), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, e["signature"]):
        raise ValueError("EVENT_HMAC_INVALID")


def evaluate_lifecycle(spine: Mapping[str, Any], events: list[Mapping[str, Any]], *,
                       trusted_spine_hash: str,
                       trusted_keys: Mapping[str, Mapping[str, Any]], now: int,
                       trusted_journal_digest: str | None = None,
                       trusted_observation_times: list[int] | None = None,
                       trusted_observations_digest: str | None = None) -> dict[str, Any]:
    """Pure replay. All 'reviewed' results still require actual admission elsewhere."""
    tokens = _strict_spine(spine, trusted_spine_hash)
    if (not isinstance(events, list) or len(events) > MAX_EVENTS or
            not isinstance(trusted_keys, Mapping) or
            type(now) is not int or now < 0):
        raise ValueError("LIFECYCLE_INPUT_INVALID")
    # A replayed list is NOT a durable log. A trusted digest supplied through a
    # separate channel detects history truncation/rollback; deriving the digest
    # from the same untrusted list cannot establish provenance.
    journal_digest = digest(events)
    if trusted_journal_digest is not None:
        if not _digest(trusted_journal_digest) or not hmac.compare_digest(
                trusted_journal_digest, journal_digest):
            raise ValueError("TOKEN_JOURNAL_ROLLBACK_OR_TAMPER")
    # Historical replay must validate an event at its *observed* time, not
    # at the much later audit time. Without independent checkpoint binding,
    # user-supplied timestamps would permit backdated expired events.
    if trusted_observation_times is not None:
        if (trusted_journal_digest is None or not _digest(trusted_observations_digest)
                or type(trusted_observation_times) is not list
                or len(trusted_observation_times) != len(events)
                or any(type(t) is not int or t < 0 or t > now
                       for t in trusted_observation_times)
                or any(a > b for a, b in zip(trusted_observation_times,
                                             trusted_observation_times[1:]))):
            raise ValueError("EVENT_OBSERVATION_TIMES_UNTRUSTED")
        expected_obs = digest({"journal_digest": journal_digest,
                               "observed_at": trusted_observation_times})
        if not hmac.compare_digest(expected_obs, trusted_observations_digest):
            raise ValueError("EVENT_OBSERVATIONS_DIGEST_MISMATCH")
    elif trusted_observations_digest is not None:
        raise ValueError("EVENT_OBSERVATION_TIMES_MISSING")
    states: dict[str, dict[str, Any]] = {
        k: {"issue": v["issue"], "status": "OBSERVED_UNVERIFIED",
            "last_event": "0" * 64, "sequence": 0, "proposer": None,
            "proposer_key": None, "verifier": None, "review_evidence": None,
            "revoked": False} for k, v in tokens.items()
    }
    nonces = set()
    for i, e in enumerate(events):
        observed_at = trusted_observation_times[i] if trusted_observation_times is not None else now
        _event(e, trusted_keys, observed_at)
        token = tokens.get(e["token_id"])
        if token is None:
            raise ValueError("EVENT_UNKNOWN_TOKEN")
        if e["issue"] != token["issue"] or e["source_head"] != token["source_head"]:
            raise ValueError("EVENT_TOKEN_BINDING_INVALID")
        s = states[e["token_id"]]
        if e["nonce"] in nonces:
            raise ValueError("EVENT_NONCE_REPLAY")
        nonces.add(e["nonce"])
        if e["sequence"] != s["sequence"] or e["prev_event_hash"] != s["last_event"]:
            raise ValueError("EVENT_CHAIN_REPLAY_OR_FORK")
        if s["revoked"]:
            raise ValueError("TOKEN_REVOKED_IRREVERSIBLY")
        action = e["action"]
        if action == "REQUEST_REVIEW":
            if s["status"] != "OBSERVED_UNVERIFIED":
                raise ValueError("REVIEW_REQUEST_BAD_STATE")
            s["status"] = "LOCAL_REVIEW_REQUESTED"
            s["proposer"], s["proposer_key"] = e["actor"], e["key_id"]
        elif action == "ATTEST_LOCAL_REVIEW":
            if s["status"] != "LOCAL_REVIEW_REQUESTED":
                raise ValueError("REVIEW_ATTESTATION_BAD_STATE")
            if e["actor"] == s["proposer"] or e["key_id"] == s["proposer_key"]:
                raise ValueError("SELF_REVIEW_FORBIDDEN")
            s["status"] = "LOCAL_REVIEW_ATTESTED_EXTERNAL_ADMISSION_REQUIRED"
            s["verifier"] = e["actor"]
            s["review_evidence"] = e["evidence_sha256"]
        else:
            s["revoked"] = True
            s["status"] = "REVOKED_NOT_ADMITTED"
        s["sequence"] += 1
        s["last_event"] = digest(e)
    items = [{"token_id": k, **v} for k, v in sorted(states.items())]
    out = {"schema": SCHEMA, "spine_receipt": trusted_spine_hash,
           "journal_digest": journal_digest,
           "observation_checkpoint": ("EXTERNALLY_SUPPLIED_DIGEST_MATCHED_NOT_AUTHENTICATED"
                                      if trusted_observation_times is not None
                                      else "NOT_PROVIDED"),
           "observations_digest": trusted_observations_digest,
           "journal_checkpoint": ("EXTERNAL_DIGEST_MATCHED" if trusted_journal_digest is not None
                                  else "UNANCHORED_NO_ROLLBACK_PROTECTION"),
           "token_count": len(items), "event_count": len(events),
           "tokens": items,
           "local_key_assertion": "SHARED_SECRET_ONLY_NO_EXTERNAL_IDENTITY_PROOF",
           "publisher_authenticated": False,
           "admission": "DENIED", "promotion_applied": False,
           "capability_granted": False,
           "authority_effect": "NONE", "execution_effect": "NONE"}
    return {**out, "receipt_hash": digest(out)}
