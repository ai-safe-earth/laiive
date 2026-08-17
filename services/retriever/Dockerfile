# Build context is services/ (not this directory) so the laiive-shared
# dependency at ../shared resolves inside the image.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY shared /shared
COPY retriever /app
WORKDIR /app

# --no-dev drops pytest and friends; --no-editable copies laiive-shared into the
# venv instead of leaving a .pth pointing at /shared, so the runtime stage needs
# no source tree but its own.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# uv is a build tool and has no business in the runtime layer.
FROM python:3.13-slim-bookworm

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=build --chown=10001:10001 /app /app
WORKDIR /app
USER 10001

EXPOSE 8002

# The venv's uvicorn directly, not `uv run`: uv re-resolves at start (which fails
# under a read-only root filesystem) and would sit between PID 1 and the signal
# uvicorn needs to drain gracefully. Graceful shutdown is set just under the
# pod's terminationGracePeriodSeconds so uvicorn always finishes first.
CMD ["/app/.venv/bin/uvicorn", "agent.api:app", \
     "--host", "0.0.0.0", "--port", "8002", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-graceful-shutdown", "110"]
