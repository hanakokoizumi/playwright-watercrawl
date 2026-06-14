import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from services import ScraplingService


@pytest.fixture
def integration_client(monkeypatch):
    service = ScraplingService(
        use_stealth=False,
        solve_cloudflare=False,
        load_dom=False,
        retries=1,
        concurrency=2,
    )
    asyncio.run(service.start())
    monkeypatch.setattr("main.service", service)
    return TestClient(app)


@pytest.mark.integration
def test_basic_html(httpserver, integration_client):
    httpserver.expect_request("/").respond_with_data(
        Path("tests/fixtures/site/index.html").read_text(encoding="utf-8"),
        content_type="text/html",
    )
    url = httpserver.url_for("/")
    response = integration_client.post("/html", json={"url": url, "timeout": 30000})
    assert response.status_code == 200
    data = response.json()
    assert data["status_code"] == 200
    assert data["error"] is None
    assert "Fixture" in data["html"]
    assert data["attachments"] == []


@pytest.mark.integration
def test_http_404(httpserver, integration_client):
    httpserver.expect_request("/missing").respond_with_data(
        "not found",
        status=404,
        content_type="text/html",
    )
    url = httpserver.url_for("/missing")
    response = integration_client.post("/html", json={"url": url, "timeout": 30000})
    assert response.status_code == 200
    data = response.json()
    assert data["status_code"] == 404
    assert data["error"] == "Not Found"
    assert data["html"]


@pytest.mark.integration
def test_proxy_null_credentials(integration_client):
    # Contract-only: request must not 422 when proxy has null credentials.
    response = integration_client.post(
        "/html",
        json={
            "url": "https://example.com",
            "timeout": 30000,
            "proxy": {
                "type": "http",
                "host": "127.0.0.1",
                "port": 9,
                "username": None,
                "password": None,
            },
        },
    )
    assert response.status_code != 422


@pytest.mark.integration
def test_cookie_isolation(httpserver, integration_client):
    httpserver.expect_request("/set").respond_with_data(
        """<!DOCTYPE html><html><body>
        <script>document.cookie='sid=abc';</script>
        <span id="marker">set</span></body></html>""",
        content_type="text/html",
    )
    httpserver.expect_request("/check").respond_with_data(
        """<!DOCTYPE html><html><body><span id="marker">clean</span></body></html>""",
        content_type="text/html",
    )
    set_url = httpserver.url_for("/set")
    check_url = httpserver.url_for("/check")

    r1 = integration_client.post("/html", json={"url": set_url, "timeout": 30000})
    r2 = integration_client.post("/html", json={"url": check_url, "timeout": 30000})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert "clean" in r2.json()["html"]


@pytest.mark.integration
def test_watercrawl_payload(httpserver, integration_client):
    httpserver.expect_request("/wc").respond_with_data(
        Path("tests/fixtures/site/index.html").read_text(encoding="utf-8"),
        content_type="text/html",
    )
    payload = {
        "url": httpserver.url_for("/wc"),
        "block_media": False,
        "wait_after_load": 0,
        "timeout": 30000,
        "user_agent": "WaterCrawlTest/1.0",
        "accept_cookies_selector": None,
        "locale": "en-US",
        "extra_headers": {},
        "actions": [],
    }
    response = integration_client.post("/html", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {"url", "html", "status_code", "error", "headers", "attachments"}
    assert data["attachments"] == []
