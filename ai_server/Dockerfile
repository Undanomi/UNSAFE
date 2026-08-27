FROM ghcr.io/astral-sh/uv:0.8 AS uv

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev \
    && install -d -o 10001 -g 10001 -m 0750 /var/lib/slsg/scenarios

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "ai_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
