# ─────────────────────── build stage ───────────────────────
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Instala el paquete y sus dependencias en un prefijo aislado que copiamos
# luego a la imagen final (mantiene la imagen runtime pequeña).
RUN pip install --prefix=/install .

# ─────────────────────── runtime stage ───────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Cliente de postgres para el wait-for-db del entrypoint.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /install /usr/local
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Usuario sin privilegios.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/uploads && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# gunicorn con workers uvicorn; el nº de workers se ajusta por env WEB_CONCURRENCY.
ENV WEB_CONCURRENCY=4
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "--timeout", "60", "--graceful-timeout", "30"]
