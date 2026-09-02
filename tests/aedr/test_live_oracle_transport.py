#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.error
from email.message import Message

from scripts.aedr.live_oracle import GitHubLiveOracle


HEAD = "1" * 40
BASE = "a" * 40


class FakeResponse:
    def __init__(self, payload, headers: dict[str, str]):
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = Message()
        for key, value in headers.items():
            self.headers[key] = value

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_etag_conditional_read_reuses_304_payload_and_tracks_rate_limit(monkeypatch):
    oracle = GitHubLiveOracle("Aegis-Omega", "AEGIS-OMEGA")
    requests = []

    def fake_urlopen(req, timeout):
        requests.append(req)
        if len(requests) == 1:
            return FakeResponse(
                {"sha": HEAD},
                {
                    "ETag": '"snapshot-v1"',
                    "X-RateLimit-Remaining": "4999",
                    "X-RateLimit-Limit": "5000",
                    "X-RateLimit-Reset": "1788318000",
                    "X-RateLimit-Resource": "core",
                },
            )
        headers = Message()
        headers["X-RateLimit-Remaining"] = "4998"
        headers["X-RateLimit-Limit"] = "5000"
        headers["X-RateLimit-Reset"] = "1788318000"
        headers["X-RateLimit-Resource"] = "core"
        raise urllib.error.HTTPError(req.full_url, 304, "Not Modified", headers, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    first = oracle.get_main_sha()
    second = oracle.get_main_sha()

    assert first == second == HEAD
    second_headers = {key.lower(): value for key, value in requests[1].header_items()}
    assert second_headers["if-none-match"] == '"snapshot-v1"'
    assert oracle.rate_limit_state.remaining == 4998
    assert oracle.rate_limit_state.limit == 5000
    assert oracle.rate_limit_state.resource == "core"


def _pull(number: int):
    hex_digit = format(number % 16, "x")
    return {
        "number": number,
        "head": {"sha": hex_digit * 40},
        "base": {"sha": BASE, "ref": "main"},
        "draft": True,
        "title": f"PR {number}",
        "body": "",
        "labels": [{"name": "domain:structural"}],
        "updated_at": "2026-09-02T02:00:00Z",
    }


def test_open_pull_pagination_is_canonicalized_by_pr_number():
    oracle = GitHubLiveOracle("Aegis-Omega", "AEGIS-OMEGA")
    first_page = [_pull(number) for number in range(100, 0, -1)]
    second_page = [_pull(101)]

    def fake_get(endpoint, params=None):
        assert endpoint == "/pulls"
        return first_page if params["page"] == "1" else second_page

    oracle._get = fake_get
    pulls = oracle.list_open_pulls()

    assert [pr.number for pr in pulls] == list(range(1, 102))
    assert all(pr.labels == ("domain:structural",) for pr in pulls)
