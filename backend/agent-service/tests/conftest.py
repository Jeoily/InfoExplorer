"""Normal tests must never inherit opt-in model credentials or enable cloud calls."""
import pytest


@pytest.fixture(autouse=True)
def disable_cloud_generation(monkeypatch, tmp_path):
    monkeypatch.setenv('INFOEXPLORER_EXECUTION_DIR', str(tmp_path/'execution-control'))
    monkeypatch.setenv("INFOEXPLORER_MODEL_ENABLED", "false")
    monkeypatch.setenv("INFOEXPLORER_WEB_ENABLED", "false")
