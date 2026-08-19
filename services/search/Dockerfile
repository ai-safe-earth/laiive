# Build context is services/ (not this directory) so the laiive-shared
# dependency at ../shared resolves inside the image.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY shared /shared
COPY search /app
WORKDIR /app

# --no-group flows keeps Prefect (and its transitive OTel/apprise tree) out of the
# API image; the flows run elsewhere. --no-dev drops the test deps, --no-editable
# copies laiive-shared into the venv rather than pointing a .pth at /shared.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --no-group flows

# uv is a build tool and has no business in the runtime layer.
FROM python:3.13-slim-bookworm

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=build --chown=10001:10001 /app /app
WORKDIR /app
USER 10001

EXPOSE 8004

# A sweep runs for minutes, so this graceful window is much wider than the other
# services' — it must sit just under the pod's terminationGracePeriodSeconds (420).
# See the retriever Dockerfile for laiive_shared.serve.
CMD ["/app/.venv/bin/python", "-m", "laiive_shared.serve", "agent.api:app", "8004", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-graceful-shutdown", "410"]
