#!/usr/bin/env python3
"""Fail closed when a pull-request body claims a head SHA that is not the head.

A PR description that hand-transcribes its own head SHA goes stale the moment
the branch moves.  This has happened three times on this repository; each time
the body's cited workflow runs and file counts belonged to an earlier commit
while the body read as current evidence.

Rule, deliberately narrow:

  * A body OPTS IN by containing a head-claim marker (see HEAD_CLAIM_MARKERS).
  * Once opted in, the body MUST contain the actual head SHA verbatim.
  * Bodies with no marker are ignored entirely -- this gate never forces a
    convention onto descriptions that do not make the claim.

Other 40-hex strings (base SHA, tree hashes, receipt roots, digests) are not
inspected.  The gate asserts presence of the true head, never absence of
others, so it cannot fail on legitimate secondary hashes.
"""

from __future__ import annotations

import re

HEAD_CLAIM_MARKERS = (
    "exact-head evidence",
    "current exact head",
    "pr head:",
    "current head",
    "exact head:",
)

_SHA40 = re.compile(r"\b[0-9a-f]{40}\b")

# ``` fenced blocks ``` and `inline code`
_CODE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.DOTALL)


def strip_code(body: str) -> str:
    """Remove fenced blocks and inline code spans.

    A marker inside code formatting is being QUOTED, not asserted -- this file
    and the pull request that introduced it both enumerate the marker strings
    as documentation, and without this the gate flags its own description.
    Markers must therefore appear in prose. The head SHA itself is still
    searched for across the whole body, because real descriptions legitimately
    put it inside a code fence.
    """
    return _CODE.sub(" ", body)


def claims_a_head(body: str) -> bool:
    low = strip_code(body).lower()
    return any(marker in low for marker in HEAD_CLAIM_MARKERS)


def verify(body: str, head_sha: str) -> tuple[bool, str]:
    """Return (ok, message).  Pure; no I/O, no environment access."""
    if not head_sha or not _SHA40.fullmatch(head_sha):
        return False, f"HEAD_SHA_MALFORMED: {head_sha!r}"
    if not claims_a_head(body):
        return True, "NO_HEAD_CLAIM: body does not claim a head SHA; gate not applicable"
    if head_sha in body:
        return True, f"BOUND: body cites the current head {head_sha}"
    cited = sorted(set(_SHA40.findall(body)))
    detail = ", ".join(s[:12] for s in cited[:6]) or "none"
    return False, (
        f"STALE_BODY: the description claims a head but never cites {head_sha}. "
        f"40-hex strings present: {detail}. "
        "The body was written against an earlier commit; its cited runs, file "
        "counts and receipts belong to that commit, not to this head."
    )


def main() -> int:
    import argparse
    import json
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    ap.add_argument("--body-file", help="read body from a file instead of the event")
    ap.add_argument("--head-sha", help="override the head SHA")
    args = ap.parse_args()

    body, head = "", args.head_sha or ""
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as fh:
            body = fh.read()
    elif args.event_path:
        with open(args.event_path, encoding="utf-8") as fh:
            pr = json.load(fh).get("pull_request") or {}
        body = pr.get("body") or ""
        head = head or (pr.get("head") or {}).get("sha", "")

    ok, message = verify(body, head)
    print(("PASS  " if ok else "FAIL  ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
