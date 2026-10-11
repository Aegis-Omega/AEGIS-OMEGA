"""AEGIS Research Loop v0.2: offline evidence-packet checks, not web attestation.

No remote requests are made. A packet can show disciplined comparative research
but cannot prove that an agent actually visited a website or that a fact is true.
The connected agent/harness must obtain current web evidence independently.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import ipaddress
import re
from urllib.parse import urlsplit

from .protocol import _artifact_bytes, Invalid, require, SHA256, _strict_pairs

SCHEMA = "aegis.research-cycle.v1"
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,39}\Z")
HOST = re.compile(r"(?=.{4,253}\Z)[a-z0-9-]+(?:\.[a-z0-9-]+)+\Z")


def _time(value):
    require(isinstance(value, str), "RESEARCH_TIME_INVALID")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Invalid("RESEARCH_TIME_INVALID") from exc
    require(d.tzinfo is not None and d.utcoffset() is not None, "RESEARCH_TIME_NAIVE")
    return d.astimezone(timezone.utc)


def _https_hostname(value):
    require(isinstance(value, str) and len(value) < 1500, "SOURCE_URL_INVALID")
    try:
        u = urlsplit(value)
        port = u.port
        hostname = u.hostname
    except ValueError as exc:
        raise Invalid("SOURCE_URL_INVALID") from exc
    require(u.scheme == "https" and u.netloc and hostname and not u.username and
            not u.password and port in (None, 443) and not u.fragment and
            not any(ord(c) < 32 for c in value), "SOURCE_URL_UNSAFE")
    hostname = hostname.lower()
    require(HOST.fullmatch(hostname), "SOURCE_HOST_INVALID")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise Invalid("SOURCE_IP_FORBIDDEN")
    require(not (hostname.endswith(".local") or hostname.endswith(".internal")
                 or hostname.endswith(".localhost") or hostname.endswith(".test")
                 or hostname.endswith(".invalid")), "SOURCE_HOST_LOCAL")
    return hostname


def _publisher_key(hostname):
    # Conservative subdomain collapse. This is a heuristic, not owner validation;
    # known multi-part public suffixes are intentionally treated as one key.
    parts = hostname.split(".")
    suffix = ".".join(parts[-2:])
    if len(parts) > 2 and suffix in {"co.uk", "com.au", "co.jp", "org.uk", "co.in"}:
        return ".".join(parts[-3:])
    return suffix


def _nontrivial(value, min_len=15, max_len=2000):
    return isinstance(value, str) and min_len <= len(value.strip()) <= max_len


def _evidence_exact_match(workspace, evaluation):
    """Recompute a bounded exact-match comparison; never execute agent code.

    Cases and their reference strings are NOT authenticated ground truth. They
    can be forged by the same model; the only claim is replay consistency.
    """
    require(evaluation.get("metric_kind") == "case_exact_match", "EVALUATOR_KIND_UNSUPPORTED")
    path = evaluation.get("evidence_artifact")
    digest = evaluation.get("evidence_sha256")
    require(isinstance(digest, str) and SHA256.fullmatch(digest), "EVALUATION_HASH_REQUIRED")
    raw = _artifact_bytes(workspace, path, cap=256 * 1024)
    require(hashlib.sha256(raw).hexdigest() == digest, "EVALUATION_ARTIFACT_TAMPERED")
    try:
        dataset = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(Invalid("EVALUATION_NONFINITE")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Invalid("EVALUATION_ARTIFACT_INVALID_JSON") from exc
    require(isinstance(dataset, dict) and dataset.get("schema") == "aegis.exact-match-eval.v1",
            "EVALUATION_SCHEMA_INVALID")
    cases = dataset.get("cases")
    require(isinstance(cases, list) and 3 <= len(cases) <= 100, "EVALUATION_CASE_COUNT")
    seen, base, candidate = set(), 0, 0
    # Compare the same cases as pairs. A raw improvement from only a few cases
    # is not evidence of reliable superiority.
    improved, regressed = 0, 0
    for case in cases:
        require(isinstance(case, dict) and set(case) == {"id", "expected", "baseline", "candidate"},
                "EVALUATION_CASE_FIELDS")
        ident = case.get("id")
        require(isinstance(ident, str) and IDENT.fullmatch(ident) and ident not in seen,
                "EVALUATION_CASE_ID_INVALID_OR_DUPLICATE")
        seen.add(ident)
        for k in ("expected", "baseline", "candidate"):
            require(isinstance(case[k], str) and len(case[k]) <= 500,
                    "EVALUATION_CASE_VALUE_INVALID")
        baseline_ok = case["baseline"] == case["expected"]
        candidate_ok = case["candidate"] == case["expected"]
        base += int(baseline_ok)
        candidate += int(candidate_ok)
        improved += int(candidate_ok and not baseline_ok)
        regressed += int(baseline_ok and not candidate_ok)
    derived = "SUPPORTED" if candidate > base else "FALSIFIED" if candidate < base else "INCONCLUSIVE"
    require(evaluation["outcome"] == derived, "EVALUATION_OUTCOME_DISAGREES_WITH_REPLAY")
    # Two-sided exact McNemar/sign test on discordant PAIRS, not two
    # independent proportions. N=0 is inconclusive by definition.
    discordant = improved + regressed
    p_value = min(1.0, (2 * sum(math.comb(discordant, k)
                                 for k in range(min(improved, regressed) + 1)) /
                         2 ** discordant)) if discordant else 1.0
    enough_cases = len(cases) >= 20
    distinguishable = enough_cases and p_value <= 0.05
    signal = ("POSITIVE_PAIRED_SIGNAL" if distinguishable and improved > regressed
              else "NEGATIVE_PAIRED_SIGNAL" if distinguishable and regressed > improved
              else "UNDERPOWERED" if not enough_cases else "NO_SIGNIFICANT_DIFFERENCE")
    # Even a statistically distinguishable SELF-REPORTED case set does not
    # authenticate reference answers, sampling, domain correctness or trial independence.
    return {"kind": "case_exact_match", "case_count": len(cases),
            "baseline_matches": base, "candidate_matches": candidate,
            "candidate_improvements": improved, "candidate_regressions": regressed,
            "discordant_pairs": discordant, "paired_accuracy_delta_pp":
                round(100 * (candidate - base) / len(cases), 6),
            "paired_test": "exact_two_sided_mcnemar_binomial",
            "paired_p_value": round(p_value, 12), "minimum_cases_for_signal": 20,
            "statistical_signal": signal, "calculated_outcome": derived,
            "outcome_interpretation": "SELF_REPORTED_DIRECTION_ONLY",
            "evidence_sha256": digest, "authenticity": "UNVERIFIED",
            "holdout_integrity": "UNVERIFIED", "oracle_independence": "UNVERIFIED",
            "cross_model_superiority": "UNPROVEN"}


def audit_research(workspace, record, *, now=None):
    """Audit source-byte anchors, comparison, falsification and learning stages.

    This is explicitly not a live web search or source-authenticity attestation.
    Caller-supplied snapshots and source URLs can be fabricated. All positive
    outcomes retain source_authenticity UNVERIFIED and improvement UNPROVEN.
    """
    result = {
        "schema": "aegis.research-audit.v1",
        "status": "BLOCKED",
        "source_authenticity": "UNVERIFIED",
        "live_web_retrieval": "NOT_PERFORMED",
        "improvement": "UNPROVEN",
        "authority_effect": "NONE",
        "sources": []
    }
    try:
        require(isinstance(record, dict) and record.get("schema") == SCHEMA,
                "RESEARCH_SCHEMA_INVALID")
        require(_nontrivial(record.get("question")), "RESEARCH_QUESTION_MISSING")
        searches = record.get("searches")
        require(isinstance(searches, list) and 1 <= len(searches) <= 20,
                "SEARCH_LOG_INVALID")
        require(all(isinstance(s, dict) and _nontrivial(s.get("query"), 5, 300)
                    and s.get("status") == "completed" and
                    s.get("tool") in ("web", "browser", "search_connector")
                    for s in searches), "LIVE_SEARCH_UNRECORDED")
        sources = record.get("sources")
        require(isinstance(sources, list) and 2 <= len(sources) <= 12,
                "RESEARCH_SOURCES_INSUFFICIENT")
        current = now or datetime.now(timezone.utc)
        require(current.tzinfo is not None, "CLOCK_NAIVE")
        current = current.astimezone(timezone.utc)
        identifiers, domains = set(), set()
        for source in sources:
            require(isinstance(source, dict), "SOURCE_INVALID")
            ident = source.get("id")
            require(isinstance(ident, str) and IDENT.fullmatch(ident)
                    and ident not in identifiers, "SOURCE_ID_DUPLICATE_OR_INVALID")
            identifiers.add(ident)
            hostname = _https_hostname(source.get("url"))
            domains.add(_publisher_key(hostname))
            stamp = _time(source.get("retrieved_at"))
            require(current-timedelta(days=7) <= stamp <= current+timedelta(minutes=5),
                    "SOURCE_STALE_OR_FUTURE")
            # Hash of a locally stored source excerpt is a byte-integrity check.
            # It is NOT evidence that the excerpt truly came from the named URL.
            expected = source.get("sha256")
            require(isinstance(expected, str) and SHA256.fullmatch(expected),
                    "SOURCE_HASH_MISSING")
            excerpt = source.get("excerpt")
            require(_nontrivial(excerpt, 12, 700), "SOURCE_EXCERPT_MISSING")
            snapshot = _artifact_bytes(workspace, source.get("artifact"))
            require(hashlib.sha256(snapshot).hexdigest() == expected,
                    "SOURCE_SNAPSHOT_TAMPERED")
            require(excerpt.encode("utf-8") in snapshot, "SOURCE_EXCERPT_NOT_ANCHORED")
            result["sources"].append({"id": ident, "domain": hostname,
                                      "snapshot_integrity": "PASS"})
        require(len(domains) >= 2, "SOURCE_PUBLISHERS_NOT_INDEPENDENT")
        comparisons = record.get("comparison")
        require(isinstance(comparisons, dict) and
                _nontrivial(comparisons.get("baseline")) and
                isinstance(comparisons.get("alternatives"), list) and
                len(comparisons["alternatives"]) >= 2, "COMPARISON_MISSING")
        variants = set()
        for option in comparisons["alternatives"]:
            require(isinstance(option, dict) and
                    _nontrivial(option.get("name"), 3, 180) and
                    _nontrivial(option.get("advantage")) and
                    _nontrivial(option.get("tradeoff")) and
                    isinstance(option.get("source_ids"), list) and
                    option["source_ids"] and all(i in identifiers for i in option["source_ids"]),
                    "ALTERNATIVE_UNGROUNDED")
            require(option["name"] not in variants, "ALTERNATIVE_DUPLICATE")
            variants.add(option["name"])
        require(_nontrivial(comparisons.get("choice"), 3, 180) and
                comparisons["choice"] in variants and
                _nontrivial(comparisons.get("reason")), "DECISION_NOT_GROUNDED")
        evaluation = record.get("evaluation")
        require(isinstance(evaluation, dict) and
                _nontrivial(evaluation.get("metric"), 5, 300) and
                _nontrivial(evaluation.get("baseline_measure")) and
                _nontrivial(evaluation.get("target_measure")) and
                _nontrivial(evaluation.get("falsification_test")) and
                evaluation.get("outcome") in ("NOT_RUN", "FALSIFIED", "INCONCLUSIVE", "SUPPORTED"),
                "EVALUATION_MISSING")
        if evaluation["outcome"] != "NOT_RUN":
            result["evaluation_replay"] = _evidence_exact_match(workspace, evaluation)
        learning = record.get("learning")
        require(isinstance(learning, dict) and
                _nontrivial(learning.get("observed")) and
                _nontrivial(learning.get("next_experiment")) and
                _nontrivial(learning.get("change_proposed")),
                "LEARNING_MISSING")
        result["status"] = "LOCAL_PACKET_COMPLETE_UNATTESTED"
        result["source_count"] = len(identifiers)
        result["publisher_count"] = len(domains)
        result["falsification_outcome_reported"] = evaluation["outcome"]
    except (Invalid, OSError, TypeError, ValueError, UnicodeError) as exc:
        result["reason"] = str(exc)
    return result
