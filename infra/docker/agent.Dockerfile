FROM python:3.12.7-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /usr/local/bin/uv
WORKDIR /app
COPY agent/pyproject.toml agent/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY agent/ ./
COPY contracts/ ./contracts/
RUN uv sync --frozen --no-dev

FROM python:3.12.7-slim
RUN useradd -m -u 10001 app
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 HOME=/home/app
USER app
# Download VAD / turn-detector weights at build time so the first call is not slow.
RUN python -m voice_agent.worker download-files
CMD ["python", "-m", "voice_agent.worker", "start"]
