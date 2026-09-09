FROM ghcr.io/astral-sh/uv:0.9.26 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

RUN uv sync --locked --no-dev

CMD ["uv", "run", "--no-sync", "uvicorn", "vetglobal.main:app", "--host", "0.0.0.0", "--port", "8000"]
