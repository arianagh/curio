FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/

ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/src

CMD ["uv", "run", "celery", "-A", "curio", "worker", "-l", "info"]
