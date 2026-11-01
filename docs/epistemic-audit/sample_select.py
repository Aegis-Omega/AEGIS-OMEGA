#!/usr/bin/env python3
"""MUSTALAH-ANANA-REPLAY-001 — deterministic sample selection (amendment §11).

Given the frozen spec hash and the full eligible case frame, applies:
    N < 30          -> FEASIBILITY_FAILURE
    30 <= N <= 100  -> full census
    N > 100         -> 100 cases with smallest SHA256(spec_hash || case_id)

Usage:
    python3 sample_select.py <spec_hash> <case_ids.txt>

case_ids.txt: one case_id per line, UTF-8, with no surrounding whitespace and
no repeats; both are refused rather than cleaned up, for the reasons in
`canonical_frame`. Output: selected case_ids on stdout, verdict line on
stderr. Exit 2 on feasibility failure so the ledger records it as a result,
not an error to retry; exit 1 on a malformed spec hash or frame.

Output order differs per verdict, and the difference is the spec, not an
oversight. Amendment §11 defines the SHA256(spec_hash ‖ case_id) ranking for
the N > 100 draw only; it prescribes nothing for the census, where every
eligible case is emitted and no selection occurs. So:

    DETERMINISTIC_100 -> hash rank order, ascending (the ranking IS the draw)
    FULL_CENSUS       -> case_id order, ascending (nothing is drawn)

Both are deterministic for a given frame. Reading hash rank order into the
census branch would add an ordering the frozen architecture does not specify.

CANONICAL spec_hash REPRESENTATION. §11 writes the ranking as
SHA256(spec_hash ‖ case_id) without saying how spec_hash is represented, while
§17 carries it in the event envelope as "sha256:<digest>". Concatenating
whichever form the caller happens to hold would make the draw depend on the
spelling of the reference rather than on the spec: the envelope form and the
bare digest would rank the same frame differently and produce two different
hundred-case samples. That is replay divergence, which the constitution
forbids outright, so the representation is pinned here rather than left to the
caller:

    canonical form   the bare lowercase 64-character SHA-256 hex digest
    also accepted    the §17 envelope form "sha256:<that digest>"
    everything else  rejected, not coerced

The two accepted forms normalize to the same bytes, so either may be passed
and the draw is identical. Uppercase digests, other prefixes, wrong lengths
and non-hex are refused with ValueError instead of being silently reshaped,
because a near-miss that still hashes is how a divergent draw gets recorded as
authoritative. Validation runs in every regime, including the ones that never
rank, so a malformed spec_hash cannot pass unnoticed just because N <= 100.
"""
import hashlib
import re
import sys

#: The canonical representation: lowercase, unprefixed, 64 hex characters.
_CANONICAL_SPEC_HASH = re.compile(r"[0-9a-f]{64}")

#: The one alternate form §17 defines for the same digest.
_EVENT_FORMAT_PREFIX = "sha256:"


def canonical_spec_hash(spec_hash: str) -> str:
    """Return the bare digest that §11 concatenates, or raise.

    Accepts the canonical digest and the §17 envelope form only. Anything
    else is refused rather than normalized, so no alternate spelling can
    reach the ranking and shift the draw.
    """
    candidate = spec_hash
    if candidate.startswith(_EVENT_FORMAT_PREFIX):
        candidate = candidate[len(_EVENT_FORMAT_PREFIX):]
    if _CANONICAL_SPEC_HASH.fullmatch(candidate) is None:
        raise ValueError(
            "spec_hash must be a bare lowercase SHA-256 hex digest, or the "
            f"amendment §17 form {_EVENT_FORMAT_PREFIX}<digest>; got {spec_hash!r}"
        )
    return candidate


def rank(spec_hash: str, case_id: str) -> str:
    digest = canonical_spec_hash(spec_hash)
    return hashlib.sha256((digest + case_id).encode("utf-8")).hexdigest()


def canonical_frame(case_ids: list[str]) -> list[str]:
    """Return the frame unchanged, or raise. Shared by both entry points.

    Two invariants used to live only in the CLI, so anything importing
    select() bypassed them:

    Duplicates. N is the frame size that §11's thresholds are read against.
    A frame of 30 entries containing one repeat is 29 cases, and admitting it
    as FULL_CENSUS puts an undersized frame past the feasibility minimum the
    amendment exists to enforce.

    Identifier shape. A case_id carrying surrounding whitespace is refused
    rather than trimmed. The CLI used to apply str.strip() per line, which
    removes any whitespace and not merely the line ending, so the identifier
    that got ranked was no longer the identifier the frame froze: a file of
    101 ids with trailing spaces exited successfully while emitting 100 ids
    that appear nowhere in the frame. Rewriting an identifier silently is the
    same failure as rewriting the spec hash silently, and it is refused for
    the same reason.
    """
    for case_id in case_ids:
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"case_id must be a non-empty string; got {case_id!r}")
        if case_id != case_id.strip():
            raise ValueError(
                f"case_id carries surrounding whitespace and will not be rewritten: {case_id!r}"
            )
    if len(case_ids) != len(set(case_ids)):
        duplicated = sorted({c for c in case_ids if case_ids.count(c) > 1})
        raise ValueError(f"duplicate case_ids in frame: {', '.join(duplicated[:10])}")
    return case_ids


def select(spec_hash: str, case_ids: list[str]) -> tuple[str, list[str]]:
    digest = canonical_spec_hash(spec_hash)
    case_ids = canonical_frame(case_ids)
    n = len(case_ids)
    if n < 30:
        return "FEASIBILITY_FAILURE", []
    if n <= 100:
        return "FULL_CENSUS", sorted(case_ids)
    ranked = sorted(case_ids, key=lambda c: rank(digest, c))
    return "DETERMINISTIC_100", ranked[:100]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    try:
        spec_hash = canonical_spec_hash(sys.argv[1])
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[2], encoding="utf-8") as f:
        # Remove the line ending only. Anything else surrounding the
        # identifier is a frame defect for canonical_frame to refuse, not
        # something to trim away behind the operator's back.
        ids = [line.rstrip("\n").rstrip("\r") for line in f]
    ids = [case_id for case_id in ids if case_id]
    try:
        verdict, chosen = select(spec_hash, ids)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    print(f"N={len(ids)} verdict={verdict} selected={len(chosen)}", file=sys.stderr)
    if verdict == "FEASIBILITY_FAILURE":
        sys.exit(2)
    for c in chosen:
        print(c)
