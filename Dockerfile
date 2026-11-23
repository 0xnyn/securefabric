# syntax=docker/dockerfile:1.7
#
# One Dockerfile for every app in the workspace. Pick the app with --build-arg:
#
#   docker build --build-arg APP=api    --target runtime -t securefabric-api .
#   docker build --build-arg APP=worker --target runtime -t securefabric-worker .
#
# Targets:
#   dev      - all workspace packages installed *editable* + dev tools; mount the
#              repo at /app and run with --reload / watchfiles for hot reload.
#   runtime  - slim, non-root, only the chosen app and its workspace deps.

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.9.15

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python${PYTHON_VERSION} \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app

# ---------------------------------------------------------------------------
# dev: hot-reload image. Source is bind-mounted over /app at runtime; the venv
# lives in /opt/venv so the mount never hides it.
FROM base AS dev
ENV UV_COMPILE_BYTECODE=0
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --all-packages
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages
CMD ["securefabric-api"]

# ---------------------------------------------------------------------------
# builder: resolve only the chosen app's dependency closure.
FROM base AS builder
ARG APP
RUN test -n "${APP}" || (echo "--build-arg APP=<api|worker> is required" >&2 && exit 1)
# 1) third-party deps only: cached until uv.lock changes
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-workspace --package "securefabric-${APP}"
# 2) workspace packages, installed non-editable so /app source isn't needed at runtime
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package "securefabric-${APP}"

# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime
ARG APP
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    MIGRATIONS_DIR=/app/db/migrations \
    APP_ENTRYPOINT="securefabric-${APP}"
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app db/migrations /app/db/migrations
USER app
LABEL org.opencontainers.image.title="securefabric-${APP}"
# Shell form so ${APP_ENTRYPOINT} expands; exec keeps it PID 1 for signal handling.
CMD ["sh", "-c", "exec ${APP_ENTRYPOINT}"]
