from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from vetglobal.api.documents import router as documents_router
from vetglobal.api.jobs import router as jobs_router
from vetglobal.api.pets import router as pets_router
from vetglobal.config import Settings, get_settings
from vetglobal.db import create_engine, create_session_factory
from vetglobal.errors import DomainError
from vetglobal.logging import configure_logging
from vetglobal.middleware import RequestBodyLimitMiddleware
from vetglobal.schemas import ErrorResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    logger = configure_logging(resolved_settings.log_level)
    engine = create_engine(resolved_settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        yield
        await engine.dispose()

    app = FastAPI(title="VetGlobal API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        RequestBodyLimitMiddleware, max_bytes=resolved_settings.max_request_body_bytes
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )
    app.include_router(pets_router)
    app.include_router(documents_router)
    app.include_router(jobs_router)

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message},
        )

    @app.middleware("http")
    async def request_logging(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid4())
        started = monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            if request.url.path.startswith("/documents/"):
                response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "elapsed_ms": int((monotonic() - started) * 1000),
                },
            )

    @app.get("/health/live", status_code=status.HTTP_200_OK)
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/health/ready",
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
    )
    async def readiness(request: Request) -> JSONResponse:
        try:
            async with request.app.state.session_factory() as session:
                await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"code": "database_unavailable", "message": "Database is unavailable"},
            )
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})

    return app


app = create_app()
