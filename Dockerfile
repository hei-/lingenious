# Needs BuildKit (default since Docker 23; otherwise DOCKER_BUILDKIT=1) for the cache mounts.
# Targets: `runtime` (no test tooling; used by web/Dockerfile) and `dev` (adds pytest/ruff; the default).
#   docker build --target runtime -t lingenious:runtime .
FROM python:3.12-slim AS base

# Optional mirrors for slow networks: --build-arg APT_MIRROR=<host> --build-arg PIP_INDEX_URL=<url>
# (Makefile and scripts/run.sh pass them through from env vars of the same name).
ARG APT_MIRROR=""
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s#deb.debian.org#${APT_MIRROR}#g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
      sed -i "s#deb.debian.org#${APT_MIRROR}#g" /etc/apt/sources.list 2>/dev/null || true; \
    fi
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglu1-mesa libxrender1 libxext6 libsm6 libxi6 libfontconfig1 fonts-wqy-microhei
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
WORKDIR /app
# Pinned, hash-checked dependencies (regenerate with `make lock`), then the package itself in editable mode.
COPY requirements.lock pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip pip install --require-hashes -r requirements.lock
COPY . .
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps -e .
ENV PYTHONPATH=/app MPLBACKEND=Agg


FROM base AS runtime
# fixed non-root uid; /app/data is the only writable place besides tmpfs
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data && chown app /app/data
ENV MPLCONFIGDIR=/tmp/mpl XDG_CACHE_HOME=/tmp/.cache
USER app


FROM base AS dev
COPY requirements-dev.lock .
RUN --mount=type=cache,target=/root/.cache/pip pip install --require-hashes -r requirements-dev.lock
