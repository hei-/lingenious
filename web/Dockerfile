# Multi-stage: build the React UI, then ship it with the Python backend (runtime deps only, no pytest/ruff).
# Build from the repo root:  docker build -f web/Dockerfile -t lingenious-web .
# Needs BuildKit (default in Docker >= 23; with older engines set DOCKER_BUILDKIT=1) for the cache mounts.
# Multi-arch: `make web-multiarch` (linux/amd64 + linux/arm64). The runtime stage copies explicit paths only
# (no docs/, tests/, eval/, adapters/, web/landing, node, *.md): see the COPY lines below.
# the UI bundle is architecture-independent: build it natively even when cross-building the image
FROM --platform=$BUILDPLATFORM node:25-slim AS ui
WORKDIR /ui
COPY web/ui/package.json web/ui/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY web/ui/ .
RUN npm run build

FROM python:3.12-slim
ARG APT_MIRROR=""
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s#deb.debian.org#${APT_MIRROR}#g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
    fi
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglu1-mesa libxrender1 libxext6 libsm6 libxi6 libfontconfig1 fonts-wqy-microhei
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
WORKDIR /app
# dependency layer: only changes when requirements.lock changes
COPY requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install --require-hashes -r requirements.lock
# application: only what the server runs (the package is used in place via PYTHONPATH; no `pip install -e .` needed)
COPY pyproject.toml config.yaml ./
COPY core core
COPY web/__init__.py web/__init__.py
COPY web/server web/server
COPY examples examples
COPY --from=ui /ui/dist web/ui/dist
RUN find /app -name __pycache__ -prune -exec rm -rf {} +

# fixed non-root uid; /app/data is the only writable path besides tmpfs (/tmp)
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data && chown app /app/data
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg LINGENIOUS_DATA=/app/data MPLCONFIGDIR=/tmp/mpl XDG_CACHE_HOME=/tmp/.cache
USER app
VOLUME /app/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
CMD ["uvicorn", "web.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
