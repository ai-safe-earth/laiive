# Build context is services/ (not this directory) so the laiive-shared
# dependency at ../shared resolves inside the image.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY shared /shared
COPY pusher /app
WORKDIR /app

# --no-dev drops the test deps; --no-editable copies laiive-shared into the venv
# instead of leaving a .pth pointing at /shared.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# uv is a build tool and has no business in the runtime layer.
FROM python:3.13-slim-bookworm

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=build --chown=10001:10001 /app /app
WORKDIR /app
USER 10001

EXPOSE 8003

# See the retriever Dockerfile for why this is the venv's own interpreter rather
# than `uv run`, and why the listener comes from laiive_shared.serve.
CMD ["/app/.venv/bin/python", "-m", "laiive_shared.serve", "agent.api:app", "8003", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-graceful-shutdown", "110"]
