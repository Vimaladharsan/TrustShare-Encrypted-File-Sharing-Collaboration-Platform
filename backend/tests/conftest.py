"""Shared test setup. Tests run against the real databases:
docker compose exec backend pytest
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # Using TestClient as a context manager runs the app's startup/shutdown (DB connections).
    with TestClient(app) as test_client:
        yield test_client
