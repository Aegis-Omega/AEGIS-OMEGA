#!/usr/bin/env python3
"""Hosted DNS verification for AEGIS OpenAI custom-domain records.

Queries two independent public DNS-over-HTTPS resolvers and fails closed unless
both expected TXT records are observed by both resolvers.

Authority effect: NONE. A PASS proves public DNS visibility only; it does not
prove OpenAI has completed tenant-domain verification.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

DOMAIN = "aegisomega.com"
EXPECTED = {
    "_openai-site-verification.aegisomega.com": (
        "openai-site-verification=zchKhAC2vSCoUTOKmlHN9tiwmpzfL81-vX2oA7-nG3c"
    ),
    "_cf-custom-hostname.aegisomega.com": "958133c2-046b-4684-b34e-08ac9a553228",
}

RESOLVERS = {
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "google": "https://dns.google/resolve",
}


def normalize_txt(value: str) -> str:
    value = value.strip()
    # DoH JSON commonly returns TXT RDATA with surrounding quotes. Some
    # implementations may split TXT strings into adjacent quoted chunks.
    if value.startswith('"') and value.endswith('"'):
        parts = []
        current = ""
        escaped = False
        in_quote = False
        for ch in value:
            if escaped:
                current += ch
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                if in_quote:
                    parts.append(current)
                    current = ""
                in_quote = not in_quote
            elif in_quote:
                current += ch
        if parts:
            return "".join(parts)
    return value.strip('"')


def query_json(base: str, name: str) -> dict:
    params = urllib.parse.urlencode({"name": name, "type": "TXT"})
    req = urllib.request.Request(
        f"{base}?{params}",
        headers={
            "Accept": "application/dns-json",
            "User-Agent": "AEGIS-DNS-Verifier/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def values_from(payload: dict) -> list[str]:
    if int(payload.get("Status", -1)) != 0:
        return []
    out: list[str] = []
    for answer in payload.get("Answer") or []:
        if int(answer.get("type", 0)) == 16:
            out.append(normalize_txt(str(answer.get("data", ""))))
    return sorted(set(out))


def main() -> int:
    observations: dict[str, dict[str, object]] = {}
    all_match = True

    for host, expected in EXPECTED.items():
        observations[host] = {"expected": expected, "resolvers": {}}
        for resolver_name, resolver_url in RESOLVERS.items():
            try:
                payload = query_json(resolver_url, host)
                values = values_from(payload)
                matched = expected in values
                observations[host]["resolvers"][resolver_name] = {
                    "matched": matched,
                    "values": values,
                    "dns_status": payload.get("Status"),
                }
                all_match = all_match and matched
            except Exception as exc:  # bounded diagnostic; no secret data
                observations[host]["resolvers"][resolver_name] = {
                    "matched": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                all_match = False

    receipt = {
        "schema": "aegis.openai-domain-dns-verification.v1",
        "domain": DOMAIN,
        "authority_effect": "NONE",
        "status": "PASS" if all_match else "UNVERIFIED",
        "observations": observations,
        "limitations": [
            "PASS establishes public TXT visibility at two resolvers only.",
            "OpenAI Admin Console verification remains a separate state transition.",
            "UNVERIFIED may mean missing records, DNS propagation lag, or resolver/network failure.",
        ],
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
