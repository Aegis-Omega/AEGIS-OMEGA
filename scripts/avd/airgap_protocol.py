from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .hermetic_guard import HermeticBoundaryError, HermeticBoundaryGuard


class AirgapViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class AirgapTrialContract:
    workspace_root: Path
    target_relative_path: str
    fresh_clean_room_context: bool
    external_repo_tools_disabled: bool
    candidate_network_mode: str

    def preflight(self, *, probe_network: bool = True) -> dict[str, object]:
        guard = HermeticBoundaryGuard(self.workspace_root)
        try:
            guard.assert_workspace_clean()
            guard.assert_context_clean(
                fresh_clean_room=self.fresh_clean_room_context,
                external_repo_tools_disabled=self.external_repo_tools_disabled,
            )
            guard.assert_anchor_target_absent(self.target_relative_path)
            if self.candidate_network_mode != "NONE":
                raise HermeticBoundaryError("CANDIDATE_NETWORK_MODE_NOT_NONE")
            if probe_network:
                guard.assert_network_blocked()
        except HermeticBoundaryError as exc:
            raise AirgapViolation(str(exc)) from exc

        return {
            "workspace_git_metadata_absent": True,
            "candidate_network_mode": "NONE",
            "fresh_clean_room_context": True,
            "external_repo_tools_disabled": True,
            "future_solution_absent_at_start": True,
        }
