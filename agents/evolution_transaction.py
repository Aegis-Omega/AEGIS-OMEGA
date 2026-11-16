"""Recoverable, fail-closed, demotion-only two-file evolution transaction.

The durable preparation journal makes crashes *detectable*, not truly atomic
to readers of two independent files. Only cooperative EvolutionEngine writers
use its lock. Other writers/readers must be migrated separately. The journal
is a SHA-256 integrity record, never a cryptographic authorization signature.
"""
from __future__ import annotations

from dataclasses import asdict
import copy
try:
    import fcntl  # POSIX advisory lock for cooperating writers
except ImportError:
    fcntl = None  # Read-only operations stay usable; mutations fail closed.
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

from harness.sdk.skill_authority import canonical_bytes, compute_registry_root, evaluate_registry

SCHEMA = "AEGIS_EVOLUTION_TRANSACTION_V1"
TIERS = ("T0", "T1", "T2", "T3", "T4", "T5")
MAX_SIZE = 8 * 1024 * 1024


class EvolutionTransactionError(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise EvolutionTransactionError(reason)


def journal_path(tree_path: str | Path) -> Path:
    p = Path(tree_path)
    return p.with_name(p.name + ".evolution.pending.json")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def secure_path(path: Path) -> None:
    require(path.is_absolute() and path.parent.is_dir(), "PATH_NOT_ABSOLUTE_OR_PARENT_MISSING")
    require(not path.is_symlink() and path.resolve(strict=False) == path, "SYMLINK_TARGET_OR_PARENT")


def sync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path: Path, data: bytes) -> None:
    secure_path(path)
    require(not path.exists() or path.is_file(), "UNSAFE_TARGET")
    require(len(data) <= MAX_SIZE, "SNAPSHOT_TOO_LARGE")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".aegis-evolution-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def inspect_pending(tree_path: str | Path, lineage_path: str | Path) -> dict[str, Any]:
    """Read-only state classification. Never silently repairs or removes a journal."""
    tree, lineage = Path(tree_path), Path(lineage_path)
    pending = journal_path(tree)
    if not pending.exists() and not pending.is_symlink():
        return {"status": "CLEAN"}
    try:
        secure_path(pending)
        require(pending.stat().st_size <= MAX_SIZE, "JOURNAL_TOO_LARGE")
        journal = json.loads(pending.read_text(encoding="utf-8"))
        require(isinstance(journal, dict) and journal.get("schema_version") == SCHEMA,
                "JOURNAL_SCHEMA_INVALID")
        supplied = journal.pop("journal_sha256", None)
        require(isinstance(supplied, str) and supplied == digest(canonical_bytes(journal)),
                "JOURNAL_HASH_INVALID")
        files = {}
        for label, target in (("registry", tree), ("lineage", lineage)):
            secure_path(target)
            actual = digest(target.read_bytes()) if target.exists() else None
            old = journal.get("old_" + label + "_sha256")
            new = journal.get("new_" + label + "_sha256")
            files[label] = "NEW" if actual == new else "OLD" if actual == old else "DIVERGED"
        if "DIVERGED" in files.values():
            status = "DIVERGED"
        elif all(x == "NEW" for x in files.values()):
            status = "READY_FOR_EXPLICIT_FINALIZATION"
        elif all(x == "OLD" for x in files.values()):
            status = "PREPARED_NOT_APPLIED"
        else:
            status = "PARTIAL_COMMIT"
        return {"status": status, "files": files, "journal_sha256": supplied}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {"status": "INVALID_PENDING_JOURNAL", "reason": type(exc).__name__}


