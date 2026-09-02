from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .crypto_util import avd_digest
from .python_closure import discover_python_closure


_MAGIC = b"AEGIS-AVD-PYTHON-CLOSURE-V1\x00"
_ALLOWED_DOMAINS = {"VERIFIER", "ORACLE"}


class ClosureCommitmentError(RuntimeError):
    pass


def _record(label: bytes, payload: bytes) -> bytes:
    return (
        len(label).to_bytes(8, "big")
        + label
        + len(payload).to_bytes(8, "big")
        + payload
    )


@dataclass(frozen=True)
class PythonClosureCommitmentV1:
    protocol_version: str
    domain: str
    entry_modules: tuple[str, ...]
    paths: tuple[str, ...]
    digest: str

    @classmethod
    def compute(
        cls,
        *,
        repo_root: Path,
        domain: str,
        entry_modules: Iterable[str],
    ) -> "PythonClosureCommitmentV1":
        if domain not in _ALLOWED_DOMAINS:
            raise ClosureCommitmentError(f"INVALID_CLOSURE_DOMAIN:{domain}")

        entries = tuple(sorted(set(entry_modules)))
        if not entries:
            raise ClosureCommitmentError("EMPTY_CLOSURE_ENTRYPOINT_SET")
        for module in entries:
            if not isinstance(module, str) or not module.startswith("scripts.avd."):
                raise ClosureCommitmentError(f"INVALID_CLOSURE_ENTRYPOINT:{module!r}")

        repo_root = repo_root.resolve()
        paths = discover_python_closure(repo_root, entries)
        if not paths:
            raise ClosureCommitmentError("EMPTY_DISCOVERED_CLOSURE")

        preimage = bytearray(_MAGIC)
        preimage.extend(_record(b"domain", domain.encode("ascii")))
        for module in entries:
            preimage.extend(_record(b"entry", module.encode("utf-8")))
        for rel in paths:
            path = (repo_root / rel).resolve()
            try:
                path.relative_to(repo_root)
            except ValueError as exc:
                raise ClosureCommitmentError(f"CLOSURE_PATH_ESCAPES_ROOT:{rel}") from exc
            if not path.is_file() or path.is_symlink():
                raise ClosureCommitmentError(f"CLOSURE_PATH_NOT_REGULAR_FILE:{rel}")
            preimage.extend(_record(rel.encode("utf-8"), path.read_bytes()))

        digest = avd_digest(f"PYTHON-CLOSURE-{domain}", bytes(preimage))
        return cls(
            protocol_version="AVD_PYTHON_CLOSURE_V1",
            domain=domain,
            entry_modules=entries,
            paths=paths,
            digest=digest,
        )
