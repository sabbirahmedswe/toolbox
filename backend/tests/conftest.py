import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def leftover_workdirs():
    """Returns a function listing ilovepdf temp dirs created since the test started."""
    tmp = Path(tempfile.gettempdir())
    before = set(tmp.glob("ilovepdf-*"))
    return lambda: set(tmp.glob("ilovepdf-*")) - before
