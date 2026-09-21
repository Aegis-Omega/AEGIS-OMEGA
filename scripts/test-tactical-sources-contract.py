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
EXECUTION_HOOK = ROOT / "tactical" / "src" / "hooks" / "useExecution.ts"
ENVELOPE = ROOT / "tactical" / "src" / "lib" / "platformEnvelope.ts"
PLATFORM_CONTRACT = ROOT / "packages" / "shared" / "lib" / "platform-contract.ts"


class TacticalSourcesContract(unittest.TestCase):
    def setUp(self) -> None:
        self.hook = HOOK.read_text(encoding="utf-8")
        self.component = COMPONENT.read_text(encoding="utf-8")
        self.app = APP.read_text(encoding="utf-8")
        self.bridge = BRIDGE.read_text(encoding="utf-8")
        self.execution_hook = EXECUTION_HOOK.read_text(encoding="utf-8")
        self.envelope = ENVELOPE.read_text(encoding="utf-8")
        self.platform_contract = PLATFORM_CONTRACT.read_text(encoding="utf-8")

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
            "SOURCE_FINDING_INVALID",
        )
        for token in required:
            self.assertIn(token, self.hook)

    def test_sources_uses_canonical_platform_envelope(self) -> None:
        self.assertIn("parsePlatformEnvelope<OperationsSourcesPayload>", self.hook)
        self.assertIn("parsePlatformEnvelope<OperationsSourcesUnavailable>", self.hook)
        self.assertIn("PLATFORM_CONTRACT_VERSION", self.envelope)
        self.assertIn("OperationsSourcesPayload", self.platform_contract)
        self.assertIn("OperationsSourcesUnavailable", self.platform_contract)
        self.assertIn("_platform_envelope(eid, payload)", self.bridge)

    def test_execution_init_reads_stream_url_from_envelope_data(self) -> None:
        self.assertIn("parsePlatformEnvelope<ExecutionInitResult>", self.execution_hook)
        self.assertIn("envelope.data.execution_id", self.execution_hook)
        self.assertIn("envelope.data.stream_url", self.execution_hook)
        self.assertIn("PLATFORM_EXECUTION_ID_MISMATCH", self.execution_hook)
        self.assertIn("PLATFORM_STREAM_URL_MISSING", self.execution_hook)
        self.assertNotIn("data.stream_url", self.execution_hook)

    def test_all_semantic_source_errors_fail_closed(self) -> None:
        self.assertIn("const semanticFailure = message.startsWith('SOURCE_')", self.hook)
        self.assertIn("semanticFailure ? 'INVALID_OR_STALE' : 'OFFLINE'", self.hook)

    def test_frontend_does_not_embed_current_evidence_counts(self) -> None:
        combined = self.hook + "\n" + self.component + "\n" + self.app
        self.assertNotIn("1163", combined)
        # 38 is allowed exactly once as the legacy label that must be replaced;
        # it may not appear as an independent numeric source value.
        without_legacy_label = combined.replace("38 arhiva + Git", "")
        for number in ("38", "24", "23"):
            self.assertIsNone(
                re.search(rf"(?<![A-Za-z0-9_]){number}(?![A-Za-z0-9_])", without_legacy_label),
                f"frontend embeds evidence value {number}",
            )

    def test_component_has_no_legacy_completeness_fallback(self) -> None:
        self.assertIn("LEGACY_COMPLETENESS_FALLBACK_DISABLED", self.component)
        self.assertNotIn("38 arhiva + Git", self.component)
        self.assertIn("payload.cards.map", self.component)

    def test_component_surfaces_dynamic_findings_and_paths(self) -> None:
        self.assertIn("COVERAGE_GROUPS ({payload.findings.length})", self.component)
        self.assertIn("NO_COUNTERPART_PATHS ({payload.unsurfaced_paths.length})", self.component)
        self.assertIn("findings.map", self.component)
        self.assertIn("payload.unsurfaced_paths.map", self.component)
        self.assertIn("finding.priority === 'P0'", self.component)
        self.assertNotIn("ECCF", self.component)
        self.assertNotIn("supabase/functions/grant-access/index.ts", self.component)

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
