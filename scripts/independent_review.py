#!/usr/bin/env python3
"""Offline falsifier reducer for independently reviewed work receipts.

The caller-supplied identity roster is not authenticated here. Every result is
simulation-only and cannot establish a live reviewer identity or grant authority.
"""
import hashlib
import json
import re

SCHEMA = "aegis.independent-review.v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
ROSTER_FIELDS = {
    "source", "snapshot_id", "identities", "selection_seed_commitment", "sha256",
}


class Invalid(Exception):
    pass


def canonical_digest(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require(condition, reason):
    if not condition:
        raise Invalid(reason)


def _identity(roster, principal_id):
    matches = [
        item for item in roster["identities"]
        if item.get("principal_id") == principal_id
    ]
    _require(len(matches) == 1, "IDENTITY_NOT_UNIQUE")
    return matches[0]


def _roster_payload(roster):
    return {
        "source": roster["source"],
        "snapshot_id": roster["snapshot_id"],
        "identities": roster["identities"],
        "selection_seed_commitment": roster["selection_seed_commitment"],
    }


def _select_identity(candidate_head, submitter_principal, roster, seed, role,
                     excluded_principals=()):
    _require(bool(SHA40.fullmatch(candidate_head or "")), "CANDIDATE_HEAD_INVALID")
    _require(bool(SHA256.fullmatch(seed or "")), "SELECTION_SEED_INVALID")
    _require(all(isinstance(item, str) for item in excluded_principals),
             "EXCLUDED_IDENTITY_INVALID")
    principals = {}
    account_owners = {}
    for item in roster["identities"]:
        principal = item.get("principal_id")
        accounts = item.get("github_ids")
        _require(isinstance(principal, str) and principal, "IDENTITY_INVALID")
        _require(isinstance(accounts, list) and accounts, "IDENTITY_INVALID")
        _require(principal not in principals, "IDENTITY_NOT_UNIQUE")
        _require(all(type(account) is int and account > 0 for account in accounts),
                 "GITHUB_ID_INVALID")
        normalized = sorted(set(accounts))
        for account in normalized:
            _require(account not in account_owners, "GITHUB_ID_AMBIGUOUS")
            account_owners[account] = principal
        principals[principal] = normalized

    _require(submitter_principal in principals, "SUBMITTER_IDENTITY_UNKNOWN")
    excluded = {submitter_principal, *excluded_principals}
    eligible = sorted(principal for principal in principals if principal not in excluded)
    _require(eligible, "NO_INDEPENDENT_REVIEWER")
    draw = canonical_digest({
        "candidate_head": candidate_head,
        "roster_digest": canonical_digest(_roster_payload(roster)),
        "role": role,
        "seed": seed,
        "submitter": submitter_principal,
        "excluded": sorted(excluded),
    })
    selected = eligible[int(draw, 16) % len(eligible)]
    return {
        "principal_id": selected,
        "github_id": principals[selected][0],
    }


def select_reviewer(candidate_head, submitter_principal, roster, seed,
                    excluded_principals=()):
    """Select one canonical reviewer, collapsing account aliases before draw."""
    return _select_identity(
        candidate_head, submitter_principal, roster, seed, "reviewer",
        excluded_principals,
    )


def select_challenge_generator(candidate_head, submitter_principal, roster, seed):
    return _select_identity(
        candidate_head, submitter_principal, roster, seed, "challenge_generator",
    )


def select_challenges(source_digest, challenge_pool, seed, count, submitter):
    """Blindly draw source-bound falsifiers from an independent challenge pool."""
    _require(bool(SHA256.fullmatch(source_digest or "")), "SOURCE_SNAPSHOT_DIGEST_INVALID")
    _require(bool(SHA256.fullmatch(seed or "")), "SELECTION_SEED_INVALID")
    _require(type(count) is int and count > 0, "CHALLENGE_COUNT_INVALID")
    _require(isinstance(challenge_pool, list) and len(challenge_pool) >= count,
             "CHALLENGE_POOL_INCOMPLETE")
    seen = set()
    ranked = []
    for item in challenge_pool:
        _require(isinstance(item, dict), "CHALLENGE_INVALID")
        ident = item.get("id")
        _require(isinstance(ident, str) and ident and ident not in seen,
                 "CHALLENGE_IDS_INVALID")
        seen.add(ident)
        _require(item.get("source_snapshot_sha256") == source_digest,
                 "CHALLENGE_SOURCE_MISMATCH")
        _require(item.get("generator_principal_id") != submitter,
                 "CHALLENGE_GENERATOR_NOT_INDEPENDENT")
        _require(item.get("expected_answer_visible") is False
                 and "expected_answer" not in item,
                 "CHALLENGE_ANSWER_LEAKED")
        _require(set(item) == {
            "id", "class", "source_snapshot_sha256",
            "prompt_sha256", "expected_answer_visible",
            "generator_principal_id",
        }, "CHALLENGE_FIELDS_INVALID")
        _require(item.get("class") in {
            "counterexample", "contradiction", "provenance", "robustness",
        }, "CHALLENGE_CLASS_INVALID")
        prompt = item.get("prompt_sha256")
        _require(isinstance(prompt, str) and SHA256.fullmatch(prompt),
                 "CHALLENGE_PROMPT_DIGEST_INVALID")
        score = canonical_digest({
            "seed": seed,
            "source_snapshot_sha256": source_digest,
            "id": ident,
            "prompt_sha256": prompt,
        })
        ranked.append((score, item))
    return [item for _, item in sorted(ranked)[:count]]


def _assess(receipt, roster):
    _require(isinstance(receipt, dict) and receipt.get("schema") == SCHEMA,
             "RECEIPT_SCHEMA_INVALID")
    _require(isinstance(roster, dict) and isinstance(roster.get("identities"), list),
             "IDENTITY_ROSTER_INVALID")
    _require(set(roster) == ROSTER_FIELDS, "IDENTITY_ROSTER_FIELDS_INVALID")
    _require(roster.get("source") == "trusted_identity_snapshot",
             "IDENTITY_SOURCE_UNVERIFIED")
    _require(isinstance(roster.get("snapshot_id"), str) and roster["snapshot_id"],
             "IDENTITY_SNAPSHOT_MISSING")

    candidate = receipt.get("candidate")
    _require(isinstance(candidate, dict), "CANDIDATE_MISSING")
    head = candidate.get("head_sha")
    _require(isinstance(head, str) and SHA40.fullmatch(head), "CANDIDATE_HEAD_INVALID")
    source = candidate.get("source_snapshot")
    _require(isinstance(source, dict) and source.get("head_sha") == head,
             "SOURCE_SNAPSHOT_STALE")
    files = source.get("files")
    _require(isinstance(files, list) and files, "SOURCE_SNAPSHOT_EMPTY")
    paths = []
    for item in files:
        _require(
            isinstance(item, dict) and isinstance(item.get("path"), str)
            and item["path"] and isinstance(item.get("blob_sha256"), str)
            and SHA256.fullmatch(item["blob_sha256"]),
            "SOURCE_FILE_INVALID",
        )
        paths.append(item["path"])
    _require(paths == sorted(set(paths)), "SOURCE_FILES_NOT_CANONICAL")
    source_digest = canonical_digest({"head_sha": head, "files": files})
    _require(source.get("sha256") == source_digest, "SOURCE_SNAPSHOT_DIGEST_INVALID")

    roster_body = _roster_payload(roster)
    _require(roster.get("sha256") == canonical_digest(roster_body),
             "IDENTITY_SNAPSHOT_DIGEST_INVALID")
    seed = receipt.get("selection_seed")
    _require(isinstance(seed, str) and SHA256.fullmatch(seed)
             and roster.get("selection_seed_commitment")
             == hashlib.sha256(seed.encode("utf-8")).hexdigest(),
             "SELECTION_SEED_UNCOMMITTED")

    submitter = receipt.get("submitter")
    review = receipt.get("review")
    _require(isinstance(submitter, dict) and isinstance(review, dict),
             "REVIEW_IDENTITY_MISSING")
    submitter_principal = submitter.get("principal_id")
    generator_principal = review.get("challenge_generator_principal_id")
    selected_generator = select_challenge_generator(
        head, submitter_principal, roster, seed,
    )
    _require(generator_principal == selected_generator["principal_id"],
             "CHALLENGE_GENERATOR_MISMATCH")
    reviewer = review.get("reviewer")
    _require(isinstance(reviewer, dict), "REVIEWER_IDENTITY_MISSING")
    reviewer_principal = reviewer.get("principal_id")
    selected = select_reviewer(
        head, submitter_principal, roster, seed,
        excluded_principals=(generator_principal,),
    )
    _require(reviewer_principal == selected["principal_id"]
             and type(reviewer.get("github_id")) is int
             and reviewer["github_id"] == selected["github_id"],
             "REVIEWER_IDENTITY_MISMATCH")
    submitter_identity = _identity(roster, submitter_principal)
    _require(type(submitter.get("github_id")) is int
             and submitter["github_id"] in submitter_identity["github_ids"],
             "SUBMITTER_IDENTITY_MISMATCH")
    _require(reviewer_principal != submitter_principal
             and reviewer.get("github_id") != submitter.get("github_id"),
             "REVIEWER_NOT_INDEPENDENT")
    _require(isinstance(review.get("approval_id"), str) and review["approval_id"],
             "APPROVAL_ID_MISSING")
    _require(review.get("approved_head_sha") == head
             and review.get("source_snapshot_sha256") == source_digest,
             "STALE_APPROVAL")
    _require(review.get("decision") == "APPROVED", "REVIEW_NOT_APPROVED")

    isolation = review.get("source_isolation")
    _require(isinstance(isolation, dict)
             and isolation.get("source_snapshot_sha256") == source_digest,
             "REVIEW_SOURCE_MISMATCH")
    _require(isolation.get("submitter_identity_visible") is False
             and "submitter_identity" not in isolation,
             "SUBMITTER_IDENTITY_LEAKED")
    _require(isolation.get("expected_answer_visible") is False
             and "expected_answer" not in isolation,
             "EXPECTED_ANSWER_LEAKED")
    _require(set(isolation) == {
        "source_snapshot_sha256",
        "submitter_identity_visible",
        "expected_answer_visible",
    }, "REVIEW_ISOLATION_FIELDS_INVALID")

    challenge_pool = review.get("challenge_pool")
    challenge_count = review.get("challenge_count")
    _identity(roster, generator_principal)
    pool = review.get("challenge_pool")
    _require(isinstance(pool, list) and all(
        isinstance(item, dict)
        and item.get("generator_principal_id") == generator_principal
        for item in pool
    ), "CHALLENGE_GENERATOR_MISMATCH")
    challenges = review.get("challenge_set")
    _require(isinstance(challenges, list) and challenges, "CHALLENGE_SET_MISSING")
    selected_challenges = select_challenges(
        source_digest, challenge_pool, receipt.get("selection_seed"),
        challenge_count, submitter_principal,
    )
    _require(challenges == selected_challenges, "CHALLENGE_SET_NOT_INDEPENDENT")
    challenge_ids = []
    for challenge in challenges:
        _require(isinstance(challenge, dict), "CHALLENGE_INVALID")
        challenge_ids.append(challenge.get("id"))
        _require(challenge.get("source_snapshot_sha256") == source_digest,
                 "CHALLENGE_SOURCE_MISMATCH")
        _require(isinstance(challenge.get("prompt_sha256"), str)
                 and SHA256.fullmatch(challenge["prompt_sha256"]),
                 "CHALLENGE_PROMPT_DIGEST_INVALID")
        _require(challenge.get("expected_answer_visible") is False,
                 "CHALLENGE_ANSWER_LEAKED")
    _require(all(isinstance(item, str) and item for item in challenge_ids)
             and len(challenge_ids) == len(set(challenge_ids)),
             "CHALLENGE_IDS_INVALID")
    _require(review.get("challenge_set_sha256") == canonical_digest(challenges),
             "CHALLENGE_SET_DIGEST_INVALID")
    evidence = review.get("evidence")
    _require(isinstance(evidence, list), "EVIDENCE_MISSING")
    _require(all(
        isinstance(item, dict) and item.get("result") in {"supports", "contradicts"}
        for item in evidence
    ), "EVIDENCE_RESULT_INVALID")
    _require(not any(item["result"] == "contradicts" for item in evidence),
             "CONFLICTING_EVIDENCE")
    accepted = [
        item for item in evidence
        if isinstance(item, dict)
        and item.get("class") in {"independent_reproduction", "domain_observation"}
        and item.get("quality") == "strong"
        and item.get("result") == "supports"
        and isinstance(item.get("provenance_group"), str)
        and item["provenance_group"]
    ]
    _require(len({item["provenance_group"] for item in accepted}) >= 2,
             "INSUFFICIENT_INDEPENDENT_EVIDENCE")
    conflicts = review.get("unresolved_conflicts")
    _require(isinstance(conflicts, list) and not conflicts, "CONFLICTING_EVIDENCE")

    falsifiers = review.get("falsifier_results")
    _require(isinstance(falsifiers, list) and falsifiers, "FALSIFIERS_MISSING")
    _require(all(
        isinstance(item, dict) and isinstance(item.get("id"), str)
        and item.get("result") in {"survived", "triggered"}
        for item in falsifiers
    ), "FALSIFIER_RESULT_INVALID")
    falsifier_ids = [item["id"] for item in falsifiers]
    _require(len(falsifier_ids) == len(set(falsifier_ids)),
             "FALSIFIER_IDS_DUPLICATED")
    _require(set(falsifier_ids) == set(challenge_ids),
             "FALSIFIER_COVERAGE_INCOMPLETE")
    failed_falsifiers = [
        item["id"] for item in falsifiers if item["result"] == "triggered"
    ]
    _require(not failed_falsifiers, "FALSIFIER_TRIGGERED")
    uncertainty = review.get("residual_uncertainty")
    _require(isinstance(uncertainty, str) and uncertainty.strip(),
             "RESIDUAL_UNCERTAINTY_MISSING")
    return {
        "reviewer_identity": {
            "principal_id": reviewer_principal,
            "github_id": reviewer["github_id"],
        },
        "source_isolation": isolation,
        "source_snapshot_sha256": source_digest,
        "challenge_set": challenges,
        "failed_falsifiers": failed_falsifiers,
        "residual_uncertainty": uncertainty,
    }


def _failure_record(receipt, reason):
    """On denial, never echo untrusted payloads into audit output."""
    if not isinstance(receipt, dict):
        return {}
    review = receipt.get("review")
    review = review if isinstance(review, dict) else {}
    falsifiers = review.get("falsifier_results")
    # IDs are usable only after _assess completed coverage and type checks.
    # Other denials must not reflect attacker-controlled challenge identifiers.
    failed_falsifiers = []
    if reason == "FALSIFIER_TRIGGERED" and isinstance(falsifiers, list):
        failed_falsifiers = [
            item["id"] for item in falsifiers
            if isinstance(item, dict) and isinstance(item.get("id"), str)
            and item.get("result") == "triggered"
        ]
    return {
        "reviewer_identity": {},
        "source_isolation": {},
        "source_snapshot_sha256": None,
        "challenge_set": [],
        "failed_falsifiers": failed_falsifiers,
        "residual_uncertainty": None,
    }


def assess(receipt, trusted_identity_snapshot):
    try:
        record = _assess(receipt, trusted_identity_snapshot)
    except Invalid as exc:
        reason = str(exc)
        return {
            "disposition": "NOT_ADMITTED",
            "authority_effect": "NONE",
            "reason": reason,
            "record": _failure_record(receipt, reason),
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        return {
            "disposition": "NOT_ADMITTED",
            "authority_effect": "NONE",
            "reason": "RECEIPT_INVALID",
            "record": _failure_record(receipt, "RECEIPT_INVALID"),
        }
    return {
        "disposition": "OFFLINE_SIMULATION_ONLY",
        "authority_effect": "NONE",
        "record": record,
    }
