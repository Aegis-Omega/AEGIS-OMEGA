#!/usr/bin/env python3
"""Read-only, fail-closed candidate matching for HubSpot contact sources.

Inputs are CSV exports supplied by the operator. No network, credentials, API
calls, contact writes, merges, or sync activations. This tool cannot approve a sync.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "aegis.crm-presync-gate.v1"
DEFAULT_SOURCES = ("google_contacts", "outlook_default", "outlook_iphone")
SOURCE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class InvalidInput(Exception):
    pass


def norm_email(raw: str | None) -> str:
    # This is a REVIEW candidate key, not proof of common ownership.
    return unicodedata.normalize("NFC", (raw or "").strip()).casefold()


def valid_email(candidate: str) -> bool:
    return (candidate.count("@") == 1 and not any(ch.isspace() for ch in candidate)
            and candidate.split("@", 1)[0] != "" and candidate.split("@", 1)[1] != "")


def norm_phone(raw: str | None) -> str:
    return "".join(c for c in (raw or "") if c.isdecimal())


def fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_csv(path: Path, required: set[str], category: str) -> tuple[list[dict[str, str]], str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InvalidInput(f"{category}: source file inaccessible ({type(exc).__name__})") from exc
    try:
        stream = io.StringIO(raw.decode("utf-8-sig"), newline="")
        reader = csv.DictReader(stream, strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise InvalidInput(f"{category}: duplicate CSV column names")
        missing = sorted(required - set(fields))
        if missing:
            raise InvalidInput(f"{category}: missing columns {', '.join(missing)}")
        items = []
        for line_no, row in enumerate(reader, start=2):
            if None in row:
                raise InvalidInput(f"{category}: extra CSV field(s) near row {line_no}")
            if any(v is None for v in row.values()):
                raise InvalidInput(f"{category}: missing CSV field(s) near row {line_no}")
            if not any(str(v).strip() for v in row.values()):
                continue
            items.append({str(k): str(v) for k, v in row.items()})
    except (UnicodeError, csv.Error) as exc:
        raise InvalidInput(f"{category}: malformed UTF-8/CSV ({type(exc).__name__})") from exc
    return items, fingerprint(raw)


def source_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise InvalidInput("--source must be NAME=PATH")
    name, path = spec.split("=", 1)
    if not SOURCE_RE.fullmatch(name) or not path.strip():
        raise InvalidInput("source name must be lowercase a-z, 0-9, _ or -; PATH must not be empty")
    return name, Path(path)


def evaluate(crm_csv: Path, sources: dict[str, Path], required_sources: tuple[str, ...] = DEFAULT_SOURCES) -> dict:
    crm, crm_digest = load_csv(crm_csv, {"hs_object_id", "email"}, "CRM")
    crm_ids: set[str] = set()
    crm_by_email: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in crm:
        oid = record["hs_object_id"].strip()
        if not oid or oid in crm_ids:
            raise InvalidInput("CRM: missing or duplicate hs_object_id")
        crm_ids.add(oid)
        em = norm_email(record["email"])
        if em:
            crm_by_email[em].append(record)

    missing_sources = sorted(set(required_sources) - sources.keys())
    source_rows: dict[str, list[dict[str, str]]] = {}
    source_digests = {}
    email_to_sources: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for name, path in sorted(sources.items()):
        rows, sha = load_csv(path, {"source_record_id", "email"}, f"source '{name}'")
        ids = set()
        for row in rows:
            sid = row["source_record_id"].strip()
            # Protect provenance keys from accidental personal email exposure in output.
            if not sid or "@" in sid or sid in ids:
                raise InvalidInput(f"source '{name}': missing, non-opaque, or duplicate source_record_id")
            ids.add(sid)
            em = norm_email(row["email"])
            if em:
                email_to_sources[em].append((name, sid))
        source_rows[name] = rows
        source_digests[name] = sha

    details = []
    for name, rows in sorted(source_rows.items()):
        for row in rows:
            em = norm_email(row["email"])
            flags: list[str] = []
            crm_id = None
            if not em:
                verdict = "MISSING_EMAIL_HOLD"
                flags.append("MISSING_EMAIL")
            elif not valid_email(em):
                verdict = "INVALID_EMAIL_HOLD"
                flags.append("INVALID_EMAIL")
            else:
                candidate_crm = crm_by_email.get(em, [])
                if len(candidate_crm) > 1:
                    verdict = "CRM_COLLISION_HOLD"
                    flags.append("DUPLICATE_CRM_EMAIL")
                elif not candidate_crm:
                    verdict = "UNMATCHED_HOLD"
                    flags.append("NOT_IN_CRM_PRIMARY_EMAILS")
                else:
                    crm_record = candidate_crm[0]
                    crm_id = crm_record["hs_object_id"].strip()
                    if len(email_to_sources[em]) > 1:
                        flags.append("CROSS_SOURCE_EMAIL_OVERLAP")
                    external_phone = norm_phone(row.get("phone"))
                    internal_phone = norm_phone(crm_record.get("phone") or crm_record.get("mobilephone"))
                    if external_phone and not internal_phone:
                        flags.append("CRM_PHONE_EMPTY_SOURCE_HAS_VALUE")
                    elif external_phone and internal_phone and external_phone != internal_phone:
                        flags.append("PHONE_CONFLICT")
                    source_org = (row.get("company") or "").strip().casefold()
                    crm_org = (crm_record.get("company") or "").strip().casefold()
                    if source_org and crm_org and source_org != crm_org:
                        flags.append("COMPANY_DISAGREEMENT")
                    if "CROSS_SOURCE_EMAIL_OVERLAP" in flags:
                        verdict = "CROSS_SOURCE_REVIEW"
                    elif flags:
                        verdict = "FIELD_REVIEW"
                    else:
                        verdict = "MATCH_REVIEW"
            details.append({
                "source": name, "source_record_id": row["source_record_id"].strip(),
                "candidate_crm_id": crm_id, "verdict": verdict, "flags": sorted(flags),
                "automatic_action_allowed": False,
            })
    details.sort(key=lambda r: (r["source"], r["source_record_id"]))
    counts = dict(sorted(Counter(row["verdict"] for row in details).items()))
    all_flags = dict(sorted(Counter(flag for row in details for flag in row["flags"]).items()))
    return {
        "schema": VERSION,
        "mode": "OFFLINE_READ_ONLY",
        "status": "INPUT_INCOMPLETE_HOLD" if missing_sources else "CANDIDATES_EVALUATED_HOLD",
        "write_authority": "NONE", "can_import": False, "can_merge": False,
        "can_enable_sync": False, "crm_mutations": [],
        "limitations": [
            "Source CSV snapshots are not proof of current Data Studio activation state.",
            "Primary-email comparison is candidate matching, not person identity proof.",
            "Secondary email addresses and exact HubSpot property history are not evaluated.",
            "No sync schedule, license, HubSpot Credits, workflow or permission check is performed.",
        ],
        "crm": {"rows": len(crm), "distinct_ids": len(crm_ids),
                "distinct_primary_emails": len(crm_by_email),
                "duplicate_primary_email_groups": sum(len(v) > 1 for v in crm_by_email.values()),
                "sha256": crm_digest},
        "source_snapshots": {name: {"rows": len(rows), "sha256": source_digests[name]}
                             for name, rows in sorted(source_rows.items())},
        "required_source_names": list(required_sources),
        "missing_source_snapshots": missing_sources,
        "cross_source_email_overlap_groups": sum(len(v) > 1 for v in email_to_sources.values()),
        "verdict_counts": counts,
        "flag_counts": all_flags,
        "candidates": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crm", required=True, type=Path, help="HubSpot contact CSV snapshot")
    parser.add_argument("--source", action="append", default=[], metavar="NAME=PATH",
                        help="Repeat per external source; sources remain in separate namespaces")
    parser.add_argument("--required-source", action="append", default=[], metavar="NAME",
                        help="Override default three required source names by repeating this option")
    parser.add_argument("--out", default="-", help="JSON output file; '-' writes stdout")
    args = parser.parse_args(argv)
    try:
        pairs = [source_spec(spec) for spec in args.source]
        sources = dict(pairs)
        if len(sources) != len(pairs):
            raise InvalidInput("duplicate --source namespace")
        required = tuple(args.required_source or DEFAULT_SOURCES)
        if len(set(required)) != len(required) or any(not SOURCE_RE.fullmatch(n) for n in required):
            raise InvalidInput("required source names must be unique and valid")
        report = evaluate(args.crm, sources, required)
        code = 3 if report["missing_source_snapshots"] else 0
    except InvalidInput as exc:
        report = {"schema": VERSION, "mode": "OFFLINE_READ_ONLY",
                  "status": "INVALID_INPUT_HOLD", "error": str(exc), "can_enable_sync": False,
                  "write_authority": "NONE", "crm_mutations": []}
        code = 2
    rendered = json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if args.out == "-":
        sys.stdout.write(rendered)
    else:
        Path(args.out).write_text(rendered, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
