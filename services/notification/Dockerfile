# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

# ---- build: resolve the locked dependencies into a virtualenv ----
FROM python:3.14-slim-bookworm AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first: this layer is cached until pyproject.toml/uv.lock change.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---- runtime: no uv, no build tools, non-root ----
FROM python:3.14-slim-bookworm
# Remove pip/setuptools: nothing installs packages at runtime, and their
# vendored libraries are the main source of CVEs in this base image.
RUN rm -rf /usr/local/lib/python3.*/site-packages/pip* /usr/local/lib/python3.*/site-packages/setuptools* /usr/local/bin/pip* \
 && groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8001

# Run migrations with: ["alembic", "upgrade", "head"]
CMD ["python", "-m", "notification_worker"]
