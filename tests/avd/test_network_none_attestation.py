from __future__ import annotations

import pytest

from scripts.avd.network_none_attestation import (
    NetworkNoneAttestationError,
    NetworkNoneAttestationV1,
)


def test_network_none_attestation_requires_exact_pinned_isolation_evidence() -> None:
    att = NetworkNoneAttestationV1.from_dict({
        "schema_version": "AVD-NETWORK-NONE-ATTESTATION-V1",
        "authority_class": "NONE",
        "toolchain_image_digest": "sha256:18ebf3da56e60e3ddfd7d4e51f4c53d10241a129f34e93dacbc71562dd43c57a",
        "docker_network_mode": "none",
        "docker_networks_empty": True,
        "eth0_absent": True,
    })
    assert att.os_network_none_attested is True


def test_network_none_attestation_rejects_bridge_mode_or_network_attachment() -> None:
    base = {
        "schema_version": "AVD-NETWORK-NONE-ATTESTATION-V1",
        "authority_class": "NONE",
        "toolchain_image_digest": "sha256:18ebf3da56e60e3ddfd7d4e51f4c53d10241a129f34e93dacbc71562dd43c57a",
        "docker_network_mode": "none",
        "docker_networks_empty": True,
        "eth0_absent": True,
    }
    with pytest.raises(NetworkNoneAttestationError, match="NETWORK_MODE_NOT_NONE"):
        NetworkNoneAttestationV1.from_dict({**base, "docker_network_mode": "bridge"})
    with pytest.raises(NetworkNoneAttestationError, match="NETWORK_ATTACHMENT_PRESENT"):
        NetworkNoneAttestationV1.from_dict({**base, "docker_networks_empty": False})
    with pytest.raises(NetworkNoneAttestationError, match="ETH0_PRESENT"):
        NetworkNoneAttestationV1.from_dict({**base, "eth0_absent": False})
