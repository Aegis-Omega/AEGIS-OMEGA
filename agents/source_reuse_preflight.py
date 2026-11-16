#!/usr/bin/env python3
"""AEGIS #753 read-only source-reuse preflight. Never grants execution authority.

Caller-supplied manifests are UNTRUSTED observations, not provider attestations.
The gate prevents false ABSENT claims, uninspected reuse, cross-tenant borrowing,
and the creation of a duplicate while a reuse candidate remains unresolved.
Existing Automaton-3 remains the sole authority path (see #773/#758).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

SCHEMA = "AEGIS_SOURCE_REUSE_PREFLIGHT_V1"
HEAD = re.compile(r"[0-9a-f]{40}\Z")
SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/#-]{0,191}\Z")
SURFACE_STATES = {"SEARCHED_COMPLETE", "SEARCHED_PARTIAL", "UNAVAILABLE", "NOT_SEARCHED"}
EVIDENCE = {"SOURCE_SEEN", "CONTENT_READ", "UNDERSTOOD_BY_TASK_TEST", "ACTUALLY_REUSED", "VERIFIED_BENEFIT"}
DECISIONS = {"REUSE", "REJECT", "UNDECIDED"}
MAX_INPUT = 512_000
MAX_ASSETS = 256


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("TIME_REQUIRES_UTC_Z")
    try:
        d = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("INVALID_OBSERVATION_TIME") from exc
    if d.tzinfo is None:
        raise ValueError("INVALID_OBSERVATION_TIME")
    return d.astimezone(timezone.utc)


def _ref(value: Any) -> bool:
    return isinstance(value, str) and SOURCE.fullmatch(value) is not None


def evaluate(manifest: Any, *, required_asset_pins: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Emit deterministic, DENY-ONLY screening of a caller-authored manifest.

    READY_FOR_AUTHORITY_REVIEW is NOT tool permission or independent verification.
    Neither this result nor its hash proves connector access or scientific validity.

    An *independently selected* task-specific source contract can be passed in
    `required_asset_pins`. Never populate it from the proposing model's manifest:
    caller-supplied search results are precisely what a missed-source incident
    can omit. Git blob pins must be verified separately against a trusted source.
    """
    if required_asset_pins is not None:
        if (not isinstance(required_asset_pins, Mapping)
                or len(required_asset_pins) > 64
                or any(not _ref(k) or not isinstance(v, str)
                       or not HEAD.fullmatch(v)
                       for k, v in required_asset_pins.items())):
            raise ValueError("INVALID_REQUIRED_ASSET_PINS")
    if not isinstance(manifest, dict) or len(canonical(manifest)) > MAX_INPUT:
        raise ValueError("INVALID_MANIFEST")
    allowed = {"task_id", "source_head", "tenant", "intent", "as_of", "max_age_hours",
               "required_surfaces", "surfaces", "assets"}
    if set(manifest) != allowed:
        raise ValueError("MANIFEST_FIELDS_INVALID")
    if not _ref(manifest["task_id"]):
        raise ValueError("INVALID_TASK_ID")
    if not isinstance(manifest["source_head"], str) or not HEAD.fullmatch(manifest["source_head"]):
        raise ValueError("INVALID_EXACT_HEAD")
    if not _ref(manifest["tenant"]):
        raise ValueError("INVALID_TENANT")
    if manifest["intent"] not in {"USE_EXISTING", "PROPOSE_NEW", "RESEARCH"}:
        raise ValueError("INVALID_INTENT")
    now = _utc(manifest["as_of"])
    age = manifest["max_age_hours"]
    if type(age) is not int or age not in range(1, 8761):
        raise ValueError("INVALID_FRESHNESS_BUDGET")
    required = manifest["required_surfaces"]
    surfaces = manifest["surfaces"]
    assets = manifest["assets"]
    if (not isinstance(required, list) or not required or len(required) > 32
            or any(not _ref(n) for n in required) or len(set(required)) != len(required)
            or not isinstance(surfaces, list) or len(surfaces) > 64
            or not isinstance(assets, list) or len(assets) > MAX_ASSETS):
        raise ValueError("INVENTORY_SHAPE_INVALID")

    blockers: set[str] = set()
    coverage: dict[str, dict[str, Any]] = {}
    for item in surfaces:
        if not isinstance(item, dict) or set(item) != {"name", "state", "observed_at"}:
            raise ValueError("SURFACE_FIELDS_INVALID")
        name, state = item["name"], item["state"]
        if not _ref(name) or state not in SURFACE_STATES or name in coverage:
            raise ValueError("SURFACE_ENTRY_INVALID_OR_DUPLICATED")
        observed = _utc(item["observed_at"])
        fresh = 0 <= (now - observed).total_seconds() <= age * 3600
        coverage[name] = {"state": state, "fresh": fresh}
    for name in required:
        s = coverage.get(name)
        if s is None:
            blockers.add("SURFACE_NOT_SEARCHED:" + name)
        elif s["state"] != "SEARCHED_COMPLETE":
            blockers.add("SURFACE_NOT_COMPLETE:" + name)
        elif not s["fresh"]:
            blockers.add("STALE_SURFACE:" + name)

    seen: dict[str, tuple[str, str]] = {}
    summarized: list[dict[str, Any]] = []
    inspected: dict[str, dict[str, Any]] = {}
    reused = 0
    for item in assets:
        fields = {"asset_id", "surface", "revision", "evidence", "disposition",
                  "reason", "access", "tenant"}
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("ASSET_FIELDS_INVALID")
        asset_id, surface, revision = item["asset_id"], item["surface"], item["revision"]
        ev, choice, access = item["evidence"], item["disposition"], item["access"]
        if (not _ref(asset_id) or not _ref(surface) or not _ref(revision)
                or ev not in EVIDENCE or choice not in DECISIONS
                or access not in {"PUBLIC", "TENANT", "PRIVATE"}
                or not _ref(item["tenant"])):
            raise ValueError("ASSET_ENTRY_INVALID")
        if asset_id in seen:
            raise ValueError("DUPLICATE_SOURCE_ID")
        seen[asset_id] = (surface, revision)
        inspected[asset_id] = item
        if surface not in coverage:
            blockers.add("ASSET_SURFACE_UNCHECKED:" + asset_id)
        if access != "PUBLIC" and item["tenant"] != manifest["tenant"]:
            blockers.add("CROSS_TENANT_REUSE_DENIED:" + asset_id)
        if choice == "UNDECIDED":
            blockers.add("UNRESOLVED_REUSE_CANDIDATE:" + asset_id)
        if choice == "REUSE":
            reused += 1
            if ev == "SOURCE_SEEN":
                blockers.add("REUSE_WITHOUT_CONTENT_READ:" + asset_id)
        if choice == "REJECT" and (not isinstance(item["reason"], str) or len(item["reason"].strip()) < 12):
            blockers.add("UNEXPLAINED_REJECTION:" + asset_id)
        if choice == "REUSE" and manifest["intent"] == "PROPOSE_NEW":
            blockers.add("DUPLICATE_BUILD_WHEN_REUSE_EXISTS:" + asset_id)
        summarized.append({"asset_id": asset_id, "surface": surface, "revision": revision,
                           "evidence_claim": ev, "decision": choice})
    # Fail closed when a trusted task contract references source material that
    # the model omitted, silently swapped, only saw by filename or rejected on
    # its own authority. This adds NO knowledge or permission: it only vetoes
    # a misleading "new work" conclusion pending independent review.
    if required_asset_pins:
        for source_id, pinned_blob_sha in required_asset_pins.items():
            prior = inspected.get(source_id)
            if prior is None:
                blockers.add("REQUIRED_PRIOR_ART_MISSING:" + source_id)
                continue
            if prior["revision"] != pinned_blob_sha:
                blockers.add("REQUIRED_PRIOR_ART_REVISION_MISMATCH:" + source_id)
            if prior["evidence"] == "SOURCE_SEEN":
                blockers.add("REQUIRED_PRIOR_ART_CONTENT_UNREAD:" + source_id)
            if manifest["intent"] == "PROPOSE_NEW" and prior["disposition"] == "REJECT":
                blockers.add("PRIOR_ART_REJECTION_NEEDS_INDEPENDENT_REVIEW:" + source_id)

    if manifest["intent"] == "USE_EXISTING" and reused == 0:
        blockers.add("NO_REUSE_SELECTED")
    if manifest["intent"] == "PROPOSE_NEW" and not assets:
        # Empty search results are not a proof that the capability is absent.
        blockers.add("NO_CONTENT_REVIEWED_BEFORE_NEW_BUILD")
    status = "HOLD" if blockers else "READY_FOR_AUTHORITY_REVIEW"
    body = {
        "schema": SCHEMA, "task_id": manifest["task_id"],
        "source_head": manifest["source_head"], "intent": manifest["intent"],
        "manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
        "required_surfaces": sorted(required), "coverage": dict(sorted(coverage.items())),
        "assets": sorted(summarized, key=lambda x: x["asset_id"]),
        "outcome": status, "blockers": sorted(blockers),
        "provenance": "CALLER_REPORTED_NOT_INDEPENDENTLY_ATTESTED",
        "new_knowledge_promoted": False, "skill_promotion": "DENIED",
        "authority_effect": "NONE", "external_effect": "NONE",
    }
    if required_asset_pins is not None:
        # Digest protects deterministic replay of the externally provided
        # pin contract; it does NOT attest that a connector fetched the blobs.
        body["required_asset_pins_sha256"] = hashlib.sha256(
            canonical(dict(required_asset_pins))
        ).hexdigest()
        body["required_source_ids"] = sorted(required_asset_pins)
        body["required_asset_pins_provenance"] = "EXTERNALLY_SUPPLIED_NOT_ATTESTED"
    return {**body, "receipt_hash": hashlib.sha256(canonical(body)).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline read-only AEGIS asset reuse preflight")
    parser.add_argument("manifest", type=Path, help="Metadata-only JSON manifest")
    parser.add_argument("--required-asset-pins", type=Path, default=None,
                        help="Independent task-scoped JSON map: source ID to exact Git blob SHA-1")
    parser.add_argument("--required-asset-pins-sha256", default=None,
                        help="SHA-256 of canonical independent source map, checked out-of-band")
    args = parser.parse_args()
    if (args.required_asset_pins is None) != (args.required_asset_pins_sha256 is None):
        print(json.dumps({"outcome": "HOLD", "reason": "PIN_CONTRACT_ARGUMENTS_INCOMPLETE",
                          "authority_effect": "NONE"}, sort_keys=True))
        return 2
    pins: dict[str, str] | None = None
    if args.required_asset_pins is not None:
        contract_path = args.required_asset_pins
        if contract_path.is_symlink() or not contract_path.is_file():
            print(json.dumps({"outcome": "HOLD", "reason": "UNTRUSTED_PIN_CONTRACT_PATH",
                              "authority_effect": "NONE"}, sort_keys=True))
            return 2
        with contract_path.open("rb") as pin_file:
            pin_raw = pin_file.read(MAX_INPUT + 1)
        if len(pin_raw) > MAX_INPUT:
            print(json.dumps({"outcome": "HOLD", "reason": "PIN_CONTRACT_TOO_LARGE",
                              "authority_effect": "NONE"}, sort_keys=True))
            return 2
        try:
            pins = json.loads(pin_raw)
            expected_hash = args.required_asset_pins_sha256
            if (not isinstance(expected_hash, str) or
                    not re.fullmatch(r"[0-9a-f]{64}", expected_hash) or
                    hashlib.sha256(canonical(pins)).hexdigest() != expected_hash):
                raise ValueError("PIN_CONTRACT_HASH_MISMATCH")
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            print(json.dumps({"outcome": "HOLD", "reason": str(exc)[:64],
                              "authority_effect": "NONE"}, sort_keys=True))
            return 2
    if args.manifest.is_symlink() or not args.manifest.is_file():
        raise SystemExit("UNTRUSTED_MANIFEST_PATH")
    with args.manifest.open("rb") as fh:
        raw = fh.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise SystemExit("MANIFEST_TOO_LARGE")
    try:
        result = evaluate(json.loads(raw), required_asset_pins=pins)
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        print(json.dumps({"outcome": "HOLD", "reason": type(exc).__name__, "authority_effect": "NONE"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "READY_FOR_AUTHORITY_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
