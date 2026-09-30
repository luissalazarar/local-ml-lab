FROM python:3.12.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 \
    OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --home-dir /app --create-home app \
    && mkdir -p /data/db /data/uploads /data/datasets /data/preflights /data/runs /data/logs /data/tmp \
    && chown -R 10001:10001 /data /app
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/
COPY backend/pyproject.toml backend/uv.lock* ./
ARG UV_INSECURE_HOST
RUN uv sync --frozen --no-dev
COPY backend/src ./src
COPY backend/alembic.ini ./alembic.ini
COPY backend/src/local_ml_lab/db/migrations ./src/local_ml_lab/db/migrations
COPY examples ./examples
COPY --chmod=755 docker/api-entrypoint.sh docker/worker-entrypoint.sh /usr/local/bin/
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["api-entrypoint.sh"]
