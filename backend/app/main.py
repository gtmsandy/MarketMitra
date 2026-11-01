from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import (
    get_application_environment,
    get_cors_origins,
    get_database_url,
    get_live_market_poll_interval,
    is_live_market_enabled,
    validate_runtime_config,
)
from app.identity.access import IdentityAccessError, SESSION_COOKIE_NAME
from app.security import RuntimeSecurityMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_config()
    worker = None
    if is_live_market_enabled() and (os.getenv("NEPSE_LIVE_API_URL") or os.getenv("LIVE_MARKET_PROVIDER", "").lower() == "replay"):
        from app.db.base import make_session_factory
        from app.providers.live_adapter import RestPollingLiveProvider
        from app.providers.replay import DevelopmentReplayProvider
        from app.services.live_polling_worker import LivePollingWorker
        provider = DevelopmentReplayProvider() if os.getenv("LIVE_MARKET_PROVIDER", "").lower() == "replay" else RestPollingLiveProvider()
        worker = LivePollingWorker(provider, make_session_factory(get_database_url()), get_live_market_poll_interval())
        if os.getenv("LIVE_MARKET_PROVIDER", "").lower() == "replay":
            import asyncio
            await asyncio.to_thread(worker.poll_cycle)
        await worker.start()
    try:
        yield
    finally:
        if worker is not None:
            await worker.stop()


app = FastAPI(title="MarketMitra API", lifespan=lifespan)


@app.exception_handler(IdentityAccessError)
async def identity_access_error_handler(_, exc: IdentityAccessError) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
    if exc.status_code == 401:
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path="/api/v1",
            httponly=True,
            secure=get_application_environment() == "production",
            samesite="lax",
        )
    return response

app.add_middleware(RuntimeSecurityMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

app.include_router(api_router, prefix="/api/v1")
