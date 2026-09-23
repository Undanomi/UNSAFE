FROM ghcr.io/astral-sh/uv:0.8 AS uv

FROM python:3.13-slim AS rockyou

ARG ROCKYOU_URL="https://gitlab.com/kalilinux/packages/wordlists/-/raw/7d461801f64424c8a5004238f07c2ece584e647b/rockyou.txt.gz"
ARG ROCKYOU_SHA256="ded2d962815e1256df8f3a0d25173c4b21b6eee636117c36999246725a6d8f9f"

ADD --checksum=sha256:${ROCKYOU_SHA256} ${ROCKYOU_URL} /tmp/rockyou.txt.gz
RUN install -d -m 0755 /wordlists \
    && python -c "import gzip, shutil; source=gzip.open('/tmp/rockyou.txt.gz', 'rb'); target=open('/wordlists/rockyou.txt', 'wb'); shutil.copyfileobj(source, target); source.close(); target.close()" \
    && test -s /wordlists/rockyou.txt

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY --from=rockyou --chown=10001:10001 /wordlists/rockyou.txt ./data/rockyou.txt
RUN uv sync --frozen --no-dev \
    && install -d -o 10001 -g 10001 -m 0750 /var/lib/slsg/scenarios

USER 10001:10001
EXPOSE 8000 8001

CMD ["uvicorn", "ai_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
