import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from mip_api.config import get_settings
from mip_api.routes import router
from mip_api.search import SearchService
from mip_observability import REQUEST_COUNT, REQUEST_LATENCY, metrics_response, setup_logging

_search_service: SearchService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _search_service
    settings = get_settings()
    setup_logging(settings.log_level)
    _search_service = SearchService()
    await _search_service.ensure_indices()
    yield
    if _search_service:
        await _search_service.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Market Intelligence Platform API",
        version="0.1.0",
        description="Public-data market intelligence platform REST API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        start = time.monotonic()
        response: Response = await call_next(request)
        duration = time.monotonic() - start
        endpoint = request.url.path
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Trace-Id"] = trace_id
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "service": settings.app_name}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(metrics_response(), media_type="text/plain")

    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "mip_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":
    run()
