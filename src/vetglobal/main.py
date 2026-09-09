from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from vetglobal.api.pets import router as pets_router
from vetglobal.config import Settings, get_settings
from vetglobal.db import create_engine, create_session_factory
from vetglobal.schemas import ErrorResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
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
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )
    app.include_router(pets_router)

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
