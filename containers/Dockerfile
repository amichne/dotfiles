# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.9@sha256:8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff AS uv
FROM node:26.0.0-bookworm-slim@sha256:3529ef69feecddd94e9c5ecd3d25a96f2f23ea40661f494f932ae2b12ab1977c

COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update \
    && apt-get install --yes --no-install-recommends bash ca-certificates git neovim shellcheck zsh \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PROJECT_ENVIRONMENT=/opt/dotfiles-venv \
    UV_PYTHON=3.12.14 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_PROGRESS=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    UV_PYTHON_DOWNLOADS=automatic uv python install 3.12.14
COPY pyproject.toml uv.lock .python-version /opt/dependencies/
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --locked --project /opt/dependencies \
    && chmod -R a+rX /opt/python /opt/dotfiles-venv \
    && useradd --uid 10001 --no-create-home --home-dir /work/home sandbox

ENV HOME=/work/home \
    XDG_CONFIG_HOME=/work/home/.config \
    XDG_DATA_HOME=/work/home/.local/share \
    XDG_STATE_HOME=/work/home/.local/state \
    XDG_CACHE_HOME=/work/home/.cache \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_OFFLINE=1 \
    GIT_CONFIG_NOSYSTEM=1 \
    GIT_CONFIG_GLOBAL=/dev/null \
    DOTFILES_SANDBOX=1
USER 10001:10001
WORKDIR /work
CMD ["sleep", "infinity"]
