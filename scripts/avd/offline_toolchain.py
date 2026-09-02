from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_BASE_IMAGE_DIGEST = (
    "sha256:18ebf3da56e60e3ddfd7d4e51f4c53d10241a129f34e93dacbc71562dd43c57a"
)
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_FIELDS = {
    "schema_version",
    "authority_class",
    "base_image_digest",
    "coq_version",
    "corn_version",
    "ocaml_version",
    "installed_packages_sha256",
    "sealed_image_id",
    "offline_network_mode",
    "offline_coqc_passed",
    "offline_corn_import_passed",
    "persistence_class",
    "package_lock_sha256",
    "sealed_image_tar_sha256",
    "opam_repository_commit",
}


class ToolchainReceiptError(RuntimeError):
    pass


def _sha64_or_none(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _SHA64.fullmatch(value) is None:
        raise ToolchainReceiptError(f"INVALID_{name.upper()}")
    return value


def _sha40_or_none(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise ToolchainReceiptError(f"INVALID_{name.upper()}")
    return value


@dataclass(frozen=True)
class OfflineToolchainReceiptV1:
    schema_version: str
    authority_class: str
    base_image_digest: str
    coq_version: str
    corn_version: str
    ocaml_version: str
    installed_packages_sha256: str
    sealed_image_id: str
    offline_network_mode: str
    offline_coqc_passed: bool
    offline_corn_import_passed: bool
    persistence_class: str
    package_lock_sha256: str | None
    sealed_image_tar_sha256: str | None
    opam_repository_commit: str | None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OfflineToolchainReceiptV1":
        if not isinstance(payload, dict) or set(payload) != _FIELDS:
            raise ToolchainReceiptError("TOOLCHAIN_RECEIPT_SURFACE_MISMATCH")
        if payload["schema_version"] != "AVD-OFFLINE-TOOLCHAIN-V1":
            raise ToolchainReceiptError("TOOLCHAIN_SCHEMA_VERSION_MISMATCH")
        if payload["authority_class"] != "NONE":
            raise ToolchainReceiptError("AUTHORITY_MUST_BE_NONE")
        if payload["base_image_digest"] != _BASE_IMAGE_DIGEST:
            raise ToolchainReceiptError("BASE_IMAGE_DIGEST_MISMATCH")
        if payload["coq_version"] != "8.20.1":
            raise ToolchainReceiptError("COQ_VERSION_MISMATCH")
        if payload["corn_version"] != "9.0.0":
            raise ToolchainReceiptError("CORN_VERSION_MISMATCH")
        if payload["ocaml_version"] != "4.13.1":
            raise ToolchainReceiptError("OCAML_VERSION_MISMATCH")

        packages_digest = payload["installed_packages_sha256"]
        if not isinstance(packages_digest, str) or _SHA64.fullmatch(packages_digest) is None:
            raise ToolchainReceiptError("INVALID_INSTALLED_PACKAGES_SHA256")
        image_id = payload["sealed_image_id"]
        if not isinstance(image_id, str) or _IMAGE_ID.fullmatch(image_id) is None:
            raise ToolchainReceiptError("INVALID_SEALED_IMAGE_ID")
        if payload["offline_network_mode"] != "none":
            raise ToolchainReceiptError("OFFLINE_NETWORK_MODE_NOT_NONE")
        if payload["offline_coqc_passed"] is not True:
            raise ToolchainReceiptError("OFFLINE_COQC_PROBE_NOT_PASSED")
        if payload["offline_corn_import_passed"] is not True:
            raise ToolchainReceiptError("CORN_IMPORT_PROBE_NOT_PASSED")

        persistence = payload["persistence_class"]
        if persistence not in {"EPHEMERAL_RUN_LOCAL", "PERSISTENT_CONTENT_ADDRESSED"}:
            raise ToolchainReceiptError("INVALID_PERSISTENCE_CLASS")

        package_lock = _sha64_or_none("package_lock_sha256", payload["package_lock_sha256"])
        image_tar = _sha64_or_none(
            "sealed_image_tar_sha256", payload["sealed_image_tar_sha256"]
        )
        repo_commit = _sha40_or_none(
            "opam_repository_commit", payload["opam_repository_commit"]
        )

        freeze_material = (package_lock, image_tar, repo_commit)
        if persistence == "PERSISTENT_CONTENT_ADDRESSED" and any(
            value is None for value in freeze_material
        ):
            raise ToolchainReceiptError("PERSISTENT_CLOSURE_MATERIAL_INCOMPLETE")

        return cls(
            schema_version=payload["schema_version"],
            authority_class=payload["authority_class"],
            base_image_digest=payload["base_image_digest"],
            coq_version=payload["coq_version"],
            corn_version=payload["corn_version"],
            ocaml_version=payload["ocaml_version"],
            installed_packages_sha256=packages_digest,
            sealed_image_id=image_id,
            offline_network_mode=payload["offline_network_mode"],
            offline_coqc_passed=True,
            offline_corn_import_passed=True,
            persistence_class=persistence,
            package_lock_sha256=package_lock,
            sealed_image_tar_sha256=image_tar,
            opam_repository_commit=repo_commit,
        )

    @property
    def offline_toolchain_executable(self) -> bool:
        return (
            self.authority_class == "NONE"
            and self.base_image_digest == _BASE_IMAGE_DIGEST
            and self.coq_version == "8.20.1"
            and self.corn_version == "9.0.0"
            and self.ocaml_version == "4.13.1"
            and self.offline_network_mode == "none"
            and self.offline_coqc_passed
            and self.offline_corn_import_passed
        )

    @property
    def frozen_toolchain_closure(self) -> bool:
        return (
            self.offline_toolchain_executable
            and self.persistence_class == "PERSISTENT_CONTENT_ADDRESSED"
            and self.package_lock_sha256 is not None
            and self.sealed_image_tar_sha256 is not None
            and self.opam_repository_commit is not None
        )
