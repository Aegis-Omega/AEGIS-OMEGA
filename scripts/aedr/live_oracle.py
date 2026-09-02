#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Mapping, Optional

from .acquisition_types import (
    RateLimitState,
    RawGitCompare,
    RawPullRequestRecord,
    RawWorkflowReceipt,
    WorkflowRunConclusion,
)


_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")


class GitHubLiveOracleError(Exception):
    pass


class GitHubLiveOracle:
    """Read-only GitHub REST adapter with conditional-read and rate-limit tracking."""

    def __init__(
        self,
        owner: str,
        repo: str,
        token: Optional[str] = None,
        *,
        timeout_seconds: float = 30.0,
    ):
        if not owner or not repo:
            raise ValueError("owner and repo are required")
        self.owner = owner
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AEDR-Live-Acquisition-v1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self._etag_cache: dict[str, tuple[str, Any]] = {}
        self.rate_limit_state = RateLimitState(None, None, None, None)

    @staticmethod
    def _validate_sha(sha: str) -> str:
        if not _SHA40.fullmatch(sha):
            raise GitHubLiveOracleError(f"INVALID_SHA: {sha!r}")
        return sha.lower()

    @staticmethod
    def _parse_optional_int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _capture_rate_limit(self, headers: Mapping[str, str]) -> None:
        self.rate_limit_state = RateLimitState(
            remaining=self._parse_optional_int(headers.get("X-RateLimit-Remaining")),
            limit=self._parse_optional_int(headers.get("X-RateLimit-Limit")),
            reset_epoch=self._parse_optional_int(headers.get("X-RateLimit-Reset")),
            resource=headers.get("X-RateLimit-Resource"),
        )

    def _get(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Any:
        query = urllib.parse.urlencode(sorted((params or {}).items()))
        url = f"{self.base_url}{endpoint}"
        if query:
            url = f"{url}?{query}"

        request_headers = dict(self.headers)
        cached = self._etag_cache.get(url)
        if cached:
            request_headers["If-None-Match"] = cached[0]

        req = urllib.request.Request(url, headers=request_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                self._capture_rate_limit(resp.headers)
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                etag = resp.headers.get("ETag")
                if etag:
                    self._etag_cache[url] = (etag, data)
                return data
        except urllib.error.HTTPError as exc:
            self._capture_rate_limit(exc.headers)
            if exc.code == 304 and cached:
                return cached[1]
            raise GitHubLiveOracleError(
                f"HTTP {exc.code} on {endpoint}: {exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GitHubLiveOracleError(
                f"READ_FAILURE on {endpoint}: {exc}"
            ) from exc

    def get_main_sha(self, branch: str = "main") -> str:
        safe_branch = urllib.parse.quote(branch, safe="")
        data = self._get(f"/commits/{safe_branch}")
        return self._validate_sha(str(data["sha"]))

    def list_open_pulls(self) -> List[RawPullRequestRecord]:
        prs: List[RawPullRequestRecord] = []
        page = 1
        while True:
            batch = self._get(
                "/pulls",
                {"state": "open", "per_page": "100", "page": str(page)},
            )
            if not isinstance(batch, list):
                raise GitHubLiveOracleError("INVALID_PULL_RESPONSE")
            for item in batch:
                labels = tuple(sorted(str(label["name"]) for label in item.get("labels", [])))
                prs.append(
                    RawPullRequestRecord(
                        number=int(item["number"]),
                        head_sha=self._validate_sha(str(item["head"]["sha"])),
                        base_sha=self._validate_sha(str(item["base"]["sha"])),
                        base_ref=str(item["base"]["ref"]),
                        draft=bool(item.get("draft", False)),
                        mergeable_state=str(item.get("mergeable_state") or "unknown"),
                        title=str(item.get("title") or ""),
                        body=str(item.get("body") or ""),
                        labels=labels,
                        updated_at=str(item.get("updated_at") or ""),
                    )
                )
            if len(batch) < 100:
                break
            page += 1
        return sorted(prs, key=lambda pr: pr.number)

    def compare_commits(self, base_sha: str, head_sha: str) -> RawGitCompare:
        base_sha = self._validate_sha(base_sha)
        head_sha = self._validate_sha(head_sha)
        data = self._get(f"/compare/{base_sha}...{head_sha}")
        files = tuple(sorted(str(item["filename"]) for item in data.get("files", [])))
        return RawGitCompare(
            base_sha=base_sha,
            head_sha=head_sha,
            merge_base_sha=self._validate_sha(str(data["merge_base_commit"]["sha"])),
            ahead_by=int(data["ahead_by"]),
            behind_by=int(data["behind_by"]),
            status=str(data["status"]),
            files_changed=files,
        )

    @staticmethod
    def _normalize_conclusion(run: Mapping[str, Any]) -> WorkflowRunConclusion:
        raw_conclusion = run.get("conclusion")
        raw_status = str(run.get("status") or "").lower()
        candidate = str(raw_conclusion).lower() if raw_conclusion else raw_status
        try:
            return WorkflowRunConclusion(candidate)
        except ValueError:
            return WorkflowRunConclusion.UNKNOWN

    def get_exact_head_workflow_receipts(self, head_sha: str) -> List[RawWorkflowReceipt]:
        expected_head = self._validate_sha(head_sha)
        receipts: list[RawWorkflowReceipt] = []
        page = 1
        while True:
            data = self._get(
                "/actions/runs",
                {"head_sha": expected_head, "per_page": "100", "page": str(page)},
            )
            runs = data.get("workflow_runs", [])
            if not isinstance(runs, list):
                raise GitHubLiveOracleError("INVALID_WORKFLOW_RESPONSE")
            for run in runs:
                run_head = self._validate_sha(str(run["head_sha"]))
                if run_head != expected_head:
                    continue
                receipts.append(
                    RawWorkflowReceipt(
                        run_id=int(run["id"]),
                        run_number=int(run["run_number"]),
                        workflow_name=str(run.get("name") or ""),
                        head_sha=run_head,
                        conclusion=self._normalize_conclusion(run),
                        completed_at=str(run.get("updated_at") or ""),
                        html_url=str(run.get("html_url") or ""),
                    )
                )
            if len(runs) < 100:
                break
            page += 1
        return sorted(
            receipts,
            key=lambda receipt: (receipt.workflow_name, receipt.run_number, receipt.run_id),
        )
