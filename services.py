import asyncio
import base64
import logging
import time
from typing import Any

from scrapling.fetchers import DynamicFetcher, StealthyFetcher

from error import get_error
from models import (
    ActionType,
    Attachment,
    AttachmentType,
    CrawlRequest,
    CrawlResponse,
)
from utils import parse_proxy_env

logger = logging.getLogger(__name__)

BROWSER_EXTRA_FLAGS = ["--no-sandbox", "--disable-dev-shm-usage"]


async def _remove_sec_ch_ua(route):
    headers = {
        key: value
        for key, value in route.request.headers.items()
        if not key.lower().startswith("sec-ch-ua")
    }
    await route.continue_(headers=headers)


async def _page_setup_chromium(page):
    await page.route("**/*", _remove_sec_ch_ua)


def _normalize_cred(value: str | None) -> str:
    return value if value is not None else ""


def _format_proxy(body: CrawlRequest, default_proxy: str | None) -> dict | None:
    if body.proxy:
        return {
            "server": f"{body.proxy.type}://{body.proxy.host}:{body.proxy.port}",
            "username": _normalize_cred(body.proxy.username),
            "password": _normalize_cred(body.proxy.password),
        }
    if default_proxy:
        server, username, password = parse_proxy_env(default_proxy)
        return {
            "server": server,
            "username": _normalize_cred(username),
            "password": _normalize_cred(password),
        }
    return None


def _build_extra_headers(body: CrawlRequest) -> dict[str, str] | None:
    headers = dict(body.extra_headers or {})
    if body.user_agent:
        headers["User-Agent"] = body.user_agent
    if body.locale:
        headers.setdefault("Accept-Language", body.locale)
    return headers or None


def _build_page_action(
    body: CrawlRequest,
    attachments: list[Attachment],
    html_capture: list[str],
):
    async def page_action(page):
        try:
            if body.wait_after_load:
                await page.wait_for_timeout(body.wait_after_load)

            try:
                scroll_height = await page.evaluate(
                    """() => {
                    const step = 50;
                    setInterval(() => window.scrollBy(0, step), 10);
                    return document.body ? document.body.scrollHeight : 0;
                }"""
                )
                await page.wait_for_timeout(scroll_height / 5)
            except Exception:
                logger.exception("Scroll step failed for %s", body.url)

            if body.accept_cookies_selector:
                try:
                    element = await page.wait_for_selector(
                        body.accept_cookies_selector, timeout=2000
                    )
                    await element.click()
                except Exception:
                    pass

            for action in body.actions:
                try:
                    if action.type == ActionType.SCREENSHOT:
                        content = await page.screenshot(full_page=True)
                        attachments.append(
                            Attachment(
                                type=AttachmentType.SCREENSHOT,
                                content=base64.b64encode(content).decode("utf-8"),
                            )
                        )
                    elif action.type == ActionType.PDF:
                        content = await page.pdf()
                        attachments.append(
                            Attachment(
                                type=AttachmentType.PDF,
                                content=base64.b64encode(content).decode("utf-8"),
                            )
                        )
                except Exception:
                    logger.exception("Failed to run action %s", action.type)
        finally:
            try:
                html_capture.append(await page.content())
            except Exception:
                logger.exception("Failed to capture page content for %s", body.url)

    return page_action


def _compute_timeout(body: CrawlRequest, use_stealth: bool, solve_cloudflare: bool) -> int:
    timeout = body.timeout
    scroll_budget = max(body.wait_after_load, 0) + 5000
    timeout = max(timeout, scroll_budget)
    if use_stealth and solve_cloudflare:
        timeout = max(timeout, 60_000)
    return timeout


class ScraplingService:
    """One-off Scrapling Fetcher renderer with per-request browser isolation."""

    def __init__(
        self,
        *,
        use_stealth: bool = False,
        solve_cloudflare: bool = False,
        load_dom: bool = False,
        retries: int = 1,
        concurrency: int = 3,
    ):
        self._use_stealth = use_stealth
        self._solve_cloudflare = solve_cloudflare
        self._load_dom = load_dom
        self._retries = retries
        self._semaphore = asyncio.Semaphore(concurrency)
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def start(self) -> None:
        self._ready = True
        logger.info(
            "Scrapling renderer configured (stealth=%s, solve_cloudflare=%s, load_dom=%s, retries=%s)",
            self._use_stealth,
            self._solve_cloudflare,
            self._load_dom,
            self._retries,
        )

    async def stop(self) -> None:
        self._ready = False

    def _build_common_fetch_kwargs(
        self,
        body: CrawlRequest,
        default_proxy: str | None,
        attachments: list[Attachment],
        html_capture: list[str],
    ) -> dict[str, Any]:
        return {
            "headless": True,
            "timeout": _compute_timeout(body, self._use_stealth, self._solve_cloudflare),
            "wait": 0,
            "proxy": _format_proxy(body, default_proxy),
            "extra_headers": _build_extra_headers(body),
            "disable_resources": body.block_media,
            "page_action": _build_page_action(body, attachments, html_capture),
            "page_setup": _page_setup_chromium,
            "google_search": False,
            "network_idle": False,
            "load_dom": self._load_dom,
            "retries": self._retries,
            "extra_flags": BROWSER_EXTRA_FLAGS,
            "useragent": body.user_agent,
            "locale": body.locale,
        }

    async def fetch(
        self, body: CrawlRequest, default_proxy: str | None = None
    ) -> CrawlResponse:
        if not self._ready:
            raise RuntimeError("Scrapling renderer is not ready")

        attachments: list[Attachment] = []
        html_capture: list[str] = []
        fetch_kwargs = self._build_common_fetch_kwargs(
            body, default_proxy, attachments, html_capture
        )

        started = time.monotonic()
        async with self._semaphore:
            if self._use_stealth:
                response = await StealthyFetcher.async_fetch(
                    body.url,
                    solve_cloudflare=self._solve_cloudflare,
                    **fetch_kwargs,
                )
            else:
                response = await DynamicFetcher.async_fetch(body.url, **fetch_kwargs)

        html = html_capture[0] if html_capture else str(response.html_content)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "Fetched %s status=%s stealth=%s proxy=%s elapsed_ms=%s",
            body.url,
            response.status,
            self._use_stealth,
            bool(fetch_kwargs.get("proxy")),
            elapsed_ms,
        )

        return CrawlResponse(
            url=body.url,
            html=html,
            status_code=response.status,
            error=get_error(response.status),
            headers=dict(response.headers) if response.headers else {},
            attachments=attachments,
        )
