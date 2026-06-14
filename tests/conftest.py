import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app, service


@pytest.fixture
def client(monkeypatch):
    class _ReadyService:
        is_ready = True

        async def fetch(self, body, default_proxy=None):
            from models import CrawlResponse

            return CrawlResponse(
                url=body.url,
                html="<html><body>ok</body></html>",
                status_code=200,
                error=None,
                headers={},
                attachments=[],
            )

    ready = _ReadyService()
    monkeypatch.setattr("main.service", ready)
    return TestClient(app)


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 0)