def commit_demotions(*, tree_path: str | Path, lineage_path: str | Path,
                     next_tree: dict[str, Any], next_lineage: Any,
                     repo_root: str | Path, fault_after: str | None = None) -> str:
    """Journaled commit for a validated demotion-only pair, no promotions.

    A failure after preparing the journal leaves a durable barrier. Consumers
    of the registry without inspect_pending() are not yet protected. No
    automated recovery/rollback, which requires a separately authorized tool.
    """
    require(fcntl is not None, "ADVISORY_LOCK_BACKEND_UNAVAILABLE")
    tree = Path(os.path.abspath(os.fspath(tree_path)))
    lineage = Path(os.path.abspath(os.fspath(lineage_path)))
    root = Path(repo_root).resolve()
    secure_path(tree)
    secure_path(lineage)
    require(tree.is_file() and tree != lineage, "REGISTRY_MISSING_OR_TARGETS_OVERLAP")
    require(tree.is_relative_to(root) and lineage.is_relative_to(root), "OUTSIDE_REPOSITORY")
    lock = tree.with_name(tree.name + ".evolution.lock")
    pending = journal_path(tree)
    secure_path(lock)
    fd = os.open(str(lock), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise EvolutionTransactionError("UNSAFE_LOCK_FILE")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise EvolutionTransactionError("CONCURRENT_WRITER") from exc
    try:
        require(not pending.exists() and not pending.is_symlink(),
                "UNRESOLVED_EVOLUTION_TRANSACTION")
        original_tree = tree.read_bytes()
        old_tree = json.loads(original_tree)
        require(evaluate_registry(old_tree, repo_root=root).outcome == "ADMITTED",
                "BASE_REGISTRY_NOT_ADMITTED")
        from agents.evolution import AdaptiveLineage, _demotion_evidence_fingerprint
        old_lineage = AdaptiveLineage.load(lineage)
        require(old_lineage.verify_chain()[0], "BASE_LINEAGE_INVALID")
        original_lineage = lineage.read_bytes() if lineage.exists() else None
        require(next_lineage.verify_chain()[0], "NEXT_LINEAGE_INVALID")

        new_tree = copy.deepcopy(next_tree)
        root_hash = compute_registry_root(new_tree)
        require(new_tree.get("registry_root") == root_hash and
                new_tree.get("genesis_seal") == root_hash, "TARGET_ROOT_NOT_BOUND")
        before_skills = old_tree.get("skills")
        after_skills = new_tree.get("skills")
        require(isinstance(before_skills, list) and isinstance(after_skills, list)
                and len(before_skills) == len(after_skills), "SKILL_SET_CHANGED")
        before_by_id = {s["skill_id"]: s for s in before_skills}
        require(len(before_by_id) == len(before_skills), "DUPLICATE_BASE_SKILL")
        target_ids = [skill.get("skill_id") for skill in after_skills]
        require(all(isinstance(sid, str) and sid for sid in target_ids),
                "INVALID_TARGET_SKILL_ID")
        require(len(set(target_ids)) == len(target_ids), "DUPLICATE_TARGET_SKILL")
        require(set(target_ids) == set(before_by_id), "SKILL_ID_SET_CHANGED")
        require(evaluate_registry(new_tree, repo_root=root).outcome == "ADMITTED",
                "TARGET_REGISTRY_NOT_ADMITTED")
        changed = {}
        for skill in after_skills:
            sid = skill.get("skill_id")
            require(sid in before_by_id, "UNKNOWN_TARGET_SKILL")
            previous = before_by_id[sid]
            first, second = previous.get("tier"), skill.get("tier")
            require(first in TIERS and second in TIERS, "TIER_INVALID")
            require(TIERS.index(second) >= TIERS.index(first), "PROMOTION_NOT_SUPPORTED")
            left, right = dict(previous), dict(skill)
            left.pop("tier", None)
            right.pop("tier", None)
            require(left == right, "OBSERVATION_CHANGED_DURING_COMMIT")
            if first != second:
                require(TIERS.index(second) == TIERS.index(first) + 1,
                        "MULTI_TIER_DEMOTION")
                changed[sid] = (first, second)
        require(bool(changed), "EMPTY_TRANSACTION")
        root_before, root_after = dict(old_tree), dict(new_tree)
        for key in ("skills", "registry_root", "genesis_seal"):
            root_before.pop(key, None)
            root_after.pop(key, None)
        require(root_before == root_after, "REGISTRY_METADATA_CHANGED")
        old_events, new_events = old_lineage.events, next_lineage.events
        require(len(new_events) == len(old_events) + len(changed), "LINEAGE_DELTA_COUNT_MISMATCH")
        require([asdict(x) for x in new_events[:len(old_events)]] ==
                [asdict(x) for x in old_events], "LINEAGE_PRIOR_EVENTS_CHANGED")
        observed = set()
        for event in new_events[len(old_events):]:
            require(event.event_type == "TIER_DEMOTION" and event.skill_id in changed,
                    "NON_DEMOTION_EVENT")
            require(event.skill_id not in observed, "DUPLICATE_DEMOTION_EVENT")
            require((event.from_tier, event.to_tier) == changed[event.skill_id],
                    "DEMOTION_EVENT_TIER_MISMATCH")
            proof = "obs=" + _demotion_evidence_fingerprint(before_by_id[event.skill_id])
            require(event.evidence.endswith(proof), "DEMOTION_EVIDENCE_FINGERPRINT_INVALID")
            require(not any(
                prior.event_type == "TIER_DEMOTION" and prior.skill_id == event.skill_id
                and prior.evidence.endswith(proof) for prior in old_events
            ), "REPLAYED_DEMOTION_EVIDENCE")
            observed.add(event.skill_id)

        registry_bytes = (json.dumps(new_tree, indent=2, ensure_ascii=False, allow_nan=False) +
                          "\n").encode("utf-8")
        lineage_bytes = (json.dumps({
            "genesis_hash": "0" * 64,
            "terminal_hash": next_lineage.terminal_hash(),
            "event_count": len(new_events),
            "events": [asdict(e) for e in new_events],
        }, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        require(max(len(registry_bytes), len(lineage_bytes)) <= MAX_SIZE, "SNAPSHOT_TOO_LARGE")
        journal = {
            "schema_version": SCHEMA,
            "old_registry_sha256": digest(original_tree),
            "new_registry_sha256": digest(registry_bytes),
            "old_lineage_sha256": digest(original_lineage) if original_lineage is not None else None,
            "new_lineage_sha256": digest(lineage_bytes),
            "base_registry_root": old_tree["registry_root"],
            "new_registry_root": new_tree["registry_root"],
            "base_lineage_head": old_lineage.terminal_hash(),
            "new_lineage_head": next_lineage.terminal_hash(),
            "demotion_skill_ids": sorted(changed),
        }
        journal["journal_sha256"] = digest(canonical_bytes(journal))
        prepared = canonical_bytes(journal)
        require(len(prepared) <= MAX_SIZE, "JOURNAL_TOO_LARGE")
        prepared_fd = os.open(str(pending), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                              getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(prepared_fd, "wb") as stream:
            stream.write(prepared)
            stream.flush()
            os.fsync(stream.fileno())
        sync_dir(pending.parent)
        if fault_after == "journal":
            raise EvolutionTransactionError("INJECTED_CRASH_AFTER_JOURNAL")
        require(digest(tree.read_bytes()) == journal["old_registry_sha256"],
                "CONCURRENT_REGISTRY_MUTATION")
        require((digest(lineage.read_bytes()) if lineage.exists() else None) ==
                journal["old_lineage_sha256"], "CONCURRENT_LINEAGE_MUTATION")

        # Lineage first, before the authority-bearing registry.
        if lineage.exists():
            atomic_write(lineage, lineage_bytes)
        else:
            first_fd = os.open(str(lineage), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                               getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(first_fd, "wb") as stream:
                stream.write(lineage_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            sync_dir(lineage.parent)
        if fault_after == "lineage":
            raise EvolutionTransactionError("INJECTED_CRASH_AFTER_LINEAGE")
        atomic_write(tree, registry_bytes)
        if fault_after == "registry":
            raise EvolutionTransactionError("INJECTED_CRASH_AFTER_REGISTRY")
        require(inspect_pending(tree, lineage)["status"] == "READY_FOR_EXPLICIT_FINALIZATION",
                "POST_COMMIT_EVIDENCE_MISMATCH")
        pending.unlink()
        sync_dir(pending.parent)
        return journal["journal_sha256"]
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
