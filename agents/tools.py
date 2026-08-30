"""
AEGIS-Ω Agent Tool Registry
============================
Real tool implementations that agents invoke through Claude's tool_use API.
No API keys required for web_search or fetch_url — they work in any environment.
Redis-backed memory tools require REDIS_URL (same as coordinator.py).

Tool schema follows Anthropic tool_use format exactly. Each tool is:
  • executable — does real I/O, not simulated
  • auditable  — every call is logged to the chain observation
  • bounded     — hard timeouts + output size limits prevent runaway costs

Available tools:
  web_search(query, max_results=5)       — DuckDuckGo HTML scrape, no key
  fetch_url(url, max_bytes=16384)        — httpx GET, text extraction
  current_datetime()                     — UTC ISO-8601, deterministic
  read_memory(namespace, key)            — Redis KV read
  write_memory(namespace, key, value)    — Redis KV write (TTL 7 days)
  search_github(query, type="code")      — GitHub search API (60 req/hr anon)
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx
import redis.asyncio as aioredis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_MEMORY_TTL = 60 * 60 * 24 * 7  # 7 days

# ── Tool schemas (Anthropic tool_use format) ──────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "web_search",
        "description": (
            "Search the web using DuckDuckGo. Returns text snippets from the top "
            "results. Use for current market data, competitor research, pricing, "
            "news, and any information not in your training data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. Be specific — include company names, dates, prices.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of result snippets (1–10). Default 5.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch the text content of a URL. Use to read documentation pages, "
            "pricing pages, LinkedIn profiles, arXiv papers, or any specific URL "
            "found in search results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch (https only)."},
                "max_bytes": {
                    "type": "integer",
                    "description": "Maximum response bytes to return (default 16384, max 65536).",
                    "default": 16384,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "search_github",
        "description": (
            "Search GitHub repositories, code, issues, or users. Use for researching "
            "competitors' open-source projects, finding potential technical partners, "
            "or auditing codebases."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "GitHub search query."},
                "search_type": {
                    "type": "string",
                    "enum": ["repositories", "code", "issues", "users"],
                    "description": "What to search for (default: repositories).",
                    "default": "repositories",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return (1–20, default 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_memory",
        "description": (
            "Read a value from the agent's persistent memory (Redis KV store). "
            "Use to recall prior research, decisions, or accumulated knowledge "
            "from previous runs. Keys are namespaced by agent role automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Memory key (e.g. 'target_accounts', 'icp_profile').",
                },
            },
            "required": ["key"],
        },
    },
    {
        "name": "write_memory",
        "description": (
            "Persist a value to the agent's memory (Redis KV store, 7-day TTL). "
            "Use to save research findings, decisions, and work products so future "
            "runs can build on prior work instead of starting from scratch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Memory key (namespaced automatically).",
                },
                "value": {
                    "type": "string",
                    "description": "Value to store (JSON string or plain text, max 64KB).",
                },
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "current_datetime",
        "description": "Returns the current UTC date and time in ISO-8601 format.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "run_python",
        "description": (
            "Execute a Python snippet and return stdout + stderr. "
            "Use for data analysis, calculations, parsing structured data, "
            "generating CSV/JSON output, or any computation that Claude cannot "
            "do precisely in prose. Only stdlib + numpy/pandas if available. "
            "No network calls inside the snippet. Timeout: 15 seconds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Use print() for output.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (max 15).",
                    "default": 10,
                },
            },
            "required": ["code"],
        },
    },
]

# ── Per-role tool specialization ──────────────────────────────────────────────
# Different departments get different tool subsets.
# This is enforced by tool_runner when building the tool list for each agent.

ROLE_TOOLS: dict[str, list[str]] = {
    # Research roles — deep web access + code execution for analysis
    "strategy":              ["web_search", "fetch_url", "search_github", "read_memory", "write_memory", "current_datetime", "run_python"],
    "ai_research":           ["web_search", "fetch_url", "search_github", "read_memory", "write_memory", "current_datetime", "run_python"],
    "applied_science":       ["web_search", "fetch_url", "search_github", "read_memory", "write_memory", "run_python"],
    "deep_researcher":       ["web_search", "fetch_url", "search_github", "read_memory", "write_memory", "current_datetime", "run_python"],
    "corpus_ingestor":       ["web_search", "fetch_url", "read_memory", "write_memory", "run_python"],
    # Engineering roles — code execution + GitHub access
    "engineering":           ["search_github", "fetch_url", "read_memory", "write_memory", "run_python", "current_datetime"],
    "platform_engineering":  ["search_github", "fetch_url", "read_memory", "write_memory", "run_python"],
    "hardware_engineering":  ["web_search", "fetch_url", "read_memory", "write_memory", "run_python"],
    # Data roles — code execution for analysis
    "data_labeling":         ["run_python", "read_memory", "write_memory"],
    "data_governance":       ["run_python", "read_memory", "write_memory", "fetch_url"],
    "batch_processor":       ["run_python", "read_memory", "write_memory", "current_datetime"],
    # Commercial roles — market research + web + contact finding
    "marketing":             ["web_search", "fetch_url", "read_memory", "write_memory", "current_datetime"],
    "biz_dev":               ["web_search", "fetch_url", "search_github", "read_memory", "write_memory", "current_datetime"],
    "partnerships":          ["web_search", "fetch_url", "search_github", "read_memory", "write_memory"],
    "sales":                 ["web_search", "fetch_url", "search_github", "read_memory", "write_memory", "current_datetime"],
    "solutions_engineering": ["web_search", "fetch_url", "search_github", "read_memory", "write_memory", "run_python"],
    "customer_success":      ["web_search", "fetch_url", "read_memory", "write_memory", "current_datetime"],
    "product_management":    ["web_search", "fetch_url", "read_memory", "write_memory", "current_datetime", "run_python"],
    # Finance + analysis roles
    "finance":               ["web_search", "fetch_url", "run_python", "read_memory", "write_memory", "current_datetime"],
    "corporate_development": ["web_search", "fetch_url", "run_python", "read_memory", "write_memory"],
    # Security roles — GitHub + web for threat intel
    "cybersecurity":         ["web_search", "fetch_url", "search_github", "read_memory", "write_memory", "run_python"],
    "ai_safety":             ["web_search", "fetch_url", "search_github", "read_memory", "write_memory"],
    "compliance":            ["web_search", "fetch_url", "read_memory", "write_memory"],
    # Default for all unlisted roles
    "_default":              ["web_search", "fetch_url", "read_memory", "write_memory", "current_datetime"],
}


def tools_for_role(role: str) -> list[dict]:
    """Return the tool schemas allowed for a given agent role."""
    allowed = ROLE_TOOLS.get(role, ROLE_TOOLS["_default"])
    schema_by_name = {s["name"]: s for s in TOOL_SCHEMAS}
    return [schema_by_name[name] for name in allowed if name in schema_by_name]


# ── Tool implementations ──────────────────────────────────────────────────────

async def web_search(query: str, max_results: int = 5) -> str:
    """Scrape DuckDuckGo HTML — no API key, works in any environment."""
    max_results = max(1, min(10, max_results))
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "us-en"},
                headers=headers,
            )
        html = resp.text

        # Extract result blocks: title + snippet pairs
        results: list[str] = []

        # Parse result__title and result__snippet using simple regex
        title_pattern = re.compile(
            r'class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        titles = title_pattern.findall(html)
        snippets = [re.sub(r"<[^>]+>", "", s).strip() for _, s in titles]
        raw_snippets = snippet_pattern.findall(html)

        for i, (url, title) in enumerate(titles[:max_results]):
            title_clean = re.sub(r"<[^>]+>", "", title).strip()
            snip = ""
            if i < len(raw_snippets):
                snip = re.sub(r"<[^>]+>", " ", raw_snippets[i]).strip()
                snip = re.sub(r"\s+", " ", snip)
            results.append(f"[{i+1}] {title_clean}\n  URL: {url}\n  {snip}")

        if not results:
            # Fallback: strip all HTML and return the first useful text block
            plain = re.sub(r"<[^>]+>", " ", html)
            plain = re.sub(r"\s+", " ", plain)
            lines = [l.strip() for l in plain.split("  ") if len(l.strip()) > 60]
            return "\n".join(lines[:max_results * 3])[:3000]

        return "\n\n".join(results[:max_results])
    except Exception as exc:
        return f"web_search error: {exc}"


async def fetch_url(url: str, max_bytes: int = 16384) -> str:
    """Fetch a URL and return extracted text."""
    max_bytes = max(1024, min(65536, max_bytes))
    if not url.startswith("https://") and not url.startswith("http://"):
        return "fetch_url error: only http/https URLs supported"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AEGIS-Omega/1.0)",
        "Accept": "text/html,text/plain",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        raw = resp.text[:max_bytes * 4]  # oversample, then trim after stripping tags
        # Strip HTML
        text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_bytes]
    except Exception as exc:
        return f"fetch_url error: {exc}"


async def search_github(
    query: str,
    search_type: str = "repositories",
    max_results: int = 5,
) -> str:
    """GitHub search API — 60 requests/hour without auth."""
    search_type = search_type if search_type in ("repositories", "code", "issues", "users") else "repositories"
    max_results = max(1, min(20, max_results))
    url = f"https://api.github.com/search/{search_type}"
    headers = {
        "User-Agent": "AEGIS-Omega-Agent/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    # Wire in token if available
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"q": query, "per_page": max_results}, headers=headers)
        data = resp.json()
        items = data.get("items", [])
        results = []
        for item in items:
            if search_type == "repositories":
                desc = item.get("description") or ""
                stars = item.get("stargazers_count", 0)
                lang = item.get("language") or "unknown"
                results.append(
                    f"• {item['full_name']} (⭐{stars}, {lang})\n"
                    f"  {desc}\n"
                    f"  {item['html_url']}"
                )
            elif search_type == "users":
                results.append(f"• {item['login']} — {item['html_url']}")
            else:
                title = item.get("title") or item.get("name", "")
                results.append(f"• {title}\n  {item.get('html_url', '')}")
        return "\n\n".join(results) if results else "No results found."
    except Exception as exc:
        return f"search_github error: {exc}"


async def read_memory(namespace: str, key: str) -> str:
    """Read from Redis KV. Returns empty string if not set."""
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        val = await redis.get(f"aegis:agent:{namespace}:{key}")
        await redis.aclose()
        return val or ""
    except Exception as exc:
        return f"memory_unavailable: {exc}"


async def write_memory(namespace: str, key: str, value: str) -> str:
    """Write to Redis KV with 7-day TTL."""
    if len(value) > 65536:
        value = value[:65536]
    try:
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.set(f"aegis:agent:{namespace}:{key}", value, ex=_MEMORY_TTL)
        await redis.aclose()
        return f"stored '{key}' ({len(value)} bytes, TTL 7d)"
    except Exception as exc:
        return f"write_memory error: {exc}"


def current_datetime() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


async def run_python(code: str, timeout: int = 10) -> str:
    """Execute a Python snippet in a subprocess and return combined stdout/stderr."""
    import asyncio
    timeout = max(1, min(15, timeout))
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"timeout after {timeout}s"
        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        combined = (out + ("\n[stderr]\n" + err if err.strip() else "")).strip()
        return combined[:4000] or "(no output)"
    except Exception as exc:
        return f"run_python error: {exc}"


# ── Dispatcher — called by tool_runner ───────────────────────────────────────

async def execute_tool(
    name: str,
    tool_input: dict[str, Any],
    namespace: str = "default",
) -> str:
    """Execute a named tool and return its string output."""
    try:
        if name == "web_search":
            return await web_search(
                query=tool_input["query"],
                max_results=tool_input.get("max_results", 5),
            )
        elif name == "fetch_url":
            return await fetch_url(
                url=tool_input["url"],
                max_bytes=tool_input.get("max_bytes", 16384),
            )
        elif name == "search_github":
            return await search_github(
                query=tool_input["query"],
                search_type=tool_input.get("search_type", "repositories"),
                max_results=tool_input.get("max_results", 5),
            )
        elif name == "read_memory":
            return await read_memory(namespace=namespace, key=tool_input["key"])
        elif name == "write_memory":
            return await write_memory(
                namespace=namespace,
                key=tool_input["key"],
                value=tool_input["value"],
            )
        elif name == "current_datetime":
            return current_datetime()
        elif name == "run_python":
            return await run_python(
                code=tool_input["code"],
                timeout=tool_input.get("timeout", 10),
            )
        else:
            return f"unknown_tool: {name}"
    except Exception as exc:
        return f"tool_error({name}): {exc}"
