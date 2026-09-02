from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AVD00AnchorV1:
    anchor_commit_sha: str
    anchor_tree_sha: str
    pr_base_sha: str
    git_parent_sha: str
    red_workflow_run: int
    red_artifact_id: int
    red_artifact_sha256: str
    red_failure_mode: str
    coq_toolchain_image_digest: str
    action_wrapper_image_sha256: str
    toolchain_spec: str
    canonical_coq_logical_path: str
    target_production_file: str
    authority_class: str = "NONE"


AVD00_ANCHOR = AVD00AnchorV1(
    anchor_commit_sha="d98ef00c6d65b45e253aa13eeebb6f9b1f256009",
    anchor_tree_sha="8fa6cc600d75cd78a518a8b5b08cfb9f4e665c30",
    pr_base_sha="88b7b937b90719cc4e05ddca2aa2bcff2894e443",
    git_parent_sha="16769820d37616d319cdee8ad9954d0fda086715",
    red_workflow_run=33584236075,
    red_artifact_id=9829698647,
    red_artifact_sha256="2fb0028dbd763d63430327e93e14747c31b8a882b85a3da2fa008fca04e8db8d",
    red_failure_mode="EXPECTED_RED_MISSING_PRODUCTION_MODULE",
    coq_toolchain_image_digest="sha256:18ebf3da56e60e3ddfd7d4e51f4c53d10241a129f34e93dacbc71562dd43c57a",
    action_wrapper_image_sha256="sha256:d91b890b752567147dc9232a75923c8ca0af9477d6b1663a0d60ca94f3768a84",
    toolchain_spec="Coq 8.20.1 / CoRN 9.0.0 / OCaml 4.13.1",
    canonical_coq_logical_path='-Q sovereign-omega-v2/formal/theories/Weil ""',
    target_production_file="sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v",
)
