from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "python"


def test_python_requirements_pin_agents_sdk_and_pydantic_major():
    text = (PYTHON / "requirements.txt").read_text()
    assert "openai-agents>=0.19.0,<0.20.0" in text
    assert "pydantic>=2.12.2,<3" in text


def test_cloud_run_uses_omega_bridge_entrypoint():
    text = (ROOT / "Dockerfile").read_text()
    assert 'CMD ["python", "omega_bridge.py"]' in text
