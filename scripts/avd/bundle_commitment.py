from __future__ import annotations

import stat
import unicodedata
from pathlib import Path


BUNDLE_MAGIC = b"AEGIS-AVD-BUNDLE-V1\x00"


def _encode_record(path: str, content: bytes) -> bytes:
    path_bytes = path.encode("utf-8")
    return (
        len(path_bytes).to_bytes(8, "big")
        + path_bytes
        + len(content).to_bytes(8, "big")
        + content
    )


def canonical_bundle_bytes(root: Path) -> bytes:
    """Return a path/content-bound deterministic byte representation.

    The bundle intentionally excludes all filesystem metadata (mtime, uid, gid,
    permissions) and refuses Git metadata, symlinks and special files. The
    resulting bytes are suitable as a commitment preimage, not as an archive
    format for execution.
    """
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("BUNDLE_ROOT_NOT_DIRECTORY")

    records: list[tuple[str, bytes]] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if ".git" in rel.parts:
            raise ValueError("GIT_METADATA_FORBIDDEN")
        normalized = unicodedata.normalize("NFC", rel.as_posix())
        if normalized != rel.as_posix():
            raise ValueError("NON_NFC_BUNDLE_PATH")

        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("SYMLINK_FORBIDDEN")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError("SPECIAL_FILE_FORBIDDEN")
        records.append((normalized, path.read_bytes()))

    records.sort(key=lambda item: item[0].encode("utf-8"))
    return BUNDLE_MAGIC + b"".join(_encode_record(path, content) for path, content in records)
