from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import CrawlRequest, CrawlResponse
from services import ScraplingService, _build_page_action


@pytest.mark.asyncio
async def test_fetch_uses_html_content_fallback():
    service = ScraplingService(use_stealth=False, load_dom=False, retries=1, concurrency=1)
    await service.start()

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.headers = {}
    mock_response.html_content = "<html><body>fallback</body></html>"

    with patch(
        "services.DynamicFetcher.async_fetch",
        new=AsyncMock(return_value=mock_response),
    ) as mock_fetch:
        result = await service.fetch(CrawlRequest(url="https://example.com"))

    mock_fetch.assert_awaited_once()
    kwargs = mock_fetch.await_args.kwargs
    assert kwargs["google_search"] is False
    assert kwargs["load_dom"] is False
    assert kwargs["retries"] == 1
    assert isinstance(result, CrawlResponse)
    assert "fallback" in result.html
    assert result.attachments == []


@pytest.mark.asyncio
async def test_stealth_fetch_passes_solve_cloudflare_and_timeout():
    service = ScraplingService(
        use_stealth=True,
        solve_cloudflare=True,
        load_dom=False,
        retries=1,
        concurrency=1,
    )
    await service.start()

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.headers = {}
    mock_response.html_content = "<html></html>"

    with patch(
        "services.StealthyFetcher.async_fetch",
        new=AsyncMock(return_value=mock_response),
    ) as mock_fetch:
        await service.fetch(CrawlRequest(url="https://example.com", timeout=15000))

    kwargs = mock_fetch.await_args.kwargs
    assert kwargs["solve_cloudflare"] is True
    assert kwargs["timeout"] >= 60_000


@pytest.mark.asyncio
async def test_page_action_captures_content_in_finally():
    body = CrawlRequest(url="https://example.com")
    attachments = []
    html_capture: list[str] = []
    action = _build_page_action(body, attachments, html_capture)

    class FakePage:
        async def wait_for_timeout(self, _):
            return None

        async def evaluate(self, _):
            return 100

        async def content(self):
            return "<html><body>captured</body></html>"

    await action(FakePage())
    assert html_capture == ["<html><body>captured</body></html>"]
