#!/usr/bin/env bash
# Entrypoint de producción del backend TODOSCARE:
#   1) espera a que Postgres acepte conexiones,
#   2) aplica las migraciones (alembic upgrade head),
#   3) siembra datos demo solo si SEED_ON_START=true (por defecto NO),
#   4) arranca el servidor (el CMD del Dockerfile).
set -euo pipefail

# DATABASE_URL es del tipo postgresql+asyncpg://user:pass@host:port/db.
# Extraemos host y puerto para el sondeo con pg_isready.
db_url="${DATABASE_URL:-}"
host="$(printf '%s' "$db_url" | sed -E 's#.*://[^@]+@([^:/]+).*#\1#')"
port="$(printf '%s' "$db_url" | sed -E 's#.*://[^@]+@[^:/]+:([0-9]+)/.*#\1#')"
host="${host:-db}"
port="${port:-5432}"

echo "[entrypoint] esperando a Postgres en ${host}:${port}…"
for i in $(seq 1 60); do
  if pg_isready -h "$host" -p "$port" >/dev/null 2>&1; then
    echo "[entrypoint] Postgres disponible."
    break
  fi
  sleep 2
  if [ "$i" -eq 60 ]; then
    echo "[entrypoint] ERROR: Postgres no respondió a tiempo." >&2
    exit 1
  fi
done

echo "[entrypoint] aplicando migraciones…"
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "[entrypoint] SEED_ON_START=true → sembrando datos demo…"
  python -m app.seed
fi

echo "[entrypoint] iniciando: $*"
exec "$@"
