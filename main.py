"""
FastAPI service that renders web pages through Scrapling and returns HTML.
"""
import logging
import os
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from models import CrawlRequest, CrawlResponse, HealthResponse
from services import ScraplingService

load_dotenv()

logger = logging.getLogger(__name__)

service: ScraplingService | None = None

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
AUTH_API_KEY = os.environ.get("AUTH_API_KEY")
DEFAULT_PROXY = os.environ.get("DEFAULT_PROXY") or None
ENGINE = os.environ.get("ENGINE", "chromium")

SCRAPLING_STEALTH = os.environ.get("SCRAPLING_STEALTH", "false").lower() in (
    "1",
    "true",
    "yes",
)
SCRAPLING_SOLVE_CLOUDFLARE = os.environ.get(
    "SCRAPLING_SOLVE_CLOUDFLARE", "false"
).lower() in ("1", "true", "yes")
SCRAPLING_LOAD_DOM = os.environ.get("SCRAPLING_LOAD_DOM", "false").lower() in (
    "1",
    "true",
    "yes",
)
SCRAPLING_RETRIES = int(os.environ.get("SCRAPLING_RETRIES", "1"))
SCRAPLING_CONCURRENCY = int(os.environ.get("SCRAPLING_CONCURRENCY", "3"))

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Depends(api_key_header)):
    if not AUTH_API_KEY:
        return True
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if api_key != AUTH_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return True


async def startup_event():
    global service
    if ENGINE not in ("chromium",):
        logger.warning(
            "ENGINE=%s is deprecated. Scrapling uses Chromium only; ignoring.",
            ENGINE,
        )
    service = ScraplingService(
        use_stealth=SCRAPLING_STEALTH,
        solve_cloudflare=SCRAPLING_SOLVE_CLOUDFLARE,
        load_dom=SCRAPLING_LOAD_DOM,
        retries=SCRAPLING_RETRIES,
        concurrency=SCRAPLING_CONCURRENCY,
    )
    await service.start()
    logger.info(
        "Scrapling renderer ready (stealth=%s, solve_cloudflare=%s, load_dom=%s, "
        "retries=%s, concurrency=%s, engine=%s)",
        SCRAPLING_STEALTH,
        SCRAPLING_SOLVE_CLOUDFLARE,
        SCRAPLING_LOAD_DOM,
        SCRAPLING_RETRIES,
        SCRAPLING_CONCURRENCY,
        ENGINE,
    )


async def shutdown_event():
    global service
    if service:
        await service.stop()
        service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()
    yield
    await shutdown_event()


app = FastAPI(lifespan=lifespan)


@app.get("/health/liveness", response_model=HealthResponse)
def liveness_probe():
    return JSONResponse(content={"status": "ok"}, status_code=200)


@app.get("/health/readiness", response_model=HealthResponse)
async def readiness_probe():
    if service and service.is_ready:
        return JSONResponse(content={"status": "ok"}, status_code=200)
    return JSONResponse(content={"status": "Service Unavailable"}, status_code=503)


@app.post("/html", response_model=CrawlResponse, dependencies=[Depends(verify_api_key)])
async def fetch_html(body: CrawlRequest):
    if not service or not service.is_ready:
        return JSONResponse(
            content={"error": "Scrapling renderer is not ready"},
            status_code=503,
        )
    try:
        return await service.fetch(body, default_proxy=DEFAULT_PROXY)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse(content={"error": str(exc)}, status_code=500)
