# AGENTS.md

## Cursor Cloud specific instructions

This is a single Python (3.12) FastAPI service: the **WaterCrawl Renderer** that renders pages with Scrapling/Playwright headless Chromium and exposes `POST /html` plus `/health/liveness` and `/health/readiness`. There is no database or other backing service, and no linter is configured. Standard commands live in `README.md` (Development section) and `.github/workflows/test.yml`.

Dependencies (pip deps + Chromium browsers via `scrapling install`) are installed by the startup update script into a virtualenv at `venv/`. Activate it before running anything: `source venv/bin/activate`.

Non-obvious caveats:
- Do NOT create a `.env` from `.env.example` when running tests: `.env.example` sets `AUTH_API_KEY=your-secret-api-key`, and because `main.py` loads `.env` at import time this makes `tests/test_contract.py::test_api_success` fail with 401. CI runs with no `.env`. Only create a `.env` (and set `AUTH_API_KEY`) when you specifically want to exercise API-key auth while running the server.
- Run the dev server with `uvicorn main:app --reload --host 0.0.0.0 --port 8000`. After startup, `/health/readiness` returns 503 until the renderer initializes, then 200.
- Tests: `pytest -m "not integration and not parity_docker" -v` (fast, no browser) and `pytest -m integration -v` (launches real Chromium; uses `pytest-httpserver`). The `parity_docker` marker requires the upstream Docker image and is normally skipped.
- "Build" is Docker-only (`docker compose up --build`); there is no app compile/bundle step for local dev.
