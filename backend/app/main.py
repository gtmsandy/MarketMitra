from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_cors_origins


app = FastAPI(title="MarketMitra API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=[],
)

app.include_router(api_router, prefix="/api/v1")
