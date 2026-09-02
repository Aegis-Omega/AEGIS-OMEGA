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
from .surface_ingestor import FalsificationSurfaceIngestor, RawArtifactMetadata


_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


class GitHubLiveOracleError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


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

    def list_run_artifacts(self, run_id: int) -> List[RawArtifactMetadata]:
        if type(run_id) is not int or run_id <= 0:
            raise GitHubLiveOracleError("INVALID_WORKFLOW_RUN_ID")

        artifacts: list[RawArtifactMetadata] = []
        page = 1
        while True:
            data = self._get(
                f"/actions/runs/{run_id}/artifacts",
                {"per_page": "100", "page": str(page)},
            )
            raw_items = data.get("artifacts", [])
            if not isinstance(raw_items, list):
                raise GitHubLiveOracleError("INVALID_ARTIFACT_RESPONSE")

            for item in raw_items:
                if not isinstance(item, Mapping):
                    raise GitHubLiveOracleError("INVALID_ARTIFACT_RECORD")
                if bool(item.get("expired", False)):
                    continue
                binding = item.get("workflow_run")
                if not isinstance(binding, Mapping):
                    raise GitHubLiveOracleError("ARTIFACT_MISSING_WORKFLOW_BINDING")
                try:
                    bound_run_id = int(binding["id"])
                    bound_head = self._validate_sha(str(binding["head_sha"]))
                    artifact_id = int(item["id"])
                    size_in_bytes = int(item["size_in_bytes"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise GitHubLiveOracleError("INVALID_ARTIFACT_BINDING") from exc
                if artifact_id <= 0 or size_in_bytes < 0:
                    raise GitHubLiveOracleError("INVALID_ARTIFACT_METADATA")

                artifacts.append(
                    RawArtifactMetadata(
                        artifact_id=artifact_id,
                        name=str(item.get("name") or ""),
                        size_in_bytes=size_in_bytes,
                        archive_download_url=str(item.get("archive_download_url") or ""),
                        workflow_run_id=bound_run_id,
                        workflow_run_head_sha=bound_head,
                    )
                )

            if len(raw_items) < 100:
                break
            page += 1

        return sorted(artifacts, key=lambda artifact: (artifact.artifact_id, artifact.name))

    def _artifact_download_headers(self, url: str) -> dict[str, str]:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise GitHubLiveOracleError("UNSAFE_ARTIFACT_DOWNLOAD_URL")

        headers = dict(self.headers)
        if parsed.hostname.lower() != "api.github.com":
            headers.pop("Authorization", None)
            headers.pop("X-GitHub-Api-Version", None)
            headers["Accept"] = "application/octet-stream"
        return headers

    def download_artifact_zip(self, artifact_id: int) -> bytes:
        if type(artifact_id) is not int or artifact_id <= 0:
            raise GitHubLiveOracleError("INVALID_ARTIFACT_ID")

        current_url = f"{self.base_url}/actions/artifacts/{artifact_id}/zip"
        opener = urllib.request.build_opener(_NoRedirect())
        max_redirects = 5

        for redirect_count in range(max_redirects + 1):
            request = urllib.request.Request(
                current_url,
                headers=self._artifact_download_headers(current_url),
                method="GET",
            )
            try:
                with opener.open(request, timeout=self.timeout_seconds) as response:
                    if urllib.parse.urlsplit(current_url).hostname == "api.github.com":
                        self._capture_rate_limit(response.headers)
                    raw = response.read(FalsificationSurfaceIngestor.MAX_ARCHIVE_BYTES + 1)
                    if len(raw) > FalsificationSurfaceIngestor.MAX_ARCHIVE_BYTES:
                        raise GitHubLiveOracleError("ARTIFACT_DOWNLOAD_EXCEEDS_SIZE_LIMIT")
                    return raw
            except urllib.error.HTTPError as exc:
                if urllib.parse.urlsplit(current_url).hostname == "api.github.com":
                    self._capture_rate_limit(exc.headers)
                if exc.code in _REDIRECT_CODES:
                    location = exc.headers.get("Location")
                    if not location:
                        raise GitHubLiveOracleError("ARTIFACT_REDIRECT_MISSING_LOCATION") from exc
                    if redirect_count >= max_redirects:
                        raise GitHubLiveOracleError("ARTIFACT_REDIRECT_LIMIT_EXCEEDED") from exc
                    current_url = urllib.parse.urljoin(current_url, location)
                    self._artifact_download_headers(current_url)
                    continue
                raise GitHubLiveOracleError(
                    f"HTTP {exc.code} downloading artifact {artifact_id}: {exc.reason}"
                ) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise GitHubLiveOracleError(
                    f"ARTIFACT_DOWNLOAD_FAILURE {artifact_id}: {exc}"
                ) from exc

        raise GitHubLiveOracleError("ARTIFACT_REDIRECT_LIMIT_EXCEEDED")
