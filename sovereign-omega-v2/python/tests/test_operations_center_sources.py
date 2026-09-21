from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "python" / "operations_center_sources.py"
DATA_PATH = ROOT / "python" / "operations_center_sources_v1.json"
BRIDGE_PATH = ROOT / "python" / "bridge.py"
DOCKERFILE_PATH = ROOT / "Dockerfile"


def load_module():
    spec = importlib.util.spec_from_file_location("operations_center_sources", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load operations_center_sources")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_projection_loads_and_is_authority_neutral():
    mod = load_module()
    payload = mod.load_operations_center_sources()
    assert payload["schema"] == "AEGIS_OPERATIONS_CENTER_SOURCES_V1"
    assert payload["authority_effect"] == "NONE"
    assert payload["projection_root"] == mod.projection_root(payload)
    assert [card["value"] for card in payload["cards"]] == [38, 1163, 24, 23]
    assert len(payload["findings"]) == 24
    assert len(payload["unsurfaced_paths"]) == 23


def test_runtime_response_is_200_for_valid_projection():
    mod = load_module()
    code, payload = mod.response_payload()
    assert code == 200
    assert payload["authority_effect"] == "NONE"
    assert payload["consumer_contract"]["legacy_label_to_replace"] == "38 arhiva + Git"


def test_missing_projection_fails_closed_to_503():
    mod = load_module()
    with TemporaryDirectory() as tmp:
        missing = Path(tmp) / "missing.json"
        with pytest.raises(mod.OperationsCenterSourcesError, match="SOURCES_PROJECTION_UNAVAILABLE"):
            mod.load_operations_center_sources(missing)


def test_tampered_projection_is_rejected_even_if_json_is_valid():
    mod = load_module()
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    payload["cards"][0]["value"] = 39

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "tampered.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(
            mod.OperationsCenterSourcesError,
            match="SOURCES_PROJECTION_ROOT_MISMATCH",
        ):
            mod.load_operations_center_sources(path)


def test_authority_escalation_is_rejected_with_recomputed_projection_root():
    mod = load_module()
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    payload["authority_effect"] = "ADMIT"
    payload["projection_root"] = mod.projection_root(payload)

    with pytest.raises(
        mod.OperationsCenterSourcesError,
        match="SOURCES_AUTHORITY_ESCALATION",
    ):
        mod.validate_projection(payload)


def test_bridge_exposes_only_read_only_sources_route():
    source = BRIDGE_PATH.read_text(encoding="utf-8")
    assert "elif self.path == '/platform/operations/sources':" in source
    assert "code, payload = _operations_sources_response()" in source
    assert "self._platform_respond(code, payload)" in source
    assert "38 arhiva + Git" in source
    assert "do_POST" in source
    # The new route itself must be in do_GET, before the next GET branch.
    get_index = source.index("def do_GET(self):")
    route_index = source.index("elif self.path == '/platform/operations/sources':")
    calibration_index = source.index("elif self.path == '/platform/calibration':")
    assert get_index < route_index < calibration_index


def test_cloud_run_image_includes_runtime_projection():
    source = DOCKERFILE_PATH.read_text(encoding="utf-8")
    assert "COPY python/ ./python/" in source
    assert "WORKDIR /app/python" in source
    assert 'CMD ["python", "bridge.py"]' in source
