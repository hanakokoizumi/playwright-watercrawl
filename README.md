# WaterCrawl Renderer Service (Scrapling)

A FastAPI-based web service that uses [Scrapling](https://github.com/d4vinci/Scrapling) to fetch and process web content. It keeps the WaterCrawl `/html` API contract for drop-in use with [watercrawl](https://github.com/watercrawl/watercrawl).

## Features

- Per-request Scrapling one-off rendering (`DynamicFetcher` / `StealthyFetcher`) with cookie isolation
- Optional stealth mode and Cloudflare solving for anti-bot sites
- Optional API key authentication
- Proxy support (including WaterCrawl `username`/`password: null` payloads)
- Media blocking, cookie-banner clicks, screenshot/PDF actions
- Docker image based on `ghcr.io/d4vinci/scrapling` (no redundant Chromium install layer)

## Quick Start

### Using Docker Compose

```bash
git clone https://github.com/hanakokoizumi/playwright-watercrawl.git
cd playwright-watercrawl
cp .env.example .env
docker compose up --build
```

The service listens on `http://localhost:8000`. API docs: `http://localhost:8000/docs`

### Using GHCR Image

```bash
docker pull ghcr.io/hanakokoizumi/playwright-watercrawl:latest
docker run -p 8000:8000 -e AUTH_API_KEY=your-secret-key ghcr.io/hanakokoizumi/playwright-watercrawl:latest
```

On first use, set the GitHub package `playwright-watercrawl` to **public**, or authenticate with a PAT that has `read:packages`.

## API

### Health Checks

- `GET /health/liveness`
- `GET /health/readiness`

### HTML Fetching

- `POST /html`

```json
{
  "url": "https://example.com",
  "proxy": {
    "type": "http",
    "host": "proxy.example.com",
    "port": 8080,
    "username": "user",
    "password": "pass"
  },
  "block_media": true,
  "wait_after_load": 1000,
  "timeout": 15000,
  "user_agent": "custom-user-agent",
  "locale": "en-US",
  "accept_cookies_selector": "#accept-cookies",
  "extra_headers": {
    "Custom-Header": "value"
  },
  "actions": [
    {"type": "screenshot"},
    {"type": "pdf"}
  ]
}
```

Authentication (when `AUTH_API_KEY` is set):

```bash
curl -X POST http://localhost:8000/html \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{"url": "https://example.com"}'
```

## Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
playwright install-deps chromium
scrapling install
uvicorn main:app --reload
pytest -m "not integration"
pytest -m integration
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_API_KEY` | API key for authentication | None (disabled) |
| `PORT` | Server port | `8000` |
| `HOST` | Server host | `0.0.0.0` |
| `SCRAPLING_STEALTH` | Use `StealthyFetcher` (`true`/`false`) | `false` |
| `SCRAPLING_SOLVE_CLOUDFLARE` | Enable Cloudflare solving (stealth only) | `false` |
| `SCRAPLING_LOAD_DOM` | Wait for extra DOM stability | `false` |
| `SCRAPLING_RETRIES` | Scrapling fetch retries per request | `1` |
| `SCRAPLING_CONCURRENCY` | Max concurrent browser fetches | `3` |
| `ENGINE` | Deprecated; only `chromium` is supported | `chromium` |
| `DEFAULT_PROXY` | Default proxy URI for all requests | None |
| `PYTHONUNBUFFERED` | Python unbuffered output | `1` |

### WaterCrawl integration notes

- Set `PLAYWRIGHT_API_KEY` in WaterCrawl to match `AUTH_API_KEY` on this service.
- When `SCRAPLING_STEALTH=true` and `SCRAPLING_SOLVE_CLOUDFLARE=true`, increase WaterCrawl `page_options.timeout` to at least `60000` ms. The WaterCrawl middleware uses `timeout/1000` as its httpx client timeout (default 15s), which is too short for Cloudflare challenges.
- Replace the WaterCrawl compose image with `ghcr.io/hanakokoizumi/playwright-watercrawl:2.0.1` (or `latest`) after publishing.

## Publishing

Tag a release to build and push to GHCR:

```bash
git tag v2.0.0
git push origin v2.0.0
```

Image: `ghcr.io/hanakokoizumi/playwright-watercrawl:<tag>`

## License

MIT — see [LICENSE](LICENSE).
