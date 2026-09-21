#!/usr/bin/env python3
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "tactical" / "src" / "hooks" / "useOperationsSources.ts"
COMPONENT = ROOT / "tactical" / "src" / "components" / "SourcesCoverage.tsx"
APP = ROOT / "tactical" / "src" / "App.tsx"
BRIDGE = ROOT / "sovereign-omega-v2" / "python" / "bridge.py"


class TacticalSourcesContract(unittest.TestCase):
    def setUp(self) -> None:
        self.hook = HOOK.read_text(encoding="utf-8")
        self.component = COMPONENT.read_text(encoding="utf-8")
        self.app = APP.read_text(encoding="utf-8")
        self.bridge = BRIDGE.read_text(encoding="utf-8")

    def test_hook_reads_exact_read_only_endpoint(self) -> None:
        self.assertIn("/platform/operations/sources", self.hook)
        self.assertIn("method: 'GET'", self.hook)
        self.assertIn("cache: 'no-store'", self.hook)
        self.assertNotIn("method: 'POST'", self.hook)

    def test_hook_enforces_epistemic_boundary(self) -> None:
        required = (
            "AEGIS_OPERATIONS_CENTER_SOURCES_V1",
            "SOURCE_AUTHORITY_ESCALATION",
            "INCOMPLETE_SELECTED_SAMPLE",
            "SOURCE_CATALOGUE_COMPLETENESS_INVALID",
            "SOURCE_LEGACY_LABEL_CONTRACT_MISMATCH",
            "SOURCE_PRIMARY_CARD_CONTRACT_MISMATCH",
            "SHOW_INVALID_OR_STALE; DO_NOT_FALL_BACK_TO_COMPLETE_INVENTORY_CLAIM",
            "SOURCE_FAIL_CLOSED_CONTRACT_MISMATCH",
            "SOURCE_PROJECTION_ROOT_INVALID",
        )
        for token in required:
            self.assertIn(token, self.hook)

    def test_all_semantic_source_errors_fail_closed(self) -> None:
        self.assertIn("const semanticFailure = message.startsWith('SOURCE_')", self.hook)
        self.assertIn("semanticFailure ? 'INVALID_OR_STALE' : 'OFFLINE'", self.hook)

    def test_frontend_does_not_embed_current_evidence_counts(self) -> None:
        combined = self.hook + "\n" + self.component + "\n" + self.app
        for literal in ("1163",):
            self.assertNotIn(literal, combined)
        # Standalone 38/24/23 values may occur in unrelated CSS class text only if
        # surrounded by non-digits; reject numeric literals in executable source.
        for number in ("38", "24", "23"):
            self.assertIsNone(
                re.search(rf"(?<![A-Za-z0-9_]){number}(?![A-Za-z0-9_])", combined),
                f"frontend embeds evidence value {number}",
            )

    def test_component_has_no_legacy_completeness_fallback(self) -> None:
        self.assertIn("LEGACY_COMPLETENESS_FALLBACK_DISABLED", self.component)
        self.assertNotIn("38 arhiva + Git", self.component)
        self.assertIn("payload.cards.map", self.component)

    def test_app_wires_sources_between_infrastructure_and_main_grid(self) -> None:
        self.assertIn("useOperationsSources()", self.app)
        self.assertIn("<SourcesCoverage sources={sources} />", self.app)
        bridge_status = self.app.index("<BridgeStatus health={health} />")
        sources = self.app.index("<SourcesCoverage sources={sources} />")
        main_grid = self.app.index("{/* Main grid */}")
        self.assertLess(bridge_status, sources)
        self.assertLess(sources, main_grid)

    def test_bridge_and_tactical_share_endpoint(self) -> None:
        endpoint = "/platform/operations/sources"
        self.assertIn(endpoint, self.hook)
        self.assertIn(endpoint, self.bridge)


if __name__ == "__main__":
    unittest.main(verbosity=2)
