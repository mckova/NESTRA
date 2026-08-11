FROM python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

WORKDIR /app
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY src ./src
COPY schemas ./schemas
COPY openapi ./openapi

RUN groupadd --system nestra \
  && useradd --system --gid nestra --home-dir /nonexistent --shell /usr/sbin/nologin nestra \
  && mkdir -p /data \
  && chown -R nestra:nestra /app /data

USER nestra
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    NESTRA_STORE_DIR=/data
EXPOSE 8787
CMD ["python", "-m", "nestra", "serve", "--host", "0.0.0.0", "--port", "8787"]
