from __future__ import annotations

import pytest

from scripts.avd.offline_toolchain import (
    OfflineToolchainReceiptV1,
    ToolchainReceiptError,
)


BASE_DIGEST = "sha256:18ebf3da56e60e3ddfd7d4e51f4c53d10241a129f34e93dacbc71562dd43c57a"


def _payload(**overrides):
    payload = {
        "schema_version": "AVD-OFFLINE-TOOLCHAIN-V1",
        "authority_class": "NONE",
        "base_image_digest": BASE_DIGEST,
        "coq_version": "8.20.1",
        "corn_version": "9.0.0",
        "ocaml_version": "4.13.1",
        "installed_packages_sha256": "1" * 64,
        "sealed_image_id": "sha256:" + "2" * 64,
        "offline_network_mode": "none",
        "offline_coqc_passed": True,
        "offline_corn_import_passed": True,
        "persistence_class": "EPHEMERAL_RUN_LOCAL",
        "package_lock_sha256": None,
        "sealed_image_tar_sha256": None,
        "opam_repository_commit": None,
    }
    payload.update(overrides)
    return payload


def test_offline_execution_and_frozen_closure_are_distinct_states() -> None:
    receipt = OfflineToolchainReceiptV1.from_dict(_payload())
    assert receipt.offline_toolchain_executable is True
    assert receipt.frozen_toolchain_closure is False


def test_persistent_content_addressed_closure_can_be_frozen() -> None:
    receipt = OfflineToolchainReceiptV1.from_dict(
        _payload(
            persistence_class="PERSISTENT_CONTENT_ADDRESSED",
            package_lock_sha256="3" * 64,
            sealed_image_tar_sha256="4" * 64,
            opam_repository_commit="5" * 40,
        )
    )
    assert receipt.offline_toolchain_executable is True
    assert receipt.frozen_toolchain_closure is True


def test_network_or_dependency_probe_failure_fails_closed() -> None:
    with pytest.raises(ToolchainReceiptError, match="OFFLINE_NETWORK_MODE_NOT_NONE"):
        OfflineToolchainReceiptV1.from_dict(_payload(offline_network_mode="bridge"))
    with pytest.raises(ToolchainReceiptError, match="CORN_IMPORT_PROBE_NOT_PASSED"):
        OfflineToolchainReceiptV1.from_dict(_payload(offline_corn_import_passed=False))


def test_authority_widening_and_unknown_fields_are_rejected() -> None:
    with pytest.raises(ToolchainReceiptError, match="AUTHORITY_MUST_BE_NONE"):
        OfflineToolchainReceiptV1.from_dict(_payload(authority_class="FORMAL_MATH_EVIDENCE_ONLY"))
    bad = _payload()
    bad["extra"] = True
    with pytest.raises(ToolchainReceiptError, match="TOOLCHAIN_RECEIPT_SURFACE_MISMATCH"):
        OfflineToolchainReceiptV1.from_dict(bad)


def test_claiming_persistent_closure_requires_all_freeze_material() -> None:
    with pytest.raises(ToolchainReceiptError, match="PERSISTENT_CLOSURE_MATERIAL_INCOMPLETE"):
        OfflineToolchainReceiptV1.from_dict(
            _payload(
                persistence_class="PERSISTENT_CONTENT_ADDRESSED",
                package_lock_sha256="3" * 64,
            )
        )
