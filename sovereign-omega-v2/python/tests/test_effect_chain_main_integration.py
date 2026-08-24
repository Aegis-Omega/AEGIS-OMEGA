"""Main-integration falsifiers for the PR-1 through PR-4 effect chain.

These tests exercise the production adapters and evidence scripts.  They prevent
an integrated candidate from retaining the older PR-2 receipt scope after
VerifyEffect and CompleteVerification have been added.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.effect_adapters import (
    EFFECT_WITNESS_KIND,
    EffectAdapterError,
    EffectWitness,
    FilesystemEffectAdapter,
    filesystem_state_commitment,
    is_adapter_bound_effect_evidence,
)
from harness.sdk.effect_verifier import FALSE, EffectVerifier
from harness.sdk.sovereign_execution import SCHEMA_VERSION
from harness.sdk.transition_receipts import (
    EXECUTION_RECEIPT_KIND,
    EXECUTION_SUCCEEDED,
    ExecutionReceipt,
    TransitionIdentity,
    admission_policy_commitment,
    verifier_policy_commitment,
)


HASHES = [f"{index:064x}" for index in range(1, 32)]


def _transition(*, pre_state_commitment: str) -> TransitionIdentity:
    return TransitionIdentity(
        schema_version=SCHEMA_VERSION,
        source_commit="c" * 40,
        pre_state_commitment=pre_state_commitment,
        identity_root=HASHES[1],
        delegation_commitment=HASHES[2],
        capability_commitment=HASHES[3],
        action_digest=HASHES[4],
        deterministic_nonce="nonce-main-effect-chain-integration",
        fence_commitment=HASHES[5],
        verifier_policy_commitment=verifier_policy_commitment(),
        admission_policy_commitment=admission_policy_commitment(),
    )


def _execution(transition: TransitionIdentity) -> ExecutionReceipt:
    return ExecutionReceipt(
        receipt_kind=EXECUTION_RECEIPT_KIND,
        transition_id=transition.root,
        execution_instance_id="exec-main-effect-chain-integration",
        outcome=EXECUTION_SUCCEEDED,
        result_digest=HASHES[6],
    )


class EffectChainMainIntegrationTests(unittest.TestCase):
    def test_fabricated_observation_handle_cannot_be_promoted_to_effect_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            target = root / "state.txt"
            target.write_bytes(b"before")
            pre_state = filesystem_state_commitment(allowed_root=root, target=target)
            transition = _transition(pre_state_commitment=pre_state)
            execution = _execution(transition)
            adapter = FilesystemEffectAdapter(allowed_root=root)
            issued = adapter.prepare_observation(transition=transition, target=target)
            fabricated = replace(issued, pre_observation_provenance="f" * 64)
            target.write_bytes(b"after")

            with self.assertRaisesRegex(
                EffectAdapterError,
                "EFFECT_OBSERVATION_HANDLE_UNISSUED",
            ):
                adapter.observe_effect(
                    transition=transition,
                    handle=fabricated,
                    execution_receipt=execution,
                )

    def test_observation_handle_is_bound_to_the_issuing_adapter_instance(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            target = root / "state.txt"
            target.write_bytes(b"before")
            pre_state = filesystem_state_commitment(allowed_root=root, target=target)
            transition = _transition(pre_state_commitment=pre_state)
            execution = _execution(transition)
            issuer = FilesystemEffectAdapter(allowed_root=root)
            non_issuer = FilesystemEffectAdapter(allowed_root=root)
            handle = issuer.prepare_observation(transition=transition, target=target)
            target.write_bytes(b"after")

            with self.assertRaisesRegex(
                EffectAdapterError,
                "EFFECT_OBSERVATION_HANDLE_UNISSUED",
            ):
                non_issuer.observe_effect(
                    transition=transition,
                    handle=handle,
                    execution_receipt=execution,
                )

    def test_allowed_root_cannot_be_retargeted_after_adapter_construction(self) -> None:
        with tempfile.TemporaryDirectory() as first_raw, tempfile.TemporaryDirectory() as second_raw:
            adapter = FilesystemEffectAdapter(allowed_root=Path(first_raw))
            with self.assertRaisesRegex(
                EffectAdapterError,
                "EFFECT_ADAPTER_SCOPE_MISMATCH",
            ):
                adapter.allowed_root = Path(second_raw)

    def test_same_path_root_replacement_is_rejected(self) -> None:
        if os.name != "posix":
            self.skipTest("descriptor-bound root falsifier requires POSIX")
        with tempfile.TemporaryDirectory() as raw_tmp:
            base = Path(raw_tmp)
            root = base / "root"
            root.mkdir()
            target = root / "state.txt"
            target.write_bytes(b"before")
            pre_state = filesystem_state_commitment(allowed_root=root, target=target)
            transition = _transition(pre_state_commitment=pre_state)
            execution = _execution(transition)
            adapter = FilesystemEffectAdapter(allowed_root=root)
            handle = adapter.prepare_observation(transition=transition, target=target)

            root.rename(base / "old-root")
            root.mkdir()
            (root / "state.txt").write_bytes(b"replacement")

            with self.assertRaisesRegex(
                EffectAdapterError,
                "EFFECT_ADAPTER_SCOPE_MISMATCH",
            ):
                adapter.observe_effect(
                    transition=transition,
                    handle=handle,
                    execution_receipt=execution,
                )

    def test_equal_adapter_issued_witnesses_remain_independently_valid(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            target = root / "state.txt"
            target.write_bytes(b"before")
            pre_state = filesystem_state_commitment(allowed_root=root, target=target)
            transition = _transition(pre_state_commitment=pre_state)
            execution = _execution(transition)
            adapter = FilesystemEffectAdapter(allowed_root=root)
            first_handle = adapter.prepare_observation(
                transition=transition,
                target=target,
            )
            second_handle = adapter.prepare_observation(
                transition=transition,
                target=target,
            )
            target.write_bytes(b"after")
            first = adapter.observe_effect(
                transition=transition,
                handle=first_handle,
                execution_receipt=execution,
            )
            second = adapter.observe_effect(
                transition=transition,
                handle=second_handle,
                execution_receipt=execution,
            )

            self.assertEqual(first.root, second.root)
            self.assertIsNot(first, second)
            self.assertTrue(is_adapter_bound_effect_evidence(witness=first))
            self.assertTrue(is_adapter_bound_effect_evidence(witness=second))

    def test_fabricated_effect_witness_is_not_adapter_issued_evidence(self) -> None:
        transition = _transition(pre_state_commitment=HASHES[7])
        execution = _execution(transition)
        fabricated = EffectWitness(
            witness_kind=EFFECT_WITNESS_KIND,
            transition_id=transition.root,
            execution_instance_id=execution.execution_instance_id,
            target_identity="state.txt",
            observed_pre_state_commitment=transition.pre_state_commitment,
            observed_post_state_commitment=HASHES[8],
            effect_changed=True,
            pre_observation_provenance=HASHES[9],
            post_observation_provenance=HASHES[10],
            adapter_identity=FilesystemEffectAdapter.identity,
            adapter_version=FilesystemEffectAdapter.version,
        )

        self.assertFalse(is_adapter_bound_effect_evidence(witness=fabricated))
        result = EffectVerifier().verify_effect(
            transition=transition,
            execution_receipt=execution,
            witness=fabricated,
        )
        self.assertEqual(FALSE, result.status)

    def test_filesystem_observation_is_not_redirectable_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            allowed = tmp / "allowed"
            allowed.mkdir()
            target = allowed / "state.txt"
            target.write_bytes(b"inside")
            outside = tmp / "outside.txt"
            outside.write_bytes(b"outside")

            adapter = FilesystemEffectAdapter(allowed_root=allowed)
            original_open = Path.open
            resolved_target = target.resolve()

            def redirected_open(path: Path, *args: object, **kwargs: object):
                if path == resolved_target:
                    return original_open(outside, *args, **kwargs)
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", new=redirected_open):
                observation = adapter._observe_state(target)

            self.assertEqual("state.txt", observation.target_identity)
            self.assertEqual(
                hashlib.sha256(b"inside").hexdigest(),
                observation.content_sha256,
            )

    def test_filesystem_observation_enforces_explicit_size_bound(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            target = Path(raw_tmp) / "oversized.bin"
            target.write_bytes(b"123456789")
            adapter = FilesystemEffectAdapter(allowed_root=Path(raw_tmp))
            adapter.max_observation_bytes = 8

            with self.assertRaisesRegex(EffectAdapterError, "EFFECT_TARGET_TOO_LARGE"):
                adapter._observe_state(target)

    def test_concurrent_content_rewrite_with_restored_mtime_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            target = root / "state.bin"
            target.write_bytes(b"A" * (128 * 1024))
            original_stat = target.stat()
            adapter = FilesystemEffectAdapter(allowed_root=root)
            original_read = os.read
            read_count = 0

            def mutate_after_first_read(fd: int, size: int) -> bytes:
                nonlocal read_count
                chunk = original_read(fd, size)
                read_count += 1
                if read_count == 1 and chunk:
                    target.write_bytes(b"B" * (128 * 1024))
                    os.utime(
                        target,
                        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
                    )
                return chunk

            with patch.object(os, "read", new=mutate_after_first_read):
                with self.assertRaisesRegex(
                    EffectAdapterError,
                    "EFFECT_TARGET_CHANGED_DURING_OBSERVATION",
                ):
                    adapter._observe_state(target)

    def test_fifo_observation_fails_closed_without_blocking(self) -> None:
        if os.name != "posix" or not hasattr(os, "mkfifo"):
            self.skipTest("FIFO behavioral falsifier requires POSIX mkfifo")
        with tempfile.TemporaryDirectory() as raw_tmp:
            fifo = Path(raw_tmp) / "effect.fifo"
            os.mkfifo(fifo)
            probe = (
                "from pathlib import Path\n"
                "from harness.sdk.effect_adapters import EffectAdapterError, "
                "FilesystemEffectAdapter\n"
                f"root = Path({raw_tmp!r})\n"
                "try:\n"
                "    FilesystemEffectAdapter(allowed_root=root)._observe_state(root / 'effect.fifo')\n"
                "except EffectAdapterError as exc:\n"
                "    raise SystemExit(0 if str(exc) == 'EFFECT_TARGET_NOT_REGULAR_FILE' else 2)\n"
                "raise SystemExit(3)\n"
            )
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                timeout=1.0,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

if __name__ == "__main__":
    unittest.main()
