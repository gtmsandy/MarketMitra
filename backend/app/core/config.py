import os


DEFAULT_CORS_ORIGIN = "http://localhost:5173"


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGIN)
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
