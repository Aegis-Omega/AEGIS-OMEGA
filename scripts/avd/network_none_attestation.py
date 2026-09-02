from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


class NetworkNoneAttestationError(RuntimeError):
    pass


_EXPECTED_KEYS = {
    "schema_version",
    "authority_class",
    "toolchain_image_digest",
    "docker_network_mode",
    "docker_networks_empty",
    "eth0_absent",
}
_EXPECTED_TOOLCHAIN = "sha256:18ebf3da56e60e3ddfd7d4e51f4c53d10241a129f34e93dacbc71562dd43c57a"


@dataclass(frozen=True)
class NetworkNoneAttestationV1:
    schema_version: str
    authority_class: str
    toolchain_image_digest: str
    docker_network_mode: str
    docker_networks_empty: bool
    eth0_absent: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetworkNoneAttestationV1":
        if not isinstance(data, dict) or set(data) != _EXPECTED_KEYS:
            raise NetworkNoneAttestationError("NETWORK_NONE_SCHEMA_MISMATCH")
        if data["schema_version"] != "AVD-NETWORK-NONE-ATTESTATION-V1":
            raise NetworkNoneAttestationError("NETWORK_NONE_SCHEMA_VERSION_MISMATCH")
        if data["authority_class"] != "NONE":
            raise NetworkNoneAttestationError("NETWORK_NONE_AUTHORITY_NOT_NONE")
        if data["toolchain_image_digest"] != _EXPECTED_TOOLCHAIN:
            raise NetworkNoneAttestationError("TOOLCHAIN_IMAGE_DIGEST_MISMATCH")
        if data["docker_network_mode"] != "none":
            raise NetworkNoneAttestationError("NETWORK_MODE_NOT_NONE")
        if data["docker_networks_empty"] is not True:
            raise NetworkNoneAttestationError("NETWORK_ATTACHMENT_PRESENT")
        if data["eth0_absent"] is not True:
            raise NetworkNoneAttestationError("ETH0_PRESENT")
        return cls(**data)

    @property
    def os_network_none_attested(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
