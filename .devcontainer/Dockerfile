FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Install git and other dev tools
RUN apt-get update && apt-get install -y \
    git \
    make \
    curl \
    nano \
    vim \
    procps \
    lsof \
    net-tools \
    psmisc \
    && rm -rf /var/lib/apt/lists/*

# Install pre-commit
RUN pip install pre-commit pytest
# Set working directory
WORKDIR /workspace

# Ensure uv is available in PATH
ENV PATH="/root/.local/bin:$PATH"

# Keep container running
CMD ["sleep", "infinity"]
