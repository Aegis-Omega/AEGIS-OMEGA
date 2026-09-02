from __future__ import annotations

import socket
from pathlib import Path


class HermeticBoundaryError(RuntimeError):
    pass


class HermeticBoundaryGuard:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()

    def assert_workspace_clean(self) -> None:
        if not self.workspace_root.is_dir():
            raise HermeticBoundaryError("WORKSPACE_NOT_DIRECTORY")
        for path in self.workspace_root.rglob("*"):
            if ".git" in path.relative_to(self.workspace_root).parts:
                raise HermeticBoundaryError("GIT_METADATA_PRESENT")
            if path.is_symlink():
                raise HermeticBoundaryError("WORKSPACE_SYMLINK_PRESENT")

    def assert_anchor_target_absent(self, target_relative_path: str) -> None:
        target = (self.workspace_root / target_relative_path).resolve()
        try:
            target.relative_to(self.workspace_root)
        except ValueError as exc:
            raise HermeticBoundaryError("TARGET_PATH_ESCAPES_WORKSPACE") from exc
        if target.exists():
            raise HermeticBoundaryError("FUTURE_SOLUTION_PRESENT_IN_BASELINE")

    @staticmethod
    def assert_context_clean(*, fresh_clean_room: bool, external_repo_tools_disabled: bool) -> None:
        if not fresh_clean_room:
            raise HermeticBoundaryError("PARTICIPANT_CONTEXT_CONTAMINATED")
        if not external_repo_tools_disabled:
            raise HermeticBoundaryError("EXTERNAL_REPOSITORY_TOOLS_ENABLED")

    @staticmethod
    def assert_network_blocked(timeout_seconds: float = 0.25) -> None:
        """Best-effort runtime proof that candidate sandbox egress is blocked.

        The authoritative benchmark workflow should run this inside an OS-level
        network namespace/container configured with no network. This probe is a
        falsifier for accidental egress, not a substitute for the isolation
        primitive itself.
        """
        probes = [("1.1.1.1", 443), ("8.8.8.8", 53)]
        for host, port in probes:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_seconds)
            try:
                if sock.connect_ex((host, port)) == 0:
                    raise HermeticBoundaryError("NETWORK_EGRESS_AVAILABLE")
            finally:
                sock.close()
        try:
            socket.getaddrinfo("github.com", 443)
        except OSError:
            return
        raise HermeticBoundaryError("DNS_RESOLUTION_AVAILABLE")
