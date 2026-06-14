import json

import pytest
from pydantic import ValidationError

from models import CrawlRequest, CrawlResponse, ProxyModel
from services import _format_proxy, _normalize_cred


def test_proxy_model_accepts_null_credentials():
    proxy = ProxyModel(
        type="http",
        host="proxy.example.com",
        port=8080,
        username=None,
        password=None,
    )
    assert proxy.username is None
    assert proxy.password is None


def test_crawl_request_watercrawl_proxy_payload():
    payload = {
        "url": "https://example.com",
        "block_media": False,
        "wait_after_load": 500,
        "timeout": 15000,
        "user_agent": "Mozilla/5.0",
        "accept_cookies_selector": None,
        "locale": "en-US",
        "extra_headers": {},
        "actions": [],
        "proxy": {
            "type": "http",
            "host": "proxy.example.com",
            "port": "8080",
            "username": None,
            "password": None,
        },
    }
    req = CrawlRequest(**payload)
    assert req.proxy.port == 8080


def test_crawl_response_attachments_never_null():
    resp = CrawlResponse(
        url="https://example.com",
        html="<html></html>",
        status_code=200,
        headers={},
    )
    data = json.loads(resp.model_dump_json())
    assert data["attachments"] == []


def test_format_proxy_normalizes_null_credentials():
    body = CrawlRequest(
        url="https://example.com",
        proxy=ProxyModel(
            type="http",
            host="p.example.com",
            port=8080,
            username=None,
            password=None,
        ),
    )
    proxy = _format_proxy(body, None)
    assert proxy == {
        "server": "http://p.example.com:8080",
        "username": "",
        "password": "",
    }


def test_normalize_cred():
    assert _normalize_cred(None) == ""
    assert _normalize_cred("user") == "user"


def test_api_success(client):
    response = client.post("/html", json={"url": "https://example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["html"]
    assert data["attachments"] == []


def test_readiness_ok(client):
    response = client.get("/health/readiness")
    assert response.status_code == 200
