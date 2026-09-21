"""Deterministic, secret-safe notebook evidence summaries.

A notebook is an evidence container, never an authority grant. This module
hash-pins the complete notebook bytes, catalogs structural metadata, and detects
credential-like material without persisting the credential values.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    SovereignExecutionError,
    canonical_hash,
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FUNCTION_RE = re.compile(r"^(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "credential_assignment",
        re.compile(
            r"""(?im)\b(?:KAGGLE_KEY|API_KEY|ACCESS_TOKEN|TOKEN|PASSWORD|SECRET|PRIVATE_KEY)\b\s*=\s*["'][^"']+["']"""
        ),
    ),
    (
        "credential_json",
        re.compile(
            r"""(?im)["'](?:key|api_key|access_token|token|password|secret|private_key)["']\s*:\s*["'][^"']+["']"""
        ),
    ),
    (
        "private_key_material",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
)


@dataclass(frozen=True)
class NotebookEvidenceSummary:
    schema_version: str
    notebook_sha256: str
    source_label: str
    source_locator_root: str
    notebook_format: int
    notebook_format_minor: int
    cell_count: int
    code_cell_count: int
    markdown_cell_count: int
    function_names: tuple[str, ...]
    secret_categories: tuple[str, ...]
    secret_finding_count: int
    distribution_status: str
    authority_effect: str = "NONE"
    scope: str = "EVIDENCE_ONLY"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("NOTEBOOK_EVIDENCE_SCHEMA_UNSUPPORTED")
        if not SHA256_RE.fullmatch(self.notebook_sha256):
            raise SovereignExecutionError("NOTEBOOK_EVIDENCE_SHA256_INVALID")
        if not SHA256_RE.fullmatch(self.source_locator_root):
            raise SovereignExecutionError("NOTEBOOK_SOURCE_LOCATOR_ROOT_INVALID")
        if not isinstance(self.source_label, str) or not self.source_label.strip():
            raise SovereignExecutionError("NOTEBOOK_SOURCE_LABEL_INVALID")
        if self.notebook_format < 0 or self.notebook_format_minor < 0:
            raise SovereignExecutionError("NOTEBOOK_FORMAT_INVALID")
        for value in (self.cell_count, self.code_cell_count, self.markdown_cell_count, self.secret_finding_count):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise SovereignExecutionError("NOTEBOOK_COUNT_INVALID")
        if self.code_cell_count + self.markdown_cell_count > self.cell_count:
            raise SovereignExecutionError("NOTEBOOK_CELL_COUNTS_INCONSISTENT")
        if tuple(sorted(set(self.function_names))) != self.function_names:
            raise SovereignExecutionError("NOTEBOOK_FUNCTION_CATALOG_NONCANONICAL")
        if tuple(sorted(set(self.secret_categories))) != self.secret_categories:
            raise SovereignExecutionError("NOTEBOOK_SECRET_CATEGORIES_NONCANONICAL")
        expected_status = "REDACTION_REQUIRED" if self.secret_finding_count else "STRUCTURALLY_SAFE"
        if self.distribution_status != expected_status:
            raise SovereignExecutionError("NOTEBOOK_DISTRIBUTION_STATUS_MISMATCH")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("NOTEBOOK_AUTHORITY_EFFECT_INVALID")
        if self.scope != "EVIDENCE_ONLY":
            raise SovereignExecutionError("NOTEBOOK_SCOPE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_NOTEBOOK_EVIDENCE_V1", asdict(self))


def summarize_notebook_bytes(
    data: bytes,
    *,
    source_label: str,
    source_locator: str,
) -> NotebookEvidenceSummary:
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise SovereignExecutionError("NOTEBOOK_BYTES_INVALID")
    try:
        notebook = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SovereignExecutionError("NOTEBOOK_JSON_INVALID") from exc
    if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
        raise SovereignExecutionError("NOTEBOOK_STRUCTURE_INVALID")

    cells = notebook["cells"]
    code_count = 0
    markdown_count = 0
    functions: set[str] = set()
    secret_categories: set[str] = set()
    secret_count = 0

    for cell in cells:
        if not isinstance(cell, dict):
            raise SovereignExecutionError("NOTEBOOK_CELL_INVALID")
        cell_type = cell.get("cell_type")
        if cell_type == "code":
            code_count += 1
        elif cell_type == "markdown":
            markdown_count += 1

        source = cell.get("source", [])
        if isinstance(source, list):
            text = "".join(str(item) for item in source)
        elif isinstance(source, str):
            text = source
        else:
            raise SovereignExecutionError("NOTEBOOK_CELL_SOURCE_INVALID")

        functions.update(FUNCTION_RE.findall(text))
        for category, pattern in SECRET_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                secret_categories.add(category)
                secret_count += len(matches)

    digest = hashlib.sha256(bytes(data)).hexdigest()
    locator_root = canonical_hash("AEGIS_NOTEBOOK_SOURCE_LOCATOR_V1", source_locator)

    summary = NotebookEvidenceSummary(
        schema_version=SCHEMA_VERSION,
        notebook_sha256=digest,
        source_label=source_label.strip(),
        source_locator_root=locator_root,
        notebook_format=int(notebook.get("nbformat", 0)),
        notebook_format_minor=int(notebook.get("nbformat_minor", 0)),
        cell_count=len(cells),
        code_cell_count=code_count,
        markdown_cell_count=markdown_count,
        function_names=tuple(sorted(functions)),
        secret_categories=tuple(sorted(secret_categories)),
        secret_finding_count=secret_count,
        distribution_status="REDACTION_REQUIRED" if secret_count else "STRUCTURALLY_SAFE",
    )
    summary.validate()
    return summary
