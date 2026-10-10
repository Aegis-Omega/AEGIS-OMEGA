#!/usr/bin/env python3
"""AEGIS production surface gate: verify actual app identity and bundle, not deployment status.

Read-only, stdlib only, no API credentials. Run after deployment, not as an
unrelated build PASS: python3 scripts/product_surface_gate.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

TARGETS = {
    "platform-picker": ("https://platform.aegisomega.com/", "Platform Picker"),
    "hook-generator": ("https://hooks.aegisomega.com/", "Hook Generator"),
}
MAX_HTML_BYTES = 512 * 1024
MAX_JS_BYTES = 4 * 1024 * 1024
TIMEOUT_SECONDS = 15


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._inside_title = False
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "title":
            self._inside_title = True
        if tag == "script" and attrs_map.get("src"):
            self.scripts.append(attrs_map["src"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self.title += data


def inspect_html(html: str, expected_title: str, origin: str) -> dict[str, str | bool]:
    parser = AssetParser()
    parser.feed(html)
    title = parser.title.strip()
    if "Vercel" in title and ("Protected" in title or "Log in" in html):
        return {"ok": False, "code": "DEPLOYMENT_PROTECTED", "title": title}
    if not title.startswith(expected_title + " —"):
        return {"ok": False, "code": "WRONG_PRODUCT", "title": title}
    scripts = [urllib.parse.urljoin(origin, s) for s in parser.scripts if "/assets/" in s and s.endswith(".js")]
    if len(scripts) != 1:
        return {"ok": False, "code": "BUNDLE_REFERENCE_INVALID", "title": title}
    if urllib.parse.urlparse(scripts[0]).netloc != urllib.parse.urlparse(origin).netloc:
        return {"ok": False, "code": "CROSS_ORIGIN_BUNDLE", "title": title}
    return {"ok": True, "code": "HTML_IDENTITY_OK", "title": title, "bundle_url": scripts[0]}


def _get(url: str, limit: int) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "AEGIS-ProductSurfaceGate/1.0", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        data = resp.read(limit + 1)
        if len(data) > limit:
            raise ValueError("RESPONSE_TOO_LARGE")
        if resp.status != 200:
            raise ValueError(f"HTTP_{resp.status}")
        return data, resp.geturl(), resp.headers.get("Content-Type", "")


def probe(name: str, url: str, expected_title: str) -> dict[str, str | bool]:
    result: dict[str, str | bool] = {"product": name, "url": url, "ok": False}
    try:
        html_bytes, final_url, _ = _get(url, MAX_HTML_BYTES)
        if urllib.parse.urlparse(final_url).netloc != urllib.parse.urlparse(url).netloc:
            return {**result, "code": "REDIRECTED_TO_OTHER_HOST", "final_url": final_url}
        parsed = inspect_html(html_bytes.decode("utf-8"), expected_title, url)
        result.update(parsed)
        if not parsed["ok"]:
            return result
        bundle_url = str(parsed["bundle_url"])
        js, final_js_url, mime = _get(bundle_url, MAX_JS_BYTES)
        if urllib.parse.urlparse(final_js_url).netloc != urllib.parse.urlparse(url).netloc:
            return {**result, "ok": False, "code": "JS_REDIRECTED_TO_OTHER_HOST"}
        if "javascript" not in mime.lower() or len(js) < 1000 or js[:64].lstrip().lower().startswith(b"<!doctype html"):
            return {**result, "ok": False, "code": "JS_NOT_SERVED", "content_type": mime}
        result.update({"ok": True, "code": "PRODUCT_SURFACE_OK", "bundle_sha256": hashlib.sha256(js).hexdigest()})
    except (urllib.error.URLError, UnicodeDecodeError, ValueError, TimeoutError, OSError) as exc:
        result.update({"ok": False, "code": "NETWORK_OR_CONTENT_ERROR", "detail": str(exc)[:160]})
    return result


def verify(results: list[dict[str, str | bool]]) -> bool:
    if len(results) != len(TARGETS) or not all(r.get("ok") for r in results):
        return False
    digests = [str(r.get("bundle_sha256", "")) for r in results]
    if any(len(d) != 64 for d in digests) or len(set(digests)) != len(digests):
        for r in results:
            r["ok"] = False
            r["code"] = "IDENTICAL_BUNDLE_FOR_DISTINCT_PRODUCTS"
        return False
    return True


def main() -> int:
    results = [probe(name, url, expected) for name, (url, expected) in TARGETS.items()]
    passed = verify(results)
    print(json.dumps({"gate": "AEGIS_PRODUCT_SURFACE_V1", "passed": passed, "results": results}, sort_keys=True))
    for r in results:
        print(f"{r['product']}: {r.get('code')} (ok={r.get('ok')})", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
